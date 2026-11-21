//! Nym-0 map check v1.5, Rust port (std only). Same decision as src_py/map_check15.py.
//! Reads a fixed table (models/map_table_v15.json + .bin, hash checked), the MiniLM encoder weights exported from the frozen ONNX file
//! (models/encoder_f32.bin, hash checked), the WordPiece vocabulary and the verb gloss table. Embeds "You must {verb} it." for each verb phrase the
//! clause finder (Python worker) found, then holds when: (list) a phrase is on the seed list, (margin) the v1.4 rule fires, or (probe) the v1.5 learned boundary fires.
//! Hold-only. Any load or hash error is an Err, which the front door turns into a hold.
use crate::json;
use crate::sha256;
use std::collections::HashMap;
use std::path::Path;

const D: usize = 384;
const HEADS: usize = 12;
const HD: usize = 32;
const FF: usize = 1536;

fn rd_f32(p: &Path) -> Result<Vec<f32>, String> {
    let b = std::fs::read(p).map_err(|e| format!("cannot read {}: {}", p.display(), e))?;
    if b.len() % 4 != 0 { return Err(format!("{} is not a float table", p.display())); }
    Ok(b.chunks_exact(4).map(|c| f32::from_le_bytes([c[0], c[1], c[2], c[3]])).collect())
}
fn file_sha(p: &Path) -> Result<String, String> {
    let b = std::fs::read(p).map_err(|e| format!("cannot read {}: {}", p.display(), e))?;
    Ok(sha256::hex(&b))
}
fn erf(x: f64) -> f64 {
    let ax = x.abs();
    let v = if ax < 3.5 {
        // Taylor series, f64
        let mut term = ax; let mut sum = ax; let x2 = ax * ax; let mut n = 0.0f64;
        loop { n += 1.0; term *= -x2 / n; let add = term / (2.0 * n + 1.0); sum += add; if add.abs() < 1e-17 * sum.abs() || n > 200.0 { break; } }
        sum * 2.0 / std::f64::consts::PI.sqrt()
    } else if ax > 7.0 { 1.0 } else {
        // continued fraction for erfc
        let mut f = 0.0f64;
        for k in (1..=80).rev() { f = (k as f64 / 2.0) / (ax + f); }
        let erfc = (-ax * ax).exp() / std::f64::consts::PI.sqrt() / (ax + f);
        1.0 - erfc
    };
    if x < 0.0 { -v } else { v }
}

