"""Цикл `auto`: advance до шага роли, затем — если роль ещё не закончила — run.

Крутится, пока в шаге работает агент (SPEC 01M1R8B3ZKXQT0Z0G6QQQDV906:
предварительный advance пробует готовый артефакт до запуска роли, не
после)."""
import re
import time
from dataclasses import dataclass

from . import (agent_log, alerts, budget, ci, config, fixation, fsm, lease,
              pause, runner, store, zone_lock)

# Действие журнала, которым отказ `advance` узнаётся вне зависимости от
# конкретной причины (SPEC T038, требование 1): каждая точка `cmd_advance`
# (orchestrator/fsm.py), отказывающая переходу НЕ через guard структуры
# артефакта, журналирует actor "fsm" и action, начинающийся с этой фразы.
# Guard же возвращает `True` и уводит цикл на существующую немедленную
# остановку раньше, до этой проверки (требование 3) — пересечения нет.
REFUSAL_ACTION_PREFIX = "переход отклонён"

# Требование 3 (SPEC 01M1KCSTBYF1CRJBSY4P6VYQEA): состояния, чья остановка
# `auto` — штатный исход, не буксование, поэтому финальный выход цикла
# (без агентской роли) НЕ поднимает алерт `kind=attention`, независимо от
# числа пройденных шагов вызова. Ручные гейты — уже сегодня «ЖДЁТ
# ОПЕРАТОРА» в `catalog.cmd_status`; `done`/`killed` — задача закрыта,
# откручивать нечего. `escalated` сюда НЕ входит: SPEC требует алерт «любой
# причины» эскалации, в т.ч. когда задача уже была в ней до вызова (ANSWER-1,
# вопрос 2; AC-7, AC-17).
_NO_ALERT_FINAL_STATES = ("spec_gate", "acceptance", "merge_gate",
                         "done", "killed")


def _run_paused_refusal(conn, task_id: str, journaled_before: int) -> bool:
    """Отказал ли `run` ИМЕННО этим вызовом из-за паузы (REVIEW.md T070,
    итерация 2, замечание 1) — а не приписан ей задним числом по текущему
    `pause.is_paused`, который путает её с одновременным отказом по бюджету
    или лимиту параллельных задач.

    `journaled_before` — число строк журнала задачи ДО вызова `run`, тем же
    приёмом, что и `_advance_refusal`: отказ ищется среди добавленных им
    самим записей, а не среди всех, что видел журнал когда-либо.
    """
    for row in store.task_steps(conn, task_id)[journaled_before:]:
        if row["action"] == pause.REFUSAL_ACTION:
            return True
    return False


def _run_zone_wait_refusal(conn, task_id: str, journaled_before: int) -> bool:
    """Отказал ли `run` ИМЕННО этим вызовом из-за занятости зоны (SPEC
    01M1P9QAG65GVF69YJEV0V18D9, требование 3) — тот же приём отсечки, что
    `_run_paused_refusal` уже применяет к штатной паузе."""
    for row in store.task_steps(conn, task_id)[journaled_before:]:
        if row["action"] == zone_lock.REFUSAL_ACTION:
            return True
    return False


def _advance_refusal(conn, task_id: str, journaled_before: int) -> str | None:
    """Текст `action` записи `fsm` «переход отклонён…», добавленной ИМЕННО
    этим вызовом `cmd_advance`; `None` — отказ не журналировался (агент ещё
    работает — требование 4).

    `journaled_before` — число строк журнала задачи ДО вызова: отказ
    ищется среди добавленных после него, иначе отказ прошлого шага
    засчитался бы за отказ текущего.
    """
    for row in store.task_steps(conn, task_id)[journaled_before:]:
        if row["actor"] == "fsm" and row["action"].startswith(REFUSAL_ACTION_PREFIX):
            return row["action"]
    return None


# Состояния роли, где возврат с неотработанным основанием переделки
# держит пред-advance до первого завершённого шага ТОЙ ЖЕ роли (SPEC
# «регрессия №13» 01M1RHFRQ2C0P4A57XJJ1WZV8N, требования 1-2; ANSWER-1
# п.2, ANSWER-2 п.1): developer (`in_dev`) — прямой предмет регрессии
# №12/№13; analyst (`spec_writing`)/test_author (`tests_writing`) — тот
# же класс, обобщённый на возврат из `escalated` (требование 2,
# AC-2/AC-8). `review` намеренно не входит: свежесть ЕГО собственного
# вердикта уже держит отдельный, куда более старый механизм
# (`artifacts.fresh_verdict_iteration`/`reviewed_iter`), не предмет
# этой задачи.
_REWORK_GATE_STATES = ("in_dev", "spec_writing", "tests_writing")

# Именованная причина отказа обоих рубежей (требование 4) — общий текст
# с `orchestrator/fsm_advance.py::_review_rework_gate_refuses`.
REWORK_REFUSAL_ACTION = "переход отклонён: замечания ревью не отработаны"

