"""Сборщик PLAN.md задачи 01M5R0AFX9Z1GA1DG5XV73JRTE: постоянный текст
(plan_static.md рядом) + строки мутаций, строки падения «до → после» из
логов прогонов mutation-run и таблицы из копий `mutation-run-<n>.tsv`.

python3 make_plan.py --before 1,2,3,4,5 --after 6,7,8,9,10
"""
import argparse
import ast
import glob
import pathlib
import re
import subprocess
import sys

DOCS = pathlib.Path(__file__).resolve().parent
TASK = DOCS.name
WT = DOCS.parent.parent / "worktrees" / TASK
LOGS = pathlib.Path(f"/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/{TASK}")
BASE = "72d52fd367828949767e234ecbe9b0cc79851084"
sys.path.insert(0, str(DOCS / "acceptance_tests"))
import _plan  # noqa: E402

M = "test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project"
SRC = {"AcquireByProjectTest": _plan.MUTEX, "ReleaseAndHeartbeatTest": _plan.MUTEX,
       "StoreMergeLockTest": _plan.MUTEX, "QueueByProjectTest": _plan.MUTEX,
       "WaitTextsByProjectTest": _plan.MUTEX}

HEAD_RE = re.compile(r"^_+ (\S.*?) _+$")
PLACE = re.compile(r"^(tests/\S+\.py):(\d+): (\w+)")


def git(*args):
    return subprocess.run(["git", "-C", str(WT), *args], capture_output=True,
                          text=True).stdout


def fail_places(run: int) -> dict:
    """{патч: {тест (Класс::метод или функция): [(файл, строка)]}}."""
    out = {}
    for path in sorted(glob.glob(f"{LOGS}/{TASK}-mutation-run-{run}-p*.log")):
        patch = int(path.rsplit("-p", 1)[1].split(".")[0])
        found = out.setdefault(patch, {})
        current = None
        pending = None
        for line in open(path, encoding="utf-8", errors="replace"):
            line = line.rstrip("\n")
            head = HEAD_RE.match(line)
            if head:
                name = head.group(1).split(" (", 1)[0].split("[", 1)[0]
                current = name.replace(".", "::")
                pending = None
                continue
            place = PLACE.match(line)
            item = None
            if place and current and place.group(3) == "AssertionError":
                item = (place.group(1), int(place.group(2)))
            elif place and current and place.group(3) == "in":
                # Кадр помощника unittest-утверждения: место — последний кадр
                # перед строкой «E   AssertionError».
                pending = (place.group(1), int(place.group(2)))
            elif pending and current and line.startswith("E   AssertionError"):
                item, pending = pending, None
            if item and item not in found.setdefault(current, []):
                found[current].append(item)
    return out


def control_seconds(run: int) -> str:
    path = LOGS / f"{TASK}-mutation-run-{run}-control.log"
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    hit = re.findall(r"(\d+) passed[^\n]* in ([\d.]+)s", text)
    return f"{hit[-1][0]} тестов за {hit[-1][1].replace('.', ',')} с" if hit else "?"


