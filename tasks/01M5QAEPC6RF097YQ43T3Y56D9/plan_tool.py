"""Временная сборка PLAN.md из plan_head.txt, копий --copy-table и логов
патчей mutation-run (удаляется к концу работы над PLAN).

python3 plan_tool.py "<до: номера прогонов через запятую>" "<после: …>"
"""
import ast
import re
import subprocess
import sys
from pathlib import Path

D = Path("/Users/al.sidorenko/projects/artel/.artel/projects/artel/tasks/01M5QAEPC6RF097YQ43T3Y56D9")
TASK = "01M5QAEPC6RF097YQ43T3Y56D9"
LOGS = Path("/Users/al.sidorenko/projects/artel/.artel/logs/suite-run") / TASK
WT = Path("/Users/al.sidorenko/projects/artel/.artel/projects/artel/worktrees") / TASK
sys.dont_write_bytecode = True  # без __pycache__ в каталоге документов
sys.path.insert(0, str(D / "acceptance_tests"))
import _plan  # noqa: E402

BASE = "579a38199ce682917b9d5e40f15ac95cde4aaddc"
HEADER = re.compile(r"^_+ ([A-Za-z]\S*)(?: \(.*\)| \[.*\])? _+$")
FRAME = re.compile(r"^(tests/[\w./-]+\.py):(\d+):")