# Номер итерации ревью в detail записи `state -> in_dev`, оставленной
# `orchestrator/fsm_advance.py::review` (`f"замечания ревью, итерация
# {iters}"`) — тем же текстом отвечает и тестовая фикстура, дописывающая
# эту запись напрямую (`tasks/01M1RHFRQ2C0P4A57XJJ1WZV8N/acceptance_tests/`).
_ITERATION_IN_DETAIL = re.compile(r"итерация (\d+)")

# Тексты `detail` записи `state -> {state}`, которыми ЛЕГИТИМНЫЙ первый
# вход роли в состояние отличается от возврата с неотработанным основанием
# переделки (ANSWER-3, п.1-2 — регрессия против AC-7 приёмки
# 01M1R8B3ZKXQT0Z0G6QQQDV906: рубеж требований 1-2, применённый ко ВСЯКОМУ
# входу без разбора, держал пред-advance даже на первом же входе в
# `in_dev` и звал developer напрямую — прежде чем предварительный
# `advance` успевал наткнуться на лок `acceptance_tests/` и остановить
# цикл существующим механизмом требования 4 без единого шага developer).
# Единственные обработчики легитимного первого входа: `orchestrator/
# fsm.py::_cmd_approve` (`spec_gate -> in_dev`/`tests_writing`) и
# `orchestrator/fsm_advance.py::tests_writing` (`tests_writing -> in_dev`)
# — тексты ниже дословно совпадают с их `detail=`. Возврат из `escalated`
# несёт ОДИН и тот же общий текст независимо от основания эскалации
# (`orchestrator/fsm.py::_cmd_approve`, «эскалация разрешена, продолжаем»)
# и намеренно НЕ входит в этот список — ANSWER-2 п.2/AC-2/AC-8 требуют
# держать рубеж и на нём (см. PLAN «Влияние на систему»: цена лишнего шага
# роли на не-rework возврате из эскалации — сознательный компромисс).
_LEGIT_FIRST_ENTRY_DETAILS = (
    "гейт SPEC пройден — приёмочные тесты до кода",
    "приёмочные тесты готовы — трассируемость AC пройдена",
)
_LEGIT_FIRST_ENTRY_PREFIXES = (
    "тесты пропущены (skip_tests):",
    "SPEC schema_version ",
)


def _is_legit_first_entry_detail(detail: str | None) -> bool:
    """Прочитала выше — detail записи, отмечающей легитимный первый вход
    в состояние роли, не возврат с неотработанным основанием переделки."""
    if detail is None:
        return False
    if detail in _LEGIT_FIRST_ENTRY_DETAILS:
        return True
    return any(detail.startswith(prefix) for prefix in _LEGIT_FIRST_ENTRY_PREFIXES)


# detail записи `state -> {state}`, оставленной ИМЕННО возвратом из
# `escalated` (SPEC 01M1VBEDGMEXHVGWAH42FTDZ4X, требование 2): текст
# `fsm.py::_approve_escalated` — общий для ЛЮБОГО основания эскалации
# (провал агента, лимит, budget); текст `budget.py::_cmd_budget` — тот же
# самый исход, вынесенный поднятием потолка отдельной командой. Ни один из
# них не несёт своего собственного основания переделки (это ВОЗВРАТ к
# работе, прерванной эскалацией, не новое замечание ревью/reject) — запись
# с таким detail не может служить анкером рубежа «возврат не отработан»:
# она моложе настоящего анкера (возврата review/reject) и маскировала бы
# его собой, из-за чего шаг роли, отработанный ДО эскалации, ошибочно не
# засчитывался бы (SPEC «Контекст», регрессия AC-5).
_ESCALATED_RETURN_DETAILS = ("эскалация разрешена, продолжаем",
                            "бюджет поднят, продолжаем")


