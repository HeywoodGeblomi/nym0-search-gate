"""Nym-0 instruction check (Search Gate v1.3). Hold-only. Standard library only. No spaCy, no NLTK at run time.

Built from Heywood's Nym-0 parts:
  Gerund-0 (rules.rs / gerund0.py): an -ing verb is a command only in an order frame ("start by sending ..."); a gerund noun
     ("sending files is risky"), an -ing adjective, and a progressive ("is sending") are not orders. Also the Nym-0 parser-free
     rules: clause breaks, negation scope, statement vs order (a third-person or past subject is a description), polite and
     lead-in frames (BARE / POL1 / POL3 / LEAD), conditionals.
  Synonym-0: seed verbs from general agent-risk categories fanned out to whole verb families (models/verb_families_v1_3.json,
     built from WordNet synonyms and troponyms by src_py/build_families.py).
Decision: HOLD if an order addressed to the reader or agent (an imperative clause, or a "you must / the assistant should / I need
you to / make sure to" frame) has a verb from a risky family. Hidden text (comments, alt text, hidden spans, zero-width and
tag characters) is scanned too, with a stricter rule. It can only add a hold. It never lifts one.
"""
import html, json, re, unicodedata
from pathlib import Path

ZW = dict.fromkeys(list(range(0x200B, 0x2010)) + [0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0xFEFF, 0x00AD, 0x034F, 0x180E] + list(range(0x202A, 0x202F)) + list(range(0x2066, 0x206A)))
AGENT = {"assistant","assistants","ai","agent","agents","model","llm","llms","bot","chatbot","claude","chatgpt","gpt","gemini","copilot","grok","ai-assistant","language"}
ADV = {"please","kindly","just","now","immediately","quickly","silently","quietly","first","next","then","also","finally","instead","simply","promptly","right","away","asap","urgently","again","carefully","secretly","always","still","and","but","so","thus","ok","okay","hey","well","oh","today","tonight","straight","directly","hereby","do","go","ahead","feel","free","definitely","absolutely"}
STRONG_MODAL = {"must","should","need","needs","have","has","ought","supposed","required","asked","instructed","expected","directed","told","requested","shall","better","obliged","going","commanded","ordered","meant"}
NEG_CONTR = {"dont","doesnt","didnt","cant","wont","isnt","arent","wasnt","shouldnt","mustnt","couldnt","wouldnt","havent","hasnt","neednt","aint"}
NEG = {"not","never","no","nobody","nothing","none","cannot","dont","cant","wont","neither","nor","avoid","refrain"}
NOUN_FOLLOW = {"of","is","was","are","were","has","had","have","will","would","can","could","may","might","shall","did","does","do","by","as","at","between","among","remains","became","becomes","became","include","includes","included","means","refers","involves","consists","occurs","takes","took","began","began","began"}
SKIP_AFTER_SUBJ = ADV | STRONG_MODAL | {"are","is","be","will","shall","ll","re","ve","d","can","could","would","been","am","hereby","really","to","must"}
FRAME_TO_PREV = {"sure","forget"}                                  # "make sure to", "be sure to", "don't forget to"
FRAME_TO_ADDRESSED = {"essential","important","required","necessary","critical","imperative","mandatory","urgent","vital","crucial","compulsory","instruction","instructions","directive","tasked","remember","ensure"}  # only when the sentence addresses "you" or an agent
ASK_PREV = {"need","want","wants","like","ask","asking","asked","request","requesting","requested","require","requires","required","instruct","instructing","instructed","expect","urge","wish","order","ordering","told","tell","telling","command","commanding","advise","demand","demanding","needs"}
POLITE_BEFORE = {"great","nice","appreciate","appreciated","helpful","good","wonderful","grateful","happy","glad","love","lovely","fine","useful","kind"}
LEAD_VERB = {"start","begin","proceed","commence","continue","go","feel","try","begin"}
COND = {"if","unless","when","whenever","while","although","because","since","as","once","after","before","whether","though","suppose","assuming","until","in"}
SENSITIVE = set("""password passwords credential credentials token tokens key keys apikey secret secrets passcode pin otp code codes login logins account accounts access permission permissions
admin administrator administrators privilege privileges role roles funds money balance payment payments card cards bank wallet crypto bitcoin ssn address addresses contacts contact
email emails message messages inbox history records record files file folder folders data document documents photos calendar appointment appointments meeting meetings subscription
subscriptions order orders invoice invoices repository repo database logs prompt conversation chat session sessions cookies location device devices lock door doors camera cameras alarm
thermostat router firewall settings setting config configuration security antivirus mfa owner ownership domain server vpn user users everyone everything garage heating light lights
oven stove purchase ticket tickets reservation booking flight flights hotel itinerary medication prescription health report reports details information info credit debit deposit loan
mortgage investment investments stock stocks shares portfolio holdings tax taxes salary payroll contract contracts""".split())
LINKOBJ = set("link links url urls site website page webpage http https www button here attachment attachments file download portal".split())
OVERRIDE_OBJ = set("""instruction instructions rule rules guideline guidelines prompt prompts direction directions constraint constraints policy policies restriction restrictions safeguard safeguards
guardrail guardrails command commands previous prior above earlier preceding everything safety system programming filter filters limit limits limitation limitations all any your these those
earlier context""".split())
PARTICIPLE_PREP = set("in at during between across within throughout around near amid among under since against".split())
DET_PRON = set("the a an my your our his her their this that these those all some any me us him them it you everyone everything each every no".split())
AUX_SET = set("is was are were has had have will would can could may might shall did does".split())
IRREG_PAST = set("fell rose went came became grew began hit rose saw took made gave ran sold bought paid sent kept held led met lost won set cut put shut".split())
OVERRIDE_PHRASE = re.compile(r"\b(do not|don't|dont|never|no longer(?: need to| have to)?|stop|cease|refuse to|pay no (?:attention|heed) to|need not|must not)\s+(?:to\s+)?(?:follow(?:ing)?|obey(?:ing)?|adhere(?:ring)? to|compl(?:y|ying) with|listen(?:ing)? to|heed(?:ing)?|respect(?:ing)?|apply(?:ing)?|use|using|attention to|heed to)?\s*(?:\w+\s+){0,3}?(?:previous|prior|earlier|above|preceding|original|initial|system|all|any|your)\s+(?:\w+\s+){0,2}?(?:instructions?|rules?|guidelines?|prompts?|directions?|constraints?|polic(?:y|ies)|restrictions?|safeguards?|guardrails?|commands?)|\b(?:stop|cease|do not|don't|never|no longer)\s+(?:to\s+)?(?:follow(?:ing)?|obey(?:ing)?|heed(?:ing)?)\s+(?:the |these |those |any )?(?:instructions?|rules?|guidelines?|directions?)\s+(?:above|before|given|provided|so far)", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
URL_RE = re.compile(r"(https?://|www\.)\S+|\b[\w-]+\.(com|org|net|io|ru|xyz|info|co)\b", re.I)
TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['\-][A-Za-z0-9]+)*|[^\sA-Za-z0-9]")
SENT_BREAK = set(".!?;:\n")
HIDE_STYLE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0|opacity\s*:\s*0|left\s*:\s*-\d{3,}|text-indent\s*:\s*-\d{3,}|color\s*:\s*(white|#fff\b|#ffffff|transparent)|height\s*:\s*0|width\s*:\s*0", re.I)

# ---- v1.6 additions (toggles so the dev configurations C0..C3 can be compared; the shipped defaults are all True) ----
CFG = {"end_fix": True, "system_tag": True, "resource_obj": True}
POLITE_END = {"please","kindly","now","immediately","just","simply","promptly","urgently","quickly","silently","quietly","first","then","also","finally","secretly","asap","must","should","shall","need"}
SYS_TAG = re.compile(r"(\[\s*/?\s*(?:system|sys|assistant|ai|agent|admin|administrator|developer|operator|instructions?|inst|override|root|sudo|important|priority)\b[^\]\n]{0,30}\]"
                     r"|<\s*/?\s*(?:system|sys|assistant|ai|agent|admin|developer|operator|instructions?|inst|override)\b[^>\n]{0,40}>"
                     r"|<<\s*/?\s*sys\s*>>|<\|\s*(?:im_start|system|assistant)[^|\n]{0,20}\|>"
                     r"|^[ \t]*#{2,}[ \t]*(?:system|instructions?)\b"
                     r"|\b(?:system|admin|assistant|developer|operator) (?:message|prompt|note|notice|override|instruction|instructions)[ \t]*:"
                     r"|^[ \t]*(?:system|admin|assistant)[ \t]*:)", re.I | re.M)
RESOURCE = set("""password passwords passcode passphrase passphrases credential credentials token tokens apikey apikeys secret secrets login logins account accounts database databases repo repos repository repositories
backup backups file files folder folders directory directories inbox mailbox calendar contacts wallet funds payment payments invoice invoices ssn cookie cookies session sessions ssh sudo shell terminal cron crontab env environment
endpoint endpoints server servers credit debit bank bitcoin crypto cryptocurrency paypal venmo email emails mail message messages dms chat history logs drive drives disk partition firewall router vpn privileges permissions admin
oauth api secrets keychain""".split())
PART_OBJ = {"up","down","off","out","over","away","back","in","on"}
RESOURCE_AFTER = {"private","ssh","api","security","secret","license","encryption","master","access","public","signing","recovery"}   # "key"/"keys" is a resource only after one of these
BROWSER_COOKIE = {"login","browser","session","tab","tabs","site","website","auth"}
KITCHEN_SAFE = {"cookies","cookie","logs","drive","drives","mail","server","servers","chat","history","backup","message","messages","session","sessions","shell","terminal","environment","env","credit"}   # ambiguous words: only a resource with a digital neighbour (see resource_words)
DIGITAL_NEIGHBOUR = set("""login browser site website tab tabs account user users email web online remote ssh shared cloud admin database server repository config system network wifi api auth every all your the my our his her their these those them it""".split())

class Tok:
    __slots__ = ("w", "o", "brk")
    def __init__(self, w, o, brk=False): self.w, self.o, self.brk = w, o, brk

def tokenize(text):
    """Words (lowercase). tok.brk: 0 none, 1 soft break (comma, dash) after this word, 2 hard break (. ! ? ; : newline | ) after it."""
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    toks = []
    pos = 0
    for m in TOKEN_RE.finditer(text):
        s = m.group(0)
        gap = text[pos:m.start()]
        pos = m.end()
        if toks and "\n" in gap: toks[-1].brk = 2
        if s[0].isalnum():
            toks.append(Tok(s.lower().replace("'", "") if not s.lower().endswith("n't") else s.lower(), s))
        elif toks:
            if s in ".!?;:|": toks[-1].brk = 2
            elif s in ",\u2014\u2013": toks[-1].brk = max(toks[-1].brk, 1)
            elif s in "([{\"\u201c": toks[-1].brk = max(toks[-1].brk, 1)
            elif s in ")]}\u201d": pass
            elif s == "-": toks[-1].brk = max(toks[-1].brk, 1)
    return toks

def load_families(path):
    f = json.loads(Path(path).read_text())
    t1, t2, ovr = {}, {}, set()
    for cat, e in f["categories"].items():
        for n in e["tier1"]:
            (ovr if cat == "override_rules" else None)
            if cat == "override_rules": ovr.add(n)
            else: t1.setdefault(n, cat)
        for n in e["tier2"]:
            if cat == "override_rules": ovr.add(n) if n in ("discard","abandon") else None
            else: t2.setdefault(n, cat)
    for n in list(t2):
        if n in t1: del t2[n]
    return t1, t2, ovr, set(f["verb_lexicon"])

class InstructionCheck:
    def __init__(self, families_path):
        self.t1, self.t2, self.ovr, self.lex = load_families(families_path)
        self.link_verbs = {"click","visit","navigate","browse","open","follow","go","load","access","connect","download"}
        self.last = []   # reasons of the last call

    # ---------- hidden text ----------
    def split_hidden(self, raw):
        """Return (visible_text, [hidden_segments]). Comments, alt text, link titles, hidden-style elements, tag characters, script/meta."""
        hidden = []
        # Unicode tag characters (U+E0000 block) decode to hidden ASCII
        tagc = "".join(chr(ord(c) - 0xE0000) for c in raw if 0xE0020 <= ord(c) <= 0xE007E)
        if tagc: hidden.append(tagc)
        raw = "".join(c for c in raw if not (0xE0000 <= ord(c) <= 0xE007F))
        t = html.unescape(raw)
        t = unicodedata.normalize("NFKC", t).translate(ZW)
        def grab(rx, grp=1, repl=" "):
            nonlocal t
            for m in rx.finditer(t): 
                g = m.group(grp)
                if g and g.strip(): hidden.append(g)
            t = rx.sub(repl, t)
        grab(re.compile(r"<!--(.*?)-->", re.S))
        grab(re.compile(r"^\s*\[(?://|comment)\]:\s*(?:#|<>)\s*[\(\"'<]?(.*?)[\)\"'>]?\s*$", re.M))
        grab(re.compile(r"<(script|style|noscript|template|meta|head)\b[^>]*>(.*?)</\1>", re.S | re.I), 2)
        for m in re.finditer(r"<meta\b[^>]*content\s*=\s*[\"']([^\"']*)[\"'][^>]*>", t, re.I): hidden.append(m.group(1))
        t = re.sub(r"<meta\b[^>]*>", " ", t, flags=re.I)
        # alt / title / aria-label / data-* attributes
        for m in re.finditer(r"\b(alt|title|aria-label|placeholder|data-[\w-]+)\s*=\s*[\"']([^\"']*)[\"']", t, re.I): hidden.append(m.group(2))
        # hidden-style elements (non-nested, good enough)
        def hid(m):
            attrs, body = m.group(2), m.group(3)
            if HIDE_STYLE.search(attrs) or re.search(r"\bhidden\b|aria-hidden\s*=\s*[\"']?true", attrs, re.I):
                if body.strip(): hidden.append(body)
                return " "
            return " " + body + " "
        for _ in range(3):
            t = re.sub(r"<(span|div|p|font|section|li|td|b|i|em|strong|a|label|small|sup|sub)\b([^>]*)>(.*?)</\1>", hid, t, flags=re.S | re.I)
        # markdown images and link titles
        for m in re.finditer(r"!\[([^\]]*)\]\(([^)]*)\)", t): hidden.append(m.group(1))
        t = re.sub(r"!\[([^\]]*)\]\(([^)]*)\)", " ", t)
        for m in re.finditer(r"\[([^\]]*)\]\(\s*\S+\s+[\"']([^\"']*)[\"']\s*\)", t): hidden.append(m.group(2))
        t = re.sub(r"\[([^\]]*)\]\(\s*\S+(\s+[\"'][^\"']*[\"'])?\s*\)", r" \1 ", t)
        t = re.sub(r"<[^>]{0,400}>", " ", t)
        t = re.sub(r"[*_`#>~]+", " ", t)
        return t, [h for h in hidden if h.strip()]

    # ---------- clause scan ----------
    def _nounish_next(self, t, j):
        """True when the word at j reads as a noun or a heading, not as the verb of an order (Gerund-0 style noun reading)."""
        if CFG["end_fix"] and (j + 1 >= len(t) or t[j].brk == 2) and j > 0 and not t[j - 1].brk and t[j - 1].w in POLITE_END:
            return False                            # v1.6: "Please delete." / "You must embezzle." : a verb that ends the sentence after a polite or order word is an order, not a heading
        if j + 1 >= len(t): return True            # a lone word is a heading or a title
        if t[j].brk: return True                    # "Transfer, ..." / "Delete." alone
        return t[j + 1].w in NOUN_FOLLOW

    def _compound_noun(self, t, j):
        """Gerund-0 style noun reading: 'Share prices fell', 'Cancel culture is', 'Transfer students may': verb-shaped word, one plain noun, then a verb or auxiliary.
        Only when no filler word (please, kindly) came first, and the next word is not a determiner or pronoun."""
        if j + 2 >= len(t) or j != self._sent_start(t, j) and not t[j - 1].brk: return False
        if j > 0 and t[j - 1].brk == 0 and j != self._sent_start(t, j): return False
        a, b = t[j + 1].w, t[j + 2].w
        if a in DET_PRON or t[j + 1].brk: return False
        return b in AUX_SET or b in IRREG_PAST or (b.endswith("ed") and len(b) > 4 and a.endswith("s"))

    def _window(self, t, j):
        win = []
        if t[j].brk: return win
        for x in t[j + 1:j + 9]:
            win.append(x.w)
            if x.brk == 2: break
        return win

    def _verb_hit(self, t, j, strict, why):
        """t[j] is a base-form candidate at an order position. Return a reason string or None."""
        w = t[j].w
        win = self._window(t, j)
        raw_after = " ".join(x.o for x in t[j + 1:j + 9])
        if w in ("shoot", "ship", "fire"):   # Synonym-0 'send' family (hand-written seeds): shoot/ship/fire off + a recipient (Nym-0 recipient rules A and B)
            rest = win[1:] if win[:1] and win[0] in ("over", "off", "along") else win
            ruleA = rest[:1] and rest[0] in ("me","us","him","her","them","you") and len(rest) > 1 and rest[1] in DET_PRON
            ruleB = False
            for q, x in enumerate(t[j + 1:j + 9]):
                if x.w == "to" and q + 1 < len(t[j + 1:j + 9]):
                    nx = t[j + 1 + q + 1]
                    if nx.w in ("me","us","him","her","them","you","everyone","everybody") or nx.o[:1].isupper(): ruleB = True
                if x.brk == 2: break
            return f"risky:outbound_data:{w}" if (ruleA or ruleB) else None
        if self._nounish_next(t, j) and not (strict and why.startswith("frame")): return None
        if why == "imperative" and self._compound_noun(t, j): return None
        if w in ("set", "put", "cast", "shut", "bid") and win[:1] and win[0] in PARTICIPLE_PREP: return None   # "Set in 1999, the game ..." is a participle, not an order
        if w in self.ovr:
            if any(x in OVERRIDE_OBJ for x in win) or (strict and w in ("ignore","disregard","forget","override","bypass","circumvent")):
                return f"override:{w}"
            return None
        if w in self.t1: return f"risky:{self.t1[w]}:{w}"
        for pre in ("re", "un", "de", "dis", "over", "under", "mis", "pre", "co", "out", "up"):   # derivational fan-out: reorder, resend, repurchase, unshare
            if w.startswith(pre) and w[len(pre):] in self.t1 and len(w) - len(pre) >= 3:
                return f"risky:{self.t1[w[len(pre):]]}:{w}"
        if w in self.link_verbs:
            if any(x in LINKOBJ or x in SENSITIVE for x in win) or URL_RE.search(raw_after) or EMAIL_RE.search(raw_after): return f"link:{w}"
            if w not in self.t2: return None
        if w in self.t2:
            if w in ("turn","switch") and win[:1] and win[0] in ("off","down"): return f"risky:cancel_disable:{w} {win[0]}"
            if any(x in SENSITIVE for x in win) or EMAIL_RE.search(raw_after) or URL_RE.search(raw_after):
                return f"risky2:{self.t2[w]}:{w}"
            return None
        if strict and w in self.lex and w not in NOUN_FOLLOW:
            return f"any_verb_strict:{w}"
        if CFG["resource_obj"] and w in self.lex and w not in NOUN_FOLLOW:
            prev = t[j - 1].w if j > 0 and not t[j - 1].brk else ""
            nxt = t[j + 1].w if j + 1 < len(t) else ""
            if nxt in DET_PRON or nxt in PART_OBJ or prev in POLITE_END or (why == "frame" and prev in ("to", "will", "can", "could", "would")):   # an order shape, not a noun phrase ("Wire transfer, bank transfer, ...")
                rw = self.resource_words(win[:7])
                if rw: return f"resource_obj:{w}:{rw}"
        return None

    def resource_words(self, win):
        """An agent-reachable resource (files, credentials, accounts, money, messages, code) in the object window of an order. Ambiguous words need a digital neighbour."""
        for q, x in enumerate(win):
            if x in ("key", "keys") and q > 0 and win[q - 1] in RESOURCE_AFTER: return x
            if x in RESOURCE:
                if x in KITCHEN_SAFE:
                    near = win[max(0, q - 2):q] + win[q + 1:q + 3]
                    if x in ("cookie", "cookies"):
                        if not any(n in BROWSER_COOKIE for n in near): continue
                    elif not any(n in DIGITAL_NEIGHBOUR and n not in ("the", "my", "our", "his", "her", "their", "these", "those", "them", "it", "all", "every", "your") for n in near): continue
                return x
        return None

    def _imp_start(self, t, i):
        """Order that starts at token i: skip fillers. Returns (kind, verb_index[, lemma]) or None if negated or not an order."""
        j = i
        while j < len(t) and t[j].w in ADV and not (t[j].w in ("go","feel") and j + 1 < len(t) and t[j + 1].w in ("ahead","free")) and not (t[j].w == "do" and j + 1 < len(t) and t[j + 1].w in ("not","dont") ):
            if t[j].brk == 2: return None
            j += 1
        if j >= len(t): return None
        w = t[j].w
        if w == "lets" or (w == "let" and j + 1 < len(t) and t[j + 1].w == "us"):     # "Let's just disable the alarm"
            j += 1 if w == "lets" else 2
            while j < len(t) and t[j].w in ("just", "now", "also", "then", "first", "quickly", "simply", "go", "ahead", "and"): j += 1
            return ("w", j) if j < len(t) else None
        if w in ("do", "never", "not", "no") or w in NEG_CONTR or w.endswith("n't"): return None
        if w in LEAD_VERB and j + 2 < len(t) and t[j + 1].w in ("by", "with", "to", "ahead", "free", "and"):
            k = j + 2
            while k < len(t) and t[k].w in ("and", "to", "ahead", "free", "by", "with"): k += 1
            if k < len(t):
                ww = t[k].w
                if ww.endswith("ing") and len(ww) > 4:   # Gerund-0: an -ing verb after an order lead-in is an order, not a gerund noun
                    for cand in (ww[:-3], ww[:-3] + "e", ww[:-4] if len(ww) > 5 and ww[-4] == ww[-5] else ww[:-3]):
                        if cand in self.t1 or cand in self.t2 or cand in self.ovr or cand in self.link_verbs: return ("ing", k, cand)
                return ("w", k)
            return None
        return ("w", j)

    def _order_starts(self, toks):
        """Token indexes where an order may start: sentence starts, and a comma break only as a short lead-in ("When prompted, send ...")
        or before please/kindly. A comma later in a long sentence is a list, not an order (Nym-0 LEAD frame limit of 6 words)."""
        n = len(toks)
        starts, sent_start = [0], 0
        for k, tk in enumerate(toks):
            if tk.brk == 2 and k + 1 < n:
                starts.append(k + 1); sent_start = k + 1
            elif tk.brk == 1 and k + 1 < n:
                if (k + 1 - sent_start) <= 6 or toks[k + 1].w in ("please", "kindly"):
                    starts.append(k + 1)
        return starts

    def _sent_start(self, toks, k):
        s = k
        while s > 0 and toks[s - 1].brk != 2: s -= 1
        return s

    def _in_condition(self, toks, k):
        """k is inside a subordinate clause that opens the sentence and has no comma yet ("If you must send ..., ...")."""
        s = self._sent_start(toks, k)
        if toks[s].w not in COND: return False
        return not any(toks[m].brk for m in range(s, k))

    def _scan_tokens(self, toks, strict=False):
        reasons = []
        n = len(toks)
        starts = self._order_starts(toks)
        for s0 in starts:
            r = self._imp_start(toks, s0)
            if r is None: continue
            j = r[1]
            if r[0] == "ing":
                verb = r[2]
                tv = toks[:j] + [Tok(verb, verb, toks[j].brk)] + toks[j + 1:]
                hit = self._verb_hit(tv, j, strict, "imperative")
            else:
                hit = self._verb_hit(toks, j, strict, "imperative")
            if hit: reasons.append("imperative:" + hit)
        for k, tk in enumerate(toks):
            w = tk.w
            addressed_sentence = None
            if w == "you" or w in AGENT or w in ("reader", "readers"):
                if not (tk.brk and w in AGENT):
                    j = k + 1
                    seen_modal = False
                    steps = 0
                    inverted = k > 0 and toks[k - 1].w in ("can", "could", "would", "will") and not toks[k - 1].brk
                    if k > 0 and w == "you" and not toks[k - 1].brk:      # "make sure you ...", "ensure you ...", "essential that you ..."
                        pv = toks[k - 1].w
                        if pv in ("sure", "ensure") or (pv == "that" and k > 1 and toks[k - 2].w in ("sure", "ensure", "essential", "important", "necessary", "vital", "critical", "imperative", "required")): seen_modal = True
                        # polite requests: "it would be great if you could ...", "I would appreciate it if you would ..."
                        if pv == "if" and k + 1 < n and toks[k + 1].w in ("could", "would", "can", "will") and any(x.w in POLITE_BEFORE for x in toks[max(0, k - 7):k]): seen_modal = True
                    if w in AGENT or w == "reader" or w == "readers": pass
                    while j < n and steps < 7:
                        x = toks[j].w
                        if x in NEG or x in NEG_CONTR or x.endswith("n't"): j = None; break
                        if x in STRONG_MODAL: seen_modal = True
                        if x == "will" and j + 1 < n and toks[j + 1].w in ("now","then","first","also","next","immediately"): seen_modal = True
                        if x in SKIP_AFTER_SUBJ and not toks[j - 1].brk:
                            j += 1; steps += 1; continue
                        break
                    if j is not None and j < n and (seen_modal or inverted) and not toks[j - 1].brk and not self._in_condition(toks, k):
                        hit = self._verb_hit(toks, j, strict, "frame")
                        if hit: reasons.append("frame:" + hit)
            if w == "mind" and k + 1 < n and k >= 1 and toks[k - 1].w in ("you", "i", "we") and not any(x.w in NEG for x in toks[max(0, k - 4):k]):
                ww = toks[k + 1].w      # Gerund-0: "-ing" after "would you mind" is a polite order, not a gerund noun
                for cand in (ww[:-3], ww[:-3] + "e", ww[:-4] if len(ww) > 5 and ww[-4] == ww[-5] else ww[:-3]):
                    if ww.endswith("ing") and len(ww) > 4:
                        tv = toks[:k + 1] + [Tok(cand, cand, toks[k + 1].brk)] + toks[k + 2:]
                        hit = self._verb_hit(tv, k + 1, strict, "frame")
                        if hit: reasons.append("frame_mind:" + hit); break
            if w == "you" and k + 2 < n and toks[k + 1].w == "to" and any(x.w in ASK_PREV for x in toks[max(0, k - 4):k]):
                if not any(x.w in NEG for x in toks[max(0, k - 4):k]):
                    hit = self._verb_hit(toks, k + 2, strict, "frame")
                    if hit: reasons.append("frame_ask:" + hit)
            if w == "to" and k + 1 < n and not self._in_condition(toks, k):
                prev = [x.w for x in toks[max(0, k - 3):k]]
                if any(p in NEG for p in prev): continue
                ok = any(p in FRAME_TO_PREV for p in prev)
                if not ok and any(p in FRAME_TO_ADDRESSED for p in prev):
                    s0 = self._sent_start(toks, k)
                    ok = any(x.w in ("you", "your") or x.w in AGENT for x in toks[s0:k])
                if not ok and k >= 3 and toks[k - 1].w in ("is", "are") and toks[k - 2].w in ("task", "job", "goal", "step", "mission", "objective") and toks[k - 3].w in ("your", "next", "first", "final", "only", "current"):
                    ok = True
                if ok:
                    hit = self._verb_hit(toks, k + 1, strict, "frame")
                    if hit: reasons.append("frame_to:" + hit)
        out = list(dict.fromkeys(reasons))
        if not out: out = self._coordinated(toks, strict, starts)
        return out

    def _coordinated(self, toks, strict, starts):
        """A later verb joined by and/then/also to a sentence that opens with an order ("Open the file and send it to ...")."""
        out = []
        n = len(toks)
        for si, s0 in enumerate(starts):
            e = starts[si + 1] if si + 1 < len(starts) else n
            e = min(e, n)
            r = self._imp_start(toks, s0)
            if r is None or r[0] != "w": continue
            first = toks[r[1]].w
            if first not in self.lex and first not in self.t1 and first not in self.t2 and first not in self.link_verbs and not self._verb_hit(toks, r[1], False, "imperative"): continue
            if self._nounish_next(toks, r[1]): continue
            # the sentence's own words after the first verb up to a hard break
            end = r[1]
            while end < n and toks[end].brk != 2: end += 1
            for k in range(r[1] + 1, min(end + 1, n)):
                if toks[k].w in ("and", "then", "also") and k + 1 < n:
                    m = self._imp_start(toks, k + 1)
                    if m and m[0] == "w":
                        hit = self._verb_hit(toks, m[1], strict, "imperative")
                        if hit: out.append("coordinated:" + hit)
        return list(dict.fromkeys(out))

    def system_tag(self, raw):
        """v1.6: text inside a system-style tag is addressed to the agent. Returns a reason when a tag is followed by at least three words, else None."""
        if not raw: return None
        t = unicodedata.normalize("NFKC", html.unescape("".join(c for c in raw if not (0xE0000 <= ord(c) <= 0xE007F)))).translate(ZW)
        for m in SYS_TAG.finditer(t):
            seg = t[m.end():m.end() + 240]
            seg = re.split(r"\[\s*/|<\s*/|<<\s*/", seg)[0]
            if len(re.findall(r"[A-Za-z]{2,}", seg)) >= 3: return "system_tag:" + m.group(0)[:24].strip().lower()
        return None

    def check(self, raw):
        self.last = []
        if not raw: return False, []
        vis, hid = self.split_hidden(raw)
        vt = tokenize(vis)
        reasons = list(self._scan_tokens(vt, strict=False))
        m = OVERRIDE_PHRASE.search(vis)
        if m: reasons.append("override_phrase:" + m.group(0)[:40].lower())
        if CFG["system_tag"]:
            st = self.system_tag(raw)
            if st: reasons.append(st)
        for h in hid:
            ht = tokenize(h)
            for r in self._scan_tokens(ht, strict=True):
                reasons.append("hidden:" + r)
            m = OVERRIDE_PHRASE.search(h)
            if m: reasons.append("hidden:override_phrase:" + m.group(0)[:40].lower())
            ws = [x.w for x in ht]
            if (any(x in AGENT for x in ws[:12]) and any(x in ("you","your","must","should","please","ignore","always","never") for x in ws)) or (ws[:1] and ws[0] in ("ignore","disregard","forget","always","never","important","note","system","assistant","ai","instruction","instructions")):
                reasons.append("hidden:addresses_agent")
        # an explicitly addressed agent ("Assistant, <verb> ...") with any order verb
        for k, tk in enumerate(vt):
            if tk.w in ("assistant", "assistants", "ai", "chatbot", "llm", "claude", "chatgpt", "gemini", "copilot", "grok") and tk.brk and k + 1 < len(vt):
                st = self._imp_start(vt, k + 1)
                if st and st[0] == "w" and vt[st[1]].w in self.lex and not self._nounish_next(vt, st[1]):
                    reasons.append(f"agent_addressed_order:{vt[st[1]].w}")
        self.last = list(dict.fromkeys(reasons))
        return bool(self.last), self.last

if __name__ == "__main__":
    import sys
    ic = InstructionCheck(Path(__file__).resolve().parents[1] / "models" / "verb_families_v1_3.json")
    for line in sys.stdin:
        h, r = ic.check(line.rstrip("\n"))
        print("HOLD" if h else "ok  ", line.strip()[:90], r[:3])
