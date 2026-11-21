#!/usr/bin/env python3
"""v1.6 how-to page waiver (Python side of the clause-finder boundary). Hold-only elsewhere; this is the only place v1.6 lifts a v1.5 hold.
A page is a how-to page when most sentences open with a command verb. The waiver applies only when nothing on the page is aimed at an agent."""
import re
from instruction_check import tokenize, OVERRIDE_PHRASE, URL_RE, EMAIL_RE, SYS_TAG, NOUN_FOLLOW, DET_PRON
from map_check import NONVERB
STRONG_AGENT = {"assistant", "assistants", "ai", "chatbot", "llm", "llms", "claude", "chatgpt", "gpt", "gemini", "copilot", "grok", "agent", "agents", "chatbots", "bot", "bots"}
WAIVER_NOUNS = set("""money cash dollar dollars euro euros usd bucks card cards giftcard giftcards subscription subscriptions refund refunds transaction transactions
record records health patient patients allergy allergies medication medications prescription prescriptions diagnosis garage alarm alarms thermostat camera cameras sensor sensors sprinkler sprinklers
front motor motors actuator actuators arm gripper drone robot robots contact""".split())
WAIVER_VERBS = set("""delete erase wipe purge format install uninstall download upload execute sudo chmod email tweet unlock disable grant revoke approve authorize
reveal exfiltrate eval reboot shutdown disarm unlink impersonate phish leak reroute""".split())
CUE_PHRASE = re.compile(r"\b(urgent|urgently|asap|secretly|silently|without (?:telling|asking|mentioning|notifying|informing)|do not (?:tell|mention|reveal|inform)|don'?t (?:tell|mention|reveal|inform)|before (?:answering|replying|responding|you (?:answer|reply|respond))|translator'?s note|the reader (?:should|must|will|needs)|i (?:need|want|would like|'d like) you to|reader-agent|(?:your|the) (?:next|final) (?:reply|answer|response|message))\b", re.I)
ORDER_PREV = {"to", "will", "can", "could", "would", "must", "should", "please", "kindly", "now", "immediately", "just", "simply", "first", "then", "also", "finally", "need", "you", "shall", "and"}
NEG_IMP = {"dont", "never", "avoid"}
CFGH = {"min_imp": 3, "min_frac": 0.3}
def howto_info(ic, text, reasons=()):
    """returns (waive, info, stats). ic is any InstructionCheck (MapCheck15 works)."""
    if not text: return False, "empty", {}
    vis, hid = ic.split_hidden(text)
    if hid: return False, "cue:hidden_text", {}
    if ic.system_tag(text): return False, "cue:system_tag", {}
    if OVERRIDE_PHRASE.search(vis): return False, "cue:override_phrase", {}
    if URL_RE.search(vis) or EMAIL_RE.search(vis): return False, "cue:url_or_email", {}
    for rs in reasons:
        if ":override:" in rs or rs.startswith("system_tag"): return False, "cue:override_reason", {}
    if CUE_PHRASE.search(vis): return False, "cue:agent_phrase", {}
    toks = tokenize(vis)
    for t in toks:
        if t.w in STRONG_AGENT: return False, f"cue:addressee:{t.w}", {}
    n = len(toks); starts = [0] + [k + 1 for k, t in enumerate(toks) if t.brk == 2 and k + 1 < n]
    n_sent = n_imp = 0; cue = None
    for si, s0 in enumerate(starts):
        e = starts[si + 1] if si + 1 < len(starts) else n
        if e - s0 < 3: continue
        n_sent += 1
        r = ic._imp_start(toks, s0)
        w0 = toks[s0].w
        if r is None:
            if w0 in ("do",) and s0 + 1 < n and toks[s0 + 1].w in ("not", "dont", "never"): n_imp += 1; continue
            if w0 in NEG_IMP or w0.endswith("n't") and w0.startswith("don"): n_imp += 1
            continue
        j = r[1]; w = toks[j].w
        if w in NONVERB or (w not in ic.lex and w not in ic.t1 and w not in ic.t2): continue
        if toks[j].brk or (j + 1 < n and toks[j + 1].w in NOUN_FOLLOW) or ic._compound_noun(toks, j): continue
        n_imp += 1
        win = []
        for x in toks[j + 1:j + 9]:
            win.append(x.w)
            if x.brk == 2: break
        rw = ic.resource_words(win[:7])
        if not rw:
            wn = [x for x in win[:7] if x in WAIVER_NOUNS]
            if wn: rw = wn[0]
        if not rw and w in WAIVER_VERBS: rw = "verb"
        if rw: return False, f"cue:resource_object:{w}:{rw}", {"n_sent": n_sent, "n_imp": n_imp}
    for j, t in enumerate(toks):                       # orders in any shape (frames, "you must ...", after a comma): same cues
        w = t.w
        if w in NONVERB or (w not in ic.lex and w not in ic.t1 and w not in ic.t2): continue
        prev = toks[j - 1] if j else None
        nxt = toks[j + 1].w if j + 1 < n else ""
        shape = prev is None or prev.brk or prev.w in ORDER_PREV or nxt in DET_PRON
        if not shape or t.brk or nxt in NOUN_FOLLOW: continue
        win = []
        for x in toks[j + 1:j + 9]:
            win.append(x.w)
            if x.brk == 2: break
        rw = ic.resource_words(win[:7]) or next((x for x in win[:7] if x in WAIVER_NOUNS), None)
        if rw: return False, f"cue:order_object:{w}:{rw}", {"n_sent": n_sent, "n_imp": n_imp}
        if w in WAIVER_VERBS and (prev is None or prev.brk or prev.w in ORDER_PREV): return False, f"cue:order_verb:{w}", {"n_sent": n_sent, "n_imp": n_imp}
    st = {"n_sent": n_sent, "n_imp": n_imp, "frac": round(n_imp / max(1, n_sent), 3)}
    if n_imp >= CFGH["min_imp"] and n_sent and n_imp / n_sent >= CFGH["min_frac"]: return True, f"howto:{n_imp}/{n_sent}", st
    return False, f"not_howto:{n_imp}/{n_sent}", st