def _role_step_since_state_entry(conn, task_id: str, state: str,
                                 role: str) -> tuple[bool, str | None]:
    """(был ли уже шаг `role` после ПОСЛЕДНЕЙ записи `state -> {state}`,
    detail этой записи) — требование 1 («запись agent run finished роли
    developer после записи state -> in_dev»), обобщённое на любое
    состояние из `_REWORK_GATE_STATES` (требование 2).

    Такой записи нет вовсе (легитимный первый вход в состояние в обход
    FSM — тестовые песочницы, правящие `tasks.state` напрямую, либо
    самый первый вход задачи в это состояние за всю её жизнь) — сверять
    не с чем, тот же вырожденный случай деградации, что и у остальных
    примитивов `auto.py`/`fsm_advance.py`: `(True, None)`, пред-advance
    не держится. Запись ЕСТЬ, но её `detail` называет легитимный первый
    вход (`_is_legit_first_entry_detail`, ANSWER-3) — та же деградация:
    роль объективно не могла отработать шаг РАНЬШЕ собственного первого
    входа в состояние, держать пред-advance здесь нечем, кроме уже
    существующих проверок требования 3/4 (PLAN.md не готов, лок
    `acceptance_tests/` и подобные).

    Записи возврата ИЗ `escalated` (`_ESCALATED_RETURN_DETAILS`,
    01M1VBEDGMEXHVGWAH42FTDZ4X, требование 2) пропускаются при поиске
    анкера — они не несут собственного основания переделки и не должны
    маскировать более раннюю запись, которая его несёт (см. её
    докстринг): анкером остаётся ПОСЛЕДНЯЯ запись `state -> {state}`
    среди ОСТАЛЬНЫХ, а «был ли шаг роли» проверяется от НЕЁ — в том
    числе через любые промежуточные записи возврата из эскалации
    (шаг роли, отработанный между анкером и эскалацией, засчитывается
    точно так же, как отработанный уже после возврата).
    """
    rows = store.task_steps(conn, task_id)
    marker = f"state -> {state}"
    last_entry = None
    for i, row in enumerate(rows):
        if row["action"] == marker and row["detail"] not in _ESCALATED_RETURN_DETAILS:
            last_entry = i
    if last_entry is None:
        return True, None
    detail = rows[last_entry]["detail"]
    if _is_legit_first_entry_detail(detail):
        return True, detail
    ran = any(row["actor"] == role and row["action"] == "agent run finished"
              for row in rows[last_entry + 1:])
    return ran, detail


def _rework_not_addressed_reason(detail: str | None, role: str) -> str:
    """Именованная причина отказа (требование 4): буквальная фраза SPEC
    («замечания ревью не отработаны: нет шага <роль> после итерации N»),
    когда запись, вернувшая задачу в состояние, называет номер итерации
    ревью (`review -> in_dev`/эскалация по тому же основанию — обе несут
    «..., итерация N» в detail, см. `orchestrator/fsm_advance.py::
    review`); иначе (`acceptance`/`merge_gate`/`verifying` reject,
    эскалация по другому основанию, возврат в `spec_writing`/
    `tests_writing`) — тот же класс причины без придуманного номера.
    """
    match = _ITERATION_IN_DETAIL.search(detail or "")
    if match:
        return (f"замечания ревью не отработаны: нет шага {role} "
                f"после итерации {match.group(1)}")
    return f"возврат не отработан: нет шага {role} после возврата"


def _verifying_poll_note(conn, task_id: str, journaled_before: int) -> str | None:
    """Detail записи `fsm.VERIFYING_STATUS_ACTION`, добавленной ИМЕННО
    последним `fsm.cmd_advance` (тот же приём отсечки, что и
    `_advance_refusal` выше) — не самой свежей строки журнала вообще: тот
    же вызов мог дописать и другую запись (переход состояния).

    `None` — эта запись не появилась вовсе (не должно случиться при
    штатной работе `fsm.cmd_advance` из `verifying`, но `_advance_
    verifying_poll` обязана остаться безопасной и на такой исход).
    """
    for row in store.task_steps(conn, task_id)[journaled_before:]:
        if row["action"] == fsm.VERIFYING_STATUS_ACTION:
            return row["detail"]
    return None


def _advance_verifying_poll(conn, task_id: str, session_id: str) -> bool:
    """Один advance-опрос CI в `verifying` внутри цикла `auto` (SPEC T086,
    требование 1): не расходует `AUTO_MAX_STEPS` — пауза здесь ждёт
    внешнее событие (CI), не выполняет шаг конвейера (требование 1, AC-2).

    Опрос — тот же `fsm.cmd_advance`, что и ручной Оператор (требование 5
    не меняется): зелёный CI уже увёл задачу в `acceptance` изнутри него,
    исчерпанный потолок времени — в `escalated` (требования 3-4) — в
    обоих случаях эта функция возвращает `False`, дальше решает вызывающий
    цикл по новому `state`. Завершённый красный CI (требование 2, AC-4)
    здесь же и останавливает цикл `auto` — задача остаётся в `verifying`,
    подсказка называет `reject`; это ЕДИНСТВЕННЫЙ исход, где функция сама
    печатает итог и возвращает `True` (цикл обязан остановиться немедленно,
    не дожидаясь потолка времени). «Проверок нет»/«проверки идут» не
    меняют состояние — функция засыпает на `VERIFYING_POLL_INTERVAL_SEC` и
    возвращает `False`, вызывающий цикл повторит опрос.
    """
    journaled_before = len(store.task_steps(conn, task_id))
    fsm.cmd_advance(task_id, session_id=session_id)
    t = store.get_task(conn, task_id)
    if t["state"] != "verifying":
        return False
    note = _verifying_poll_note(conn, task_id, journaled_before)
    if note is not None and ci.verifying_is_red(note):
        reason, hint = config.AUTO_STOP_VERIFYING_RED
        auto_stop(conn, task_id, "verifying", f"{reason} — {note}",
                  hint.format(id=task_id), alert=True)
        return True
    time.sleep(config.VERIFYING_POLL_INTERVAL_SEC)
    return False


