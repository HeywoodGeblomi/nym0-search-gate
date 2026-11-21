"""Harness-only fault proxy for the v3.3.1 crash test. Sits on its own Unix socket in front of the real warm worker, forwards every request
unchanged, and on every Nth "decide" request replaces the reply with a bad one. The real worker and the pipeline binary are not touched.
usage: fault_proxy.py --listen SOCK --upstream SOCK --every N --fault KIND --faultlog FILE
KIND: notjson | truncated | empty | nofinal | numfinal | errobj | unknown | fire"""
import json, os, socket, sys
def opt(k, d=None): return sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
LISTEN, UP, EVERY, KIND, FLOG = opt("--listen"), opt("--upstream"), int(opt("--every", 5)), opt("--fault"), opt("--faultlog")
up = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); up.connect(UP); upf = up.makefile("rwb", buffering=0)
if os.path.exists(LISTEN): os.unlink(LISTEN)
srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); srv.bind(LISTEN); srv.listen(4)
n = 0; faulted = []
def bad(req, real):
    i = req.get("id")
    if KIND == "notjson": return b"this is not json\n", False
    if KIND == "truncated": return real.rstrip(b"\n")[: max(1, len(real) // 2)], True   # no newline, then the connection closes
    if KIND == "empty": return b"\n", False
    if KIND == "nofinal": return (json.dumps({"id": i}) + "\n").encode(), False
    if KIND == "numfinal": return (json.dumps({"id": i, "final": 42, "reason": "x"}) + "\n").encode(), False
    if KIND == "errobj": return (json.dumps({"id": i, "err": "injected worker error"}) + "\n").encode(), False
    if KIND == "unknown": return (json.dumps({"id": i, "final": "LAUNCH_ROCKET", "reason": "x"}) + "\n").encode(), False
    if KIND == "fire": return (json.dumps({"id": i, "final": "FIRE_WEAPON", "reason": "injected"}) + "\n").encode(), False
    raise SystemExit("bad fault kind")
while True:
    conn, _ = srv.accept(); cf = conn.makefile("rwb", buffering=0)
    try:
        for raw in cf:
            if not raw.strip(): continue
            req = json.loads(raw)
            upf.write(raw if raw.endswith(b"\n") else raw + b"\n"); real = upf.readline()
            if req.get("op") == "decide":
                n += 1
                if n % EVERY == 0:
                    out, close = bad(req, real); faulted.append({"n": n, "id": req.get("id")})
                    open(FLOG, "w").write(json.dumps(faulted))
                    cf.write(out)
                    if close: break
                    continue
            cf.write(real)
    except (BrokenPipeError, ConnectionResetError): pass
    finally:
        for c in (cf, conn):
            try: c.close()
            except OSError: pass
        try: conn.shutdown(socket.SHUT_RDWR)
        except OSError: pass
