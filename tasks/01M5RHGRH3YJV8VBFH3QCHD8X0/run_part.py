"""Одна часть `mutation-run` задачи 01M5RHGRH3YJV8VBFH3QCHD8X0 одним вызовом
команды пульта (`--wait 5` — отчёт тем же вызовом), затем копия таблицы —
в PLAN.md (`add_table.py`), только если вывод несёт итоговую строку.
Ожидания замка сверх `--wait-lock 4` и повторов здесь нет.

python3 run_part.py before 12-12
python3 run_part.py after 1-11
"""
import re
import subprocess
import sys

TASK = "01M5RHGRH3YJV8VBFH3QCHD8X0"
WT = f"/Users/al.sidorenko/projects/artel/.artel/projects/artel/worktrees/{TASK}"
ARTEL = "/Users/al.sidorenko/projects/artel/orchestrator/artel.py"
DOCS = f"/Users/al.sidorenko/projects/artel/.artel/projects/artel/tasks/{TASK}"
BEFORE = ",".join(f"tests/{n}.py" for n in (
    "test_01m44ep0d47f498tee08mngbyt_answer_merge_after",
    "test_01m44ep0d47f498tee08mngbyt_guard_merge_after",
    "test_01m44ep0d47f498tee08mngbyt_plan_merge_after",
    "test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after",
    "test_01m44ep0d47f498tee08mngbyt_status_show_merge_after",
    "test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after"))
AFTER = "tests/test_merge_after_module.py"


def main(kind: str, patches: str):
    status = ""
    if kind == "after":
        status = subprocess.run(["git", "status", "--porcelain", "--",
                                 "orchestrator/", "scripts/"], cwd=WT,
                                capture_output=True, text=True).stdout
        if status.strip():
            sys.exit(f"git status orchestrator/ scripts/ не пуст:\n{status}")
    ref, tests = ("base", BEFORE) if kind == "before" else ("worktree", AFTER)
    res = subprocess.run(["python3", ARTEL, "mutation-run", TASK, "--ref", ref,
                          "--tests", tests, "--copy-table", "--wait-lock", "4",
                          "--patches", patches, "--wait", "5"],
                         cwd=WT, capture_output=True, text=True)
    out = res.stdout + res.stderr
    print(out[-6000:])
    final = re.search(r"mutation-run №(\d+): прогнано патчей", out)
    if not final:
        sys.exit("итоговой строки нет — таблица в PLAN не дописана")
    subprocess.run(["python3", f"{DOCS}/add_table.py", f"--{kind}", final.group(1)],
                   check=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