def _final_stop_raises_alert(state: str, steps: int) -> bool:
    """Требование 3: алерт финального выхода цикла (нет агентской роли,
    `auto_stop_advice`) — за вычетом исключений требования 3 (ANSWER-1,
    вопрос 2): ручной гейт/терминал (`_NO_ALERT_FINAL_STATES`) и
    `spec_writing` без единого пройденного шага — роли не было с самого
    начала вызова, потому что `tasks/<id>/TZ.md` не заведён (SPEC T025;
    AC-16). Пауза сюда не доходит — обрабатывается отдельной веткой
    `SystemExit` внутри цикла шагов.
    """
    if state in _NO_ALERT_FINAL_STATES:
        return False
    if state == "spec_writing" and steps == 0:
        return False
    return True


def auto_stop_advice(conn, task_id: str, state: str) -> tuple[str, str]:
    """Причина остановки и следующая команда — по факту, а не по имени состояния.

    Имя состояния не всегда называет причину: в `escalated` задача оказывается
    и после падения агента, и после пробитого потолка, а команды у этих двух
    случаев разные. Потолок спрашиваем у того же `budget_block`, которым
    отказывается стартовать `run`, — так подсказка цикла не может разойтись с
    его отказом.

    Подсказки состояний из `fsm.APPROVE_NEEDS_SHA` несут `{sha}` (SPEC
    «approve: полный sha в подсказках», требование 1) — зафиксированный
    sha готовым к копированию, а не голым `<id>`, которым Оператору
    иначе пришлось бы достраивать значение по памяти (инцидент 02.09,
    мерж T101). Потолок бюджета подменяет подсказку `escalated` на
    `AUTO_STOP_BUDGET` (без `{sha}`, следующая команда — `budget`, не
    `approve`) — sha в этом случае не ищется.
    """
    reason, hint = config.AUTO_STOP.get(
        state, (f"состояние {state} циклом не обслуживается", "artel.py show {id}"))
    needs_sha = state in fsm.APPROVE_NEEDS_SHA
    if state == "escalated" and budget.budget_block(
            store.get_task(conn, task_id)) is not None:
        reason, hint = config.AUTO_STOP_BUDGET
        needs_sha = False
    sha_hint = ""
    if needs_sha:
        target = store.task_target(conn, task_id)
        sha_hint = fixation.approve_sha_hint(task_id, target)
    return reason, hint.format(id=task_id, sha=sha_hint)


def auto_stop(conn, task_id: str, state: str, reason: str, hint: str, *,
              alert: bool) -> None:
    """Остановка цикла: запись в журнал и итог Оператору (требования 2, 5).

    `alert` (требование 3, обязателен и keyword-only — молчаливый дефолт
    свёл бы решение «поднимать или нет» на нет для любого пропущенного
    вызова, тот же довод, что и у `store.set_state`'а `expected_state`):
    каждая точка остановки цикла решает это явно, по СВОЕЙ причине —
    `False` только для ручного гейта/паузы/нулевого числа шагов без роли
    с самого начала (AC-14..AC-16), `True` во всех прочих случаях.
    """
    store.journal(conn, task_id, "operator", "auto остановлен",
                  f"{state}: {reason}")
    print(f"[{task_id}] auto остановлен: {reason}")
    print(f"  состояние: {state}")
    print(f"  дальше: {hint}")
    if alert:
        alerts.raise_attention_alert(
            conn, task_id, f"[{task_id}] auto остановлен: {state}: {reason}")


def cmd_auto(task_id: str, session_id: str | None = None) -> None:
    """Цикл advance+run, пока в шаге работает агент, — до места, где нужен человек.

    Механику шага команда не дублирует: внутри те же `cmd_run` и
    `cmd_advance`, которые Оператор зовёт руками, — бюджет, ретраи, журнал
    и вердикты FSM остаются целиком в них. Своё у цикла одно — условие
    выхода: работаем, пока у шага есть агентская роль, останавливаемся на
    первом же состоянии без неё. Так новое агентское состояние (MVP,
    plan_review) подхватится само, а новое ручное — само остановит.

    Роль шага резолвит `runner.step_role`, а не прямое чтение
    `config.STATE_ROLE`: `spec_writing` — агентское состояние только при
    заведённом `tasks/<id>/TZ.md` (SPEC T025, требование 1) — условность
    зависит от конкретной задачи, а не только от имени состояния, поэтому
    статический словарь эту проверку сам провести не может.

    Решений auto не принимает: approve и reject остаются за Оператором —
    ручные гейты обходить нечем (docs/design.md §4, docs/invariants.md 18).

    Держит lease задачи один раз на весь цикл (SPEC T044, требование 2) и
    передаёт свой `session_id` во внутренние `run`/`advance` — те видят
    уже существующий lease своей же сессии и на каждом шаге его продлевают
    (требование 7), сами не отпуская (см. `orchestrator/lease.py`).

    Префикс -> полный id (SPEC T094, требование 3, AC-3) резолвится ЗДЕСЬ,
    до lease (REVIEW T094 итерация 1, замечание 1).
    """
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_auto(conn, task_id, sid),
                     on_refusal="print")