def table_text(run: int) -> str:
    return (DOCS / f"mutation-run-{run}.tsv").read_text(encoding="utf-8").rstrip("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default="")
    ap.add_argument("--after", default="")
    ap.add_argument("--status", default="draft")
    args = ap.parse_args()
    before_runs = [int(x) for x in args.before.split(",") if x]
    after_runs = [int(x) for x in args.after.split(",") if x]
    sys.path.insert(0, str(DOCS))
    import plan_data as data  # noqa: E402

    base_trees = {p: ast.parse(git("show", f"{BASE}:{p}")) for p in _plan.SOURCE_FILES}
    head_trees = {p: ast.parse(git("show", f"HEAD:{p}")) for p in _plan.MODULE_FILES}
    tests = {}
    for p in _plan.SOURCE_FILES:
        for t in _plan.base_tests(p, git("show", f"{BASE}:{p}")):
            tests[t.key] = t
    prep = _plan.prep_line_nodes(base_trees)

    def before_form(test, line):
        node = _plan.assertion_at(base_trees[test.path], line)
        if node is None or node.lineno in {n.lineno for n in prep.get(test.path, [])}:
            return None
        if not _plan.site_ok(base_trees[test.path], line, test.func,
                             ("setUp", *_plan.PREP_HELPERS)):
            return None
        return _plan.normal_form(node, _plan.base_canon(base_trees[test.path],
                                                        test.path, test.cls))

    def after_form(test, path, func_name, line):
        tree = head_trees[path]
        funcs = _plan.module_functions(tree)
        func = funcs.get(func_name)
        if func is None:
            return None
        base_c = _plan.base_canon(base_trees[test.path], test.path, test.cls)
        canon = _plan.new_canon(func, test.func, base_c)
        forms = {_plan.normal_form(n, base_c) for n in _plan.self_assertions(test.func)
                 if n.lineno in {p.lineno for p in prep.get(test.path, [])}}
        if not _plan.site_ok(tree, line, func, _plan.PREP_HELPERS, forms, canon):
            return None
        node = _plan.assertion_at(tree, line)
        site = _plan.function_chain(tree, line)[0]
        site_canon = canon if site is func else _plan.Canon(
            {a.arg for a in site.args.args}, {})
        return _plan.normal_form(node, site_canon)

    before_rows, after_rows = {}, {}
    before_places, after_places = {}, {}
    for run in before_runs:
        before_rows.update(_plan.last_rows(_plan.tables(table_text(run))[0]))
        before_places.update(fail_places(run))
    for run in after_runs:
        after_rows.update(_plan.last_rows(_plan.tables(table_text(run))[0]))
        after_places.update(fail_places(run))

    kill_lines, problems = [], []
    for n in sorted(before_rows):
        outcome, nodes = before_rows[n]
        if outcome != _plan.KILLED:
            continue
        after_outcome, after_nodes = after_rows.get(n, ("нет строки", []))
        after_funcs = {_plan.after_node(x) for x in after_nodes}
        good = False
        for node in nodes:
            key = _plan.node_key(node)
            test = tests.get(key)
            if test is None:
                continue
            places = before_places.get(n, {}).get(key, [])
            target = test.target
            func_places = [pl for pl in after_places.get(n, {}).get(test.name, [])
                           if pl[0] == target]
            in_after = (target, test.name) in after_funcs
            pair = None
            for bp in places:
                bf = before_form(test, bp[1])
                if bf is None:
                    continue
                for ap_ in func_places:
                    if after_form(test, target, test.name, ap_[1]) == bf:
                        pair = (bp, ap_)
                        break
                if pair:
                    break
            stem = pathlib.Path(target).name
            if pair:
                good = True
                kill_lines.append(
                    f"- mutation-{n:03d}: {key} — {pair[0][0]}:{pair[0][1]} → "
                    f"{stem}::{test.name} — {pair[1][0]}:{pair[1][1]} (то же утверждение)")
            else:
                bp = places[0] if places else None
                ap_ = func_places[0] if func_places else None
                why = "только утверждением подготовки — не доказательство" if places == [] or all(
                    before_form(test, p[1]) is None for p in places) else "строка формы не найдена"
                kill_lines.append(
                    f"- mutation-{n:03d}: {key}"
                    + (f" — {bp[0]}:{bp[1]}" if bp else "")
                    + f" → {stem}::{test.name}"
                    + (f" — {ap_[0]}:{ap_[1]}" if ap_ else "")
                    + f" ({why})")
            if not in_after:
                problems.append(f"мутация {n}: {key} убил «до», функция не среди убийц «после» "
                                f"({after_outcome})")
        if not good:
            problems.append(f"мутация {n}: нет строки с тем же утверждением")
    for n in sorted(after_rows):
        if after_rows[n][0] != before_rows.get(n, ("?",))[0]:
            problems.append(f"мутация {n}: «до» {before_rows.get(n, ('?',))[0]}, "
                            f"«после» {after_rows[n][0]}")

    head_texts = {p: git("show", f"HEAD:{p}") for p in _plan.MODULE_FILES}
    counts = {p: len(_plan.module_tests(ast.parse(t))) for p, t in head_texts.items()}
    lines = {p: t.count("\n") for p, t in head_texts.items()}

    before_tables = []
    for run in before_runs:
        before_tables.append(f"Часть №{run}:\n\n```\n{table_text(run)}\n```\n")
    after_tables = []
    for run in after_runs:
        after_tables.append(
            f"Перед частью №{run}: `git status --porcelain -- orchestrator/` — "
            f"{data.STATUS_BEFORE.get(run, 'вывод пуст')}\n\n```\n{table_text(run)}\n```\n")

    text = (DOCS / "plan_static.txt").read_text(encoding="utf-8")
    text = text.replace("{{STATUS}}", args.status)
    text = text.replace("{{PATCHES}}", "\n".join(data.patch_lines()))
    text = text.replace("{{SEEDS}}", "\n".join(data.seed_lines()))
    text = text.replace("{{KILLS}}", "\n".join(kill_lines) or "(прогонов «после» ещё нет)")
    text = text.replace("{{BEFORE}}", "\n".join(before_tables) or "(частей ещё нет)")
    text = text.replace("{{AFTER}}", "\n".join(after_tables) or "(частей ещё нет)")
    text = text.replace("{{COUNTS}}", (
        f"- После свода (HEAD): `tests/test_merge_lock_module.py` — "
        f"{counts[_plan.LOCK_MODULE]} тестов, {lines[_plan.LOCK_MODULE]} строк; "
        f"`tests/test_merge_queue.py` — {counts[_plan.QUEUE_MODULE]} тестов, "
        f"{lines[_plan.QUEUE_MODULE]} строк; `tests/test_merge_after_module.py` — "
        f"{counts[_plan.AFTER_MODULE]} тестов, {lines[_plan.AFTER_MODULE]} строк; "
        f"всего {sum(counts.values())} тестов, {sum(lines.values())} строк."))
    controls = [f"«до» №{r}: {control_seconds(r)}" for r in before_runs] + \
        [f"«после» №{r}: {control_seconds(r)}" for r in after_runs]
    text = text.replace("{{TIMES}}", "; ".join(controls) or "?")
    (DOCS / "PLAN.md").write_text(text, encoding="utf-8")
    print("\n".join(problems) or "согласованность «до → после»: расхождений нет")


if __name__ == "__main__":
    main()
