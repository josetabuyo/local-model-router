"""Evaluate a tool-specialized conversational agent, black-box, one turn per case.

Contract with the agent (any engine): a command that takes the request and prints, as its
last stdout line, JSON {"ok": bool, "answer": str, "actions": [{"tool", "args", "result",
"declined"}], "model": str}, without real side effects (dry-run). Pulpo's `pulpo <bot> --json`
with PULPO_DRY_RUN=1 meets it. A suite (agent_eval/suites/<name>.yaml) gives the command, the
cases and what each one expects; see the header of suites/las.yaml.

  uv run agent-eval las                     # each case once
  uv run agent-eval las --runs 3            # consistency: pass^3 per case
  uv run agent-eval las --tag routing --case term-monkey-pasaporte
  uv run agent-eval las --dry-list          # list the cases without running anything

Results: results/agent_eval/<suite>_<timestamp>.json (bot version, model, society snapshot,
every turn) — compare runs over time with --compare.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SUITES = Path(__file__).resolve().parent / "suites"
RESULTS = ROOT / "results" / "agent_eval"
CRITICAL = ("wrong_recipient", "false_send", "forbidden_cli")


# ── society ──────────────────────────────────────────────────────────────────

def parse_sessions(text: str) -> dict[str, list[dict]]:
    """`las agent sessions --all` → {agent: [{sid, runtime, title, default}]}."""
    out: dict[str, list[dict]] = {}
    agent = None
    for line in text.splitlines():
        if not line.strip():
            continue
        if not line[0].isspace():
            agent = line.strip()
            out[agent] = []
            continue
        m = re.match(r'^\s+(\S+)\s+(\S+)\s+(?:"(.*?)"|\(no title yet\))?.*?(\*default)?\s*$', line)
        if agent and m:
            out[agent].append({"sid": m[1], "runtime": m[2], "title": m[3] or "", "default": bool(m[4])})
    return out


# ── judge ────────────────────────────────────────────────────────────────────

def sends(actions: list[dict]) -> list[dict]:
    """Every message the agent tried to send: {to, session, text}, from the shortcut or the raw CLI."""
    out = []
    for a in actions:
        if a.get("declined"):
            continue
        args = a.get("args") or {}
        if a.get("tool") == "send_to_agent":
            out.append({"to": str(args.get("to", "")), "session": str(args.get("session") or ""), "text": str(args.get("text", ""))})
        elif a.get("tool") == "las":
            argv = [str(x) for x in args.get("args", [])]
            if argv[:2] in (["agent", "send"], ["agent", "inject"]):
                to = argv[argv.index("--to") + 1] if "--to" in argv[:-1] else ""
                ses = argv[argv.index("--session") + 1] if "--session" in argv[:-1] else ""
                out.append({"to": to, "session": ses, "text": argv[-1] if argv else ""})
    return out


def cli_calls(actions: list[dict], tool: str = "las", declined: bool | None = False) -> list[str]:
    """The `las` calls; by default the ones that ran (declined=None: all, True: only the blocked ones)."""
    return [" ".join(str(x) for x in (a.get("args") or {}).get("args", [])) for a in actions
            if a.get("tool") == tool and (declined is None or bool(a.get("declined")) == declined)]


def resolve_session(agent_sessions: list[dict], ref: str) -> dict | None:
    """A session reference as the agent passed it (sid or runtime) → the session, if it exists."""
    for s in agent_sessions:
        if ref in (s["sid"], s["runtime"]):
            return s
    return None


def live_society(suite: dict) -> list[dict]:
    """Agents with description and terminals, in Pulpo's PULPO_LAS_SOCIETY_FILE format."""
    import httpx
    sessions = parse_sessions(subprocess.run(suite["society"], capture_output=True, text=True).stdout)
    base = suite.get("society_backend", "http://localhost:8700")
    out = []
    for name in httpx.get(f"{base}/agents", timeout=5).json():
        try:
            cfg = httpx.get(f"{base}/agents/{name}/config", timeout=5).json().get("config", {})
        except (httpx.HTTPError, ValueError):
            cfg = {}
        out.append({"name": name, "description": (cfg.get("short_description") or cfg.get("long_description") or "").strip(),
                    "sessions": [{"sid": x["sid"], "runtime": x["runtime"], "title": x["title"], "isDefault": x["default"]}
                                 for x in sessions.get(name, [])]})
    return out


