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

from . import (acceptance, artifact_source, budget, ci, config, fixation,
              gates, gitcmd, store, workspace)

AUTOGATE_PASS_MESSAGE = "acceptance пройден автогейтом (политика gates.yaml)"

# Требование 1 (01M2B6K76EAFDF5X1B3Z9XK30Q): единственная точка входа
# задачи в acceptance (эта функция, зовётся ровно один раз из
# `fsm_advance._review_approved`) журналирует и печатает ОДНОЙ записью,
# что approve/автогейт проверят автоматически, а что остаётся сверить
# Оператору — вместо устаревшего протокола `docs/operator-gates.md`.
# `config.AUTO_STOP["acceptance"]` ссылается на это действие (требование
# 3, AC-6).
ACCEPTANCE_CHECKLIST_ACTION = "приёмка: что проверит approve"

# Требование 1 (AC-4/AC-8): планка без единого manual/skip/escalate
# критерия — вторая группа записи заменяется целиком этой фразой,
# поведение автогейта (переход без Оператора) не меняется.
_ACCEPTANCE_AUTOPASS_NOTE = "автогейт пройдёт сам"

# Требование 3 (AC-3) — литеральный факт: дифф уже сверен с зонами
# гейтом `in_dev -> review` (`fsm_advance._zones_gate`), задолго до
# входа в acceptance — здесь только констатация для Оператора.
_ZONES_ALREADY_CHECKED_FACT = "дифф сверен с зонами — уже сделано гейтом"


def _acceptance_pull_merge_commits(branch: str) -> list[str]:
    """Требование 3/AC-3: «родители подтяжек» — merge-коммиты main в
    кодовую ветку задачи за её жизнь. В этой системе единственный вид
    merge-коммита на кодовой ветке задачи — автослияние подтяжки main
    (docstring `orchestrator/fsm_advance.py::_PULL_MAIN_COMMIT_INFIX`:
    «единственный вид коммита на кодовой ветке, не являющийся работой
    developer'а») — сам факт `--merges` уже и есть искомый список, без
    текстового фильтра по сообщению коммита (который распознавал бы
    только автослияние настоящего пульта, но не любой ручной `git merge
    --no-ff main` — а оба случая одинаково остаются подтяжкой main,
    которую Оператору полезно увидеть на приёмке).

    Полный sha (`%H`), не сокращённый: длина сокращения git выбирает
    сама и не гарантирует конкретное число знаков — печать обязана
    называть значение, однозначно узнаваемое Оператором в `git log`
    независимо от этого выбора.

    Пустой список — merge-коммитов не было (легитимно, требование 3:
    «если такие были») либо git не ответил: оба случая означают одно и
    то же для печати — эту строку факта просто не включать."""
    res = gitcmd.git("log", "--merges", "--format=%H", branch)
    if res is None or res.returncode != 0:
        return []
    return [line for line in res.stdout.splitlines() if line.strip()]


def _acceptance_manual_criteria(task_id: str, branch: str) -> list[str]:
    """Требование 3/AC-3, вычислено требованием 2/AC-5 через
    `guard.scan_ac_content` целиком (не через `_autogate_conditions`,
    чьё короткое замыкание на первом отказе не даёт увидеть остальные
    критерии планки, docstring `_autogate_conditions`) — каждый
    manual/skip/escalate критерий планки, номером AC и первой строкой
    его пометки. Критерий `ci` не входит (требование 3: он не остаётся
    человеку — уже автоматика, `_autogate_conditions` условие «а»).

    Чтение планки — теми же примитивами, что и условие «а»
    (`gitcmd.ls_tree_files`/`gitcmd.show` с артефактной ветки,
    `*.py` целиком, не только `test_*.py` — тот же приём T031)."""
    tests_rel = f"tasks/{task_id}/acceptance_tests"
    py_paths = [p for p in (gitcmd.ls_tree_files(branch, tests_rel) or [])
               if p.endswith(".py")]
    sources = []
    for p in py_paths:
        text, _ = gitcmd.show(branch, p)
        if text is not None:
            sources.append(text)
    _, markers = guard.scan_ac_content(sources)
    return [f"AC-{n}: {kind}" + (f" — {reason}" if reason else "")
            for n, (kind, reason) in sorted(markers.items())
            if kind in ("manual", "skip", "escalate")]


