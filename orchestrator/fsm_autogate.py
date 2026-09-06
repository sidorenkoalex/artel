"""Автогейт acceptance по политике gates.yaml (ADR-0007, SPEC T066).
Перенесено из orchestrator/fsm.py без изменения поведения (T091,
декомпозиция диспетчеров fsm/runner). Условие «а» (планка и её
AC-пометки) переведено на чтение через источник артефактов задачи
(SPEC 01M1NBWWPJMHKJMYXRDCM0W0C5) — каталог `tasks/<id>/acceptance_tests/`
на диске рабочей копии после переноса артефактов в артефактную ветку
(A7) остаётся пустым, автогейт видел только это и не мог отличить
«планки нет» от «планка живёт в ветке».
"""
from pathlib import Path

from scripts import guard

from . import (acceptance, artifact_source, budget, ci, fixation, gates,
              gitcmd, store, workspace)

AUTOGATE_PASS_MESSAGE = "acceptance пройден автогейтом (политика gates.yaml)"


def _autogate_conditions(conn, task_id: str, t, acc_tdir: Path,
                         iteration: int) -> tuple[list[str], str | None]:
    """(выполненные условия, причина первого невыполненного).

    Короткое замыкание на первом несовпадении — SPEC требование 4 просит
    ОДНУ строку причины, не собранный список всех отказов сразу. Условие
    "б" (приёмочные тесты задачи зелёные) сюда не входит отдельной
    проверкой: к этой точке код уже гарантированно прошёл `acceptance.run`
    зелёным (иначе переход не добрался бы до состояния `acceptance`
    вообще) — только записывается в перечень как выполненное.

    Условие "а" (каталог `acceptance_tests/` и его AC-пометки
    manual/skip/ci) читается через источник артефактов задачи
    (`artifact_source.resolve` + `gitcmd.ls_tree_files`/`gitcmd.show`,
    SPEC 01M1NBWWPJMHKJMYXRDCM0W0C5) — тем же приёмом, что уже несёт
    `fsm._tests_writing_ac_state` (SPEC T031): разбираются ВСЕ `*.py`
    файлы каталога, не только `test_*.py` (расходится с дисковым
    `guard.scan_acceptance_tests`, но повторяет прецедент, а не заводит
    третий вариант разбора), общим ядром `guard.scan_ac_content`.
    `acc_tdir` (диск рабочей копии) условия "а" больше не касается —
    параметр сохранён ради сигнатуры, которую использует остальной код
    функции (условия б/в/г/д, эта задача их не меняет) и вызывающий код.

    Пометка `ci` (01M1SHJTT0V516BWHYXWS50F3G) — отдельная от
    manual/skip категория: не блокирует автогейт самим фактом
    присутствия, а исполняется по зелёному CI ГОЛОВЫ КОДОВОЙ ветки
    задачи (`t["branch"]`, не той `branch` артефактов чуть выше) —
    `ci.verifying_status`, та же функция, что уже опрашивает
    `orchestrator/fsm_advance.py::verifying`.
    """
    ok: list[str] = []

    branch, _ = artifact_source.resolve(conn, task_id)
    branch_sha = gitcmd.branch_head_sha(branch)
    source_note = f"источник планки: ветка {branch}, sha {branch_sha}"

    tests_rel = f"tasks/{task_id}/acceptance_tests"
    paths = gitcmd.ls_tree_files(branch, tests_rel) or []
    py_paths = [p for p in paths if p.endswith(".py")]
    if not py_paths:
        return ok, ("автогейт: каталог приёмочных тестов пуст или "
                    f"отсутствует ({source_note})")
    sources = []
    for p in py_paths:
        text, _ = gitcmd.show(branch, p)
        if text is not None:
            sources.append(text)
    _, markers = guard.scan_ac_content(sources)
    manual_ns = sorted(n for n, (kind, _) in markers.items() if kind == "manual")
    skip_ns = sorted(n for n, (kind, _) in markers.items() if kind == "skip")
    if manual_ns:
        return ok, (f"автогейт: критерии manual — "
                    f"{', '.join(f'AC-{n}' for n in manual_ns)} "
                    f"({source_note})")
    if skip_ns:
        return ok, (f"автогейт: критерии skip — "
                    f"{', '.join(f'AC-{n}' for n in skip_ns)} "
                    f"({source_note})")
    # Пометка `ci` (01M1SHJTT0V516BWHYXWS50F3G, требования 2-3): не
    # manual/skip — отдельная категория (fail-closed: не смешивается со
    # списками выше). Исполнена, если CI ГОЛОВЫ КОДОВОЙ ветки задачи
    # (`t["branch"]`, не артефактной) зелёный — `ci.verifying_status`
    # сама берёт sha из головы этой ветки и спрашивает CI именно этого
    # sha, так что «sha головы обязан совпасть со sha, для которого CI
    # зелёный» (требование 2) — свойство самой этой функции, не
    # отдельная проверка здесь.
    ci_ns = sorted(n for n, (kind, _) in markers.items() if kind == "ci")
    if ci_ns:
        ci_kind, ci_note = ci.verifying_status(t["branch"])
        if ci_kind != ci.VERIFYING_GREEN:
            return ok, (f"автогейт: критерий ci не пройден — "
                        f"{', '.join(f'AC-{n}' for n in ci_ns)} "
                        f"({ci_note}; {source_note})")
        ok.append(f"критерии ci подтверждены зелёным CI кодовой ветки — "
                  f"{', '.join(f'AC-{n}' for n in ci_ns)} ({ci_note})")
    ok.append("каталог приёмочных тестов: 0 manual, 0 skip критериев")
    ok.append("приёмочные тесты задачи зелёные")
    ok.append(source_note)

    wt_root = (workspace.path(task_id)
              if workspace.on_task_branch(task_id, t["branch"]) is True
              else None)
    if wt_root is None:
        return ok, ("автогейт: полный набор tests/ не проверен — worktree "
                    "задачи не заведён")
    green, _ = acceptance.run_full_suite(wt_root)
    if not green:
        return ok, "автогейт: полный набор tests/ красный"
    ok.append("полный набор tests/ в worktree ветки зелёный")

    if budget.budget_block(t) is not None:
        return ok, "автогейт: бюджет задачи исчерпан"
    ok.append(f"бюджет задачи не превышен (${t['spent_usd'] or 0.0:.2f} из "
              f"${t['budget_usd'] or 0.0:.2f})")

    ok.append(f"вердикт REVIEW approved текущей итерации ({iteration})")
    return ok, None