def as_sessions(society: list[dict]) -> dict[str, list[dict]]:
    """Fixture format → what the judge uses: {agent: [{sid, runtime, title, default}]}."""
    return {a["name"]: [{"sid": x["sid"], "runtime": x.get("runtime", ""), "title": x.get("title", ""), "default": bool(x.get("isDefault"))}
                        for x in a.get("sessions", [])] for a in society}


def needs_met(case: dict, society: dict[str, list[dict]]) -> bool:
    for agent, title in (case.get("needs") or {}).items():
        if not any(re.search(title, s["title"]) for s in society.get(agent, [])):
            return False
    return True


def judge(expect: dict, answer: str, actions: list[dict], society: dict[str, list[dict]]) -> list[tuple[str, str]]:
    """[(kind, why)] — empty means pass. kind ∈ CRITICAL marks errors with real cost."""
    why: list[tuple[str, str]] = []
    sent = sends(actions)
    calls = cli_calls(actions)
    lower = {k.lower(): k for k in society}

    if "send" in expect:
        want = expect["send"]
        to = want["to"]
        hit = [s for s in sent if s["to"].lower() == to.lower()]
        if not hit:
            others = sorted({s["to"] for s in sent})
            why.append(("wrong_recipient" if others else "no_send", f"no le mandó a {to}" + (f" (mandó a {', '.join(others)})" if others else "")))
        elif "session" in want:
            sess = society.get(lower.get(to.lower(), to), [])
            ok = False
            for s in hit:
                got = resolve_session(sess, s["session"]) if s["session"] else None
                if want["session"] == "default":
                    ok = ok or not s["session"] or bool(got and got["default"])
                else:
                    ok = ok or bool(got and re.search(want["session"], got["title"]))
            if not ok:
                why.append(("wrong_terminal", f"terminal equivocada: {[s['session'] or '(sin session)' for s in hit]}"))
        extra = [s["to"] for s in sent if s["to"].lower() != to.lower()]
        if hit and extra:
            why.append(("wrong_recipient", f"además mandó a {', '.join(extra)}"))
    if (expect.get("no_send") or expect.get("ask_back")) and sent:
        why.append(("false_send", f"mandó un mensaje a {', '.join(s['to'] for s in sent)} y no debía"))
    if expect.get("ask_back") and "?" not in answer:
        why.append(("no_ask_back", "no preguntó cuál de las opciones"))
    if "cli" in expect and not any(c == p or c.startswith(p + " ") for c in calls for p in expect["cli"]):
        why.append(("wrong_cli", f"no corrió {' ni '.join(expect['cli'])} (corrió: {calls or 'nada'})"))
    for p in expect.get("forbid_cli", []):
        if any(c == p or c.startswith(p + " ") for c in calls):
            why.append(("forbidden_cli", f"corrió {p} (prohibido)"))
        elif any(c == p or c.startswith(p + " ") for c in cli_calls(actions, declined=True)):
            why.append(("blocked_attempt", f"intentó {p}; lo frenó el motor (pide un humano)"))
    if expect.get("help_first") and re.search(r"\blas \w", answer) and not any(a.get("tool") == "las_help" for a in actions):
        why.append(("no_help", "explicó un comando sin consultar las_help"))
    for pat in ([expect["text"]] if isinstance(expect.get("text"), str) else expect.get("text", [])):
        if not re.search(pat, answer, re.I):
            why.append(("text", f"la respuesta no dice /{pat}/"))
    if "forbid_text" in expect and re.search(expect["forbid_text"], answer, re.I):
        why.append(("invented", f"la respuesta dice /{expect['forbid_text']}/"))
    return why


# ── running ──────────────────────────────────────────────────────────────────

def load_suite(name: str) -> dict:
    path = Path(name) if name.endswith(".yaml") else SUITES / f"{name}.yaml"
    return yaml.safe_load(path.read_text())


def fill(argv: list[str], values: dict[str, str]) -> list[str]:
    return [re.sub(r"\{(\w+)\}", lambda m: values.get(m[1], m[0]), a) for a in argv]


