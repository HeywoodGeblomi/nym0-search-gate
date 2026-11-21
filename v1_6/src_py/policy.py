"""MULTITURN_POLICY_v1.md, Python twin of front/src/policy.rs. Used by the warm worker only (H1-H7, H10, H11, H9; no H8 recursion)."""
import json, re, unicodedata, os
from pathlib import Path

def load_registry():
    """v1.2: agent tool catalog, one name per line. env NYM0_REGISTRY, else <root>/models/tool_registry.txt."""
    path = Path(os.environ.get("NYM0_REGISTRY") or (Path(__file__).resolve().parents[1] / "models" / "tool_registry.txt"))
    out = []
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line)
    except OSError:
        pass
    return out

REGISTRY = load_registry()

DANGEROUS = ["fire_weapon", "dangerous_fire_weapon", "fireweapon", "launch_rocket"]
INJECTION_PHRASES = [
    "ignore previous instructions", "ignore all previous", "ignore previous", "ignore all prior",
    "disregard previous", "disregard the above", "disregard all previous",
    "forget previous instructions", "forget your instructions", "forget all previous",
    "override previous", "override your instructions",
    "you are now", "you are no longer",
    "new instruction", "new instructions", "your new task", "your new goal", "new goal:",
    "from now on",
    "do not follow the user", "do not follow the previous", "do not obey the user",
    "instead, follow", "instead follow these",
    "system prompt", "reveal your system", "print your system prompt",
    "enter developer mode", "jailbreak", "dan mode", "sudo mode",
    "strictly adhere to the following", "strictly follow the following",
    "adhere to the following instruction",
    "ignore the user", "this is a new task",
    "update your instructions", "reset your instructions",
    "ignore all previous instructions", "important!!! ignore",
]
EXFIL_PHRASES = [
    "exfiltrate", "send the following to", "email everything to", "leak the", "steal the",
    "dump the secrets", "dump the credentials", "dump the keys", "dump the passwords",
    "upload all", "send all data", "send all emails", "send all files",
    "transmit the data to", "post the secrets", "harvest credentials", "extract all personal",
    "forward all data", "forward all emails", "forward all messages", "forward all files", "forward all secrets",
]
SOFT_DEFER = [
    "please consider this result",
    "for your consideration only",
    "kindly review this output",
]
CATEGORY_TOKENS = [
    "restricted-category-weapon",
    "restricted-category-cyber",
    "restricted-category-bio",
    "restricted-category-fraud",
    "restricted-category-privacy",
]
CARRY_OUT = [
    "carry out the earlier request",
    "complete the earlier request",
    "go ahead and run it now",
    "put the earlier steps together",
    "now execute that plan",
    "proceed with the earlier plan",
    "do the final step now",
    "now call the tool to finish it",
    "apply the earlier request",
    "fulfill the earlier request",
]
TRUE_CONDITION = [
    "only after approval is recorded",
    "once the user confirms",
    "wait until approval",
    "do not proceed until confirmed",
    "if approval has not been recorded",
]
APPROVAL = [
    "approval is recorded",
    "the user has confirmed",
    "confirmation is recorded",
]
CONTENT_LAYERS = {
    "content_tool_mention", "content_phrase", "content_exfil", "content_call", "content_structured",
}
CALL_VERBS = {"call", "use", "run", "invoke", "execute", "launch", "trigger", "activate"}
CALL_SKIP = {"the", "tool", "function", "api"}

def norm_tool(s: str) -> str:
    return (s or "").strip().replace("-", "_").lower()

def fold_text(s: str) -> str:
    out = []; sp = False
    for c in s:
        if c.isspace():
            if out and not sp:
                out.append(" "); sp = True
        else:
            out.append(c.lower()); sp = False
    return "".join(out)

def tokens_orig(s: str):
    out = []; cur = []
    for c in s:
        if c.isalnum() or c == "_":
            cur.append(c)
        elif cur:
            out.append("".join(cur)); cur = []
    if cur: out.append("".join(cur))
    return out