pub struct Dec { pub hold: bool, pub rule: &'static str, pub region: String, pub phrase: String, pub score: f64, pub m14: f64, pub probe: f64 }

pub struct MapEngine {
    frame: String, topk: usize, tau: f64, thr: f64, bias: f64,
    regions: Vec<(String, usize, usize)>, anchors: (usize, usize),
    table: Vec<f32>, wv: usize, wg: usize,
    seedlist: std::collections::HashSet<String>,
    vocab: HashMap<String, usize>, unk: usize, cls: usize, sep: usize,
    t: HashMap<String, (usize, usize)>, w: Vec<f32>,
    gidx: HashMap<String, usize>, gloss: Vec<f32>,
    cache: HashMap<String, Vec<f32>>,
    pub tag: String,
}

impl MapEngine {
    pub fn load(models: &Path) -> Result<MapEngine, String> {
        let hp = models.join("map_table_v15.json");
        let hs = std::fs::read_to_string(&hp).map_err(|e| format!("map table header missing: {}", e))?;
        let h = json::parse(&hs).ok_or("map table header unreadable")?;
        let files = h.get("files").ok_or("header: files")?;
        for f in ["map_table_v15.bin", "encoder_f32.bin", "encoder_f32.index.json", "vocab.txt", "verb_gloss_f32.bin", "verb_gloss_index.txt"] {
            let want = files.get(f).and_then(|x| x.as_str()).ok_or(format!("header: no hash for {}", f))?.to_string();
            let got = file_sha(&models.join(f))?;
            if got != want { return Err(format!("map engine file {} hash mismatch ({} != {})", f, &got[..12], &want[..12])); }
        }
        let num = |k: &str| h.get(k).and_then(|x| x.as_f64()).ok_or(format!("header: {}", k));
        let frame = h.get("frame").and_then(|x| x.as_str()).ok_or("header: frame")?.to_string();
        let topk = num("topk")? as usize; let tau = num("tau")?; let thr = num("thr")?; let bias = num("bias")?;
        let mut regions = vec![];
        for r in h.get("regions").and_then(|x| x.as_arr()).ok_or("header: regions")? {
            regions.push((r.get("name").and_then(|x| x.as_str()).ok_or("region name")?.to_string(), r.get("start").and_then(|x| x.as_u64()).ok_or("start")? as usize, r.get("n").and_then(|x| x.as_u64()).ok_or("n")? as usize));
        }
        let a = h.get("anchors").ok_or("header: anchors")?;
        let anchors = (a.get("start").and_then(|x| x.as_u64()).ok_or("anchors")? as usize, a.get("n").and_then(|x| x.as_u64()).ok_or("anchors")? as usize);
        let wv = num("wv_offset_floats")? as usize; let wg = num("wg_offset_floats")? as usize;
        let seedlist = h.get("seedlist").and_then(|x| x.as_arr()).ok_or("header: seedlist")?.iter().filter_map(|x| x.as_str().map(|s| s.to_string())).collect();
        let table = rd_f32(&models.join("map_table_v15.bin"))?;
        if table.len() != wg + D { return Err("map table has the wrong size".into()); }
        let vtxt = std::fs::read_to_string(models.join("vocab.txt")).map_err(|e| e.to_string())?;
        let mut vocab = HashMap::new();
        for (i, l) in vtxt.lines().enumerate() { vocab.insert(l.to_string(), i); }
        let unk = *vocab.get("[UNK]").ok_or("no [UNK]")?; let cls = *vocab.get("[CLS]").ok_or("no [CLS]")?; let sep = *vocab.get("[SEP]").ok_or("no [SEP]")?;
        let ix = json::parse(&std::fs::read_to_string(models.join("encoder_f32.index.json")).map_err(|e| e.to_string())?).ok_or("encoder index unreadable")?;
        let mut t = HashMap::new();
        for e in ix.as_arr().ok_or("encoder index")? {
            let name = e.get("name").and_then(|x| x.as_str()).ok_or("name")?.to_string();
            let off = e.get("offset").and_then(|x| x.as_u64()).ok_or("offset")? as usize;
            let n: usize = e.get("shape").and_then(|x| x.as_arr()).ok_or("shape")?.iter().map(|d| d.as_u64().unwrap_or(0) as usize).product();
            t.insert(name, (off, n));
        }
        let w = rd_f32(&models.join("encoder_f32.bin"))?;
        let gl = std::fs::read_to_string(models.join("verb_gloss_index.txt")).map_err(|e| e.to_string())?;
        let mut gidx = HashMap::new();
        for (i, wd) in gl.split_whitespace().enumerate() { gidx.insert(wd.to_string(), i); }
        let gloss = rd_f32(&models.join("verb_gloss_f32.bin"))?;
        if gloss.len() != gidx.len() * D { return Err("gloss table has the wrong size".into()); }
        let onnx = h.get("sources").and_then(|s| s.get("onnx__model.onnx")).and_then(|x| x.as_str()).unwrap_or("");
        let tag = format!("all-MiniLM-L6-v2@{} tau={:+.3} thr={:+.3} rust-map-v1.5 tab={}", &onnx[..12.min(onnx.len())], tau, thr, &file_sha(&hp)?[..12]);
        Ok(MapEngine { frame, topk, tau, thr, bias, regions, anchors, table, wv, wg, seedlist, vocab, unk, cls, sep, t, w, gidx, gloss, cache: HashMap::new(), tag })
    }
    fn wp(&self, word: &str, out: &mut Vec<usize>) {
        if word.len() > 100 { out.push(self.unk); return; }
        let b = word.as_bytes(); let mut s = 0; let mut pieces = vec![];
        while s < b.len() {
            let mut e = b.len(); let mut got = None;
            while s < e {
                let sub = if s == 0 { word[s..e].to_string() } else { format!("##{}", &word[s..e]) };
                if let Some(&id) = self.vocab.get(&sub) { got = Some(id); break; }
                e -= 1;
            }
            match got { Some(id) => { pieces.push(id); s = e; } None => { out.push(self.unk); return; } }
        }
        out.extend(pieces);
    }
    fn tokenize(&self, text: &str) -> Result<Vec<usize>, String> {
        if !text.is_ascii() { return Err("non-ASCII phrase".into()); }
        let low: String = text.chars().map(|c| if c.is_ascii_control() { ' ' } else { c.to_ascii_lowercase() }).collect();
        let mut ids = vec![self.cls]; let mut cur = String::new();
        for c in low.chars() {
            if c == ' ' { if !cur.is_empty() { self.wp(&cur, &mut ids); cur.clear(); } }
            else if c.is_ascii_punctuation() { if !cur.is_empty() { self.wp(&cur, &mut ids); cur.clear(); } self.wp(&c.to_string(), &mut ids); }
            else { cur.push(c); }
        }
        if !cur.is_empty() { self.wp(&cur, &mut ids); }
        ids.truncate(63); ids.push(self.sep);
        Ok(ids)
    }
    fn tw(&self, name: &str) -> Result<&[f32], String> { let (o, n) = *self.t.get(name).ok_or(format!("missing tensor {}", name))?; Ok(&self.w[o..o + n]) }
    fn lin(&self, x: &[f32], n: usize, inn: usize, outn: usize, wname: &str, bname: &str) -> Result<Vec<f32>, String> {
        let w = self.tw(wname)?; let b = self.tw(bname)?;
        let mut y = vec![0f32; n * outn];
        for r in 0..n {
            let yr = &mut y[r * outn..(r + 1) * outn];
            yr.copy_from_slice(b);
            for i in 0..inn { let xv = x[r * inn + i]; let wr = &w[i * outn..(i + 1) * outn]; for j in 0..outn { yr[j] += xv * wr[j]; } }
        }
        Ok(y)
    }
    fn ln(&self, x: &mut [f32], n: usize, wname: &str, bname: &str) -> Result<(), String> {
        let w = self.tw(wname)?; let b = self.tw(bname)?;
        for r in 0..n {
            let row = &mut x[r * D..(r + 1) * D];
            let mu: f64 = row.iter().map(|&v| v as f64).sum::<f64>() / D as f64;
            let var: f64 = row.iter().map(|&v| { let d = v as f64 - mu; d * d }).sum::<f64>() / D as f64;
            let inv = 1.0 / (var + 1e-12).sqrt();
            for i in 0..D { row[i] = (((row[i] as f64 - mu) * inv) as f32) * w[i] + b[i]; }
        }
        Ok(())
    }
    fn forward(&self, ids: &[usize]) -> Result<Vec<f32>, String> {
        let n = ids.len();
        let we = self.tw("word_emb")?; let pe = self.tw("pos_emb")?; let te = self.tw("type_emb")?;
        let mut x = vec![0f32; n * D];
        for (p, &id) in ids.iter().enumerate() { for i in 0..D { x[p * D + i] = we[id * D + i] + pe[p * D + i] + te[i]; } }
        self.ln(&mut x, n, "emb_ln_w", "emb_ln_b")?;
        for l in 0..6 {
            let q = self.lin(&x, n, D, D, &format!("l{}_q_w", l), &format!("l{}_q_b", l))?;
            let k = self.lin(&x, n, D, D, &format!("l{}_k_w", l), &format!("l{}_k_b", l))?;
            let v = self.lin(&x, n, D, D, &format!("l{}_v_w", l), &format!("l{}_v_b", l))?;
            let mut ctx = vec![0f32; n * D];
            let scale = (HD as f64).sqrt();
            for h in 0..HEADS {
                for i in 0..n {
                    let mut sc = vec![0f64; n];
                    for j in 0..n { let mut s = 0f64; for d in 0..HD { s += q[i * D + h * HD + d] as f64 * k[j * D + h * HD + d] as f64; } sc[j] = s / scale; }
                    let mx = sc.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
                    let mut z = 0f64; for s in sc.iter_mut() { *s = (*s - mx).exp(); z += *s; }
                    for d in 0..HD { let mut a = 0f64; for j in 0..n { a += sc[j] / z * v[j * D + h * HD + d] as f64; } ctx[i * D + h * HD + d] = a as f32; }
                }
            }
            let mut a = self.lin(&ctx, n, D, D, &format!("l{}_ao_w", l), &format!("l{}_ao_b", l))?;
            for i in 0..n * D { a[i] += x[i]; }
            self.ln(&mut a, n, &format!("l{}_ln1_w", l), &format!("l{}_ln1_b", l))?;
            let mut hdn = self.lin(&a, n, D, FF, &format!("l{}_ff1_w", l), &format!("l{}_ff1_b", l))?;
            for v in hdn.iter_mut() { let f = *v as f64; *v = (0.5 * f * (1.0 + erf(f / std::f64::consts::SQRT_2))) as f32; }
            let mut o = self.lin(&hdn, n, FF, D, &format!("l{}_ff2_w", l), &format!("l{}_ff2_b", l))?;
            for i in 0..n * D { o[i] += a[i]; }
            self.ln(&mut o, n, &format!("l{}_ln2_w", l), &format!("l{}_ln2_b", l))?;
            x = o;
        }
        let mut e = vec![0f64; D];
        for p in 0..n { for i in 0..D { e[i] += x[p * D + i] as f64; } }
        for v in e.iter_mut() { *v /= n as f64; }
        let nm = e.iter().map(|v| v * v).sum::<f64>().sqrt() + 1e-12;
        Ok(e.iter().map(|v| (v / nm) as f32).collect())
    }
    fn embed(&mut self, phrase: &str) -> Result<Vec<f32>, String> {
        let text = self.frame.replace("{v}", phrase);
        if let Some(v) = self.cache.get(&text) { return Ok(v.clone()); }
        let ids = self.tokenize(&text)?;
        let v = self.forward(&ids)?;
        if self.cache.len() > 20000 { self.cache.clear(); }
        self.cache.insert(text, v.clone());
        Ok(v)
    }
    fn dot(a: &[f32], b: &[f32]) -> f64 { let mut s = 0f64; for i in 0..a.len() { s += a[i] as f64 * b[i] as f64; } s }
    fn topk_mean(&self, mut v: Vec<f64>) -> f64 {
        v.sort_by(|a, b| b.partial_cmp(a).unwrap_or(std::cmp::Ordering::Equal));
        let k = self.topk.min(v.len()); v[..k].iter().sum::<f64>() / k as f64
    }
    /// v1.4 margin and nearest region for one phrase
    pub fn margin(&mut self, phrase: &str) -> Result<(f64, String), String> {
        let x = self.embed(phrase)?;
        Ok(self.margin_x(&x))
    }
    fn margin_x(&self, x: &[f32]) -> (f64, String) {
        let mut best = -9.0f64; let mut reg = String::new();
        for (name, st, n) in &self.regions {
            let sims: Vec<f64> = (0..*n).map(|i| Self::dot(x, &self.table[(st + i) * D..(st + i + 1) * D])).collect();
            let s = self.topk_mean(sims);
            if s > best { best = s; reg = name.clone(); }
        }
        let (as_, an) = self.anchors;
        let sims: Vec<f64> = (0..an).map(|i| Self::dot(x, &self.table[(as_ + i) * D..(as_ + i + 1) * D])).collect();
        (best - self.topk_mean(sims), reg)
    }
    fn probe_x(&self, phrase: &str, x: &[f32]) -> f64 {
        let first = phrase.split(' ').next().unwrap_or("");
        let mut s = self.bias + Self::dot(&self.table[self.wv..self.wv + D], x);
        if let Some(&i) = self.gidx.get(first) { s += Self::dot(&self.table[self.wg..self.wg + D], &self.gloss[i * D..(i + 1) * D]); }
        s
    }
    pub fn probe(&mut self, phrase: &str) -> Result<f64, String> { let x = self.embed(phrase)?; Ok(self.probe_x(phrase, &x)) }
    /// One found order: all its phrase variants.
    pub fn decide(&mut self, variants: &[String]) -> Result<Dec, String> {
        for ph in variants { if self.seedlist.contains(ph) { return Ok(Dec { hold: true, rule: "list", region: String::new(), phrase: ph.clone(), score: 1.0, m14: f64::NAN, probe: f64::NAN }); } }
        let mut b14: Option<(f64, String, String)> = None; let mut bp: Option<(f64, String)> = None;
        for ph in variants {
            let x = self.embed(ph)?;
            let (m, reg) = self.margin_x(&x); let p = self.probe_x(ph, &x);
            if b14.as_ref().map_or(true, |b| m > b.0) { b14 = Some((m, reg, ph.clone())); }
            if bp.as_ref().map_or(true, |b| p > b.0) { bp = Some((p, ph.clone())); }
        }
        let (m, reg, mph) = b14.ok_or("no phrase")?; let (p, pph) = bp.ok_or("no phrase")?;
        if m >= self.tau { return Ok(Dec { hold: true, rule: "margin", region: reg, phrase: mph, score: m, m14: m, probe: p }); }
        if p >= self.thr { return Ok(Dec { hold: true, rule: "probe", region: String::new(), phrase: pph, score: p, m14: m, probe: p }); }
        Ok(Dec { hold: false, rule: "", region: String::new(), phrase: String::new(), score: 0.0, m14: m, probe: p })
    }
    /// mapx: orders separated by ';', phrase variants separated by '|'. Returns the reasons (deduplicated, in order).
    pub fn check(&mut self, mapx: &str) -> Result<Vec<String>, String> {
        let mut reasons: Vec<String> = vec![];
        for cand in mapx.split(';') {
            if cand.is_empty() { continue; }
            let variants: Vec<String> = cand.split('|').map(|s| s.to_string()).collect();
            let d = self.decide(&variants)?;
            if d.hold { let r = format!("map:{}:{}:{}:{:.3}", d.rule, d.region, d.phrase, d.score); if !reasons.contains(&r) { reasons.push(r); } }
        }
        Ok(reasons)
    }
}
