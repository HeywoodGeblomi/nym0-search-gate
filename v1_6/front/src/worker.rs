//! Client for the warm policy worker (Unix socket, one JSON line per request).
//! Protocol and --die-after / --hang-after flags follow the official Nym-0 v3.3 worker shape.
use crate::json::{self, esc};
use crate::pipeline::Worker;
use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

pub struct Client {
    pub sock: PathBuf,
    pub root: PathBuf,
    pub autostart: bool,
    pub timeout: Duration,
    pub start_wait: Duration,
    conn: Option<(UnixStream, BufReader<UnixStream>)>,
    pub pid: Option<u64>,
    pub events: Vec<String>,
    n: u64,
}

impl Client {
    pub fn new(sock: PathBuf, root: PathBuf) -> Client {
        Client { sock, root, autostart: true, timeout: Duration::from_secs(15), start_wait: Duration::from_secs(30), conn: None, pid: None, events: vec![], n: 0 }
    }
    fn roundtrip(&mut self, req: &str) -> Result<json::V, String> {
        let (w, r) = self.conn.as_mut().ok_or("not connected")?;
        w.write_all(req.as_bytes()).and_then(|_| w.write_all(b"\n")).and_then(|_| w.flush()).map_err(|e| format!("write to worker failed: {}", e))?;
        let mut line = String::new();
        match r.read_line(&mut line) {
            Ok(0) => Err("worker closed the connection (it died)".into()),
            Ok(_) => json::parse(line.trim()).ok_or_else(|| "worker sent an unreadable answer".to_string()),
            Err(e) if matches!(e.kind(), std::io::ErrorKind::WouldBlock | std::io::ErrorKind::TimedOut) => Err("worker timed out".into()),
            Err(e) => Err(format!("read from worker failed: {}", e)),
        }
    }
    pub fn connect(&mut self) -> Result<(), String> {
        let s = UnixStream::connect(&self.sock).map_err(|e| format!("no worker at {} ({})", self.sock.display(), e))?;
        s.set_read_timeout(Some(self.timeout)).ok(); s.set_write_timeout(Some(Duration::from_secs(10))).ok();
        let r = BufReader::new(s.try_clone().map_err(|e| e.to_string())?);
        self.conn = Some((s, r));
        match self.roundtrip("{\"op\":\"ping\"}") {
            Ok(v) => { self.pid = v.get("pid").and_then(|p| p.as_u64()); Ok(()) }
            Err(e) => { self.conn = None; Err(e) }
        }
    }
    pub fn spawn(&mut self) -> Result<(), String> {
        let script = self.root.join("worker").join("run_worker.sh");
        let st = Command::new("setsid").arg("-f").arg(&script).arg("--socket").arg(&self.sock).arg("--pidfile").arg(self.root.join("run").join("worker.pid"))
            .stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null()).status().map_err(|e| format!("cannot start worker: {}", e))?;
        if !st.success() { return Err("worker launcher failed".into()); }
        Ok(())
    }
    pub fn ensure(&mut self) -> Result<(), String> {
        if self.conn.is_some() { return Ok(()); }
        let first = self.connect();
        if first.is_ok() { return Ok(()); }
        if !self.autostart { return first; }
        let old = self.pid;
        self.events.push(format!("worker_starting (previous pid {:?})", old));
        self.spawn()?;
        let t = Instant::now();
        loop {
            std::thread::sleep(Duration::from_millis(50));
            if self.connect().is_ok() { self.events.push(format!("worker_ready pid {:?} after {:.1}s", self.pid, t.elapsed().as_secs_f64())); return Ok(()); }
            if t.elapsed() > self.start_wait { return Err(format!("worker did not become ready within {}s", self.start_wait.as_secs())); }
        }
    }
    fn kill_if_hung(&mut self) {
        if let Some(p) = self.pid { Command::new("kill").arg("-9").arg(p.to_string()).stdout(Stdio::null()).stderr(Stdio::null()).status().ok(); }
    }
    /// Ask for one decision on a full record JSON object (already compact object text).
    pub fn ask(&mut self, id: &str, record_json: &str, session_json: &str) -> (Worker, Option<f64>) {
        if let Err(e) = self.ensure() { return (Worker::Unavailable(e), None); }
        self.n += 1;
        let req = format!("{{\"op\":\"decide\",\"id\":\"{}\",\"record\":{},\"session\":{}}}", esc(id), record_json, session_json);
        let t = Instant::now();
        match self.roundtrip(&req) {
            Ok(v) => {
                let ms = t.elapsed().as_secs_f64() * 1000.0;
                if let Some(e) = v.get("err").and_then(|e| e.as_str()) { return (Worker::Failed(format!("worker error: {}", e)), Some(ms)); }
                match v.get("final") {
                    Some(f) => {
                        let fin = if f.is_null() { None } else { f.as_str().map(|s| s.to_string()) };
                        if !f.is_null() && fin.is_none() { return (Worker::Failed("worker answer 'final' is not text".into()), Some(ms)); }
                        (Worker::Ok(fin, v.get("reason").and_then(|r| r.as_str()).unwrap_or("").to_string()), Some(ms))
                    }
                    None => (Worker::Failed("worker answer has no 'final'".into()), Some(ms)),
                }
            }
            Err(e) => {
                let ms = t.elapsed().as_secs_f64() * 1000.0;
                self.conn = None;
                self.events.push(format!("worker_failed on request {}: {} (pid {:?})", self.n, e, self.pid));
                if e.contains("timed out") { self.kill_if_hung(); }
                if self.autostart { if let Err(e2) = self.ensure() { self.events.push(format!("worker_restart_failed: {}", e2)); } }
                (Worker::Failed(e), Some(ms))
            }
        }
    }
    pub fn shutdown(&mut self) -> Result<(), String> {
        if self.conn.is_none() { self.connect()?; }
        let _ = self.roundtrip("{\"op\":\"shutdown\"}");
        self.conn = None; Ok(())
    }
}