@dataclass
class _CycleState:
    """Состояние, разделяемое между итерациями цикла (AC-2): не локальные
    флаги `_cmd_auto`, а поля объекта, которым владеет и который мутирует
    только шаг (б) — `_pre_advance_step`. `idle_steps` — число шагов
    подряд без смены состояния (требование 2, сбрасывается любым
    переходом); `prev_refusal` — текст отказа `advance` предыдущего шага
    без смены состояния, `None` — предыдущий шаг не был таким отказом
    (SPEC T038, требование 1)."""
    idle_steps: int = 0
    prev_refusal: str | None = None


@dataclass(frozen=True)
class Advanced:
    """Исход шага (б): переход выполнен предварительным advance по уже
    готовому артефакту роли — сам шаг роли этой итерации не нужен, не
    расходует `steps`."""
    before: str
    after: str


@dataclass(frozen=True)
class RoleRan:
    """Исход шага (в): `runner.cmd_run` отработал (успешно или с
    эффектом вроде эскалации внутри самого шага) — `after` уже отражает
    этот эффект."""
    role: str
    before: str
    after: str


@dataclass(frozen=True)
class Refused:
    """Исход, которым итерация журналирует отказ и не продвигает
    задачу — холостой шаг без немедленной остановки цикла; `reason` —
    текст отказа, по которому следующая такая же итерация ловит стоп-кран
    «два подряд одинаковых»."""
    reason: str | None


@dataclass(frozen=True)
class Stop:
    """Исход шага (г): цикл обязан остановиться этой же итерацией — поля
    ровно те, что принимает `auto_stop` (шаг д)."""
    state: str
    reason: str
    hint: str
    alert: bool


def _step_limit_stop(task_id: str, state: str, steps: int) -> Stop | None:
    """Стоп-кран (г) — лимит шагов за вызов. Гейтит попытку РОЛИ (реальный
    `run` или отказ, который её замещает), не саму итерацию цикла
    (REVIEW.md итерации 1, R1-F1): переход, который предварительный
    `advance` выполняет САМ по уже готовому артефакту — без единого
    вызова `runner.cmd_run` — бесплатен для лимита ровно так же, как
    раньше был бесплатен для него advance, следовавший за `run` СРАЗУ
    внутри одной и той же итерации (SPEC T038, «run+advance»): та же
    работа, просто вызов сдвинулся на итерацию раньше. C
    `AUTO_MAX_STEPS == 1` цикл всё равно обязан сделать РОВНО одну пару
    (advance, run) и встать (AC-1 приёмки): то же самое место проверки,
    только сам счётчик растёт реже."""
    if steps >= config.AUTO_MAX_STEPS:
        hint = (f"artel.py log {task_id} (что происходит), "
                f"затем artel.py auto {task_id} — продолжит отсюда")
        return Stop(state, f"лимит {config.AUTO_MAX_STEPS} шагов за вызов исчерпан",
                    hint, True)
    return None


def _rework_gate_blocks(conn, task_id: str, state: str, role: str) -> bool:
    """Шаг (а) — решение «нужен ли пред-advance» (требования 1-2, SPEC
    «регрессия №13» 01M1RHFRQ2C0P4A57XJJ1WZV8N, ANSWER-1 п.2, ANSWER-2
    п.1): текущее пребывание в состоянии роли (`_REWORK_GATE_STATES`)
    началось переходом с основанием переделки (замечания ревью/reject/
    эскалация), ещё не отработанным — готовый артефакт роли мог
    существовать ещё ДО этого возврата (SPEC «Контекст», регрессия
    №12/№13), и предварительный advance продвинул бы задачу мимо роли по
    нему же. Гейт держит именно вызов advance — до первого завершённого
    шага той же роли ПОСЛЕ возврата; удовлетворив условие один раз, роль
    больше не блокируется этим гейтом до следующего такого возврата."""
    gated_role = role is not None and state in _REWORK_GATE_STATES
    role_ran, entry_detail = (
        _role_step_since_state_entry(conn, task_id, state, role)
        if gated_role else (True, None))
    if gated_role and not role_ran:
        reason = _rework_not_addressed_reason(entry_detail, role)
        store.journal(conn, task_id, "fsm", REWORK_REFUSAL_ACTION, reason)
        print(f"[{task_id}] переход отклонён: {reason}")
        return True
    return False


