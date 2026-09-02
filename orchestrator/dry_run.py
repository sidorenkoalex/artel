"""Команда `acceptance-dry-run`: сухой прогон приёмки — предпросмотр без
исполнения (tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/SPEC.md).

Read-only, тот же класс команд, что `status`/`log` (требование 3): не
запускает unittest, не пишет в журнал задачи и БД, не меняет `status`,
не берёт lease. Чтение `SPEC.md` и `tasks/<id>/acceptance_tests/` —
ВСЕГДА с ВЕТКИ задачи через git (`gitcmd.branch_exists`/
`gitcmd.ls_tree_files`/`gitcmd.show`, инвариант 28), никогда с диска
рабочей копии — безусловно, не только при «чужом чекауте»: диск не
источник вовсе, ничего не материализуется на нём (требование 5).

Разбор тестовых файлов и AC-маркеров — целиком через
`scripts/guard.py::scan_ac_content` (ядро `scan_acceptance_tests`) над
текстом, прочитанным `gitcmd.show` (требование 2) — тот же приём, что
`orchestrator/fsm.py::_tests_writing_ac_state` использует для «чужой
ветки»: расхождение источников разбора между этой командой и переходами
FSM/сводкой гейта acceptance (`orchestrator/acceptance.py::summary`)
невозможно по построению.
"""
import sys
from pathlib import Path

from scripts import guard

from . import gitcmd, store

DRY_RUN_MARKER = "сухой прогон — не является прохождением приёмки"


def _is_test_file(path: str) -> bool:
    """`test_*.py` под `acceptance_tests/` — тот же фильтр, что
    `guard.scan_acceptance_tests` держит для рабочей копии
    (`tests_dir.rglob("test_*.py")`), здесь — по путям `git ls-tree`."""
    name = Path(path).name
    return name.startswith("test_") and name.endswith(".py")


def cmd_acceptance_dry_run(task_id: str) -> None:
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    t = store.get_task(conn, task_id)
    branch = t["branch"]

    if not gitcmd.branch_exists(branch):
        sys.exit(f"[{task_id}] сухой прогон приёмки: отказ — ветка задачи "
                 f"{branch!r} не существует, приёмочные тесты недоступны")

    prefix = f"tasks/{task_id}/acceptance_tests"
    paths = gitcmd.ls_tree_files(branch, prefix)
    test_paths = sorted(p for p in (paths or []) if _is_test_file(p))
    if not test_paths:
        sys.exit(f"[{task_id}] сухой прогон приёмки: отказ — на ветке "
                 f"{branch!r} нет каталога {prefix}/ (или в нём нет "
                 f"тестовых файлов) — приёмочные тесты не заведены")

    spec_rel = f"tasks/{task_id}/SPEC.md"
    spec_text, spec_reason = gitcmd.show(branch, spec_rel)
    if spec_text is None:
        sys.exit(f"[{task_id}] сухой прогон приёмки: отказ — SPEC.md "
                 f"ветки {branch!r} не прочитан: {spec_reason}")

    sources: list[str] = []
    file_methods: list[tuple[str, list[str]]] = []
    for path in test_paths:
        text, _ = gitcmd.show(branch, path)
        if text is None:
            continue
        sources.append(text)
        file_methods.append((Path(path).name, guard.TEST_METHOD.findall(text)))

    tested, markers = guard.scan_ac_content(sources)
    ac_numbers = sorted(int(n) for n in guard.AC_ITEM.findall(
        guard.section_body(spec_text, "Критерии приёмки")))

    print(f"[{task_id}] {DRY_RUN_MARKER} (ветка {branch})")
    print()
    print(f"Тестовые файлы и методы ({len(file_methods)} файл(ов)):")
    for name, methods in file_methods:
        print(f"  {name}")
        for method in methods:
            print(f"    {method}")
    print()
    print(f"AC-маркеры manual/skip/escalate ({len(markers)}):")
    if markers:
        for n in sorted(markers):
            kind, reason = markers[n]
            tail = f" — {reason}" if reason else ""
            print(f"  AC-{n}: {kind}{tail}")
    else:
        print("  нет")
    print()
    print("Трассируемость AC -> покрытие:")
    uncovered = []
    for n in ac_numbers:
        if n in tested:
            print(f"  AC-{n}: покрыт тестом")
        elif n in markers:
            kind, reason = markers[n]
            tail = f" — {reason}" if reason else ""
            print(f"  AC-{n}: покрыт пометкой {kind}{tail}")
        else:
            print(f"  AC-{n}: не покрыт")
            uncovered.append(n)
    if uncovered:
        names = ", ".join(f"AC-{n}" for n in uncovered)
        print(f"  непокрытые AC: {names}")
    else:
        print("  непокрытых AC нет")
    print()
    print(DRY_RUN_MARKER)
