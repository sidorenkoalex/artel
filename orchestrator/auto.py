"""Цикл `auto`: advance до шага роли, затем — если роль ещё не закончила — run.

Крутится, пока в шаге работает агент (SPEC 01M1R8B3ZKXQT0Z0G6QQQDV906:
предварительный advance пробует готовый артефакт до запуска роли, не
после)."""
import re
import signal
import time
from dataclasses import dataclass

from . import (agent_log, alerts, budget, ci, config, cycle_hint, fixation,
              fsm, lease, models, pause, pull, runner, store, zone_lock)
from .advance_gates import refusal_classes

# Флаг «пришёл SIGTERM (команда `stop`, SPEC 01M1NWCHVTYQ0M8PCJ1YJ2N78P,
# требование 5)»: цикл доигрывает уже начатый шаг и останавливается сам
# на ближайшей границе между шагами, не разрывая run+advance текущего.
# Модульный уровень — сигнал асинхронный, обычный локальный флаг функции
# ему не адресуем.
_stop_requested = False

# Взведён только на время сна между опросами зоны
# (`_sleep_until_next_poll`) — единственная длинная пауза цикла, в которой
# «остановлюсь на границе между шагами» означало бы «не остановлюсь часами».
_zone_wait_sleeping = False


class _StopDuringZoneWait(Exception):
    """Сон между опросами зоны прерван командой `stop`. Бросается ИЗ
    обработчика сигнала, поэтому возникает ровно в точке `time.sleep` и
    только пока `_zone_wait_sleeping` взведён; ловит его тот же
    `_sleep_until_next_poll`, который сон и начал."""


def _on_sigterm(signum, frame) -> None:
    global _stop_requested
    _stop_requested = True
    if _zone_wait_sleeping:
        # Решение Оператора 28.09.2026 (ANSWER-2, п.1): пока ожидание зоны
        # включалось флагом вручную, «стоп учтётся на границе шагов» было
        # терпимо; с включённым `config.AUTO_WAIT_ZONE_DEFAULT` в ожидание
        # уходит КАЖДЫЙ вызов `auto`, и `stop` молча переставал бы работать
        # на срок до `config.ZONE_WAIT_MAX_SEC`. Уже начатый шаг роли это
        # по-прежнему не прерывает — там флаг не взведён.
        raise _StopDuringZoneWait()

# Действие журнала, которым отказ `advance` узнаётся вне зависимости от
# конкретной причины (SPEC T038, требование 1): каждая точка `cmd_advance`
# (orchestrator/fsm.py) журналирует отказ actor'ом "fsm" и action,
# начинающимся с этой фразы, — включая guard структуры артефакта
# («переход отклонён guard'ом»), который с SPEC 01M446WEVJXARR5CDED8RE9CCR
# (требование 4) — такой же отказ класса «чинит роль», как остальные.
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


# Причина остановки цикла по исчерпанному потолку ожидания (требование
# 3, AC-4/AC-8б) — задача остаётся в `state`, НЕ эскалирует. Тексты
# входа/выхода самого ожидания (AC-1..AC-3) живут в `zone_lock.
# wait_enter_action`/`wait_exit_action` — `catalog.cmd_status`
# (требование 4, AC-6) читает те же записи независимо от `auto`, единый
# словарь, тот же приём, что уже развёл REFUSAL_ACTION/RELEASE_ACTION.
_ZONE_WAIT_CEILING_REASON = "потолок ожидания зоны исчерпан"

# Причина остановки цикла, если heartbeat lease этой сессии не удалось
# продлить внутри ожидания (REVIEW.md итерация 1, R1-F2): `lease.acquire`
# отказывает только чужой ЖИВОЙ сессии (см. её докстринг) — при
# `_wait_for_zone`, вызванном из-под `_cmd_auto`, это может значить
# только перехват lease другой сессией во время долгого ожидания.
# Продолжать опрос как ни в чём не бывало значило бы молча делить
# владение задачей с чужой сессией — именованная остановка безопаснее
# тихого игнорирования отказа.
_ZONE_WAIT_LEASE_LOST_REASON = "lease задачи потерян во время ожидания зоны"