def _maybe_autogate_acceptance(conn, task_id: str, t, acc_tdir: Path,
                               iteration: int) -> None:
    """После входа в `acceptance` (с SPEC T079 — из `verifying`, раньше —
    напрямую из `review`) — попытка автогейта.

    Политика гейта acceptance не `auto` (включая неизвестное значение,
    отсутствие секции или нечитаемый `gates.yaml` — `gates.policy`
    вырождает всё это в `manual`) — функция не журналирует и не печатает
    НИЧЕГО: поведение обязано остаться байт-в-байт прежним (SPEC AC-5).

    Условие не выполнено — задача остаётся в `acceptance` (уже
    установлено вызывающим кодом) и ждёт Оператора; причина — одной
    строкой в журнале и в выводе (SPEC AC-4). Все условия выполнены —
    гейт проходится автогейтом: переход `acceptance -> merge_gate` тем
    же действием, `actor=autogate`, перечень условий в детали журнала
    (SPEC AC-1..AC-3).

    Сверка свежести ветки (T051) здесь намеренно не повторяется: между
    входом в `acceptance` (только что, этим же вызовом) и этим решением
    не проходит времени, в отличие от ручного approve после ожидания
    Оператора — второй такой же проверкой без временнóго окна нечего
    ловить.
    """
    if gates.policy("acceptance") != gates.AUTO:
        return
    ok_conditions, reason = _autogate_conditions(conn, task_id, t, acc_tdir,
                                                 iteration)
    if reason is not None:
        store.journal(conn, task_id, "fsm", "автогейт acceptance не пройден",
                      reason)
        print(f"[{task_id}] {reason} — жду Оператора")
        return
    print(f"[{task_id}] {AUTOGATE_PASS_MESSAGE}")
    store.set_state(conn, task_id, "merge_gate", "autogate",
                    expected_state="acceptance",
                    detail="; ".join(ok_conditions))
    # Sha, зафиксированный ЭТИМ переходом (SPEC «approve: полный sha в
    # подсказках», требование 1) — тот же приём, что и ручной вход в
    # merge_gate из `fsm._cmd_approve`.
    sha_hint = fixation.approve_sha_hint(task_id, store.task_target(conn, task_id))
    print(f"  дальше: artel.py approve {task_id}{sha_hint}  (выполнит merge)")
