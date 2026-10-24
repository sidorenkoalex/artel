"""Строки падений из логов патчей `mutation-run` задачи 01M5R0DPNHZ7N8YBXMH375SMEE.

python3 failines.py <прогоны «до» через запятую> [<прогоны «после» через запятую>]

Для каждого лога `<id>-mutation-run-<n>-p<nnn>.log`: секции FAILURES
(`_ <Класс>.<метод> (…) _` / `_ <функция> _`), в секции — последний кадр
`tests/<файл>.py:<строка>: <исключение>`. Печатает строки PLAN:
«до → после» на пару (мутация, исходный тест), если есть оба прогона;
иначе только «до». Неутвердительные падения (не AssertionError) и падения
в методах подготовки помечаются в конце строки `[!…]`."""
import ast
import re
import subprocess
import sys
from pathlib import Path

TASK = "01M5R0DPNHZ7N8YBXMH375SMEE"
LOGS = Path("/Users/al.sidorenko/projects/artel/.artel/logs/suite-run") / TASK
ROOT = Path("/Users/al.sidorenko/projects/artel/.artel/projects/artel/worktrees") / TASK
HEADER = re.compile(r"^_+ (?:(\w+)\.)?(test\w*)(?:\[[^\]]*\])?(?: \(.*\))? _+$")
FRAME = re.compile(r"^(tests/[\w./-]+\.py):(\d+): (\w+)")
BASE = "72d52fd367828949767e234ecbe9b0cc79851084"
PREP = ("setUp", "direct_task", "verifying_task", "rewrite_passed", "in_dev_task",
        "artel_in_dev_task", "operator_mandate")
OLD = {"tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py": "test_merge_outcome_module.py",
       "tests/test_outcome_integrity_added_lines.py": "test_outcome_gate_module.py"}


def failures(log: Path) -> list:
    """[(класс или "", тест, файл, строка, исключение)] секций FAILURES."""
    out, current, frame = [], None, None
    for line in log.read_text(encoding="utf-8", errors="replace").split("\n"):
        m = HEADER.match(line)
        if m:
            if current and frame:
                out.append((*current, *frame))
            current, frame = (m.group(1) or "", m.group(2)), None
            continue
        if line.startswith("=") and "short test summary" in line:
            break
        f = FRAME.match(line)
        if f and current:
            frame = (f.group(1), int(f.group(2)), f.group(3))
    if current and frame:
        out.append((*current, *frame))
    return out


def chain(text: str, line: int) -> list:
    tree = ast.parse(text)
    return [n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.lineno <= line <= (n.end_lineno or n.lineno)]


def text_of(path: str, before: bool) -> str:
    if before:
        return subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE}:{path}"],
                              capture_output=True, text=True).stdout
    return (ROOT / path).read_text(encoding="utf-8")


def by_patch(runs: list) -> dict:
    found = {}
    for run in runs:
        for log in sorted(LOGS.glob(f"{TASK}-mutation-run-{run}-p*.log")):
            number = int(log.stem.rsplit("-p", 1)[1])
            found[number] = failures(log)
    return found


def mark(path, line, exc, before) -> str:
    names = chain(text_of(path, before), line)
    bad = []
    if exc != "AssertionError":
        bad.append(exc)
    if any(n in PREP for n in names):
        bad.append("подготовка")
    return f" [!{', '.join(bad)}]" if bad else ""


def main() -> None:
    before = by_patch(sys.argv[1].split(","))
    after = by_patch(sys.argv[2].split(",")) if len(sys.argv) > 2 else {}
    for number in sorted(before):
        seen = set()
        for cls, test, path, line, exc in before[number]:
            key = (cls, test)
            if key in seen:
                continue
            seen.add(key)
            text = (f"- mutation-{number:03d}: «до» `{cls}::{test}` — `{path}:{line}`"
                    + mark(path, line, exc, True))
            if after:
                hits = [a for a in after.get(number, []) if a[1] == test]
                if hits:
                    _c, _t, apath, aline, aexc = hits[0]
                    target = OLD.get(path, "test_merge_outcome_module.py")
                    text += (f" → «после» `{target}::{test}` — `{apath}:{aline}`"
                             + mark(apath, aline, aexc, False))
                else:
                    text += " → «после» [!нет падения функции]"
            print(text)


if __name__ == "__main__":
    main()