def _acceptance_checklist_detail(conn, task_id: str, t, iteration: int) -> str:
    """Содержимое единой записи «приёмка: что проверит approve»
    (требования 1-3, AC-1..AC-4): группа «а» — ровно четыре пункта,
    которые approve/автогейт исполняют автоматически (AC-2); группа
    «б» — что остаётся Оператору (AC-3), либо, если у планки нет ни
    одного manual/skip/escalate критерия, литеральная фраза «автогейт
    пройдёт сам» вместо всей группы целиком (AC-4).

    Источник планки (артефактная ветка + sha) — те же
    `artifact_source.resolve`/`gitcmd.branch_head_sha`, что несёт
    условие «а» `_autogate_conditions` (требование 2/AC-5) — значение
    не может разойтись с тем, что реально видит автогейт. Подтяжки/
    свежесть — про КОДОВУЮ ветку `t["branch"]`, отдельно от
    артефактной, тем же разделением, что и остальной модуль.
    """
    artifact_branch_name, _ = artifact_source.resolve(conn, task_id)
    artifact_sha = gitcmd.branch_head_sha(artifact_branch_name)
    group_a = (
        f"прогон планки приёмочных тестов (источник: артефактная ветка "
        f"{artifact_branch_name}, sha {artifact_sha}); "
        "полный набор tests/ в worktree ветки задачи; "
        f"потолок бюджета задачи (${t['budget_usd'] or 0.0:.2f}); "
        f"свежесть кодовой ветки против origin/{config.MAIN_BRANCH}"
    )
    header = f"автоматически при approve: {group_a}"
    manual_items = _acceptance_manual_criteria(task_id, artifact_branch_name)
    if not manual_items:
        return f"{header} | {_ACCEPTANCE_AUTOPASS_NOTE}"
    group_b_items = list(manual_items)
    group_b_items.append(_ZONES_ALREADY_CHECKED_FACT)
    merges = _acceptance_pull_merge_commits(t["branch"])
    if merges:
        group_b_items.append(f"родители подтяжек: {'; '.join(merges)}")
    group_b_items.append(f"вердикт ревью: tasks/{task_id}/REVIEW.md, "
                         f"итерация {iteration}")
    return f"{header} | остаётся человеку: {'; '.join(group_b_items)}"


def _log_acceptance_checklist(conn, task_id: str, t, iteration: int) -> None:
    """Журналирует и печатает `_acceptance_checklist_detail` (AC-1) —
    одна и та же запись, независимо от исхода `_autogate_conditions`
    (эта задача не меняет, что и как автогейт проверяет — только
    сообщает об этом заранее)."""
    detail = _acceptance_checklist_detail(conn, task_id, t, iteration)
    store.journal(conn, task_id, "fsm", ACCEPTANCE_CHECKLIST_ACTION, detail)
    print(f"[{task_id}] {ACCEPTANCE_CHECKLIST_ACTION}")
    print(f"  {detail}")


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

    Требование 1 (01M2B6K76EAFDF5X1B3Z9XK30Q): единственная точка входа
    в acceptance во всей кодовой базе — эта функция журналирует и
    печатает «приёмка: что проверит approve» ОДНОЙ записью, до решения
    самого автогейта (ниже) и независимо от его исхода — печать
    описывает, что approve/автогейт проверят, не то, что уже проверено.
    """
    if gates.policy("acceptance") != gates.AUTO:
        return
    _log_acceptance_checklist(conn, task_id, t, iteration)
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
