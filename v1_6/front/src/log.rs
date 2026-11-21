//! Append-only, hash-chained decision log (JSONL). Each record ends with `,"prev":"<hash of the record before>","hash":"<sha256(prev + "\n" + body)>"}`.
//! The driver only ever opens the file for append, refuses to append to a log whose chain is broken, and sets it read-only between runs.
use crate::json::{self, esc};
use crate::sha256;
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

pub const GENESIS: &str = "0000000000000000000000000000000000000000000000000000000000000000";
const MARK: &str = ",\"prev\":\"";

pub struct Log { path: PathBuf, f: File, pub seq: u64, prev: String, pending: u64 }

/// Split a stored line into (body, prev, hash).
pub fn split(line: &str) -> Option<(&str, &str, &str)> {
    let i = line.rfind(MARK)?;
    let body = &line[..i];
    let rest = &line[i + MARK.len()..];
    let j = rest.find("\",\"hash\":\"")?;
    let prev = &rest[..j];
    let h = rest[j + 10..].strip_suffix("\"}")?;
    Some((body, prev, h))
}
pub fn chain_hash(prev: &str, body: &str) -> String { sha256::hex(format!("{}\n{}", prev, body).as_bytes()) }

/// Verify a whole log file. Ok((records, last_hash)) or Err(description of the first problem).
pub fn verify(path: &Path) -> Result<(u64, String), String> {
    let text = fs::read_to_string(path).map_err(|e| format!("cannot read log: {}", e))?;
    let mut prev = GENESIS.to_string();
    let mut n = 0u64;
    for (k, line) in text.lines().enumerate() {
        let (body, p, h) = split(line).ok_or_else(|| format!("record {}: malformed line", k + 1))?;
        if p != prev { return Err(format!("record {}: prev hash does not match the record before it", k + 1)); }
        if chain_hash(p, body) != h { return Err(format!("record {}: hash does not match its content", k + 1)); }
        let v = json::parse(&format!("{}}}", body)).ok_or_else(|| format!("record {}: body is not valid JSON", k + 1))?;
        let seq = v.get("seq").and_then(|s| s.as_u64()).ok_or_else(|| format!("record {}: no seq", k + 1))?;
        if seq != n + 1 { return Err(format!("record {}: seq {} out of order (expected {})", k + 1, seq, n + 1)); }
        prev = h.to_string(); n += 1;
    }
    Ok((n, prev))
}

impl Log {
    /// Open for append. Creates the file if missing. An existing log must verify first.
    pub fn open(path: &Path) -> Result<Log, String> {
        let (seq, prev) = if path.exists() { verify(path)? } else { (0, GENESIS.to_string()) };
        if path.exists() { let mut p = fs::metadata(path).map_err(|e| e.to_string())?.permissions(); p.set_mode(0o644); fs::set_permissions(path, p).map_err(|e| e.to_string())?; }
        let f = OpenOptions::new().create(true).append(true).open(path).map_err(|e| format!("cannot open log for append: {}", e))?;
        Ok(Log { path: path.to_path_buf(), f, seq, prev, pending: 0 })
    }
    /// `fields` is the record body without the closing brace and without seq (it must start with a comma-free list of "key":value pairs).
    pub fn append(&mut self, kind: &str, ts_ms: u128, fields: &str) -> Result<(), String> {
        let seq = self.seq + 1;
        let body = format!("{{\"seq\":{},\"type\":\"{}\",\"ts_ms\":{},{}", seq, esc(kind), ts_ms, fields);
        let h = chain_hash(&self.prev, &body);
        let line = format!("{}{}{}\",\"hash\":\"{}\"}}\n", body, MARK, self.prev, h);
        self.f.write_all(line.as_bytes()).map_err(|e| format!("log write failed: {}", e))?;
        self.seq = seq; self.prev = h; self.pending += 1;
        if self.pending >= 64 { self.f.sync_data().ok(); self.pending = 0; }
        Ok(())
    }
    pub fn prev_hash(&self) -> &str { &self.prev }
    pub fn close(self) {
        self.f.sync_all().ok();
        if let Ok(m) = fs::metadata(&self.path) { let mut p = m.permissions(); p.set_mode(0o444); fs::set_permissions(&self.path, p).ok(); }
    }
}
