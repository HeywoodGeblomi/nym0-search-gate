#!/usr/bin/env python3
"""Synonym-0 fan-out for the Search Gate instruction check (v1.3).
Seeds come from general agent-risk categories (locked in PREREG.md). Each seed verb is fanned out through WordNet 3.0:
the dominant senses of the seed, their synonyms, and their troponyms (one level of more-specific verbs).
Writes a frozen JSON table, so the gate needs no NLTK at run time. Build-time only: needs nltk + the wordnet corpus."""
import json, sys, hashlib
from pathlib import Path
from nltk.corpus import wordnet as wn
ROOT = Path(__file__).resolve().parents[1]

# category -> (tier1 seeds: an agent-addressed order with this verb is enough to hold,
#              tier2 seeds: ambiguous everyday verbs; need a sensitive object or an outside target as well)
SEEDS = {
 "outbound_data": (["send","forward","email","share","post","publish","upload","transmit","reveal","export","mail","tweet","leak"],
                   ["give","show","tell","print","copy","reply","message","text","provide","hand","pass","output","paste","attach","include"]),
 "destroy": (["delete","remove","erase","wipe","destroy","purge","uninstall","format","shred"], ["drop","clear","empty","reset","discard"]),
 "money_commerce": (["transfer","pay","withdraw","deposit","purchase","buy","order","sell","refund","donate","bid","subscribe","reserve","book","schedule","reschedule"],
                    ["charge","bill","trade","spend","fund","send","add","redeem"]),
 "authorize_identity": (["approve","grant","authorize","unlock","revoke","invite","sign","whitelist","delegate","impersonate","enroll","register"],
                        ["allow","enable","permit","confirm","accept","verify","assign","change","update","reset","set","create","modify","edit","replace","overwrite"]),
 "cancel_disable": (["cancel","terminate","deactivate","disable","suspend","unsubscribe","disarm","decommission","shutdown"], ["close","stop","lock","block","turn","switch","end","pause","halt"]),
 "execute_acquire": (["execute","install","download","launch","deploy","invoke","trigger","activate","fetch"], ["run","open","call","use","load","start","follow","go","access","connect","enter","type","click","visit","navigate","browse"]),
 "override_rules": (["ignore","disregard","forget","override","bypass","circumvent","neglect","skip"], ["stop","drop","discard","abandon","set"]),
}
# lemmas never added by fan-out (too general or mostly non-agent senses)
DENY = set("time can may will shall must need dare second foot list file edit command default closure cloture climax dangle decide complete hesitate bench bone broom bur burl burr bust gut hull husk ream scoop sponge spoon stone towel tusk weed harvest hollow indent lade laden ladle muck rape sack scalp shed spoon squeegee goose nip pinch pool pouch print out tweak twirp unfold unwrap unpack undress osculate excavate airt bewray blackwash communalise communalize prostitute corrupt bribe congratulate felicitate wedge sop spool second remainder recede retreat foot repair retail instruct enjoin command bless damn imprecate maledict beshrew anathemise anathemize bedamn crucify enthrone astrogate pilot spark tick vest sightsee voyage frequent conjure retrofit pension visa task trademark patent certificate allowance depute devolve matriculate unionise unionize award elevate demote promote relegate adjudicate adjourn invalid handicap pinion hock offset countervail paralyse paralyze vanish disappear ablate ax axe can aspirate expectorate defang dehorn demagnetise demagnetize delouse delve disburden dilapidate harry rase ravage rape ream wrack unsaddle offsaddle unstring unseat unhinge undock unburden dislodge expel oust circumcise amputate disembowel eviscerate exenterate enucleate epilate depilate decorticate debone decalcify decarbonise decarbonize decarburise decarburize decoke degas demineralise demineralize demyelinate descale desorb despoil detoxicate detoxify detusk hypophysectomise hypophysectomize leach resect rubricate shuck pulverise pulverize vandalise vandalize beleaguer besiege discount discredit disoblige ebb muff outfox outsmart outwit overreach overthrow pretermit scoff slight snub unlearn demilitarise demilitarize inactivate resuspend finalise finalize conclude cease culminate discontinue partake peach tattle blab confide gazette placard muckrake netmail".split())
STOP = set("be have do get make take put go come see look know think want need like say tell ask let keep hold bring leave turn move change set run use give try find call work play show feel seem become begin start end stop help live pass cut hit fall raise rise follow lead meet lose win pay spend sit stand walk talk speak read write learn teach grow draw break build cover carry catch charge check clear close cost count cross drive eat fill fire fix fly hang hear hurt join jump kick kill kiss land laugh lay lie lift light lock mark mean mix note offer pick pull push reach rest ring roll rub save sell send shake share shoot shut sing sleep smell smile stay step stick strike swim touch train travel wait wake wash watch wear wish worry".split())
KEEP_ALWAYS = set()  # filled with seeds
def lemmas_of(ss, need_count=False):
    """single-word lowercase lemmas of a synset, kept only when this synset is one of the lemma's two dominant verb senses
    (WordNet order is by frequency of use), and the lemma has at most 5 verb senses. This drops very polysemous words."""
    out = []
    for l in ss.lemmas():
        n = l.name()
        if "_" in n or "-" in n or not n.isalpha() or not n.islower(): continue
        vs = wn.synsets(n, "v")
        if ss not in vs[:2] or len(vs) > 5: continue
        if need_count and l.count() == 0: continue
        out.append(n)
    return out
