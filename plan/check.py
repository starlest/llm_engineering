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

VERSION = "5"


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

It runs the tests for each lesson's exercise and for the project's code, checks the other files under plan/,
prints a report, and writes plan/status.json, the file the tracker page shows.
"""
import ast
import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import checks  # noqa: E402

# the course's lesson notebooks, in order. Each has one exercise: plan/exercises/<week>/<slug>.py
LESSONS = [
    "week1/day1.ipynb", "week1/day2.ipynb", "week1/day4.ipynb", "week1/day5.ipynb", "week1/week1 EXERCISE.ipynb",
    "week2/day1.ipynb", "week2/day2.ipynb", "week2/day3.ipynb", "week2/day4.ipynb", "week2/day5.ipynb",
    "week2/week2 EXERCISE.ipynb",
    "week3/day1.ipynb", "week3/day2.ipynb", "week3/day3.ipynb", "week3/day4.ipynb", "week3/day5.ipynb",
    "week4/day3.ipynb", "week4/day4.ipynb", "week4/day5.ipynb",
    "week5/day1.ipynb", "week5/day2.ipynb", "week5/day3.ipynb", "week5/day4.ipynb", "week5/day5.ipynb",
    "week6/day1.ipynb", "week6/day2.ipynb", "week6/day3.ipynb", "week6/day4.ipynb", "week6/day5.ipynb",
    "week7/day1.ipynb", "week7/day2.ipynb", "week7/day3 and 4.ipynb", "week7/day5.ipynb",
    "week8/day1.ipynb", "week8/day2.ipynb", "week8/day3.ipynb", "week8/day4.ipynb", "week8/day5.ipynb",
]


def exercise_of(lesson):
    """(the learner's exercise file, its tests file) for a lesson notebook such as week1/week1 EXERCISE.ipynb."""
    week, stem = lesson[:-len(".ipynb")].split("/")
    slug = stem.lower().replace(" ", "_")
    return f"plan/exercises/{week}/{slug}.py", f"tests_ex_{week.replace('week', 'w')}_{slug}.py"


def lesson_name(lesson):
    week, stem = lesson[:-len(".ipynb")].split("/")
    n = week[len("week"):]
    return f"Week {n} exercise" if "exercise" in stem.lower() else f"Week {n}, " + stem.replace("day", "Day ")


def planned(tests_name):
    """The checks a tests file holds, read without running it: the first line of each test's docstring."""
    with open(os.path.join(HERE, tests_name), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    return [(ast.get_docstring(node) or node.name).strip().split("\n")[0]
            for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]


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


def clean_env(home):
    """The environment the tests run in: a placeholder API key, a temporary home folder, and only what the
    operating system needs to start Python. Nothing else from your shell reaches the tests, so no real key does."""
    env = {"HOME": home, "OPENAI_API_KEY": "not-a-real-key"}
    if os.name == "nt":  # Windows needs these to start Python and to make temporary files
        for key in ("SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "PATH", "TEMP", "TMP"):
            if os.environ.get(key):
                env[key] = os.environ[key]
        env["USERPROFILE"] = home
    else:
        env["PATH"] = "/usr/bin:/bin"
    return env


def run_tests(py, work, fork, learner_rel, tests_name, isolate, ready):
    """Run one exercise's tests in a separate process: a clean environment, a placeholder key and a time limit,
    with no network where the system allows that. Python itself enforces the limit, so this works on Windows,
    macOS and Linux alike."""
    out = os.path.join(work, tests_name + ".json")
    if os.path.exists(out):
        os.remove(out)
    home = os.path.join(work, "home")
    os.makedirs(home, exist_ok=True)
    if os.path.isfile(os.path.join(fork, learner_rel)) and not ready:
        return [{"what": "The tests ran", "ok": False,
                 "why": "this Python has no pydantic, openai or dotenv; run the check with the course environment: uv run python plan/check.py"}]
    cmd = (["unshare", "-rn"] if isolate else []) + [
        py, "-I", os.path.join(HERE, "harness.py"), os.path.join(fork, learner_rel), os.path.join(HERE, tests_name), out]
    try:
        done = subprocess.run(cmd, cwd=fork, env=clean_env(home), capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        return [{"what": "The tests ran", "ok": False, "why": f"the tests on {learner_rel} did not finish within 2 minutes"}]
    except OSError as e:
        return [{"what": "The tests ran", "ok": False, "why": f"the tests on {learner_rel} could not be started: {e}"}]
    try:
        with open(out, encoding="utf-8") as fh:
            results = json.load(fh)
        assert isinstance(results, list) and results
        return results
    except Exception:  # noqa: BLE001 - say what the test process said, so the cause can be found
        said = [line.strip() for line in done.stderr.decode("utf-8", "replace").splitlines() if line.strip()]
        detail = said[-1][:160] if said else f"it stopped with exit code {done.returncode}"
        return [{"what": "The tests ran", "ok": False, "why": f"the tests on {learner_rel} could not be run: {detail}"}]


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
    f = checks.Fork(root)
    isolate, ready = can_unshare(), has_packages(py)
    groups = {}
    for lesson in LESSONS:  # a lesson is done when its exercise passes every test
        learner_rel, tests_name = exercise_of(lesson)
        if os.path.isfile(os.path.join(root, learner_rel)):
            groups[lesson] = run_tests(py, work, root, learner_rel, tests_name, isolate, ready)
        else:  # nothing to run yet: list the checks that wait for the file
            groups[lesson] = [{"what": what, "ok": False, "why": f"{learner_rel} is not in your fork yet"} for what in planned(tests_name)]
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

    lessons_done = [lesson for lesson in LESSONS if done(lesson)]
    weeks = {}
    for w in range(1, 9):
        mine = [lesson for lesson in LESSONS if lesson.startswith(f"week{w}/")]
        weeks[w] = {"worked": sum(1 for lesson in mine if lesson in lessons_done), "total": len(mine),
                    "todo": [lesson.split("/", 1)[1][:-len(".ipynb")] for lesson in mine if lesson not in lessons_done]}
    flags = {key for key in groups if key not in LESSONS and done(key)}
    for n in range(1, 9):
        if not weeks[n]["todo"]:
            flags.add(f"b{n}.course")
    head = git(root, "log", "-1", "--format=%h|%cd", "--date=format:%d %b %Y").strip().split("|")
    head = head if len(head) == 2 else ["", ""]
    stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    return {"repo": "starlest/llm_engineering", "checked_at": stamp.isoformat(timespec="seconds"),
            "checked_label": stamp.strftime("%d %b %Y, %H:%M") + " WIB", "commit": head[0], "commit_date": head[1],
            "lessons_done": lessons_done,
            "lesson_weeks": {str(w): v for w, v in weeks.items()},
            "items_done": sorted(flags),
            "checks": {key.replace(".", "_"): summarize(results) for key, results in groups.items()},
            "documents": len(docs), "documents_in": docs_in, "tests_isolated": isolate, "checker": VERSION}


def counts(status):
    done = set(status["items_done"])
    rows_done = len(status["lessons_done"]) + sum(ROWS.get(k, 1) for k, _ in ITEMS if k in done)
    return rows_done, len(LESSONS) + sum(ROWS.get(k, 1) for k, _ in ITEMS)


def detail_lines(out, label, g):
    """One unfinished item: its count of passing checks, then each check that has not passed and why."""
    out.append(f"  [    ] {label}: {g['pass']} of {g['total']} checks pass")
    last = ""
    for i in g["items"]:
        if i["state"] == "pass":
            continue
        out.append(f"           {'x' if i['state'] == 'fail' else '-'} {i['what']}")
        if i["why"] and i["why"] != last:
            out.append(f"               {i['why']}")
        last = i["why"] or last


def report(status, everything=False):
    """The same results as the tracker page, as text."""
    done, out = set(status["items_done"]), []
    out.append(f"AI Engineering Tracker, checked {status['checked_label']}")
    out.append("")
    worked = {int(w): v for w, v in status["lesson_weeks"].items()}
    out.append(f"Course exercises: {len(status['lessons_done'])} of {len(LESSONS)} pass")
    for w in sorted(worked):
        v = worked[w]
        if v["worked"] and v["worked"] < v["total"]:
            out.append(f"  Week {w}: {v['worked']} of {v['total']}, to go: {', '.join(v['todo'])}")
        elif v["worked"]:
            out.append(f"  Week {w}: all {v['total']}")
    todo = [lesson for lesson in LESSONS if lesson not in status["lessons_done"]]
    if todo:
        out.append(f"  Next: {lesson_name(todo[0])}, in {exercise_of(todo[0])[0]}")
    started = False
    for lesson in LESSONS:  # exercises you have started but that do not pass yet
        g = status["checks"].get(lesson.replace(".", "_"))
        if g and lesson not in status["lessons_done"] and any(i["state"] != "wait" for i in g["items"]):
            detail_lines(out, lesson_name(lesson) + " exercise" * ("exercise" not in lesson.lower()), g)
            started = True
    if started:
        out.append("")
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
            detail_lines(out, label, g)
    if quiet:
        out.append("")
        out.append(("Blocks " if len(quiet) > 1 else "Block ") + ", ".join(quiet) + ": nothing to check yet. Add --all to list them.")
    rows_done, rows_total = counts(status)
    out.append("")
    out.append(f"{rows_done} of {rows_total} items done.")
    return "\n".join(out)


def main(root, work, py, argv):
    for stream in (sys.stdout, sys.stderr):  # a Windows console may not print every character; never crash on one
        try:
            stream.reconfigure(errors="replace")
        except Exception:  # noqa: BLE001 - an unusual stream; printing still works in most cases
            pass
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
Time limits use a thread rather than a signal, so they work the same on Windows, macOS and Linux.
"""
import importlib.util
import json
import os
import sys
import threading


class Timeout(Exception):
    pass


def within(seconds, fn, *args):
    """fn(*args), or Timeout after the given seconds. An overrunning call keeps running in the
    background; the harness leaves without waiting for it."""
    box = {}

    def run():
        try:
            box["value"] = fn(*args)
        except BaseException as e:  # noqa: BLE001 - handed back to the caller below
            box["error"] = e

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(seconds)
    if worker.is_alive():
        raise Timeout()
    if "error" in box:
        raise box["error"]
    return box.get("value")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main(learner_path, tests_path, out_path):
    try:
        tests = load(tests_path, "plan_tests")
    except ModuleNotFoundError as e:  # the tests themselves need a package this Python lacks
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump([{"what": "The tests ran", "ok": False,
                        "why": f"these tests need {e.name}, which this Python does not have; run the check with the course "
                               f"environment: uv run python plan/check.py"}], fh)
        return
    names = [n for n in dir(tests) if n.startswith("test_") and callable(getattr(tests, n))]
    names.sort(key=lambda n: getattr(tests, n).__code__.co_firstlineno)
    results, problem, learner = [], None, None
    shown = os.path.relpath(learner_path).replace(os.sep, "/")  # the checker runs from the fork's top folder
    if not os.path.isfile(learner_path):
        problem = f"{shown} is not in your fork yet"
    else:
        sys.path.insert(0, os.path.dirname(os.path.abspath(learner_path)))
        try:
            learner = within(20, load, learner_path, "learner")
        except Timeout:
            problem = f"importing {shown} took longer than 20 seconds; keep model calls inside functions"
        except ModuleNotFoundError as e:
            problem = (f"{shown} imports {e.name}, which the tests do not have (the standard library, openai, pydantic, "
                       f"dotenv, numpy, bs4 and tiktoken). Move that code to another file")
        except BaseException as e:  # noqa: BLE001 - report anything the learner's file raises
            problem = f"{shown} could not be imported: {type(e).__name__}: {e}"
    for n in names:
        fn = getattr(tests, n)
        what = (fn.__doc__ or n).strip().split("\n")[0]
        if problem:
            results.append({"what": what, "ok": False, "why": problem})
            continue
        try:
            within(10, fn, learner)
            results.append({"what": what, "ok": True, "why": ""})
        except Timeout:
            results.append({"what": what, "ok": False, "why": "it took longer than 10 seconds"})
        except AssertionError as e:
            results.append({"what": what, "ok": False, "why": str(e) or "the result was not what the exercise expects"})
        except BaseException as e:  # noqa: BLE001
            results.append({"what": what, "ok": False, "why": f"{type(e).__name__}: {e}"})
    for r in results:
        r["why"] = " ".join(str(r["why"]).split())[:220]
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)  # do not wait for a test that is still running past its limit
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

FILES['tests_ex_w1_day1.py'] = r'''"""Tests for plan/exercises/week1/day1.py (run by harness.py). No real model is called: the tests pass in a stand-in."""

FILE = "day1.py"
HTML = """<html><head><title>WrestleMania III</title><style>body { color: red; }</style></head>
<body>
<nav>Home | Events | Shop</nav>
<h1>WrestleMania III</h1>
<p>29 March 1987, Pontiac Silverdome</p>
<script>trackVisitor();</script>
<p>Main event: Hulk Hogan defeated André the Giant.</p>
<img src="slam.jpg" alt="The slam">
<input type="text" value="search">
<footer>Copyright notice</footer>
</body></html>"""


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def text_of(m, html=HTML):
    got = need(m, "page_text")(html)
    assert isinstance(got, str), f"page_text returned {type(got).__name__}, expected a string"
    return got


def test_title_first(m):
    """page_text starts with the page title, then a blank line"""
    got = text_of(m)
    assert got.startswith("WrestleMania III\n\n"), f"it starts with {got[:40]!r}; expected the title, then a blank line"


def test_no_title(m):
    """A page without a title starts with 'No title found'"""
    got = text_of(m, "<html><body><p>Card to be announced</p></body></html>")
    assert got.startswith("No title found\n\n"), f"it starts with {got[:40]!r}"
    assert "Card to be announced" in got, "the body text is missing"


def test_keeps_visible_text(m):
    """The visible text of the body is kept, one piece per line"""
    lines = [line.strip() for line in text_of(m).split("\n")]
    for piece in ("29 March 1987, Pontiac Silverdome", "Main event: Hulk Hogan defeated André the Giant."):
        assert piece in lines, f"{piece!r} is not on a line of its own"


def test_drops_noise(m):
    """Scripts, styles, images, inputs, navigation and footers are left out"""
    got = text_of(m)
    for noise in ("trackVisitor", "color: red", "Home | Events", "Copyright notice", "search", "The slam"):
        assert noise not in got, f"{noise!r} should have been left out"


def test_truncates(m):
    """page_text returns at most 2,000 characters"""
    long_page = "<html><head><title>Results</title></head><body>" + "<p>Pinfall victory.</p>" * 500 + "</body></html>"
    got = text_of(m, long_page)
    assert 0 < len(got) <= 2000, f"it returned {len(got)} characters, expected at most 2000"


def test_messages(m):
    """messages_for returns your system message, then a user message holding the page"""
    page = text_of(m)
    msgs = need(m, "messages_for")(page)
    assert isinstance(msgs, list) and len(msgs) == 2, "messages_for must return a list of two messages"
    assert [x.get("role") for x in msgs] == ["system", "user"], "the roles must be system, then user"
    assert isinstance(msgs[0].get("content"), str) and len(msgs[0]["content"].strip()) >= 20, "the system message is too short"
    assert page in msgs[1].get("content", ""), "the page text is not in the user message"


def test_with_style_copies(m):
    """with_style ends the system message with the style and leaves your list untouched"""
    original = [{"role": "system", "content": "You summarise pages."}, {"role": "user", "content": "The page"}]
    before = [dict(x) for x in original]
    got = need(m, "with_style")(original, "Answer like a ring announcer.")
    assert original == before, "with_style changed the messages it was given; build new ones instead"
    assert got[0]["role"] == "system" and got[0]["content"].endswith("\nAnswer like a ring announcer."), \
        "the system message must end with a new line, then the style"
    assert got[0]["content"].startswith("You summarise pages."), "keep the original system text before the style"
    assert got[1] == original[1], "the user message must stay the same"


def test_summarize(m):
    """summarize calls the model once with your messages and returns its reply, trimmed"""
    seen = []

    def model(msgs):
        seen.append(msgs)
        return "  Hogan slams André.  \n"

    got = need(m, "summarize")(HTML, model)
    assert got == "Hogan slams André.", f"summarize returned {got!r}, expected the reply without blank space around it"
    assert len(seen) == 1, f"the model was called {len(seen)} times, expected once"
    assert seen[0] == need(m, "messages_for")(need(m, "page_text")(HTML)), "the model did not get messages_for(page_text(html))"


def test_summarize_style(m):
    """summarize with a style sends the styled messages"""
    seen = []
    need(m, "summarize")(HTML, lambda msgs: seen.append(msgs) or "ok", style="Answer in Bahasa Indonesia.")
    assert seen and seen[0][0]["content"].endswith("\nAnswer in Bahasa Indonesia."), "the style did not reach the system message"
'''

FILES['tests_ex_w1_day2.py'] = r'''"""Tests for plan/exercises/week1/day2.py (run by harness.py). Nothing goes over the network: the tests pass in a stand-in for requests.post."""
from types import SimpleNamespace

FILE = "day2.py"
MESSAGES = [{"role": "user", "content": "Who won the main event of WrestleMania III?"}]
ANSWER = "Hulk Hogan defeated André the Giant."
URLS = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "ollama": "http://localhost:11434/v1",
}


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def completion(content):
    """The parsed JSON of a successful reply, with the parts that matter here."""
    return {"id": "chatcmpl-1", "object": "chat.completion", "model": "gpt-5-nano",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}


def stand_in_post(calls, answer):
    """Takes the same parameters as requests.post, records each call, and returns a response whose .json() is answer."""
    def post(url, data=None, json=None, **kwargs):
        calls.append({"url": url, "data": data, "json": json, **kwargs})
        return SimpleNamespace(status_code=200, json=lambda: answer)
    return post


def value_error(fn, arg, what):
    """Calls fn(arg) and returns the text of the ValueError it raises. Fails clearly if it does anything else."""
    try:
        got = fn(arg)
    except ValueError as e:
        return str(e)
    except Exception as e:  # noqa: BLE001 - reported to the learner
        raise AssertionError(f"{what} raised {type(e).__name__}: {e}, expected ValueError") from None
    raise AssertionError(f"{what} returned {got!r} instead of raising ValueError")


def test_body(m):
    """request_body holds the model and the messages"""
    got = need(m, "request_body")("gpt-5-nano", MESSAGES)
    assert isinstance(got, dict), f"request_body returned {type(got).__name__}, expected a dict"
    assert set(got) == {"model", "messages"}, f"with no options the body has the keys {sorted(got)}, expected only 'messages' and 'model'"
    assert got["model"] == "gpt-5-nano" and got["messages"] == MESSAGES, \
        "the body must hold the model and the messages you were given, as they are"


def test_body_options(m):
    """request_body adds each option that is set and leaves out options that are None"""
    got = need(m, "request_body")("gpt-5-nano", MESSAGES, temperature=0, max_tokens=None, seed=1987)
    assert got.get("model") == "gpt-5-nano" and got.get("messages") == MESSAGES, "model and messages are missing"
    assert "max_tokens" not in got, "max_tokens was None, so leave it out of the body"
    assert got.get("seed") == 1987, "seed=1987 was given, so the body needs 'seed': 1987"
    assert "temperature" in got and got["temperature"] == 0, \
        "temperature=0 was left out. Only None means not set: keep 0 and False"


def test_headers(m):
    """headers sends the key as a Bearer token, with a JSON content type"""
    got = need(m, "headers")("sk-proj-wm3")
    expected = {"Authorization": "Bearer sk-proj-wm3", "Content-Type": "application/json"}
    assert got == expected, f"headers('sk-proj-wm3') returned {got!r}, expected {expected!r}"


def test_reply_text(m):
    """reply_text returns the content of the first choice's message"""
    data = completion(ANSWER)
    data["choices"].append({"index": 1, "message": {"role": "assistant", "content": "A second choice"}})
    got = need(m, "reply_text")(data)
    assert got == ANSWER, f"reply_text returned {got!r}, expected {ANSWER!r}, from choices[0].message.content"


def test_reply_errors(m):
    """reply_text raises ValueError for an error reply, with its message, or for no choices"""
    fn = need(m, "reply_text")
    error = {"error": {"message": "Incorrect API key provided", "type": "invalid_request_error",
                       "param": None, "code": "invalid_api_key"}}
    text = value_error(fn, error, "reply_text on an error reply")
    assert "Incorrect API key provided" in text, \
        f"the ValueError says {text!r}. Include the error's own message, 'Incorrect API key provided'"
    value_error(fn, {"id": "chatcmpl-1", "choices": []}, "reply_text on a reply whose choices list is empty")
    value_error(fn, {"id": "chatcmpl-1"}, "reply_text on a reply with no choices")


def test_base_url(m):
    """base_url gives the lesson's base URL for openai, gemini and ollama, in any case"""
    fn = need(m, "base_url")
    for name, url in URLS.items():
        for spelling in (name, name.upper(), name.capitalize()):
            try:
                got = fn(spelling)
            except Exception as e:  # noqa: BLE001 - reported to the learner
                raise AssertionError(f"base_url({spelling!r}) raised {type(e).__name__}: {e}, expected {url!r}") from None
            assert got == url, f"base_url({spelling!r}) returned {got!r}, expected {url!r}"


def test_base_url_unknown(m):
    """base_url raises ValueError for a provider it does not know"""
    for name in ("acme", ""):
        value_error(need(m, "base_url"), name, f"base_url({name!r})")


def test_chat(m):
    """chat posts the body as JSON to the chat/completions endpoint, once, and returns the reply"""
    calls = []
    got = need(m, "chat")("openai", "sk-proj-wm3", "gpt-5-nano", MESSAGES, stand_in_post(calls, completion(ANSWER)),
                          temperature=0)
    assert len(calls) == 1, f"post was called {len(calls)} times, expected once"
    call = calls[0]
    assert call["url"] == "https://api.openai.com/v1/chat/completions", \
        f"post got the url {call['url']!r}, expected the lesson's endpoint 'https://api.openai.com/v1/chat/completions'"
    assert call.get("headers") == need(m, "headers")("sk-proj-wm3"), "post did not get headers=headers(api_key)"
    assert call["data"] is None and call["json"] == need(m, "request_body")("gpt-5-nano", MESSAGES, temperature=0), \
        "post did not get json=request_body(model, messages, **options). Pass the body as json=, as the lesson does"
    assert got == ANSWER, f"chat returned {got!r}, expected {ANSWER!r}, the reply_text of response.json()"


def test_chat_one_slash(m):
    """chat puts exactly one / before chat/completions for gemini and ollama too"""
    for provider in ("gemini", "ollama"):
        calls = []
        need(m, "chat")(provider, "a-key", "a-model", MESSAGES, stand_in_post(calls, completion(ANSWER)))
        expected = URLS[provider].rstrip("/") + "/chat/completions"
        got = calls[0]["url"] if calls else None
        assert got == expected, f"for {provider} post got the url {got!r}, expected {expected!r}"
'''

FILES['tests_ex_w1_day4.py'] = r'''"""Tests for plan/exercises/week1/day4.py (run by harness.py). No tokenizer is downloaded: the tests pass in a stand-in for encoding.encode."""
import copy
import re

FILE = "day4.py"
SYSTEM = "You answer questions about WWE history."  # 7 tokens with the stand-in below
SYSTEM_MESSAGE = {"role": "system", "content": SYSTEM}
HISTORY = [
    {"role": "user", "content": "Hi! I'm Ed!"},  # 7 tokens
    {"role": "assistant", "content": "Hi Ed! How can I help?"},  # 8
    {"role": "user", "content": "Where was WrestleMania III held?"},  # 6
    {"role": "assistant", "content": "At the Pontiac Silverdome, on 29 March 1987."},  # 10
    {"role": "user", "content": "Who won the main event?"},  # 6
    {"role": "assistant", "content": "Hulk Hogan defeated André the Giant."},  # 7
    {"role": "user", "content": "What's my name?"},  # 6
]
LONG = ("WrestleMania III was held on 29 March 1987 at the Pontiac Silverdome in Pontiac, Michigan, where Hulk Hogan "
        "defeated André the Giant to retain the WWF World Heavyweight Championship.")  # 32 tokens


def encode(text):
    """A stand-in for tiktoken's encoding.encode: one token per word and per punctuation mark."""
    return [len(piece) for piece in re.findall(r"\w+|[^\w\s]", text)]


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def first_words(messages):
    """A short view of a list of messages, for error text."""
    if not isinstance(messages, list):
        return repr(messages)[:60]
    return [" ".join(str(x.get("content", "") if isinstance(x, dict) else x).split()[:2]) for x in messages]


def test_count_tokens(m):
    """count_tokens returns how many token ids encode gives for the text"""
    fn = need(m, "count_tokens")
    got = fn("Hi! I'm Ed!", encode)
    assert got == 7, (f"count_tokens(\"Hi! I'm Ed!\", encode) returned {got!r}, expected 7, the length of encode(text). "
                      "This encode gives a token per word and per punctuation mark")
    got = fn("WrestleMania", lambda text: [54, 1043, 4935])
    assert got == 3, f"with an encode that returns [54, 1043, 4935], count_tokens returned {got!r}, expected 3"


def test_fit_all(m):
    """fit_history keeps the whole history after the system message when it all fits"""
    fit = need(m, "fit_history")
    for budget in (1000, 57):
        got = fit(SYSTEM, HISTORY, budget, encode)
        assert got == [SYSTEM_MESSAGE] + HISTORY, \
            f"budget {budget}: all 57 tokens fit, expected the system message, then all 7 messages in order. Got {first_words(got)}"


def test_fit_recent(m):
    """fit_history drops the oldest messages first and keeps the rest in their order"""
    fit = need(m, "fit_history")
    expected = [SYSTEM_MESSAGE] + HISTORY[-3:]
    for budget in (26, 35):
        got = fit(SYSTEM, HISTORY, budget, encode)
        assert got == expected, (f"budget {budget}: expected {first_words(expected)}, the system message and the last 3 "
                                 f"(7 + 6 + 7 + 6 = 26 tokens), got {first_words(got)}")


def test_fit_stops(m):
    """fit_history stops at the first message that does not fit and skips nothing"""
    history = [{"role": "user", "content": "Hi! I'm Ed!"}, {"role": "assistant", "content": LONG},
               {"role": "user", "content": "What's my name?"}]
    got = need(m, "fit_history")(SYSTEM, history, 30, encode)
    assert got == [SYSTEM_MESSAGE, history[2]], (
        f"budget 30: 7 + 6 = 13 tokens fit, the 32-token message before them does not, so stop there and do not skip "
        f"it to keep the older \"Hi! I'm Ed!\". Got {first_words(got)}")


def test_fit_system(m):
    """fit_history never drops the system message"""
    fit = need(m, "fit_history")
    for budget in (3, 0):
        got = fit(SYSTEM, HISTORY, budget, encode)
        assert got == [SYSTEM_MESSAGE], (f"budget {budget}: the system message alone has 7 tokens, so return just "
                                         f"[{{'role': 'system', 'content': system}}], got {first_words(got)}")


def test_fit_untouched(m):
    """fit_history keeps whole messages and leaves the history it was given unchanged"""
    history = copy.deepcopy(HISTORY)
    got = need(m, "fit_history")(SYSTEM, history, 30, encode)
    assert history == HISTORY, "fit_history changed the history it was given. Build a new list instead"
    for message in got[1:]:
        assert message in HISTORY, f"{message!r} is not one of the history's messages. Keep each message whole"


def test_remember(m):
    """remember returns a new history with the question and reply added, leaving yours unchanged"""
    fn = need(m, "remember")
    history = copy.deepcopy(HISTORY[:2])
    got = fn(history, "Where was WrestleMania III held?", "At the Pontiac Silverdome, on 29 March 1987.")
    assert history == HISTORY[:2], "remember changed the list it was given. Return a new list instead"
    assert got == HISTORY[:4], (f"remember returned {first_words(got)}, expected the 2 old messages, then the user's "
                                "question, then the assistant's reply")
    got = fn([], "Hi! I'm Ed!", "Hi Ed! How can I help?")
    assert got == HISTORY[:2], f"remember([], ...) returned {got!r}, expected a user message, then an assistant message"
'''

FILES['tests_ex_w1_day5.py'] = r'''"""Tests for plan/exercises/week1/day5.py (run by harness.py). No real model or website is used: the tests pass in stand-ins."""
import json

FILE = "day5.py"
SITE = "https://corporate.wwe.com"
ABOUT = "https://corporate.wwe.com/about"
CAREERS = "https://corporate.wwe.com/careers"
INVENTED = "https://corporate.wwe.com/history"
SHOWS = "https://www.wwe.com/shows/wrestlemania"
PAGE_LINKS = ["/", "/about", "/careers", "/privacy-policy", SHOWS]
REPLY = json.dumps({"links": [
    {"type": "careers page", "url": CAREERS},
    {"type": "about page", "url": ABOUT},
    {"type": "history page", "url": INVENTED},
    {"type": "about page", "url": ABOUT},
    {"type": "events page", "url": SHOWS},
]}, indent=4)
KEPT = [CAREERS, ABOUT, SHOWS]
PAGES = {
    ABOUT: "About\n\nKnown as the World Wrestling Federation until 6 May 2002, when the company announced its new name.",
    CAREERS: "Careers\n\nRaw first aired on 11 January 1993. Join the people who make it.",
    SHOWS: "WrestleMania\n\nThe first WrestleMania was held on 31 March 1985 at Madison Square Garden.",
}


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def value_error(fn, arg, what):
    """Calls fn(arg) and returns the text of the ValueError it raises. Fails clearly if it does anything else."""
    try:
        got = fn(arg)
    except ValueError as e:
        return str(e)
    except Exception as e:  # noqa: BLE001 - reported to the learner
        raise AssertionError(f"{what} raised {type(e).__name__}: {e}, expected ValueError") from None
    raise AssertionError(f"{what} returned {got!r} instead of raising ValueError")


def test_parse_links(m):
    """parse_links returns the urls from the lesson's JSON shape, in order"""
    reply = json.dumps({"links": [{"type": "about page", "url": ABOUT}, {"type": "careers page", "url": CAREERS}]})
    got = need(m, "parse_links")(reply)
    assert got == [ABOUT, CAREERS], f"parse_links returned {got!r}, expected [{ABOUT!r}, {CAREERS!r}]"


def test_parse_fenced(m):
    """parse_links also reads JSON wrapped in a ``` fenced block"""
    body = json.dumps({"links": [{"type": "about page", "url": ABOUT}]}, indent=4)
    for reply in (f"```json\n{body}\n```", f"\n```\n{body}\n```\n"):
        try:
            got = need(m, "parse_links")(reply)
        except Exception as e:  # noqa: BLE001 - reported to the learner
            raise AssertionError(f"a reply starting {reply[:9]!r} raised {type(e).__name__}: {e}. "
                                 "Remove the fence lines and blank space first") from None
        assert got == [ABOUT], f"for a reply starting {reply[:9]!r} parse_links returned {got!r}, expected [{ABOUT!r}]"


def test_parse_bad(m):
    """parse_links raises ValueError for text that is not JSON or has no links list"""
    for reply in ("Here are the links: /about and /careers", '{"pages": ["/about"]}', '{"links": "/about"}', '["/about"]'):
        value_error(need(m, "parse_links"), reply, f"parse_links({reply!r})")


def test_select_prompt(m):
    """select_links makes one call that asks for JSON and lists every page link on its own line"""
    seen = []
    need(m, "select_links")(SITE, PAGE_LINKS, lambda msgs: seen.append(msgs) or REPLY)
    assert len(seen) == 1, f"the model was called {len(seen)} times, expected once"
    msgs = seen[0]
    assert [x.get("role") for x in msgs] == ["system", "user"], "send a system message, then a user message"
    system, user = msgs[0]["content"], msgs[1]["content"]
    assert "json" in system.lower() and all(f'"{key}"' in system for key in ("links", "type", "url")), \
        'the system message must ask for JSON and show an example with the keys "links", "type" and "url"'
    assert SITE in user, f"the user message does not name the page's url, {SITE}"
    lines = [line.strip() for line in user.split("\n")]
    for link in PAGE_LINKS:
        assert link in lines, f"the page link {link!r} is not on a line of its own in the user message"


def test_select_keeps_real(m):
    """select_links keeps only links that are on the page, without repeats, in the model's order"""
    got = need(m, "select_links")(SITE, PAGE_LINKS, lambda msgs: REPLY)
    assert isinstance(got, list), f"select_links returned {type(got).__name__}, expected a list of urls"
    assert INVENTED not in got, f"{INVENTED} is not on the page, the model made it up. Leave it out"
    for url in KEPT:
        assert url in got, f"{url} is on the page, so keep it. Compare with urljoin(url, link) for each page link"
    assert got.count(ABOUT) == 1, "the model gave the about page twice. Keep each url once"
    assert got == KEPT, f"select_links returned {got!r}, expected the model's order: careers, about, then wrestlemania"


def test_brochure_messages(m):
    """brochure_messages names the company and puts each page under its url, in order"""
    msgs = need(m, "brochure_messages")("WWE", PAGES)
    assert isinstance(msgs, list) and [x.get("role") for x in msgs] == ["system", "user"], \
        "brochure_messages must return a system message, then a user message"
    assert len(msgs[0]["content"].strip()) >= 20, "the system message is too short"
    user = msgs[1]["content"]
    assert "WWE" in user, "the user message does not name the company"
    end = 0
    for url, text in PAGES.items():
        start = user.find(text, end)
        assert start >= 0, f"the text of {url} is missing from the user message, or out of the dict's order"
        assert user.rfind(url, end, start) >= 0, f"the url {url} must come just before its page text"
        end = start + len(text)


def test_brochure_cut(m):
    """brochure_messages cuts the user message to its first 5,000 characters"""
    pages = {ABOUT: PAGES[ABOUT] * 40, CAREERS: PAGES[CAREERS] * 40}
    user = need(m, "brochure_messages")("WWE", pages)[1]["content"]
    assert len(user) == 5000, f"the user message has {len(user)} characters, expected the first 5000 of it"
    assert "WWE" in user and ABOUT in user, "keep the start of the user message, with the company and the first page"


def test_create_brochure(m):
    """create_brochure makes two model calls and fetches only the landing page and the kept links"""
    site_pages = {SITE: "WWE\n\nA division of TKO Group Holdings since 12 September 2023.", **PAGES}
    fetched, seen = [], []

    def fetch(url):
        fetched.append(url)
        return site_pages.get(url, "Page not found")

    def model(msgs):
        seen.append(msgs)
        return REPLY if len(seen) == 1 else "  # WWE\n\nA brochure.\n  "

    got = need(m, "create_brochure")("WWE", SITE, PAGE_LINKS, fetch, model)
    assert len(seen) == 2, f"the model was called {len(seen)} times, expected twice: once to pick links, once to write"
    assert INVENTED not in fetched, "the invented link was fetched. Fetch only links that are on the page"
    assert fetched == [SITE] + KEPT, f"fetch got {fetched!r}, expected the landing page, then each kept link in order"
    pages = {url: site_pages[url] for url in [SITE] + KEPT}
    assert seen[1] == need(m, "brochure_messages")("WWE", pages), \
        "the second call did not get brochure_messages(company, pages), with the landing page first"
    assert got == "# WWE\n\nA brochure.", f"create_brochure returned {got!r}, expected the reply without blank space around it"
'''

FILES['tests_ex_w1_week1_exercise.py'] = r'''"""Tests for plan/exercises/week1/week1_exercise.py (run by harness.py). No real model is called: the tests pass in stand-ins."""
from types import SimpleNamespace

FILE = "week1_exercise.py"
QUESTION = 'Please explain what this code does and why:\nyield from {match.get("winner") for match in card if match.get("winner")}'
PIECES = ["It yields", " every winner", " once."]


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def chunk(content):
    """A stand-in for one chunk of an openai stream, read as chunk.choices[0].delta.content."""
    return SimpleNamespace(choices=[SimpleNamespace(index=0, delta=SimpleNamespace(content=content))])


def test_messages(m):
    """explain_messages gives a 20+ character system message, then the question as a user message"""
    msgs = need(m, "explain_messages")(QUESTION)
    assert isinstance(msgs, list) and len(msgs) == 2, "explain_messages must return a list of two messages"
    assert [x.get("role") for x in msgs] == ["system", "user"], "the roles must be system, then user"
    assert isinstance(msgs[0].get("content"), str) and len(msgs[0]["content"].strip()) >= 20, "the system message is too short"
    assert QUESTION in msgs[1].get("content", ""), "the question is not in the user message"


def test_pieces(m):
    """text_pieces yields each chunk's text, skipping None, empty text and chunks with no choices"""
    chunks = [chunk(""), chunk("It yields"), chunk(None), chunk(" every winner"), SimpleNamespace(choices=[]),
              chunk(" once."), chunk(None)]
    try:
        got = list(need(m, "text_pieces")(chunks))
    except Exception as e:  # noqa: BLE001 - reported to the learner
        raise AssertionError(f"text_pieces raised {type(e).__name__}: {e}. Skip a chunk whose choices list is empty") from None
    assert got == PIECES, f"text_pieces gave {got!r}, expected {PIECES!r}"


def test_pieces_lazy(m):
    """text_pieces gives the first piece before it reads the next chunk"""
    read = []

    def stream():
        for text in PIECES:
            read.append(text)
            yield chunk(text)

    first = next(iter(need(m, "text_pieces")(stream())))
    assert first == "It yields", f"the first piece was {first!r}, expected 'It yields'"
    assert len(read) == 1, (f"text_pieces read {len(read)} chunks before giving the first piece. "
                            "Use yield, so each piece comes out as soon as its chunk arrives")


def test_stream_once(m):
    """stream_explanation calls stream once, with explain_messages(question)"""
    seen = []

    def stream(msgs):
        seen.append(msgs)
        return iter(PIECES)

    list(need(m, "stream_explanation")(QUESTION, stream))
    assert len(seen) == 1, f"stream was called {len(seen)} times, expected once"
    assert seen[0] == need(m, "explain_messages")(QUESTION), "stream did not get explain_messages(question)"


def test_stream_text_so_far(m):
    """stream_explanation yields the whole text so far after each piece that has text"""
    pieces = ["It yields", None, " every winner", "", " once."]
    got = list(need(m, "stream_explanation")(QUESTION, lambda msgs: iter(pieces)))
    expected = ["It yields", "It yields every winner", "It yields every winner once."]
    assert got == expected, f"stream_explanation yielded {got!r}, expected {expected!r}"


def test_stream_lazy(m):
    """stream_explanation yields as soon as each piece arrives"""
    read = []

    def stream(msgs):
        for text in PIECES:
            read.append(text)
            yield text

    first = next(iter(need(m, "stream_explanation")(QUESTION, stream)))
    assert first == "It yields", f"the first thing yielded was {first!r}, expected 'It yields'"
    assert len(read) == 1, (f"stream_explanation read {len(read)} pieces before yielding anything. "
                            "Yield after each piece, so the text shows while it is still arriving")


def test_explain(m):
    """explain calls the model once with explain_messages(question) and returns the trimmed reply"""
    seen = []

    def model(msgs):
        seen.append(msgs)
        return "\n  It yields every winner once.  \n"

    got = need(m, "explain")(QUESTION, model)
    assert got == "It yields every winner once.", f"explain returned {got!r}, expected the reply without blank space around it"
    assert len(seen) == 1, f"the model was called {len(seen)} times, expected once"
    assert seen[0] == need(m, "explain_messages")(QUESTION), "the model did not get explain_messages(question)"
'''

FILES['tests_ex_w2_day1.py'] = r'''"""Tests for plan/exercises/week2/day1.py (run by harness.py). No real model is called: the tests pass in stand-ins."""
import time
from types import SimpleNamespace

import pydantic

FILE = "day1.py"
QUESTION = [{"role": "user", "content": "Where was WrestleMania III held?"}]
SIXTY = "WrestleMania III was held at the Pontiac Silverdome in 1987."  # exactly 60 characters
LONG = "Hulk Hogan slammed André the Giant and pinned him after a leg drop, in front of 93,173 fans."


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


class FakeClient:
    """Shaped like OpenAI(): client.chat.completions.create(...) returns a response that holds `reply`."""

    def __init__(self, reply):
        self.reply = reply
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))])


