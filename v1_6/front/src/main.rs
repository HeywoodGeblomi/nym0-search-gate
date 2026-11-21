//! nym0asgate -- Nym-0 Agent Safety Gate v1 command line (standard library only).
//!   nym0asgate batch [IN.jsonl] [--out FILE] [--log LOG] [--sandbox DIR] [--timing FILE]
//!   nym0asgate stream [--log LOG] [--sandbox DIR]
//!   nym0asgate replay LOG
//!   nym0asgate verify LOG
//!   nym0asgate worker start|stop|status
//!   nym0asgate log-update LOG SEQ | log-delete LOG SEQ     always refused: the log is insert-only
//! flags: --sock PATH  --clf-sock PATH  --weights PATH  --root DIR  --no-restart  --no-classifier  --worker-timeout-ms N  --clf-timeout-ms N  --start-wait-s N  --no-emit
//! Session memory is kept in this process and rebuilt from the log on replay.
mod classifier; mod gate; mod json; mod log; mod mapcheck; mod pipeline; mod policy; mod sandbox; mod sha256; mod worker;
use json::esc;
use pipeline::{recompute, Worker, Clf};
use policy::SessionState;
use std::collections::HashMap;
use std::io::{self, BufRead, BufWriter, Write};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

fn now_ms() -> u128 { SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_millis()).unwrap_or(0) }
fn median(v: &mut Vec<f64>) -> Option<f64> { if v.is_empty() { None } else { v.sort_by(|a, b| a.partial_cmp(b).unwrap()); Some(v[v.len() / 2]) } }
fn jf(x: Option<f64>) -> String { x.map_or("null".into(), |v| format!("{:.3}", v)) }

struct Engine {
    client: worker::Client,
    clf: classifier::Client,
    log: Option<log::Log>,
    timing: Option<BufWriter<std::fs::File>>,
    sandbox: PathBuf,
    emit: bool,
    fast_us: Vec<f64>,
    fb_ms: Vec<f64>,
    layers: std::collections::BTreeMap<&'static str, u64>,
    n: u64,
    acts: u64,
    sessions: HashMap<String, SessionState>,
}

