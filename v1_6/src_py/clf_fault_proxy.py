"""Harness-only fault proxy for the classifier process.
Forwards classify requests, and on every Nth classify replaces the reply with a bad one.
KIND: notjson | noscore | textscore | fire
"""
import json, os, socket, sys
def opt(k, d=None): return sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
LISTEN, UP, EVERY, KIND, FLOG = opt("--listen"), opt("--upstream"), int(opt("--every", 1)), opt("--fault"), opt("--faultlog")
up = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); up.connect(UP); upf = up.makefile("rwb", buffering=0)
if os.path.exists(LISTEN): os.unlink(LISTEN)
srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); srv.bind(LISTEN); srv.listen(4)
n = 0; faulted = []
def bad(req):
    i = req.get("id")
    if KIND == "notjson": return b"this is not json\n"
    if KIND == "noscore": return (json.dumps({"id": i, "hold": True}) + "\n").encode()
    if KIND == "textscore": return (json.dumps({"id": i, "score": "hot", "hold": False, "threshold": 0.5}) + "\n").encode()
    if KIND == "fire": return (json.dumps({"id": i, "score": "FIRE_WEAPON", "hold": False}) + "\n").encode()
    raise SystemExit("bad fault kind")
while True:
    conn, _ = srv.accept(); cf = conn.makefile("rwb", buffering=0)
    try:
        for raw in cf:
            if not raw.strip(): continue
            req = json.loads(raw)
            upf.write(raw if raw.endswith(b"\n") else raw + b"\n"); real = upf.readline()
            if req.get("op") == "classify":
                n += 1
                if n % EVERY == 0:
                    faulted.append({"n": n, "id": req.get("id")})
                    open(FLOG, "w").write(json.dumps(faulted))
                    cf.write(bad(req)); continue
            cf.write(real)
    except (BrokenPipeError, ConnectionResetError): pass
    finally:
        try: conn.close()
        except OSError: pass