def _pre_advance_step(conn, task_id: str, session_id: str, role: str,
                      state: str, before: str,
                      cycle: _CycleState) -> Advanced | Refused | Stop | None:
    """Шаг (б) — предварительный advance по уже готовым артефактам (SPEC
    01M1R8B3ZKXQT0Z0G6QQQDV906, требования 1-4): пробуем перейти по уже
    готовым артефактам ДО шага роли — так цикл не тратит шаг на
    подтверждение очевидного (PLAN.md, поднятый ready ДО возврата из
    эскалации по бюджету; REVIEW.md, вердикт которого уже вынесен).
    Разбор исхода включает часть стоп-кранов (г) — «два подряд
    одинаковых отказа» и «N шагов без перехода» — они считаются по факту
    именно ЭТОЙ попытки, поэтому естественно живут здесь же, не в
    отдельной функции.

    `None` — advance не отказал и не перевёл состояние (артефакт роли
    ещё не готов, либо журналируемый отказ того же класса, что «роль ещё
    не закончила», требование 3): вызывающий запускает роль как обычно.
    """
    journaled_before = len(store.task_steps(conn, task_id))
    if fsm.cmd_advance(task_id, session_id=session_id):
        # guard отклонил артефакт-условие: тот же по характеру немедленный
        # стоп, что и раньше был доступен только ПОСЛЕ шага роли, — цикл
        # не зовёт cmd_run для того же состояния.
        hint = f"почини артефакт и повтори artel.py advance {task_id}"
        return Stop(state,
                    f"advance отклонён guard'ом артефакта-условия — {hint}",
                    hint, True)

    t = store.get_task(conn, task_id)
    new_state = t["state"]
    if new_state != before:
        # Требование 2: переход уже случился по готовым артефактам — шаг
        # роли этой итерации не нужен, цикл продолжает уже с нового
        # состояния. Не расходует `steps` — ни один агент не звался.
        note = f"шаг {role} не нужен: переход выполнен по готовым артефактам"
        store.journal(conn, task_id, "operator", note, f"{before} -> {new_state}")
        print(f"[{task_id}] {note} ({before} -> {new_state})")
        cycle.idle_steps = 0
        cycle.prev_refusal = None
        return Advanced(before, new_state)

    refusal = _advance_refusal(conn, task_id, journaled_before)
    # Требование 4 отказывает шагу роли только на отказах, которые
    # ЧЕЛОВЕК обязан разобрать руками — лок acceptance_tests/, свежесть
    # ветки, гейт ёмкости diff: примеры требования 4 (кроме «дерево не на
    # ветке задачи», см. ниже) — из ПРОВЕРОК `in_dev` ПОВЕРХ готового
    # артефакта (PLAN.md уже ready/approved), не из готовности самого
    # артефакта роли. У `review`/`tests_writing` тот же журналируемый
    # префикс несёт и «вердикт REVIEW.md уже учтён»
    # (`artifacts.fresh_verdict_iteration`), и «не все AC покрыты тестом»
    # (`fsm._tests_writing_ac_state`) — оба ЖДУТ именно НОВОГО прогона
    # ЭТОЙ ЖЕ роли (тот же смысл, что и класс требования 3), только
    # исторически журналируются. Скопировать требование 4 на них
    # буквально значило бы, что `review`/`tests_writing` теряют гарантию
    # «роль хотя бы раз получит шанс отработать» насовсем: текст отказа
    # не меняется без нового прогона, стоп-кран T038 бьёт на второй же
    # итерации, и роль так и не запускается ни разу — проверено прогоном
    # `tests/test_auto_cycle.py::AutoStopsWhereTheOperatorIsNeededTest::
    # test_review_iterations_are_passed_without_the_operator` (после
    # ЛЮБОГО changes_requested ревьювер больше не может вынести новый
    # вердикт) и `test_fresh_task_first_developer_step_still_runs`
    # (свежая задача, ещё нет ни одного теста/PLAN.md — тот же стоп-кран
    # до первого запуска test_author/developer). Оба — регресс тяжелее
    # того, что чинит эта SPEC, поэтому «другой класс» здесь — только
    # `in_dev`; для прочих состояний журналируемый отказ ведёт себя как
    # класс требования 3 (роль всё равно запускается).
    #
    # «Дерево не на ветке задачи» (`fsm._read_branch_text_or_refuse`,
    # общий узел ВСЕХ четырёх обработчиков) срабатывает ДО того, как
    # handler вообще прочитал содержимое артефакта — файла нет НА ВЕТКЕ,
    # а не «нет доступа к git»: у `in_dev` это ПЕРВЫЙ ЖЕ заход в
    # состояние для КАЖДОЙ задачи (PLAN.md появляется только ВМЕСТЕ с
    # первым прогоном developer, ничто не заводит его файл заранее) —
    # тот же класс требования 3, что и «PLAN.md не ready» ниже по тому же
    # handler'у, журналируется только по историческому совпадению
    # реализации общего узла. Считать его «другим классом» даже для
    # `in_dev` блокировало бы developer НАВСЕГДА уже на второй итерации
    # ПЕРВОГО же вызова `auto` любой новой задачи (стоп-кран T038 бьёт по
    # идентичному тексту раньше, чем developer получит хоть один шанс
    # написать PLAN.md) — регрессия, которую ловит
    # `test_fresh_task_first_developer_step_still_runs`.
    tree_missing = refusal == "переход отклонён: дерево не на ветке задачи"
    other_class_refusal = refusal if (refusal is not None
                                      and state == "in_dev"
                                      and not tree_missing) else None
    if other_class_refusal is not None and other_class_refusal == cycle.prev_refusal:
        # Требование 1 (инцидент T035, SPEC T038): два подряд отказа одним
        # текстом — причина отказа вне зоны агента, прогон агента её не
        # лечит.
        hint = f"почини причину и повтори artel.py advance {task_id}"
        return Stop(state, f"{other_class_refusal} — {hint}", hint, True)
    cycle.prev_refusal = other_class_refusal
    cycle.idle_steps += 1
    if cycle.idle_steps >= config.AUTO_STALL_STEPS_LIMIT:
        # Требование 2: N шагов подряд без перехода — независимо от
        # класса отказа (в отличие от стоп-крана требования 1 выше,
        # который уже отсёк бы ДВА подряд отказа ОДНОГО класса раньше,
        # чем счётчик успел бы дойти до N при дефолтных значениях). Хвост
        # «, последний отказ: <класс>» — только если ПОСЛЕДНИЙ из N шагов
        # журналировал отказ требования 4 (ANSWER-1, вопрос 3): его
        # отсутствие само по себе несёт факт «агент продолжал работу».
        tail = (f", последний отказ: {other_class_refusal}"
               if other_class_refusal is not None else "")
        reason = f"цикл не сходится: {cycle.idle_steps} шагов без перехода{tail}"
        hint = (f"artel.py log {task_id} — глянь, что происходит на "
                f"последних шагах, затем artel.py advance {task_id}")
        return Stop(state, reason, hint, True)
    if other_class_refusal is not None:
        # Требование 4: журналируемый отказ другого класса — шаг роли на
        # этой итерации не запускается, цикл повторит advance следующей
        # итерацией (та же реакция, что и раньше — после шага роли, —
        # просто без самого шага). Расходует `steps` (не свободный
        # переход — агент так и не получил шанса).
        return Refused(other_class_refusal)
    return None


