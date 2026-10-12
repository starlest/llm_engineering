#!/usr/bin/env python3
"""AI Engineering Tracker: the checker for your fork.

Run it from anywhere inside the fork, with the course environment:

    uv run python plan/check.py          check everything and write plan/status.json
    uv run python plan/check.py --all    also list the checks of blocks you have not started

It looks at the lesson notebooks and at your files under plan/. It runs the tests for python_check.py, ask.py and
chat.py with a stand-in model, so no API call is made and nothing is spent. It prints what passed and what did not,
and writes plan/status.json. Commit that file with your work: the tracker page reads it from GitHub.

Claude wrote this file for the plan. Its parts are unpacked into a temporary folder on each run.
To update it, replace the whole file with a new copy from the tracker page.
"""
import os
import shutil
import subprocess
import sys
import tempfile

VERSION = "3"


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    top = subprocess.run(["git", "-C", here, "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
    root = top or os.path.dirname(here)
    work = tempfile.mkdtemp(prefix="plan-check-")
    try:
        for name, text in FILES.items():
            with open(os.path.join(work, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        sys.path.insert(0, work)
        import tracker
        tracker.VERSION = VERSION
        return tracker.main(root, work, sys.executable, sys.argv[1:])
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ---- the parts ----------------------------------------------------------------------------------------------
FILES = {}

FILES['tracker.py'] = r'''"""Checks a fork of ed-donner/llm_engineering against the AI Engineering Tracker's plan.

It looks at the lesson notebooks and at the files under plan/, runs the tests for the exercises that have them,
prints a report, and writes plan/status.json, the file the tracker page shows.
"""
import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import checks  # noqa: E402

# first 12 characters of each lesson notebook's original git blob id (course repo, 8 Aug 2026)
BASELINE = {
    "week1/day1.ipynb": "986dc12e3917", "week1/day2.ipynb": "a96a46a8bee7", "week1/day4.ipynb": "129eaaf43ec6",
    "week1/day5.ipynb": "6e4014eae6d8", "week1/week1 EXERCISE.ipynb": "f3486fe32523",
    "week2/day1.ipynb": "85e643a308b1", "week2/day2.ipynb": "d5716bc9becb", "week2/day3.ipynb": "d49959a74192",
    "week2/day4.ipynb": "d3c3693f6c64", "week2/day5.ipynb": "47d1bc1f81cf", "week2/week2 EXERCISE.ipynb": "765a87ca547b",
    "week3/day1.ipynb": "0bb319db4073", "week3/day2.ipynb": "eab737e971bd", "week3/day3.ipynb": "de7b73b477ce",
    "week3/day4.ipynb": "13aac7391db2", "week3/day5.ipynb": "928f30562928",
    "week4/day3.ipynb": "6c583915bf2e", "week4/day4.ipynb": "d1318ea19212", "week4/day5.ipynb": "1c744cb38c34",
    "week5/day1.ipynb": "d61c2b524815", "week5/day2.ipynb": "7cd0a60ca49a", "week5/day3.ipynb": "4c2672905d27",
    "week5/day4.ipynb": "754fea656a69", "week5/day5.ipynb": "d2a642ddbc87",
    "week6/day1.ipynb": "43ff3b54e221", "week6/day2.ipynb": "875b27a47872", "week6/day3.ipynb": "52079f05fa28",
    "week6/day4.ipynb": "f8bfa516fc8e", "week6/day5.ipynb": "63b8d0d4424f",
    "week7/day1.ipynb": "b49a5a211c65", "week7/day2.ipynb": "e43bd5607306", "week7/day3 and 4.ipynb": "1b4ddc01309c",
    "week7/day5.ipynb": "bd62fd7c7e69",
    "week8/day1.ipynb": "29867c88234e", "week8/day2.ipynb": "3a5dd22c5c84", "week8/day3.ipynb": "0153090a71fa",
    "week8/day4.ipynb": "0ce8673b1094", "week8/day5.ipynb": "e001afd3e5ca",
}
# notebooks the course ships that are not lessons
EXTRAS = {"week2/extra.ipynb", "week6/redemption_run.ipynb", "week6/redemption_train.ipynb", "week6/results.ipynb",
          "week7/results.ipynb", "week8/results.ipynb"}
CODE_TESTS = {  # exercises whose code is run against tests
    "b0.python": ("plan/block0/python_check.py", "tests_b0.py"),
    "b1.build": ("plan/block1/ask.py", "tests_b1.py"),
    "b2.build": ("plan/block2/chat.py", "tests_b2.py"),
}
BLOCKS = ["Set up", "First LLM product", "Chat UI, typed output and tools", "Open-source models",
          "Choosing models and first evals", "RAG", "Fine-tuning data, light", "Fine-tuning a model, light", "Agents", "Ship"]
# every item the page tracks besides the lessons: key, name in the report
ITEMS = ([("b0.setup", "Set up"), ("b0.python", "Python self-check"), ("b0.check", "Check")]
         + [(f"b{n}.{k}", name) for n in range(1, 9) for k, name in (("read", "Read"), ("build", "Build"), ("check", "Check"))]
         + [("b9.read", "Read"), ("b9.build", "Build: API"), ("b9.deploy", "Build: container and deploy"),
            ("b9.readme", "Build: README"), ("b9.check", "Check")])
ROWS = {"b4.read": 2}  # Block 4 reads two chapters into one notes file, so it marks two rows of the schedule
VERSION = "dev"  # check.py sets this to its own version


def git(root, *args):
    return subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True).stdout


def lessons(root):
    """For each course week, the lesson notebooks that show work in the working copy."""
    present = sorted(p for p in BASELINE if os.path.isfile(os.path.join(root, p)))
    ids = git(root, "hash-object", "--", *present).split() if present else []
    blob = dict(zip(present, ids)) if len(ids) == len(present) else {}
    out = {}
    for w in range(1, 9):
        mine = sorted(p for p in BASELINE if p.startswith(f"week{w}/"))
        changed = [p for p in mine if p in blob and blob[p][:12] != BASELINE[p]]
        folder = os.path.join(root, f"week{w}")
        names = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
        own = [f"week{w}/{n}" for n in names if n.lower().endswith(".ipynb") and os.path.isfile(os.path.join(folder, n))]
        own = [p for p in own if p not in BASELINE and p not in EXTRAS]
        worked = min(len(mine), len(changed) + len(own))
        covered = changed + [p for p in mine if p not in changed][:max(0, worked - len(changed))]
        out[w] = {"done": worked == len(mine), "worked": worked, "total": len(mine), "covered": covered,
                  "todo": [p.split("/", 1)[1][:-6] for p in mine if p not in covered]}
    return out


def can_unshare():
    try:
        return subprocess.run(["unshare", "-rn", "true"], capture_output=True, timeout=10).returncode == 0
    except Exception:  # noqa: BLE001
        return False


def has_packages(py):
    try:
        return subprocess.run([py, "-I", "-c", "import pydantic, openai, dotenv"], capture_output=True, timeout=60).returncode == 0
    except Exception:  # noqa: BLE001
        return False


def run_tests(py, work, fork, learner_rel, tests_name, isolate, ready):
    """Run one exercise's tests in a separate process: a clean environment, a placeholder key and a time limit,
    with no network where the system allows that."""
    out = os.path.join(work, tests_name + ".json")
    if os.path.exists(out):
        os.remove(out)
    home = os.path.join(work, "home")
    os.makedirs(home, exist_ok=True)
    if os.path.isfile(os.path.join(fork, learner_rel)) and not ready:
        return [{"what": "The tests ran", "ok": False,
                 "why": "this Python has no pydantic, openai or dotenv; run the check with the course environment: uv run python plan/check.py"}]
    cmd = ["timeout", "120"] + (["unshare", "-rn"] if isolate else []) + [
        "env", "-i", "PATH=/usr/bin:/bin", "HOME=" + home, "OPENAI_API_KEY=not-a-real-key",
        py, "-I", os.path.join(HERE, "harness.py"), os.path.join(fork, learner_rel), os.path.join(HERE, tests_name), out]
    try:
        done = subprocess.run(cmd, cwd=fork, capture_output=True, timeout=150)
        if done.returncode == 124:  # the timeout command stopped it
            raise subprocess.TimeoutExpired(cmd, 120)
        with open(out) as fh:
            results = json.load(fh)
        assert isinstance(results, list) and results
        return results
    except subprocess.TimeoutExpired:
        return [{"what": "The tests ran", "ok": False, "why": f"the tests on {learner_rel} did not finish within 2 minutes"}]
    except Exception:  # noqa: BLE001
        return [{"what": "The tests ran", "ok": False, "why": f"the tests on {learner_rel} could not be run; try the check again"}]


def root_cause(why):
    """The thing itself is not there yet."""
    return "not in your fork yet" in why


def follow_on(why):
    """A check that cannot say anything until an earlier one passes."""
    return (why.startswith("there are no ") and not root_cause(why)) or why.startswith("fix the ")


def summarize(results):
    """Counts, up to three distinct reasons, and every check with its state: pass, fail, or wait (nothing to judge yet)."""
    fails = [r for r in results if not r["ok"]]
    distinct, seen = [], set()
    for r in fails:
        if r["why"] not in seen:
            seen.add(r["why"])
            distinct.append(r)
    if any(not follow_on(r["why"]) for r in distinct):
        distinct = [r for r in distinct if not follow_on(r["why"])]
    shown = [{"what": "" if root_cause(r["why"]) else r["what"], "why": r["why"]} for r in distinct[:3]]
    items = [{"what": r["what"], "why": "" if r["ok"] else r["why"],
              "state": "pass" if r["ok"] else "wait" if r.get("wait") or root_cause(r["why"]) or follow_on(r["why"]) else "fail"}
             for r in results[:24]]
    return {"pass": len(results) - len(fails), "total": len(results), "fail": shown, "more": max(0, len(distinct) - len(shown)), "items": items}


def depends(parts):
    """Checks that pass once other items are done: (description, name of the item, done?)."""
    return [{"what": what, "ok": bool(ok), "why": "" if ok else f"{name} is not done yet", "wait": True} for what, name, ok in parts]


def check(root, work, py):
    """Run every check. Returns the status that goes into plan/status.json."""
    weeks = lessons(root)
    f = checks.Fork(root)
    isolate, ready = can_unshare(), has_packages(py)
    groups = {}
    started, problem = f.text("plan/README.md")
    groups["b0.setup"] = [{"what": "plan/README.md is in your fork", "ok": not problem and bool(started.strip()),
                           "why": problem or "plan/README.md is empty"}]
    docs, docs_in = checks.documents(f)
    for key, (learner_rel, tests_name) in CODE_TESTS.items():
        groups[key] = run_tests(py, work, root, learner_rel, tests_name, isolate, ready)
    groups["b1.check"] = checks.b1_output(f, docs)
    groups["b2.check"] = checks.b2_output(f)
    groups["b3.build"], groups["b3.check"] = checks.b3(f)
    groups["b4.build"], groups["b4.check"], question_ids = checks.b4(f, docs)
    groups["b5.build"], groups["b5.check"] = checks.b5(f, docs, question_ids)
    groups["b6.build"], groups["b6.check"] = checks.b6(f)
    groups["b7.build"], groups["b7.check"] = checks.b7(f, docs)
    groups["b8.build"], groups["b8.check"] = checks.b8(f)
    groups["b9.build"], groups["b9.deploy"], groups["b9.readme"] = checks.b9(f)
    seen_notes = {}
    for n in range(1, 10):
        groups[f"b{n}.read"] = checks.notes(f, n, seen_notes)

    def done(key):
        return bool(groups[key]) and all(r["ok"] for r in groups[key])

    groups["b0.check"] = depends([
        ("Set up is done", "the set-up item", done("b0.setup")),
        ("python_check.py passes all its tests", "the Python self-check", done("b0.python"))])
    groups["b9.check"] = depends([
        ("The assistant is behind an API", "the API item", done("b9.build")),
        ("It is in a container and deployed, with its link in the README", "the deploy item", done("b9.deploy")),
        ("The README shows every score and three known failures", "the README item", done("b9.readme"))])

    flags = {key for key in groups if done(key)}
    for n in range(1, 9):
        if weeks[n]["done"]:
            flags.add(f"b{n}.course")
    head = git(root, "log", "-1", "--format=%h|%cd", "--date=format:%d %b %Y").strip().split("|")
    head = head if len(head) == 2 else ["", ""]
    stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    return {"repo": "starlest/llm_engineering", "checked_at": stamp.isoformat(timespec="seconds"),
            "checked_label": stamp.strftime("%d %b %Y, %H:%M") + " WIB", "commit": head[0], "commit_date": head[1],
            "lessons_done": sorted(p for w in weeks.values() for p in w["covered"]),
            "lesson_weeks": {str(w): {"worked": v["worked"], "total": v["total"], "todo": v["todo"]} for w, v in weeks.items()},
            "items_done": sorted(flags),
            "checks": {key.replace(".", "_"): summarize(results) for key, results in groups.items()},
            "documents": len(docs), "documents_in": docs_in, "tests_isolated": isolate, "checker": VERSION}


def counts(status):
    done = set(status["items_done"])
    rows_done = len(status["lessons_done"]) + sum(ROWS.get(k, 1) for k, _ in ITEMS if k in done)
    return rows_done, len(BASELINE) + sum(ROWS.get(k, 1) for k, _ in ITEMS)


def report(status, everything=False):
    """The same results as the tracker page, as text."""
    done, out = set(status["items_done"]), []
    out.append(f"AI Engineering Tracker, checked {status['checked_label']}")
    out.append("")
    worked = {int(w): v for w, v in status["lesson_weeks"].items()}
    out.append(f"Course lessons: {len(status['lessons_done'])} of {len(BASELINE)} marked")
    for w in sorted(worked):
        v = worked[w]
        if v["worked"] and v["worked"] < v["total"]:
            out.append(f"  Week {w}: {v['worked']} of {v['total']}, to go: {', '.join(v['todo'])}")
        elif v["worked"]:
            out.append(f"  Week {w}: all {v['total']}")
    found, where = status.get("documents", 0), status.get("documents_in", "")
    if where == checks.OWN:
        out.append(f"Documents: {found} in {where}/")
    else:
        out.append(f"Documents: none in {checks.OWN}/ yet. Block 1's Build item on the tracker page says how to add them.")
    quiet, current = [], None
    for n, name in enumerate(BLOCKS):
        mine = [(k, label) for k, label in ITEMS if k.startswith(f"b{n}.")]
        groups = {k: status["checks"][k.replace(".", "_")] for k, _ in mine}
        active = any(i["state"] != "wait" for g in groups.values() for i in g["items"])
        if current is None and not all(k in done for k, _ in mine):
            current = n  # the first block with something left is always listed
        if not active and not everything and current != n:
            quiet.append(str(n))
            continue
        out.append("")
        out.append(f"Block {n}: {name}")
        for k, label in mine:
            g = groups[k]
            if k in done:
                out.append(f"  [done] {label}")
                continue
            if k in ("b0.check", "b9.check"):  # these pass when the block's other items do
                out.append(f"  [    ] {label}: waits for the items above")
                continue
            waiting = [i for i in g["items"] if i["state"] == "wait"]
            if len(waiting) == len(g["items"]):  # nothing to judge yet: one line
                same = len({i["why"] for i in waiting}) == 1
                out.append(f"  [    ] {label}: {waiting[0]['why']}" + (f" ({len(waiting)} checks)" if same and len(waiting) > 1 else ""))
                continue
            out.append(f"  [    ] {label}: {g['pass']} of {g['total']} checks pass")
            last = ""
            for i in g["items"]:
                if i["state"] == "pass":
                    continue
                out.append(f"           {'x' if i['state'] == 'fail' else '-'} {i['what']}")
                if i["why"] and i["why"] != last:
                    out.append(f"               {i['why']}")
                last = i["why"] or last
    if quiet:
        out.append("")
        out.append(("Blocks " if len(quiet) > 1 else "Block ") + ", ".join(quiet) + ": nothing to check yet. Add --all to list them.")
    rows_done, rows_total = counts(status)
    out.append("")
    out.append(f"{rows_done} of {rows_total} items done.")
    return "\n".join(out)


def main(root, work, py, argv):
    status = check(root, work, py)
    print(report(status, everything="--all" in argv))
    if "--no-write" in argv:
        return 0
    out = os.path.join(root, "plan", "status.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(status, fh, indent=1)
        fh.write("\n")
    print("Wrote plan/status.json. Commit and push it with your work, and the tracker page picks it up.")
    return 0


if __name__ == "__main__":
    work_dir = os.path.abspath(sys.argv[2])
    os.makedirs(work_dir, exist_ok=True)
    sys.exit(main(os.path.abspath(sys.argv[1]), work_dir, os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else sys.executable, sys.argv[4:]))
'''

FILES['checks.py'] = r'''"""Checks the files each block's exercise should leave in plan/. It only reads files; it runs nothing.

Every function returns a list of results: {"what": plain description, "ok": bool, "why": reason when not ok}.
"""
import json
import os
import re

LIMIT = 2_000_000


class Fork:
    def __init__(self, root):
        self.root = root

    def path(self, rel):
        return os.path.join(self.root, rel)

    def text(self, rel):
        """(text, problem) for a file inside the fork."""
        p = self.path(rel)
        if os.path.islink(p) or not os.path.isfile(p):
            return None, f"{rel} is not in your fork yet"
        if os.path.getsize(p) > LIMIT:
            return None, f"{rel} is larger than 2 MB"
        try:
            with open(p, encoding="utf-8") as fh:
                return fh.read(), None
        except UnicodeDecodeError:
            return None, f"{rel} is not UTF-8 text"

    def json(self, rel):
        text, problem = self.text(rel)
        if problem:
            return None, problem
        try:
            return json.loads(text), None
        except ValueError as e:
            return None, f"{rel} is not valid JSON ({e})"

    def jsonl(self, rel):
        text, problem = self.text(rel)
        if problem:
            return [], problem
        rows = []
        for i, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                return [], f"{rel} line {i} is not valid JSON"
            if not isinstance(row, dict):
                return [], f"{rel} line {i} is not a JSON object"
            rows.append(row)
        return rows, None


def add(out, what, ok, why=""):
    out.append({"what": what, "ok": bool(ok), "why": "" if ok else " ".join(str(why).split())[:220]})


def some(names, limit=3):
    names = list(names)
    return ", ".join(str(n) for n in names[:limit]) + (f" and {len(names) - limit} more" if len(names) > limit else "")


def text_of(row, key):
    v = row.get(key) if isinstance(row, dict) else None
    return v.strip() if isinstance(v, str) else ""


def count_of(v):
    """A {"correct": n, "total": n} pair, or None."""
    if not isinstance(v, dict):
        return None
    c, t = v.get("correct"), v.get("total")
    if isinstance(c, bool) or isinstance(t, bool) or not isinstance(c, int) or not isinstance(t, int):
        return None
    return (c, t) if 0 <= c <= t and t > 0 else None


def has_file(out, fork, rel, minimum=200):
    text, problem = fork.text(rel)
    add(out, f"{rel} is in your fork ({minimum}+ characters)", not problem and len(text.strip()) >= minimum,
        problem or f"it has only {len(text.strip())} characters")


def notes(fork, n, seen):
    """The reading notes for block n. seen maps the text of earlier blocks' notes to their block number."""
    out, rel = [], f"plan/block{n}/notes.md"
    text, problem = fork.text(rel)
    body = " ".join(text.split()) if text else ""
    why = problem or (f"it has only {len(body)} characters" if len(body) < 100 else "")
    if not why and body in seen:
        why = f"it is the same text as plan/block{seen[body]}/notes.md; write this block's own notes"
    if not why:
        seen[body] = n
    add(out, f"{rel} holds your notes for this block (100+ characters)", not why, why)
    return out


# ---- the documents -------------------------------------------------------------------------------
OWN = "plan/docs"                   # the project's documents
KNOWLEDGE = "week5/knowledge-base"  # the course's set, which counts while plan/docs/ holds none
EXAMPLE = "plan/docs/wrestlemania/wrestlemania-03.md"


def files_under(fork, base):
    """Every .md or .txt file under base, at any depth, as its path from the top of the fork.
    Files named README.md are left out."""
    paths, top = set(), fork.path(base)
    if os.path.islink(top) or not os.path.isdir(top):
        return paths
    for folder, _, files in os.walk(top):
        rel = os.path.relpath(folder, fork.root).replace(os.sep, "/")
        for n in files:
            full = os.path.join(folder, n)
            if n.lower().endswith((".md", ".txt")) and n.lower() != "readme.md" and not os.path.islink(full) and os.path.isfile(full):
                paths.add(f"{rel}/{n}")
    return paths


def documents(fork):
    """(the paths that count as documents, the folder they are in). The documents are the files under
    plan/docs/. While that folder holds none, the course's knowledge base counts instead."""
    own = files_under(fork, OWN)
    if own:
        return own, OWN
    course = files_under(fork, KNOWLEDGE)
    return course, KNOWLEDGE if course else ""


# ---- Block 1 -----------------------------------------------------------------------------------
def b1_output(fork, docs):
    out, rel = [], "plan/block1/answers.json"
    data, problem = fork.json(rel)
    rows = data if isinstance(data, list) else []
    add(out, f"{rel} is a JSON list", not problem and isinstance(data, list), problem or "it holds JSON, but not a list")
    good = [r for r in rows if all(text_of(r, k) for k in ("question", "document", "answer"))]
    add(out, "It has at least 5 entries, each with a question, a document and an answer",
        len(rows) >= 5 and len(good) == len(rows), problem or f"{len(good)} of {len(rows)} entries are complete; 5 are needed")
    stray = [text_of(r, "document") for r in good if text_of(r, "document") not in docs]
    add(out, f"Every document is the path of a real document, such as {EXAMPLE}", good and not stray,
        problem or (some(stray) + " is not one of the documents" if stray else "there are no complete entries yet"))
    asked = [text_of(r, "question").lower() for r in good]
    add(out, "No question repeats", good and len(set(asked)) == len(asked), problem or "the same question appears more than once" if good else "there are no complete entries yet")
    return out


# ---- Block 2 -----------------------------------------------------------------------------------
def b2_output(fork):
    out, rel = [], "plan/block2/transcript.json"
    data, problem = fork.json(rel)
    msgs = data if isinstance(data, list) and all(isinstance(m, dict) for m in data) else []
    roles_ok = bool(msgs) and all(m.get("role") in ("system", "user", "assistant", "tool") for m in msgs)
    add(out, f"{rel} is the list of messages from one real chat", not problem and roles_ok,
        problem or "it must be a JSON list of messages, each with a role of system, user, assistant or tool")
    calls = [c for m in msgs if m.get("role") == "assistant" and isinstance(m.get("tool_calls"), list) for c in m["tool_calls"] if isinstance(c, dict)]
    add(out, "The model asks for a tool at least once (an assistant message with tool_calls)", calls, problem or "no assistant message has tool_calls")
    answered = {m.get("tool_call_id") for m in msgs if m.get("role") == "tool"}
    open_ids = [c.get("id") for c in calls if c.get("id") not in answered]
    add(out, "Every tool call is answered by a tool message with the same tool_call_id", calls and not open_ids,
        problem or (f"no tool message answers {some(open_ids)}" if open_ids else "there are no tool calls yet"))
    final_ok, why = False, "the last message must come from the assistant"
    if msgs and msgs[-1].get("role") == "assistant" and isinstance(msgs[-1].get("content"), str):
        try:
            last = json.loads(msgs[-1]["content"])
            final_ok = isinstance(last, dict) and bool(text_of(last, "answer")) and bool(text_of(last, "source"))
            why = 'its content must be JSON with a non-empty "answer" and "source"'
        except ValueError:
            why = "its content is not JSON"
    add(out, 'The last message is the assistant\'s final JSON: {"answer": ..., "source": ...}', final_ok, problem or why)
    return out


# ---- Block 3 -----------------------------------------------------------------------------------
def b3(fork):
    build, out, rel = [], [], "plan/block3/comparison.json"
    has_file(build, fork, "plan/block3/compare.py")
    data, problem = fork.json(rel)
    rows = data if isinstance(data, list) else []
    add(out, f"{rel} is a JSON list of at least 5 questions", not problem and len(rows) >= 5, problem or f"it has {len(rows)} entries")

    def side(r, k):
        s = r.get(k) if isinstance(r, dict) else None
        return isinstance(s, dict) and bool(text_of(s, "model")) and isinstance(s.get("answer"), str)

    good = [r for r in rows if text_of(r, "question") and side(r, "small") and side(r, "frontier") and isinstance(r.get("small_ok"), bool)]
    add(out, 'Each entry has question, small and frontier (each {"model", "answer"}) and small_ok (true or false)',
        rows and len(good) == len(rows), problem or f"{len(good)} of {len(rows)} entries are complete")
    same = [r for r in good if text_of(r["small"], "model") == text_of(r["frontier"], "model")]
    add(out, "The small model and the frontier model are different models", good and not same, problem or "an entry names the same model twice" if good else "there are no complete entries yet")
    return build, out


# ---- Blocks 4 and 7: question sets ---------------------------------------------------------------
def question_set(fork, rel, docs, answerable=False):
    """(rows, complete rows, problem). A complete row has id, question, expected and source."""
    rows, problem = fork.jsonl(rel)
    keys = ("id", "question", "expected", "source")
    good = [r for r in rows if all(text_of(r, k) for k in keys) and (not answerable or isinstance(r.get("answerable"), bool))]
    return rows, good, problem


def b4(fork, docs):
    build, out, rel = [], [], "plan/block4/questions.jsonl"
    has_file(build, fork, "plan/block4/evaluate.py")
    rows, good, problem = question_set(fork, rel, docs)
    add(out, f"{rel} has 20 to 30 questions, one JSON object per line", not problem and 20 <= len(rows) <= 30, problem or f"it has {len(rows)}")
    ids = [text_of(r, "id") for r in good]
    add(out, "Each has id, question, expected and source, and no id repeats", rows and len(good) == len(rows) and len(set(ids)) == len(ids),
        problem or (f"{len(good)} of {len(rows)} lines are complete" if len(good) != len(rows) else "an id appears twice"))
    stray = [text_of(r, "source") for r in good if text_of(r, "source") not in docs]
    add(out, f"Every source is the path of a real document, such as {EXAMPLE}", good and not stray,
        problem or (some(stray) + " is not one of the documents" if stray else "there are no complete questions yet"))
    res, rproblem = fork.json("plan/block4/results.json")
    floor, ceiling = (count_of(res.get("floor")), count_of(res.get("ceiling"))) if isinstance(res, dict) else (None, None)
    add(out, 'plan/block4/results.json records floor and ceiling, each as {"correct": n, "total": n}', floor and ceiling,
        rproblem or "floor or ceiling is missing, or its numbers do not make sense")
    add(out, "Both totals equal the number of questions, and the ceiling is not below the floor",
        floor and ceiling and floor[1] == ceiling[1] == len(rows) and ceiling[0] >= floor[0],
        rproblem or "check the totals against your question count, and that ceiling.correct is at least floor.correct")
    return build, out, {text_of(r, "id") for r in good}


# ---- Block 5 -----------------------------------------------------------------------------------
def b5(fork, docs, question_ids):
    build, out, rel = [], [], "plan/block5/runs.jsonl"
    has_file(build, fork, "plan/block5/rag.py")
    rows, problem = fork.jsonl(rel)
    by_id = {text_of(r, "id"): r for r in rows}
    missing = sorted(question_ids - set(by_id))
    add(out, f"{rel} has one run for every question id in plan/block4/questions.jsonl", not problem and question_ids and not missing,
        problem or (f"no run for {some(missing)}" if missing else "plan/block4/questions.jsonl has no complete questions yet"))

    def chunks(r):
        got = r.get("retrieved")
        return got if isinstance(got, list) and 1 <= len(got) <= 20 and all(isinstance(c, dict) and text_of(c, "source") in docs and text_of(c, "text") for c in got) else None

    bad = [text_of(r, "id") or "?" for r in rows if chunks(r) is None]
    add(out, "Each run lists what it retrieved: 1 to 20 chunks, each with the path of a real document as source, and its text", rows and not bad,
        problem or (f"check run {some(bad)}" if bad else "there are no runs yet"))
    off = [text_of(r, "id") or "?" for r in rows if chunks(r) is not None and text_of(r, "source") != "none"
           and text_of(r, "source") not in {text_of(c, "source") for c in chunks(r)}]
    add(out, 'Each run\'s source is one of its retrieved sources, or "none"', rows and not bad and not off,
        problem or (f"run {some(off)} cites a source it did not retrieve" if off else "fix the retrieved lists first"))
    incomplete = [text_of(r, "id") or "?" for r in rows if not isinstance(r.get("answer"), str) or not isinstance(r.get("correct"), bool)]
    add(out, "Each run has an answer and a correct of true or false", rows and not incomplete,
        problem or (f"check run {some(incomplete)}" if incomplete else "there are no runs yet"))
    res, rproblem = fork.json("plan/block5/results.json")
    rag = count_of(res.get("rag")) if isinstance(res, dict) else None
    marked = sum(1 for r in rows if r.get("correct") is True)
    add(out, 'plan/block5/results.json has rag as {"correct": n, "total": n}, matching the runs marked correct',
        rag and rag == (marked, len(rows)), rproblem or f"the runs give {marked} correct of {len(rows)}; results.json must say the same")
    return build, out


# ---- Block 6 -----------------------------------------------------------------------------------
def b6(fork):
    build, out, rel = [], [], "plan/block6/experiments.json"
    has_file(build, fork, "plan/block6/experiments.py")
    data, problem = fork.json(rel)
    rows = data if isinstance(data, list) else []
    add(out, f"{rel} is a JSON list of at least 3 experiments", not problem and len(rows) >= 3, problem or f"it has {len(rows)}")
    good = [r for r in rows if len(text_of(r, "change")) >= 10 and count_of(r)]
    add(out, "Each has change (what you changed, 10+ characters), correct and total", rows and len(good) == len(rows),
        problem or f"{len(good)} of {len(rows)} entries are complete")
    changes = [text_of(r, "change").lower() for r in good]
    add(out, "No two experiments describe the same change", good and len(set(changes)) == len(changes),
        problem or ("two entries have the same change" if good else "there are no complete entries yet"))
    return build, out


# ---- Block 7 -----------------------------------------------------------------------------------
def b7(fork, docs):
    build, out, rel = [], [], "plan/block7/questions.jsonl"
    has_file(build, fork, "plan/block7/judge.py")
    has_file(build, fork, "plan/block7/judge_prompt.md")
    rows, good, problem = question_set(fork, rel, docs, answerable=True)
    ids = {text_of(r, "id") for r in good}
    add(out, f"{rel} has at least 50 questions with id, question, expected, source and answerable",
        not problem and len(rows) >= 50 and len(good) == len(rows) and len(ids) == len(good),
        problem or f"{len(good)} of {len(rows)} lines are complete with unique ids; 50 are needed")
    cannot = [r for r in good if r.get("answerable") is False and text_of(r, "source") == "none"]
    add(out, 'At least 5 cannot be answered from the documents (answerable false, source "none")', len(cannot) >= 5,
        problem or f"{len(cannot)} such questions so far")
    judged, jproblem = fork.jsonl("plan/block7/judged.jsonl")
    verdicts = {text_of(r, "id"): r for r in judged if text_of(r, "judge") in ("pass", "fail")}
    missing = sorted(ids - set(verdicts))
    add(out, 'plan/block7/judged.jsonl has a judge verdict of "pass" or "fail" for every question id', not jproblem and ids and not missing,
        jproblem or (f"no verdict for {some(missing)}" if missing else "there are no complete questions yet"))
    human = [r for r in verdicts.values() if text_of(r, "human") in ("pass", "fail")]
    add(out, "At least 20 of them also carry your own grade in human", len(human) >= 20, jproblem or f"{len(human)} have a human grade")
    essay, eproblem = fork.text("plan/block7/finetuning.md")
    add(out, "plan/block7/finetuning.md says whether fine-tuning would help your project (400+ characters)",
        not eproblem and len(essay.strip()) >= 400, eproblem or f"it has only {len(essay.strip())} characters")
    return build, out


# ---- Block 8 -----------------------------------------------------------------------------------
def b8(fork):
    build, out, rel = [], [], "plan/block8/trace.json"
    has_file(build, fork, "plan/block8/agent.py")
    data, problem = fork.json(rel)
    steps = data.get("steps") if isinstance(data, dict) and isinstance(data.get("steps"), list) else []
    steps = [s for s in steps if isinstance(s, dict)]
    add(out, f"{rel} records one run: a question and a list of steps", not problem and isinstance(data, dict) and text_of(data, "question") and steps,
        problem or 'it must be {"question": ..., "steps": [...]}')
    searches = [s for s in steps if s.get("type") == "tool_call" and re.search(r"search|retriev", text_of(s, "name"), re.I)]
    add(out, "The run searches at least twice (tool_call steps whose name contains search or retrieve)", len(searches) >= 2,
        problem or f"{len(searches)} search steps found")
    approved = False
    for i, s in enumerate(steps):
        if s.get("type") == "approval" and s.get("approved") is True and text_of(s, "name"):
            approved = approved or any(t.get("type") == "tool_result" and text_of(t, "name") == text_of(s, "name") for t in steps[i + 1:])
    unapproved = [text_of(s, "name") for i, s in enumerate(steps) if s.get("type") == "tool_result"
                  and any(a.get("type") == "approval" and text_of(a, "name") == text_of(s, "name") for a in steps)
                  and not any(a.get("type") == "approval" and a.get("approved") is True and text_of(a, "name") == text_of(s, "name") for a in steps[:i])]
    add(out, "A tool that changes something runs only after an approval step with approved true", approved and not unapproved,
        problem or "add an approval step before that tool's tool_result, with the same name")
    last = steps[-1] if steps else {}
    add(out, "The run ends with an answer step holding answer and source", last.get("type") == "answer" and text_of(last, "answer") and text_of(last, "source"),
        problem or "the last step must have type answer, with answer and source")
    res, rproblem = fork.json("plan/block8/results.json")
    agent = res.get("agent") if isinstance(res, dict) and isinstance(res.get("agent"), dict) else {}

    def number(k):
        v = agent.get(k)
        return isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0

    add(out, "plan/block8/results.json has agent with correct, total, cost_usd and seconds_per_question",
        count_of(agent) and number("cost_usd") and number("seconds_per_question"), rproblem or "one of the four numbers is missing")
    return build, out


# ---- Block 9 -----------------------------------------------------------------------------------
def b9(fork):
    """Three groups: the API, the deployment, and the README."""
    build, deploy, readme, rel = [], [], [], "plan/block9/README.md"
    has_file(build, fork, "plan/block9/api.py")
    has_file(deploy, fork, "plan/block9/Dockerfile", minimum=40)
    text, problem = fork.text(rel)
    text = text or ""
    add(deploy, f"{rel} gives the public https link to your assistant", re.search(r"https://[^\s)>\]]+\.[^\s)>\]]+", text), problem or "no https link found")
    rows = [line.lower() for line in text.splitlines() if line.count("|") >= 2]
    lacking = [name for name in ("floor", "ceiling", "rag", "agent") if not any(name in r and re.search(r"\d", r) for r in rows)]
    add(readme, f"{rel} has a results table with rows for floor, ceiling, RAG and agent, each with a number", not problem and not lacking,
        problem or f"no table row with a number for {some(lacking, 4)}")
    after = re.split(r"(?im)^#+\s*known failures.*$", text, maxsplit=1)
    bullets = re.findall(r"(?m)^\s*(?:[-*]|\d+\.)\s+\S", after[1].split("\n#")[0]) if len(after) == 2 else []
    add(readme, 'It lists at least three known failures under a "Known failures" heading', len(bullets) >= 3,
        problem or f"{len(bullets)} listed under that heading")
    return build, deploy, readme
'''

FILES['harness.py'] = r'''"""Runs one test file against one of the learner's files.

Usage: python -I harness.py LEARNER_FILE.py TESTS.py OUT.json

Each test is a function test_*(m) taking the learner's module. Its docstring says, in plain words,
what it checks. A test fails by raising AssertionError; the message is shown to the learner.
"""
import importlib.util
import json
import os
import signal
import sys


class Timeout(Exception):
    pass


def _alarm(*_):
    raise Timeout()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main(learner_path, tests_path, out_path):
    tests = load(tests_path, "plan_tests")
    names = [n for n in dir(tests) if n.startswith("test_") and callable(getattr(tests, n))]
    names.sort(key=lambda n: getattr(tests, n).__code__.co_firstlineno)
    results, problem, learner = [], None, None
    shown = os.path.relpath(learner_path)  # the checker runs from the fork's top folder
    signal.signal(signal.SIGALRM, _alarm)
    if not os.path.isfile(learner_path):
        problem = f"{shown} is not in your fork yet"
    else:
        sys.path.insert(0, os.path.dirname(os.path.abspath(learner_path)))
        try:
            signal.alarm(20)
            learner = load(learner_path, "learner")
            signal.alarm(0)
        except Timeout:
            problem = f"importing {shown} took longer than 20 seconds; keep model calls inside functions"
        except ModuleNotFoundError as e:
            signal.alarm(0)
            problem = (f"{shown} imports {e.name}, which the tests do not have (only the standard library, openai, pydantic "
                       f"and dotenv). Move that code to another file")
        except BaseException as e:  # noqa: BLE001 - report anything the learner's file raises
            signal.alarm(0)
            problem = f"{shown} could not be imported: {type(e).__name__}: {e}"
    for n in names:
        fn = getattr(tests, n)
        what = (fn.__doc__ or n).strip().split("\n")[0]
        if problem:
            results.append({"what": what, "ok": False, "why": problem})
            continue
        try:
            signal.alarm(10)
            fn(learner)
            signal.alarm(0)
            results.append({"what": what, "ok": True, "why": ""})
        except Timeout:
            results.append({"what": what, "ok": False, "why": "it took longer than 10 seconds"})
        except AssertionError as e:
            signal.alarm(0)
            results.append({"what": what, "ok": False, "why": str(e) or "the result was not what the exercise expects"})
        except BaseException as e:  # noqa: BLE001
            signal.alarm(0)
            results.append({"what": what, "ok": False, "why": f"{type(e).__name__}: {e}"})
    for r in results:
        r["why"] = " ".join(str(r["why"]).split())[:220]
    with open(out_path, "w") as fh:
        json.dump(results, fh)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
'''

FILES['tests_b0.py'] = r'''"""Tests for plan/block0/python_check.py (run by harness.py)."""
import asyncio
import inspect
import time

FILE = "python_check.py"


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def rejects(model, data):
    import pydantic
    try:
        model.model_validate(data)
    except pydantic.ValidationError:
        return True
    return False


def test_tally_empty(m):
    """A new Tally has a total of 0"""
    t = need(m, "Tally")()
    assert t.total() == 0, f"Tally().total() gave {t.total()!r}, expected 0"


def test_tally_adds(m):
    """Tally.add collects numbers and Tally.total returns their sum"""
    t = need(m, "Tally")()
    t.add(2)
    t.add(3.5)
    assert t.total() == 5.5, f"after add(2) and add(3.5), total() gave {t.total()!r}, expected 5.5"


def test_tally_separate(m):
    """Two Tally objects keep separate totals"""
    cls = need(m, "Tally")
    a, b = cls(), cls()
    a.add(4)
    assert b.total() == 0, "adding to one Tally changed another; keep the numbers on self, not on the class"


def test_gather_is_async(m):
    """gather_two is an async function"""
    assert inspect.iscoroutinefunction(need(m, "gather_two")), "define it with 'async def gather_two(first, second)'"


def test_gather_results(m):
    """gather_two returns both results, in the order given"""
    async def a():
        return "a"

    async def b():
        return "b"

    got = asyncio.run(need(m, "gather_two")(a, b))
    assert tuple(got) == ("a", "b"), f"gather_two(a, b) gave {got!r}, expected ('a', 'b')"


def test_gather_concurrent(m):
    """gather_two runs the two calls at the same time, not one after the other"""
    async def slow_a():
        await asyncio.sleep(0.25)
        return 1

    async def slow_b():
        await asyncio.sleep(0.25)
        return 2

    start = time.perf_counter()
    got = asyncio.run(need(m, "gather_two")(slow_a, slow_b))
    took = time.perf_counter() - start
    assert tuple(got) == (1, 2), f"gave {got!r}, expected (1, 2)"
    assert took < 0.42, f"two 0.25-second calls took {took:.2f}s; run them together with asyncio.gather"


def test_note_accepts(m):
    """Note accepts {"title": "Intro", "words": 120}"""
    import pydantic
    cls = need(m, "Note")
    assert isinstance(cls, type) and issubclass(cls, pydantic.BaseModel), "Note must be a pydantic BaseModel"
    n = cls.model_validate({"title": "Intro", "words": 120})
    assert (n.title, n.words) == ("Intro", 120), f"fields came back as {(n.title, n.words)!r}"


def test_note_rejects_empty_title(m):
    """Note rejects an empty title"""
    assert rejects(need(m, "Note"), {"title": "", "words": 5}), 'Note accepted {"title": ""}; require at least 1 character'


def test_note_rejects_negative_words(m):
    """Note rejects a negative word count"""
    assert rejects(need(m, "Note"), {"title": "x", "words": -1}), 'Note accepted {"words": -1}; require 0 or more'


def test_note_rejects_missing_and_wrong(m):
    """Note rejects a missing field and a word count that is not a number"""
    cls = need(m, "Note")
    assert rejects(cls, {"title": "x"}), "Note accepted a dictionary with no 'words'"
    assert rejects(cls, {"title": "x", "words": "many"}), 'Note accepted {"words": "many"}'
'''

FILES['tests_b1.py'] = r'''"""Tests for plan/block1/ask.py (run by harness.py). No real model is called: the tests pass in a stand-in."""

FILE = "ask.py"
QUESTION = "What colour is the Zorblat beacon?"
DOCUMENT = "Field manual, page 9. The Zorblat beacon is painted teal so that crews can find it at dusk."


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def messages_of(m):
    msgs = need(m, "build_messages")(QUESTION, DOCUMENT)
    assert isinstance(msgs, list), f"build_messages returned {type(msgs).__name__}, expected a list"
    return msgs


def test_two_messages(m):
    """build_messages returns a system message, then a user message"""
    msgs = messages_of(m)
    assert len(msgs) == 2, f"it returned {len(msgs)} messages, expected 2"
    assert all(isinstance(x, dict) for x in msgs), "each message must be a dictionary"
    roles = [x.get("role") for x in msgs]
    assert roles == ["system", "user"], f"roles were {roles!r}, expected ['system', 'user']"


def test_system_instructions(m):
    """The system message carries your instructions (20 characters or more)"""
    system = messages_of(m)[0].get("content")
    assert isinstance(system, str) and len(system.strip()) >= 20, "the system message is empty or too short to instruct the model"
    assert DOCUMENT not in system, "put the document in the user message, not the system message"


def test_user_has_document_and_question(m):
    """The user message contains the document and the question"""
    user = messages_of(m)[1].get("content")
    assert isinstance(user, str), "the user message content must be a string"
    assert DOCUMENT in user, "the document text is not in the user message"
    assert QUESTION in user, "the question is not in the user message"


def test_ask_returns_reply(m):
    """ask returns the model's reply"""
    got = need(m, "ask")(QUESTION, DOCUMENT, lambda msgs: "Teal.")
    assert got == "Teal.", f"with a model that replies 'Teal.', ask returned {got!r}"


def test_ask_trims(m):
    """ask trims blank space around the reply"""
    got = need(m, "ask")(QUESTION, DOCUMENT, lambda msgs: "  Teal.\n\n")
    assert got == "Teal.", f"a reply of '  Teal.\\n\\n' came back as {got!r}, expected 'Teal.'"


def test_ask_calls_model_once(m):
    """ask calls the model exactly once, with the messages from build_messages"""
    seen = []

    def model(msgs):
        seen.append(msgs)
        return "ok"

    need(m, "ask")(QUESTION, DOCUMENT, model)
    assert len(seen) == 1, f"the model was called {len(seen)} times, expected 1"
    assert seen[0] == need(m, "build_messages")(QUESTION, DOCUMENT), "the model did not receive build_messages(question, document)"
'''

FILES['tests_b2.py'] = r'''"""Tests for plan/block2/chat.py (run by harness.py). The model is a scripted stand-in; nothing calls a real one."""
import json
import os
import tempfile

FILE = "chat.py"


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def final(answer="Teal.", source="beacon.md"):
    return {"role": "assistant", "content": json.dumps({"answer": answer, "source": source})}


def tool_call(call_id, name, **arguments):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


def wants(*calls):
    return {"role": "assistant", "content": None, "tool_calls": list(calls)}


def scripted(*replies):
    """A stand-in model that returns the given replies in turn and records what it was sent."""
    state = {"calls": 0}

    def model(messages):
        i = min(state["calls"], len(replies) - 1)
        state["calls"] += 1
        return json.loads(json.dumps(replies[i]))

    model.state = state
    return model


def start():
    return [{"role": "system", "content": "Answer from the documents."}, {"role": "user", "content": "What colour is the beacon?"}]


def test_answer_model(m):
    """Answer accepts {"answer": ..., "source": ...} and rejects an empty answer or a missing source"""
    import pydantic
    cls = need(m, "Answer")
    assert isinstance(cls, type) and issubclass(cls, pydantic.BaseModel), "Answer must be a pydantic BaseModel"
    a = cls.model_validate({"answer": "Teal.", "source": "beacon.md"})
    assert (a.answer, a.source) == ("Teal.", "beacon.md"), "the fields did not come back as given"
    for bad in ({"answer": "", "source": "beacon.md"}, {"answer": "Teal."}):
        try:
            cls.model_validate(bad)
        except pydantic.ValidationError:
            continue
        raise AssertionError(f"Answer accepted {bad!r}")


def test_list_documents(m):
    """list_documents returns the sorted names of the .md and .txt files in a folder"""
    fn = need(m, "list_documents")
    with tempfile.TemporaryDirectory() as d:
        for name in ("b.md", "a.txt", "c.pdf"):
            open(os.path.join(d, name), "w").close()
        os.mkdir(os.path.join(d, "sub"))
        open(os.path.join(d, "sub", "x.md"), "w").close()
        got = fn(d)
    assert got == ["a.txt", "b.md"], f"for a folder holding a.txt, b.md, c.pdf and sub/x.md it gave {got!r}, expected ['a.txt', 'b.md']"


def test_direct_answer(m):
    """run_chat returns an Answer when the model replies with the final JSON straight away"""
    messages, model = start(), scripted(final())
    got = need(m, "run_chat")(messages, model, {})
    assert isinstance(got, need(m, "Answer")), f"run_chat returned {type(got).__name__}, expected an Answer"
    assert (got.answer, got.source) == ("Teal.", "beacon.md"), f"got {(got.answer, got.source)!r}"
    assert model.state["calls"] == 1, f"the model was called {model.state['calls']} times, expected 1"
    assert len(messages) == 3 and messages[-1].get("role") == "assistant", "append the model's reply to the messages list you were given"


def test_tool_round(m):
    """run_chat runs a requested tool, sends back its result, then returns the final Answer"""
    seen = []

    def lister(folder):
        seen.append(folder)
        return ["beacon.md", "crew.md"]

    messages = start()
    model = scripted(wants(tool_call("call_1", "list_documents", folder="plan/docs")), final())
    got = need(m, "run_chat")(messages, model, {"list_documents": lister})
    assert seen == ["plan/docs"], f"the tool was called with {seen!r}, expected one call with folder='plan/docs'"
    assert (got.answer, got.source) == ("Teal.", "beacon.md"), f"got {(got.answer, got.source)!r}"
    roles = [x.get("role") for x in messages]
    assert roles == ["system", "user", "assistant", "tool", "assistant"], f"message roles ended as {roles!r}"
    tool_msg = messages[3]
    assert tool_msg.get("tool_call_id") == "call_1", "the tool message needs tool_call_id set to the id of the call it answers"
    assert isinstance(tool_msg.get("content"), str), "the tool message content must be a string (use json.dumps on the result)"
    assert json.loads(tool_msg["content"]) == ["beacon.md", "crew.md"], "the tool message content is not the tool's result as JSON"


def test_two_tools_in_one_reply(m):
    """When one reply asks for two tools, run_chat answers both, in order"""
    log = []

    def lister(folder):
        log.append(("list", folder))
        return [folder + "/a.md"]

    messages = start()
    model = scripted(wants(tool_call("c1", "list_documents", folder="x"), tool_call("c2", "list_documents", folder="y")), final())
    need(m, "run_chat")(messages, model, {"list_documents": lister})
    assert log == [("list", "x"), ("list", "y")], f"tool calls ran as {log!r}"
    ids = [x.get("tool_call_id") for x in messages if x.get("role") == "tool"]
    assert ids == ["c1", "c2"], f"tool messages answered ids {ids!r}, expected ['c1', 'c2']"


def test_gives_up(m):
    """run_chat raises RuntimeError rather than loop forever (5 model calls at most)"""
    model = scripted(wants(tool_call("again", "list_documents", folder="x")))
    try:
        need(m, "run_chat")(start(), model, {"list_documents": lambda folder: []})
    except RuntimeError:
        assert model.state["calls"] <= 5, f"it called the model {model.state['calls']} times before stopping, expected at most 5"
        return
    raise AssertionError("a model that keeps asking for tools never made run_chat raise RuntimeError")


def test_bad_final_reply(m):
    """run_chat raises ValueError when the final reply is not the expected JSON"""
    for reply in ("The beacon is teal.", json.dumps({"answer": "Teal."})):
        try:
            need(m, "run_chat")(start(), scripted({"role": "assistant", "content": reply}), {})
        except ValueError:
            continue
        raise AssertionError(f"a final reply of {reply!r} did not raise ValueError")
'''


if __name__ == "__main__":
    sys.exit(main())