# Причина остановки цикла по команде `stop` — общая у границы между шагами
# и у прерванного ожидания зоны (ANSWER-2, п.2: прерванное ожидание
# завершает цикл ТАК ЖЕ, как `stop` на границе): задача остаётся в своём
# состоянии, lease снимает `lease.run_locked` штатно, эскалации нет.
_STOP_COMMAND_REASON = "штатная остановка — команда stop"


def _stop_command_stop(conn, task_id: str, state: str) -> "Stop":
    """Исход остановки по команде `stop` — один на обе её точки."""
    return Stop(state, _STOP_COMMAND_REASON,
                cycle_hint.launch_text(conn, task_id, "auto",
                                       "— продолжит отсюда"), False)


def _sleep_until_next_poll() -> bool:
    """Пауза до следующего опроса зоны; `True` — пришла команда `stop`,
    ожидание прерывается, не досыпая интервал.

    Пауза остаётся ОДНИМ вызовом `time.sleep(config.ZONE_WAIT_POLL_SEC)`:
    интервал опроса задача не меняет (ANSWER-2, п.1), и на «ровно
    интервал» опирается всё, что этот сон подменяет. Слышимость `stop`
    даёт не нарезка сна на короткие шаги, а прерывание самого сна —
    обработчик сигнала бросает `_StopDuringZoneWait` прямо из
    `time.sleep`, поэтому команда слышна в тот же момент, а не через
    очередной интервал опроса.
    """
    global _zone_wait_sleeping
    if _stop_requested:
        return True
    try:
        _zone_wait_sleeping = True
        # Сигнал мог прийти в окне между проверкой выше и взведением
        # флага — тогда обработчик только пометил `_stop_requested` и не
        # бросил; проверка закрывает окно, не начиная сон.
        if not _stop_requested:
            time.sleep(config.ZONE_WAIT_POLL_SEC)
    except _StopDuringZoneWait:
        pass
    finally:
        _zone_wait_sleeping = False
    return _stop_requested