impl Engine {
    fn process(&mut self, raw: &str, idx: u64) -> String {
        let t0 = Instant::now();
        self.n += 1;
        let parsed = policy::parse_record(raw, idx);
        let (rec, worker, fast_kind, fast_why, fin, layer, out, dec_ns);
        let mut clf_ans = Clf::NotAsked;
        let mut session_before = SessionState::default();
        match parsed {
            Err(m) => {
                let id = idx.to_string();
                let dummy = policy::empty_record(id, raw.to_string());
                worker = Worker::InputError(m);
                let f = recompute(&dummy, &worker, &session_before, &Clf::NotAsked);
                dec_ns = t0.elapsed().as_nanos();
                rec = dummy; fast_kind = f.fast_kind; fast_why = f.fast_why; fin = f.fin; layer = f.layer; out = f.out;
            }
            Ok(r) => {
                rec = r;
                session_before = self.sessions.get(&rec.session_id).cloned().unwrap_or_default();
                match policy::fast_stage(&rec, &session_before) {
                    policy::Stage::Hold { layer: la, reason } => {
                        out = pipeline::out_json(&rec.id, None, la, &reason);
                        dec_ns = t0.elapsed().as_nanos();
                        worker = Worker::NotAsked; fast_kind = "settled"; fast_why = reason; fin = None; layer = la;
                    }
                    policy::Stage::Allow { layer: la, reason } => {
                        let span = policy::classifier_span(&rec);
                        clf_ans = if span.is_empty() { Clf::NotAsked } else { self.clf.classify(&rec.id, &span).0 };
                        let (fi, la, reason2, c2) = pipeline::apply_h12(&rec, Some(rec.proposed_tool.clone()), la, reason, &clf_ans);
                        clf_ans = c2;
                        out = pipeline::out_json(&rec.id, fi.as_deref(), la, &reason2);
                        dec_ns = t0.elapsed().as_nanos();
                        worker = Worker::NotAsked; fast_kind = "settled"; fast_why = reason2; fin = fi; layer = la;
                    }
                    policy::Stage::Ask { why } => {
                        let rec_json = policy::record_to_json(&rec);
                        let sess_json = session_before.to_json();
                        let (w, ms) = self.client.ask(&rec.id, &rec_json, &sess_json);
                        if let Some(ms) = ms { if matches!(w, Worker::Ok(..)) { self.fb_ms.push(ms); } }
                        let (fi, la, reason) = pipeline::finish(&why, &w, &rec, &session_before);
                        let span = policy::classifier_span(&rec);
                        clf_ans = if fi.is_none() || span.is_empty() { Clf::NotAsked } else { self.clf.classify(&rec.id, &span).0 };
                        let (fi, la, reason, c2) = pipeline::apply_h12(&rec, fi, la, reason, &clf_ans);
                        clf_ans = c2;
                        out = pipeline::out_json(&rec.id, fi.as_deref(), la, &reason);
                        dec_ns = 0;
                        worker = w; fast_kind = "fallback"; fast_why = why; fin = fi; layer = la;
                    }
                }
            }
        }
        *self.layers.entry(layer).or_insert(0) += 1;
        if fin.is_some() { self.acts += 1; }
        if self.emit {
            if let Some(ref tool) = fin {
                if let Err(m) = sandbox::emit(&self.sandbox, &rec.id, tool, &rec.proposed_args) {
                    eprintln!("emit refused: {}", m);
                }
            }
        }
        if dec_ns > 0 && layer == "fast" { self.fast_us.push(dec_ns as f64 / 1000.0); }
        let evs: Vec<String> = self.client.events.drain(..).collect();
        let mut session_after = session_before.clone();
        policy::update_session(&mut session_after, &rec, layer);
        if let Some(lg) = self.log.as_mut() {
            for e in &evs { if let Err(m) = lg.append("event", now_ms(), &format!("\"event\":\"{}\"", esc(e))) { eprintln!("{}", m); } }
            let fields = format!(
                "\"id\":\"{}\",\"record\":{},\"fast\":\"{}\",\"fast_why\":\"{}\",\"session_before\":{},\"session_after\":{},\"worker\":{},\"classifier\":{},\"out\":{}",
                esc(&rec.id), policy::record_to_json(&rec), fast_kind, esc(&fast_why),
                session_before.to_json(), session_after.to_json(), worker.to_json(), clf_ans.to_json(), out
            );
            match lg.append("decision", now_ms(), &fields) {
                Ok(()) => { session_after.last_hash = lg.prev_hash().to_string(); }
                Err(m) => { eprintln!("{}", m); }
            }
        } else {
            for e in &evs { eprintln!("[worker] {}", e); }
        }
        self.sessions.insert(rec.session_id.clone(), session_after);
        if let Some(t) = self.timing.as_mut() {
            writeln!(t, "{{\"id\":\"{}\",\"session_id\":\"{}\",\"layer\":\"{}\",\"decide_us\":{:.3},\"total_us\":{:.3}}}", esc(&rec.id), esc(&rec.session_id), layer, dec_ns as f64 / 1000.0, t0.elapsed().as_nanos() as f64 / 1000.0).ok();
        }
        let _ = (fin, dec_ns);
        out
    }
    fn summary(&mut self, wall_s: f64) -> String {
        let layers: Vec<String> = self.layers.iter().map(|(k, v)| format!("\"{}\":{}", k, v)).collect();
        format!("{{\"lines\":{},\"acts\":{},\"sessions\":{},\"by_layer\":{{{}}},\"fast_decide_median_us\":{},\"fallback_roundtrip_median_ms\":{},\"fallback_answered\":{},\"wall_s_inside_driver\":{:.3}}}",
            self.n, self.acts, self.sessions.len(), layers.join(","), jf(median(&mut self.fast_us)), jf(median(&mut self.fb_ms)), self.fb_ms.len(), wall_s)
    }
}

