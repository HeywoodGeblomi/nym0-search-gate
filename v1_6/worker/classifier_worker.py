"""Warm hold-only classifier for nym0clgate. Standard library + NumPy. Frozen artifact only.
  {"op":"ping"} -> {"ok":true,"pid":N}
  {"op":"classify","id":ID,"text":STR} -> {"id":ID,"score":FLOAT,"hold":BOOL,"threshold":FLOAT}
  {"op":"shutdown"} -> {"ok":true}
Test-only flags: --die-after N, --hang-after N.
Never outputs FIRE_WEAPON. Never names a tool. May only recommend a hold.
"""
import json, os, signal, socket, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src_py"))
from classifier_infer import Classifier
from instruction_check import InstructionCheck
from map_check15 import MapCheck15
from howto16 import howto_info

T0 = time.time()
args = sys.argv[1:]
def opt(k, d=None):
    return args[args.index(k) + 1] if k in args else d
SOCK = opt("--socket", str(ROOT / "run" / "classifier.sock"))
PIDF = opt("--pidfile", str(ROOT / "run" / "classifier.pid"))
WEIGHTS = opt("--weights", str(ROOT / "models" / "classifier_v1_6.json"))
DIE = int(opt("--die-after", -1)); HANG = int(opt("--hang-after", -1))
FAMILIES = opt("--families", str(ROOT / "models" / "verb_families_v1_3.json"))
MODELS = opt("--models", str(ROOT / "models"))
MAP_ENGINE = opt("--map-engine", "rust")   # rust: this worker only finds the orders; the Rust front door embeds and decides. python: this worker decides (ONNX Runtime), the reference for the parity check
MAP_RAISE = int(opt("--map-raise-after", -1))   # test-only: the map check raises after N requests (must become a hold)
INSTR_RAISE = int(opt("--instr-raise-after", -1))   # test-only: the instruction check raises after N requests (must become a hold)

def alive(path):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(2)
    try:
        s.connect(path); s.close(); return True
    except OSError:
        return False
if os.path.exists(SOCK) and alive(SOCK):
    print("classifier already running at", SOCK, flush=True); sys.exit(0)

clf = Classifier.load(WEIGHTS)
ic = InstructionCheck(FAMILIES)
mc = MapCheck15(FAMILIES, MODELS, embed=(MAP_ENGINE == "python"))
MAPM = mc.tag() if MAP_ENGINE == "python" else "rust-engine"
LOADED = time.time() - T0
if os.path.exists(SOCK):
    os.unlink(SOCK)
os.makedirs(os.path.dirname(SOCK) or ".", exist_ok=True)
srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); srv.bind(SOCK); srv.listen(4)
Path(PIDF).parent.mkdir(parents=True, exist_ok=True)
Path(PIDF).write_text(str(os.getpid()))
print(f"classifier ready pid={os.getpid()} loaded_in={LOADED:.3f}s sock={SOCK} die_after={DIE} hang_after={HANG} threshold={clf.threshold}", flush=True)
served = 0; real = 0; running = True
def bye(*_):
    try: os.unlink(SOCK)
    except OSError: pass
    sys.exit(0)
signal.signal(signal.SIGTERM, bye)
while running:
    conn, _ = srv.accept()
    f = conn.makefile("rwb", buffering=0)
    try:
        for raw in f:
            raw = raw.strip()
            if not raw: continue
            try: req = json.loads(raw)
            except Exception as e:
                f.write((json.dumps({"err": f"bad json: {e}"}) + "\n").encode()); continue
            op = req.get("op")
            if op == "ping":
                f.write((json.dumps({"ok": True, "pid": os.getpid(), "loaded_s": round(LOADED, 3), "served": served, "threshold": clf.threshold, "map_model": MAPM}) + "\n").encode())
            elif op == "shutdown":
                f.write(b'{"ok":true}\n'); running = False; break
            elif op == "classify":
                real += 1
                if DIE >= 0 and real > DIE:
                    os.kill(os.getpid(), signal.SIGKILL)
                if HANG >= 0 and real > HANG:
                    time.sleep(10**6)
                t = time.time()
                try:
                    text = req.get("text")
                    if text is None:
                        rec = req.get("record") or {}
                        from classifier_infer import span_text
                        text = span_text(rec)
                    held, score = clf.hold(text or "")
                    if INSTR_RAISE >= 0 and real > INSTR_RAISE: raise RuntimeError("instruction check test fault")
                    ih, ireasons = ic.check(text or "")
                    if MAP_RAISE >= 0 and real > MAP_RAISE: raise RuntimeError("map check test fault")
                    if MAP_ENGINE == "python": mh, mreasons = mc.check(text or "")
                    else: mc.candidates(text or ""); mh, mreasons = False, []
                    wv, winfo, _ = howto_info(mc, text or "", ireasons)     # v1.6: the only place a v1.5 hold can be lifted (see PREREG and DEVIATIONS)
                    out = {"relax": (winfo if wv else ""), "mapx": mc.mapx(), "id": req.get("id"), "score": float(score), "hold": bool(held), "threshold": float(clf.threshold), "instr": ("; ".join(ireasons[:3]) if ih else ""), "mapc": ("; ".join(mreasons[:3]) if mh else ""), "mapm": MAPM, "ms": round((time.time() - t) * 1000, 2)}
                except Exception as e:
                    out = {"id": req.get("id"), "err": f"{type(e).__name__}: {e}"}
                served += 1
                f.write((json.dumps(out) + "\n").encode())
            else:
                f.write((json.dumps({"err": f"unknown op {op}"}) + "\n").encode())
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        try: conn.close()
        except OSError: pass
bye()