def _wait_for_zone(conn, task_id: str, session_id: str, state: str) -> "Stop | None":
    """Цикл ожидания зоны требования 1 (AC-1..AC-4, AC-8а/б): опрашивает
    `zone_lock.blocking_conflict` целиком (та же проверка, что не пускает
    `run` дальше, не отдельная копия — `done`/`killed` держателя
    освобождают зону ровно так же, как и любой другой исход, AC-8а) с
    интервалом `config.ZONE_WAIT_POLL_SEC`, продлевая heartbeat lease
    (`lease.acquire` тем же `session_id`, что уже держит lease весь цикл
    `_cmd_auto`) на каждом опросе.

    Потолок `config.ZONE_WAIT_MAX_SEC` — НАКОПЛЕННОЕ время опросов
    (счётчик внутри самой функции), не разница `store.now()`: секундная
    точность `store.now()` не различает несколько РЕАЛЬНЫХ опросов
    внутри одного вызова (AC-8б, доли секунды) — счётчик верен
    независимо от того, подменяет ли вызывающий код источник времени.

    `None` — зона свободна (либо не была занята вовсе — вызывающий уже
    убедился в конфликте до вызова). `Stop` — потолок исчерпан, lease
    этой сессии потерян во время ожидания либо пришла команда `stop`
    (`_sleep_until_next_poll`, ANSWER-2 01M3KHQS7EQTHDT1RGCNH4KGTW):
    задача остаётся `state` (обычно `in_dev`), НЕ эскалирует
    (требование 3).
    """
    t = store.get_task(conn, task_id)
    conflict = zone_lock.blocking_conflict(conn, task_id, t)
    if conflict is None:
        return None
    path, occupier_id, occupier_state = conflict
    entry = zone_lock.wait_enter_action(path, occupier_id, occupier_state)
    store.journal(conn, task_id, "operator", entry, "")
    print(f"[{task_id}] {entry}")

    elapsed_sec = 0.0
    while True:
        if _stop_requested:
            return _stop_command_stop(conn, task_id, state)
        if elapsed_sec >= config.ZONE_WAIT_MAX_SEC:
            hint = (f"artel.py status  (кто держит зону) — дождись мержа/kill "
                    f"занявшей задачи либо artel.py zone-release {task_id}, "
                    f"затем " + cycle_hint.launch_text(conn, task_id, "auto"))
            return Stop(state, _ZONE_WAIT_CEILING_REASON, hint, False)
        if _sleep_until_next_poll():
            return _stop_command_stop(conn, task_id, state)
        elapsed_sec += config.ZONE_WAIT_POLL_SEC
        lease_refusal, _ = lease.acquire(conn, task_id, session_id)
        if lease_refusal is not None:
            hint = cycle_hint.launch_text(conn, task_id, "auto",
                                          "— перезапусти ожидание")
            return Stop(state, f"{_ZONE_WAIT_LEASE_LOST_REASON}: {lease_refusal}",
                        hint, True)
        t = store.get_task(conn, task_id)
        conflict = zone_lock.blocking_conflict(conn, task_id, t)
        if conflict is None:
            break
        # Требование 1/AC-3: держатель мог смениться между опросами (одна
        # задача мержится/убивается, следующая по очереди зону не отпускает
        # тут же) — атрибуция записи выхода обязана называть ПОСЛЕДНЕГО
        # реального держателя, а не того, кто был занявшим до входа в цикл
        # (REVIEW.md итерации 1, R1-F1: без этого обновления запись «зона
        # свободна... держал <id>» называла бы устаревшего держателя).
        path, occupier_id, occupier_state = conflict

    minutes = int(elapsed_sec // 60)
    exit_action = zone_lock.wait_exit_action(occupier_id, minutes)
    store.journal(conn, task_id, "operator", exit_action, "")
    print(f"[{task_id}] {exit_action}")
    return None


def _run_wave_breaker_refusal(conn, task_id: str, journaled_before: int) -> bool:
    """Отказал ли `run` ИМЕННО этим вызовом из-за открытого алерта
    стоп-крана волны self (01M1THKRK8HPXA7Y2SRB0RFTN2, требование 1) —
    тот же приём отсечки, что `_run_paused_refusal` уже применяет к
    штатной паузе."""
    for row in store.task_steps(conn, task_id)[journaled_before:]:
        if row["action"] == runner.WAVE_BREAKER_REFUSAL_ACTION:
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
REWORK_REFUSAL_ACTION = refusal_classes.REWORK_REFUSAL_ACTION

# Действие журнала общего узла чтения артефакта роли текущего состояния
# с ветки (`fsm._read_branch_text_or_refuse`).
TREE_NOT_ON_BRANCH_REFUSAL_ACTION = refusal_classes.TREE_NOT_ON_BRANCH_REFUSAL_ACTION

# Подкласс «роль ещё не закончила» (SPEC 01M290PYPV5T2NFW1Y0HB8BD6E,
# требование 3) — из единого перечня классов отказов.
ROLE_NOT_FINISHED_REFUSAL_ACTIONS = refusal_classes.ROLE_NOT_FINISHED_REFUSAL_ACTIONS

# Действия класса «чинит роль» (SPEC 01M446WEVJXARR5CDED8RE9CCR,
# требование 1) — прежнее имя перечня `in_dev` сохранено: класс задаёт
# `refusal_classes`, а не состояние.
_IN_DEV_ROLE_FIXABLE_REFUSAL_ACTIONS = tuple(
    action for action, klass in refusal_classes.REFUSAL_CLASSES.items()
    if klass == refusal_classes.ROLE_FIXES)

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

# Маркеры эскалаций, несущих СОБСТВЕННОЕ основание переделки — запись
# возврата из `escalated`, которой предшествовал любой из них, становится
# анкером рубежа `_role_step_since_state_entry`, а не пропускается как
# `_ESCALATED_RETURN_DETAILS` (см. докстринг там же). Конфликт подтяжки
# `in_dev` (SPEC 01M290PYPV5T2NFW1Y0HB8BD6E) и эскалация по содержимому
# артефакта роли — пометка `AC-n: escalate`/батч `QUESTIONS.md` (SPEC
# 01M2XFSJ1Z7BS6HR69SAT1D81Y, требование 3) — один класс: разрешить
# основание некому, кроме роли, и ответ Оператора обязан дойти до неё
# раньше следующего предварительного advance.
_ROLE_STEP_REQUIRED_MARKERS = (pull.PULL_CONFLICT_ROLE_STEP_MARKER,
                               fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER)


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

    Исключение (SPEC 01M290PYPV5T2NFW1Y0HB8BD6E, требование 1, П1
    копилки 11.09): эскалация `in_dev` по НЕРАЗРЕШЁННОМУ конфликту
    содержимого подтяжки метит себя `pull.PULL_CONFLICT_ROLE_STEP_MARKER`
    (журналируется сразу ПОСЛЕ записи `state -> escalated`, до возврата) —
    в отличие от `_ESCALATED_RETURN_DETAILS`, ЭТА эскалация несёт
    собственное основание переделки (разрешить конфликт некому, кроме
    роли): запись возврата, которой ПРЕДШЕСТВОВАЛ такой маркер, сама
    становится анкером — не пропускается, даже хотя её `detail` совпадает
    с общим текстом `_approve_escalated`. Маркер «гасится» первой же
    следующей записью `state -> {state}` (израсходован — независимо от
    того, пропущена она или стала анкером) и любым ДРУГИМ переходом
    состояния (`state -> X`, `X` не `escalated`) — иначе разросся бы на
    несвязанный последующий визит state, до которого маркер не долетел
    бы по смыслу.

    Тот же класс и тот же приём (SPEC 01M2XFSJ1Z7BS6HR69SAT1D81Y,
    требования 3-4, П1 копилки 13.09) — эскалация по СОДЕРЖИМОМУ артефакта
    роли (`fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER`: пометка `AC-n:
    escalate` в `tests_writing`, батч `QUESTIONS.md` в `spec_writing`):
    без анкера на записи возврата пред-advance перечитывал ту же
    пометку/тот же батч и повторял уже отвеченную эскалацию раньше шага
    роли, поднимая `answer_baseline`. Оба маркера — `_ROLE_STEP_REQUIRED_
    MARKERS` — читаются и гасятся одинаково; в `spec_writing` анкером
    может стать и самая первая запись `state -> spec_writing` задачи
    (первый вход туда `cmd_new` не журналирует).
    """
    rows = store.task_steps(conn, task_id)
    marker = f"state -> {state}"
    last_entry = None
    role_step_required = False
    for i, row in enumerate(rows):
        action = row["action"]
        if action in _ROLE_STEP_REQUIRED_MARKERS:
            role_step_required = True
            continue
        if action == marker:
            if row["detail"] not in _ESCALATED_RETURN_DETAILS or role_step_required:
                last_entry = i
            role_step_required = False
            continue
        if action.startswith("state -> ") and action != "state -> escalated":
            role_step_required = False
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
    sha_hint = set_hint = ""
    if needs_sha:
        target = store.task_target(conn, task_id)
        sha_hint = fixation.approve_sha_hint(task_id, target)
        # Набор моделей задачи — в подсказке гейта (SPEC
        # 01M3YCHS4F08VTV6XX10VF92H3, требование 8): Оператор решает
        # гейт, зная, на каких моделях шла задача.
        set_hint = models.task_set_hint(store.get_task(conn, task_id))
    return reason, hint.format(id=task_id, sha=sha_hint) + set_hint


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


def cmd_auto(task_id: str, session_id: str | None = None,
            wait_zone: bool = False) -> None:
    """Цикл advance+run, пока в шаге работает агент, — до места, где нужен человек.

    `wait_zone` (SPEC 01M1VBEAWZW4EBZHKMGNBBK648, требования 1, 3,
    AC-1..AC-5): `True` (либо `config.AUTO_WAIT_ZONE_DEFAULT`, AC-5) —
    отказ занятости зоны не останавливает цикл, а ждёт освобождения
    (`_wait_for_zone`) и продолжает тем же вызовом (AC-3). С 28.09.2026
    настройка включена решением Оператора (SPEC
    01M3KHQS7EQTHDT1RGCNH4KGTW), поэтому ждут ВСЕ вызовы `auto`: флаг
    остаётся допустимым, но ничего не меняет, а дефолт `False` самого
    параметра значит лишь «флага в командной строке не было». Границы
    ожидания — потолок `config.ZONE_WAIT_MAX_SEC` и команда `stop`
    (`_sleep_until_next_poll` прерывает сон между опросами).

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
    global _stop_requested
    _stop_requested = False
    # SIGTERM — сигнал команды `stop` (SPEC требование 5), штатная просьба
    # остановиться между шагами (см. `_stop_requested` выше). Ставится ДО
    # lease/цикла — сигнал технически может прийти даже до первого шага.
    signal.signal(signal.SIGTERM, _on_sigterm)
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    try:
        lease.run_locked(conn, task_id, session_id,
                         lambda sid: _cmd_auto(conn, task_id, sid, wait_zone),
                         on_refusal="print")
    except BaseException as exc:
        # Обрыв НЕ через `stop` (SPEC требование 7, AC-11): сигнал без
        # обработчика вроде SIGINT, необработанное исключение — если
        # процесс успевает выполнить код (в отличие от SIGKILL/
        # аварийного убийства ОС), это место его ловит и журналирует
        # причину до того, как исключение уронит процесс.
        store.journal(conn, task_id, "operator", "цикл оборван",
                      f"{type(exc).__name__}: {exc}")
        raise


@dataclass
class _CycleState:
    """Состояние, разделяемое между итерациями цикла (AC-2): не локальные
    флаги `_cmd_auto`, а поля объекта, которым владеет и который мутирует
    только шаг (б) — `_pre_advance_step`. `idle_steps` — число шагов
    подряд без смены состояния (требование 2, сбрасывается любым
    переходом); `prev_refusal` — наследие стоп-крана «два подряд
    одинаковых отказа» (SPEC T038): с единой реакцией по классу отказа
    (SPEC 01M446WEVJXARR5CDED8RE9CCR) второй одинаковый отказ класса
    «чинит Оператор» не наступает — остановка уже на первом, поэтому
    `_pre_advance_step` только сбрасывает поле."""
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
class Stop:
    """Исход шага (г): цикл обязан остановиться этой же итерацией — поля
    ровно те, что принимает `auto_stop` (шаг д)."""
    state: str
    reason: str
    hint: str
    alert: bool


def _step_limit_stop(conn, task_id: str, state: str, steps: int) -> Stop | None:
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
                f"затем " + cycle_hint.launch_text(conn, task_id, "auto",
                                                   "— продолжит отсюда"))
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