def show(rev, path):
    res = subprocess.run(["git", "-C", str(WT), "show", f"{rev}:{path}"],
                         capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else None


def failures(run_no, patch_no):
    """{имя узла из заголовка: [(файл, строка) кадров по порядку]}."""
    path = LOGS / f"{TASK}-mutation-run-{run_no}-p{patch_no:03d}.log"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    if "= FAILURES =" not in text:
        return {}
    text = text[text.index("= FAILURES ="):]
    end = text.find("short test summary info")
    text = text[:end] if end > 0 else text
    blocks, current = {}, None
    for line in text.splitlines():
        m = HEADER.match(line)
        if m and not line.startswith("_ _"):
            current = m.group(1).replace(".", "::")
            blocks.setdefault(current, [])
            blocks[current].append([])
            continue
        f = FRAME.match(line)
        if f and current:
            blocks[current][-1].append((f.group(1), int(f.group(2))))
    return blocks


def good_site(texts, path, line):
    text = texts.get(path)
    if text is None:
        return False
    inside, chain = _plan.assertion_site(text, line)
    return bool(inside and chain) and not _plan.in_preparation(chain)


def table_runs(nums):
    found = []
    for n in nums:
        text = (D / f"mutation-run-{n}.tsv").read_text(encoding="utf-8")
        tables, errors = _plan.tables(text.rstrip("\n"))
        assert not errors and len(tables) == 1, (n, errors)
        found.append((n, text.rstrip("\n"), tables[0]))
    return found


def part_label(table):
    nums = sorted(table.patches)
    return f"`--patches {nums[0]}-{nums[-1]}`, рабочих процессов {table.workers}"


def main():
    before_runs = [int(x) for x in sys.argv[1].split(",") if x]
    after_runs = [int(x) for x in sys.argv[2].split(",") if x] if len(sys.argv) > 2 else []
    head = (D / "plan_head.txt").read_text(encoding="utf-8")
    base_texts = {p: show(BASE, p) for p in (_plan.OUTCOME_FILE, _plan.SANDBOX_FILE)}
    head_texts = {_plan.NEW_FILE: show("HEAD", _plan.NEW_FILE)}
    problems = []

    before = table_runs(before_runs)
    out = []
    for k, (n, text, table) in enumerate(before, 1):
        out.append(f"Прогон №{n} ({part_label(table)}):\n\n{text}\n")
    before_text = "\n".join(out)

    after = table_runs(after_runs)
    out = []
    for k, (n, text, table) in enumerate(after, 1):
        out.append(f"Прогон №{n} ({part_label(table)}). Перед стартом части "
                   f"`git status --porcelain -- orchestrator/` рабочей копии — "
                   f"пустой вывод.\n\n{text}\n")
    after_text = "\n".join(out) if out else "Прогонов «после» ещё нет.\n"

    # строки падений
    fails = []
    last_before = {}
    for n, _text, table in before:
        for number, outcome, nodes in table.rows:
            last_before[number] = (n, outcome, nodes)
    last_after = {}
    for n, _text, table in after:
        for number, outcome, nodes in table.rows:
            last_after[number] = (n, outcome, nodes)
    for number in sorted(last_before):
        n, outcome, nodes = last_before[number]
        if outcome != _plan.KILLED:
            continue
        blocks = failures(n, number)
        found_before = 0
        for node in nodes:
            key = _plan.node_key(node)
            for frames in blocks.get(key, []):
                if frames and good_site(base_texts, *frames[-1]):
                    path, line = frames[-1]
                    fails.append(f"- mutation-{number:03d} «до»: `{key}` — "
                                 f"`{path}:{line}`")
                    found_before += 1
                    break
        if not found_before:
            problems.append(f"мутация {number} «до»: нет годной строки падения")
        if number not in last_after:
            continue
        n2, outcome2, nodes2 = last_after[number]
        if outcome2 != _plan.KILLED:
            problems.append(f"мутация {number} «после»: {outcome2}")
            continue
        blocks2 = failures(n2, number)
        found_after = 0
        for node in nodes2:
            func, variant = _plan.after_node_parts(node)
            for frames in blocks2.get(func, []):
                if frames and good_site(head_texts, *frames[-1]):
                    path, line = frames[-1]
                    fails.append(f"- mutation-{number:03d} «после»: "
                                 f"`test_outcome_gate_module.py::{func}` — "
                                 f"`{path}:{line}`")
                    found_after += 1
                    break
        if not found_after:
            problems.append(f"мутация {number} «после»: нет годной строки падения")
    fails_text = "\n".join(fails) + "\n"

    src = base_texts[_plan.OUTCOME_FILE]
    mapping = []
    for t in _plan.base_tests(_plan.OUTCOME_FILE, src):
        mapping.append(f"- `{t.key}` → `test_outcome_gate_module.py::{t.func.name}`")
    map_text = "\n".join(mapping) + "\n"

    new = head_texts[_plan.NEW_FILE]
    counts = {
        "SRC_TESTS": str(len(_plan.base_tests(_plan.OUTCOME_FILE, src))),
        "SRC_LINES": str(src.count("\n")),
        "MOD_BASE_TESTS": str(len(_plan.module_tests(ast.parse(show(BASE, _plan.NEW_FILE)))))
        , "MOD_BASE_LINES": str(show(BASE, _plan.NEW_FILE).count("\n")),
        "NEW_TESTS": str(len(_plan.module_tests(ast.parse(new)))),
        "NEW_LINES": str(new.count("\n")),
    }
    plan = (head.replace("@@BEFORE@@", before_text)
            .replace("@@AFTER@@", after_text)
            .replace("@@FAILS@@", fails_text)
            .replace("@@MAP@@", map_text))
    def control(nums):
        found = []
        for n in nums:
            path = LOGS / f"{TASK}-mutation-run-{n}-control.log"
            m = re.findall(r" in (\d+(?:\.\d+)?)s", path.read_text(encoding="utf-8",
                                                                  errors="replace"))
            found.append(f"{m[-1]} с (прогон №{n})" if m else f"нет итога (прогон №{n})")
        return ", ".join(found) or "ещё не было"
    counts["TIMES"] = (f"- Время контрольных прогонов `mutation-run` (без патча, "
                       f"`auto` рабочих процессов): «до» — {control(before_runs)}; "
                       f"«после» — {control(after_runs)}.")
    for k, v in counts.items():
        plan = plan.replace(f"@@{k}@@", v)
    (D / "PLAN.md").write_text(plan, encoding="utf-8")
    print("\n".join(problems) or "строки падений: все на месте")


main()