def _role_run_step(conn, task_id: str, session_id: str, role: str,
                   state: str, before: str, steps: int) -> RoleRan | Stop:
    """Шаг (в) — запуск шага роли и разбор исхода: успешное завершение
    (включая эффект вроде эскалации внутри самого шага) против отказа
    `run` стартовать (пауза, занятость зоны, бюджет, лимит
    параллельности). Отказ стартовать `cmd_run` сообщает единственным
    способом — `sys.exit` с текстом; в цикле текст печатаем сами:
    пойманный `SystemExit` нигде не покажется."""
    run_journaled_before = len(store.task_steps(conn, task_id))
    try:
        runner.cmd_run(task_id, session_id=session_id)
    except SystemExit as exc:
        print(str(exc))
        # Пауза (SPEC T070, требование 2) — не «эскалация по бюджету»:
        # причина должна быть видна Оператору в итоговом сообщении, а не
        # потеряться среди прочих отказов `run`. Причина — по тому, что
        # реально журналировал ИМЕННО этот вызов `cmd_run`
        # (`_run_paused_refusal`), а не по независимому текущему опросу
        # `pause.is_paused`: тот путал бы паузу с ОДНОВРЕМЕННЫМ отказом по
        # бюджету/лимиту параллельных задач, если Оператор выставил оба
        # (REVIEW.md T070, итерация 2, замечание 1).
        if _run_paused_refusal(conn, task_id, run_journaled_before):
            reason, hint = config.AUTO_STOP_PAUSE
            # Пауза — действие самого Оператора (ANSWER-1, вопрос 2): он
            # уже знает о причине остановки, алерт был бы уведомлением о
            # собственном же решении.
            return Stop(state, reason, hint.format(id=task_id), False)
        # Занятость зоны (SPEC 01M1P9QAG65GVF69YJEV0V18D9, требование 3) —
        # причина внешняя (держит другая задача), не буксование ЭТОГО
        # агента: `status`/`doctor` берут на себя объяснение, кто держит
        # зону (требование 4), алерт буксования не открывается.
        if _run_zone_wait_refusal(conn, task_id, run_journaled_before):
            reason, hint = config.AUTO_STOP_ZONE_WAIT
            return Stop(state, reason, hint.format(id=task_id), False)
        return Stop(state, "run отказался стартовать",
                    f"artel.py budget {task_id} <usd> или artel.py kill {task_id}",
                    True)

    # Состояние перечитываем: упавший агент и исчерпанный потолок уводят
    # задачу в escalated изнутри run — `before`/`state` здесь ещё след
    # предыдущей роли (для сообщения ниже), не текущего перечитанного
    # состояния.
    t = store.get_task(conn, task_id)
    new_state = t["state"]
    # Живой вывод агента уже был на экране и в логе — здесь только сводка
    # шага и ссылка на лог прогона (требование 6). Advance по СВЕЖЕМУ
    # результату этого шага цикл не зовёт отдельно — тем же вызовом
    # займётся предварительный `advance` следующей итерации (или, если
    # роли в новом состоянии больше нет, финальный стоп ниже цикла).
    print(f"[{task_id}] auto шаг {steps}/{config.AUTO_MAX_STEPS}: {role} "
          f"{before} -> {new_state}, "
          f"лог: {agent_log.last_agent_log(task_id, role)}")
    return RoleRan(role, before, new_state)


