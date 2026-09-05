"""Цикл `auto`: advance до шага роли, затем — если роль ещё не закончила — run.

Крутится, пока в шаге работает агент (SPEC 01M1R8B3ZKXQT0Z0G6QQQDV906:
предварительный advance пробует готовый артефакт до запуска роли, не
после)."""
import time

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


def _cmd_auto(conn, task_id: str, session_id: str) -> None:
    t = store.get_task(conn, task_id)
    state = t["state"]
    store.journal(conn, task_id, "operator", "auto старт",
                  f"состояние {state}, лимит {config.AUTO_MAX_STEPS} шагов")
    print(f"[{task_id}] auto: старт из {state}, "
          f"лимит {config.AUTO_MAX_STEPS} шагов за вызов")

    steps = 0
    role = runner.step_role(t)
    # Текст отказа `advance` предыдущего шага без смены состояния; `None` —
    # предыдущий шаг не был таким отказом, или это первый шаг цикла
    # (SPEC T038, требование 1).
    prev_refusal = None
    # Число шагов ПОДРЯД без смены состояния (требование 2): сбрасывается
    # на 0 любым переходом, независимо от стоп-крана требования 1 (тот
    # считает только повтор ОДНОГО класса отказа, этот — каждый холостой
    # шаг). Опрос `verifying` (`_advance_verifying_poll`) не расходует
    # счётчик — не агентный шаг конвейера (см. `continue` ниже).
    idle_steps = 0
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

        # Лимит шагов гейтит попытку РОЛИ (реальный `run` или отказ,
        # который её замещает), не саму итерацию цикла (REVIEW.md итерации
        # 1, R1-F1): переход, который предварительный `advance` выполняет
        # САМ по уже готовому артефакту — без единого вызова `runner.
        # cmd_run` — бесплатен для лимита ровно так же, как раньше был
        # бесплатен для него advance, следовавший за `run` СРАЗУ внутри
        # одной и той же итерации (SPEC T038, «run+advance»): та же работа,
        # просто вызов сдвинулся на итерацию раньше. `steps` считает
        # каждую попытку, которая ЛИБО зовёт `cmd_run`, ЛИБО останавливает
        # цикл, ЛИБО пропускает шаг роли по отказу требования 4 — не
        # голые переходы. C `AUTO_MAX_STEPS == 1` цикл всё равно обязан
        # сделать РОВНО одну пару (advance, run) и встать (AC-1 приёмки):
        # то же самое место проверки, только сам счётчик растёт реже.
        if steps >= config.AUTO_MAX_STEPS:
            auto_stop(conn, task_id, state,
                      f"лимит {config.AUTO_MAX_STEPS} шагов за вызов исчерпан",
                      f"artel.py log {task_id} (что происходит), "
                      f"затем artel.py auto {task_id} — продолжит отсюда",
                      alert=True)
            return
        before = state

        # Предварительный advance (SPEC 01M1R8B3ZKXQT0Z0G6QQQDV906,
        # требования 1-4): пробуем перейти по уже готовым артефактам ДО
        # шага роли — так цикл не тратит шаг ($1-6) на подтверждение
        # очевидного (PLAN.md, поднятый ready ДО возврата из эскалации по
        # бюджету; REVIEW.md, вердикт которого уже вынесен).
        journaled_before = len(store.task_steps(conn, task_id))
        if fsm.cmd_advance(task_id, session_id=session_id):
            # guard отклонил артефакт-условие: тот же по характеру
            # немедленный стоп, что и раньше был доступен только ПОСЛЕ
            # шага роли, — цикл не зовёт cmd_run для того же состояния.
            steps += 1
            hint = f"почини артефакт и повтори artel.py advance {task_id}"
            auto_stop(conn, task_id, state,
                      f"advance отклонён guard'ом артефакта-условия — "
                      f"{hint}", hint, alert=True)
            return
        t = store.get_task(conn, task_id)
        state = t["state"]
        if state != before:
            # Требование 2: переход уже случился по готовым артефактам —
            # шаг роли этой итерации не нужен, цикл продолжает уже с
            # нового состояния. Не расходует `steps` (см. комментарий у
            # проверки лимита выше, R1-F1) — ни один агент не звался.
            note = f"шаг {role} не нужен: переход выполнен по готовым артефактам"
            store.journal(conn, task_id, "operator", note, f"{before} -> {state}")
            print(f"[{task_id}] {note} ({before} -> {state})")
            idle_steps = 0
            prev_refusal = None
            role = runner.step_role(t)
            continue

        refusal = _advance_refusal(conn, task_id, journaled_before)
        # Требование 4 отказывает шагу роли только на отказах, которые
        # ЧЕЛОВЕК обязан разобрать руками — лок acceptance_tests/,
        # свежесть ветки, гейт ёмкости diff: примеры требования 4 (кроме
        # «дерево не на ветке задачи», см. ниже) — из ПРОВЕРОК `in_dev`
        # ПОВЕРХ готового артефакта (PLAN.md уже ready/approved), не из
        # готовности самого артефакта роли. У `review`/`tests_writing` тот
        # же журналируемый префикс несёт и «вердикт REVIEW.md уже учтён»
        # (`artifacts.fresh_verdict_iteration`), и «не все AC покрыты
        # тестом» (`fsm._tests_writing_ac_state`) — оба ЖДУТ именно НОВОГО
        # прогона ЭТОЙ ЖЕ роли (тот же смысл, что и класс требования 3),
        # только исторически журналируются. Скопировать требование 4 на
        # них буквально значило бы, что `review`/`tests_writing` теряют
        # гарантию «роль хотя бы раз получит шанс отработать» насовсем:
        # текст отказа не меняется без нового прогона, стоп-кран T038 бьёт
        # на второй же итерации, и роль так и не запускается ни разу —
        # проверено прогоном `tests/test_auto_cycle.py::
        # AutoStopsWhereTheOperatorIsNeededTest::
        # test_review_iterations_are_passed_without_the_operator` (после
        # ЛЮБОГО changes_requested ревьювер больше не может вынести новый
        # вердикт) и `test_fresh_task_first_developer_step_still_runs`
        # (свежая задача, ещё нет ни одного теста/PLAN.md — тот же
        # стоп-кран до первого запуска test_author/developer). Оба —
        # регресс тяжелее того, что чинит эта SPEC (см. PLAN «Влияние на
        # систему»), поэтому «другой класс» здесь — только `in_dev`; для
        # прочих состояний журналируемый отказ ведёт себя как класс
        # требования 3 (роль всё равно запускается).
        #
        # «Дерево не на ветке задачи» (`fsm._read_branch_text_or_refuse`,
        # общий узел ВСЕХ четырёх обработчиков) срабатывает ДО того, как
        # handler вообще прочитал содержимое артефакта — файла нет НА
        # ВЕТКЕ, а не «нет доступа к git»: у `in_dev` это ПЕРВЫЙ ЖЕ заход
        # в состояние для КАЖДОЙ задачи (PLAN.md появляется только ВМЕСТЕ
        # с первым прогоном developer, ничто не заводит его файл заранее)
        # — тот же класс требования 3, что и «PLAN.md не ready» ниже по
        # тому же handler'у, журналируется только по историческому
        # совпадению реализации общего узла. Считать его «другим классом»
        # даже для `in_dev` блокировало бы developer НАВСЕГДА уже на
        # второй итерации ПЕРВОГО же вызова `auto` любой новой задачи
        # (стоп-кран T038 бьёт по идентичному тексту раньше, чем developer
        # получит хоть один шанс написать PLAN.md) — регрессия, которую
        # ловит `test_fresh_task_first_developer_step_still_runs`.
        tree_missing = refusal == "переход отклонён: дерево не на ветке задачи"
        other_class_refusal = refusal if (refusal is not None
                                          and state == "in_dev"
                                          and not tree_missing) else None
        if other_class_refusal is not None and other_class_refusal == prev_refusal:
            # Требование 1 (инцидент T035, SPEC T038): два подряд отказа
            # одним текстом — причина отказа вне зоны агента, прогон
            # агента её не лечит.
            steps += 1
            hint = f"почини причину и повтори artel.py advance {task_id}"
            auto_stop(conn, task_id, state, f"{other_class_refusal} — {hint}",
                      hint, alert=True)
            return
        prev_refusal = other_class_refusal
        idle_steps += 1
        if idle_steps >= config.AUTO_STALL_STEPS_LIMIT:
            # Требование 2: N шагов подряд без перехода — независимо от
            # класса отказа (в отличие от стоп-крана требования 1 выше,
            # который уже отсёк бы ДВА подряд отказа ОДНОГО класса раньше,
            # чем счётчик успел бы дойти до N при дефолтных значениях).
            # Хвост «, последний отказ: <класс>» — только если ПОСЛЕДНИЙ
            # из N шагов журналировал отказ требования 4 (ANSWER-1,
            # вопрос 3): его отсутствие само по себе несёт факт «агент
            # продолжал работу».
            steps += 1
            tail = (f", последний отказ: {other_class_refusal}"
                   if other_class_refusal is not None else "")
            reason = f"цикл не сходится: {idle_steps} шагов без перехода{tail}"
            hint = (f"artel.py log {task_id} — глянь, что происходит на "
                    f"последних шагах, затем artel.py advance {task_id}")
            auto_stop(conn, task_id, state, reason, hint, alert=True)
            return
        if other_class_refusal is not None:
            # Требование 4: журналируемый отказ другого класса — шаг роли
            # на этой итерации не запускается, цикл повторит advance
            # следующей итерацией (та же реакция, что и раньше — после
            # шага роли, — просто без самого шага). Расходует `steps`
            # (не свободный переход — агент так и не получил шанса).
            steps += 1
            continue

        # Требование 3: «артефакт роли не готов» (или, для `review`/
        # `tests_writing`, отказ, который лечится только новым прогоном
        # ЭТОЙ роли, см. комментарий выше) — запускаем роль как раньше.
        steps += 1
        run_journaled_before = len(store.task_steps(conn, task_id))
        try:
            runner.cmd_run(task_id, session_id=session_id)
        except SystemExit as exc:
            # Отказ стартовать `cmd_run` сообщает единственным способом —
            # sys.exit с текстом (исчерпанный бюджет, лимит параллельных
            # задач, штатная пауза). В цикле текст печатаем сами: пойманный
            # SystemExit нигде не покажется.
            print(str(exc))
            # Пауза (SPEC T070, требование 2) — не «эскалация по бюджету»:
            # причина должна быть видна Оператору в итоговом сообщении, а
            # не потеряться среди прочих отказов `run`. Причина — по тому,
            # что реально журналировал ИМЕННО этот вызов `cmd_run`
            # (`_run_paused_refusal`), а не по независимому текущему опросу
            # `pause.is_paused`: тот путал бы паузу с ОДНОВРЕМЕННЫМ отказом
            # по бюджету/лимиту параллельных задач, если Оператор выставил
            # оба (REVIEW.md T070, итерация 2, замечание 1) — тот же приём
            # различения, что уже несёт `_advance_refusal` выше.
            if _run_paused_refusal(conn, task_id, run_journaled_before):
                reason, hint = config.AUTO_STOP_PAUSE
                # Пауза — действие самого Оператора (ANSWER-1, вопрос 2):
                # он уже знает о причине остановки, алерт был бы
                # уведомлением о собственном же решении.
                auto_stop(conn, task_id, state, reason, hint.format(id=task_id),
                          alert=False)
                return
            # Занятость зоны (SPEC 01M1P9QAG65GVF69YJEV0V18D9, требование
            # 3) — причина внешняя (держит другая задача), не буксование
            # ЭТОГО агента: `status`/`doctor` берут на себя объяснение, кто
            # держит зону (требование 4), алерт буксования не открывается.
            if _run_zone_wait_refusal(conn, task_id, run_journaled_before):
                reason, hint = config.AUTO_STOP_ZONE_WAIT
                auto_stop(conn, task_id, state, reason, hint.format(id=task_id),
                          alert=False)
                return
            auto_stop(conn, task_id, state, "run отказался стартовать",
                      f"artel.py budget {task_id} <usd> или artel.py kill {task_id}",
                      alert=True)
            return

        # Состояние перечитываем: упавший агент и исчерпанный потолок
        # уводят задачу в escalated изнутри run — след предыдущей роли
        # (для сообщения ниже), не текущего перечитанного состояния.
        t = store.get_task(conn, task_id)
        state = t["state"]
        # Живой вывод агента уже был на экране и в логе — здесь только
        # сводка шага и ссылка на лог прогона (требование 6). Advance по
        # СВЕЖЕМУ результату этого шага цикл не зовёт отдельно — тем же
        # вызовом займётся предварительный `advance` следующей итерации
        # (или, если роли в новом состоянии больше нет, финальный стоп
        # ниже цикла).
        print(f"[{task_id}] auto шаг {steps}/{config.AUTO_MAX_STEPS}: {role} "
              f"{before} -> {state}, "
              f"лог: {agent_log.last_agent_log(task_id, role)}")
        role = runner.step_role(t)

    reason, hint = auto_stop_advice(conn, task_id, state)
    auto_stop(conn, task_id, state, reason, hint,
              alert=_final_stop_raises_alert(state, steps))