def answers(text, seen=None, name=None):
    def model(messages):
        if seen is not None:
            seen.append((name, messages))
        return text
    return model


def raises(error):
    def model(messages):
        raise error
    return model


def run_all(m, models):
    try:
        got = need(m, "ask_all")(models, QUESTION)
    except Exception as e:
        raise AssertionError(f"ask_all let a model's {type(e).__name__} escape; catch it, store its message in error "
                             f"and go on with the next model") from None
    assert isinstance(got, list), f"ask_all returned {type(got).__name__}, expected a list of Reply"
    assert len(got) == len(models), \
        f"ask_all returned {len(got)} replies for {len(models)} models; expected one each, also for the models that fail"
    assert all(isinstance(r, need(m, "Reply")) for r in got), "ask_all must return a list of Reply objects"
    return got


def test_reply(m):
    """Reply is a pydantic model whose error is None unless you set it"""
    Reply = need(m, "Reply")
    assert isinstance(Reply, type) and issubclass(Reply, pydantic.BaseModel), \
        "Reply must be a class that inherits from pydantic's BaseModel"
    fields = set(getattr(Reply, "model_fields", {}))
    assert {"model", "text", "seconds", "error"} <= fields, \
        f"Reply must have the fields model, text, seconds and error; it has {sorted(fields)!r:.80}"
    r = Reply(model="gpt-4.1-mini", text="The Pontiac Silverdome.", seconds=1.5)
    got = (r.model, r.text, r.seconds, r.error)
    assert got == ("gpt-4.1-mini", "The Pontiac Silverdome.", 1.5, None), \
        f"Reply(model=..., text=..., seconds=1.5) gave {got!r:.120}; expected those values and error None"
    failed = Reply(model="claude", text="", seconds=0.2, error="Overloaded")
    assert failed.error == "Overloaded", "Reply(..., error='Overloaded') must keep the error"


def test_caller(m):
    """caller returns a function that sends the model, the messages and any options to the client"""
    client = FakeClient("The Pontiac Silverdome.")
    ask = need(m, "caller")(client, "gpt-5-nano", reasoning_effort="minimal")
    assert callable(ask), f"caller returned {type(ask).__name__}; expected a function that takes messages"
    assert client.calls == [], "caller called the client straight away; only the function it returns should call it"
    got = ask(QUESTION)
    assert len(client.calls) == 1, f"one call of the returned function called create {len(client.calls)} times, expected once"
    args, kwargs = client.calls[0]
    assert not args, "pass everything to create as keyword arguments: create(model=model, messages=messages, **options)"
    assert kwargs == {"model": "gpt-5-nano", "messages": QUESTION, "reasoning_effort": "minimal"}, \
        f"create got {sorted(kwargs)}; expected model='gpt-5-nano', messages and reasoning_effort='minimal' (pass **options on)"
    assert got == "The Pontiac Silverdome.", f"the function returned {got!r:.60}; expected response.choices[0].message.content"
    plain = FakeClient("Hogan.")
    need(m, "caller")(plain, "gpt-4.1-mini")(QUESTION)
    assert plain.calls and plain.calls[0][1] == {"model": "gpt-4.1-mini", "messages": QUESTION}, \
        "with no options, create must get only model and messages"


def test_ask_all_order(m):
    """ask_all asks every model in the dict's order and returns one Reply each, in that order"""
    seen = []
    models = {"gpt": answers("Pontiac Silverdome", seen, "gpt"), "claude": answers("Pontiac, Michigan", seen, "claude"),
              "gemini": answers("The Silverdome", seen, "gemini")}
    got = run_all(m, models)
    assert seen == [("gpt", QUESTION), ("claude", QUESTION), ("gemini", QUESTION)], \
        f"the models were called as {[name for name, _ in seen]}; expected gpt, claude, gemini, once each, with the messages"
    assert [r.model for r in got] == ["gpt", "claude", "gemini"], \
        f"the replies are for {[r.model for r in got]}; expected the dict's order: gpt, claude, gemini"
    assert [r.text for r in got] == ["Pontiac Silverdome", "Pontiac, Michigan", "The Silverdome"], \
        f"the texts are {[r.text for r in got]!r:.120}; expected each model's reply"
    assert all(r.error is None for r in got), "replies from models that worked must have error None"


def test_ask_all_timing(m):
    """ask_all times each call on its own"""
    def slow(messages):
        time.sleep(0.2)
        return "Pontiac Silverdome"

    got = run_all(m, {"slow": slow, "quick": answers("Pontiac Silverdome")})
    assert got[0].seconds >= 0.19, \
        f"the slow model took 0.2 seconds but its Reply says {got[0].seconds:.3f}; time the call with time.perf_counter()"
    assert got[1].seconds < 0.15, \
        f"the quick model answered at once but its Reply says {got[1].seconds:.3f} seconds; start a new timer for each model"


def test_ask_all_errors(m):
    """A model that fails gets an empty text and its error, and the others still run"""
    later = []
    models = {"gpt": answers("Pontiac Silverdome"), "claude": raises(RuntimeError("Overloaded")),
              "slowpoke": raises(TimeoutError()), "gemini": answers("The Silverdome", later, "gemini")}
    got = run_all(m, models)
    claude, slowpoke = got[1], got[2]
    assert (claude.text, claude.error) == ("", "Overloaded"), \
        f"the failed model has text={claude.text!r:.30} and error={claude.error!r:.40}; expected '' and 'Overloaded'"
    assert slowpoke.error == "TimeoutError", \
        f"TimeoutError() has no message and gave error={slowpoke.error!r:.40}; use the class name, 'TimeoutError', instead"
    assert later and got[3].text == "The Silverdome", "the model after the failures did not run; go on with the next model"
    assert got[0].error is None and got[3].error is None, "the models that worked must have error None"
    assert isinstance(claude.seconds, float) and claude.seconds >= 0, "a failed call still needs its seconds"


def test_fastest(m):
    """fastest names the quickest reply without an error, or None if every call failed"""
    Reply, fastest = need(m, "Reply"), need(m, "fastest")
    replies = [Reply(model="gpt", text="ok", seconds=1.84), Reply(model="claude", text="", seconds=0.31, error="Overloaded"),
               Reply(model="gemini", text="ok", seconds=0.92), Reply(model="llama", text="ok", seconds=0.92)]
    got = fastest(replies)
    assert got == "gemini", \
        f"fastest gave {got!r:.40}; expected 'gemini': claude was quicker but failed, and gemini comes before llama in a tie"
    got = fastest([Reply(model="claude", text="", seconds=0.31, error="Overloaded")])
    assert got is None, f"with only failed replies fastest gave {got!r:.40}, expected None"
    assert fastest([]) is None, "fastest([]) must return None"


def table_lines(m, replies):
    got = need(m, "as_table")(replies)
    assert isinstance(got, str), f"as_table returned {type(got).__name__}, expected one string"
    assert not got.endswith("\n"), "the table must not end with a new line"
    return got.split("\n")


def test_table(m):
    """as_table starts with the two header lines, then one row per reply in order"""
    Reply = need(m, "Reply")
    lines = table_lines(m, [Reply(model="gpt", text="Hulk Hogan.", seconds=1.5),
                            Reply(model="claude", text="André the Giant.", seconds=0.314)])
    assert lines[:2] == ["| Model | Seconds | Reply |", "| --- | --- | --- |"], \
        f"the table starts {lines[:2]!r:.120}; expected '| Model | Seconds | Reply |' then '| --- | --- | --- |'"
    assert lines[2:] == ["| gpt | 1.50 | Hulk Hogan. |", "| claude | 0.31 | André the Giant. |"], \
        f"the rows are {lines[2:]!r:.100}; expected '| gpt | 1.50 | Hulk Hogan. |' then the claude row, seconds to 2 places"


def test_table_cells(m):
    """as_table keeps each reply on one line, cuts it after 60 characters and shows errors"""
    Reply = need(m, "Reply")
    rows = table_lines(m, [Reply(model="gpt", text="  Hulk Hogan\nwon.\n", seconds=1.0),
                           Reply(model="claude", text=LONG, seconds=1.0),
                           Reply(model="gemini", text=SIXTY, seconds=1.0),
                           Reply(model="llama", text="", seconds=0.2, error="Overloaded")])[2:]
    assert len(rows) == 4, f"the table has {len(rows)} rows for 4 replies; replace each new line in a reply with a space"
    assert rows[0] == "| gpt | 1.00 | Hulk Hogan won. |", \
        f"got {rows[0]!r:.80}; expected '| gpt | 1.00 | Hulk Hogan won. |' (new lines become spaces, ends trimmed)"
    assert rows[1] == f"| claude | 1.00 | {LONG[:60]}... |", \
        f"got {rows[1]!r:.100}; a reply longer than 60 characters keeps its first 60, then ..."
    assert rows[2] == f"| gemini | 1.00 | {SIXTY} |", "a reply of exactly 60 characters must stay whole, with no ..."
    assert rows[3] == "| llama | 0.20 | ERROR: Overloaded |", \
        f"got {rows[3]!r:.80}; expected '| llama | 0.20 | ERROR: Overloaded |' for a failed call"
'''

FILES['tests_ex_w2_day2.py'] = r'''"""Tests for plan/exercises/week2/day2.py (run by harness.py). No real model and no Gradio: the tests pass in stand-ins."""
from types import SimpleNamespace

FILE = "day2.py"


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def chunk(text):
    """Shaped like one chunk of a streamed reply: chunk.choices[0].delta.content is the text."""
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])


def recorded(name, calls, pieces=("ok",)):
    """A model stand-in: a function(prompt) that notes its call and returns the pieces."""
    def stream(prompt):
        calls.append((name, prompt))
        return iter(pieces)
    return stream


def pieces_of(m, chunks):
    got = need(m, "text_pieces")(chunks)
    assert hasattr(got, "__iter__"), f"text_pieces returned {type(got).__name__}; make it a generator that yields each piece"
    return got


def start(m, prompt, model_name, streams):
    got = need(m, "stream_model")(prompt, model_name, streams)
    assert hasattr(got, "__iter__"), \
        f"stream_model returned {type(got).__name__}; make it a generator that yields the text so far"
    return got


def run(m, prompt, model_name, streams):
    try:
        return list(start(m, prompt, model_name, streams))
    except AssertionError:
        raise
    except Exception as e:
        raise AssertionError(f"stream_model raised {type(e).__name__}: {e}") from None


def test_pieces(m):
    """text_pieces gives the text of each chunk and skips chunks that carry no text"""
    chunks = [chunk("Wrestle"), chunk(None), chunk("Mania"), chunk(""), chunk(" III")]
    got = list(pieces_of(m, chunks))
    assert got == ["Wrestle", "Mania", " III"], \
        f"got {got!r:.100}; expected ['Wrestle', 'Mania', ' III']: skip None and empty text, keep the rest unchanged"


def test_pieces_lazy(m):
    """text_pieces hands over each piece before it reads the next chunk"""
    read = []

    def chunks():
        for text in ["Hulk", " Hogan", " won"]:
            read.append(text)
            yield chunk(text)

    first = next(iter(pieces_of(m, chunks())), None)
    assert first == "Hulk", f"the first piece was {first!r:.40}, expected 'Hulk'"
    assert read == ["Hulk"], (f"text_pieces read {len(read)} chunks before handing over the first piece; "
                              f"yield each piece as soon as its chunk arrives")


def test_stream_text(m):
    """stream_model yields an empty string, then all the text so far after each piece"""
    got = run(m, "Who won the main event?", "GPT", {"GPT": lambda prompt: iter(["Hulk", " Hogan", " won"])})
    assert got[:1] == [""], f"the first value was {got[:1]!r:.40}; yield an empty string first, so the old answer clears"
    assert got == ["", "Hulk", "Hulk Hogan", "Hulk Hogan won"], \
        f"stream_model yielded {got!r:.110}; expected ['', 'Hulk', 'Hulk Hogan', 'Hulk Hogan won']"


def test_stream_lazy(m):
    """stream_model yields each step before it reads the next piece"""
    read = []

    def stream(prompt):
        for piece in ["Wrestle", "Mania"]:
            read.append(piece)
            yield piece

    text = None
    for text in start(m, "Which event?", "GPT", {"GPT": stream}):
        if text:
            break
    assert text == "Wrestle", f"the first value with text in it was {text!r:.40}, expected 'Wrestle'"
    assert read == ["Wrestle"], (f"stream_model read {len(read)} pieces before it yielded the first one; "
                                 f"yield after each piece instead of collecting them first")


def test_stream_choice(m):
    """stream_model calls only the chosen model, once, with the prompt"""
    calls = []
    streams = {"GPT": recorded("GPT", calls), "Claude": recorded("Claude", calls)}
    run(m, "Who main-evented WrestleMania I?", "Claude", streams)
    assert calls == [("Claude", "Who main-evented WrestleMania I?")], \
        f"the models were called as {calls!r:.120}; expected Claude once, with the prompt"


def test_unknown_model(m):
    """An unknown model name raises ValueError that names the models you can choose"""
    calls = []
    streams = {"GPT": recorded("GPT", calls), "Claude": recorded("Claude", calls)}
    try:
        list(need(m, "stream_model")("Who won?", "Llama", streams))
    except ValueError as e:
        message = str(e)
    except Exception as e:
        raise AssertionError(f"an unknown model name raised {type(e).__name__}; expected ValueError") from None
    else:
        raise AssertionError("an unknown model name gave no error; raise ValueError")
    for name in ("Llama", "Claude", "GPT"):
        assert name in message, \
            f"the error says {message!r:.100}; it should name 'Llama' and the models you can choose, Claude and GPT"
    assert calls == [], "no model should be called when the name is unknown"


def test_choices(m):
    """model_choices lists the names from A to Z, ignoring upper and lower case"""
    calls = []
    streams = {name: recorded(name, calls) for name in ("GPT", "claude-haiku", "Gemini", "llama3.2")}
    got = need(m, "model_choices")(streams)
    assert isinstance(got, list), f"model_choices returned {type(got).__name__}, expected a list"
    assert got == ["claude-haiku", "Gemini", "GPT", "llama3.2"], \
        f"got {got!r:.70}; expected ['claude-haiku', 'Gemini', 'GPT', 'llama3.2']: A to Z, ignoring upper and lower case"
    assert calls == [], "model_choices must not call any model"
'''

FILES['tests_ex_w2_day3.py'] = r'''"""Tests for plan/exercises/week2/day3.py (run by harness.py). No real model and no Gradio: the tests pass in stand-ins."""
import copy

FILE = "day3.py"
BASE = "You help shoppers in a replica title store."
NO_AUTOGRAPHS = "The store sells no autographed items. If asked, suggest a replica title instead."
CLEAN = [{"role": "user", "content": "Do you sell an Intercontinental Championship replica?"},
         {"role": "assistant", "content": "Yes, we do. Would you like to see it?"}]
HISTORY = [dict(CLEAN[0], metadata=None, options=None),  # as Gradio passes it, with extra keys
           dict(CLEAN[1], metadata={"title": "Store note"}, options=[])]


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def messages_of(m, history, message="Is it full size?"):
    got = need(m, "to_messages")(BASE, history, message)
    assert isinstance(got, list), f"to_messages returned {type(got).__name__}, expected a list of messages"
    return got


def test_order(m):
    """to_messages puts the system message first, then the history, then the new message"""
    got = messages_of(m, copy.deepcopy(CLEAN))
    roles = [x.get("role") for x in got]
    assert roles == ["system", "user", "assistant", "user"], \
        f"the roles are {roles}; expected system, then the history's roles, then user"
    assert got[0] == {"role": "system", "content": BASE}, "the first message must be {'role': 'system', 'content': system}"
    assert got[1:3] == CLEAN, "the history must come next, in its own order"
    assert got[-1] == {"role": "user", "content": "Is it full size?"}, \
        "the last message must be {'role': 'user', 'content': message}"


def test_clean(m):
    """to_messages keeps only role and content from each history entry"""
    got = messages_of(m, copy.deepcopy(HISTORY))
    extra = [sorted(x) for x in got if set(x) != {"role", "content"}]
    assert not extra, (f"some messages have the keys {extra!r:.80}; keep only role and content "
                       f"(Gradio adds keys such as metadata and options)")
    assert got[1:3] == CLEAN, "each history entry must keep its role and content as they were"


def test_untouched(m):
    """to_messages leaves the history it was given unchanged"""
    history = copy.deepcopy(HISTORY)
    messages_of(m, history)
    assert history == HISTORY, "to_messages changed the history it was given; build new messages instead"


def test_system_plain(m):
    """system_for returns the base prompt as it is when the message has no autograph in it"""
    got = need(m, "system_for")("Is the Intercontinental replica full size?", BASE)
    assert got == BASE, f"system_for gave {got!r:.100}; when the message does not mention autograph, return base unchanged"


def test_system_keyword(m):
    """system_for adds the no-autographs line when the message mentions autograph, in any case"""
    for message in ("Do you have AUTOGRAPHED titles?", "Is there an autograph on the Women's title?"):
        got = need(m, "system_for")(message, BASE)
        assert got == BASE + "\n" + NO_AUTOGRAPHS, \
            f"for {message!r} system_for gave {got!r:.70}; expected base, a new line, then the no-autographs line"


def test_chat(m):
    """chat calls the model once with the built messages and returns its reply"""
    system = need(m, "SYSTEM")
    assert isinstance(system, str) and len(system.strip()) >= 20, "SYSTEM must be your store's system message, 20+ characters"
    seen = []

    def model(messages):
        seen.append(copy.deepcopy(messages))
        return "Sorry, we sell no autographed items."

    history, message = copy.deepcopy(HISTORY), "Is there an autographed one?"
    got = need(m, "chat")(message, history, model)
    assert got == "Sorry, we sell no autographed items.", f"chat returned {got!r:.60}; expected the model's reply"
    assert len(seen) == 1, f"the model was called {len(seen)} times, expected once"
    assert history == HISTORY, "chat changed the history it was given"
    expected = need(m, "to_messages")(need(m, "system_for")(message, system), copy.deepcopy(HISTORY), message)
    assert seen[0] == expected, "the model did not get to_messages(system_for(message, SYSTEM), history, message)"
'''

FILES['tests_ex_w2_day4.py'] = r'''"""Tests for plan/exercises/week2/day4.py (run by harness.py). No real model is called: the tests pass in stand-ins."""
import copy
import json

FILE = "day4.py"
HISTORY = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello! Ask me about WrestleMania."}]


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def call(call_id, name, arguments):
    """One tool call in the API's format; the arguments are a JSON string."""
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


def asks(*calls):
    return {"role": "assistant", "content": None, "tool_calls": list(calls)}


def scripted(*replies):
    """A model stand-in: model(messages, tools) gives the replies in turn and notes what it was sent."""
    calls = []

    def model(messages, tools=None):
        calls.append({"messages": copy.deepcopy(messages), "tools": copy.deepcopy(tools)})
        return copy.deepcopy(replies[min(len(calls), len(replies)) - 1])
    return model, calls


def handle(m, message):
    try:
        got = need(m, "handle_tool_calls")(message)
    except Exception as e:
        raise AssertionError(f"handle_tool_calls raised {type(e).__name__}: {e}") from None
    assert isinstance(got, list), f"handle_tool_calls returned {type(got).__name__}, expected a list"
    return got


def run_chat(m, message, history, model):
    try:
        return need(m, "chat")(message, history, model)
    except Exception as e:
        hint = "; a reply without tool calls may have no 'tool_calls' key" if isinstance(e, KeyError) else ""
        raise AssertionError(f"chat raised {type(e).__name__}: {e}{hint}") from None


def test_known_events(m):
    """get_event_date finds the four WrestleManias in the spec, ignoring case and outer spaces"""
    get = need(m, "get_event_date")
    for event, date in [("WrestleMania I", "31 March 1985"), ("  wrestlemania iii ", "29 March 1987"),
                        ("WRESTLEMANIA X", "20 March 1994"), ("WrestleMania 32", "3 April 2016")]:
        got = get(event)
        assert got == date, f"get_event_date({event!r}) gave {got!r:.40}; expected {date!r}"


def test_unknown_event(m):
    """get_event_date returns 'unknown' for any name that is not in its dict"""
    for event in ("WrestleMania 99", "WrestleMania", "Mania III"):
        got = need(m, "get_event_date")(event)
        assert got == "unknown", f"get_event_date({event!r}) gave {got!r:.40}; expected 'unknown': the whole name must match"


def test_tool_entry(m):
    """EVENT_TOOL describes get_event_date with one required string parameter, event"""
    tool = need(m, "EVENT_TOOL")
    assert isinstance(tool, dict) and tool.get("type") == "function", "EVENT_TOOL must be a dict with 'type': 'function'"
    fn = tool.get("function")
    assert isinstance(fn, dict) and fn.get("name") == "get_event_date", "EVENT_TOOL['function'] must have 'name': 'get_event_date'"
    assert isinstance(fn.get("description"), str) and fn["description"].strip(), \
        "the function needs a description, so the model knows when to use it"
    params = fn.get("parameters")
    assert isinstance(params, dict) and params.get("type") == "object", "parameters must have 'type': 'object'"
    props = params.get("properties")
    assert isinstance(props, dict) and list(props) == ["event"], \
        f"parameters must have one property, 'event'; it has {list(props) if isinstance(props, dict) else props!r:.60}"
    assert isinstance(props["event"], dict) and props["event"].get("type") == "string", \
        "the event property must have 'type': 'string'"
    assert isinstance(props["event"].get("description"), str) and props["event"]["description"].strip(), \
        "the event property needs a description too"
    assert params.get("required") == ["event"], f"parameters has required={params.get('required')!r:.40}; expected ['event']"
    assert params.get("additionalProperties") is False, "parameters must have 'additionalProperties': False"


