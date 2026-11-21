//! Client for the warm hold-only classifier (Unix socket, one JSON line per request).
//! Protocol and --die-after / --hang-after flags follow the same family as the policy worker.
use crate::json::{self, esc};
use crate::pipeline::Clf;
use crate::mapcheck::MapEngine;
use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

pub struct Client {
    pub sock: PathBuf,
    pub root: PathBuf,
    pub weights: PathBuf,
    pub autostart: bool,
    pub timeout: Duration,
    pub start_wait: Duration,
    conn: Option<(UnixStream, BufReader<UnixStream>)>,
    pub pid: Option<u64>,
    pub events: Vec<String>,
    n: u64,
    /// v1.5: true = the Rust map engine decides the map check from the orders the worker found; false = the worker's own (Python) answer is used.
    pub map_rust: bool,
    map: Option<Result<MapEngine, String>>,
}

impl Client {
    pub fn new(sock: PathBuf, root: PathBuf, weights: PathBuf) -> Client {
        Client { sock, root, weights, autostart: true, timeout: Duration::from_secs(15), start_wait: Duration::from_secs(30), conn: None, pid: None, events: vec![], n: 0, map_rust: true, map: None }
    }
    fn roundtrip(&mut self, req: &str) -> Result<json::V, String> {
        let (w, r) = self.conn.as_mut().ok_or("not connected")?;
        w.write_all(req.as_bytes()).and_then(|_| w.write_all(b"\n")).and_then(|_| w.flush()).map_err(|e| format!("write to classifier failed: {}", e))?;
        let mut line = String::new();
        match r.read_line(&mut line) {
            Ok(0) => Err("classifier closed the connection (it died)".into()),
            Ok(_) => json::parse(line.trim()).ok_or_else(|| "classifier sent an unreadable answer".to_string()),
            Err(e) if matches!(e.kind(), std::io::ErrorKind::WouldBlock | std::io::ErrorKind::TimedOut) => Err("classifier timed out".into()),
            Err(e) => Err(format!("read from classifier failed: {}", e)),
        }
    }
    pub fn connect(&mut self) -> Result<(), String> {
        let s = UnixStream::connect(&self.sock).map_err(|e| format!("no classifier at {} ({})", self.sock.display(), e))?;
        s.set_read_timeout(Some(self.timeout)).ok(); s.set_write_timeout(Some(Duration::from_secs(10))).ok();
        let r = BufReader::new(s.try_clone().map_err(|e| e.to_string())?);
        self.conn = Some((s, r));
        match self.roundtrip("{\"op\":\"ping\"}") {
            Ok(v) => { self.pid = v.get("pid").and_then(|p| p.as_u64()); Ok(()) }
            Err(e) => { self.conn = None; Err(e) }
        }
    }
    pub fn spawn(&mut self) -> Result<(), String> {
        let script = self.root.join("worker").join("run_classifier.sh");
        let st = Command::new("setsid").arg("-f").arg(&script)
            .arg("--socket").arg(&self.sock)
            .arg("--pidfile").arg(self.root.join("run").join("classifier.pid"))
            .arg("--weights").arg(&self.weights)
            .stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null()).status()
            .map_err(|e| format!("cannot start classifier: {}", e))?;
        if !st.success() { return Err("classifier launcher failed".into()); }
        Ok(())
    }
    pub fn ensure(&mut self) -> Result<(), String> {
        if self.conn.is_some() { return Ok(()); }
        let first = self.connect();
        if first.is_ok() { return Ok(()); }
        if !self.autostart { return first; }
        let old = self.pid;
        self.events.push(format!("classifier_starting (previous pid {:?})", old));
        self.spawn()?;
        let t = Instant::now();
        loop {
            std::thread::sleep(Duration::from_millis(50));
            if self.connect().is_ok() { self.events.push(format!("classifier_ready pid {:?} after {:.1}s", self.pid, t.elapsed().as_secs_f64())); return Ok(()); }
            if t.elapsed() > self.start_wait { return Err(format!("classifier did not become ready within {}s", self.start_wait.as_secs())); }
        }
    }
    fn kill_if_hung(&mut self) {
        if let Some(p) = self.pid { Command::new("kill").arg("-9").arg(p.to_string()).stdout(Stdio::null()).stderr(Stdio::null()).status().ok(); }
    }
    pub fn classify(&mut self, id: &str, text: &str) -> (Clf, Option<f64>) {
        if let Err(e) = self.ensure() { return (Clf::Unavailable(e), None); }
        self.n += 1;
        let req = format!("{{\"op\":\"classify\",\"id\":\"{}\",\"text\":\"{}\"}}", esc(id), esc(text));
        let t = Instant::now();
        match self.roundtrip(&req) {
            Ok(v) => {
                let ms = t.elapsed().as_secs_f64() * 1000.0;
                if let Some(e) = v.get("err").and_then(|e| e.as_str()) { return (Clf::Failed(format!("classifier error: {}", e)), Some(ms)); }
                let score_v = v.get("score");
                let score = match score_v.and_then(|s| s.as_f64()) {
                    Some(x) if x.is_finite() => x,
                    _ => {
                        // also accept a numeric string? no: non-finite or non-numeric is a fail-safe hold
                        return (Clf::Failed("classifier score is not a finite number".into()), Some(ms));
                    }
                };
                let hold = v.get("hold").and_then(|h| h.as_bool()).unwrap_or(false);
                let threshold = v.get("threshold").and_then(|s| s.as_f64()).unwrap_or(f64::NAN);
                let instr = v.get("instr").and_then(|m| m.as_str()).unwrap_or("").to_string();
                let mut mapc = v.get("mapc").and_then(|m| m.as_str()).unwrap_or("").to_string();
                let mut mapm = v.get("mapm").and_then(|m| m.as_str()).unwrap_or("").to_string();
                let mapx = v.get("mapx").and_then(|m| m.as_str()).unwrap_or("").to_string();
                let relax = v.get("relax").and_then(|m| m.as_str()).unwrap_or("").to_string();
                if self.map_rust {
                    if v.get("mapx").and_then(|m| m.as_str()).is_none() { return (Clf::Failed("classifier answer has no mapx field (the Rust map engine needs the found orders)".into()), Some(ms)); }
                    if self.map.is_none() { self.map = Some(MapEngine::load(&self.root.join("models"))); }
                    match self.map.as_mut().unwrap() {
                        Err(m) => return (Clf::Failed(format!("map engine unavailable: {}", m)), Some(ms)),
                        Ok(e) => match e.check(&mapx) {
                            Err(m) => return (Clf::Failed(format!("map engine error: {}", m)), Some(ms)),
                            Ok(rs) => { mapc = rs.iter().take(3).cloned().collect::<Vec<_>>().join("; "); mapm = e.tag.clone(); }
                        },
                    }
                }
                (Clf::Ok { score, hold, threshold, instr, mapc, mapm, mapx, relax }, Some(ms))
            }
            Err(e) => {
                let ms = t.elapsed().as_secs_f64() * 1000.0;
                self.conn = None;
                self.events.push(format!("classifier_failed on request {}: {} (pid {:?})", self.n, e, self.pid));
                if e.contains("timed out") { self.kill_if_hung(); }
                if self.autostart { if let Err(e2) = self.ensure() { self.events.push(format!("classifier_restart_failed: {}", e2)); } }
                (Clf::Failed(e), Some(ms))
            }
        }
    }
    pub fn shutdown(&mut self) -> Result<(), String> {
        if self.conn.is_none() { self.connect()?; }
        let _ = self.roundtrip("{\"op\":\"shutdown\"}");
        self.conn = None; Ok(())
    }
}
