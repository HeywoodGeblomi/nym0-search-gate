"""Warm policy worker for nym0gate. Standard library only. Same socket protocol as official Nym-0 v3.3.
  {"op":"ping"} -> {"ok":true,"pid":N,...}
  {"op":"decide","id":ID,"record":{...}} -> {"id":ID,"final":TOOL|null,"reason":STR}
  {"op":"shutdown"} -> {"ok":true} then exit
Test-only flags: --die-after N (SIGKILL itself on the (N+1)th real request, before answering), --hang-after N.
Re-applies MULTITURN_POLICY_v1 hard holds (including the session snapshot sent with the request) and the explicit ALLOW path. Never outputs FIRE_WEAPON. Does not apply H8. The worker does not keep its own session map.
"""
import json, os, signal, socket, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src_py"))
from policy import worker_decide, is_dangerous, norm_tool

T0 = time.time()
args = sys.argv[1:]
def opt(k, d=None):
    return args[args.index(k) + 1] if k in args else d
SOCK = opt("--socket", str(ROOT / "run" / "worker.sock"))
PIDF = opt("--pidfile", str(ROOT / "run" / "worker.pid"))
DIE = int(opt("--die-after", -1)); HANG = int(opt("--hang-after", -1))

def alive(path):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(2)
    try:
        s.connect(path); s.close(); return True
    except OSError:
        return False
if os.path.exists(SOCK) and alive(SOCK):
    print("worker already running at", SOCK, flush=True); sys.exit(0)

LOADED = time.time() - T0
if os.path.exists(SOCK):
    os.unlink(SOCK)
srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); srv.bind(SOCK); srv.listen(4)
Path(PIDF).parent.mkdir(parents=True, exist_ok=True)
Path(PIDF).write_text(str(os.getpid()))
print(f"worker ready pid={os.getpid()} loaded_in={LOADED:.3f}s sock={SOCK} die_after={DIE} hang_after={HANG}", flush=True)
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
                f.write((json.dumps({"ok": True, "pid": os.getpid(), "loaded_s": round(LOADED, 3), "served": served}) + "\n").encode())
            elif op == "shutdown":
                f.write(b'{"ok":true}\n'); running = False; break
            elif op == "decide":
                real += 1
                if DIE >= 0 and real > DIE:
                    os.kill(os.getpid(), signal.SIGKILL)
                if HANG >= 0 and real > HANG:
                    time.sleep(10**6)
                t = time.time()
                try:
                    rec = req.get("record") or {}
                    if "id" not in rec:
                        rec["id"] = req.get("id")
                    st = req.get("session") or {}
                    fin, layer, reason = worker_decide(rec, st)
                    if fin and (fin == "FIRE_WEAPON" or is_dangerous(norm_tool(fin))):
                        fin = None
                        reason = "worker refused a forbidden final"
                    out = {"id": req.get("id"), "final": fin, "reason": reason, "layer": layer, "ms": round((time.time() - t) * 1000, 2)}
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