def _cmd_auto(conn, task_id: str, session_id: str) -> None:
    """Цикл advance+run, пока в шаге работает агент, — до места, где нужен
    человек. После разбора (SPEC «R1» 01M1SC40NT8T1WFKKKJ67CK96Z) —
    короткая композиция именованных шагов: (а) `_rework_gate_blocks`, (б)
    `_pre_advance_step`, (в) `_role_run_step`, (г) `_step_limit_stop` (и
    часть стоп-кранов внутри (б)), (д) `auto_stop` — вызывается на каждом
    `Stop` и ниже цикла на финальной остановке.
    """
    t = store.get_task(conn, task_id)
    state = t["state"]
    store.journal(conn, task_id, "operator", "auto старт",
                  f"состояние {state}, лимит {config.AUTO_MAX_STEPS} шагов")
    print(f"[{task_id}] auto: старт из {state}, "
          f"лимит {config.AUTO_MAX_STEPS} шагов за вызов")

    steps = 0
    role = runner.step_role(t)
    cycle = _CycleState()

    # `verifying` не входит в STATE_ROLE (нет агентской роли, SPEC T086) —
    # условие цикла держит его отдельным дизъюнктом, не значением `role`:
    # состояние достижимо и как стартовое для всего вызова, и как исход
    # обычного шага изнутри цикла (review -> verifying при approved
    # вердикте, ADR-0009) — второе разрешает войти в опрос, даже если
    # `role` к этому моменту уже `None`.
    #
    # Канареечная задача (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, требование
    # 11/AC-11) в опрос НЕ входит вовсе: `_advance_verifying_poll` ждёт
    # реальный CI ветки, которого у неё нет и не будет (нет Draft MR,
    # нет origin) — без этого исключения цикл спал бы внутри ЭТОГО ЖЕ
    # вызова `AUTO_MAX_STEPS`-независимым `time.sleep` до самого потолка
    # `config.VERIFYING_CEILING_SEC` (боевое значение — часы), и только
    # тогда возвращал бы управление `canary._drive_task` — тот убивает
    # задачу на `verifying` сразу (`_kill_at_verifying`), но не успевает
    # даже начать: весь прогон канарейки блокируется здесь первым же
    # входом в `verifying` (диагностировано ANSWER-2/ANSWER-3, инцидент
    # 04-05.09 — часовые «зависания» шагов developer этой же задачи).
    while role is not None or (state == "verifying" and not t["is_canary"]):
        if state == "verifying":
            if _advance_verifying_poll(conn, task_id, session_id):
                return
            t = store.get_task(conn, task_id)
            state = t["state"]
            role = runner.step_role(t)
            continue

        limit_stop = _step_limit_stop(task_id, state, steps)
        if limit_stop is not None:
            auto_stop(conn, task_id, limit_stop.state, limit_stop.reason,
                      limit_stop.hint, alert=limit_stop.alert)
            return
        before = state

        if not _rework_gate_blocks(conn, task_id, state, role):
            outcome = _pre_advance_step(conn, task_id, session_id, role,
                                        state, before, cycle)
            if isinstance(outcome, Stop):
                auto_stop(conn, task_id, outcome.state, outcome.reason,
                          outcome.hint, alert=outcome.alert)
                return
            if isinstance(outcome, Advanced):
                t = store.get_task(conn, task_id)
                state = t["state"]
                role = runner.step_role(t)
                continue
            if isinstance(outcome, Refused):
                steps += 1
                continue

        steps += 1
        outcome = _role_run_step(conn, task_id, session_id, role, state,
                                 before, steps)
        if isinstance(outcome, Stop):
            auto_stop(conn, task_id, outcome.state, outcome.reason,
                      outcome.hint, alert=outcome.alert)
            return
        t = store.get_task(conn, task_id)
        state = t["state"]
        role = runner.step_role(t)

    reason, hint = auto_stop_advice(conn, task_id, state)
    auto_stop(conn, task_id, state, reason, hint,
              alert=_final_stop_raises_alert(state, steps))