# Основание (требование 2) — единственный класс эскалации, отмеченный
# `pull.PULL_CONFLICT_ROLE_STEP_MARKER`, читается стоп-краном ниже.
_PULL_CONFLICT_BASIS_LABEL = "конфликт подтяжки"


def _pull_conflict_marker_streak(rows: list) -> int:
    """Число подряд идущих эскалаций `in_dev` по одному и тому же
    основанию — неразрешённому конфликту подтяжки (требование 2, AC-4):
    считает записи `pull.PULL_CONFLICT_ROLE_STEP_MARKER`, но сбрасывается
    ЛЮБЫМ переходом состояния, кроме самой пары `escalated`/`in_dev`
    (`state -> escalated` держит счёт — это собственный переход
    эскалации; `state -> in_dev` держит его тоже — это возврат
    Оператора) — задача реально продвинулась мимо конфликта (например,
    ушла в `review`), новая эскалация того же основания, если случится
    позже, начинает счёт заново, не продолжает старый."""
    streak = 0
    for row in rows:
        action = row["action"]
        if action == pull.PULL_CONFLICT_ROLE_STEP_MARKER:
            streak += 1
        elif (action.startswith("state -> ")
              and action not in ("state -> escalated", "state -> in_dev")):
            streak = 0
    return streak