def test_handle_calls(m):
    """handle_tool_calls answers every call, in order, with role tool and the call's id"""
    got = handle(m, asks(call("call_1", "get_event_date", {"event": "WrestleMania III"}),
                         call("call_2", "get_event_date", {"event": "WrestleMania 32"})))
    expected = [{"role": "tool", "tool_call_id": "call_1", "content": "29 March 1987"},
                {"role": "tool", "tool_call_id": "call_2", "content": "3 April 2016"}]
    assert len(got) == 2, f"handle_tool_calls gave {len(got)} results for 2 calls; expected one per call"
    for result, wanted in zip(got, expected):
        assert result == wanted, f"got {result!r:.100}; expected {wanted!r}"


def test_handle_unknown_tool(m):
    """A call to any other tool gets 'unknown tool', and a reply with no calls gets []"""
    got = handle(m, asks(call("call_7", "get_ticket_price", {"destination_city": "London"}),
                         call("call_8", "get_event_date", {"event": "WrestleMania X"})))
    assert got == [{"role": "tool", "tool_call_id": "call_7", "content": "unknown tool"},
                   {"role": "tool", "tool_call_id": "call_8", "content": "20 March 1994"}], \
        f"got {got!r:.110}; every call needs an answer, and a tool you do not know gets 'unknown tool'"
    for reply in ({"role": "assistant", "content": "Hello!"}, {"role": "assistant", "content": "Hi", "tool_calls": None}):
        got = handle(m, reply)
        assert got == [], f"for a reply without tool calls handle_tool_calls gave {got!r:.60}; expected []"


def test_chat_plain(m):
    """chat sends SYSTEM, the history and the message with [EVENT_TOOL], then returns the text"""
    model, calls = scripted({"role": "assistant", "content": "I answer questions about WrestleMania."})
    got = run_chat(m, "Who are you?", copy.deepcopy(HISTORY), model)
    assert len(calls) == 1, f"the model was called {len(calls)} times; expected once, as the reply has no tool calls"
    expected = [{"role": "system", "content": need(m, "SYSTEM")}] + HISTORY + [{"role": "user", "content": "Who are you?"}]
    assert calls[0]["messages"] == expected, \
        "the model must get the system message with SYSTEM, then the history, then the new message as a user message"
    assert calls[0]["tools"] == [need(m, "EVENT_TOOL")], "the model must get tools=[EVENT_TOOL]"
    assert got == "I answer questions about WrestleMania.", f"chat returned {got!r:.60}; expected the reply's content"


def test_chat_tool_round(m):
    """chat runs the tool calls and asks the model again with their results"""
    first = asks(call("call_1", "get_event_date", {"event": "WrestleMania III"}))
    model, calls = scripted(first, {"role": "assistant", "content": "WrestleMania III took place on 29 March 1987."})
    history = copy.deepcopy(HISTORY)
    got = run_chat(m, "When was WrestleMania III?", history, model)
    assert len(calls) == 2, f"the model was called {len(calls)} times; after a reply with tool calls, call it once more"
    expected = calls[0]["messages"] + [first, {"role": "tool", "tool_call_id": "call_1", "content": "29 March 1987"}]
    assert calls[1]["messages"] == expected, \
        "the second call must get the first messages, then the model's reply with its tool calls, then the tool results"
    assert got == "WrestleMania III took place on 29 March 1987.", f"chat returned {got!r:.60}; expected the last reply's content"
    assert history == HISTORY, "chat changed the history it was given"
'''

FILES['tests_ex_w2_day5.py'] = r'''"""Tests for plan/exercises/week2/day5.py (run by harness.py). No real model is called: the tests pass in stand-ins."""
import copy
import json

import pydantic

FILE = "day5.py"
QUESTION = "Where was WrestleMania III held?"
ANSWER = "WrestleMania III was held at the Pontiac Silverdome in Pontiac, Michigan."
SUBJECT = "the Pontiac Silverdome packed with fans"
HISTORY = [{"role": "user", "content": "Who won WrestleMania III?"}, {"role": "assistant", "content": "Hulk Hogan."}]


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


class Studio:
    """Stand-ins for the three models. Each one notes what it was given."""

    def __init__(self, reply):
        self.reply, self.chats, self.drawings, self.speeches = reply, [], [], []

    def chat_model(self, messages):
        self.chats.append(copy.deepcopy(messages))
        return self.reply

    def artist(self, prompt):
        self.drawings.append(prompt)
        return "IMAGE"

    def talker(self, text):
        self.speeches.append(text)
        return b"AUDIO"


def take_turn(m, reply, history=None):
    studio = Studio(json.dumps(reply))
    history = copy.deepcopy(HISTORY) if history is None else history
    got = need(m, "multimodal_turn")(QUESTION, history, studio.chat_model, studio.artist, studio.talker)
    assert isinstance(got, dict), f"multimodal_turn returned {type(got).__name__}, expected a dict"
    return got, studio


def test_turn(m):
    """Turn is a pydantic model with a text answer and a draw that defaults to None"""
    Turn = need(m, "Turn")
    assert isinstance(Turn, type) and issubclass(Turn, pydantic.BaseModel), \
        "Turn must be a class that inherits from pydantic's BaseModel"
    fields = set(getattr(Turn, "model_fields", {}))
    assert {"answer", "draw"} <= fields, f"Turn must have the fields answer and draw; it has {sorted(fields)!r:.80}"
    plain = Turn(answer="Hulk Hogan.")
    assert plain.answer == "Hulk Hogan." and plain.draw is None, "Turn(answer='Hulk Hogan.') must have draw None"
    assert Turn(answer="Hulk Hogan.", draw=SUBJECT).draw == SUBJECT, "Turn must keep draw when it is given"


def test_image_prompt(m):
    """image_prompt follows the pattern exactly, without the blank space around the subject"""
    got = need(m, "image_prompt")("  the Pontiac Silverdome packed with fans \n")
    assert got == "A vibrant pop-art poster of the Pontiac Silverdome packed with fans, with no words in the picture", \
        f"got {got!r:.110}; expected 'A vibrant pop-art poster of <subject>, with no words in the picture'"


def test_system(m):
    """SYSTEM asks for a reply in JSON with the keys answer and draw"""
    system = need(m, "SYSTEM")
    assert isinstance(system, str), f"SYSTEM is {type(system).__name__}, expected a string"
    for word in ("json", "answer", "draw"):
        assert word in system.lower(), f"SYSTEM does not mention {word}; ask for a reply in JSON with the keys answer and draw"


def test_messages(m):
    """multimodal_turn sends SYSTEM, the history and the message, and leaves the history alone"""
    history = copy.deepcopy(HISTORY)
    _, studio = take_turn(m, {"answer": ANSWER, "draw": None}, history)
    assert len(studio.chats) == 1, f"the chat model was called {len(studio.chats)} times, expected once"
    expected = [{"role": "system", "content": need(m, "SYSTEM")}] + HISTORY + [{"role": "user", "content": QUESTION}]
    assert studio.chats[0] == expected, \
        "the chat model must get SYSTEM as the system message, then the history, then the message as a user message"
    assert history == HISTORY, "multimodal_turn changed the history it was given"


def test_draws_and_speaks(m):
    """When draw is set, artist gets image_prompt(draw) and talker gets the answer"""
    got, studio = take_turn(m, {"answer": ANSWER, "draw": SUBJECT})
    assert studio.drawings == [need(m, "image_prompt")(SUBJECT)], \
        f"artist got {studio.drawings!r:.110}; expected one call with image_prompt(draw)"
    assert studio.speeches == [ANSWER], f"talker got {studio.speeches!r:.110}; expected one call with the answer"
    assert got == {"answer": ANSWER, "image": "IMAGE", "audio": b"AUDIO"}, \
        f"multimodal_turn returned {got!r:.100}; expected the keys answer, image and audio"


def test_no_draw(m):
    """When draw is null, missing, empty or blank, artist is not called and image is None"""
    for reply in ({"answer": ANSWER, "draw": None}, {"answer": ANSWER}, {"answer": ANSWER, "draw": ""},
                  {"answer": ANSWER, "draw": "  "}):
        got, studio = take_turn(m, reply)
        assert studio.drawings == [], \
            f"with draw={reply.get('draw', '(missing)')!r} artist was called; call it only when draw holds text"
        assert got.get("image") is None, f"with draw={reply.get('draw', '(missing)')!r} image must be None"
        assert studio.speeches == [ANSWER] and got.get("audio") == b"AUDIO", "talker must still speak the answer, once"


def test_bad_reply(m):
    """A reply that is not JSON, or has no answer, raises ValueError before drawing or speaking"""
    for reply in ("Sure! WrestleMania III was held at the Pontiac Silverdome.", json.dumps({"draw": SUBJECT})):
        studio = Studio(reply)
        try:
            need(m, "multimodal_turn")(QUESTION, [], studio.chat_model, studio.artist, studio.talker)
        except ValueError:
            pass
        except Exception as e:
            raise AssertionError(f"for the reply {reply!r:.50} multimodal_turn raised {type(e).__name__}; "
                                 f"expected ValueError") from None
        else:
            raise AssertionError(f"for the reply {reply!r:.60} multimodal_turn raised nothing; expected ValueError")
        assert not studio.drawings and not studio.speeches, "artist and talker must not run when the reply is unusable"
'''

FILES['tests_ex_w2_week2_exercise.py'] = r'''"""Tests for plan/exercises/week2/week2_exercise.py (run by harness.py). No real model and no Gradio: the tests pass in
stand-ins."""
import copy

FILE = "week2_exercise.py"
QUESTION = "Where was it held?"
HISTORY = [{"role": "user", "content": "Who won the main event of WrestleMania III?"},
           {"role": "assistant", "content": "Hulk Hogan."}]
UNKNOWN = "no such expertise"


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def expertise_names(m):
    experts = need(m, "EXPERTISE")
    assert isinstance(experts, dict) and len(experts) >= 2, "EXPERTISE must be a dict with at least two entries"
    return list(experts)


def chat_with(text):
    """What answer should yield: the history, the question, then the answer so far."""
    return HISTORY + [{"role": "user", "content": QUESTION}, {"role": "assistant", "content": text}]


def recorded(name, calls, pieces):
    """A model stand-in: a function(messages) that notes its call and returns the pieces."""
    def stream(messages):
        calls.append((name, copy.deepcopy(messages)))
        return iter(pieces)
    return stream


def run(m, model_name, streams, expertise, history=None):
    history = copy.deepcopy(HISTORY) if history is None else history
    try:
        got = need(m, "answer")(QUESTION, history, model_name, streams, expertise)
        assert hasattr(got, "__iter__"), f"answer returned {type(got).__name__}; make it a generator that yields the chat"
        return list(got)
    except AssertionError:
        raise
    except Exception as e:
        raise AssertionError(f"answer raised {type(e).__name__}: {e}") from None


def test_expertise(m):
    """EXPERTISE holds at least two named system prompts, each different"""
    experts = need(m, "EXPERTISE")
    assert isinstance(experts, dict) and len(experts) >= 2, "EXPERTISE must be a dict with at least two entries"
    for name, prompt in experts.items():
        assert isinstance(name, str) and name.strip(), f"the key {name!r:.30} must be a name, such as 'python'"
        assert isinstance(prompt, str) and len(prompt.strip()) >= 20, \
            f"EXPERTISE[{name!r:.30}] must be a system prompt of 20 characters or more"
    assert len(set(experts.values())) == len(experts), "each expertise needs a system prompt of its own"


def test_build_messages(m):
    """build_messages puts the expertise's prompt first, then the history, then the question"""
    gradio_history = [dict(entry, metadata=None, options=None) for entry in HISTORY]
    for name in expertise_names(m)[:2]:
        history = copy.deepcopy(gradio_history)
        got = need(m, "build_messages")(QUESTION, history, name)
        assert isinstance(got, list) and len(got) == 4, \
            f"for 2 history entries build_messages returned {len(got) if isinstance(got, list) else got!r:.40}; expected 4 messages"
        assert got[0] == {"role": "system", "content": m.EXPERTISE[name]}, \
            f"for {name!r:.30} the first message must be {{'role': 'system', 'content': EXPERTISE[{name!r:.30}]}}"
        assert got[1:3] == HISTORY, "the history must come next, with only role and content in each entry, as on Day 3"
        assert got[3] == {"role": "user", "content": QUESTION}, "the last message must be the question, as a user message"
        assert history == gradio_history, "build_messages changed the history it was given"


def test_unknown_expertise(m):
    """build_messages raises ValueError for an unknown expertise and lists the choices"""
    names = expertise_names(m)
    try:
        need(m, "build_messages")(QUESTION, [], UNKNOWN)
    except ValueError as e:
        message = str(e)
    except Exception as e:
        raise AssertionError(f"an unknown expertise raised {type(e).__name__}; expected ValueError") from None
    else:
        raise AssertionError(f"build_messages(question, [], {UNKNOWN!r}) gave no error; raise ValueError")
    for name in names:
        assert name in message, f"the error says {message!r:.90}; it should list every key of EXPERTISE"


def test_next_history(m):
    """next_history returns a new list with the question and answer added, the old one unchanged"""
    history = copy.deepcopy(HISTORY)
    got = need(m, "next_history")(history, QUESTION, "At the Pontiac Silverdome.")
    assert history == HISTORY and got is not history, "next_history changed the list it was given; return a new list"
    assert isinstance(got, list), f"next_history returned {type(got).__name__}, expected a list"
    assert got == chat_with("At the Pontiac Silverdome."), \
        f"it ends with {got[-2:]!r:.100}; expected the question as a user message, then the answer as an assistant message"


def test_answer_streams(m):
    """answer yields the whole chat: first with an empty answer, then after each piece"""
    history = copy.deepcopy(HISTORY)
    got = run(m, "GPT", {"GPT": lambda messages: iter(["At the Pontiac", " Silverdome."])}, expertise_names(m)[0], history)
    assert all(isinstance(chat, list) for chat in got), \
        f"answer yielded {got[:1]!r:.60}; each yield must be the whole chat as a list of messages, not just the text"
    assert len(got) == 3, f"answer yielded {len(got)} times for 2 pieces; expected 3: once at the start, then after each piece"
    for step, (chat, text) in enumerate(zip(got, ["", "At the Pontiac", "At the Pontiac Silverdome."]), 1):
        assert chat == chat_with(text), \
            f"yield {step} ends with {chat[-1:]!r:.90}; expected the history, the question, then {text!r} from the assistant"
    assert history == HISTORY, "answer changed the history it was given"


def test_answer_model(m):
    """answer sends build_messages(question, history, expertise) to the chosen model only"""
    names, calls = expertise_names(m), []
    streams = {"GPT": recorded("GPT", calls, ["Hulk Hogan."]), "Claude": recorded("Claude", calls, ["Hulk Hogan."])}
    run(m, "Claude", streams, names[1])
    assert [name for name, _ in calls] == ["Claude"], \
        f"the models called were {[name for name, _ in calls]}; expected Claude only, once"
    assert calls[0][1] == need(m, "build_messages")(QUESTION, copy.deepcopy(HISTORY), names[1]), \
        "Claude did not get build_messages(question, history, expertise)"


def test_answer_unknown(m):
    """An unknown model or expertise raises ValueError before any yield or model call"""
    names, calls = expertise_names(m), []
    streams = {"GPT": recorded("GPT", calls, ["ok"]), "Claude": recorded("Claude", calls, ["ok"])}
    for model_name, expertise in (("Llama", names[0]), ("GPT", UNKNOWN)):
        case = f"with model {model_name!r} and expertise {expertise!r}"
        try:
            first = next(iter(need(m, "answer")(QUESTION, [], model_name, streams, expertise)))
        except ValueError:
            pass
        except StopIteration:
            raise AssertionError(f"{case}, answer yielded nothing and raised nothing; raise ValueError") from None
        except Exception as e:
            raise AssertionError(f"{case}, answer raised {type(e).__name__}; expected ValueError") from None
        else:
            raise AssertionError(f"{case}, answer first yielded {first!r:.50}; check both names before the first yield")
        assert calls == [], f"{case}, a model was called; check both names before calling any model"
'''

FILES['tests_ex_w3_day1.py'] = r'''"""Tests for plan/exercises/week3/day1.py (run by harness.py). Plain arithmetic: no GPU and no torch are needed."""
import math

FILE = "day1.py"
GPUS = [("large", 80), ("small", 16), ("medium", 40)]


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def test_weights_gb(m):
    """weights_gb gives decimal gigabytes: billions of parameters times bits, divided by 8"""
    f = need(m, "weights_gb")
    for args, want in [((8, 16), 16.0), ((7, 4), 3.5), ((70, 32), 280.0), ((1.5, 4), 0.75)]:
        got = f(*args)
        assert is_number(got) and math.isclose(got, want, rel_tol=1e-9), \
            f"weights_gb{args} returned {got!r}, expected {want} (8 bits to a byte, 1 GB = 1,000,000,000 bytes, no rounding)"


def test_weights_gb_rejects(m):
    """weights_gb raises ValueError when the size or the bits are zero or below"""
    f = need(m, "weights_gb")
    for args in [(0, 16), (-8, 16), (8, 0), (8, -4)]:
        try:
            got = f(*args)
        except ValueError:
            continue
        except Exception as e:  # noqa: BLE001 - say which error came instead
            raise AssertionError(f"weights_gb{args} raised {type(e).__name__}, expected ValueError")
        raise AssertionError(f"weights_gb{args} returned {got!r}, expected it to raise ValueError")


def test_fits_overhead(m):
    """fits multiplies the weights by the overhead before comparing with the GPU's memory"""
    f = need(m, "fits")
    got = f(8, 16, 16)
    assert got is False, f"fits(8, 16, 16) returned {got!r}, expected False: 16 GB times the default overhead 1.2 is 19.2 GB"
    got = f(8, 8, 15)
    assert got is True, f"fits(8, 8, 15) returned {got!r}, expected True: 8 GB times 1.2 is 9.6 GB"
    got = f(8, 8, 11, overhead=1.5)
    assert got is False, f"fits(8, 8, 11, overhead=1.5) returned {got!r}, expected False: 8 GB times 1.5 is 12 GB"


def test_fits_exact(m):
    """fits counts an exact match as fitting"""
    f = need(m, "fits")
    got = f(8, 8, 10, overhead=1.25)
    assert got is True, f"fits(8, 8, 10, overhead=1.25) returned {got!r}, expected True: 8 GB times 1.25 is exactly 10 GB"
    got = f(8, 8, 9.99, overhead=1.25)
    assert got is False, f"fits(8, 8, 9.99, overhead=1.25) returned {got!r}, expected False: 10 GB is more than 9.99 GB"


def test_best_precision(m):
    """best_precision returns the most bits at which the model fits"""
    f = need(m, "best_precision")
    cases = [((8, 15), {}, 8, "16 bits needs 19.2 GB with the overhead, 8 bits needs 9.6 GB"),
             ((3, 15), {}, 32, "32 bits needs 14.4 GB with the overhead"),
             ((8, 24), {}, 16, "32 bits needs 38.4 GB with the overhead, 16 bits needs 19.2 GB"),
             ((8, 16), {"overhead": 1.0}, 16, "with overhead=1.0, 16 bits needs exactly 16 GB")]
    for args, kwargs, want, why in cases:
        got = f(*args, **kwargs)
        shown = ", ".join([str(a) for a in args] + [f"{k}={v}" for k, v in kwargs.items()])
        assert got == want, f"best_precision({shown}) returned {got!r}, expected {want}: {why}"


def test_best_precision_none(m):
    """best_precision returns None when the model fits at none of the options"""
    f = need(m, "best_precision")
    got = f(70, 15)
    assert got is None, f"best_precision(70, 15) returned {got!r}, expected None: even 4 bits needs 42 GB with the overhead"
    got = f(70, 48, options=(16, 8))
    assert got is None, f"best_precision(70, 48, options=(16, 8)) returned {got!r}, expected None: 8 bits needs 84 GB"


def test_best_precision_any_order(m):
    """best_precision checks every option, whatever their order, and leaves the options unchanged"""
    f = need(m, "best_precision")
    options = [4, 16, 8]
    got = f(8, 24, options=options)
    assert got == 16, f"best_precision(8, 24, options=[4, 16, 8]) returned {got!r}, expected 16: the most bits that fit, not the first that fits"
    assert options == [4, 16, 8], f"the options list became {options!r}; do not sort or change the list you were given"


def test_pick_gpu(m):
    """pick_gpu returns the smallest GPU the model fits on, the first listed on a tie, or None"""
    f = need(m, "pick_gpu")
    got = f(8, 16, GPUS)
    assert got == "medium", f"pick_gpu(8, 16, {GPUS}) returned {got!r}, expected 'medium': 19.2 GB fits on medium and large, and medium is smaller"
    got = f(8, 4, GPUS)
    assert got == "small", f"pick_gpu(8, 4, ...) returned {got!r}, expected 'small': 4.8 GB fits on all three"
    got = f(70, 16, GPUS)
    assert got is None, f"pick_gpu(70, 16, ...) returned {got!r}, expected None: 168 GB fits on none of them"
    got = f(8, 16, [("large", 80), ("card A", 24), ("card B", 24)])
    assert got == "card A", f"with two 24 GB GPUs, pick_gpu returned {got!r}, expected 'card A', the one listed first"
    assert GPUS == [("large", 80), ("small", 16), ("medium", 40)], "pick_gpu changed the list it was given"
'''

FILES['tests_ex_w3_day2.py'] = r'''"""Tests for plan/exercises/week3/day2.py (run by harness.py). No model is loaded: the tests pass in results shaped
like the ones the pipelines return."""

FILE = "day2.py"
TEXT = ("Hulk Hogan faced André the Giant at WrestleMania III in the Pontiac Silverdome. "
        "Hulk Hogan slammed André the Giant and pinned him after a leg drop.")
ZERO_SHOT = {"sequence": TEXT, "labels": ["sport", "entertainment", "politics"], "scores": [0.62, 0.35, 0.03]}
UNSORTED = {"sequence": TEXT, "labels": ["politics", "entertainment", "sport"], "scores": [0.03, 0.35, 0.62]}
SENTIMENT = [{"label": "POSITIVE", "score": 0.9998}, {"label": "NEGATIVE", "score": 0.9871},
             {"label": "POSITIVE", "score": 0.9954}]


def entity(group, word, score, after=0):
    start = TEXT.index(word.strip(), after)
    return {"entity_group": group, "score": score, "word": word, "start": start, "end": start + len(word.strip())}


SECOND = TEXT.index("Hulk Hogan slammed")
ENTITIES = [entity("PER", "Hulk Hogan", 0.9991), entity("PER", "André the Giant", 0.9876),
            entity("MISC", "WrestleMania III", 0.9712), entity("LOC", "Pontiac Silverdome", 0.9934),
            entity("PER", "Hulk Hogan", 0.9989, SECOND), entity("PER", "André the Giant", 0.9853, SECOND)]
QA = {"score": 0.9312, "start": TEXT.index("Pontiac"), "end": TEXT.index("Pontiac") + 18, "answer": "Pontiac Silverdome"}


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def test_top_label(m):
    """top_label returns the label with the highest score"""
    got = need(m, "top_label")(ZERO_SHOT)
    assert got == "sport", f"for labels {ZERO_SHOT['labels']} with scores {ZERO_SHOT['scores']}, top_label returned {got!r}, expected 'sport'"


def test_top_label_any_order(m):
    """top_label finds the highest score even when the labels are not sorted"""
    got = need(m, "top_label")(UNSORTED)
    assert got == "sport", (f"for labels {UNSORTED['labels']} with scores {UNSORTED['scores']}, top_label returned {got!r}, "
                            f"expected 'sport'; find the highest score instead of taking the first label")


def test_top_label_threshold(m):
    """top_label returns 'unsure' when the best score is below the threshold"""
    f = need(m, "top_label")
    got = f(ZERO_SHOT, threshold=0.7)
    assert got == "unsure", f"the best score is 0.62 and threshold=0.7, but top_label returned {got!r}, expected 'unsure'"
    got = f(ZERO_SHOT, threshold=0.62)
    assert got == "sport", f"a best score equal to the threshold (0.62) is enough, but top_label returned {got!r}, expected 'sport'"
    low = {"sequence": TEXT, "labels": ["sport", "music", "politics"], "scores": [0.48, 0.47, 0.05]}
    got = f(low)
    assert got == "unsure", f"the best score is 0.48, under the default threshold of 0.5, but top_label returned {got!r}, expected 'unsure'"


def test_sentiment_counts(m):
    """sentiment_counts counts each label in lower case, and gives {} for no results"""
    f = need(m, "sentiment_counts")
    got = f(SENTIMENT)
    assert got == {"positive": 2, "negative": 1}, \
        f"for two POSITIVE results and one NEGATIVE, sentiment_counts returned {got!r}, expected {{'positive': 2, 'negative': 1}}"
    got = f([])
    assert got == {}, f"for an empty list sentiment_counts returned {got!r}, expected {{}}"


def test_entity_words(m):
    """entity_words lists the words of one group, each once, in the order they first appear"""
    f = need(m, "entity_words")
    got = f(ENTITIES, "PER")
    assert got == ["Hulk Hogan", "André the Giant"], \
        f"entity_words(entities, 'PER') returned {got!r}, expected ['Hulk Hogan', 'André the Giant']"
    got = f(ENTITIES, "LOC")
    assert got == ["Pontiac Silverdome"], f"entity_words(entities, 'LOC') returned {got!r}, expected ['Pontiac Silverdome']"
    got = f(ENTITIES, "ORG")
    assert got == [], f"no entity is in the group 'ORG', but entity_words returned {got!r}, expected []"


def test_entity_words_spaces(m):
    """entity_words removes spaces around each word before keeping it once"""
    spaced = [entity("PER", "Hulk Hogan", 0.99), entity("PER", " Hulk Hogan", 0.98, SECOND),
              entity("PER", "André the Giant ", 0.97)]
    got = need(m, "entity_words")(spaced, "PER")
    assert got == ["Hulk Hogan", "André the Giant"], \
        f"for the words 'Hulk Hogan', ' Hulk Hogan' and 'André the Giant ', entity_words returned {got!r}, expected ['Hulk Hogan', 'André the Giant']"


def test_confident_answer(m):
    """confident_answer returns the answer, trimmed, when its score reaches min_score"""
    f = need(m, "confident_answer")
    got = f(QA)
    assert got == "Pontiac Silverdome", f"for a score of 0.9312, confident_answer returned {got!r}, expected 'Pontiac Silverdome'"
    got = f(dict(QA, answer=" Pontiac Silverdome \n"))
    assert got == "Pontiac Silverdome", f"for the answer ' Pontiac Silverdome \\n', confident_answer returned {got!r}, expected 'Pontiac Silverdome'"
    got = f(dict(QA, score=0.8), min_score=0.8)
    assert got == "Pontiac Silverdome", f"a score equal to min_score (0.8) is enough, but confident_answer returned {got!r}"


def test_confident_answer_low(m):
    """confident_answer returns None when the score is below min_score"""
    f = need(m, "confident_answer")
    got = f(dict(QA, score=0.12))
    assert got is None, f"for a score of 0.12, under the default min_score of 0.5, confident_answer returned {got!r}, expected None"
    got = f(QA, min_score=0.95)
    assert got is None, f"for a score of 0.9312 with min_score=0.95, confident_answer returned {got!r}, expected None"
'''

FILES['tests_ex_w3_day3.py'] = r'''"""Tests for plan/exercises/week3/day3.py (run by harness.py). No tokenizer is downloaded: the tests compare strings."""

FILE = "day3.py"
SYSTEM = "You answer questions about WWE history."
QUESTION = "Who won the main event of WrestleMania III?"
MESSAGES = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": QUESTION}]
HEAD = "<|start_header_id|>{}<|end_header_id|>\n\n"
PROMPT = ("<|begin_of_text|>" + HEAD.format("system") + SYSTEM + "<|eot_id|>"
          + HEAD.format("user") + QUESTION + "<|eot_id|>" + HEAD.format("assistant"))
