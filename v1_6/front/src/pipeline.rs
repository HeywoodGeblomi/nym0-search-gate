//! Decision logic: hard holds, then optional worker, then explicit ALLOW.
//! Pure functions so `replay` can recompute byte-identical output from the logged worker answer.
use crate::json::{esc, opt_str};
use crate::policy::{self, Record, SessionState, Stage};

#[derive(Debug, Clone, PartialEq)]
pub enum Worker {
    NotAsked,
    Ok(Option<String>, String),
    Failed(String),
    Unavailable(String),
    InputError(String),
}
impl Worker {
    pub fn to_json(&self) -> String {
        match self {
            Worker::NotAsked => "{\"status\":\"none\"}".into(),
            Worker::Ok(f, r) => format!("{{\"status\":\"ok\",\"final\":{},\"reason\":\"{}\"}}", opt_str(f.as_deref()), esc(r)),
            Worker::Failed(m) => format!("{{\"status\":\"failed\",\"msg\":\"{}\"}}", esc(m)),
            Worker::Unavailable(m) => format!("{{\"status\":\"unavailable\",\"msg\":\"{}\"}}", esc(m)),
            Worker::InputError(m) => format!("{{\"status\":\"input_error\",\"msg\":\"{}\"}}", esc(m)),
        }
    }
    pub fn from_json(v: &crate::json::V) -> Option<Worker> {
        let st = v.get("status")?.as_str()?;
        let msg = || v.get("msg").and_then(|m| m.as_str()).unwrap_or("").to_string();
        Some(match st {
            "none" => Worker::NotAsked,
            "ok" => Worker::Ok(v.get("final").and_then(|f| f.as_str()).map(|s| s.to_string()), v.get("reason").and_then(|m| m.as_str()).unwrap_or("").to_string()),
            "failed" => Worker::Failed(msg()),
            "unavailable" => Worker::Unavailable(msg()),
            "input_error" => Worker::InputError(msg()),
            _ => return None,
        })
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum Clf {
    NotAsked,
    Ok { score: f64, hold: bool, threshold: f64, instr: String, mapc: String, mapm: String, mapx: String, relax: String },
    Failed(String),
    Unavailable(String),
}
impl Clf {
    pub fn to_json(&self) -> String {
        match self {
            Clf::NotAsked => "{\"status\":\"none\"}".into(),
            Clf::Ok { score, hold, threshold, instr, mapc, mapm, mapx, relax } => format!(
                "{{\"status\":\"ok\",\"score\":{:.10},\"hold\":{},\"threshold\":{:.10},\"instr\":\"{}\",\"mapc\":\"{}\",\"mapm\":\"{}\",\"mapx\":\"{}\",\"relax\":\"{}\"}}",
                score, hold, threshold, esc(instr), esc(mapc), esc(mapm), esc(mapx), esc(relax)
            ),
            Clf::Failed(m) => format!("{{\"status\":\"failed\",\"msg\":\"{}\"}}", esc(m)),
            Clf::Unavailable(m) => format!("{{\"status\":\"unavailable\",\"msg\":\"{}\"}}", esc(m)),
        }
    }
    pub fn from_json(v: &crate::json::V) -> Option<Clf> {
        let st = v.get("status")?.as_str()?;
        let msg = || v.get("msg").and_then(|m| m.as_str()).unwrap_or("").to_string();
        Some(match st {
            "none" => Clf::NotAsked,
            "ok" => {
                let score = v.get("score")?.as_f64()?;
                let hold = v.get("hold").and_then(|h| h.as_bool()).unwrap_or(false);
                let threshold = v.get("threshold").and_then(|s| s.as_f64()).unwrap_or(f64::NAN);
                let instr = v.get("instr").and_then(|m| m.as_str()).unwrap_or("").to_string();
                let mapc = v.get("mapc").and_then(|m| m.as_str()).unwrap_or("").to_string();
                let mapm = v.get("mapm").and_then(|m| m.as_str()).unwrap_or("").to_string();
                let mapx = v.get("mapx").and_then(|m| m.as_str()).unwrap_or("").to_string();
                let relax = v.get("relax").and_then(|m| m.as_str()).unwrap_or("").to_string();
                Clf::Ok { score, hold, threshold, instr, mapc, mapm, mapx, relax }
            }
            "failed" => Clf::Failed(msg()),
            "unavailable" => Clf::Unavailable(msg()),
            _ => return None,
        })
    }
}

fn clip(s: &str, n: usize) -> String { if s.chars().count() <= n { s.to_string() } else { format!("{}...", s.chars().take(n).collect::<String>()) } }

/// True if this final string must never be emitted.
pub fn is_forbidden_final(s: &str) -> bool {
    if s == "FIRE_WEAPON" { return true; }
    policy::is_dangerous(&policy::norm_tool(s))
}

pub fn finish(why: &str, w: &Worker, rec: &Record, st: &SessionState) -> (Option<String>, &'static str, String) {
    // Re-check hard holds; they always win.
    if let Some((layer, reason)) = policy::hard_hold(rec, st) {
        return (None, layer, format!("hard hold after worker path: {} | deferred: {}", reason, why));
    }
    match w {
        Worker::Ok(f, r) => match f.as_deref() {
            Some(a) if is_forbidden_final(a) => (None, "worker", format!("worker said {}; the pipeline never outputs it, held back | deferred: {}", a, why)),
            Some(a) => {
                let n = policy::norm_tool(a);
                let expected = policy::norm_tool(&rec.proposed_tool);
                if n != expected {
                    return (None, "held_worker_failed", format!("worker answered '{}', which is not the proposed tool, held back | deferred: {}", clip(a, 40), why));
                }
                (Some(rec.proposed_tool.clone()), "worker", format!("policy worker: {} | deferred: {}", clip(r, 200), why))
            }
            None => (None, "worker", format!("policy worker held: {} | deferred: {}", clip(r, 200), why)),
        },
        Worker::Failed(m) | Worker::Unavailable(m) => (None, "held_worker_failed", format!("worker not usable, held back ({}) | deferred: {}", clip(m, 120), why)),
        Worker::NotAsked => (None, "held_worker_failed", format!("worker was not asked, held back | deferred: {}", why)),
        Worker::InputError(m) => (None, "held_input_error", format!("unusable input line, held back ({})", clip(m, 120))),
    }
}

/// Hold-only classifier layer H12. If fin is already None, this is a no-op.
pub fn apply_h12(rec: &Record, fin: Option<String>, layer: &'static str, reason: String, clf: &Clf) -> (Option<String>, &'static str, String, Clf) {
    if fin.is_none() {
        return (None, layer, reason, Clf::NotAsked);
    }
    let span = policy::classifier_span(rec);
    if span.is_empty() {
        return (fin, layer, reason, Clf::NotAsked);
    }
    match clf {
        Clf::NotAsked => (None, "held_classifier_failed", format!("classifier was not asked, held back | prior: {}", reason), clf.clone()),
        Clf::Ok { score, hold, threshold, instr, mapc, mapm: _, mapx: _, relax } => {
            if !score.is_finite() {
                return (None, "held_classifier_failed", format!("classifier score is not a finite number, held back | prior: {}", reason), clf.clone());
            }
            if !relax.is_empty() {
                // v1.6: how-to page waiver. The worker found a how-to page with nothing aimed at an agent. It waives only the classifier, instruction-check and map holds.
                // Hard holds, the allow-list, fail-safe holds and a worker that is not usable are decided before or outside this arm and are never lifted.
                return (fin, layer, reason, clf.clone());
            }
            let over = if threshold.is_finite() { *score >= *threshold } else { *hold };
            if *hold || over {
                (None, "classifier", format!("classifier hold (score {:.4}, threshold {:.4}) | prior: {}", score, threshold, reason), clf.clone())
            } else if !instr.is_empty() {
                // v1.3: hold-only instruction check (OR with the classifier). It can add a hold, never lift one.
                (None, "instruction_check", format!("instruction check hold ({}) | prior: {}", clip(instr, 160), reason), clf.clone())
            } else if !mapc.is_empty() {
                // v1.4: hold-only verb meaning map check (OR with the classifier and the instruction check). It can add a hold, never lift one.
                (None, "meaning_map", format!("meaning map hold ({}) | prior: {}", clip(mapc, 160), reason), clf.clone())
            } else {
                (fin, layer, reason, clf.clone())
            }
        }
        Clf::Failed(m) | Clf::Unavailable(m) => {
            (None, "held_classifier_failed", format!("classifier not usable, held back ({}) | prior: {}", clip(m, 120), reason), clf.clone())
        }
    }
}

pub fn out_json(id: &str, fin: Option<&str>, layer: &str, reason: &str) -> String {
    let decision = if fin.is_some() { "allow" } else { "hold" };
    format!("{{\"id\":\"{}\",\"decision\":\"{}\",\"final\":{},\"label\":\"{}\",\"layer\":\"{}\",\"reason\":\"{}\"}}",
        esc(id), decision, opt_str(fin), fin.unwrap_or("NO_ACTION"), layer, esc(reason))
}

pub struct Full { pub out: String, pub fast_kind: &'static str, pub fast_why: String, pub fin: Option<String>, pub layer: &'static str }

pub fn recompute(rec: &Record, w: &Worker, st: &SessionState, clf: &Clf) -> Full {
    if let Worker::InputError(_) = w {
        let (fin, layer, reason) = finish("", w, rec, st);
        return Full { out: out_json(&rec.id, fin.as_deref(), layer, &reason), fast_kind: "none", fast_why: String::new(), fin, layer };
    }
    match policy::fast_stage(rec, st) {
        Stage::Hold { layer, reason } => Full { out: out_json(&rec.id, None, layer, &reason), fast_kind: "settled", fast_why: reason, fin: None, layer },
        Stage::Allow { layer, reason } => {
            let (fin, layer, reason, _) = apply_h12(rec, Some(rec.proposed_tool.clone()), layer, reason, clf);
            Full { out: out_json(&rec.id, fin.as_deref(), layer, &reason), fast_kind: "settled", fast_why: reason, fin, layer }
        }
        Stage::Ask { why } => {
            let (fin, layer, reason) = finish(&why, w, rec, st);
            let (fin, layer, reason, _) = apply_h12(rec, fin, layer, reason, clf);
            Full { out: out_json(&rec.id, fin.as_deref(), layer, &reason), fast_kind: "fallback", fast_why: why, fin, layer }
        }
    }
}