def _role_step_between_repeated_refusals(rows: list, journaled_before: int,
                                         action: str, role: str) -> bool:
    """Был ли завершённый шаг `role` (запись `agent run finished`) между
    ПРЕДЫДУЩИМ отказом `action` этого же визита состояния и текущим
    (записи с индекса `journaled_before` — текущий вызов `cmd_advance`) —
    защита от кружения на отказе «мандат есть, раздел PLAN не оформлен»
    (SPEC 01M2XFSNVGWA2VX5XFEYR93Y4Z, требование 5/AC-5), с SPEC
    01M446WEVJXARR5CDED8RE9CCR (требование 2) — на любом отказе класса
    «чинит роль» в любом из четырёх агентских состояний.

    Именно «шаг между двумя отказами», не «шаг с момента входа в
    состояние» (`_role_step_since_state_entry`): в сценарии инцидента
    13.09 шаг developer уже БЫЛ до первого такого отказа, и общая проверка
    остановила бы цикл, не дав роли ни одного шага на оформление раздела
    (AC-3). Предыдущего отказа `action` в этом визите нет (граница — любая
    запись `state -> …`, как у `store.refusal_history`) — `False`: роль
    свой гарантированный шаг ещё не получала."""
    seen_role_step = False
    for row in reversed(rows[:journaled_before]):
        if row["action"] == action:
            return seen_role_step
        if row["action"].startswith("state -> "):
            return False
        if row["actor"] == role and row["action"] == "agent run finished":
            seen_role_step = True
    return False


