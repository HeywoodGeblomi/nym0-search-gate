//! Small strict JSON reader/writer helpers (standard library only). Used for input lines, worker answers and log records.
#[derive(Debug, Clone, PartialEq)]
pub enum V { Null, Bool(bool), Num(String), Str(String), Arr(Vec<V>), Obj(Vec<(String, V)>) }
impl V {
    pub fn get(&self, k: &str) -> Option<&V> { if let V::Obj(o) = self { o.iter().find(|(a, _)| a == k).map(|(_, v)| v) } else { None } }
    pub fn as_str(&self) -> Option<&str> { if let V::Str(s) = self { Some(s) } else { None } }
    pub fn as_u64(&self) -> Option<u64> { if let V::Num(n) = self { n.parse().ok() } else { None } }
    pub fn as_f64(&self) -> Option<f64> { if let V::Num(n) = self { n.parse().ok() } else { None } }
    pub fn is_null(&self) -> bool { matches!(self, V::Null) }
    #[allow(dead_code)]
    pub fn as_bool(&self) -> Option<bool> { if let V::Bool(b) = self { Some(*b) } else { None } }
    #[allow(dead_code)]
    pub fn as_arr(&self) -> Option<&[V]> { if let V::Arr(a) = self { Some(a) } else { None } }
    pub fn compact(&self) -> String {
        match self {
            V::Null => "null".into(),
            V::Bool(b) => if *b { "true".into() } else { "false".into() },
            V::Num(n) => n.clone(),
            V::Str(s) => {
                let mut o = String::new();
                o.push('"');
                o.push_str(&esc(s));
                o.push('"');
                o
            }
            V::Arr(a) => format!("[{}]", a.iter().map(|x| x.compact()).collect::<Vec<_>>().join(",")),
            V::Obj(o) => {
                let parts: Vec<String> = o.iter().map(|(k, v)| {
                    let mut s = String::new();
                    s.push('"');
                    s.push_str(&esc(k));
                    s.push('"');
                    s.push(':');
                    s.push_str(&v.compact());
                    s
                }).collect();
                format!("{{{}}}", parts.join(","))
            }
        }
    }
}
struct P<'a> { b: &'a [u8], i: usize, depth: usize }
impl<'a> P<'a> {
    fn ws(&mut self) { while self.i < self.b.len() && matches!(self.b[self.i], b' ' | b'\t' | b'\r' | b'\n') { self.i += 1; } }
    fn lit(&mut self, s: &str, v: V) -> Option<V> { if self.b[self.i..].starts_with(s.as_bytes()) { self.i += s.len(); Some(v) } else { None } }
    fn val(&mut self) -> Option<V> {
        self.ws();
        if self.depth > 64 || self.i >= self.b.len() { return None; }
        match self.b[self.i] {
            b'{' => {
                self.i += 1; self.depth += 1; let mut o = Vec::new();
                loop {
                    self.ws();
                    if self.i < self.b.len() && self.b[self.i] == b'}' { self.i += 1; break; }
                    if !o.is_empty() { if self.b.get(self.i) != Some(&b',') { return None; } self.i += 1; self.ws(); }
                    let k = match self.val()? { V::Str(s) => s, _ => return None };
                    self.ws(); if self.b.get(self.i) != Some(&b':') { return None; } self.i += 1;
                    let v = self.val()?; o.push((k, v));
                }
                self.depth -= 1; Some(V::Obj(o))
            }
            b'[' => {
                self.i += 1; self.depth += 1; let mut a = Vec::new();
                loop {
                    self.ws();
                    if self.i < self.b.len() && self.b[self.i] == b']' { self.i += 1; break; }
                    if !a.is_empty() { if self.b.get(self.i) != Some(&b',') { return None; } self.i += 1; }
                    a.push(self.val()?);
                }
                self.depth -= 1; Some(V::Arr(a))
            }
            b'"' => self.string().map(V::Str),
            b't' => self.lit("true", V::Bool(true)),
            b'f' => self.lit("false", V::Bool(false)),
            b'n' => self.lit("null", V::Null),
            b'-' | b'0'..=b'9' => {
                let s = self.i; self.i += 1;
                while self.i < self.b.len() && matches!(self.b[self.i], b'0'..=b'9' | b'.' | b'e' | b'E' | b'+' | b'-') { self.i += 1; }
                Some(V::Num(String::from_utf8_lossy(&self.b[s..self.i]).into_owned()))
            }
            _ => None,
        }
    }
    fn hex4(&mut self) -> Option<u32> {
        if self.i + 4 > self.b.len() { return None; }
        let s = std::str::from_utf8(&self.b[self.i..self.i + 4]).ok()?; self.i += 4; u32::from_str_radix(s, 16).ok()
    }
    fn string(&mut self) -> Option<String> {
        self.i += 1; let mut out: Vec<u8> = Vec::new();
        loop {
            let c = *self.b.get(self.i)?; self.i += 1;
            match c {
                b'"' => break,
                b'\\' => {
                    let e = *self.b.get(self.i)?; self.i += 1;
                    match e {
                        b'n' => out.push(b'\n'), b't' => out.push(b'\t'), b'r' => out.push(b'\r'), b'b' => out.push(8), b'f' => out.push(12),
                        b'"' => out.push(b'"'), b'\\' => out.push(b'\\'), b'/' => out.push(b'/'),
                        b'u' => {
                            let mut cp = self.hex4()?;
                            if (0xD800..0xDC00).contains(&cp) {
                                if self.b.get(self.i) == Some(&b'\\') && self.b.get(self.i + 1) == Some(&b'u') {
                                    self.i += 2; let lo = self.hex4()?;
                                    if !(0xDC00..0xE000).contains(&lo) { return None; }
                                    cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                                } else { return None; }
                            }
                            let ch = char::from_u32(cp)?; let mut buf = [0u8; 4]; out.extend_from_slice(ch.encode_utf8(&mut buf).as_bytes());
                        }
                        _ => return None,
                    }
                }
                c if c < 0x20 => return None,
                c => out.push(c),
            }
        }
        String::from_utf8(out).ok()
    }
}
pub fn parse(s: &str) -> Option<V> {
    let mut p = P { b: s.as_bytes(), i: 0, depth: 0 };
    let v = p.val()?; p.ws();
    if p.i == p.b.len() { Some(v) } else { None }
}
pub fn esc(s: &str) -> String {
    let mut o = String::with_capacity(s.len() + 2);
    for c in s.chars() {
        match c { '"' => o.push_str("\\\""), '\\' => o.push_str("\\\\"), '\n' => o.push_str("\\n"), '\t' => o.push_str("\\t"), '\r' => o.push_str("\\r"),
                  c if (c as u32) < 0x20 => o.push_str(&format!("\\u{:04x}", c as u32)), c => o.push(c) }
    }
    o
}
pub fn opt_str(s: Option<&str>) -> String { s.map_or("null".to_string(), |f| format!("\"{}\"", esc(f))) }
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn roundtrip() {
        let v = parse(r#"{"id":7,"text":"a \"q\" \u00e9 \ud83d\ude00","n":null,"x":{"y":[1,2,{"z":true}]}}"#).unwrap();
        assert_eq!(v.get("text").unwrap().as_str().unwrap(), "a \"q\" é 😀");
        assert!(v.get("n").unwrap().is_null());
        assert_eq!(v.get("id").unwrap().as_u64(), Some(7));
        assert!(parse("{\"a\":1} x").is_none());
        assert!(parse("{\"a\":").is_none());
        assert_eq!(parse(&format!("\"{}\"", esc("t\"\\\n\u{1}"))).unwrap().as_str().unwrap(), "t\"\\\n\u{1}");
    }
}