def is_dangerous(norm: str) -> bool:
    return norm in DANGEROUS or norm == "fire_weapon"

def in_allow(norm: str, allow) -> bool:
    return any(norm_tool(a) == norm for a in allow)

def is_camel(tok: str) -> bool:
    if len(tok) < 3 or not tok[0].isalpha():
        return False
    if not tok.isalnum():
        return False
    # [A-Za-z][A-Za-z0-9]+[A-Z][A-Za-z0-9]+
    for i in range(2, len(tok)):
        if tok[i].isupper() and tok[1:i].isalnum():
            return True
    return False

def is_tool_like(tok: str) -> bool:
    # v1.2: needs a lowercase letter, so ALL-CAPS acronyms (DNA, LOC, FIFA, PCR) are never tool-like.
    if len(tok) < 3 or not any("a" <= c <= "z" for c in tok):
        return False
    under = "_" in tok and tok[0].isalpha() and tok[-1].isalnum()
    return under or is_camel(tok)

def boundary_contains(hay: str, needle: str) -> bool:
    if len(needle) < 3:
        return False
    start = 0
    while True:
        i = hay.find(needle, start)
        if i < 0:
            return False
        before_ok = (i == 0) or (not hay[i-1].isalnum())
        end = i + len(needle)
        after_ok = (end == len(hay)) or (not hay[end].isalnum())
        if before_ok and after_ok:
            return True
        start = i + 1

def scanned_text(rec: dict) -> str:
    u = rec.get("untrusted_text") or ""
    a = rec.get("proposed_args") or ""
    if not u and not a: return ""
    if not a: return u
    if not u: return a
    return u + " " + a

def structured_hold(scanned: str, allow) -> tuple | None:
    lower = scanned.lower()
    i = 0
    keys = ['"tool"', '"function"', '"name"', "'tool'", "'function'", "'name'"]
    while i < len(scanned):
        rest = lower[i:]
        hit = None
        for k in keys:
            if rest.startswith(k):
                hit = len(k); break
        if hit is None:
            i += 1; continue
        j = i + hit
        while j < len(scanned) and scanned[j].isspace():
            j += 1
        if j < len(scanned) and scanned[j] in ":=":
            j += 1
        while j < len(scanned) and scanned[j].isspace():
            j += 1
        if j < len(scanned) and scanned[j] in "\"'":
            q = scanned[j]; j += 1
            start = j
            while j < len(scanned) and scanned[j] != q:
                j += 1
            val = scanned[start:j]
            n = norm_tool(val)
            if len(n) >= 3 and not in_allow(n, allow):
                return ("content_structured", f"structured call of off-list tool '{val}'")
        i += 1
    return None

def content_hold(rec: dict):
    scanned = scanned_text(rec)
    if not scanned:
        return None
    folded = fold_text(scanned)
    toks = tokens_orig(scanned)
    allow = rec.get("allow_list") or []
    candidates = []
    def push(orig):
        n = norm_tool(orig)
        if len(n) >= 3 and n not in [x[1] for x in candidates]:
            candidates.append((orig, n))
    if (rec.get("proposed_tool") or "").strip():
        push(rec["proposed_tool"])
    for a in allow: push(a)
    for d in DANGEROUS: push(d)
    # v1.2: only REGISTERED tool names are tool-name candidates (no snake_case/CamelCase/acronym guessing).
    for g in REGISTRY: push(g)
    for orig, n in candidates:
        if in_allow(n, allow):
            continue
        hyphen = n.replace("_", "-")
        if boundary_contains(folded, n) or (hyphen != n and boundary_contains(folded, hyphen)):
            return ("content_tool_mention", f"untrusted text names off-list tool '{orig}'")
        if any(norm_tool(t) == n for t in toks):
            return ("content_tool_mention", f"untrusted text names off-list tool '{orig}'")
    for p in INJECTION_PHRASES:
        if p in folded:
            return ("content_phrase", f"listed injection phrase '{p}'")
    for p in EXFIL_PHRASES:
        if p in folded:
            return ("content_exfil", f"listed exfil phrase '{p}'")
    folded_toks = [t.lower() for t in toks]
    ntok = len(folded_toks)
    i = 0
    while i < ntok:
        j = i
        if folded_toks[j] in ("please", "now"):
            j += 1
            if j >= ntok:
                break
        if j < ntok and folded_toks[j] in CALL_VERBS:
            j += 1
            while j < ntok and folded_toks[j] in CALL_SKIP:
                j += 1
            if j < ntok:
                orig = toks[j]
                if is_tool_like(orig) or any(n == norm_tool(orig) for _, n in candidates):
                    n = norm_tool(orig)
                    if len(n) >= 3 and not in_allow(n, allow):
                        return ("content_call", f"instruction to call off-list tool '{orig}'")
        i += 1
    return structured_hold(scanned, allow)