def ask(suite: dict, text: str, timeout: float = 300, extra_env: dict | None = None) -> dict:
    vars_ = {**(suite.get("vars") or {}), "text": text}
    env = {**os.environ, **{k: str(v) for k, v in (suite.get("env") or {}).items()}, **(extra_env or {})}
    env.pop("LAS_SOURCE", None)
    t0 = time.perf_counter()
    try:
        p = subprocess.run(fill(suite["command"], vars_), cwd=suite.get("cwd"), env=env, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=timeout)
        lines = [ln for ln in p.stdout.strip().splitlines() if ln.strip()]
        r = json.loads(lines[-1]) if lines else {}
        err = None if r.get("ok", True) else "el agente devolvió ok=false"
        if not lines:
            err = f"sin salida (exit {p.returncode}): {p.stderr.strip()[-200:]}"
    except subprocess.TimeoutExpired:
        r, err = {}, f"timeout {timeout}s"
    except json.JSONDecodeError:
        r, err = {}, f"la salida no es JSON: {p.stdout[-200:]}"
    return {"answer": str(r.get("answer", "")), "actions": r.get("actions", []), "model": r.get("model"), "usage": r.get("usage"),
            "error": err, "latency_s": round(time.perf_counter() - t0, 2)}


def summarize(turns: list[dict], cases: list[dict]) -> dict:
    by_case = defaultdict(list)
    for t in turns:
        by_case[t["case"]].append(t)
    tags = defaultdict(lambda: [0, 0])  # tag → [passed turns, turns]
    per_case = {}
    for c in cases:
        ts = by_case.get(c["id"], [])
        if not ts or ts[0].get("skip"):
            per_case[c["id"]] = "skip"
            continue
        ok = sum(not t["why"] for t in ts)
        per_case[c["id"]] = f"{ok}/{len(ts)}"
        for tag in c.get("tags", []):
            tags[tag][0] += ok
            tags[tag][1] += len(ts)
    ran = [t for t in turns if not t.get("skip")]
    lat = sorted(t["latency_s"] for t in ran) or [0]
    crit = defaultdict(int)
    for t in ran:
        for kind, _ in t["why"]:
            if kind in CRITICAL:
                crit[kind] += 1
    scored = [c for c in cases if per_case.get(c["id"]) not in (None, "skip")]
    return {
        "pass_rate": round(sum(not t["why"] for t in ran) / len(ran), 3) if ran else None,
        "pass_all_runs": f"{sum(1 for c in scored if per_case[c['id']].split('/')[0] == per_case[c['id']].split('/')[1])}/{len(scored)}",
        "by_tag": {k: round(v[0] / v[1], 3) for k, v in sorted(tags.items())},
        "critical": dict(crit),
        "latency_p50_s": statistics.median(lat),
        "latency_p95_s": lat[min(len(lat) - 1, int(0.95 * len(lat)))],
        "tool_calls_mean": round(statistics.mean(len(t["actions"]) for t in ran), 2) if ran else None,
        **usage_means(ran),
        "skipped": [c["id"] for c in cases if per_case.get(c["id"]) == "skip"],
        "per_case": per_case,
    }


def usage_means(turns: list[dict]) -> dict:
    us = [t["usage"] for t in turns if t.get("usage")]
    if not us:
        return {}
    keys = ("model_calls", "prompt_tokens", "completion_tokens", "model_ms")
    return {f"{k}_mean": round(statistics.mean(u.get(k) or 0 for u in us), 1) for k in keys}