struct Opts { args: Vec<String> }
impl Opts {
    fn flag(&mut self, name: &str) -> bool { if let Some(i) = self.args.iter().position(|a| a == name) { self.args.remove(i); true } else { false } }
    fn val(&mut self, name: &str) -> Option<String> { if let Some(i) = self.args.iter().position(|a| a == name) { if i + 1 < self.args.len() { let v = self.args.remove(i + 1); self.args.remove(i); return Some(v); } } None }
}

fn find_root(o: &mut Opts) -> PathBuf {
    if let Some(r) = o.val("--root") { return PathBuf::from(r); }
    let exe = std::env::current_exe().unwrap_or_default();
    exe.parent().and_then(|p| p.parent()).map(|p| p.to_path_buf()).unwrap_or_else(|| PathBuf::from("."))
}
fn make_client(o: &mut Opts, root: &Path, no_restart: bool) -> worker::Client {
    let sock = o.val("--sock").map(PathBuf::from).or_else(|| std::env::var("NYM0ASGATE_SOCK").ok().map(PathBuf::from).or_else(|| std::env::var("NYM0CLGATE_SOCK").ok().map(PathBuf::from))).unwrap_or_else(|| root.join("run").join("worker.sock"));
    let mut c = worker::Client::new(sock, root.to_path_buf());
    if no_restart { c.autostart = false; }
    if let Some(ms) = o.val("--worker-timeout-ms").and_then(|v| v.parse::<u64>().ok()) { c.timeout = Duration::from_millis(ms); }
    if let Some(s) = o.val("--start-wait-s").and_then(|v| v.parse::<u64>().ok()) { c.start_wait = Duration::from_secs(s); }
    c
}
fn make_classifier(o: &mut Opts, root: &Path, no_restart: bool) -> classifier::Client {
    let sock = o.val("--clf-sock").map(PathBuf::from).or_else(|| std::env::var("NYM0ASGATE_CLF_SOCK").ok().map(PathBuf::from).or_else(|| std::env::var("NYM0CLGATE_CLF_SOCK").ok().map(PathBuf::from))).unwrap_or_else(|| root.join("run").join("classifier.sock"));
    let weights = o.val("--weights").map(PathBuf::from).unwrap_or_else(|| root.join("models").join("classifier_v1.json"));
    let mut c = classifier::Client::new(sock, root.to_path_buf(), weights);
    // D5 fix, taken from Injection Classifier Layer v2: --no-restart also disables classifier autostart.
    if no_restart { c.autostart = false; }
    if o.flag("--no-classifier") { c.autostart = false; }
    if let Some(m) = o.val("--map-engine") { c.map_rust = m != "python"; }
    if let Some(ms) = o.val("--clf-timeout-ms").and_then(|v| v.parse::<u64>().ok()) { c.timeout = Duration::from_millis(ms); }
    c
}
fn make_engine(o: &mut Opts, root: &Path, mode: &str) -> Result<Engine, String> {
    let no_emit = o.flag("--no-emit");
    let no_restart = o.flag("--no-restart");
    let sandbox = o.val("--sandbox").map(PathBuf::from).unwrap_or_else(|| root.join("sandbox"));
    let client = make_client(o, root, no_restart);
    let clf = make_classifier(o, root, no_restart);
    let log = match o.val("--log") {
        Some(p) => {
            let mut lg = log::Log::open(Path::new(&p))?;
            let exe = std::env::current_exe().ok().and_then(|p| std::fs::read(p).ok()).map(|b| sha256::hex(&b)).unwrap_or_default();
            lg.append("session", now_ms(), &format!("\"mode\":\"{}\",\"binary_sha256\":\"{}\",\"version\":\"nym0asgate 1.5.0 (search gate v1.5, rust map engine)\",\"sock\":\"{}\",\"clf_sock\":\"{}\"", mode, exe, esc(&client.sock.display().to_string()), esc(&clf.sock.display().to_string())))?;
            Some(lg)
        }
        None => None,
    };
    let timing = match o.val("--timing") { Some(p) => Some(BufWriter::new(std::fs::File::create(p).map_err(|e| e.to_string())?)), None => None };
    Ok(Engine { client, clf, log, timing, sandbox, emit: !no_emit, fast_us: vec![], fb_ms: vec![], layers: Default::default(), n: 0, acts: 0, sessions: HashMap::new() })
}
fn finish_engine(mut e: Engine, wall_s: f64) {
    if let Some(t) = e.timing.as_mut() { t.flush().ok(); }
    eprintln!("{}", e.summary(wall_s));
    if let Some(l) = e.log.take() { l.close(); }
}

