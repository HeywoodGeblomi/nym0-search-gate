//! Runtime emit: write one receipt under a sandbox directory. No network. Paths may not leave the sandbox.
use std::fs;
use std::path::{Path, PathBuf};

pub fn emit(sandbox: &Path, id: &str, tool: &str, args: &str) -> Result<PathBuf, String> {
    if crate::pipeline::is_forbidden_final(tool) {
        return Err(format!("refusing to emit forbidden tool {}", tool));
    }
    let base = if sandbox.exists() { sandbox.canonicalize().map_err(|e| e.to_string())? } else {
        fs::create_dir_all(sandbox).map_err(|e| e.to_string())?;
        sandbox.canonicalize().map_err(|e| e.to_string())?
    };
    let emitted = base.join("emitted");
    fs::create_dir_all(&emitted).map_err(|e| e.to_string())?;
    // id may contain characters; keep it a single path component
    let safe: String = id.chars().map(|c| if c.is_ascii_alphanumeric() || c == '-' || c == '_' { c } else { '_' }).collect();
    let path = emitted.join(format!("{}.json", safe));
    let parent = path.parent().unwrap();
    let parent_c = parent.canonicalize().map_err(|e| e.to_string())?;
    if !parent_c.starts_with(&base) {
        return Err(format!("refusing path outside sandbox: {}", path.display()));
    }
    let body = format!("{{\"id\":\"{}\",\"tool\":\"{}\",\"proposed_args\":\"{}\"}}\n",
        crate::json::esc(id), crate::json::esc(tool), crate::json::esc(args));
    fs::write(&path, body).map_err(|e| e.to_string())?;
    Ok(path)
}