def fan(seed, nsenses=2, troponyms=True):
    found = {}
    syns = wn.synsets(seed, "v")[:nsenses]
    for si, ss in enumerate(syns):
        for n in lemmas_of(ss):
            found.setdefault(n, f"synonym:{ss.name()}")
        for t in (ss.hyponyms() if troponyms else []):          # troponyms
            for n in lemmas_of(t, need_count=True):
                found.setdefault(n, f"troponym:{t.name()}<{ss.name()}")
    return found
def main():
    fam = {"wordnet": wn.get_version(), "categories": {}}
    for cat, (t1, t2) in SEEDS.items():
        e = {"tier1_seed": t1, "tier2_seed": t2, "tier1": {}, "tier2": {}}
        for tier, seeds in (("tier1", t1), ("tier2", t2)):
            for s in seeds:
                e[tier][s] = "seed"
            for s in seeds:
                # tier-2 seeds are ambiguous: dominant sense synonyms only, no troponyms
                for n, why in (fan(s, nsenses=2, troponyms=True) if tier == "tier1" else fan(s, nsenses=1, troponyms=False)).items():
                    if n in e[tier] or n in STOP or n in DENY: continue
                    e[tier][n] = f"{why} via {s}"
        fam["categories"][cat] = e
    # a lemma that is tier1 anywhere wins over tier2
    t1all = {n for c in fam["categories"].values() for n in c["tier1"]}
    for c in fam["categories"].values():
        for n in list(c["tier2"]):
            if n in t1all and c["tier2"][n] != "seed": del c["tier2"][n]
    # general verb lexicon (any WordNet verb with a corpus count of at least 2 in some verb sense): used only for agent-addressed and hidden text
    lex = set()
    for ss in wn.all_synsets("v"):
        for l in ss.lemmas():
            n = l.name()
            if n.isalpha() and n.islower() and l.count() >= 2: lex.add(n)
    fam["verb_lexicon"] = sorted(lex)
    out = ROOT/"models"/"verb_families_v1_3.json"
    out.write_text(json.dumps(fam, indent=1, sort_keys=True))
    print(out, hashlib.sha256(out.read_bytes()).hexdigest())
    for cat, c in fam["categories"].items():
        print(cat, len(c["tier1"]), len(c["tier2"]))
main()