fn cmd_batch(mut o: Opts, root: &Path) -> i32 {
    let out_path = o.val("--out");
    let mut eng = match make_engine(&mut o, root, "batch") { Ok(e) => e, Err(m) => { eprintln!("error: {}", m); return 3; } };
    let reader: Box<dyn BufRead> = match o.args.first() {
        Some(p) => match std::fs::File::open(p) { Ok(f) => Box::new(io::BufReader::new(f)), Err(e) => { eprintln!("error: cannot open {}: {}", p, e); return 2; } },
        None => Box::new(io::BufReader::new(io::stdin())),
    };
    let mut out: Box<dyn Write> = match &out_path { Some(p) => Box::new(BufWriter::new(std::fs::File::create(p).expect("cannot create --out file"))), None => Box::new(BufWriter::new(io::stdout())) };
    let t = Instant::now();
    let mut idx = 0u64;
    for l in reader.lines().map_while(Result::ok) {
        if l.trim().is_empty() { continue; }
        let line = eng.process(&l, idx); idx += 1;
        writeln!(out, "{}", line).ok();
    }
    out.flush().ok();
    finish_engine(eng, t.elapsed().as_secs_f64());
    0
}
fn cmd_stream(mut o: Opts, root: &Path) -> i32 {
    let mut eng = match make_engine(&mut o, root, "stream") { Ok(e) => e, Err(m) => { eprintln!("error: {}", m); return 3; } };
    let t = Instant::now();
    let stdout = io::stdout(); let mut out = stdout.lock();
    let mut idx = 0u64;
    for l in io::stdin().lock().lines().map_while(Result::ok) {
        if l.trim().is_empty() { continue; }
        let line = eng.process(&l, idx); idx += 1;
        writeln!(out, "{}", line).ok(); out.flush().ok();
    }
    finish_engine(eng, t.elapsed().as_secs_f64());
    0
}
fn cmd_verify(o: Opts) -> i32 {
    let Some(p) = o.args.first() else { eprintln!("usage: nym0asgate verify LOG"); return 2 };
    match log::verify(Path::new(p)) {
        Ok((n, last)) => { println!("{{\"ok\":true,\"records\":{},\"last_hash\":\"{}\"}}", n, last); 0 }
        Err(m) => { println!("{{\"ok\":false,\"problem\":\"{}\"}}", esc(&m)); 1 }
    }
}
fn cmd_replay(o: Opts) -> i32 {
    let Some(p) = o.args.first() else { eprintln!("usage: nym0asgate replay LOG"); return 2 };
    let chain = log::verify(Path::new(p));
    let text = match std::fs::read_to_string(p) { Ok(t) => t, Err(e) => { eprintln!("cannot read log: {}", e); return 2; } };
    let (mut decisions, mut mism, mut other) = (0u64, 0u64, 0u64);
    let mut bad: Vec<String> = vec![];
    let mut sessions: HashMap<String, SessionState> = HashMap::new();
    for line in text.lines() {
        let Some((body, _, _)) = log::split(line) else { mism += 1; bad.push("malformed record".into()); continue };
        let Some(v) = json::parse(&format!("{}}}", body)) else { mism += 1; bad.push("unreadable record".into()); continue };
        if v.get("type").and_then(|t| t.as_str()) != Some("decision") { other += 1; continue; }
        decisions += 1;
        let id = v.get("id").and_then(|s| s.as_str()).unwrap_or("");
        let w = v.get("worker").and_then(Worker::from_json);
        let clf = v.get("classifier").and_then(Clf::from_json).unwrap_or(Clf::NotAsked);
        let stored_out = body.find(",\"out\":").map(|i| &body[i + 7..]).unwrap_or("");
        let Some(w) = w else { mism += 1; bad.push(format!("{}: unreadable worker field", id)); continue };
        let rec = if let Some(rv) = v.get("record") {
            policy::parse_record(&rv.compact(), 0)
        } else { Err("no record field".into()) };
        let Ok(rec) = rec else { mism += 1; bad.push(format!("{}: unreadable record field", id)); continue };
        let st = sessions.get(&rec.session_id).cloned().unwrap_or_default();
        let f = recompute(&rec, &w, &st, &clf);
        let fast_ok = v.get("fast").and_then(|s| s.as_str()) == Some(f.fast_kind) && v.get("fast_why").and_then(|s| s.as_str()) == Some(f.fast_why.as_str());
        if f.out != stored_out || !fast_ok { mism += 1; bad.push(format!("{}: replayed {} but log has {}", id, f.out, stored_out)); }
        let mut after = st;
        policy::update_session(&mut after, &rec, f.layer);
        sessions.insert(rec.session_id.clone(), after);
    }
    let list: Vec<String> = bad.iter().take(20).map(|b| format!("\"{}\"", esc(b))).collect();
    println!("{{\"chain_ok\":{},\"chain_problem\":{},\"decisions\":{},\"other_records\":{},\"mismatches\":{},\"mismatch_examples\":[{}]}}",
        chain.is_ok(), match &chain { Ok(_) => "null".into(), Err(m) => format!("\"{}\"", esc(m)) }, decisions, other, mism, list.join(","));
    if mism == 0 && chain.is_ok() { 0 } else { 1 }
}
/// mapscore: stdin lines of orders (';' between orders, '|' between phrase variants); prints one JSON line per order with the Rust decision and raw scores.
fn cmd_mapscore(_o: Opts, root: &Path) -> i32 {
    let mut e = match mapcheck::MapEngine::load(&root.join("models")) { Ok(e) => e, Err(m) => { eprintln!("map engine: {}", m); return 3; } };
    for l in io::stdin().lock().lines().map_while(Result::ok) {
        let variants: Vec<String> = l.split('|').map(|s| s.to_string()).collect();
        match e.decide(&variants) {
            Ok(d) => println!("{{\"hold\":{},\"rule\":\"{}\",\"region\":\"{}\",\"phrase\":\"{}\",\"score\":{:.9},\"m14\":{:.9},\"probe\":{:.9}}}", d.hold, d.rule, esc(&d.region), esc(&d.phrase), d.score, if d.m14.is_nan() { 0.0 } else { d.m14 }, if d.probe.is_nan() { 0.0 } else { d.probe }),
            Err(m) => println!("{{\"error\":\"{}\"}}", esc(&m)),
        }
    }
    0
}
/// mapverify LOG: recompute the map decision from the orders logged in each decision (field classifier.mapx) and compare with the logged mapc.
fn cmd_mapverify(o: Opts, root: &Path) -> i32 {
    let Some(p) = o.args.first() else { eprintln!("usage: nym0asgate mapverify LOG"); return 2 };
    let text = match std::fs::read_to_string(p) { Ok(t) => t, Err(e) => { eprintln!("cannot read log: {}", e); return 2; } };
    let mut e = match mapcheck::MapEngine::load(&root.join("models")) { Ok(e) => e, Err(m) => { eprintln!("map engine: {}", m); return 3; } };
    let (mut checked, mut mism) = (0u64, 0u64); let mut bad: Vec<String> = vec![];
    for line in text.lines() {
        let Some((body, _, _)) = log::split(line) else { continue };
        let Some(v) = json::parse(&format!("{}}}", body)) else { continue };
        if v.get("type").and_then(|t| t.as_str()) != Some("decision") { continue; }
        let Some(c) = v.get("classifier") else { continue };
        if c.get("status").and_then(|s| s.as_str()) != Some("ok") { continue; }
        let id = v.get("id").and_then(|s| s.as_str()).unwrap_or("");
        let mapx = c.get("mapx").and_then(|s| s.as_str()).unwrap_or("");
        let logged = c.get("mapc").and_then(|s| s.as_str()).unwrap_or("");
        checked += 1;
        match e.check(mapx) {
            Ok(rs) => { let now = rs.iter().take(3).cloned().collect::<Vec<_>>().join("; "); if now != logged { mism += 1; bad.push(format!("{}: recomputed '{}' but log has '{}'", id, now, logged)); } }
            Err(m) => { mism += 1; bad.push(format!("{}: error {}", id, m)); }
        }
    }
    let list: Vec<String> = bad.iter().take(20).map(|b| format!("\"{}\"", esc(b))).collect();
    println!("{{\"checked\":{},\"mismatches\":{},\"examples\":[{}],\"map_engine\":\"{}\"}}", checked, mism, list.join(","), esc(&e.tag));
    if mism == 0 { 0 } else { 1 }
}
fn cmd_worker(mut o: Opts, root: &Path) -> i32 {
    let no_restart = o.flag("--no-restart");
    let mut c = make_client(&mut o, root, no_restart);
    match o.args.first().map(|s| s.as_str()) {
        Some("status") => match c.connect() { Ok(()) => { println!("{{\"running\":true,\"pid\":{}}}", c.pid.map_or("null".into(), |p| p.to_string())); 0 } Err(e) => { println!("{{\"running\":false,\"detail\":\"{}\"}}", esc(&e)); 1 } },
        Some("start") => { c.autostart = true; match c.ensure() { Ok(()) => { println!("{{\"running\":true,\"pid\":{}}}", c.pid.map_or("null".into(), |p| p.to_string())); 0 } Err(e) => { println!("{{\"running\":false,\"detail\":\"{}\"}}", esc(&e)); 1 } } }
        Some("stop") => match c.shutdown() { Ok(()) => { println!("{{\"stopped\":true}}"); 0 } Err(e) => { println!("{{\"stopped\":false,\"detail\":\"{}\"}}", esc(&e)); 1 } },
        _ => { eprintln!("usage: nym0asgate worker start|stop|status"); 2 }
    }
}
fn main() {
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() { eprintln!("usage: nym0asgate batch|stream|replay|verify|worker|log-update|log-delete ..."); std::process::exit(2); }
    let cmd = args.remove(0);
    let mut o = Opts { args };
    let root = find_root(&mut o);
    policy::load_registry(&root);
    let code = match cmd.as_str() {
        "batch" => cmd_batch(o, &root),
        "stream" => cmd_stream(o, &root),
        "verify" => cmd_verify(o),
        "replay" => cmd_replay(o),
        "worker" => cmd_worker(o, &root),
        "mapscore" => cmd_mapscore(o, &root),
        "mapverify" => cmd_mapverify(o, &root),
        "log-update" | "log-delete" => { eprintln!("refused: the decision log is insert-only; records cannot be updated or deleted"); 4 }
        _ => { eprintln!("unknown command {}", cmd); 2 }
    };
    std::process::exit(code);
}