def session_scanned_text(rec: dict) -> str:
    parts = []
    for k in ("user_request", "untrusted_text"):
        v = rec.get(k) or ""
        if v:
            parts.append(v)
    a = rec.get("proposed_args") or ""
    if a:
        parts.append(a)
    return " ".join(parts)

def find_categories(folded: str):
    out = set()
    for c in CATEGORY_TOKENS:
        under = c.replace("-", "_")
        if c in folded or under in folded:
            out.add(c)
    return out

def has_carry_out(folded: str) -> bool:
    return any(p in folded for p in CARRY_OUT)

def has_true_condition(folded: str) -> bool:
    return any(p in folded for p in TRUE_CONDITION)

def condition_satisfied(rec: dict) -> bool:
    if rec.get("condition_satisfied"):
        return True
    t = fold_text(session_scanned_text(rec))
    for p in TRUE_CONDITION:
        t = t.replace(p, " ")
    t = fold_text(t)
    return any(p in t for p in APPROVAL)

def session_tainted(st: dict) -> bool:
    return bool(st.get("injection") or st.get("allow_list_held") or st.get("dangerous_held"))

def soft_defer(rec: dict) -> bool:
    f = fold_text(rec.get("untrusted_text") or "")
    return any(p in f for p in SOFT_DEFER)

def hard_hold(rec: dict, st=None):
    st = st or {}
    if rec.get("override") == "hold":
        return ("override_hold", "override hold is honored")
    pt = norm_tool(rec.get("proposed_tool") or "")
    if pt and is_dangerous(pt):
        return ("dangerous", f"proposed tool '{rec.get('proposed_tool')}' is on the dangerous list")
    if not (rec.get("proposed_tool") or "").strip():
        return ("allow_list", "proposed tool is missing or empty")
    if not in_allow(pt, rec.get("allow_list") or []):
        return ("allow_list", f"proposed tool '{rec.get('proposed_tool')}' is not on the user allow-list")
    if rec.get("prior_hold") or rec.get("prior_injection"):
        return ("session_prior", "prior turn was held or flagged as injection")
    if session_tainted(st):
        return ("session_prior", "session memory is tainted by an earlier injection, allow-list miss, dangerous tool, or split-goal hold")
    ch = content_hold(rec)
    if ch:
        return ch
    folded = fold_text(session_scanned_text(rec))
    cats = find_categories(folded)
    mem_cats = set(st.get("categories") or [])
    if has_carry_out(folded) and (mem_cats or cats):
        return ("session_split", "carry-out cue with a restricted category token in this turn or in session memory")
    sat = condition_satisfied(rec)
    if (st.get("pending_condition") or has_true_condition(folded)) and not sat:
        return ("session_condition", "a true condition is pending or stated, and is not satisfied on this turn")
    return None

def worker_decide(rec: dict, st=None):
    """H1-H7, H10, H11 and H9 only. Never returns FIRE_WEAPON. No H8."""
    h = hard_hold(rec, st)
    if h:
        layer, reason = h
        return None, layer, reason
    tool = rec.get("proposed_tool") or ""
    return tool, "worker", "proposed tool is on the allow-list and no hard hold fired"
