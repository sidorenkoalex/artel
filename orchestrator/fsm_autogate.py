"""Автогейт acceptance по политике gates.yaml (ADR-0007, SPEC T066).
Перенесено из orchestrator/fsm.py без изменения поведения (T091,
декомпозиция диспетчеров fsm/runner).
"""
from pathlib import Path

from scripts import guard

from . import acceptance, budget, gates, store, workspace

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
    """
    ok: list[str] = []

    tests_dir = acc_tdir / "acceptance_tests"
    if not tests_dir.is_dir() or not any(tests_dir.glob("*.py")):
        return ok, ("автогейт: каталог приёмочных тестов пуст или "
                    "отсутствует")
    _, markers = guard.scan_acceptance_tests(acc_tdir)
    manual_ns = sorted(n for n, (kind, _) in markers.items() if kind == "manual")
    skip_ns = sorted(n for n, (kind, _) in markers.items() if kind == "skip")
    if manual_ns:
        return ok, (f"автогейт: критерии manual — "
                    f"{', '.join(f'AC-{n}' for n in manual_ns)}")
    if skip_ns:
        return ok, (f"автогейт: критерии skip — "
                    f"{', '.join(f'AC-{n}' for n in skip_ns)}")
    ok.append("каталог приёмочных тестов: 0 manual, 0 skip критериев")
    ok.append("приёмочные тесты задачи зелёные")

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
    print(f"  дальше: artel.py approve {task_id}  (выполнит merge)")
