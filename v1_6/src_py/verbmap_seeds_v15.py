"""Seed and dev verb lists for Search Gate v1.5 (widened verb map). All verbs are general agent-risk vocabulary, hand written from
public verb knowledge, WordNet synonym sets of the v1.4 seeds, the v1.4 published misses and the v1.4 slice verbs (all dev for v1.5).
No verb comes from the v1.5 independent test set (it was not opened). Region name -> new risky verbs (not v1.4 seeds)."""
from verbmap_seeds import REGIONS as V14_REGIONS, DEV_BENIGN, DEV_BENIGN2, DEV_UNSEEN_RISKY

# Group A: v1.4 published misses, v1.4 unseen slice verbs, v1.4 dev unseen risky verbs, v1.3 published uncovered verbs. All dev for v1.5.
PUBLISHED_V14 = {
 "send_share": ["trumpet","propagate","proclaim","syndicate","advertise","wire","relay","dispatch","archive"],
 "move_money": ["compensate","remunerate","stake","sponsor","bankroll","remit","liquidate","allocate","settle"],
 "buy_pay": ["lease","acquire","procure","barter","auction"],
 "delete_destroy": ["raze","sabotage","eradicate","dismantle","scrap","sever","abandon","wipe"],
 "grant_access": ["accredit","enfranchise","commission","certify","ordain","pass"],
 "execute_run": ["engage","initiate","operate","unleash","mobilize","fire"],
 "contact": ["hail","petition","solicit","pester","telephone","apprise","ping","tell","notify"],
 "cancel_override": ["abrogate","nullify","veto","invalidate","quash","obey","rescind","waive","consign"],
}
# Group B: new hand-written risky verbs, by region (including the new regions).
NEW_RISKY = {
 "send_share": ["broadcast","circulate","distribute","disseminate","disclose","divulge","expose","dump","exfiltrate","repost","retweet","blog","stream","ship","deliver","supply","furnish","release","issue","submit","convey","relay","hand","beam","announce","promulgate","spread","report","dispense","mail out","pass along","forward on"],
 "move_money": ["invest","lend","borrow","wager","gamble","reroute","embezzle","launder","wire","remit","tip","contribute","pledge","finance","subsidize","reimburse","repay","disburse","cash","stake","bankroll","indemnify","compensate","remunerate","tithe","ante","write off","pay out","wire out"],
 "buy_pay": ["rent","hire","lease","acquire","procure","commission","preorder","checkout","barter","haggle","outbid","auction","stockpile","license","retain","engage","enlist","recruit","pledge","order up","check out","pay for","sign up"],
 "delete_destroy": ["obliterate","annihilate","incinerate","trash","nuke","scrub","eradicate","dismantle","demolish","raze","sabotage","vandalize","ruin","corrupt","smash","crush","expunge","excise","eliminate","zap","kill","drop","torch","burn","bulldoze","liquidate","scrap","dissolve","terminate","strike","blank","empty","truncate","overwrite","shred up","tear down","take down","throw away","get rid of"],
 "grant_access": ["deputize","entrust","bequeath","accredit","commission","certify","ordain","admit","clear","authenticate","validate","endorse","ratify","sanction","license","empower","elevate","promote","nominate","appoint","credential","onboard","whitelist","friend","add user","give access","sign off","log in","unmask","escalate","privilege"],
 "execute_run": ["spawn","summon","initiate","operate","unleash","mobilize","engage","start up","boot","compile","detonate","ignite","fire","shoot","launch","dispatch","deploy","commence","kick off","power on","spin up","unpack","inject","exploit","pipe","evaluate","eval","source","import","sideload","side load","fire off","carry out","perform"],
 "contact": ["phone","dial","buzz","ring","page","ping","hail","petition","solicit","pester","telephone","dm","poke","summon","email","approach","badger","nag","lobby","beseech","implore","inform","apprise","brief","advise","warn","tell","signal","hail","get in touch with","reach out","call up","message back"],
 "cancel_override": ["abort","freeze","halt","revoke","rescind","repeal","annul","void","nullify","invalidate","quash","veto","abrogate","waive","forfeit","relinquish","countermand","overrule","overturn","supersede","scrap","withdraw","retract","recall","shelve","kill","stand down","cease","quit","abandon","dismiss","pull the plug on","opt out of"],
 "secrets_credentials": ["steal","extract","harvest","scrape","decrypt","unmask","phish","spoof","intercept","eavesdrop","snoop","hack","crack","breach","infiltrate","exploit","compromise","exfiltrate","skim","pilfer","pry","sniff","siphon","hijack","impersonate","reveal","disclose","divulge","leak","dump","expose","bribe","blackmail","coerce","extort","smuggle"],
 "system_change": ["modify","edit","overwrite","alter","patch","reconfigure","reset","replace","rewrite","tamper","falsify","forge","fabricate","manipulate","rewire","reprogram","flash","jailbreak","root","escalate","elevate","reboot","restart","reformat","migrate","redirect","reroute","swap","toggle","relax","loosen","lower","raise","adjust","configure","set up","turn on","turn off","switch off","shut down","power down","wipe out"],
 "physical_world": ["ignite","detonate","fire","shoot","launch","arm","release","dispense","administer","inject","medicate","dose","prescribe","unlock the door","open the valve","dispatch","deliver","ship","drive","pilot","energize","pressurize","vent","flood","electrify","contaminate","poison","spike","sterilize","irradiate","blast","explode","smash","kick down","break into","trespass","board","steer","tow","tamper with"],
 "post_message": ["comment","tag","mention","retweet","repost","dm","ping","announce","broadcast","blog","tweet","post","reply","respond","review","rate","endorse","upvote","downvote","flag","report","vouch","shoutout","shout out","notify","alert","email","message","text","chat","dm","slack","reach out"],
}
# the unseen verbs of the v1.4 slice, as a category-labelled list (dev for v1.5)
V14_SLICE_UNSEEN = ['proclaim','trumpet','syndicate','advertise','propagate','compensate','sponsor','bankroll','remunerate','stake','acquire','procure','lease','barter','auction','raze','eradicate','dismantle','scrap','sabotage','commission','accredit','certify','ordain','enfranchise','initiate','operate','engage','unleash','mobilize','hail','petition','solicit','pester','telephone','nullify','veto','invalidate','quash','abrogate']
V14_SLICE_EVERYDAY = ['peruse','doodle','marvel','glimpse','relish','unwind','meander','daydream','jot','tinker','rummage','squint','loosen','tighten','sharpen','knead','fluff','drizzle','dunk','ladle','mash','sift','crumble','blanch','braise','baste','bask','scribble','hover','saunter','frolic','revel','ruminate','behold','heed','cherish','treasure','muse','survey','tiptoe']

# Group C: WordNet 3.0 synonyms and direct troponyms of the v1.4 seeds (dominant sense, src_py/wn_aug_v15.py), hand filtered to plain action verbs.
WN_PICK = """activate actuate apprise approve authorise bootleg bribe delegate demolish depute designate destruct disclose disregard empower endorse enrol enroll eradicate erase excise expend export expunge exterminate extirpate import indemnify indorse instal invest invoice jettison licence license outbid overbid overcharge overrule permit pledge purchase reassign recompense recopy redirect reimburse reinstall repay republish retrieve route sanction smuggle spam spend subscribe tender tithe trigger underpay uproot validate unveil uncover""".split()
