#!/usr/bin/env python3
"""Guard: валидатор СТРУКТУРЫ артефактов задач (frontmatter + обязательные
секции). Содержательность не проверяет — это работа гейтов и людей (§04).

Использование:
    python3 scripts/guard.py tasks/T001/SPEC.md [ещё файлы...]
    python3 scripts/guard.py --all          # все артефакты в tasks/
Выход: 0 — ок, 1 — есть нарушения (список в stdout).
"""
import re
import sys
from pathlib import Path

REQUIRED_META = {"task", "type", "author_role", "status"}

RULES = {
    "spec": {
        "sections": ["Контекст", "Требования", "Критерии приёмки", "Не входит"],
        "statuses": {"draft", "ready", "approved"},
    },
    "plan": {
        "sections": ["Подход", "Шаги", "Покрытие требований",
                     "Влияние на систему"],  # принцип целостности (ADR-0002)
        "statuses": {"draft", "ready", "approved"},
    },
    "review": {
        "sections": ["Соответствие SPEC", "Замечания", "Вердикт"],
        "statuses": {"draft", "approved", "changes_requested", "escalate"},
    },
    "test_report": {
        "sections": ["Матрица критериев", "Вердикт"],
        "statuses": {"draft", "passed", "failed"},
    },
}


def parse_frontmatter(text: str) -> dict | None:
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.split("#")[0].strip()
    return meta


def check(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")

    meta = parse_frontmatter(text)
    if meta is None:
        return [f"{path}: нет frontmatter (--- ... ---)"]

    missing = REQUIRED_META - meta.keys()
    if missing:
        errors.append(f"{path}: frontmatter без полей: {', '.join(sorted(missing))}")

    atype = meta.get("type", "")
    rules = RULES.get(atype)
    if rules is None:
        errors.append(f"{path}: неизвестный type '{atype}' (ожидается: {', '.join(RULES)})")
        return errors

    status = meta.get("status", "")
    if status not in rules["statuses"]:
        errors.append(
            f"{path}: недопустимый status '{status}' для {atype} "
            f"(валидные: {', '.join(sorted(rules['statuses']))})"
        )

    headers = set(re.findall(r"^##\s+(.+?)\s*$", text, re.M))
    for section in rules["sections"]:
        if section not in headers:
            errors.append(f"{path}: отсутствует обязательная секция '## {section}'")

    if meta.get("task") in ("", "TASK_ID"):
        errors.append(f"{path}: поле task не заполнено (осталось TASK_ID)")

    return errors


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1

    if args == ["--all"]:
        files = sorted(Path("tasks").rglob("*.md"))
    else:
        files = [Path(a) for a in args]

    all_errors: list[str] = []
    for f in files:
        if not f.exists():
            all_errors.append(f"{f}: файл не найден")
            continue
        all_errors.extend(check(f))

    if all_errors:
        print("GUARD: нарушения структуры артефактов:")
        for e in all_errors:
            print(f"  - {e}")
        return 1
    print(f"GUARD: ок ({len(files)} файлов)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
