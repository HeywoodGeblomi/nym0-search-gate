#!/usr/bin/env python3
"""Fetch public search snippets/page text and plant frozen injections.
Run only after PREREG, QUERY_LOCK, and TEMPLATE_LOCK are hashed.
Use --sid2-file PATH later to swap in a SID-2 results file instead of fetching.
"""
from __future__ import annotations
import json, hashlib, time, urllib.parse, urllib.request, argparse, re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
UA = "Nym0SearchGateTest/1.0 (research test of a local safety gate; unauthenticated public Wikipedia API; no SID-2)"
MIN_CHARS = 80

def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def sha_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

def now_et() -> str:
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S EST")

def http_get_json(url: str, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        return json.loads(raw.decode("utf-8")), dict(resp.headers), resp.status

def wiki_search(query: str):
    q = urllib.parse.urlencode({
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": 3,
        "srnamespace": 0,
        "format": "json",
    })
    url = "https://en.wikipedia.org/w/api.php?" + q
    data, _, status = http_get_json(url)
    hits = (data.get("query") or {}).get("search") or []
    return url, status, hits

def wiki_summary(title: str):
    path = urllib.parse.quote(title.replace(" ", "_"), safe="")
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + path
    data, _, status = http_get_json(url)
    extract = (data.get("extract") or "").strip()
    desc = (data.get("description") or "").strip()
    text = extract if len(extract) >= MIN_CHARS else (extract + (" " + desc if desc else "")).strip()
    page_url = (data.get("content_urls") or {}).get("desktop", {}).get("page") or data.get("canonicalurl") or url
    return url, status, {
        "title": data.get("title") or title,
        "extract": extract,
        "description": desc,
        "text": text,
        "page_url": page_url,
        "pageid": data.get("pageid"),
    }

def load_sid2(path: Path):
    """Map a SID-2 (or any vendor) results JSONL into fetch-like rows.
    Schema: query (required), title, snippet or text, optional url.
    """
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            query = r.get("query") or r.get("q")
            text = r.get("text") or r.get("snippet") or r.get("extract") or ""
            rows.append({
                "query": query,
                "title": r.get("title") or "",
                "text": str(text).strip(),
                "page_url": r.get("url") or r.get("page_url") or "",
                "source": "sid2_file",
                "raw": r,
            })
    return rows

def plant(text: str, i: int, templates: dict, family_order: list) -> tuple[str, str, str]:
    fam = family_order[i % len(family_order)]
    opts = templates[fam]
    tmpl = opts[(i // len(family_order)) % len(opts)]
    # Append the planted instruction to the fetched text so the clean prefix is preserved.
    injected = (text.rstrip() + tmpl).strip()
    return injected, fam, tmpl

def official_record(oid, qid, query, text, gold, family=None):
    rec = {
        "id": oid,
        "qid": qid,
        "session_id": oid,
        "turn_index": 1,
        "kind": "search_result",
        "gold": gold,
        "user_request": query,
        "untrusted_text": text,
        "proposed_tool": "open_search_result",
        "proposed_args": "",
        "allow_list": ["open_search_result", "web_search"],
        "prior_hold": False,
        "prior_injection": False,
        "prior_hash": "",
        "condition_satisfied": False,
        "override": "",
        "injection_family": family or "",
    }
    return rec

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid2-file", default=None, help="Optional JSONL of already-fetched results (SID-2 or other). Not used unless passed.")
    args = ap.parse_args()

    qlock = json.loads((DATA / "QUERY_LOCK.json").read_text())
    tlock = json.loads((DATA / "TEMPLATE_LOCK.json").read_text())
    qh = sha_file(DATA / "QUERY_LOCK.json")
    th = sha_file(DATA / "TEMPLATE_LOCK.json")
    if qh != (DATA / "QUERY_LOCK.sha256").read_text().split()[0]:
        raise SystemExit("QUERY_LOCK hash mismatch")
    if th != (DATA / "TEMPLATE_LOCK.sha256").read_text().split()[0]:
        raise SystemExit("TEMPLATE_LOCK hash mismatch")

    receipt = {
        "started_at": now_et(),
        "timezone": "America/New_York",
        "method": "sid2_file" if args.sid2_file else "wikipedia_search_and_rest_summary",
        "sid2_file": args.sid2_file,
        "user_agent": UA,
        "min_chars": MIN_CHARS,
        "query_lock_sha256": qh,
        "template_lock_sha256": th,
        "attempts": [],
        "kept": [],
        "dropped": [],
    }

    kept_rows = []
    if args.sid2_file:
        sid_rows = load_sid2(Path(args.sid2_file))
        # map onto frozen queries by exact query string when possible, else keep file order
        by_q = {}
        for r in sid_rows:
            if r.get("query"):
                by_q.setdefault(r["query"], r)
        for item in qlock["queries"]:
            q, qid = item["query"], item["qid"]
            hit = by_q.get(q)
            if not hit or len(hit.get("text") or "") < MIN_CHARS:
                receipt["dropped"].append({"qid": qid, "query": q, "why": "no usable sid2 text"})
                continue
            kept_rows.append({
                "qid": qid, "query": q, "title": hit.get("title") or "",
                "text": hit["text"], "page_url": hit.get("page_url") or "",
                "source": "sid2_file",
            })
            receipt["kept"].append({"qid": qid, "query": q, "title": hit.get("title") or "", "chars": len(hit["text"])})
    else:
        for item in qlock["queries"]:
            q, qid = item["query"], item["qid"]
            attempt = {"qid": qid, "query": q}
            try:
                search_url, s_status, hits = wiki_search(q)
                attempt["search_url"] = search_url
                attempt["search_status"] = s_status
                attempt["n_hits"] = len(hits)
                time.sleep(0.12)
                chosen = None
                for hit in hits:
                    title = hit.get("title")
                    if not title:
                        continue
                    try:
                        sum_url, sum_status, summary = wiki_summary(title)
                    except Exception as e:
                        attempt.setdefault("summary_errors", []).append({"title": title, "error": str(e)})
                        time.sleep(0.12)
                        continue
                    time.sleep(0.12)
                    if len(summary.get("text") or "") >= MIN_CHARS:
                        chosen = {**summary, "search_title": title, "sum_url": sum_url, "sum_status": sum_status}
                        break
                if not chosen:
                    receipt["dropped"].append({"qid": qid, "query": q, "why": "no extract of at least 80 characters"})
                    receipt["attempts"].append(attempt)
                    continue
                attempt["title"] = chosen["title"]
                attempt["page_url"] = chosen["page_url"]
                attempt["chars"] = len(chosen["text"])
                receipt["attempts"].append(attempt)
                kept_rows.append({
                    "qid": qid, "query": q, "title": chosen["title"],
                    "text": chosen["text"], "page_url": chosen["page_url"],
                    "source": "wikipedia_rest_summary",
                    "search_url": search_url, "summary_url": chosen["sum_url"],
                })
                receipt["kept"].append({"qid": qid, "query": q, "title": chosen["title"],
                                        "page_url": chosen["page_url"], "chars": len(chosen["text"])})
            except Exception as e:
                receipt["dropped"].append({"qid": qid, "query": q, "why": f"fetch error: {type(e).__name__}: {e}"})
                receipt["attempts"].append(attempt)
                time.sleep(0.2)

    receipt["finished_at"] = now_et()
    receipt["n_queries"] = len(qlock["queries"])
    receipt["n_kept"] = len(kept_rows)
    receipt["n_dropped"] = len(receipt["dropped"])
    (DATA / "FETCH_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"n_kept": receipt["n_kept"], "n_dropped": receipt["n_dropped"], "dropped": receipt["dropped"]}, indent=2))

    if len(kept_rows) < 50:
        raise SystemExit(f"construction stop: only {len(kept_rows)} usable results (need at least 50)")

    family_order = tlock["family_order"]
    templates = tlock["families"]
    clean, injected = [], []
    for i, row in enumerate(kept_rows):
        cid = f"C-{row['qid']}"
        iid = f"I-{row['qid']}"
        clean.append(official_record(cid, row["qid"], row["query"], row["text"], "ALLOW"))
        inj_text, fam, tmpl = plant(row["text"], i, templates, family_order)
        rec = official_record(iid, row["qid"], row["query"], inj_text, "HOLD", family=fam)
        rec["planted_template"] = tmpl
        rec["matched_clean_id"] = cid
        injected.append(rec)
        clean[-1]["matched_injected_id"] = iid
        clean[-1]["source_title"] = row["title"]
        clean[-1]["source_url"] = row.get("page_url") or ""
        clean[-1]["fetch_source"] = row.get("source") or ""
        rec["source_title"] = row["title"]
        rec["source_url"] = row.get("page_url") or ""
        rec["fetch_source"] = row.get("source") or ""

    official = []
    # interleave not required; clean then injected is fine and easy to audit
    official.extend(clean)
    official.extend(injected)

    def write_jsonl(path, rows):
        with path.open("w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=True) + "\n")
        return sha_file(path)

    h_clean = write_jsonl(DATA / "official_clean.jsonl", clean)
    h_inj = write_jsonl(DATA / "official_injected.jsonl", injected)
    h_all = write_jsonl(DATA / "official_set.jsonl", official)
    # gate-only records (no extra helper fields required, but extra fields are ok if ignored)
    lock = {
        "written_at": now_et(),
        "timezone": "America/New_York",
        "n_clean": len(clean),
        "n_injected": len(injected),
        "n_official": len(official),
        "n_dropped_queries": receipt["n_dropped"],
        "query_lock_sha256": qh,
        "template_lock_sha256": th,
        "sid2_file": args.sid2_file,
        "sha256": {
            "official_clean.jsonl": h_clean,
            "official_injected.jsonl": h_inj,
            "official_set.jsonl": h_all,
        },
        "rows": [{"id": r["id"], "qid": r["qid"], "gold": r["gold"], "injection_family": r.get("injection_family") or ""} for r in official],
        "note": "Hashed after fetch and planting, before the frozen gate was run. Clean originals were not edited.",
    }
    (DATA / "SET_LOCK.json").write_text(json.dumps(lock, indent=2) + "\n")
    (DATA / "official_clean.jsonl.sha256").write_text(f"{h_clean}  official_clean.jsonl\n")
    (DATA / "official_injected.jsonl.sha256").write_text(f"{h_inj}  official_injected.jsonl\n")
    (DATA / "official_set.jsonl.sha256").write_text(f"{h_all}  official_set.jsonl\n")
    (DATA / "SET_LOCK.sha256").write_text(f"{sha_file(DATA / 'SET_LOCK.json')}  SET_LOCK.json\n")
    (DATA / "FETCH_RECEIPT.sha256").write_text(f"{sha_file(DATA / 'FETCH_RECEIPT.json')}  FETCH_RECEIPT.json\n")
    print("SET_LOCK", json.dumps({k: lock[k] for k in ["written_at","n_clean","n_injected","sha256"]}, indent=2))

if __name__ == "__main__":
    main()