REPLY = "Hulk Hogan defeated André the Giant to retain the WWF World Heavyweight Championship."


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def first_difference(got, want):
    if not isinstance(got, str):
        return f"it returned {type(got).__name__}, expected a string"
    i = next((k for k, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
    return f"they differ at character {i}: yours has {got[i:i + 30]!r}, expected {want[i:i + 30]!r}"


def test_render_with_prompt(m):
    """render_llama3 writes the Llama 3 format, ending with the assistant header"""
    got = need(m, "render_llama3")(MESSAGES)
    assert got == PROMPT, "render_llama3(messages) is not the Llama 3 format: " + first_difference(got, PROMPT)


def test_render_without_prompt(m):
    """render_llama3 leaves out the assistant header when add_generation_prompt is False"""
    want = PROMPT[: -len(HEAD.format("assistant"))]
    got = need(m, "render_llama3")(MESSAGES, add_generation_prompt=False)
    assert got == want, "with add_generation_prompt=False, " + first_difference(got, want)


def test_render_strips_and_copies(m):
    """render_llama3 trims each message's content and leaves the messages unchanged"""
    chat = [{"role": "user", "content": "  Where was WrestleMania III held?\n"},
            {"role": "assistant", "content": "At the Pontiac Silverdome in Pontiac, Michigan.\n\n"},
            {"role": "user", "content": "\nAnd who won the main event? "}]
    before = [dict(x) for x in chat]
    want = ("<|begin_of_text|>" + HEAD.format("user") + "Where was WrestleMania III held?<|eot_id|>"
            + HEAD.format("assistant") + "At the Pontiac Silverdome in Pontiac, Michigan.<|eot_id|>"
            + HEAD.format("user") + "And who won the main event?<|eot_id|>" + HEAD.format("assistant"))
    got = need(m, "render_llama3")(chat)
    assert chat == before, "render_llama3 changed the messages it was given; build the string without editing them"
    assert got == want, "for a three-message chat with blank space around the contents, " + first_difference(got, want)


def test_special_tokens_order(m):
    """special_tokens lists the special tokens in order, repeats included"""
    text = "<|im_start|>system\nYou answer questions.<|im_end|>\n<|im_start|>user\nWho won?<|im_end|>\n"
    got = need(m, "special_tokens")(text)
    want = ["<|im_start|>", "<|im_end|>", "<|im_start|>", "<|im_end|>"]
    assert got == want, f"special_tokens returned {got!r}, expected {want!r}"


def test_special_tokens_strict(m):
    """special_tokens splits tokens side by side and skips look-alikes such as <|eot id|>"""
    f = need(m, "special_tokens")
    got = f("<|eot_id|><|start_header_id|>assistant<|end_header_id|>")
    want = ["<|eot_id|>", "<|start_header_id|>", "<|end_header_id|>"]
    assert got == want, f"for three tokens side by side, special_tokens returned {got!r}, expected {want!r}"
    got = f("Neither <||> nor <|eot id|> is a token, but <|reserved_special_token_5|> is.")
    want = ["<|reserved_special_token_5|>"]
    assert got == want, f"special_tokens returned {got!r}, expected {want!r}: a token has only letters, digits or underscores inside"


def test_last_reply(m):
    """last_reply returns the text after the last assistant header, up to <|eot_id|>"""
    f = need(m, "last_reply")
    got = f(PROMPT + REPLY + "<|eot_id|>")
    assert got == REPLY, f"for the prompt followed by the reply and <|eot_id|>, last_reply returned {got!r}, expected {REPLY!r}"
    earlier = ("<|begin_of_text|>" + HEAD.format("user") + "Where was WrestleMania III held?<|eot_id|>"
               + HEAD.format("assistant") + "At the Pontiac Silverdome.<|eot_id|>" + HEAD.format("user")
               + "Who won the main event?<|eot_id|>" + HEAD.format("assistant") + "Hulk Hogan.<|eot_id|>")
    got = f(earlier)
    assert got == "Hulk Hogan.", f"with two assistant messages, last_reply returned {got!r}, expected 'Hulk Hogan.', the last one"


def test_last_reply_edges(m):
    """last_reply reads a reply cut off before <|eot_id|>, and returns None with no header"""
    f = need(m, "last_reply")
    got = f(PROMPT + "Hulk Hogan defeated André the")
    assert got == "Hulk Hogan defeated André the", \
        f"for a reply with no <|eot_id|>, last_reply returned {got!r}, expected 'Hulk Hogan defeated André the'"
    got = f("<|begin_of_text|>" + HEAD.format("user") + QUESTION + "<|eot_id|>")
    assert got is None, f"for text with no assistant header, last_reply returned {got!r}, expected None"
'''

FILES['tests_ex_w3_day4.py'] = r'''"""Tests for plan/exercises/week3/day4.py (run by harness.py). Plain arithmetic on short lists: no model and no GPU."""
import math
import numbers
import random

FILE = "day4.py"
VALUES = [0.5, -2.1, 1.4]


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def weight_lists(seed):
    """Fixed lists of made-up weights: small ones like a model's, and larger ones."""
    rng = random.Random(seed)
    return ([[rng.gauss(0, 0.02) for _ in range(50)] for _ in range(20)]
            + [[rng.uniform(-3, 3) for _ in range(50)] for _ in range(20)])


def quantized(m, values, bits):
    shown = f"quantize({values!r}, {bits})" if len(values) <= 3 else f"quantize(values, {bits})"
    try:
        got = need(m, "quantize")(values, bits)
    except Exception as e:  # noqa: BLE001 - say what went wrong in the learner's words
        raise AssertionError(f"{shown} raised {type(e).__name__}: {e}")
    assert isinstance(got, tuple) and len(got) == 2, f"{shown} returned {got!r}, expected a tuple (ints, scale)"
    ints, scale = got
    return list(ints), scale


def test_quantize_example(m):
    """quantize finds the scale (largest size over top) and rounds each value divided by it"""
    ints, scale = quantized(m, VALUES, 4)
    assert math.isclose(scale, 0.3, rel_tol=1e-9), \
        f"quantize([0.5, -2.1, 1.4], 4) gave the scale {scale!r}, expected 0.3: the largest size, 2.1, divided by top, 7"
    assert ints == [2, -7, 5], \
        f"quantize([0.5, -2.1, 1.4], 4) gave the ints {ints!r}, expected [2, -7, 5]: round(0.5 / 0.3), round(-2.1 / 0.3), round(1.4 / 0.3)"


def test_quantize_range(m):
    """quantize keeps every int between -top and top, and the largest value becomes top or -top"""
    for bits in (2, 3, 4, 8):
        top = 2 ** (bits - 1) - 1
        for values in weight_lists(7):
            ints, _ = quantized(m, values, bits)
            assert len(ints) == len(values), f"quantize gave {len(ints)} ints for {len(values)} values, expected one per value"
            bad = [i for i in ints if not isinstance(i, numbers.Integral) or not -top <= i <= top]
            assert not bad, f"with {bits} bits quantize gave {bad[0]!r}, expected whole numbers from {-top} to {top}"
            k = max(range(len(values)), key=lambda j: abs(values[j]))
            want = top if values[k] > 0 else -top
            assert ints[k] == want, f"with {bits} bits the value with the largest size, {values[k]:.5f}, became {ints[k]!r}, expected {want}"


def test_quantize_zeros(m):
    """quantize uses the scale 1.0 when every value is zero, and for an empty list"""
    ints, scale = quantized(m, [0.0, 0.0, 0.0], 4)
    assert ints == [0, 0, 0] and scale == 1.0, f"quantize([0.0, 0.0, 0.0], 4) gave {(ints, scale)!r}, expected ([0, 0, 0], 1.0)"
    ints, scale = quantized(m, [], 4)
    assert ints == [] and scale == 1.0, f"quantize([], 4) gave {(ints, scale)!r}, expected ([], 1.0)"


def test_quantize_bits(m):
    """quantize raises ValueError when bits is less than 2"""
    f = need(m, "quantize")
    for bits in (1, 0):
        try:
            got = f([0.5, -2.1], bits)
        except ValueError:
            continue
        except Exception as e:  # noqa: BLE001 - say which error came instead
            raise AssertionError(f"quantize([0.5, -2.1], {bits}) raised {type(e).__name__}, expected ValueError")
        raise AssertionError(f"quantize([0.5, -2.1], {bits}) returned {got!r}, expected it to raise ValueError")


def test_dequantize(m):
    """dequantize multiplies each int by the scale, in order"""
    got = need(m, "dequantize")([2, -7, 5], 0.3)
    want = [0.6, -2.1, 1.5]
    assert isinstance(got, list) and len(got) == 3 and all(math.isclose(a, b, rel_tol=1e-9) for a, b in zip(got, want)), \
        f"dequantize([2, -7, 5], 0.3) returned {got!r}, expected a list close to {want}"


def test_round_trip_error_example(m):
    """round_trip_error returns the largest difference between a value and what came back"""
    f = need(m, "round_trip_error")
    got = f(VALUES, 4)
    assert isinstance(got, float) and math.isclose(got, 0.1, rel_tol=1e-6), \
        f"round_trip_error([0.5, -2.1, 1.4], 4) returned {got!r}, expected about 0.1: they come back as 0.6, -2.1 and 1.5"
    got = f([], 4)
    assert got == 0.0, f"round_trip_error([], 4) returned {got!r}, expected 0.0"


def test_round_trip_error_bound(m):
    """round_trip_error matches your quantize and is never more than half the scale"""
    f = need(m, "round_trip_error")
    for bits in (2, 3, 4, 8):
        for values in weight_lists(11):
            ints, scale = quantized(m, values, bits)
            want = max(abs(v - i * scale) for v, i in zip(values, ints))
            got = f(values, bits)
            assert isinstance(got, float) and math.isclose(got, want, rel_tol=1e-9, abs_tol=1e-15), \
                f"with {bits} bits round_trip_error returned {got!r}, but your quantize and dequantize give a largest difference of {want!r}"
            assert got <= scale / 2 * (1 + 1e-9), \
                f"with {bits} bits the error {got!r} is more than half the scale ({scale / 2!r}); round to the nearest whole number"
'''

FILES['tests_ex_w3_day5.py'] = r'''"""Tests for plan/exercises/week3/day5.py (run by harness.py). No real model is called: the tests pass in a stand-in."""

FILE = "day5.py"
TRANSCRIPT = ("Maya: Welcome, everyone. Today we plan the WrestleMania III episode.\n"
              "Tom: It took place on 29 March 1987\nat the Pontiac Silverdome.\n"
              "The WWF announced an attendance of 93,173.\n"
              "Maya: Later reporting put the crowd at about 78,000. Tom, can you check that?\n"
              "Tom: Yes, I will check it by Friday.")
S1 = "Maya: Welcome, everyone."  # 3 words
S2 = "Today we plan the WrestleMania III episode."  # 7
S3 = "Tom: It took place on 29 March 1987 at the Pontiac Silverdome."  # 12
S4 = "The WWF announced an attendance of 93,173."  # 7
S5 = "Maya: Later reporting put the crowd at about 78,000."  # 9
S6 = "Tom, can you check that?"  # 5
S7 = "Tom: Yes, I will check it by Friday."  # 8
LOCATION, DATE = "Studio 2", "14 October 2026"
MINUTES = """# Minutes: the WrestleMania III episode

## Summary
Maya and Tom met in Studio 2 on 14 October 2026.

## Action Items
- Tom: Check the later estimate of the crowd at WrestleMania III.
- **Maya**: Book the studio for Thursday.
  - Rina: Find the length of Steamboat against Savage: it was 14:35.
Remember the scripts.
- A line without a colon is skipped

## Next meeting
- Tom: This is not an action item.
"""


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def short(value, size=110):
    text = repr(value)
    return text if len(text) <= size else text[:size - 3] + "..."


def test_chunk_packs(m):
    """chunk_words packs whole sentences into pieces of at most max_words words"""
    got = need(m, "chunk_words")(TRANSCRIPT, 20)
    want = [" ".join([S1, S2]), " ".join([S3, S4]), " ".join([S5, S6]), S7]
    assert isinstance(got, list), f"chunk_words returned {type(got).__name__}, expected a list of strings"
    too_long = [p for p in got if isinstance(p, str) and len(p.split()) > 20]
    assert not too_long, f"a piece has {len(too_long[0].split())} words, more than max_words=20: {too_long[0][:60]!r}"
    assert got == want, (f"chunk_words(transcript, 20) should give 4 pieces of 10, 19, 14 and 8 words, each joined "
                         f"with single spaces; got {len(got)} pieces starting {short([p[:20] for p in got])}")


def test_chunk_exact_fit(m):
    """chunk_words lets a piece have exactly max_words words"""
    got = need(m, "chunk_words")(TRANSCRIPT, 19)
    want = [" ".join([S1, S2]), " ".join([S3, S4]), " ".join([S5, S6]), S7]
    assert got == want, (f"with max_words=19 the second piece should hold two sentences of 12 and 7 words, "
                         f"exactly 19; got pieces starting {short([p[:20] for p in got])}")


def test_chunk_long_sentence(m):
    """chunk_words puts a sentence longer than max_words in a piece of its own"""
    long = ("Ricky Steamboat defeated Randy Savage by pinfall to win the WWF Intercontinental Championship "
            "at WrestleMania III.")
    got = need(m, "chunk_words")("Steamboat won. " + long + " What a match!", 6)
    want = ["Steamboat won.", long, "What a match!"]
    assert got == want, (f"with max_words=6, expected 3 pieces: 'Steamboat won.', the 16-word sentence on its own, "
                         f"then 'What a match!'; got {short(got)}")


def test_chunk_edges(m):
    """chunk_words gives [] for blank text and raises ValueError when max_words is below 1"""
    f = need(m, "chunk_words")
    got = f("  \n  ", 10)
    assert got == [], f"for blank text chunk_words returned {got!r}, expected []"
    got = f("No full stop at the end", 3)
    assert got == ["No full stop at the end"], \
        f"text without a final full stop is one sentence, but chunk_words returned {got!r}, expected ['No full stop at the end']"
    try:
        got = f(TRANSCRIPT, 0)
    except ValueError:
        return
    except Exception as e:  # noqa: BLE001 - say which error came instead
        raise AssertionError(f"chunk_words(transcript, 0) raised {type(e).__name__}, expected ValueError")
    raise AssertionError(f"chunk_words(transcript, 0) returned {got!r}, expected it to raise ValueError")


def test_minutes_messages(m):
    """minutes_messages asks for the four headings and the item format, and holds the meeting"""
    msgs = need(m, "minutes_messages")(TRANSCRIPT, LOCATION, DATE)
    assert isinstance(msgs, list) and len(msgs) == 2, "minutes_messages must return a list of two messages"
    assert [x.get("role") for x in msgs] == ["system", "user"], "the roles must be system, then user"
    system, user = msgs[0].get("content", ""), msgs[1].get("content", "")
    for text in ("## Summary", "## Discussion points", "## Takeaways", "## Action items", "- Owner: task"):
        assert text in system, f"the system message does not contain {text!r}, written exactly like that"
    for name, value in (("location", LOCATION), ("date", DATE), ("transcript", TRANSCRIPT)):
        assert value in user, f"the {name} is not in the user message"


def test_action_items(m):
    """action_items reads the '- Owner: task' lines under ## Action items, in order"""
    got = need(m, "action_items")(MINUTES)
    want = [("Tom", "Check the later estimate of the crowd at WrestleMania III."),
            ("Maya", "Book the studio for Thursday."),
            ("Rina", "Find the length of Steamboat against Savage: it was 14:35.")]
    assert got == want, (f"expected the 3 items under '## Action Items' (any letter case), bold removed, split at the "
                         f"first colon, up to '## Next meeting'; got {short(got)}")


def test_action_items_none(m):
    """action_items returns [] when there is no Action items heading"""
    text = "## Summary\nPlanning only.\n- Tom: Not under the heading.\n### Action items\n- Maya: Still not."
    got = need(m, "action_items")(text)
    assert got == [], f"with no '## Action items' heading, action_items returned {got!r}, expected []"


def test_collect_actions(m):
    """collect_actions asks the model once per piece and joins the items, leaving out repeats"""
    replies = ["## Summary\nPlanning.\n\n## Action items\n- Tom: Check the attendance figure.\n",
               "## Action items\n- Tom: Check the attendance figure.\n- **Maya**: Book the studio.\n\n## Takeaways\n- Rina: no.\n",
               "## Summary\nNothing to do here.\n",
               "## Action items\n- Tom: Send the notes by Friday.\n"]
    seen = []

    def model(msgs):
        seen.append(msgs)
        return replies[len(seen) - 1] if len(seen) <= len(replies) else ""

    got = need(m, "collect_actions")(TRANSCRIPT, LOCATION, DATE, model, max_words=20)
    want = [("Tom", "Check the attendance figure."), ("Maya", "Book the studio."), ("Tom", "Send the notes by Friday.")]
    assert len(seen) == 4, f"with max_words=20 the transcript has 4 pieces, but the model was called {len(seen)} times"
    pieces = need(m, "chunk_words")(TRANSCRIPT, 20)
    assert seen == [need(m, "minutes_messages")(p, LOCATION, DATE) for p in pieces], \
        "the model did not get minutes_messages(piece, location, date) for each piece, in order"
    assert got == want, f"expected 3 items, each once, in the order the replies gave them; got {short(got)}"
    seen.clear()
    need(m, "collect_actions")(TRANSCRIPT, LOCATION, DATE, model)
    assert len(seen) == 1, f"with the default max_words=2000 the model should be called once, not {len(seen)} times"
'''

FILES['tests_ex_w4_day3.py'] = r'''"""Tests for plan/exercises/week4/day3.py (run by harness.py). No model, compiler or program is run: the tests pass in
stand-ins."""
import re

FILE = "day3.py"
PROGRAM = "\n".join([
    "import time",
    "",
    "start = time.time()",
    'attendance = {"WrestleMania I": 19121, "WrestleMania III": 93173}',
    'print(f"Total: {sum(attendance.values())}")',
    'print(f"Execution Time: {time.time() - start:.6f} seconds")',
    "",
])
CPP = '#include <cstdio>\nint main() {\n    std::printf("Total: %d\\n", 19121 + 93173);\n}'
RUST = 'fn main() {\n    println!("Total: {}", 19121 + 93173);\n}'
REPLY = f"Here is the fast version:\n\n```cpp\n{CPP}\n```\n\nIt prints the same total."
PI_PYTHON = "Result: 3.141592656089\nExecution Time: 19.178207 seconds\n"
PI_NATIVE = "Result: 3.141592656089\nExecution Time: 0.082168 seconds\n"


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def short(value, size=100):
    text = repr(value)
    return text if len(text) <= size else text[:size - 3] + "..."


def messages_of(m, *args):
    msgs = need(m, "port_messages")(PROGRAM, *args)
    assert isinstance(msgs, list) and len(msgs) == 2, "port_messages must return a list of two messages"
    assert [x.get("role") for x in msgs] == ["system", "user"], "the roles must be system, then user"
    return msgs[0].get("content", ""), msgs[1].get("content", "")


def test_port_messages_roles(m):
    """port_messages returns a system message, then a user message"""
    messages_of(m)


def test_port_messages_content(m):
    """port_messages names the language, asks for identical output and fences the Python code"""
    for args, language in (((), "C++"), (("Rust",), "Rust")):
        system, user = messages_of(m, *args)
        assert language in system and language in user, f"for language {language!r}, both messages must name {language}"
        assert "identical" in system.lower(), "the system message must ask for identical output, with the word 'identical'"
        fenced = re.search(r"```python[ \t]*\n(.*?)\n[ \t]*```", user, re.DOTALL)
        assert fenced, "the user message has no fenced block that opens with a line ```python and closes with a line ```"
        assert fenced.group(1).strip() == PROGRAM.strip(), "the fenced python block in the user message does not hold the Python code"


def test_extract_prefers_language(m):
    """extract_code returns the code of the first block tagged with the language"""
    f = need(m, "extract_code")
    got = f(REPLY)
    assert got == CPP, f"for a reply with a sentence before and after a cpp block, extract_code returned {short(got)}, expected the C++ alone"
    both = f"The original:\n```python\nprint('Total:', 19121 + 93173)\n```\nThe port:\n```CPP\n{CPP}\n```\n"
    got = f(both)
    assert got == CPP, f"with a python block before a CPP block, extract_code(reply) returned {short(got)}, expected the C++ (tags match in any case)"
    got = f(both, "python")
    assert got == "print('Total:', 19121 + 93173)", f"extract_code(reply, 'python') returned {short(got)}, expected the python block"


def test_extract_fallbacks(m):
    """extract_code falls back to the first fenced block, then to the whole reply"""
    f = need(m, "extract_code")
    got = f(f"Sure.\n```rust\n{RUST}\n```\n```\nsecond\n```")
    assert got == RUST, f"with no cpp block, extract_code returned {short(got)}, expected the first fenced block (the Rust one)"
    got = f(f"```\n{CPP}\n```")
    assert got == CPP, f"for a block with no tag, extract_code returned {short(got)}, expected its code"
    got = f(f"\n  {CPP}\n\n")
    assert got == CPP, f"for a reply with no fences, extract_code returned {short(got)}, expected the whole reply, trimmed"


def test_same_output_ignores(m):
    """same_output ignores timing lines, spaces at line ends and empty lines at the end"""
    f = need(m, "same_output")
    got = f(PI_PYTHON, PI_NATIVE)
    assert got is True, f"outputs that differ only in their Execution Time lines gave {got!r}, expected True"
    got = f(PI_PYTHON, "Result: 3.141592656089  \r\nExecution Time: 0.082168 seconds\r\n\r\n\r\n")
    assert got is True, f"spaces at line ends, Windows line endings and empty lines at the end gave {got!r}, expected True"
    got = f(PI_PYTHON, "Result: 3.141592656089\n")
    assert got is True, f"an output with no Execution Time line at all gave {got!r}, expected True"


def test_same_output_differs(m):
    """same_output returns False when any other line differs"""
    f = need(m, "same_output")
    cases = [(PI_PYTHON, PI_NATIVE.replace("656089", "656090"), "a different result"),
             (PI_PYTHON, "Execution Time: 0.082168 seconds\n", "a missing result line"),
             ("Total: 112294\nDone\n", "Total: 112294\n\nDone\n", "an extra blank line between two lines"),
             (PI_PYTHON, "  " + PI_NATIVE, "spaces at the start of a line")]
    for expected, actual, what in cases:
        got = f(expected, actual)
        assert got is False, f"same_output gave {got!r} for {what}, expected False"


def test_port_and_check(m):
    """port_and_check runs the extracted code, not the raw reply, and compares the outputs"""
    calls = {"model": [], "python": [], "native": []}

    def model(msgs):
        calls["model"].append(msgs)
        return REPLY

    def run_python(code):
        calls["python"].append(code)
        return "Total: 112294\nExecution Time: 0.000012 seconds\n"

    def run_native(code):
        calls["native"].append(code)
        return "Total: 112294\nExecution Time: 0.000001 seconds\n"

    got = need(m, "port_and_check")(PROGRAM, model, run_python, run_native)
    assert calls["model"] == [need(m, "port_messages")(PROGRAM, "C++")], "the model must be called once, with port_messages(python, 'C++')"
    assert calls["python"] == [PROGRAM], "run_python must be called once, with the Python code"
    assert calls["native"] == [CPP], f"run_native must be called once with the extracted code; it got {short(calls['native'])}"
    assert got == (CPP, True), f"port_and_check returned {short(got)}, expected (the C++ code, True)"
    got = need(m, "port_and_check")(PROGRAM, model, run_python, lambda code: "Total: 112293\n")
    assert isinstance(got, tuple) and got[1] is False, f"with a native program that prints another total, port_and_check returned {short(got)}, expected (code, False)"


def test_port_and_check_rust(m):
    """port_and_check asks for the language given and extracts the block with its tag"""
    seen = []
    reply = f"```python\n{PROGRAM}```\n\n```rust\n{RUST}\n```"

    def model(msgs):
        seen.append(msgs)
        return reply

    got = need(m, "port_and_check")(PROGRAM, model, lambda code: "Total: 112294\n", lambda code: "Total: 112294\n", language="Rust")
    assert seen == [need(m, "port_messages")(PROGRAM, "Rust")], "with language='Rust', the model must get port_messages(python, 'Rust')"
    assert isinstance(got, tuple) and got[0] == RUST, f"with language='Rust', port_and_check returned {short(got)}, expected the rust block's code"
'''

FILES['tests_ex_w4_day4.py'] = r'''"""Tests for plan/exercises/week4/day4.py (run by harness.py). The data are Ed's own timings from the lessons."""
import math

FILE = "day4.py"
PYTHON_SECONDS = 19.178207
RESULTS = [  # in the order of the lesson's models list
    {"model": "gpt-5", "correct": True, "seconds": 0.082168},
    {"model": "claude-sonnet-4-5-20250929", "correct": True, "seconds": 0.104241},
    {"model": "grok-4", "correct": True, "seconds": 0.018092},
    {"model": "gemini-2.5-pro", "correct": True, "seconds": 0.013314},
    {"model": "qwen2.5-coder", "correct": False, "seconds": None},
    {"model": "deepseek-coder-v2", "correct": True, "seconds": 0.114050084},
    {"model": "gpt-oss:20b", "correct": True, "seconds": 0.080438},
    {"model": "qwen/qwen3-coder-30b-a3b-instruct", "correct": True, "seconds": 0.113734},
    {"model": "openai/gpt-oss-120b", "correct": True, "seconds": 1.407383},
]
RANKING = ["gemini-2.5-pro", "grok-4", "gpt-oss:20b", "gpt-5", "claude-sonnet-4-5-20250929",
           "qwen/qwen3-coder-30b-a3b-instruct", "deepseek-coder-v2", "openai/gpt-oss-120b", "qwen2.5-coder"]
MIXED = [{"model": "model-a", "correct": True, "seconds": 0.5},
         {"model": "model-b", "correct": False, "seconds": 0.0001},
         {"model": "model-c", "correct": True, "seconds": 0.2},
         {"model": "model-d", "correct": False, "seconds": 3.0},
         {"model": "model-e", "correct": False, "seconds": None}]


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def copy(results):
    return [dict(r) for r in results]


def short(value, size=100):
    text = repr(value)
    return text if len(text) <= size else text[:size - 3] + "..."


def same_lines(got, want, what):
    assert isinstance(got, list) and len(got) == len(want), f"{what} returned {short(got)}; expected a list of {len(want)} lines"
    for i, (line, expected) in enumerate(zip(got, want)):
        assert line == expected, f"line {i + 1} of {what} is {line!r}, expected {expected!r}"


def test_speedup(m):
    """speedup divides the Python time by the native time, without rounding"""
    f = need(m, "speedup")
    got = f(PYTHON_SECONDS, 0.082168)
    assert isinstance(got, float) and math.isclose(got, 233.40238292279233, rel_tol=1e-12), \
        f"speedup(19.178207, 0.082168) returned {got!r}, expected about 233.4023829 (not rounded)"
    got = f(10, 4)
    assert got == 2.5, f"speedup(10, 4) returned {got!r}, expected 2.5"


def test_speedup_rejects(m):
    """speedup raises ValueError when the native time is zero or below"""
    f = need(m, "speedup")
    for native in (0, -0.5):
        try:
            got = f(PYTHON_SECONDS, native)
        except ValueError:
            continue
        except Exception as e:  # noqa: BLE001 - say which error came instead
            raise AssertionError(f"speedup(19.178207, {native}) raised {type(e).__name__}, expected ValueError")
        raise AssertionError(f"speedup(19.178207, {native}) returned {got!r}, expected it to raise ValueError")


def test_leaderboard_lesson(m):
    """leaderboard ranks Ed's nine models as the lesson does, with the failed one last"""
    got = need(m, "leaderboard")(copy(RESULTS))
    assert got == RANKING, f"expected gemini-2.5-pro, grok-4, gpt-oss:20b, gpt-5, ... and qwen2.5-coder last; got {short(got)}"


def test_leaderboard_wrong_last(m):
    """leaderboard puts every wrong model after the correct ones, in the order given"""
    got = need(m, "leaderboard")(copy(MIXED))
    want = ["model-c", "model-a", "model-b", "model-d", "model-e"]
    assert got == want, f"expected {want!r}: wrong ones go last in the order given, whatever their times; got {short(got)}"


def test_leaderboard_ties_and_input(m):
    """leaderboard keeps the given order for equal times and leaves the list unchanged"""
    results = [{"model": "model-a", "correct": True, "seconds": 0.5},
               {"model": "model-b", "correct": True, "seconds": 0.2},
               {"model": "model-c", "correct": True, "seconds": 0.2}]
    before = copy(results)
    got = need(m, "leaderboard")(results)
    assert results == before, "leaderboard changed the list it was given; sort a copy instead"
    assert got == ["model-b", "model-c", "model-a"], f"with model-b and model-c both at 0.2 seconds, leaderboard returned {got!r}, expected ['model-b', 'model-c', 'model-a']"


def test_summary_lesson(m):
    """summary gives one line per model in leaderboard order, as 'name: 1,440x faster'"""
    results = copy(RESULTS[:5])
    got = need(m, "summary")(results, PYTHON_SECONDS)
    want = ["gemini-2.5-pro: 1,440x faster", "grok-4: 1,060x faster", "gpt-5: 233x faster",
            "claude-sonnet-4-5-20250929: 184x faster", "qwen2.5-coder: wrong output"]
    same_lines(got, want, "summary(results, 19.178207)")


def test_summary_rounding(m):
    """summary rounds the speedup to a whole number, with commas between thousands"""
    f = need(m, "summary")
    got = f([{"model": "openai/gpt-oss-120b", "correct": True, "seconds": 0.000304}], 33.755209)
    assert got == ["openai/gpt-oss-120b: 111,037x faster"], \
        f"for 33.755209 seconds against 0.000304, summary returned {got!r}, expected ['openai/gpt-oss-120b: 111,037x faster']"
    got = f([{"model": "openai/gpt-oss-120b", "correct": True, "seconds": 1.407383}], PYTHON_SECONDS)
    assert got == ["openai/gpt-oss-120b: 14x faster"], f"a speedup of 13.63 gave {got!r}, expected ['openai/gpt-oss-120b: 14x faster']"


def test_summary_wrong(m):
    """summary writes 'wrong output' for each incorrect model, after the correct ones"""
    got = need(m, "summary")(copy(MIXED), 1.0)
    want = ["model-c: 5x faster", "model-a: 2x faster", "model-b: wrong output", "model-d: wrong output",
            "model-e: wrong output"]
    same_lines(got, want, "summary(results, 1.0)")
'''

FILES['tests_ex_w4_day5.py'] = r'''"""Tests for plan/exercises/week4/day5.py (run by harness.py). No program is compiled or run: the tests pass in
outputs like the ones the lesson's programs print."""

FILE = "day5.py"
FAILED = "An error occurred:\nerror[E0308]: mismatched types\n"


def out(seconds):
    return f"Total Maximum Subarray Sum (20 runs): 10980\nExecution Time: {seconds} seconds\n"


ROWS = [{"model": "model-a", "language": "C++", "output": out("0.000512")},
        {"model": "model-b", "language": "Rust", "output": out("0.000317")},
        {"model": "model-a", "language": "Rust", "output": FAILED},
        {"model": "model-c", "language": "C++", "output": out("3.41e-04")}]
TABLE = ["| Model | C++ | Rust |", "| --- | --- | --- |",
         "| model-a | 0.000512 | failed |", "| model-b | - | 0.000317 |", "| model-c | 0.000341 | - |"]


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def copy(rows):
    return [dict(r) for r in rows]


def table_of(m, rows):
    got = need(m, "report")(rows)
    assert isinstance(got, str), f"report returned {type(got).__name__}, expected one string"
    return got


def same_table(got, want):
    lines = got.split("\n")
    for i, (line, expected) in enumerate(zip(lines, want)):
        assert line == expected, f"line {i + 1} of the table is {line!r}, expected {expected!r}"
    assert len(lines) == len(want), f"the table has {len(lines)} lines, expected {len(want)}"


def test_parse_time(m):
    """parse_time reads the seconds that follow Execution Time:"""
    f = need(m, "parse_time")
    for output, want in [(out("0.000304"), 0.000304), ("Result: 3.141592656089\nExecution Time: 19.178207 seconds\n", 19.178207),
                         ("Execution Time:2 seconds", 2.0), ("Execution Time:    33.755209 seconds", 33.755209)]:
        got = f(output)
        assert got == want, f"parse_time returned {got!r} for {output.splitlines()[-1]!r}, expected {want!r}"


def test_parse_time_exponent(m):
    """parse_time reads numbers written with an exponent, such as 3.04e-05"""
    f = need(m, "parse_time")
    for text, want in [("3.04e-05", 3.04e-05), ("1E-3", 0.001), ("2.5e+01", 25.0)]:
        got = f(f"Execution Time: {text} seconds\n")
        assert got == want, f"for 'Execution Time: {text} seconds' parse_time returned {got!r}, expected {want!r}"


def test_parse_time_first_or_none(m):
    """parse_time uses the first timing line, and gives None when there is none"""
    f = need(m, "parse_time")
    got = f("Execution Time: 0.000317 seconds\nExecution Time: 0.000341 seconds\n")
    assert got == 0.000317, f"with two timing lines, parse_time returned {got!r}, expected 0.000317 from the first one"
    for output in (FAILED, "", "Execution Time: unknown\n"):
        got = f(output)
        assert got is None, f"for {output!r}, which has no time, parse_time returned {got!r}, expected None"


def test_report_header(m):
    """report has one column per language, in order of first appearance, and no final new line"""
    got = table_of(m, copy(ROWS))
    assert got.split("\n")[:2] == TABLE[:2], f"the table starts {got.split(chr(10))[:2]!r}, expected {TABLE[:2]!r}"
    assert not got.endswith("\n"), "the table ends with a new line; join the lines with \\n and add nothing after the last"
    got = table_of(m, [])
    assert got == "| Model |\n| --- |", f"with no rows, report returned {got!r}, expected '| Model |\\n| --- |'"


def test_report_cells(m):
    """report writes each model's time per language with 6 decimals, 'failed', or '-'"""
    rows = copy(ROWS)
    got = table_of(m, rows)
    assert rows == ROWS, "report changed the rows it was given"
    same_table(got, TABLE)


def test_report_fastest_run(m):
    """report keeps a model's fastest time when it ran more than once in a language"""
    rows = copy(ROWS) + [{"model": "model-a", "language": "C++", "output": out("0.000304")},
                         {"model": "model-a", "language": "C++", "output": out("0.000498")},
                         {"model": "model-a", "language": "Rust", "output": out("0.000333")},
                         {"model": "model-b", "language": "Rust", "output": ""}]
    want = TABLE[:2] + ["| model-a | 0.000304 | 0.000333 |", "| model-b | - | 0.000317 |", "| model-c | 0.000341 | - |"]
    same_table(table_of(m, rows), want)


def test_fastest_language(m):
    """fastest_language returns the language of the fastest run, or None"""
    f = need(m, "fastest_language")
    got = f(copy(ROWS) + [{"model": "model-c", "language": "Rust", "output": out("3.04e-04")}])
    assert got == "Rust", f"fastest_language returned {got!r}, expected 'Rust': model-c ran in 3.04e-04 seconds in Rust"
    got = f(copy(ROWS))
    assert got == "Rust", f"fastest_language returned {got!r}, expected 'Rust': model-b ran in 0.000317 seconds"
    tie = [{"model": "model-x", "language": "C++", "output": out("0.000341")},
           {"model": "model-y", "language": "Rust", "output": out("3.41e-04")}]
    got = f(tie)
    assert got == "C++", f"when C++ and Rust tie, fastest_language returned {got!r}, expected 'C++', whose row comes first"
    for rows in ([], [ROWS[2]]):
        got = f(rows)
        assert got is None, f"with no timed rows, fastest_language returned {got!r}, expected None"
'''

FILES['tests_ex_w5_day1.py'] = r'''"""Tests for plan/exercises/week5/day1.py (run by harness.py). No model is called. load_docs reads a temporary folder."""
import os
import tempfile

FILE = "day1.py"
HOGAN = "# Hulk Hogan\n\n- **Born:** 11 August 1953, Augusta, Georgia, United States\n"
ANDRE = "# André the Giant\n\n- **Born:** 19 May 1946, Coulommiers, France\n"
WM3 = "# WrestleMania III (1987)\n\n- **Date:** 29 March 1987\n- **Announced attendance:** 93,173\n\n## Results\n"
EDGE = "# Edge\n\n- **Hall of Fame:** Class of 2012\n"
DOCS = {
    "wrestlemania/wrestlemania-03.md": WM3,
    "people/hulk-hogan.md": HOGAN,
    "people/edge.md": EDGE,
    "people/andre-the-giant.md": ANDRE,
    "notes/untitled.md": "Card to be announced.\n",
}
BOTH = "Compare Hulk Hogan and André the Giant."


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def write(folder, rel, text):
    path = os.path.join(folder, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def loaded(m):
    with tempfile.TemporaryDirectory() as folder:
        write(folder, "about.md", "# About\n")
        write(folder, "people/hulk-hogan.md", HOGAN)
        write(folder, "people/andre-the-giant.md", ANDRE)
        write(folder, "people/notes.txt", "Not a Markdown file.\n")
        write(folder, "wrestlemania/1980s/wrestlemania-03.md", WM3)
        got = need(m, "load_docs")(folder)
    assert isinstance(got, dict), f"load_docs returned {type(got).__name__}, expected a dictionary"
    return got


def first_difference(got, want):
    for i, (a, b) in enumerate(zip(got, want)):
        if a != b:
            return i
    return min(len(got), len(want))


def test_load_paths(m):
    """load_docs finds every .md file below the folder, keyed by its path from that folder"""
    got = loaded(m)
    want = ["about.md", "people/andre-the-giant.md", "people/hulk-hogan.md", "wrestlemania/1980s/wrestlemania-03.md"]
    missing = [k for k in want if k not in got]
    assert not missing, (f"there is no key {missing[0]!r}. Keys are paths from the folder, with forward slashes, "
                         f"for .md files at any depth")
    extra = sorted(str(k) for k in got if k not in want)
    assert not extra, f"unexpected key {extra[0]!r}: keep only .md files"


def test_load_text(m):
    """load_docs keeps each file's text exactly as written, read as UTF-8"""
    got = loaded(m)
    for key, want in (("people/andre-the-giant.md", ANDRE), ("wrestlemania/1980s/wrestlemania-03.md", WM3)):
        text = got.get(key)
        assert text is not None, f"there is no key {key!r}; fix the keys first"
        assert text == want, f"the text for {key} starts {str(text)[:40]!r}, expected {want[:40]!r}. Read with encoding='utf-8'"


def test_title(m):
    """title_of returns the first line that starts with '# ', without the marker"""
    title_of = need(m, "title_of")
    cases = (("# WrestleMania III (1987)\n\n- **Date:** 29 March 1987\n", "WrestleMania III (1987)"),
             ("\n# Edge   \n", "Edge"),
             ("## Results\n- Hogan won\n# The Rock\n", "The Rock"))
    for text, want in cases:
        got = title_of(text)
        assert got == want, f"title_of({text!r}) returned {got!r}, expected {want!r}"


def test_no_title(m):
    """title_of returns '' when no line starts with '# '"""
    for text in ("## Results\n- Hogan won\n", "#Hashtag\nNo title here\n", ""):
        got = need(m, "title_of")(text)
        assert got == "", f"title_of({text!r}) returned {got!r}, expected ''"


def test_relevant(m):
    """relevant returns the sorted paths whose title is in the question, ignoring case"""
    got = need(m, "relevant")("Did HULK HOGAN slam André the Giant at WrestleMania III (1987)?", dict(DOCS))
    want = ["people/andre-the-giant.md", "people/hulk-hogan.md", "wrestlemania/wrestlemania-03.md"]
    assert isinstance(got, list), f"relevant returned {type(got).__name__}, expected a list"
    missing = [p for p in want if p not in got]
    assert not missing, (f"{missing[0]} is missing: its title is in the question, ignoring case. Only a letter or "
                         f"digit right before or after a title rules it out")
    extra = [p for p in got if p not in want]
    assert not extra, f"{extra[0]} should not be there: it has no title, or its title is not in the question as whole words"
    assert got == want, f"relevant returned {got}; expected the same paths, sorted"


def test_whole_words(m):
    """A title counts only as whole words, and a document without a title never matches"""
    relevant = need(m, "relevant")
    got = relevant("What is in the knowledge base?", dict(DOCS))
    assert got == [], (f"relevant returned {got}, expected []. 'edge' inside 'knowledge' is not the whole word Edge, "
                       f"and a document without a title never matches")
    got = relevant("Does the knowledge base cover Edge?", dict(DOCS))
    assert got == ["people/edge.md"], (f"relevant returned {got}, expected ['people/edge.md']. Look past the 'edge' "
                                       f"inside 'knowledge' to the whole word Edge at the end")


def test_context(m):
    """context joins a '## Source: <path>' part for each relevant document, a blank line apart"""
    got = need(m, "context")(BOTH, dict(DOCS), 10000)
    want = f"## Source: people/andre-the-giant.md\n{ANDRE.strip()}\n\n## Source: people/hulk-hogan.md\n{HOGAN.strip()}"
    assert isinstance(got, str), f"context returned {type(got).__name__}, expected a string"
    i = first_difference(got, want)
    assert got == want, f"at character {i}, context gives {got[i:i + 40]!r} where {want[i:i + 40]!r} was expected"


def test_context_limit(m):
    """context returns at most limit characters, and '' when nothing is relevant"""
    context = need(m, "context")
    full = context(BOTH, dict(DOCS), 10000)
    got = context(BOTH, dict(DOCS), 50)
    assert got == full[:50], f"with limit 50 it returned {len(got)} characters, {got!r}; expected the first 50 of the full context"
    got = context("Who is Bret Hart?", dict(DOCS), 1000)
    assert got == "", f"no title is in the question, so it should return '', not {got[:60]!r}"
'''

FILES['tests_ex_w5_day2.py'] = r'''"""Tests for plan/exercises/week5/day2.py (run by harness.py). No tokenizer is downloaded: the tests pass in a stand-in."""

FILE = "day2.py"
MAIN_EVENT = "Hulk Hogan defeated André the Giant by pinfall to retain the WWF World Heavyweight Championship (12:01)."
WORDS = MAIN_EVENT.split()  # 16 words
DOCS = {
    "wrestlemania/wrestlemania-03.md": "The WWF announced a paid attendance of 93,173.",
    "people/andre-the-giant.md": "André the Giant was born on 19 May 1946 in Coulommiers, France.",
}


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def words(start, end):
    return " ".join(WORDS[start:end])


def same_chunks(got, want, call):
    assert isinstance(got, list), f"{call} returned {type(got).__name__}, expected a list of strings"
    for i, (g, w) in enumerate(zip(got, want)):
        assert g == w, f"{call}: chunk {i} is {g!r}, expected {w!r}"
    assert len(got) == len(want), f"{call} returned {len(got)} chunks, expected {len(want)}"


def same_dicts(got, want):
    assert isinstance(got, list), f"chunk_documents returned {type(got).__name__}, expected a list of dictionaries"
    for i, (g, w) in enumerate(zip(got, want)):
        assert isinstance(g, dict) and sorted(g) == sorted(w), \
            f"chunk {i} has the keys {sorted(g) if isinstance(g, dict) else g!r}; expected exactly {sorted(w)}"
        wrong = [k for k in w if g[k] != w[k]]
        assert not wrong, f"chunk {i}: {wrong[0]} is {g[wrong[0]]!r}, expected {w[wrong[0]]!r}"
    assert len(got) == len(want), f"chunk_documents returned {len(got)} chunks, expected {len(want)}"


def test_kb_stats(m):
    """kb_stats counts documents, characters, and tokens from the encode function given"""
    docs = {"people/edge.md": "# Edge\n\n- **Hall of Fame:** Class of 2012\n",
            "events/royal-rumble-1988.md": "# Royal Rumble 1988\n\nJim Duggan won the 20-man Royal Rumble match.\n"}
    calls = []

    def encode(text):
        calls.append(text)
        return text.split()

    got = need(m, "kb_stats")(docs, encode)
    assert isinstance(got, dict) and sorted(got) == ["characters", "documents", "tokens"], \
        f"kb_stats returned {got!r}; expected a dictionary with the keys documents, characters and tokens"
    hints = {"documents": "count the documents",
             "characters": "add up len(text) for each document, with nothing between them",
             "tokens": "add up len(encode(text)) for each document. This stand-in encode returns the words"}
    for key, want in (("documents", 2), ("characters", 109), ("tokens", 21)):
        assert got[key] == want, f"{key} is {got[key]!r}, expected {want}: {hints[key]}"
    assert sorted(calls) == sorted(docs.values()), f"encode was called {len(calls)} times; call it once for each document"


def test_chunk_words(m):
    """chunk_words makes chunks of size words, each starting with overlap words of the last"""
    got = need(m, "chunk_words")(MAIN_EVENT, 6, 2)
    same_chunks(got, [words(0, 6), words(4, 10), words(8, 14), words(12, 16)], "chunk_words(text, 6, 2)")


def test_chunk_words_stops(m):
    """chunk_words stops at the chunk that holds the last word, so no chunk is only repeats"""
    got = need(m, "chunk_words")(MAIN_EVENT, 8, 4)
    want = [words(0, 8), words(4, 12), words(8, 16)]
    assert not (isinstance(got, list) and got[:3] == want and len(got) == 4), \
        f"the 4th chunk, {got[3]!r}, only repeats words of the 3rd. Stop after the chunk that holds the last word"
    same_chunks(got, want, "chunk_words(text, 8, 4)")


def test_chunk_words_spaces(m):
    """Words split at any blank space and join with single spaces, and no words gives []"""
    chunk_words = need(m, "chunk_words")
    text = "WrestleMania III\n\n29 March 1987,\tPontiac   Silverdome\n"
    same_chunks(chunk_words(text, 3, 0), ["WrestleMania III 29", "March 1987, Pontiac", "Silverdome"],
                "chunk_words(text, 3, 0)")
    same_chunks(chunk_words("Card to be announced", 10, 2), ["Card to be announced"],
                "chunk_words('Card to be announced', 10, 2)")
    same_chunks(chunk_words(" \n\t ", 5, 1), [], "chunk_words(' \\n\\t ', 5, 1)")


def test_chunk_words_bad(m):
    """chunk_words raises ValueError when overlap is negative or not smaller than size"""
    chunk_words = need(m, "chunk_words")
    for text, size, overlap in (("", 4, 4), ("", 4, 6), (MAIN_EVENT, 4, -1)):
        try:
            got = chunk_words(text, size, overlap)
        except ValueError:
            continue
        raise AssertionError(f"chunk_words({text[:12]!r}, {size}, {overlap}) returned {str(got)[:50]} instead of raising "
                             f"ValueError. Check size and overlap first, even for an empty text")


def test_chunk_documents(m):
    """chunk_documents gives source, doc_type, index and text, in sorted order of path"""
    got = need(m, "chunk_documents")(dict(DOCS), 5, 1)
    andre, wm3 = "people/andre-the-giant.md", "wrestlemania/wrestlemania-03.md"
    want = [
        {"source": andre, "doc_type": "people", "index": 0, "text": "André the Giant was born"},
        {"source": andre, "doc_type": "people", "index": 1, "text": "born on 19 May 1946"},
        {"source": andre, "doc_type": "people", "index": 2, "text": "1946 in Coulommiers, France."},
        {"source": wm3, "doc_type": "wrestlemania", "index": 0, "text": "The WWF announced a paid"},
        {"source": wm3, "doc_type": "wrestlemania", "index": 1, "text": "paid attendance of 93,173."},
    ]
    same_dicts(got, want)


def test_chunk_documents_types(m):
    """doc_type is the first folder in the path, and an empty document adds no chunk"""
    hogan = "Hulk Hogan won the WWF World Heavyweight Championship on 23 January 1984."
    got = need(m, "chunk_documents")({"people/empty.md": " \n", "eras/golden-era/hulk-hogan.md": hogan}, 50, 10)
    want = [{"source": "eras/golden-era/hulk-hogan.md", "doc_type": "eras", "index": 0, "text": hogan}]
    same_dicts(got, want)
'''

FILES['tests_ex_w5_day3.py'] = r'''"""Tests for plan/exercises/week5/day3.py (run by harness.py). No real model or embedding is called: the tests pass in stand-ins."""
import math

FILE = "day3.py"
QUESTION = "Who won the first Royal Rumble match?"
CHUNKS = [
    {"source": "people/edge.md", "text": "Edge debuted on Raw on 22 June 1998."},
    {"source": "events/royal-rumble-1988.md", "text": "Jim Duggan won the 20-man Royal Rumble match."},
    {"source": "wrestlemania/wrestlemania-03.md", "text": "The WWF announced a paid attendance of 93,173."},
    {"source": "people/andre-the-giant.md", "text": "In 1993 André became the first member of the WWF Hall of Fame."},
    {"source": "match-types/royal-rumble.md", "text": "Pat Patterson created the Royal Rumble match."},
    {"source": "topics/undertakers-wrestlemania-streak.md", "text": "The Undertaker won 21 WrestleMania matches in a row."},
]
QUERY = [1, 0, 0]
VECTORS = [[0, 1, 0], [1, 0, 0], [1, 1, 0], [0, 0, 1], [2, 1, 0], [-1, 0, 0]]
# Cosines with QUERY: 0, 1, 0.71, 0, 0.89, -1. Most similar first: 1, 4, 2, then 0 and 3 (a tie), then 5.


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def chunks():
    return [dict(c) for c in CHUNKS]


def vectors():
    return [list(v) for v in VECTORS]


def positions(got):
    assert isinstance(got, list), f"top_k returned {type(got).__name__}, expected a list of positions"
    return [int(i) for i in got]


def test_cosine(m):
    """cosine gives 1.0, 0.0, -1.0 and 0.96 for these pairs of vectors"""
    cosine = need(m, "cosine")
    for a, b, want in (([1, 2], [2, 4], 1.0), ([1, 0], [0, 3], 0.0), ([1, 0], [-2, 0], -1.0), ([3, 4], [4, 3], 0.96)):
        got = cosine(list(a), list(b))
        assert isinstance(got, (int, float)) and math.isclose(got, want, abs_tol=1e-9), \
            f"cosine({a}, {b}) returned {got!r}, expected {want}"


def test_cosine_zero(m):
    """cosine raises ValueError when either vector is all zeros"""
    cosine = need(m, "cosine")
    for a, b in (([0, 0], [1, 2]), ([3, 4], [0, 0])):
        try:
            got = cosine(list(a), list(b))
        except ValueError:
            continue
        except ZeroDivisionError:
            raise AssertionError(f"cosine({a}, {b}) raised ZeroDivisionError. Check for a vector of zeros first "
                                 f"and raise ValueError") from None
        raise AssertionError(f"cosine({a}, {b}) returned {got!r}. A vector of zeros has no direction: raise ValueError")


def test_top_k(m):
    """top_k returns the positions of the k most similar vectors, most similar first"""
    got = positions(need(m, "top_k")(list(QUERY), vectors(), 3))
    assert got == [1, 4, 2], f"top_k(query, vectors, 3) returned {got}, expected [1, 4, 2]: the cosines are 0, 1, 0.71, 0, 0.89, -1"


def test_top_k_ties(m):
    """On a tie the lower position comes first, and a k above the count returns them all"""
    top_k = need(m, "top_k")
    got = positions(top_k([1, 0], [[0, 1], [1, 0], [0, 2], [3, 0]], 4))
    assert got == [1, 3, 0, 2], f"top_k returned {got}, expected [1, 3, 0, 2]: 1 and 3 tie at 1.0, and 0 and 2 tie at 0.0"
    got = positions(top_k(list(QUERY), vectors(), 10))
    assert got == [1, 4, 2, 0, 3, 5], f"top_k(query, vectors, 10) returned {got}, expected all six: [1, 4, 2, 0, 3, 5]"


def test_rag_messages(m):
    """rag_messages lists each chunk under 'Extract from <source>:' in the system message"""
    msgs = need(m, "rag_messages")(QUESTION, chunks()[:3])
    assert isinstance(msgs, list) and len(msgs) == 2, "rag_messages must return a list of two messages"
    assert [x.get("role") for x in msgs] == ["system", "user"], "the roles must be system, then user"
    system = msgs[0].get("content")
    assert isinstance(system, str), "the system message has no text content"
    blocks = [f"Extract from {c['source']}:\n{c['text']}" for c in CHUNKS[:3]]
    for block in blocks:
        assert block in system, f"the system message lacks {block!r}"
    assert "\n\n".join(blocks) in system, "the extracts must come in the order given, with a blank line between them"
    assert len(system[:system.find(blocks[0])].strip()) >= 20, \
        "start the system message with instructions of your own, 20 characters or more, before the extracts"
    assert msgs[1].get("content") == QUESTION, f"the user message must be the question unchanged, not {msgs[1].get('content')!r}"


def test_answer_calls(m):
    """answer embeds only the question, then calls the model once with the top k chunks"""
    embedded, seen = [], []

    def embed(text):
        embedded.append(text)
        return list(QUERY)

    def model(msgs):
        seen.append(msgs)
        return "Jim Duggan won it."

    need(m, "answer")(QUESTION, chunks(), vectors(), embed, model, k=2)
    assert embedded == [QUESTION], (f"embed was called {len(embedded)} times; call it once, with the question only. "
                                    f"The chunks' vectors are given")
    assert len(seen) == 1, f"the model was called {len(seen)} times, expected once"
    want = need(m, "rag_messages")(QUESTION, [dict(CHUNKS[1]), dict(CHUNKS[4])])
    assert seen[0] == want, "the model did not get rag_messages(question, the 2 most similar chunks, most similar first)"


def test_answer_returns(m):
    """answer returns the trimmed reply and the chunks it used, k=4 by default"""
    got = need(m, "answer")(QUESTION, chunks(), vectors(), lambda text: list(QUERY), lambda msgs: "  Jim Duggan won it.\n")
    assert isinstance(got, tuple) and len(got) == 2, f"answer returned {type(got).__name__}, expected a pair: (reply, chunks used)"
    reply, used = got
    assert reply == "Jim Duggan won it.", f"the reply is {reply!r}, expected it without the blank space around it"
    assert isinstance(used, list), f"the chunks used are a {type(used).__name__}, expected a list"
    found = [CHUNKS.index(c) if c in CHUNKS else "?" for c in used]
    assert found == [1, 4, 2, 0], (f"it used the chunks at positions {found}, expected [1, 4, 2, 0]: "
                                   f"the 4 most similar, most similar first (k is 4 by default)")
'''

FILES['tests_ex_w5_day4.py'] = r'''"""Tests for plan/exercises/week5/day4.py (run by harness.py). Only the standard library is needed."""
import math

FILE = "day4.py"
WM3 = "wrestlemania/wrestlemania-03.md"
HOGAN = "people/hulk-hogan.md"
ANDRE = "people/andre-the-giant.md"
ERA = "eras/1982-1992-national-expansion-and-the-golden-era.md"
TEXT = "The WWF announced a paid attendance of 93,173 and called it a record for an indoor event."


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def close(got, want):
    return isinstance(got, (int, float)) and math.isclose(got, want, abs_tol=1e-9)


def test_rr(m):
    """reciprocal_rank is 1 divided by the rank of the first relevant path, counting from 1"""
    reciprocal_rank = need(m, "reciprocal_rank")
    for retrieved, want in (([WM3, HOGAN], 1.0), ([HOGAN, WM3], 0.5), ([HOGAN, ANDRE, WM3, WM3], 1 / 3)):
        got = reciprocal_rank(retrieved, {WM3})
        assert close(got, want), (f"with the first relevant path at rank {retrieved.index(WM3) + 1}, reciprocal_rank "
                                  f"returned {got!r}, expected {want:.4f}")


def test_rr_none(m):
    """reciprocal_rank is 0.0 when no retrieved path is relevant"""
    reciprocal_rank = need(m, "reciprocal_rank")
    for retrieved in ([HOGAN, ANDRE], []):
        got = reciprocal_rank(retrieved, {WM3})
        assert close(got, 0.0), f"with {len(retrieved)} retrieved paths and none relevant, it returned {got!r}, expected 0.0"


def test_mrr(m):
    """mrr is the mean of the runs' reciprocal ranks, and 0.0 for no runs"""
    mrr = need(m, "mrr")
    runs = [([WM3, HOGAN], {WM3}), ([HOGAN, ANDRE], {ANDRE}), ([HOGAN, ANDRE], {ERA}), ([ERA, HOGAN, WM3], {WM3, ANDRE})]
    got = mrr(runs)
    assert close(got, (1 + 0.5 + 0 + 1 / 3) / 4), (f"mrr returned {got!r}, expected 0.4583: the reciprocal ranks of "
                                                   f"the four runs are 1, 0.5, 0 and 0.3333")
    try:
        got = mrr([])
    except ZeroDivisionError:
        raise AssertionError("mrr([]) raised ZeroDivisionError; with no runs, return 0.0") from None
    assert close(got, 0.0), f"mrr([]) returned {got!r}, expected 0.0"


def test_ndcg_ideal(m):
    """ndcg_at_k is 1.0 when the relevant paths come first, even a path seen twice"""
    ndcg_at_k = need(m, "ndcg_at_k")
    got = ndcg_at_k([WM3, WM3, HOGAN, ANDRE], {WM3}, 4)
    assert close(got, 1.0), (f"for retrieved [A, A, B, C] with only A relevant, ndcg_at_k returned {got!r}, expected 1.0. "
                             f"The ideal DCG comes from your own top k relevances, sorted with the 1s first")
    got = ndcg_at_k([WM3, ANDRE, HOGAN], {WM3, ANDRE}, 3)
    assert close(got, 1.0), f"for retrieved [A, B, C] with A and B relevant, ndcg_at_k returned {got!r}, expected 1.0"


def test_ndcg_value(m):
    """ndcg_at_k follows the lesson's formula: 0.6509 for miss, hit, miss, hit"""
    got = need(m, "ndcg_at_k")([HOGAN, WM3, ANDRE, WM3], {WM3}, 4)
    want = (1 / math.log2(3) + 1 / math.log2(5)) / (1 + 1 / math.log2(3))
    assert close(got, want), (f"for retrieved [B, A, C, A] with only A relevant, ndcg_at_k returned {got!r}, expected "
                              f"{want:.4f}: DCG = 1/log2(3) + 1/log2(5), ideal DCG = 1/log2(2) + 1/log2(3)")


def test_ndcg_k(m):
    """ndcg_at_k looks only at the first k paths, and is 0.0 with no hit among them"""
    ndcg_at_k = need(m, "ndcg_at_k")
    got = ndcg_at_k([HOGAN, WM3, WM3, WM3], {WM3}, 2)
    want = 1 / math.log2(3)
    assert close(got, want), (f"for retrieved [B, A, A, A] with only A relevant and k=2, ndcg_at_k returned {got!r}, "
                              f"expected {want:.4f}. Take the first k relevances, then build the ideal from those")
    got = ndcg_at_k([HOGAN, ANDRE, WM3], {WM3}, 2)
    assert close(got, 0.0), f"with k=2 and the only hit at rank 3, ndcg_at_k returned {got!r}, expected 0.0"


def test_coverage(m):
    """keyword_coverage is the fraction of keywords found in the text, ignoring case"""
    got = need(m, "keyword_coverage")(TEXT, ["93,173", "INDOOR", "Pontiac"])
    assert close(got, 2 / 3), (f"keyword_coverage returned {got!r}, expected 0.6667: 93,173 and INDOOR are in the text "
                               f"(ignoring case), Pontiac is not. Return a fraction, not a percentage")


def test_coverage_empty(m):
    """keyword_coverage is 0.0 when there are no keywords"""
    got = need(m, "keyword_coverage")(TEXT, [])
    assert close(got, 0.0), f"keyword_coverage(text, []) returned {got!r}, expected 0.0"
'''

FILES['tests_ex_w5_day5.py'] = r'''"""Tests for plan/exercises/week5/day5.py (run by harness.py). No real model is called: the tests pass in stand-ins."""
from pydantic import BaseModel

FILE = "day5.py"
QUESTION = "When did Edge cash in his first Money in the Bank contract?"
CHUNKS = [
    {"source": "people/edge.md", "text": "He announced his retirement on Raw on 11 April 2011."},
    {"source": "match-types/money-in-the-bank.md",
     "text": "Edge won the first match against Chris Jericho, Chris Benoit, Shelton Benjamin, Kane and Christian."},
    {"source": "match-types/money-in-the-bank.md",
     "text": "He cashed in on 8 January 2006 at New Year's Revolution in Albany, New York, and beat John Cena "
             "for the WWE Championship."},
]
HISTORY = [
    {"role": "user", "content": "Who won the first Money in the Bank ladder match?"},
    {"role": "assistant", "content": "Edge won it, at WrestleMania 21."},
]
FOLLOW_UP = "When did he cash it in?"


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def chunks():
    return [dict(c) for c in CHUNKS]


def history():
    return [dict(x) for x in HISTORY]


def ids_of(got):
    return [CHUNKS.index(c) + 1 if c in CHUNKS else "?" for c in got] if isinstance(got, list) else got


def test_rank_order(m):
    """RankOrder is a pydantic model with one field, order: list[int], and its description"""
    RankOrder = need(m, "RankOrder")
    assert isinstance(RankOrder, type) and issubclass(RankOrder, BaseModel), "RankOrder must be a class built on pydantic's BaseModel"
    fields = RankOrder.model_json_schema().get("properties", {})
    assert list(fields) == ["order"], f"RankOrder has the fields {list(fields)}; expected only order"
    order = fields["order"]
    assert order.get("type") == "array" and order.get("items", {}).get("type") == "integer", "order must be a list[int]"
    assert len(str(order.get("description", ""))) >= 20, \
        "give order a Field(description=...) of 20 characters or more: the model reads it"
    assert RankOrder.model_validate_json('{"order": [2, 1, 3]}').order == [2, 1, 3], 'RankOrder did not read {"order": [2, 1, 3]}'


def test_parse_order(m):
    """parse_order turns the model's chunk ids, counted from 1, into positions counted from 0"""
    parse_order = need(m, "parse_order")
    for reply, n, want in (('{"order": [3, 1, 2]}', 3, [2, 0, 1]), ('{"order": [1, 2, 3, 4]}', 4, [0, 1, 2, 3])):
        got = parse_order(reply, n)
        assert got == want, f"parse_order({reply!r}, {n}) returned {got}, expected {want}"


def test_parse_order_repairs(m):
    """parse_order skips repeats and ids outside 1 to n, then adds the left-out ones in order"""
    reply = '{"order": [4, 2, 2, 0, 9]}'
    got = need(m, "parse_order")(reply, 4)
    assert got == [3, 1, 0, 2], (f"parse_order({reply!r}, 4) returned {got}, expected [3, 1, 0, 2]: keep ids 4 and 2 once, "
                                 f"skip 0 and 9, then add the left-out ids 1 and 3")


def test_parse_order_invalid(m):
    """parse_order raises ValueError when the reply is not RankOrder JSON"""
    parse_order = need(m, "parse_order")
    for reply in ("3, 1, 2", '{"ranking": [3, 1, 2]}', '{"order": ["first"]}'):
        try:
            got = parse_order(reply, 3)
        except ValueError:
            continue
        except Exception as e:  # noqa: BLE001 - any other error is reported to the learner
            raise AssertionError(f"parse_order({reply!r}, 3) raised {type(e).__name__}, not ValueError. "
                                 f"Read the reply with RankOrder.model_validate_json") from None
        raise AssertionError(f"parse_order({reply!r}, 3) returned {got}; expected a ValueError")


def test_rerank_prompt(m):
    """rerank calls the model once, with the question and each chunk under '# CHUNK ID: n:'"""
    seen = []

    def model(msgs):
        seen.append(msgs)
        return '{"order": [3, 2, 1]}'

    need(m, "rerank")(QUESTION, chunks(), model)
    assert len(seen) == 1, f"the model was called {len(seen)} times, expected once"
    msgs = seen[0]
    assert isinstance(msgs, list) and [x.get("role") for x in msgs] == ["system", "user"], \
        "send a system message, then one user message"
    assert len(str(msgs[0].get("content", "")).strip()) >= 20, "the system message needs instructions of 20 characters or more"
    user = str(msgs[1].get("content", ""))
    assert QUESTION in user, "the question is not in the user message"
    blocks = [f"# CHUNK ID: {i}:\n\n{c['text']}" for i, c in enumerate(CHUNKS, start=1)]
    for block in blocks:
        assert block in user, f"the user message lacks {block[:40]!r}... Write '# CHUNK ID: <id>:', a blank line, then the text"
    where = [user.index(block) for block in blocks]
    assert where == sorted(where), "the chunks must come in the order given, with ids 1, 2, 3"


def test_rerank_order(m):
    """rerank returns the chunks in the model's order and leaves the given list unchanged"""
    rerank = need(m, "rerank")
    given = chunks()
    got = rerank(QUESTION, given, lambda msgs: '{"order": [3, 1, 2]}')
    assert given == CHUNKS, "rerank changed the list it was given, or the chunks in it. Build a new list"
    assert got == [CHUNKS[2], CHUNKS[0], CHUNKS[1]], f"for the reply [3, 1, 2], rerank returned the chunks with ids {ids_of(got)}"
    got = rerank(QUESTION, chunks(), lambda msgs: '{"order": [3]}')
    assert got == [CHUNKS[2], CHUNKS[0], CHUNKS[1]], (f"for the reply [3], rerank returned the chunks with ids {ids_of(got)}, "
                                                      f"expected [3, 1, 2]. Use parse_order")


def test_rewrite_prompt(m):
    """rewrite_query calls the model once, showing each history message as 'role: content'"""
    seen = []

    def model(msgs):
        seen.append(msgs)
        return "When did Edge cash in his Money in the Bank contract?"

    need(m, "rewrite_query")(FOLLOW_UP, history(), model)
    assert len(seen) == 1, f"the model was called {len(seen)} times, expected once"
    msgs = seen[0]
    assert isinstance(msgs, list) and msgs and all(isinstance(x, dict) and isinstance(x.get("content"), str) for x in msgs), \
        "send a list of messages, each a dictionary with a role and a text content"
    text = "\n".join(x["content"] for x in msgs)
    for line in ("user: Who won the first Money in the Bank ladder match?", "assistant: Edge won it, at WrestleMania 21."):
        assert line in text, f"the messages lack {line!r}. Show each history message as role: content"
    assert FOLLOW_UP in text, "the question is not in the messages"


def test_rewrite_reply(m):
    """rewrite_query returns the reply's first non-blank line, trimmed, or else the question"""
    rewrite_query = need(m, "rewrite_query")
    reply = "\n  When did Edge cash in his Money in the Bank contract?  \nThis names Edge.\n"
    got = rewrite_query(FOLLOW_UP, history(), lambda msgs: reply)
    assert got == "When did Edge cash in his Money in the Bank contract?", \
        (f"for a three-line reply, rewrite_query returned {str(got)[:70]!r}. Keep only the reply's first line that is "
         f"not blank, without the blank space around it")
    got = rewrite_query(FOLLOW_UP, history(), lambda msgs: " \n ")
    assert got == FOLLOW_UP, f"for a blank reply, rewrite_query returned {got!r}; expected the question unchanged"
'''

FILES['tests_ex_w6_day1.py'] = r'''"""Tests for plan/exercises/week6/day1.py (run by harness.py). The products are made up and nothing is downloaded."""
import json

FILE = "day1.py"
BELT = {
    "main_category": "Toys & Games",
    "title": "Replica Heavyweight Championship Title Belt, Adult Size",
    "description": [
        "This full-size replica championship belt is made for display and for fans who want the look and weight "
        "of a real title.",
        "Five zinc alloy plates are deeply etched and plated in 24k gold, with hand-painted details and stones on "
        "the centre plate.",
        "The strap is genuine cowhide leather, 4mm thick, with three snaps\nso you can adjust the fit. It fits waists "
        "from 34 to 52 inches.",
    ],
    "features": [
        "Full-size adult replica, about 8 pounds",
        "Real leather strap with snap closure",
        "Comes with a soft carry bag and a certificate of authenticity",
        "Wipe the plates with a soft dry cloth and do not use polish",
    ],
    "details": json.dumps({
        "Brand": "Strapforge Replicas",
        "Item Weight": "8 pounds",
        "Material": "Zinc alloy, leather",
        "Best Sellers Rank": {"Toys & Games": 15204, "Replica Belts": 12},
        "Item model number": "RR-HWC-01",
        "Date First Available": "March 3, 2021",
    }),
    "price": "449.99",
    "store": "Strapforge Replicas",
}


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def scrubbed(m, *args):
    got = need(m, "scrub")(*args)
    assert isinstance(got, str), f"scrub returned {type(got).__name__}, expected a string"
    return got


def same_lines(got, want):
    got_lines, want_lines = got.split("\n"), want.split("\n")
    for i, (g, w) in enumerate(zip(got_lines, want_lines)):
        assert g == w, f"line {i + 1} is {g[:70]!r}, expected {w[:70]!r}"
    assert len(got_lines) == len(want_lines), f"scrub gave {len(got_lines)} lines, expected {len(want_lines)}"


def product(title, price):
    return {"title": title, "category": "Toys_and_Games", "price": price, "full": f"{title}, a gift for fans."}


def titles(items):
    assert isinstance(items, list), f"balanced_sample returned {type(items).__name__}, expected a list"
    return [x["title"] for x in items]


def test_scrub_lines(m):
    """scrub writes title, description, features and details as lines, leaving out empty ones"""
    got = scrubbed(m, "Replica Title Belt", ["Five zinc plates,\nplated in gold.", "Real leather  strap."],
                   ["Adult size", "Snap closure"], {"Brand": "Strapforge Replicas", "Item Weight": "8 pounds"})
    same_lines(got, 'Replica Title Belt\nFive zinc plates, plated in gold. Real leather strap.\nAdult size Snap closure\n'
                    '{"Brand": "Strapforge Replicas", "Item Weight": "8 pounds"}')
    got = scrubbed(m, "USB-C Cable", ["Braided nylon cable."], [], {"Part Number": "CB-100"})
    assert got == "USB-C Cable\nBraided nylon cable.", \
        f"with no features and no details left, scrub returned {got!r}, expected 'USB-C Cable\\nBraided nylon cable.'"


def test_scrub_removals(m):
    """scrub drops the five REMOVALS details without editing the dict it was given"""
    details = {"Brand": "Strapforge Replicas", "Part Number": "RR-HWC-01", "Best Sellers Rank": {"Toys & Games": 15204},
               "Batteries Included?": "No", "Batteries Required?": "No", "Item model number": "RR-HWC-01",
               "Material": "Zinc alloy"}
    before = json.loads(json.dumps(details))
    got = scrubbed(m, "Replica Title Belt", ["A display piece."], [], details)
    assert details == before, "scrub changed the details dict it was given; build a new dict instead of popping keys"
    want = json.dumps({"Brand": "Strapforge Replicas", "Material": "Zinc alloy"})
    last = got.split("\n")[-1]
    assert last == want, f"the details line is {last[:100]!r}, expected {want!r}"


def test_scrub_part_numbers(m):
    """scrub removes part numbers but keeps capital words, plain numbers and short codes"""
    got = scrubbed(m, "Replica Title Belt WB7710X", ["Ships in a WATERPROOF case."],
                   ["Strap code RB2024 is rated for 1500000 flexes."], {"ASIN": "B07XJ8C8F5", "Brand": "Strapforge Replicas"})
    for word in ("WB7710X", "B07XJ8C8F5"):
        assert word not in got, f"{word!r} is a part number (7 or more capitals and digits, with both), so remove it"
    for word, why in (("WATERPROOF", "it has no digit"), ("1500000", "it has no capital letter"),
                      ("RB2024", "it is shorter than 7 characters")):
        assert word in got, f"{word!r} should stay because {why}"


def test_scrub_limits(m):
    """scrub cuts description and features to 3,000 characters each and the whole text to 4,000"""
    got = scrubbed(m, "Belt", ["x" * 5000], ["y" * 5000], {})
    lines = got.split("\n")
    size = len(lines[1]) if len(lines) > 1 else 0
    assert size == 3000 and lines[1] == "x" * 3000, f"the description line has {size} characters, expected 3000"
    assert len(got) == 4000, f"scrub returned {len(got)} characters, expected 4000"


def test_parse_price_range(m):
    """parse keeps prices from 0.5 to 999.49 and returns None outside them or for non-numbers"""
    parse = need(m, "parse")
    for price in ("0.5", "449.99", "999.49"):
        got = parse(dict(BELT, price=price), "Toys_and_Games")
        assert isinstance(got, dict), f"parse returned {got!r} for the price {price!r}; prices from 0.5 to 999.49 are kept"
    for price in ("0.49", "999.5", "1500.00", "None", ""):
        got = parse(dict(BELT, price=price), "Toys_and_Games")
        assert got is None, f"parse kept the price {price!r}; expected None (only numbers from 0.5 to 999.49 are kept)"


def test_parse_item(m):
    """parse returns title, category, price and scrubbed full text, or None under 600 characters"""
    parse, scrub = need(m, "parse"), need(m, "scrub")
    got = parse(BELT, "Toys_and_Games")
    assert isinstance(got, dict), f"parse returned {type(got).__name__} for a good product, expected a dict"
    assert got.get("title") == BELT["title"], "the title must be the product's title, unchanged"
    assert got.get("category") == "Toys_and_Games", f"category is {got.get('category')!r}, expected the one you were given"
    price = got.get("price")
    assert isinstance(price, float) and price == 449.99, f"price is {price!r}, expected the float 449.99"
    want = scrub(BELT["title"], BELT["description"], BELT["features"], json.loads(BELT["details"]))
    assert got.get("full") == want, "full must be scrub(title, description, features, details), with details read from JSON"
    short = {"title": "Belt", "description": ["a" * 595], "features": [], "details": "{}", "price": "25.00"}
    assert parse(short, "Toys_and_Games") is not None, "a text of exactly 600 characters is long enough (MIN_CHARS is 600)"
    short["description"] = ["a" * 594]
    assert parse(short, "Toys_and_Games") is None, "a text of 599 characters is too short; expected None"


def test_balanced_first_per_band(m):
    """balanced_sample keeps the first per_band items of each $100 band, in their original order"""
    items = [product("Stickers", 4.99), product("Title belt", 449.99), product("Foam finger", 12.0),
             product("Figure", 24.5), product("Photo", 129.0), product("Bell", 89.0), product("Pads", 149.0),
             product("Kids belt", 64.0), product("Ring mat", 899.0)]
    got = titles(need(m, "balanced_sample")(items, 2))
    want = ["Stickers", "Title belt", "Foam finger", "Photo", "Pads", "Ring mat"]
    assert got == want, f"with per_band=2 it kept {got}, expected {want}"


def test_balanced_bands(m):
    """balanced_sample uses price // band_width as the band and leaves your list unchanged"""
    sample = need(m, "balanced_sample")
    items = [product("A", 99.99), product("B", 100.0), product("C", 0.5), product("D", 199.99)]
    before = [dict(x) for x in items]
    got = titles(sample(items, 1))
    assert got == ["A", "B"], f"with per_band=1 it kept {got}, expected ['A', 'B']: $99.99 is band 0, $100 starts band 1"
    assert items == before, "balanced_sample changed the list it was given"
    got = titles(sample([product("A", 49.99), product("B", 50.0), product("C", 99.99), product("D", 10.0)], 1, band_width=50))
    assert got == ["A", "B"], f"with band_width=50 it kept {got}, expected ['A', 'B']: $50 and $99.99 are both band 1"
'''

FILES['tests_ex_w6_day2.py'] = r'''"""Tests for plan/exercises/week6/day2.py (run by harness.py). No batch is sent: the results file is made up here."""
import json
from types import SimpleNamespace

FILE = "day2.py"
FULL = ('Replica Heavyweight Championship Title Belt, Adult Size\n'
        'Full-size replica belt with five zinc plates, plated in 24k gold. Real leather strap.\n'
        'Adult size Snap closure\n{"Brand": "Strapforge Replicas", "Item Weight": "8 pounds"}')
BELT = ("Title: Replica Heavyweight Championship Title Belt\nCategory: Collectibles\nBrand: Strapforge Replicas\n"
        "Description: A full-size replica title belt with five gold-plated zinc plates on a real leather strap.\n"
        "Details: Weighs about 8 pounds, fits waists from 34 to 52 inches and comes with a carry bag.")
FINGER = ("Title: Giant Foam Finger\nCategory: Toys and Games\nBrand: Fanhand\n"
          "Description: An oversized foam hand for cheering at live events.\n"
          "Details: Lightweight foam, 18 inches tall, printed on both sides.")


def ok_line(i, content):
    body = {"id": f"chatcmpl-0{i}", "object": "chat.completion", "model": "openai/gpt-oss-20b",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 212, "completion_tokens": 64, "total_tokens": 276}}
    return json.dumps({"id": f"batch_req_0{i}", "custom_id": str(i),
                       "response": {"status_code": 200, "request_id": f"req_0{i}", "body": body}, "error": None})


EXPIRED = json.dumps({"id": "batch_req_01", "custom_id": "1", "response": None,
                      "error": {"code": "batch_expired", "message": "This request could not be executed in time."}})
SERVER_ERROR = json.dumps({"id": "batch_req_02", "custom_id": "2", "error": None,
                           "response": {"status_code": 500, "request_id": "req_02",
                                        "body": {"error": {"message": "Internal server error"}}}})


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def item(i, full=FULL):
    return SimpleNamespace(id=i, full=full, summary=None)


def read(m, text):
    try:
        got = need(m, "read_results")(text)
    except ValueError as e:
        raise AssertionError(f"read_results could not read a line ({e}); skip blank lines") from None
    except (TypeError, KeyError) as e:
        raise AssertionError(f"read_results crashed ({type(e).__name__}: {e}); a failed request must give None") from None
    assert isinstance(got, dict), f"read_results returned {type(got).__name__}, expected a dict"
    return got


def test_request_line(m):
    """make_jsonl builds the lesson's batch request: custom_id, method, url and body"""
    line = need(m, "make_jsonl")(item(7), "test-model", "Rewrite this product.")
    assert isinstance(line, str), f"make_jsonl returned {type(line).__name__}, expected one line of JSON text"
    try:
        got = json.loads(line)
    except ValueError:
        raise AssertionError("json.loads could not read the line; make_jsonl must return the request as JSON text") from None
    assert got.get("custom_id") == "7", f"custom_id is {got.get('custom_id')!r}, expected the text '7' (the batch API wants text)"
    assert got.get("method") == "POST" and got.get("url") == "/v1/chat/completions", \
        "method must be 'POST' and url must be '/v1/chat/completions'"
    assert sorted(got) == ["body", "custom_id", "method", "url"], f"the line has the keys {sorted(got)}, expected body, custom_id, method, url"
    body = got["body"]
    assert isinstance(body, dict) and sorted(body) == ["messages", "model", "reasoning_effort"], \
        "the body must hold exactly model, messages and reasoning_effort"
    assert body["model"] == "test-model", f"the body's model is {body['model']!r}, expected the model you were given"
    assert body["messages"] == [{"role": "system", "content": "Rewrite this product."}, {"role": "user", "content": FULL}], \
        "messages must be the system prompt you were given, then the item's full text as the user message"
    assert body["reasoning_effort"] == "low", f"reasoning_effort is {body['reasoning_effort']!r}, expected 'low' as in the lesson"


def test_one_line(m):
    """make_jsonl stays on one line even when the text has new lines and quotes"""
    product = item(12, 'Title belt\n"Gold" plates\nWaist: 52"')
    line = need(m, "make_jsonl")(product, "test-model", "Rewrite.")
    assert not line.endswith("\n"), "make_jsonl added a new line at the end; leave that to make_file"
    assert "\n" not in line, "the line has a new line inside it; write it with json.dumps and no indent, which escapes them"
    assert json.loads(line)["body"]["messages"][1]["content"] == product.full, "the user message must be item.full, unchanged"


def test_file_text(m):
    """make_file writes one make_jsonl line per item, in order, each ending with a new line"""
    make_file, make_jsonl = need(m, "make_file"), need(m, "make_jsonl")
    items = [item(3, "Foam finger\nBlue"), item(1, "Title belt"), item(2, "Ring bell")]
    text = make_file(items, "test-model", "Rewrite.")
    assert isinstance(text, str), f"make_file returned {type(text).__name__}, expected the text of the file"
    assert text.endswith("\n"), "the file text must end with a new line: the lesson writes one after every line"
    lines = text.split("\n")[:-1]
    assert len(lines) == 3, f"the file has {len(lines)} lines, expected 3, one per item"
    ids = [json.loads(x).get("custom_id") for x in lines]
    assert ids == ["3", "1", "2"], f"the custom_ids are {ids}, expected ['3', '1', '2'], the order of the items"
    assert lines == [make_jsonl(x, "test-model", "Rewrite.") for x in items], \
        "each line must be make_jsonl(item, model, system_prompt) for that item"
    assert make_file([], "test-model", "Rewrite.") == "", "with no items, make_file must return an empty text"


def test_read_results(m):
    """read_results maps each item id, as an int, to its reply text"""
    got = read(m, ok_line(0, BELT) + "\n" + ok_line(3, FINGER))
    assert "0" not in got, "the keys are text; turn custom_id back into an int, as the lesson does"
    assert sorted(got) == [0, 3], f"the ids are {sorted(got)}, expected [0, 3]"
    assert got[0] == BELT, f"id 0 gave {got[0]!r:.80}, expected the content of its reply message"
    assert got[3] == FINGER, f"id 3 gave {got[3]!r:.80}, expected the content of its reply message"


def test_read_failures(m):
    """read_results gives None for a request that failed"""
    got = read(m, "\n".join([ok_line(0, BELT), EXPIRED, SERVER_ERROR, ok_line(3, FINGER)]))
    assert sorted(got) == [0, 1, 2, 3], f"the ids are {sorted(got)}, expected [0, 1, 2, 3]: failed requests stay in, as None"
    assert got[1] is None, f"id 1 has an error and a null response, so it must give None, not {got[1]!r:.60}"
    assert got[2] is None, f"id 2 came back with status_code 500, so it must give None, not {got[2]!r:.60}"
    assert got[0] == BELT and got[3] == FINGER, "the failed lines must not change the results of the good ones"


def test_read_blank_lines(m):
    """read_results skips blank lines, including the one after the last new line"""
    got = read(m, ok_line(0, BELT) + "\n\n" + EXPIRED + "\n" + ok_line(3, FINGER) + "\n")
    assert sorted(got) == [0, 1, 3], f"the ids are {sorted(got)}, expected [0, 1, 3]"


def test_apply_results(m):
    """apply_results sets the summaries it has and returns the ids still without one"""
    items = [item(i, f"Product {i}") for i in range(5)]
    items[4].summary = "Title: An older summary"
    try:
        got = need(m, "apply_results")(items, {0: BELT, 1: None, 3: FINGER, 4: None, 9: "Title: Not one of ours"})
    except (IndexError, KeyError) as e:
        raise AssertionError(f"apply_results crashed ({type(e).__name__}: {e}); ignore result ids such as 9 that match no item") from None
    assert items[0].summary == BELT and items[3].summary == FINGER, "items 0 and 3 must get their summaries from the results"
    assert items[1].summary is None, f"item 1 failed, so its summary must stay None, not {items[1].summary!r:.40}"
    assert items[4].summary == "Title: An older summary", "a None result must not wipe out the summary item 4 already had"
    assert got == [1, 2], f"apply_results returned {got!r}, expected [1, 2]: the ids still without a summary, in item order"
'''

FILES['tests_ex_w6_day3.py'] = r'''"""Tests for plan/exercises/week6/day3.py (run by harness.py). The pricers are stand-ins with fixed guesses."""
import math
from types import SimpleNamespace

FILE = "day3.py"
TEST = [SimpleNamespace(title="Replica title belt", price=450.0), SimpleNamespace(title="Foam finger", price=12.0),
        SimpleNamespace(title="Ring bell", price=89.99), SimpleNamespace(title="Practice ring mat", price=899.0)]
GUESSES = {"Replica title belt": 430, "Foam finger": 70.0, "Ring bell": 180.0, "Practice ring mat": 700.0}


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def near(a, b):
    return isinstance(a, (int, float)) and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def scored(m, predictor, items, **size):
    got = need(m, "evaluate")(predictor, items, **size)
    assert isinstance(got, dict), f"evaluate returned {type(got).__name__}, expected a dict"
    assert sorted(got) == ["average_error", "colors", "count", "mse", "r2"], \
        f"the keys are {sorted(got)}, expected average_error, colors, count, mse and r2"
    return got


def check_colors(m, cases):
    color_for = need(m, "color_for")
    for error, truth, want, why in cases:
        got = color_for(error, truth)
        assert got == want, f"color_for({error}, {truth}) gave {got!r}, expected {want!r}: {why}"


def test_color_dollars(m):
    """color_for gives green under $40 off, orange under $80, and red from $80 up"""
    check_colors(m, [(39.99, 100.0, "green", "39.99 is under 40"),
                     (40, 100.0, "orange", "40 is not under 40, and 40% of the price is not under 20%"),
                     (79.99, 100.0, "orange", "79.99 is under 80"),
                     (80, 100.0, "red", "80 is not under 80, and 80% of the price is not under 40%")])


def test_color_share(m):
    """color_for also gives green under 20% of the price and orange under 40%"""
    check_colors(m, [(99, 500.0, "green", "99 is under 20% of 500"),
                     (100, 500.0, "orange", "100 is exactly 20% of 500, not under it"),
                     (199, 500.0, "orange", "199 is under 40% of 500"),
                     (200, 500.0, "red", "200 is exactly 40% of 500, not under it")])


def test_r_squared(m):
    """r_squared is 1 for perfect guesses, 0 for guessing the mean, and can go below 0"""
    r_squared = need(m, "r_squared")
    truths = [100.0, 200.0, 300.0]
    for guesses, want in (([100.0, 200.0, 300.0], 1.0), ([200.0, 200.0, 200.0], 0.0),
                          ([110.0, 190.0, 330.0], 0.945), ([300.0, 200.0, 100.0], -3.0)):
        got = r_squared(truths, guesses)
        assert near(got, want), f"r_squared({truths}, {guesses}) gave {got!r}, expected {want}"


def test_evaluate_summary(m):
    """evaluate returns count, average_error, mse, r2 and colors for the predictor's guesses"""
    seen = []

    def predictor(item):
        seen.append(item.title)
        return GUESSES[item.title]

    got = scored(m, predictor, TEST)
    assert seen == [x.title for x in TEST], f"the predictor was called for {seen}, expected each item once, in order"
    assert got["count"] == 4, f"count is {got['count']!r}, expected 4"
    assert near(got["average_error"], 91.7525), f"average_error is {got['average_error']!r}, expected 91.7525 (errors 20, 58, 90.01, 199)"
    assert near(got["mse"], 12866.700025), f"mse is {got['mse']!r}, expected 12866.700025, the mean of the squared errors"
    truths, guesses = [x.price for x in TEST], [float(GUESSES[x.title]) for x in TEST]
    want = need(m, "r_squared")(truths, guesses)
    assert near(got["r2"], want), f"r2 is {got['r2']!r}, expected r_squared(prices, guesses) = {want!r}"
    assert got["colors"] == {"green": 1, "orange": 2, "red": 1}, \
        f"colors is {got['colors']!r}, expected {{'green': 1, 'orange': 2, 'red': 1}}"


def test_evaluate_size(m):
    """evaluate scores only the first size items and always reports all three colours"""
    seen = []
    items = [SimpleNamespace(title=f"Item {i}", price=100.0 + i * 50) for i in range(5)]
    got = scored(m, lambda item: seen.append(item.title) or item.price + 1, items, size=3)
    assert seen == ["Item 0", "Item 1", "Item 2"], f"the predictor was called for {seen}, expected the first 3 items only"
    assert got["count"] == 3, f"count is {got['count']!r}, expected 3"
    assert got["colors"] == {"green": 3, "orange": 0, "red": 0}, \
        f"colors is {got['colors']!r}, expected {{'green': 3, 'orange': 0, 'red': 0}}: keep a colour at 0 when none match"
    seen.clear()
    assert scored(m, lambda item: seen.append(item.title) or 1.0, items)["count"] == 5, \
        "with the default size of 200 and only 5 items, evaluate must score all 5"


def test_constant_pricer(m):
    """make_constant_pricer returns a pricer that always guesses the average training price"""
    train = [SimpleNamespace(title="Stickers", price=10.0), SimpleNamespace(title="Foam finger", price=20.0),
             SimpleNamespace(title="Kids title belt", price=60.0)]
    pricer = need(m, "make_constant_pricer")(train)
    assert callable(pricer), f"make_constant_pricer returned {type(pricer).__name__}, expected a function"
    try:
        guesses = [pricer(SimpleNamespace(title="Mystery box")), pricer(TEST[0])]
    except AttributeError:
        raise AssertionError("the pricer read the item it was pricing; it must ignore the item") from None
    assert all(near(g, 30.0) for g in guesses), f"the pricer guessed {guesses}, expected 30.0 each time (the average of 10, 20, 60)"


def test_constant_r2(m):
    """The constant pricer scores an r2 of 0 on the prices it was built from"""
    train = [SimpleNamespace(title=f"Item {i}", price=p) for i, p in enumerate([4.99, 12.0, 89.99, 450.0, 899.0])]
    got = scored(m, need(m, "make_constant_pricer")(train), train)
    assert near(got["r2"], 0.0), f"r2 is {got['r2']!r}, expected 0: always guessing the mean of the prices scores exactly 0"
'''

FILES['tests_ex_w6_day4.py'] = r'''"""Tests for plan/exercises/week6/day4.py (run by harness.py). No real model is called: the models are stand-ins."""
import math
from types import SimpleNamespace

FILE = "day4.py"
INSTRUCTION = "Estimate the price of this product. Respond with the price, no explanation"
BELT = SimpleNamespace(title="Replica Heavyweight Championship Title Belt", price=449.99, summary=(
    "Title: Replica Heavyweight Championship Title Belt\nCategory: Collectibles\nBrand: Strapforge Replicas\n"
    "Description: A full-size replica title belt with five gold-plated zinc plates on a real leather strap.\n"
    "Details: Weighs about 8 pounds, fits waists from 34 to 52 inches and comes with a carry bag."))
FINGER = SimpleNamespace(title="Giant Foam Finger", price=12.0, summary=(
    "Title: Giant Foam Finger\nCategory: Toys and Games\nBrand: Fanhand\n"
    "Description: An oversized foam hand for cheering at live events.\n"
    "Details: Lightweight foam, 18 inches tall, printed on both sides."))
BELL = SimpleNamespace(title="Brass Ring Bell", price=89.99, summary=(
    "Title: Brass Ring Bell with Wooden Base\nCategory: Sports Equipment\nBrand: Clangmore\n"
    "Description: A loud brass bell for boxing and wrestling events.\n"
    "Details: Polished brass, 6 inch bell, mounted on a hardwood base with a striker."))
ITEMS = [BELT, FINGER, BELL]


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def check_prices(m, cases):
    get_price = need(m, "get_price")
    for text, want in cases:
        got = get_price(text)
        assert isinstance(got, (int, float)) and math.isclose(got, want), f"get_price({text!r}) gave {got!r}, expected {want}"


def stand_in(reply_for):
    """A fake model: finds the item by the summary at the end of the user message and replies with reply_for(item)."""
    calls = []

    def model(messages):
        calls.append(messages)
        text = messages[-1]["content"]
        found = [x for x in ITEMS if text.endswith(x.summary)]
        assert found, "the model got a last message that does not end with an item's summary; send messages_for(item)"
        return reply_for(found[0])

    return model, calls


def test_messages_for(m):
    """messages_for sends one user message: the lesson's instruction, a blank line, the summary"""
    got = need(m, "messages_for")(BELT)
    assert isinstance(got, list) and len(got) == 1, "messages_for must return a list with one message, as the lesson does"
    assert got[0].get("role") == "user", f"the message's role is {got[0].get('role')!r}, expected 'user' (no system message)"
    want = f"{INSTRUCTION}\n\n{BELT.summary}"
    content = got[0].get("content")
    assert content == want, f"the content starts {str(content)[:90]!r}, expected the lesson's instruction, a blank line, then the summary"


def test_get_price_formats(m):
    """get_price drops $ and commas and reads a number with its decimals"""
    check_prices(m, [("$1,299.99", 1299.99), ("Price is $45.", 45.0), ("$129.99 (was $159.99)", 129.99),
                     ("about 99.5 dollars", 99.5), ("$2,450", 2450.0)])


def test_get_price_first_number(m):
    """get_price takes the first number, even a wrong one, and gives 0.0 when there is none"""
    check_prices(m, [("Between $20 and $30", 20.0), ("4 pack for $12", 4.0),
                     ("I cannot tell from this description.", 0.0), ("", 0.0)])


def test_make_pricer(m):
    """make_pricer's pricer sends messages_for(item) once and returns get_price of the reply"""
    model, calls = stand_in(lambda item: "I would say $1,299.99 for this one.")
    pricer = need(m, "make_pricer")(model)
    assert callable(pricer), f"make_pricer returned {type(pricer).__name__}, expected a function"
    assert calls == [], "make_pricer called the model already; only the pricer should call it"
    got = pricer(BELT)
    assert len(calls) == 1, f"the model was called {len(calls)} times for one item, expected once"
    assert calls[0] == need(m, "messages_for")(BELT), "the model did not get messages_for(item)"
    want = need(m, "get_price")("I would say $1,299.99 for this one.")
    assert got == want, f"the pricer returned {got!r}, expected get_price of the reply, {want!r}"


def test_compare(m):
    """compare ranks the models by average error, best first, pricing every item once"""
    replies = {"silent": lambda item: "I can't tell.", "chatty": lambda item: "Sure! For 1 item I'd say $50",
               "exact": lambda item: f"${item.price:,.2f}", "fifty": lambda item: "$50"}
    models, calls = {}, {}
    for name, reply_for in replies.items():
        models[name], calls[name] = stand_in(reply_for)
    got = need(m, "compare")(models, ITEMS)
    assert isinstance(got, list) and all(isinstance(x, tuple) and len(x) == 2 for x in got), \
        "compare must return a list of (name, average_error) tuples"
    get_price = need(m, "get_price")
    scores = {name: sum(abs(get_price(reply_for(x)) - x.price) for x in ITEMS) / len(ITEMS)
              for name, reply_for in replies.items()}
    want = sorted(replies, key=scores.get)
    names = [name for name, _ in got]
    assert names == want, f"the order is {names}, expected {want}, lowest average error first"
    for name, error in got:
        assert math.isclose(error, scores[name], abs_tol=1e-9), f"{name} scored {error!r}, expected its average error {scores[name]!r}"
    for name, made in calls.items():
        assert len(made) == 3, f"the {name} model was called {len(made)} times, expected once for each of the 3 items"


def test_compare_ties(m):
    """compare keeps the order of models that have the same error"""
    first, _ = stand_in(lambda item: "$100")
    second, _ = stand_in(lambda item: "Roughly $100")
    got = need(m, "compare")({"zebra": first, "aardvark": second}, ITEMS)
    names = [name for name, _ in got]
    assert names == ["zebra", "aardvark"], f"the order is {names}, expected ['zebra', 'aardvark']: a tie keeps the dict's order"
'''

FILES['tests_ex_w6_day5.py'] = r'''"""Tests for plan/exercises/week6/day5.py (run by harness.py). Nothing is uploaded: the tests only read the text."""
import json
from types import SimpleNamespace

FILE = "day5.py"
INSTRUCTION = "Estimate the price of this product. Respond with the price, no explanation"
BELT = SimpleNamespace(title="Replica Heavyweight Championship Title Belt", price=449.99, summary=(
    "Title: Replica Heavyweight Championship Title Belt\nCategory: Collectibles\nBrand: Strapforge Replicas\n"
    "Description: A full-size replica title belt with five gold-plated zinc plates on a real leather strap.\n"
    "Details: Weighs about 8 pounds, fits waists from 34 to 52 inches and comes with a carry bag."))
FINGER = SimpleNamespace(title="Giant Foam Finger", price=12.0, summary=(
    "Title: Giant Foam Finger\nCategory: Toys and Games\nBrand: Fanhand\n"
    "Description: An oversized foam hand for cheering at live events.\nDetails: Lightweight foam, 18 inches tall."))
BELL = SimpleNamespace(title="Brass Ring Bell", price=89.99, summary=(
    "Title: Brass Ring Bell with Wooden Base\nCategory: Sports Equipment\nBrand: Clangmore\n"
    "Description: A loud brass bell for boxing and wrestling events.\nDetails: Polished brass on a hardwood base."))
ITEMS = [BELT, FINGER, BELL]


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def numbered(count):
    return [SimpleNamespace(title=f"Item {i}", price=float(i + 1), summary=f"Title: Item {i}") for i in range(count)]


def test_messages_for(m):
    """messages_for gives the lesson's user prompt, then the price as the assistant's answer"""
    got = need(m, "messages_for")(BELT)
    assert isinstance(got, list), f"messages_for returned {type(got).__name__}, expected a list of messages"
    roles = [x.get("role") for x in got]
    assert roles == ["user", "assistant"], f"the roles are {roles}, expected ['user', 'assistant'] (the lesson has no system message)"
    content = got[0].get("content")
    assert content == f"{INSTRUCTION}\n\n{BELT.summary}", \
        f"the user message starts {str(content)[:90]!r}, expected the lesson's instruction, a blank line, then the summary"
    assert got[1].get("content") == "$449.99", f"the assistant says {got[1].get('content')!r}, expected '$449.99'"


def test_price_format(m):
    """The assistant writes the price with a $ and two decimals, like $1234.50"""
    messages_for = need(m, "messages_for")
    for price, want in ((12.0, "$12.00"), (1234.5, "$1234.50"), (9.999, "$10.00"), (25, "$25.00")):
        got = messages_for(SimpleNamespace(title="Item", price=price, summary="Title: Item"))[-1].get("content")
        assert got == want, f"for a price of {price} the assistant says {got!r}, expected {want!r}"


def test_inference_prompt(m):
    """test_messages_for is messages_for without the assistant's answer"""
    got = need(m, "test_messages_for")(BELT)
    assert isinstance(got, list), f"test_messages_for returned {type(got).__name__}, expected a list of messages"
    want = need(m, "messages_for")(BELT)[:1]
    assert got == want, "test_messages_for must give exactly the user message of messages_for(item), and nothing else"


def test_jsonl_lines(m):
    """make_jsonl writes one line per item, each a JSON object with the item's messages"""
    text = need(m, "make_jsonl")(ITEMS)
    assert isinstance(text, str), f"make_jsonl returned {type(text).__name__}, expected the text of the file"
    lines = text.removesuffix("\n").split("\n")
    assert len(lines) == 3, f"the text has {len(lines)} lines, expected 3, one per item"
    for i, (line, product) in enumerate(zip(lines, ITEMS)):
        try:
            got = json.loads(line)
        except ValueError:
            raise AssertionError(f"line {i + 1} is not one JSON object; write each line with json.dumps") from None
        assert got == {"messages": need(m, "messages_for")(product)}, \
            f"line {i + 1} must be the object {{\"messages\": messages_for(item)}} for item {i + 1}"


def test_jsonl_ends(m):
    """make_jsonl puts new lines only between lines, none at the end, as the lesson does"""
    make_jsonl = need(m, "make_jsonl")
    text = make_jsonl(ITEMS)
    assert not text.endswith("\n"), "the text ends with a new line; the lesson strips the last one"
    assert text.count("\n") == 2, \
        f"the text has {text.count(chr(10))} new lines, expected 2: the summaries' own new lines must be escaped by json.dumps"
    assert make_jsonl([]) == "", "with no items, make_jsonl must return an empty text"


def test_split(m):
    """split takes the first train_size items for training and the next val_size for validation"""
    split = need(m, "split")
    items = numbered(200)
    before = list(items)
    got = split(items)
    assert isinstance(got, tuple) and len(got) == 2, "split must return a tuple of two lists: (train, validation)"
    train, validation = got
    assert isinstance(train, list) and isinstance(validation, list), "train and validation must both be lists"
    assert train == items[:100], f"train has {len(train)} items, expected the first 100 (the lesson's size)"
    assert validation == items[100:150], f"validation has {len(validation)} items, expected the next 50, items 100 to 149"
    assert items == before, "split changed the list it was given"
    train, validation = split(numbered(10), 6, 3)
    assert [x.title for x in train] == [f"Item {i}" for i in range(6)], "split(items, 6, 3) must train on items 0 to 5"
    assert [x.title for x in validation] == ["Item 6", "Item 7", "Item 8"], "split(items, 6, 3) must validate on items 6 to 8"


def test_split_too_few(m):
    """split raises ValueError when there are too few items, and accepts exactly enough"""
    split = need(m, "split")
    for count, sizes in ((140, ()), (8, (6, 3))):
        try:
            split(numbered(count), *sizes)
        except ValueError:
            continue
        need_count = sum(sizes) if sizes else 150
        raise AssertionError(f"split with {count} items must raise ValueError, because it needs {need_count}")
    train, validation = split(numbered(9), 6, 3)
    assert len(train) == 6 and len(validation) == 3, "split with exactly 9 items for sizes 6 and 3 must work"
'''

FILES['tests_ex_w7_day1.py'] = r'''"""Tests for plan/exercises/week7/day1.py (run by harness.py). Plain arithmetic: no model is loaded."""
import math

FILE = "day1.py"
SHAPES = {"q_proj": (12, 12), "k_proj": (12, 4), "v_proj": (12, 4), "o_proj": (12, 12),
          "gate_proj": (12, 32), "up_proj": (12, 32), "down_proj": (32, 12)}
ATTENTION = ["q_proj", "k_proj", "v_proj", "o_proj"]


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def expect_value_error(fn, args, call):
    """Passes when fn(*args) raises ValueError; otherwise fails with a message naming the call."""
    try:
        got = fn(*args)
    except ValueError as e:
        return e
    except Exception as e:  # noqa: BLE001 - the learner should raise ValueError, not something else
        raise AssertionError(f"{call} raised {type(e).__name__}, expected ValueError") from None
    raise AssertionError(f"{call} returned {got!r}, expected it to raise ValueError")


def test_lora_params(m):
    """lora_params returns r * (d_in + d_out), also when d_out differs from d_in"""
    f = need(m, "lora_params")
    for args, want in (((3072, 3072, 32), 196_608), ((3072, 1024, 32), 131_072), ((4, 2, 1), 6)):
        got = f(*args)
        assert got == want, f"lora_params{args} returned {got!r}, expected {want}: r * (d_in + d_out)"


def test_lora_params_rank(m):
    """lora_params raises ValueError when r is below 1"""
    for r in (0, -4):
        expect_value_error(need(m, "lora_params"), (12, 4, r), f"lora_params(12, 4, {r})")


def test_total(m):
    """lora_total sums the targeted modules, then multiplies by the number of layers"""
    got = need(m, "lora_total")(SHAPES, list(SHAPES), 2, 3)
    assert got == 1272, (f"lora_total with all 7 modules targeted, r=2 and 3 layers returned {got!r}, "
                         f"expected 1272: the 7 modules add 424 per layer, times 3 layers")


def test_total_targets_only(m):
    """lora_total counts only the modules named in targets"""
    got = need(m, "lora_total")(SHAPES, ATTENTION, 2, 3)
    assert got == 480, (f"lora_total with only the 4 attention modules targeted, r=2 and 3 layers returned {got!r}, "
                        f"expected 480: leave out the 3 modules that are not in targets")


def test_total_once(m):
    """lora_total counts a module once even when targets lists it twice"""
    got = need(m, "lora_total")(SHAPES, ["q_proj", "v_proj", "q_proj"], 1, 1)
    assert got == 40, (f"lora_total with targets ['q_proj', 'v_proj', 'q_proj'], r=1 and 1 layer returned {got!r}, "
                       f"expected 40: q_proj (24) once plus v_proj (16)")


def test_total_unknown(m):
    """lora_total raises ValueError naming a target that is not in shapes"""
    e = expect_value_error(need(m, "lora_total"), (SHAPES, ["q_proj", "qkv_proj"], 2, 3),
                           "lora_total with the target 'qkv_proj', which is not in shapes,")
    assert "qkv_proj" in str(e), f"the ValueError says {str(e)!r}, expected it to name qkv_proj"


def test_scale(m):
    """lora_scale returns alpha / r as a float and raises ValueError when r is below 1"""
    f = need(m, "lora_scale")
    for alpha, r, want in ((64, 32, 2.0), (16, 32, 0.5), (8, 8, 1.0)):
        got = f(alpha, r)
        assert isinstance(got, float) and got == want, \
            f"lora_scale({alpha}, {r}) returned {got!r}, expected the float {want}: alpha / r, not alpha // r"
    expect_value_error(f, (16, 0), "lora_scale(16, 0)")


def test_percent(m):
    """trainable_percent divides by all the parameters: the base ones plus the trained ones"""
    f = need(m, "trainable_percent")
    for base, trained in ((900, 100), (3_212_749_824, 18_350_080)):
        got = f(base, trained)
        want = 100 * trained / (base + trained)
        assert isinstance(got, (int, float)) and math.isclose(got, want, rel_tol=1e-9), \
            f"trainable_percent({base}, {trained}) returned {got!r}, expected {want:.6g}: 100 * {trained} / ({base} + {trained})"
'''

FILES['tests_ex_w7_day2.py'] = r'''"""Tests for plan/exercises/week7/day2.py (run by harness.py). No tokenizer is downloaded: the tests pass in a stand-in."""
import re

FILE = "day2.py"
QUESTION = "What does this cost to the nearest dollar?"
FIRST_LINE = "Title: Cordless Electric Kettle, 1.7 Litre"
SUMMARY = (FIRST_LINE + "\n"
           "Category: Appliances\n"
           "Brand: Generic\n"
           "Description: A stainless steel kettle that boils water quickly and switches itself off.\n"
           "Details: 1500 watt element, water window and a removable filter.")  # 66 stand-in tokens
LONG = SUMMARY + "\nNotes: " + "Fits most kitchen counters and cupboards. " * 12  # 190 stand-in tokens
PIECE = re.compile(r"\n| ?\S{1,4}| +|\s")


class StandIn:
    """A stand-in tokenizer. A token is a new line, a run of spaces, or 1 to 4 other characters with
    at most one space before them. encode gives a list of numbers and decode turns them back into text."""

    def __init__(self):
        self.pieces, self.ids = [], {}

    def encode(self, text):
        assert isinstance(text, str), f"encode was given {type(text).__name__}, expected a string"
        out = []
        for piece in PIECE.findall(text):
            if piece not in self.ids:
                self.ids[piece] = len(self.pieces)
                self.pieces.append(piece)
            out.append(self.ids[piece])
        return out

    def decode(self, ids):
        return "".join(self.pieces[i] for i in ids)


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def short(value, size=44):
    """The repr of a value, cut down so that a message stays readable."""
    text = repr(value)
    return text if len(text) <= size else text[:size - 3] + "..."


def where(got, want):
    """Where two texts first differ, in a few words."""
    if not isinstance(got, str):
        return f"it returned {type(got).__name__}, expected a string"
    i = next((k for k, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
    return f"from character {i} it has {got[i:i + 20]!r} where the expected text has {want[i:i + 20]!r}"


def test_truncate_fits(m):
    """truncate returns a text of max_tokens tokens or fewer exactly as it is"""
    tok = StandIn()
    text = "Brand: Generic\n"  # 5 tokens
    for limit in (5, 110):
        got = need(m, "truncate")(text, tok.encode, tok.decode, limit)
        assert got == text, (f"truncate({text!r}, encode, decode, {limit}) should give the text unchanged, new line "
                             f"included, as it has only 5 tokens. It gave {short(got)}")


def test_truncate_cuts(m):
    """truncate keeps the first max_tokens tokens, decoded, with no blank space at the end"""
    tok = StandIn()
    for limit, want, why in ((12, FIRST_LINE, "the first 12 tokens end with a new line, which must go"),
                             (5, "Title: Cordless Elec", "tokens are not words: the 5th token is ' Elec'")):
        got = need(m, "truncate")(SUMMARY, tok.encode, tok.decode, limit)
        assert got == want, f"truncate(summary, encode, decode, {limit}) should give {want!r} ({why}). It gave {short(got)}"


def test_prompt_format(m):
    """make_prompt gives the question, the summary, then 'Price is $' and the rounded price"""
    tok = StandIn()
    f = need(m, "make_prompt")
    got = f(SUMMARY, 129.99, tok.encode, tok.decode)
    want = QUESTION + "\n\n" + SUMMARY + "\n\nPrice is $130.00"
    assert got == want, f"make_prompt(summary, 129.99, encode, decode) is not as expected: {where(got, want)}"
    for price, end in ((7.2, "\n\nPrice is $7.00"), (1000, "\n\nPrice is $1000.00")):
        got = f(SUMMARY, price, tok.encode, tok.decode)
        assert isinstance(got, str) and got.endswith(end), \
            f"make_prompt(summary, {price}, encode, decode) ends {str(got)[-20:]!r}, expected it to end {end!r}"


def test_prompt_cutoff(m):
    """make_prompt cuts the summary to cutoff tokens, 110 unless told otherwise"""
    tok = StandIn()
    for extra, limit in (({}, 110), ({"cutoff": 12}, 12)):
        got = need(m, "make_prompt")(LONG, 45, tok.encode, tok.decode, **extra)
        cut = tok.decode(tok.encode(LONG)[:limit]).rstrip()
        want = QUESTION + "\n\n" + cut + "\n\nPrice is $45.00"
        call = "make_prompt(summary, 45, encode, decode" + (", cutoff=12)" if extra else ")")
        assert got == want, f"{call} should cut a 190-token summary to {limit} tokens: {where(got, want)}"


def test_test_prompt(m):
    """test_prompt keeps everything up to 'Price is $' and leaves out the price"""
    head = QUESTION + "\n\n" + SUMMARY + "\n\nPrice is $"
    got = need(m, "test_prompt")(head + "130.00")
    assert got == head, f"test_prompt(a prompt ending 'Price is $130.00') is not as expected: {where(got, head)}"


def test_test_prompt_last(m):
    """test_prompt cuts at the last 'Price is $', even when the summary has those words too"""
    head = QUESTION + "\n\n" + SUMMARY + " Price is $20 lower in the twin pack.\n\nPrice is $"
    got = need(m, "test_prompt")(head + "25.00")
    assert got == head, (f"test_prompt returned a prompt ending {str(got)[-34:]!r}, expected it to end "
                         f"{head[-34:]!r}: cut at the last 'Price is $', not the first")


def test_test_prompt_missing(m):
    """test_prompt raises ValueError when the prompt has no 'Price is $'"""
    try:
        got = need(m, "test_prompt")(QUESTION + "\n\n" + SUMMARY)
    except ValueError:
        return
    except Exception as e:  # noqa: BLE001 - the learner should raise ValueError, not something else
        raise AssertionError(f"test_prompt on a prompt without 'Price is $' raised {type(e).__name__}, "
                             f"expected ValueError") from None
    raise AssertionError(f"test_prompt on a prompt without 'Price is $' returned text ending {str(got)[-24:]!r}, "
                         f"expected it to raise ValueError")


def test_count_truncated(m):
    """count_truncated counts the summaries over cutoff tokens, 110 unless told otherwise"""
    tok = StandIn()
    f = need(m, "count_truncated")
    got = f(["abcd" * 109, "abcd" * 110, "abcd" * 111, "abcd" * 300, ""], tok.encode)
    assert got == 2, (f"count_truncated(summaries of 109, 110, 111, 300 and 0 tokens, encode) returned {short(got)}, "
                      f"expected 2: only summaries over 110 tokens get cut")
    got = f(["Brand: Generic", SUMMARY, "Title: Kettle"], tok.encode, cutoff=4)
    assert got == 1, (f"count_truncated(summaries of 4, 66 and 4 tokens, encode, cutoff=4) returned {short(got)}, "
                      f"expected 1: a summary of exactly 4 tokens is not cut")
'''

FILES['tests_ex_w7_day3_and_4.py'] = r'''"""Tests for plan/exercises/week7/day3_and_4.py (run by harness.py). Plain arithmetic: nothing is trained."""
import math

FILE = "day3_and_4.py"


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def close(got, want):
    return isinstance(got, (int, float)) and math.isclose(got, want, rel_tol=1e-9, abs_tol=1e-15)


def expect_value_error(fn, args, call):
    """Passes when fn(*args) raises ValueError; otherwise fails with a message naming the call."""
    try:
        got = fn(*args)
    except ValueError:
        return
    except Exception as e:  # noqa: BLE001 - the learner should raise ValueError, not something else
        raise AssertionError(f"{call} raised {type(e).__name__}, expected ValueError") from None
    raise AssertionError(f"{call} returned {got!r}, expected it to raise ValueError")


def test_steps_per_epoch(m):
    """steps_per_epoch divides by batch size times accumulation and rounds a partial step up"""
    f = need(m, "steps_per_epoch")
    for args, want in (((20_000, 32), 625), ((1_000, 32), 32), ((17, 16), 2), ((16, 16), 1),
                       ((1_000, 8, 4), 32), ((100, 4, 4), 7)):
        got = f(*args)
        assert got == want, f"steps_per_epoch{args} returned {got!r}, expected {want}: examples / (batch_size * grad_accum), rounded up"


def test_total_steps(m):
    """total_steps works out the steps per epoch first, then multiplies by epochs and rounds up"""
    f = need(m, "total_steps")
    for args, per_epoch, want in (((800_000, 256, 3), 3_125, 9_375), ((20_000, 32, 1), 625, 625), ((100, 16, 2), 7, 14),
                                  ((100, 16, 1.5), 7, 11), ((1_000, 8, 2, 4), 32, 64)):
        got = f(*args)
        assert got == want, (f"total_steps{args} returned {got!r}, expected {want}: {per_epoch} steps per epoch "
                             f"times {args[2]} epochs, rounded up")


def test_warmup_steps(m):
    """warmup_steps is total times warmup_ratio, rounded up"""
    f = need(m, "warmup_steps")
    for args, want in (((625, 0.01), 7), ((9_375, 0.01), 94), ((100, 0.1), 10), ((200, 0.0), 0)):
        got = f(*args)
        assert got == want, f"warmup_steps{args} returned {got!r}, expected {want}: {args[0]} * {args[1]} rounded up"


def test_lr_warmup(m):
    """lr_at climbs in a straight line from 0 to learning_rate over the warmup steps"""
    f = need(m, "lr_at")
    for step, want in ((0, 0.0), (5, 5e-5), (9, 9e-5)):
        got = f(step, 100, 1e-4, 0.1)
        assert close(got, want), (f"lr_at({step}, 100, 1e-4, 0.1) returned {got!r}, expected {want}: "
                                  f"10 warmup steps, so 1e-4 * {step} / 10")
    got = f(6, 625, 1e-4, 0.01)
    assert close(got, 1e-4 * 6 / 7), (f"lr_at(6, 625, 1e-4, 0.01) returned {got!r}, expected {1e-4 * 6 / 7:.4g}: "
                                      f"warmup_steps(625, 0.01) is 7, so 1e-4 * 6 / 7")


def test_lr_cosine(m):
    """lr_at follows the cosine down from learning_rate after warmup to 0 at the last step"""
    f = need(m, "lr_at")
    for step, want in ((10, 1e-4), (32, 1e-4 * 0.5 * (1 + math.cos(math.pi * 22 / 90))), (55, 5e-5), (100, 0.0)):
        got = f(step, 100, 1e-4, 0.1)
        assert close(got, want), (f"lr_at({step}, 100, 1e-4, 0.1) returned {got!r}, expected {want:.6g}: "
                                  f"progress is ({step} - 10) / (100 - 10)")
    got = f(0, 100, 1e-4, 0.0)
    assert close(got, 1e-4), f"lr_at(0, 100, 1e-4, 0.0) returned {got!r}, expected 0.0001: with no warmup, step 0 is the peak"


def test_lr_range(m):
    """lr_at raises ValueError for a step below 0 or above total"""
    for step in (-1, 101):
        expect_value_error(need(m, "lr_at"), (step, 100, 1e-4, 0.1), f"lr_at({step}, 100, 1e-4, 0.1)")


def test_time_left(m):
    """time_left assumes the average step time so far and writes the rest as H:MM:SS"""
    f = need(m, "time_left")
    for args, want, why in (((125, 300, 625), "0:20:00", "500 steps left at 2.4 seconds each"),
                            ((10, 120, 9_375), "31:13:00", "112,380 seconds, and hours can pass 24"),
                            ((1, 3_725, 2), "1:02:05", "3,725 seconds"),
                            ((3, 10, 5), "0:00:07", "6.67 seconds rounds to 7"),
                            ((625, 1_500, 625), "0:00:00", "no steps left")):
        got = f(*args)
        assert got == want, f"time_left{args} returned {got!r}, expected {want!r}: {why}"


def test_time_left_range(m):
    """time_left raises ValueError before the first step or past the last one"""
    for args in ((0, 0, 625), (626, 1_500, 625)):
        expect_value_error(need(m, "time_left"), args, f"time_left{args}")
'''

FILES['tests_ex_w7_day5.py'] = r'''"""Tests for plan/exercises/week7/day5.py (run by harness.py). No model is run: the tests pass in stand-in predictors."""
import math

FILE = "day5.py"
QUESTION = "What does this cost to the nearest dollar?\n\n"
POINTS = [{"prompt": QUESTION + "Title: Desk Lamp\n\nPrice is $", "completion": "100.0"},
          {"prompt": QUESTION + "Title: Office Chair\n\nPrice is $", "completion": "250.5"},
          {"prompt": QUESTION + "Title: Phone Case\n\nPrice is $", "completion": "40.0"}]
GUESSES = [90.0, 170.5, 140.0]  # errors of 10 (green), 80 (orange) and 100 (red)


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def short(value, size=40):
    """The repr of a value, cut down so that a message stays readable."""
    text = repr(value)
    return text if len(text) <= size else text[:size - 3] + "..."


def stand_in(guesses):
    """A stand-in predictor that looks up its guess by the datapoint's prompt."""
    by_prompt = {point["prompt"]: guess for point, guess in zip(POINTS, guesses)}

    def predict(datapoint):
        assert isinstance(datapoint, dict), \
            f"predict was given the {type(datapoint).__name__} {short(datapoint)}, expected the datapoint dict itself"
        return by_prompt[datapoint["prompt"]]

    return predict


def expect_value_error(fn, args, call):
    """Passes when fn(*args) raises ValueError; otherwise fails with a message naming the call."""
    try:
        got = fn(*args)
    except ValueError:
        return
    except Exception as e:  # noqa: BLE001 - the learner should raise ValueError, not something else
        raise AssertionError(f"{call} raised {type(e).__name__}, expected ValueError") from None
    raise AssertionError(f"{call} returned {got!r}, expected it to raise ValueError")


def test_green(m):
    """color_for gives green for an error under 40 or under 20% of the truth"""
    f = need(m, "color_for")
    for error, truth in ((0, 10), (39.99, 50), (50, 300), (150, 1000)):
        got = f(error, truth)
        assert got == "green", f"color_for({error}, {truth}) returned {got!r}, expected 'green'"


def test_orange_red(m):
    """color_for gives orange for an error under 80 or under 40% of the truth, and red otherwise"""
    f = need(m, "color_for")
    for error, truth, want, why in ((40, 200, "orange", "40 is not under 40, and 40 / 200 is not under 0.2"),
                                    (79, 100, "orange", "79 is under 80"),
                                    (100, 300, "orange", "100 / 300 is under 0.4"),
                                    (80, 200, "red", "80 is not under 80, and 80 / 200 is not under 0.4"),
                                    (90, 150, "red", "90 / 150 is 0.6")):
        got = f(error, truth)
        assert got == want, f"color_for({error}, {truth}) returned {got!r}, expected {want!r}: {why}"


def test_counts(m):
    """color_counts counts each colour and gives 0 for a colour that no guess got"""
    f = need(m, "color_counts")
    got = f([100, 150, 10, 300], [110, 100, 200, 290])
    want = {"green": 2, "orange": 1, "red": 1}
    assert got == want, f"color_counts([100, 150, 10, 300], [110, 100, 200, 290]) returned {got!r}, expected {want}"
    got = f([20.0, 41.0], [25.0, 40.0])
    want = {"green": 2, "orange": 0, "red": 0}
    assert got == want, f"color_counts([20.0, 41.0], [25.0, 40.0]) returned {got!r}, expected {want}, zeros included"


def test_counts_lengths(m):
    """color_counts raises ValueError when guesses and truths differ in length"""
    expect_value_error(need(m, "color_counts"), ([100, 150, 10], [110, 100]), "color_counts([100, 150, 10], [110, 100])")


def test_evaluate_calls(m):
    """evaluate calls predict once for each datapoint, in order, with the datapoint itself"""
    seen = []

    def predict(datapoint):
        seen.append(datapoint)
        return 100.0

    need(m, "evaluate")(predict, POINTS)
    assert len(seen) == len(POINTS), f"predict was called {len(seen)} times for {len(POINTS)} datapoints, expected once each"
    for i, (got, want) in enumerate(zip(seen, POINTS)):
        assert got == want, (f"call {i + 1} of predict was given {short(got)}, expected datapoint {i + 1} itself, "
                             f"the dict {short(want)}")


def test_evaluate_scores(m):
    """evaluate returns the average error and the colour counts, with the truth from completion"""
    got = need(m, "evaluate")(stand_in(GUESSES), POINTS)
    assert isinstance(got, dict), f"evaluate returned {type(got).__name__}, expected a dict"
    assert set(got) == {"error", "green", "orange", "red"}, \
        f"evaluate returned the keys {sorted(got)}, expected 'error', 'green', 'orange' and 'red'"
    assert isinstance(got["error"], (int, float)) and math.isclose(got["error"], 190 / 3), \
        f"the error is {got['error']!r}, expected {190 / 3:.4f}: the average of the errors 10, 80 and 100"
    counts = {color: got[color] for color in ("green", "orange", "red")}
    assert counts == {"green": 1, "orange": 1, "red": 1}, \
        f"the counts are {counts}, expected one of each: errors of 10 on 100.0, 80 on 250.5 and 100 on 40.0"


def test_evaluate_empty(m):
    """evaluate raises ValueError when there are no datapoints"""
    expect_value_error(need(m, "evaluate"), (lambda datapoint: 1.0, []), "evaluate(predict, [])")


def test_improvement(m):
    """improvement gives the drop in error as a percentage of the old error, negative if worse"""
    f = need(m, "improvement")
    for new, old, want in ((30, 120, 75.0), (39.85, 110.72, 100 * (110.72 - 39.85) / 110.72), (50, 40, -25.0), (40, 40, 0.0)):
        got = f(new, old)
        assert isinstance(got, (int, float)) and math.isclose(got, want, rel_tol=1e-9, abs_tol=1e-12), \
            f"improvement({new}, {old}) returned {got!r}, expected {want:.4g}: 100 * ({old} - {new}) / {old}"
'''

FILES['tests_ex_w8_day1.py'] = r'''"""Tests for plan/exercises/week8/day1.py (run by harness.py). No Modal call is made: the tests pass in stand-ins."""
import logging

FILE = "day1.py"
CODES = {"RED": "\033[31m", "GREEN": "\033[32m", "YELLOW": "\033[33m", "BLUE": "\033[34m", "MAGENTA": "\033[35m",
         "CYAN": "\033[36m", "WHITE": "\033[37m", "BG_BLACK": "\033[40m", "RESET": "\033[0m"}
CREATED = "[Specialist Agent] Specialist Agent is initializing - connecting to modal"
CALLING = "[Specialist Agent] Specialist Agent is calling remote fine-tuned model"
logging.getLogger().addHandler(logging.NullHandler())  # so logging.info never sets up printing of its own


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def show(value):
    """repr(value), with the escape character written \\033 as in the exercise."""
    return repr(value).replace("\\x1b", "\\033")


class Catch(logging.Handler):
    """Collects the messages logged while a test runs."""

    def __init__(self):
        super().__init__(logging.INFO)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def logged(action):
    """Runs action() with INFO logging switched on, and returns the messages logged."""
    root, catch = logging.getLogger(), Catch()
    level = root.level
    root.addHandler(catch)
    root.setLevel(logging.INFO)
    try:
        action()
    finally:
        root.removeHandler(catch)
        root.setLevel(level)
    return catch.messages


def scout(m):
    """A kind of agent the tests build on your Agent: name 'Scout Agent', color CYAN."""
    base = need(m, "Agent")

    class Scout(base):
        name = "Scout Agent"
        color = getattr(base, "CYAN", "")

    return Scout()


def specialist(m, remote_price):
    try:
        return need(m, "SpecialistAgent")(remote_price)
    except AttributeError as e:
        if "lines" in str(e):
            raise AssertionError(f"SpecialistAgent(remote_price) failed with {e}: call super().__init__() before you log") from None
        raise


def test_log_lines(m):
    """Agent.log appends '[name] message' to the agent's lines"""
    agent = scout(m)
    agent.log("Found 4 deals")
    agent.log("Done")
    got = getattr(agent, "lines", None)
    assert got == ["[Scout Agent] Found 4 deals", "[Scout Agent] Done"], \
        f"after log('Found 4 deals') and log('Done'), lines must be ['[Scout Agent] Found 4 deals', '[Scout Agent] Done']; it is {show(got)}"


def test_log_colors(m):
    """Agent has the course's color codes, and log sends BG_BLACK + color + line + RESET"""
    base = need(m, "Agent")
    for name, code in CODES.items():
        got = getattr(base, name, None)
        assert got == code, f"Agent.{name} is {show(got)}, expected {show(code)}"
    agent = scout(m)
    messages = logged(lambda: agent.log("Found 4 deals"))
    want = "\033[40m\033[36m[Scout Agent] Found 4 deals\033[0m"
    assert want in messages, f"logging.info must receive {show(want)}; it received {show(messages)}"


def test_own_lines(m):
    """Each agent starts with an empty lines list of its own"""
    first, second = scout(m), scout(m)
    got = getattr(first, "lines", None)
    assert got == [], f"a new agent must start with lines == [] (make the list in Agent.__init__, not on the class); it has {got!r}"
    first.log("Found 4 deals")
    assert second.lines == [], \
        "logging on one agent changed another agent's lines: make the list in Agent.__init__ (self.lines = []), not on the class"


def test_specialist_setup(m):
    """SpecialistAgent is an Agent named 'Specialist Agent', in red, that logs when created"""
    base, special = need(m, "Agent"), need(m, "SpecialistAgent")
    assert isinstance(special, type) and issubclass(special, base), "SpecialistAgent must be a subclass of Agent"
    agent = specialist(m, lambda description: 1.0)
    assert agent.name == "Specialist Agent", f"its name is {agent.name!r}, expected 'Specialist Agent'"
    assert agent.color == "\033[31m", f"its color is {show(agent.color)}, expected Agent.RED, {show(CODES['RED'])}"
    got = getattr(agent, "lines", None)
    assert got == [CREATED], f"right after it is created, lines must be [{CREATED!r}]; it is {show(got)}"


def test_price_float(m):
    """price calls remote_price once with the description and returns a float"""
    calls = []

    def remote_price(description):
        calls.append(description)
        return 178

    got = specialist(m, remote_price).price("55-inch 4K UHD smart TV")
    assert calls == ["55-inch 4K UHD smart TV"], \
        f"remote_price was called with {calls!r}; expected one call with '55-inch 4K UHD smart TV'"
    assert isinstance(got, float) and got == 178.0, f"price returned {got!r} when remote_price gave 178; expected 178.0, a float"


def test_price_logs(m):
    """price logs before it calls remote_price, then logs the prediction to 2 decimals"""
    seen = []
    agent = None

    def remote_price(description):
        seen.append(list(agent.lines))
        return 1299.5

    agent = specialist(m, remote_price)
    agent.price("15.6-inch gaming laptop")
    before = seen[0][-1:] if seen else []
    assert before == [CALLING], f"when remote_price is called, the last line must be {CALLING!r}; it was {show(before)}"
    done = "[Specialist Agent] Specialist Agent completed - predicting $1299.50"
    assert agent.lines[-1:] == [done], f"after price, the last line must be {done!r}; it is {show(agent.lines[-1:])}"


def test_pricer_lazy(m):
    """Pricer loads nothing when created, loads on the first price, and returns a float"""
    loads = []

    def load():
        loads.append("load")
        return lambda description: 30

    pricer = need(m, "Pricer")(load)
    assert loads == [], "Pricer(load) called load at once; wait for the first setup() or price()"
    got = pricer.price("21.5-inch meeting display")
    assert len(loads) == 1, f"the first price called load {len(loads)} times, expected once"
    assert isinstance(got, float) and got == 30.0, f"price returned {got!r} when the model gave 30; expected 30.0, a float"


def test_pricer_once(m):
    """Pricer loads the model only once, however often setup and price are called"""
    loads, asked = [], []

    def model(description):
        asked.append(description)
        return 446

    def load():
        loads.append("load")
        return model

    pricer = need(m, "Pricer")(load)
    pricer.setup()
    got = [pricer.price(d) for d in ("16-inch laptop", "55-inch TV", "USB microphone")]
    pricer.setup()
    assert len(loads) == 1, f"load was called {len(loads)} times, expected once: keep the model after the first setup"
    assert asked == ["16-inch laptop", "55-inch TV", "USB microphone"], f"the model was asked about {asked!r}, expected each description once"
    assert got == [446.0, 446.0, 446.0], f"the three prices were {got!r}, expected [446.0, 446.0, 446.0]"
'''

FILES['tests_ex_w8_day2.py'] = r'''"""Tests for plan/exercises/week8/day2.py (run by harness.py). No model, Chroma or Modal call: the agents are stand-ins."""

FILE = "day2.py"
INTRO = "To provide some context, here are some other items that might be similar to the item you need to estimate.\n\n"
QUESTION = "Estimate the price of this product. Respond with the price, no explanation"
SIMILARS = ["USB condenser microphone with a shock mount", "Dynamic podcast microphone with USB-C and XLR outputs"]
PRICES = [129.5, 249]
CONTEXT = (INTRO
           + "Potentially related product:\nUSB condenser microphone with a shock mount\nPrice is $129.50\n\n"
           + "Potentially related product:\nDynamic podcast microphone with USB-C and XLR outputs\nPrice is $249.00\n\n")
# Each row: the frontier, specialist and neural network agents' prices for one product.
ROWS = [[150.0, 100.0, 140.0], [45.0, 60.0, 50.0], [300.0, 250.0, 280.0], [80.0, 95.0, 70.0], [510.0, 450.0, 520.0]]
TRUTHS = [144.0, 47.0, 293.0, 80.5, 505.0]  # exactly 0.8 * frontier + 0.1 * specialist + 0.1 * neural network


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def differ(got, want):
    """Where two texts first differ, shown briefly."""
    if not isinstance(got, str):
        return f"is {type(got).__name__}, expected a string"
    i = next((k for k, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
    return f"differs at character {i}: got {got[max(0, i - 20):i + 25]!r}, expected {want[max(0, i - 20):i + 25]!r}"


def raises_value_error(action):
    try:
        action()
    except ValueError:
        return True
    return False


class Fixed:
    """A stand-in agent: always gives the same price, and remembers what it was asked."""

    def __init__(self, value):
        self.value, self.asked = value, []

    def price(self, description):
        self.asked.append(description)
        return self.value


def test_context_opening(m):
    """make_context starts with the course's opening sentence and a blank line"""
    got = need(m, "make_context")(SIMILARS, PRICES)
    assert isinstance(got, str) and got.startswith(INTRO), \
        f"make_context {differ(got, INTRO)}. It must open with frontier_agent.py's sentence, then a blank line"


def test_context_products(m):
    """make_context adds each product, then its price with 2 decimals, in order"""
    got = need(m, "make_context")(SIMILARS, PRICES)
    blocks = CONTEXT[len(INTRO):]
    start = got.find("Potentially related product:") if isinstance(got, str) else -1
    assert start >= 0, "make_context has no 'Potentially related product:' line"
    assert got[start:] == blocks, f"from the first 'Potentially related product:', the text {differ(got[start:], blocks)}"


def test_context_lengths(m):
    """make_context raises ValueError when products and prices differ in number"""
    make = need(m, "make_context")
    assert raises_value_error(lambda: make(SIMILARS, [129.5])), "two products with one price must raise ValueError"
    assert raises_value_error(lambda: make(SIMILARS[:1], PRICES)), "one product with two prices must raise ValueError"


def test_messages_for(m):
    """messages_for returns one user message: instruction, description, then the context"""
    description = "Professional podcast microphone with USB-C and XLR outputs"
    got = need(m, "messages_for")(description, SIMILARS, PRICES)
    assert isinstance(got, list) and len(got) == 1 and isinstance(got[0], dict), \
        f"messages_for returned {got!r:.80}; expected a list holding one message"
    assert got[0].get("role") == "user", f"the message's role is {got[0].get('role')!r}, expected 'user'"
    want = f"{QUESTION}\n\n{description}\n\n" + need(m, "make_context")(SIMILARS, PRICES)
    assert got[0].get("content") == want, f"the content {differ(got[0].get('content'), want)}"


def test_fit_exact(m):
    """fit_weights finds the weights that made the true prices, as a list of floats"""
    got = need(m, "fit_weights")(ROWS, TRUTHS)
    assert isinstance(got, list) and len(got) == 3, \
        f"fit_weights returned {got!r}; expected a list of 3 weights, one per agent (one per column)"
    assert all(isinstance(w, float) for w in got), f"the weights must be floats; they are {[type(w).__name__ for w in got]}"
    assert all(abs(w - want) < 1e-6 for w, want in zip(got, [0.8, 0.1, 0.1])), \
        f"fit_weights returned {got}; expected 0.8, 0.1 and 0.1, which give these true prices exactly"


def test_fit_least_squares(m):
    """fit_weights gives the least squares answer when no weights fit exactly"""
    got = need(m, "fit_weights")([[1.0], [2.0]], [1.0, 3.0])
    assert isinstance(got, list) and len(got) == 1 and abs(got[0] - 1.4) < 1e-6, \
        f"fit_weights([[1.0], [2.0]], [1.0, 3.0]) returned {got!r}; expected [1.4], the w that makes (w - 1)**2 + (2*w - 3)**2 smallest"


def test_fit_bad_rows(m):
    """fit_weights raises ValueError when rows and true prices differ in number"""
    fit = need(m, "fit_weights")
    assert raises_value_error(lambda: fit(ROWS, TRUTHS[:4])), "5 rows of predictions with 4 true prices must raise ValueError"


def test_ensemble_price(m):
    """EnsembleAgent.price asks each agent once and returns the weighted sum as a float"""
    agents = [Fixed(150.0), Fixed(100), Fixed(140.0)]
    got = need(m, "EnsembleAgent")(agents, [0.8, 0.1, 0.1]).price("Podcast microphone")
    asked = [agent.asked for agent in agents]
    assert asked == [["Podcast microphone"]] * 3, \
        f"each agent must be asked once, with the description unchanged; the three agents were asked {asked!r}"
    assert isinstance(got, float) and abs(got - 144.0) < 1e-9, \
        f"price returned {got!r}; expected 0.8 * 150 + 0.1 * 100 + 0.1 * 140 = 144.0, as a float"


def test_ensemble_mismatch(m):
    """EnsembleAgent raises ValueError when agents and weights differ in number"""
    ensemble = need(m, "EnsembleAgent")
    assert raises_value_error(lambda: ensemble([Fixed(1.0), Fixed(2.0)], [1.0])), \
        "EnsembleAgent(two agents, one weight) must raise ValueError when it is made"
'''

FILES['tests_ex_w8_day3.py'] = r'''"""Tests for plan/exercises/week8/day3.py (run by harness.py). No model or Pushover call: the replies are written out here."""
import json

import pydantic

FILE = "day3.py"
TV = {"product_description": "A 55-inch 4K UHD smart TV with HDR and three HDMI ports.", "price": 178,
      "url": "https://deals.example.com/tv-55"}
DISPLAY = {"product_description": "A 21.5-inch 1080p meeting display with a webcam and stereo speakers.", "price": 30,
           "url": "https://deals.example.com/display-21"}
LAPTOP = {"product_description": "A 16-inch touch laptop with a 6-core CPU, 16GB of RAM and a 512GB SSD.", "price": 446,
          "url": "https://deals.example.com/laptop-16"}
FREE = {"product_description": "A gaming mouse that comes free with a magazine subscription.", "price": 0,
        "url": "https://deals.example.com/mouse"}
HEAD = "Deal Alert! Price=$178.00, Estimate=$300.00, Discount=$122.00 :"
TAIL = "... https://deals.example.com/tv-55"


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def model(m, name):
    found = need(m, name)
    assert isinstance(found, type) and issubclass(found, pydantic.BaseModel), f"{name} must be a pydantic BaseModel"
    return found


def described(schema, name):
    """The description of one field in a model's JSON schema."""
    return schema.get("properties", {}).get(name, {}).get("description", "")


def differ(got, want):
    """Where two texts first differ, shown briefly."""
    if not isinstance(got, str):
        return f"is {type(got).__name__}, expected a string"
    i = next((k for k, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
    return f"differs at character {i}: got {got[max(0, i - 20):i + 25]!r}, expected {want[max(0, i - 20):i + 25]!r}"


def test_deal_fields(m):
    """Deal has product_description, price and url, each with a description of 20+ characters"""
    schema = model(m, "Deal").model_json_schema()
    props = schema.get("properties", {})
    assert set(props) == {"product_description", "price", "url"}, \
        f"Deal's fields are {sorted(props)}; expected product_description, price and url"
    types = {name: props[name].get("type") for name in ("product_description", "price", "url")}
    assert types == {"product_description": "string", "price": "number", "url": "string"}, \
        f"the fields' JSON types are {types}; expected str, float and str"
    assert set(schema.get("required", [])) == set(props), "all three fields must be required: give them no default"
    short = [name for name in props if len(described(schema, name)) < 20]
    assert not short, f"give these fields a Field(description=...) of at least 20 characters: {short}"


def test_selection_model(m):
    """DealSelection keeps a list of Deal objects in deals, described in 20+ characters"""
    selection_class, deal_class = model(m, "DealSelection"), model(m, "Deal")
    selection = selection_class(deals=[TV, DISPLAY])
    got = getattr(selection, "deals", None)
    assert isinstance(got, list) and len(got) == 2 and all(isinstance(d, deal_class) for d in got), \
        f"DealSelection(deals=[two dicts]).deals is {got!r:.80}; expected a list of two Deal objects"
    schema = selection_class.model_json_schema()
    assert schema.get("required") == ["deals"], "deals must be a required field: give it no default"
    assert len(described(schema, "deals")) >= 20, "give deals a Field(description=...) of at least 20 characters"


def test_parse_order(m):
    """parse_selection turns the JSON reply into a DealSelection, deals in the reply's order"""
    got = need(m, "parse_selection")(json.dumps({"deals": [LAPTOP, TV, DISPLAY]}))
    assert isinstance(got, model(m, "DealSelection")), f"parse_selection returned {type(got).__name__}, expected a DealSelection"
    urls = [deal.url for deal in got.deals]
    assert urls == [LAPTOP["url"], TV["url"], DISPLAY["url"]], f"the deals came back as {urls}; expected the reply's order"
    assert got.deals[1].price == 178.0, f"the TV's price is {got.deals[1].price!r}, expected 178.0"


def test_parse_drops_free(m):
    """parse_selection drops the deals whose price is 0 or less"""
    reply = json.dumps({"deals": [FREE, TV, {**DISPLAY, "price": -5}]})
    urls = [deal.url for deal in need(m, "parse_selection")(reply).deals]
    assert urls == [TV["url"]], f"parse_selection kept {urls}; expected only the TV, the one deal priced above 0"


def test_parse_bad(m):
    """parse_selection raises ValueError when the reply does not fit DealSelection"""
    parse = need(m, "parse_selection")
    for reply in ("Here are 5 great deals!", json.dumps({"deals": [{"price": 10}]}), json.dumps({"items": [TV]})):
        try:
            parse(reply)
        except ValueError:
            continue
        raise AssertionError(f"parse_selection({reply!r}) did not raise ValueError")


def test_unseen(m):
    """unseen drops deals seen before or earlier in the list, keeping the order"""
    deal = model(m, "Deal")
    tv, display, laptop, display_again = deal(**TV), deal(**DISPLAY), deal(**LAPTOP), deal(**{**DISPLAY, "price": 25})
    try:
        got = need(m, "unseen")([tv, display, laptop, display_again], [LAPTOP["url"]])
    except AttributeError as e:
        raise AssertionError(f"unseen failed with {e}: seen_urls may be a list, so keep a set of your own") from None
    kept = [d.url.rsplit("/", 1)[-1] for d in got]
    assert kept == ["tv-55", "display-21"], \
        (f"unseen must keep only the deals whose urls end in tv-55 and display-21: laptop-16 was seen before, "
         f"and the second display-21 repeats a url. It kept {kept}")
    assert got[1].price == 30, "when two deals share a url, keep the first one"


def test_unseen_inputs(m):
    """unseen leaves the list and the seen urls it was given unchanged"""
    deal = model(m, "Deal")
    given = [deal(**TV), deal(**DISPLAY), deal(**TV)]
    before = list(given)
    seen = {LAPTOP["url"]}
    need(m, "unseen")(given, seen)
    assert given == before, "unseen changed the list of deals it was given; build a new list instead"
    assert seen == {LAPTOP["url"]}, f"unseen changed seen_urls to {sorted(seen)}; keep a set of your own instead"


def test_alert_format(m):
    """alert_text writes the course's alert: prices, discount, description, '... ' and url"""
    got = need(m, "alert_text")(model(m, "Deal")(**TV), 300)
    want = HEAD + TV["product_description"] + TAIL
    assert got == want, f"alert_text(tv, 300) {differ(got, want)}"


def test_alert_limit(m):
    """alert_text cuts only the description to fit limit, and raises ValueError if it cannot"""
    tv, alert = model(m, "Deal")(**TV), need(m, "alert_text")
    fixed = len(HEAD) + len(TAIL)
    want = HEAD + TV["product_description"][:120 - fixed] + TAIL
    got = alert(tv, 300, limit=120)
    assert got == want, f"alert_text(tv, 300, limit=120) {differ(got, want)}"
    try:
        got = alert(tv, 300, limit=fixed)
    except ValueError:
        raise AssertionError(f"with limit={fixed} the alert fits with no description at all, so alert_text must "
                             f"return it without the description, not raise ValueError") from None
    assert got == HEAD + TAIL, f"with limit={fixed} there is room for no description at all; alert_text {differ(got, HEAD + TAIL)}"
    try:
        alert(tv, 300, limit=fixed - 1)
    except ValueError:
        return
    raise AssertionError(f"with limit={fixed - 1} even the prices and the url do not fit, so alert_text must raise ValueError")
'''

FILES['tests_ex_w8_day4.py'] = r'''"""Tests for plan/exercises/week8/day4.py (run by harness.py). No model is called: scan, estimate and notify are stand-ins."""

FILE = "day4.py"
NAMES = ["scan_the_internet_for_bargains", "estimate_true_value", "notify_user_of_deal"]
PARAMETERS = {"scan_the_internet_for_bargains": {},
              "estimate_true_value": {"description": "string"},
              "notify_user_of_deal": {"description": "string", "deal_price": "number",
                                      "estimated_true_value": "number", "url": "string"}}


def deal(description, price, slug):
    return {"product_description": description, "price": price, "url": f"https://deals.example.com/{slug}"}


TV = deal("55-inch 4K UHD smart TV", 178.0, "tv")
DISPLAY = deal("21.5-inch 1080p meeting display", 30.0, "display")
LAPTOP = deal("16-inch touch laptop with 16GB of RAM", 446.0, "laptop")
GAMING = deal("15.6-inch gaming laptop with an RTX 3050", 650.0, "gaming")
VALUES = {TV["product_description"]: 300.0, DISPLAY["product_description"]: 120.0,
          LAPTOP["product_description"]: 600.0, GAMING["product_description"]: 700.0}
# The discounts: TV 122, display 90, laptop 154, gaming laptop 50.


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


class Desk:
    """Stand-ins for the three functions, remembering how they were called."""

    def __init__(self, deals, values=None):
        self.deals, self.values = deals, values or VALUES
        self.scans, self.asked, self.sent = 0, [], []

    def scan(self):
        self.scans += 1
        return self.deals

    def estimate(self, description):
        self.asked.append(description)
        return self.values.get(description, 0.0) if isinstance(description, str) else 0.0

    def notify(self, description, deal_price, estimated_true_value, url):
        self.sent.append((description, deal_price, estimated_true_value, url))
        return "notification sent ok"


def planner(m, desk):
    return need(m, "PlanningAgent")(desk.scan, desk.estimate, desk.notify)


def first_difference(got, want, where):
    """The first place where got differs from want, in a few words, or '' if they match."""
    if isinstance(want, dict):
        if not isinstance(got, dict):
            return f"{where} is {got!r:.60}, expected a dict"
        for key in want:
            if key not in got:
                return f"{where} has no {key!r}"
            found = first_difference(got[key], want[key], f"{where}[{key!r}]")
            if found:
                return found
        extra = [key for key in got if key not in want]
        return f"{where} has keys it should not have: {extra}" if extra else ""
    return "" if got == want else f"{where} is {got!r:.60}, expected {want!r:.60}"


def tools_by_name(m):
    tools = need(m, "get_tools")()
    names = [t.get("function", {}).get("name") if isinstance(t, dict) else None for t in tools] if isinstance(tools, list) else []
    assert names == NAMES, "fix the tool names first: get_tools must give the lesson's three tools, in order"
    return {t["function"]["name"]: t["function"] for t in tools}


def test_run(m):
    """run estimates the deal's description once and returns deal, estimate and discount"""
    desk = Desk([TV])
    got = planner(m, desk).run(TV)
    assert desk.asked == [TV["product_description"]], \
        f"estimate was called with {desk.asked!r}; expected one call with the deal's product_description"
    want = {"deal": TV, "estimate": 300.0, "discount": 122.0}
    assert got == want, f"run(tv) must return {{'deal': tv, 'estimate': 300.0, 'discount': 122.0}}: {first_difference(got, want, 'its result')}"


def test_plan_first_five(m):
    """plan estimates only the first 5 deals, once each, in order"""
    many = [deal(f"Deal number {i}", 10.0, f"deal-{i}") for i in range(1, 8)]
    desk = Desk(many, {d["product_description"]: 20.0 for d in many})
    planner(m, desk).plan()
    assert desk.scans == 1, f"scan was called {desk.scans} times, expected once"
    want = [f"Deal number {i}" for i in range(1, 6)]
    assert desk.asked == want, f"estimate was asked about {desk.asked}; expected the first 5 of the 7 deals, in order"


def test_plan_best(m):
    """plan notifies the largest discount once, with its details, and returns that opportunity"""
    desk = Desk([TV, DISPLAY, LAPTOP, GAMING])
    got = planner(m, desk).plan()
    sent = [(LAPTOP["product_description"], 446.0, 600.0, LAPTOP["url"])]
    assert desk.sent == sent, \
        f"notify must be called once, for the laptop (discount 154, the largest), with {sent[0]!r}; it got {desk.sent!r:.60}"
    want = {"deal": LAPTOP, "estimate": 600.0, "discount": 154.0}
    assert got == want, f"plan must return the laptop's opportunity: {first_difference(got, want, 'its result')}"


def test_plan_threshold(m):
    """plan returns None and notifies nobody unless the best discount is above the threshold"""
    desk = Desk([GAMING])
    got = planner(m, desk).plan()
    assert got is None and desk.sent == [], \
        (f"a best discount of exactly 50 is not above DEAL_THRESHOLD, so plan must notify nobody and return None; "
         f"plan made {len(desk.sent)} notify call(s) and returned {got!r:.60}")
    desk = Desk([TV, DISPLAY, LAPTOP])
    agent = planner(m, desk)
    agent.DEAL_THRESHOLD = 200
    got = agent.plan()
    assert got is None and desk.sent == [], \
        "with DEAL_THRESHOLD set to 200 and a best discount of 154, plan must return None: read the threshold from self.DEAL_THRESHOLD"


def test_plan_no_deals(m):
    """plan returns None without estimating or notifying when scan finds no deals"""
    for found in ([], None):
        desk = Desk(found)
        try:
            got = planner(m, desk).plan()
        except TypeError as e:
            raise AssertionError(f"plan failed with {e} when scan gave {found!r}: treat None like an empty list") from None
        assert got is None, f"plan returned {got!r} when scan gave {found!r}; expected None"
        assert desk.asked == [] and desk.sent == [], f"when scan gave {found!r}, estimate and notify must not be called"


def test_tool_schema(m):
    """tool_schema builds a function description in the lesson's format"""
    schema = need(m, "tool_schema")
    got = schema("estimate_true_value", "Estimate what an item is worth", {"description": ("string", "The item to estimate")})
    want = {"name": "estimate_true_value", "description": "Estimate what an item is worth",
            "parameters": {"type": "object", "properties": {"description": {"type": "string", "description": "The item to estimate"}},
                           "required": ["description"], "additionalProperties": False}}
    assert got == want, f"for estimate_true_value, {first_difference(got, want, 'the schema')}"
    got = schema("scan_the_internet_for_bargains", "Find bargains online", {})
    want = {"name": "scan_the_internet_for_bargains", "description": "Find bargains online",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}}
    assert got == want, f"with no parameters, {first_difference(got, want, 'the schema')}"


def test_get_tools_names(m):
    """get_tools gives three function tools, named after the lesson's pretend functions"""
    tools = need(m, "get_tools")()
    assert isinstance(tools, list) and len(tools) == 3, f"get_tools returned {tools!r:.80}; expected a list of 3 tools"
    assert all(isinstance(t, dict) and t.get("type") == "function" and isinstance(t.get("function"), dict) for t in tools), \
        "each tool must be a dict {'type': 'function', 'function': {...}}"
    names = [t["function"].get("name") for t in tools]
    assert names == NAMES, f"the tools are named {names}; expected {NAMES}, in that order"
    short = [t["function"]["name"] for t in tools if len(str(t["function"].get("description", ""))) < 10]
    assert not short, f"give these tools a description of at least 10 characters: {short}"


def test_get_tools_parameters(m):
    """get_tools gives each tool the lesson's parameters and types, all required"""
    for name, function in tools_by_name(m).items():
        parameters = function.get("parameters", {})
        types = {key: value.get("type") for key, value in parameters.get("properties", {}).items()}
        assert types == PARAMETERS[name], f"{name} has the parameters {types}; expected {PARAMETERS[name]}"
        assert parameters.get("required") == list(PARAMETERS[name]), \
            f"{name} requires {parameters.get('required')!r}; expected {list(PARAMETERS[name])!r}, in that order"
        assert parameters.get("type") == "object" and parameters.get("additionalProperties") is False, \
            f"{name}'s parameters need 'type': 'object' and 'additionalProperties': False"
        short = [key for key, value in parameters["properties"].items() if len(str(value.get("description", ""))) < 10]
        assert not short, f"give these parameters of {name} a description of at least 10 characters: {short}"
'''

FILES['tests_ex_w8_day5.py'] = r'''"""Tests for plan/exercises/week8/day5.py (run by harness.py). Every file is written in a temporary folder."""
import json
import os
import tempfile

FILE = "day5.py"


def opportunity(description, price, estimate, slug):
    return {"deal": {"product_description": description, "price": price, "url": f"https://deals.example.com/{slug}"},
            "estimate": estimate, "discount": estimate - price}


WATCH = opportunity("47mm LTE titanium smartwatch", 350.0, 773.81, "watch")
TV = opportunity("55-inch 4K UHD smart TV", 178.0, 300.0, "tv")
DISPLAY = opportunity("21.5-inch 1080p meeting display", 30.0, 120.0, "display")
LAPTOP = opportunity("16-inch touch laptop with 16GB of RAM", 446.0, 600.0, "laptop")


def need(m, name):
    assert hasattr(m, name), f"{FILE} has nothing named {name}"
    return getattr(m, name)


def slugs(opportunities):
    """The end of each deal's url, to keep messages short."""
    try:
        return [o["deal"]["url"].rsplit("/", 1)[-1] for o in opportunities]
    except (TypeError, KeyError, AttributeError):
        return repr(opportunities)[:80]


def filled(m, folder):
    """A Memory with the watch, TV, display and laptop added in that order."""
    memory = need(m, "Memory")(os.path.join(folder, "memory.json"))
    for item in (WATCH, TV, DISPLAY, LAPTOP):
        memory.add(item)
    return memory


def test_missing_file(m):
    """A Memory on a missing file starts with an empty list and does not create the file"""
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "memory.json")
        memory = need(m, "Memory")(path)
        got = getattr(memory, "opportunities", None)
        assert got == [], f"memory.opportunities is {got!r} when the file is missing; expected []"
        assert not os.path.exists(path), "Memory created the file before anything was added; leave that to add"


def test_reads_file(m):
    """Memory loads the opportunities already in the file, in the framework's format"""
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "memory.json")
        with open(path, "w", encoding="utf-8") as file:
            json.dump([WATCH, TV], file, indent=2)
        got = need(m, "Memory")(path).opportunities
        assert got == [WATCH, TV], f"memory.opportunities is {slugs(got)}; expected the file's two opportunities, ['watch', 'tv']"


def test_add_writes(m):
    """add appends the opportunity, returns True and writes the list as JSON with indent 2"""
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "memory.json")
        memory = need(m, "Memory")(path)
        first, second = memory.add(TV), memory.add(DISPLAY)
        assert first is True and second is True, f"add returned {first!r} and {second!r} for two new deals; expected True both times"
        assert memory.opportunities == [TV, DISPLAY], f"memory.opportunities is {slugs(memory.opportunities)}; expected ['tv', 'display']"
        assert os.path.exists(path), "add did not write the file"
        with open(path, encoding="utf-8") as file:
            text = file.read()
        assert json.loads(text) == [TV, DISPLAY], "the file must hold the whole list of opportunities, oldest first"
        assert text.strip() == json.dumps([TV, DISPLAY], indent=2), \
            "write the file with json.dump(..., indent=2), as the framework's write_memory does"


def test_add_repeat(m):
    """add returns False and changes nothing when the deal's url is already remembered"""
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "memory.json")
        memory = need(m, "Memory")(path)
        memory.add(TV)
        assert os.path.exists(path), "fix the writing first: add must write the file"
        with open(path, encoding="utf-8") as file:
            before = file.read()
        again = opportunity("55-inch 4K UHD smart TV, now cheaper", 160.0, 300.0, "tv")
        got = memory.add(again)
        assert got is False, f"adding a deal whose url is already remembered returned {got!r}; expected False"
        assert memory.opportunities == [TV], "the same url was added twice: compare the deals' urls, not whole opportunities"
        with open(path, encoding="utf-8") as file:
            assert file.read() == before, "the file changed although nothing was added"


def test_survives_restart(m):
    """A new Memory on the same file sees everything added before"""
    with tempfile.TemporaryDirectory() as folder:
        filled(m, folder)
        got = need(m, "Memory")(os.path.join(folder, "memory.json")).opportunities
        assert got == [WATCH, TV, DISPLAY, LAPTOP], \
            f"a new Memory on the same file has {slugs(got)}; expected ['watch', 'tv', 'display', 'laptop']"


def test_latest(m):
    """latest(n) returns the n most recently added opportunities, newest first"""
    with tempfile.TemporaryDirectory() as folder:
        got = filled(m, folder).latest(2)
        assert got == [LAPTOP, DISPLAY], f"latest(2) gave {slugs(got)}; expected ['laptop', 'display'], the newest first"


def test_latest_edges(m):
    """latest gives all when n is too big, nothing for 0, and leaves memory unchanged"""
    with tempfile.TemporaryDirectory() as folder:
        memory = filled(m, folder)
        got = memory.latest(10)
        assert got == [LAPTOP, DISPLAY, TV, WATCH], f"latest(10) gave {slugs(got)}; expected all four, newest first"
        got = memory.latest(0)
        assert got == [], f"latest(0) gave {slugs(got)}; expected []. Careful: items[-0:] is the whole list"
        assert memory.opportunities == [WATCH, TV, DISPLAY, LAPTOP], \
            f"after latest, memory.opportunities is {slugs(memory.opportunities)}; latest must not change it"


def first_difference(got, want):
    """The first cell where two tables differ, in a few words."""
    if not isinstance(got, list) or len(got) != len(want):
        return f"gave {got!r:.80}; expected {len(want)} rows"
    for r, (row, wanted) in enumerate(zip(got, want)):
        if not isinstance(row, list) or len(row) != len(wanted):
            return f"row {r} is {row!r:.80}; expected a list of {len(wanted)} items"
        for c, (cell, wanted_cell) in enumerate(zip(row, wanted)):
            if cell != wanted_cell:
                return f"in row {r}, item {c} is {cell!r}; expected {wanted_cell!r}"
    return "matches"


def test_table_for(m):
    """table_for gives description, price, estimate, discount and url for each opportunity"""
    got = need(m, "table_for")([WATCH, TV])
    want = [["47mm LTE titanium smartwatch", "$350.00", "$773.81", "$423.81", "https://deals.example.com/watch"],
            ["55-inch 4K UHD smart TV", "$178.00", "$300.00", "$122.00", "https://deals.example.com/tv"]]
    assert got == want, f"table_for([watch, tv]): {first_difference(got, want)}"
'''


if __name__ == "__main__":
    sys.exit(main())