def _pre_advance_step(conn, task_id: str, session_id: str, role: str,
                      state: str, before: str,
                      cycle: _CycleState) -> Advanced | Stop | None:
    """Шаг (б) — предварительный advance по уже готовым артефактам (SPEC
    01M1R8B3ZKXQT0Z0G6QQQDV906, требования 1-4): пробуем перейти по уже
    готовым артефактам ДО шага роли — так цикл не тратит шаг на
    подтверждение очевидного (PLAN.md, поднятый ready ДО возврата из
    эскалации по бюджету; REVIEW.md, вердикт которого уже вынесен).
    Разбор исхода включает часть стоп-кранов (г) — реакцию на отказ по
    его классу и «N шагов без перехода» — они считаются по факту именно
    ЭТОЙ попытки, поэтому естественно живут здесь же, не в отдельной
    функции.

    Реакция на журналируемый отказ — по классу из единого перечня
    `refusal_classes` (SPEC 01M446WEVJXARR5CDED8RE9CCR, требования 1-4),
    одинаково во всех четырёх агентских состояниях: «чинит Оператор»
    (и всё, чего в перечне нет) — `Stop` с первого отказа; «чинит роль»
    (включая guard артефакта) — `None`, вызывающий запускает шаг роли, а
    тот же отказ, повторившийся после завершённого шага той же роли в
    этом визите, — `Stop`.

    `None` — advance не перевёл состояние, а отказ, если был, класса
    «чинит роль»: вызывающий запускает роль как обычно.
    """
    journaled_before = len(store.task_steps(conn, task_id))
    guard_refused = fsm.cmd_advance(task_id, session_id=session_id)

    t = store.get_task(conn, task_id)
    new_state = t["state"]
    if new_state != before:
        # Требование 2 (AC-4): ЭТОТ ЖЕ вызов только что эскалировал по
        # неразрешённому конфликту подтяжки (маркер среди строк,
        # добавленных ИМЕННО этим `cmd_advance`, не более раннего) —
        # если это уже ВТОРАЯ подряд эскалация того же основания (гейт
        # (а) `_rework_gate_blocks` уже дал роли её единственный
        # гарантированный шанс между ними), новых шансов больше не даём:
        # именованная остановка вместо тихого продвижения в generic
        # «advance остановлен на escalated» (не даёт циклу жечь эскалации
        # по кругу).
        just_escalated_via_pull_conflict = any(
            row["action"] == pull.PULL_CONFLICT_ROLE_STEP_MARKER
            for row in store.task_steps(conn, task_id)[journaled_before:])
        if new_state == "escalated" and just_escalated_via_pull_conflict:
            streak = _pull_conflict_marker_streak(store.task_steps(conn, task_id))
            if streak >= 2:
                hint = (f"artel.py show {task_id} — реши конфликт вручную, "
                        f"затем artel.py answer/approve {task_id}")
                reason = (f"предварительный advance дважды упёрся в "
                          f"{_PULL_CONFLICT_BASIS_LABEL} без шага роли — "
                          f"решение Оператора")
                return Stop(new_state, reason, hint, True)
        # Требование 2 (SPEC 01M1R8B3ZKXQT0Z0G6QQQDV906): переход уже
        # случился по готовым артефактам — шаг роли этой итерации не
        # нужен, цикл продолжает уже с нового состояния. Не расходует
        # `steps` — ни один агент не звался.
        note = f"шаг {role} не нужен: переход выполнен по готовым артефактам"
        store.journal(conn, task_id, "operator", note, f"{before} -> {new_state}")
        print(f"[{task_id}] {note} ({before} -> {new_state})")
        cycle.idle_steps = 0
        cycle.prev_refusal = None
        return Advanced(before, new_state)

    refusal = _advance_refusal(conn, task_id, journaled_before)
    if guard_refused and refusal is None:
        # guard отказал, не журналировав отказ (подменённый `cmd_advance`
        # без записи): класса не прочитать — прежняя немедленная остановка.
        hint = f"почини артефакт и повтори artel.py advance {task_id}"
        return Stop(state,
                    f"advance отклонён guard'ом артефакта-условия — {hint}",
                    hint, True)
    cycle.prev_refusal = None
    if refusal is not None:
        # Отказ класса «чинит Оператор» (решение, мандат, сбой git/окружения,
        # действие вне перечня) прогон роли не лечит — остановка с первого
        # раза, без шага роли (требование 3).
        operator_class = (refusal_classes.refusal_class(refusal)
                          == refusal_classes.OPERATOR_FIXES)
        # Отказ класса «чинит роль», повторившийся после завершённого шага
        # той же роли в этом визите: роль свой гарантированный шаг уже
        # получила и причину не устранила — дальше решает Оператор
        # (требование 2). Подкласс «роль ещё не закончила» — артефакта роли
        # на ветке ещё нет, как и у нежурналируемого «PLAN.md не ready»:
        # роль дописывает его следующим шагом, от кружения держит порог
        # холостых шагов (`tests/test_auto_cycle.py::
        # test_review_iterations_are_passed_without_the_operator`).
        repeated = (refusal not in ROLE_NOT_FINISHED_REFUSAL_ACTIONS
                    and _role_step_between_repeated_refusals(
                        store.task_steps(conn, task_id), journaled_before,
                        refusal, role))
        if operator_class or repeated:
            hint = f"почини причину и повтори artel.py advance {task_id}"
            return Stop(state, f"{refusal} — {hint}", hint, True)
    cycle.idle_steps += 1
    if cycle.idle_steps >= config.AUTO_STALL_STEPS_LIMIT:
        # Требование 2 (SPEC 01M1KCSTBYF1CRJBSY4P6VYQEA): N шагов подряд без
        # перехода — считает и шаги роли на отказах класса «чинит роль» с
        # разными действиями (SPEC 01M446WEVJXARR5CDED8RE9CCR, требование
        # 7). Хвост «, последний отказ: …» — только если ПОСЛЕДНИЙ из N
        # шагов журналировал отказ (ANSWER-1, вопрос 3): его отсутствие
        # само по себе несёт факт «агент продолжал работу».
        tail = f", последний отказ: {refusal}" if refusal is not None else ""
        reason = f"цикл не сходится: {cycle.idle_steps} шагов без перехода{tail}"
        hint = (f"artel.py log {task_id} — глянь, что происходит на "
                f"последних шагах, затем artel.py advance {task_id}")
        return Stop(state, reason, hint, True)
    return None