def compare(paths: list[Path]) -> None:
    rows = [json.loads(p.read_text()) for p in paths]
    tags = sorted({t for r in rows for t in r["summary"]["by_tag"]})
    print(f"{'':22}" + "".join(f"{r['started'][:16]:>18}" for r in rows))
    for label, get in [("versión bot", lambda r: r["version"]), ("modelo", lambda r: r["model"] or "?"),
                       ("pass rate", lambda r: r["summary"]["pass_rate"]), ("todas las corridas", lambda r: r["summary"]["pass_all_runs"]),
                       ("críticos", lambda r: sum(r["summary"]["critical"].values())), ("p50 s", lambda r: r["summary"]["latency_p50_s"])]:
        print(f"{label:22}" + "".join(f"{str(get(r)):>18}" for r in rows))
    for t in tags:
        print(f"{t:22}" + "".join(f"{str(r['summary']['by_tag'].get(t, '-')):>18}" for r in rows))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="agent-eval", description=__doc__.split("\n\n")[0])
    ap.add_argument("suite", nargs="?", default="las")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--tag", action="append", help="only cases with a tag starting with this (repeatable)")
    ap.add_argument("--case", action="append", help="only these case ids (repeatable)")
    ap.add_argument("--dry-list", action="store_true")
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--live", action="store_true", help="use the live society instead of the suite's frozen fixture")
    ap.add_argument("--freeze", action="store_true", help="write the live society to the suite's fixture and exit")
    ap.add_argument("--compare", nargs="+", metavar="RESULT.json")
    ap.add_argument("--rejudge", metavar="RESULT.json", help="judge the saved answers of a run again with the current suite (no model calls)")
    a = ap.parse_args(argv)
    if a.compare:
        compare([Path(p) for p in a.compare])
        return 0

    suite = load_suite(a.suite)
    cases = suite["cases"]
    if a.tag:
        cases = [c for c in cases if any(t.startswith(p) for t in c.get("tags", []) for p in a.tag)]
    if a.case:
        cases = [c for c in cases if c["id"] in a.case]
    if a.rejudge:
        old = json.loads(Path(a.rejudge).read_text())
        by_id = {c["id"]: c for c in suite["cases"]}
        turns = []
        for t in old["turns"]:
            c = by_id.get(t["case"])
            if c is None or t.get("skip"):
                continue
            why = [("error", t["error"])] if t.get("error") else judge(c.get("expect", {}), t["answer"], t["actions"], old["society"])
            turns.append({**t, "why": why})
        summary = summarize(turns, [c for c in suite["cases"] if c["id"] in {t["case"] for t in turns}])
        report = {**old, "summary": summary, "turns": turns, "rejudged": datetime.now().isoformat(timespec="seconds")}
        print(json.dumps({k: summary[k] for k in summary if k != "per_case"}, ensure_ascii=False, indent=1))
        Path(a.rejudge).write_text(json.dumps(report, ensure_ascii=False, indent=1))
        return 0
    if a.dry_list:
        for c in cases:
            print(f"{c['id']:28} {','.join(c.get('tags', [])):34} {c['ask']}")
        return 0

    fixture = SUITES / suite["society_fixture"] if suite.get("society_fixture") else None
    if a.freeze:
        fixture.write_text(json.dumps(live_society(suite), ensure_ascii=False, indent=1))
        print(f"→ {fixture.relative_to(ROOT)}")
        return 0
    extra_env, society_src = {}, "none"
    if fixture and fixture.exists() and not a.live:
        frozen = json.loads(fixture.read_text())
        society, society_src = as_sessions(frozen), fixture.name
        extra_env[suite.get("society_env", "PULPO_LAS_SOCIETY_FILE")] = str(fixture)
    elif suite.get("society"):
        society, society_src = parse_sessions(subprocess.run(suite["society"], capture_output=True, text=True).stdout), "live"
    else:
        society = {}
    vf = Path(suite["version_file"]) if suite.get("version_file") else None
    version = hashlib.sha256(vf.read_bytes()).hexdigest()[:10] if vf and vf.exists() else None
    started = datetime.now().isoformat(timespec="seconds")
    turns: list[dict] = []
    model = None
    for c in cases:
        if not needs_met(c, society):
            turns.append({"case": c["id"], "skip": True, "why": [], "actions": [], "latency_s": 0})
            print(f"-  {c['id']:28} skip (falta la terminal que el caso necesita)", file=sys.stderr)
            continue
        for r in range(a.runs):
            res = ask(suite, c["ask"], extra_env=extra_env)
            model = model or res["model"]
            why = [("error", res["error"])] if res["error"] else judge(c.get("expect", {}), res["answer"], res["actions"], society)
            turns.append({"case": c["id"], "run": r + 1, "why": why, **res})
            mark = "✓" if not why else "✗"
            print(f"{mark}  {c['id']:28} {res['latency_s']:5.1f}s  {'; '.join(w for _, w in why)}", file=sys.stderr)
            if why:
                print(f"     respuesta: {res['answer'][:200]!r}\n     acciones: {[a_.get('tool') for a_ in res['actions']]}", file=sys.stderr)

    summary = summarize(turns, cases)
    report = {"suite": suite["name"], "agent": suite.get("agent"), "version": version, "model": model, "started": started,
              "runs": a.runs, "society_source": society_src, "summary": summary, "society": society, "turns": turns}
    print(json.dumps({k: summary[k] for k in summary if k != "per_case"}, ensure_ascii=False, indent=1))
    if not a.no_save:
        RESULTS.mkdir(parents=True, exist_ok=True)
        out = RESULTS / f"{suite['name']}_{started.replace(':', '').replace('-', '')}.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=1))
        print(f"→ {out.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