def _role_run_step(conn, task_id: str, session_id: str, role: str,
                   state: str, before: str, steps: int,
                   wait_zone: bool) -> RoleRan | Stop:
    """Шаг (в) — запуск шага роли и разбор исхода: успешное завершение
    (включая эффект вроде эскалации внутри самого шага) против отказа
    `run` стартовать (пауза, занятость зоны, бюджет, лимит
    параллельности). Отказ стартовать `cmd_run` сообщает единственным
    способом — `sys.exit` с текстом; в цикле текст печатаем сами:
    пойманный `SystemExit` нигде не покажется.

    `wait_zone` (SPEC 01M1VBEAWZW4EBZHKMGNBBK648, требования 1, 3,
    AC-1..AC-4, AC-8): эффективный режим — `wait_zone or config.
    AUTO_WAIT_ZONE_DEFAULT` (AC-5). Отказ занятости зоны в этом режиме
    не останавливает цикл — `_wait_for_zone` ждёт освобождения (либо
    возвращает `Stop` по исчерпанному потолку, требование 3, по потере
    lease или по команде `stop`) и, если зона освободилась, ЭТА ЖЕ
    функция повторяет `runner.cmd_run` тем же вызовом (AC-3) — без
    выхода наружу и без ручного перезапуска.
    """
    while True:
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
                if wait_zone or config.AUTO_WAIT_ZONE_DEFAULT:
                    wait_outcome = _wait_for_zone(conn, task_id, session_id, state)
                    if wait_outcome is not None:
                        return wait_outcome
                    # Зона освободилась — повторяем run тем же вызовом
                    # (AC-3), без выхода из этой функции.
                    continue
                reason, hint = config.AUTO_STOP_ZONE_WAIT
                return Stop(state, reason, hint.format(id=task_id), False)
            # Стоп-кран волны, часть 2 (01M1THKRK8HPXA7Y2SRB0RFTN2, требования
            # 1, 3-4) — причина уже видна первой строкой `doctor` и пометкой
            # `status` у каждой задачи target self: алерт буксования здесь
            # был бы дублем уже открытого incident-алерта.
            if _run_wave_breaker_refusal(conn, task_id, run_journaled_before):
                reason, hint = config.AUTO_STOP_WAVE_BREAKER
                return Stop(state, reason, hint.format(id=task_id), False)
            return Stop(state, "run отказался стартовать",
                        f"artel.py budget {task_id} <usd> или artel.py kill {task_id}",
                        True)
        else:
            break

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


def _cmd_auto(conn, task_id: str, session_id: str, wait_zone: bool = False) -> None:
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
        if _stop_requested:
            # SPEC 01M1NWCHVTYQ0M8PCJ1YJ2N78P требование 5, AC-9:
            # проверяется ИМЕННО на границе между шагами (верх цикла,
            # после того как прошлый run+advance уже отработал целиком)
            # — уже начатый шаг сигнал не прерывает, доиграет своим
            # чередом. Вторая точка того же исхода — прерванное ожидание
            # зоны (`_wait_for_zone`, ANSWER-2 п.2), поэтому поля стопа
            # собирает общий `_stop_command_stop`.
            stop = _stop_command_stop(conn, task_id, state)
            auto_stop(conn, task_id, stop.state, stop.reason, stop.hint,
                      alert=stop.alert)
            return
        if state == "verifying":
            if _advance_verifying_poll(conn, task_id, session_id):
                return
            t = store.get_task(conn, task_id)
            state = t["state"]
            role = runner.step_role(t)
            continue

        limit_stop = _step_limit_stop(conn, task_id, state, steps)
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

        steps += 1
        outcome = _role_run_step(conn, task_id, session_id, role, state,
                                 before, steps, wait_zone)
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
