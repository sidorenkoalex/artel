"""Потолок задачи: значение из SPEC, блокировка `run`, реакция после шага."""
import sqlite3
import sys

from . import alerts, config, gitcmd, lease, retro, spend, store

# Действие журнала, которым `enforce_budget` фиксирует sha головы кодовой
# ветки в момент эскалации ПО БЮДЖЕТУ из состояния `review` (SPEC
# 01M1VBEDGMEXHVGWAH42FTDZ4X, требование 3): `fsm_advance.py::review()`
# читает эту запись, чтобы решить, нужен ли новый прогон reviewer при
# возврате (см. её докстринг про отсечку «новее последнего прогона
# reviewer»).
REVIEW_ESCALATION_CODE_SHA_ACTION = "эскалация review: sha кода зафиксирован"


def spec_budget(meta: dict) -> tuple[float | None, str]:
    """Потолок из frontmatter SPEC: (сумма, причина отказа).

    Исходов три, а не два. Поля нет — (None, ""), и это не событие: задача
    работает по дефолту, как работала (требование 2). Поле есть, но взять
    его нельзя — (None, причина): аналитик что-то имел в виду, и молчать об
    этом нельзя. Иначе (сумма, "").

    Число разбирается тем же `cli_number`, что и аргумент команды `budget`:
    одно правило на оба входа в потолок, включая отсев nan/inf.

    Причин отказа две, и они разные по смыслу: «не сумма» — значение
    непонятно, «выше потолка ролей» — значение понятно, но применить его
    значило бы поднять потолок задачи выше `ROLE_BUDGET_CAP` без Оператора
    (инвариант 10, ADR-0014). В пределах потолка ролей значение
    применяется и выше, и ниже DEFAULT_BUDGET_USD — сравнение с потолком
    задачи здесь ни при чём: у задач из старых БД потолок $5–$10 от
    прежних дефолтов, и сравнение с текущим потолком отвергло бы у них
    разрешённые SPEC суммы.
    """
    if "budget_usd" not in meta:
        return None, ""
    raw = str(meta["budget_usd"]).strip()
    # YAML-кавычки вокруг числа — форма записи, а не отказ: `budget_usd: "25"`
    # аналитик пишет по привычке, и сумма от этого суммой быть не перестаёт.
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        raw = raw[1:-1].strip()
    value = spend.cli_number(raw)
    if value is None or value <= 0:
        return None, f"'{raw}' — не сумма в долларах"
    if value > config.ROLE_BUDGET_CAP:
        return None, (f"${value:.2f} выше потолка ролей "
                      f"${config.ROLE_BUDGET_CAP:.2f} — "
                      f"поднятие выше только командой budget (Оператором)")
    return value, ""


def apply_spec_budget(conn, t: sqlite3.Row, meta: dict) -> None:
    """Ставит задаче потолок из SPEC — перечитывая изменения, но никогда
    поверх ручного.

    Вызывается на переходе spec_writing -> spec_gate: SPEC к этому моменту
    прочитан и признан готовым, а денег задача ещё не потратила (агент
    запускается только из in_dev и review).

    Кто задал потолок, помнит `budget_source`: значение из SPEC никогда
    не перебивает поднятие Оператора (`budget_source=operator`) — в
    какую бы сторону ни шёл порядок (требование 4). Но источник `spec`
    сам по себе не запрещает повторное применение — запрещает только
    совпадение с уже применённым значением (REVIEW.md
    01M1SHJX22EMEP4AJ9FFJJ09DC итерация 1, R1-F1): approve на spec_gate
    (SPEC 01M1SHJX22EMEP4AJ9FFJJ09DC, требования 4-5) зовёт эту функцию
    ВТОРЫМ разом, уже после того, как `spec_writing -> spec_gate`
    применил исходное значение — если Оператор успел поправить SPEC
    ПРЯМО на гейте, новое значение обязано подхватиться, а не быть
    молча отвергнутым как «уже применён».

    Функция ничего не бросает и состояние не двигает: и непонятное значение,
    и значение выше дефолта — это предупреждение Оператору, а не остановка
    задачи (требование 3). Отказ и «не применён» — разные действия журнала:
    Оператор читает журнал по действию, и обе строки означают, что потолок
    остался прежним.
    """
    task_id = t["id"]
    old = t["budget_usd"] or 0.0
    value, refused = spec_budget(meta)

    if refused:
        detail = f"{refused}, остаётся потолок ${old:.2f}"
        store.journal(conn, task_id, "fsm", "бюджет из SPEC отклонён", detail)
        print(f"[{task_id}] ВНИМАНИЕ: бюджет из SPEC отклонён: {detail}")
        return
    if value is None:
        return

    source = t["budget_source"]
    if source == config.BUDGET_SOURCE_OPERATOR:
        detail = f"${value:.2f} — потолок задан Оператором, остаётся ${old:.2f}"
        store.journal(conn, task_id, "fsm",
                      "бюджет из SPEC не применён", detail)
        print(f"[{task_id}] бюджет из SPEC не применён: {detail}")
        return
    if source == config.BUDGET_SOURCE_SPEC and value == old:
        detail = f"${value:.2f} — уже применён, остаётся ${old:.2f}"
        store.journal(conn, task_id, "fsm",
                      "бюджет из SPEC не применён", detail)
        print(f"[{task_id}] бюджет из SPEC не применён: {detail}")
        return

    store.update_task(conn, task_id, budget_usd=value,
                      budget_source=config.BUDGET_SOURCE_SPEC,
                      updated_at=store.now())
    detail = (f"${value:.2f} (прежний потолок ${old:.2f}, "
              f"дефолт ${config.DEFAULT_BUDGET_USD:.2f})")
    store.journal(conn, task_id, "fsm", "бюджет из SPEC", detail)
    print(f"[{task_id}] бюджет из SPEC: {detail}")


def recommended_budget_usd(ac_count: int, zone_files: int) -> float:
    """Ориентир потолка задачи по калибровочной таблице
    (`config.BUDGET_CALIBRATION_TABLE`, ADR-0014 п.7) — по числу
    критериев приёмки SPEC и числу файлов зоны (SPEC
    01M1TQ11K4WJZD7ZE3MR0J4ZK4, требование 1).

    Таблица проверяется по порядку: первый уровень, чьи оба потолка
    (критериев приёмки, файлов зоны) не превышены, и даёт ответ;
    последний уровень таблицы не ограничен ни тем, ни другим — функция
    всегда возвращает значение.
    """
    for amount, max_ac, max_zone_files in config.BUDGET_CALIBRATION_TABLE:
        if max_ac is not None and ac_count > max_ac:
            continue
        if max_zone_files is not None and zone_files > max_zone_files:
            continue
        return max(amount, config.BUDGET_CALIBRATION_FLOOR_USD)
    return config.BUDGET_CALIBRATION_FLOOR_USD


def calibration_warning(actual_usd: float, orientir_usd: float) -> str | None:
    """«рамка ниже калибровки: $N против ~$M» (SPEC
    01M1TQ11K4WJZD7ZE3MR0J4ZK4, AC-6/AC-10) — `actual_usd` ниже
    `orientir_usd` больше чем на треть; иначе `None`.

    Общий узел для `catalog.cmd_new` (требование 2) и гейта SPEC
    (требование 3, `fsm._cmd_approve`) — SPEC требует буквально одну и
    ту же строку в обеих точках.
    """
    if actual_usd < orientir_usd * 2 / 3:
        return (f"рамка ниже калибровки: ${actual_usd:.2f} против "
                f"~${orientir_usd:.2f}")
    return None


def count_zone_paths(text: str | None) -> int:
    """Число непустых путей в строке зон через запятую (SPEC
    01M1TQ11K4WJZD7ZE3MR0J4ZK4, требования 2-3) — общий разбор и для
    frontmatter `zones:` SPEC (гейт SPEC), и для строки «Зоны: ...» ТЗ
    (`new`, где текст предложения может нести завершающую точку сразу
    за последним путём)."""
    if not text:
        return 0
    return len([p for p in
               (piece.strip().rstrip(".") for piece in text.split(","))
               if p])


def spent_with_estimate(t: sqlite3.Row) -> float:
    """`spent_usd + spent_estimate_usd` задачи (SPEC
    01M1NWCM3TDY0YABEKE8DYQA1C, требование 5): бюджетный гейт сравнивает
    с потолком эту сумму, а не только точный расход — иначе верхняя
    оценка неучтённой стоимости (требование 3) не защищала бы потолок
    ни от чего."""
    return (t["spent_usd"] or 0.0) + (t["spent_estimate_usd"] or 0.0)


def budget_block(t: sqlite3.Row) -> str | None:
    """Сообщение, почему `run` не стартует по бюджету, или None.

    Потолок ≤ 0 (или NULL в БД прошлых версий) — потолка нет: иначе задача
    без бюджета эскалировалась бы на первом же шаге при нулевом расходе.
    """
    budget, spent = t["budget_usd"] or 0.0, spent_with_estimate(t)
    if budget <= 0 or spent < budget:
        return None
    return (f"[{t['id']}] бюджет исчерпан: ${spent:.2f} из ${budget:.2f} — "
            f"агент не запускается.\n"
            f"  подними потолок: artel.py budget {t['id']} <usd>\n"
            f"  или закрой задачу: artel.py kill {t['id']}")


def enforce_budget(conn, task_id: str, state: str) -> bool:
    """Реакция на потолок после шага: True — задача ушла в escalated.

    Считает по свежим значениям из БД — стоимость шага туда уже прибавлена.
    """
    t = store.get_task(conn, task_id)
    budget, spent = t["budget_usd"] or 0.0, spent_with_estimate(t)
    if budget <= 0:
        return False

    if spent >= budget:
        # Точка возврата (T006): шаг мог отработать успешно, и возвращать
        # задачу из escalated надо туда, где она стояла, а не в разработку.
        store.update_task(conn, task_id, escalated_from=state)
        if state == "review":
            # Требование 3: sha кода на момент эскалации ИЗ review — до
            # смены состояния, чтобы момент записи однозначно предшествовал
            # самой эскалации. Пусто (git не ответил) — не журналируем
            # вовсе, тот же вырожденный случай, что и у соседних sha-примитивов
            # (`fixation.py`): нечему быть опорой сравнения.
            code_sha = gitcmd.branch_head_sha(t["branch"])
            if code_sha:
                store.journal(conn, task_id, "fsm",
                              REVIEW_ESCALATION_CODE_SHA_ACTION, code_sha)
        store.set_state(conn, task_id, "escalated", "fsm",
                        expected_state=state,
                        detail=f"бюджет исчерпан: ${spent:.2f} из ${budget:.2f}")
        print(f"  дальше: artel.py budget {task_id} <usd>  (или kill)")
        return True

    if spent >= budget * config.BUDGET_ALERT_RATIO:
        detail = (f"израсходовано ${spent:.2f} из ${budget:.2f} — "
                  f"больше {int(config.BUDGET_ALERT_RATIO * 100)}% бюджета")
        store.journal(conn, task_id, "fsm", "бюджет: предупреждение", detail)
        print(f"[{task_id}] ВНИМАНИЕ: {detail}")
    return False


def check_program_spend(conn, task_id: str, cost: dict | None) -> None:
    """Пороги суммарного расхода программы: предупреждение и событие журнала.

    Второй контур учёта поверх потолков задач (roadmap §5, ADR-0003 3ж):
    кошелёк Оператора один на все target'ы, поэтому сумма считается по
    всем задачам всех проектов, а не по текущей. Пороги ничего не
    блокируют — пробой стоп-лосса это повод для внеочередного пересмотра
    программы, а не для остановки шага.

    Событие пишется в момент ПЕРЕСЕЧЕНИЯ порога, а не пока сумма выше
    него: иначе каждый следующий шаг повторял бы ту же строку, и в
    журнале порог перестал бы читаться как событие. Стоимость шага уже
    учтена в `spent_usd` — значение до шага восстанавливается вычитанием.

    Носитель события журнала ЗАДАЧИ остаётся (существующие тесты
    `tests/test_multitarget.py::ProgramSpendTest`,
    `tests/test_multitarget_invariants.py::ProgramSpendAcrossTargetsTest`
    читают его по имени действия и не про алерты — не трогаем по принципу
    целостности); ДОБАВЛЕНА таблица `alerts` (kind=threshold, A3, SPEC T022
    требование 7) как задаче-независимый носитель порога программы: дедуп
    `alerts.raise_alert` закрывает «повторный прогон не дублирует» без
    своей проверки здесь (порог и так пересекается не более одного раза
    на задачу — before<threshold<=after монотонно, — но дедуп защищает от
    случая, когда тот же порог пересекла ДРУГАЯ задача секундой позже
    с тем же текстом сообщения).
    """
    if cost is None or cost["usd"] <= 0:
        return
    after = store.total_spent(conn)
    before = after - cost["usd"]
    for ratio in config.PROGRAM_ALERT_RATIOS:
        threshold = config.PROGRAM_STOP_LOSS_USD * ratio
        if before < threshold <= after:
            detail = (f"суммарно по всем задачам ${after:.2f} из "
                      f"${config.PROGRAM_STOP_LOSS_USD:.2f} — пересечён "
                      f"порог {int(ratio * 100)}% расхода программы")
            store.journal(conn, task_id, "orchestrator",
                          "программа: порог расхода", detail)
            alerts.raise_alert(conn, None, "threshold",
                              "budget.program_spend", detail)
            print(f"[{task_id}] ВНИМАНИЕ: {detail}")


def reseed_program_spend(conn) -> None:
    """Пересевает суммарный программный расход (roadmap §5, `PROGRAM_
    STOP_LOSS_USD`) суммой «Стоимость итого» из всех `docs/retro/T*.md`
    (SPEC T049, требования 4–5, холодный старт — ADR-0005 п.5). Журнал
    шагов, откуда раньше считались события порога, при потере `.artel/`
    теряется вместе с БД — RETRO переживает потерю (в git-истории main,
    ADR-0005 п.1) и остаётся единственным детерминированным источником.

    Сумма кладётся в `spent_usd` синтетической строки `tasks`
    (`config.PROGRAM_SPEND_RESEED_TASK_ID`): `store.total_spent`
    суммирует именно эту колонку по ВСЕМ строкам — тем самым пересев
    учитывается порогами программы (`check_program_spend`) без
    отдельного контура учёта.

    Именно поэтому в сумму идёт RETRO только тех задач, чьей строки
    СЕЙЧАС нет в `tasks` (`store.task_exists`) — только они и есть
    «потерянный вместе с БД» расход, ради которого вообще существует
    этот пересев (SPEC T049, ADR-0005 п.5). RETRO задачи, чья строка
    в БД жива (обычное, не холодное состояние — `.artel` не терялась),
    уже учтена в `total_spent` её собственным `tasks.spent_usd`:
    сложить эту же сумму ещё раз в синтетическую строку — задвоить
    программный расход на «тёплом» пульте (REVIEW T049 итерации 1,
    замечание blocker, воспроизведено на `T001` со своей строкой И
    своим RETRO одновременно).

    Идемпотентно — сумма и число задач каждый раз ПЕРЕСЧИТЫВАЮТСЯ заново
    и ПЕРЕЗАПИСЫВАЮТ прежнее значение строки, не прибавляются к нему:
    повторный `init`/пересев после появления новых RETRO не задваивает
    расход. RETRO ещё нет вовсе (все учтены живыми строками `tasks`, или
    каталог недоступен) — функция не создаёт строку и не журналирует:
    нечего пересевать, а не «пересеяно $0.00 по 0 задачам» в каждом
    прогоне `init` пустого/тёплого проекта.
    """
    retro_dir = config.ROOT / retro.RETRO_DIR_REL
    total = 0.0
    count = 0
    if retro_dir.is_dir():
        for path in sorted(retro_dir.glob("T*.md")):
            if store.task_exists(conn, path.stem):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            cost = retro.parse_total_cost(text)
            if cost is None:
                continue
            total += cost
            count += 1
    if count == 0:
        return

    task_id = config.PROGRAM_SPEND_RESEED_TASK_ID
    if not store.task_exists(conn, task_id):
        store.insert_task(conn, task_id,
                          "Пересеянный программный расход (RETRO, "
                          "холодный старт)", "done", "",
                          config.DEFAULT_TARGET, total)
    store.update_task(conn, task_id, spent_usd=total, budget_usd=total,
                      updated_at=store.now())
    store.journal(conn, task_id, "orchestrator", "программа: пересев расхода",
                  f"расход пересеян из RETRO: ${total:.2f} по {count} задачам")


def cmd_budget(task_id: str, raw_usd: str, session_id: str | None = None) -> None:
    """Меняет потолок задачи — единственный способ снять блокировку по бюджету.

    Берёт lease задачи перед работой (SPEC T044, требование 2) — обёртка
    вокруг `_cmd_budget`, см. `orchestrator/lease.py`. `same_host_ok=True`
    (SPEC 01M1VBEDGMEXHVGWAH42FTDZ4X, требование 1): `budget` — ЕДИНСТВЕННАЯ
    команда, которой разрешено менять потолок под живым lease того же
    hostname чужой сессии (другой терминал того же Оператора) — «Не
    входит» SPEC прямо ограничивает исключение этой командой.

    `mid_step` читается ДО `run_locked` — живая (в момент вызова, до
    какой-либо мутации lease самим `acquire`) lease-строка задачи, чья бы
    сессия её ни держала, означает «прямо сейчас идёт шаг роли» (требование
    1, AC-2/AC-10): auto держит lease весь цикл, поэтому и собственная
    сессия внутри `auto`, и чужая сессия того же хоста — оба случая «во
    время шага».

    Префикс -> полный id (SPEC T094, требование 3, AC-3) резолвится ЗДЕСЬ,
    до lease (REVIEW T094 итерация 1, замечание 1).
    """
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    mid_step = lease.is_live(conn, task_id)
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_budget(conn, task_id, raw_usd, mid_step),
                     same_host_ok=True)


def _cmd_budget(conn, task_id: str, raw_usd: str, mid_step: bool = False) -> None:
    t = store.get_task(conn, task_id)
    new_budget = spend.cli_number(raw_usd)
    if new_budget is None or new_budget <= 0:
        sys.exit(f"budget: '{raw_usd}' — не сумма в долларах "
                 f"(пример: artel.py budget {task_id} 10)")

    old, spent = t["budget_usd"] or 0.0, t["spent_usd"] or 0.0
    # Источник «operator» ставится и здесь, и при поднятии уже поднятого:
    # решение Оператора о деньгах не перебивается значением из SPEC ни
    # после него, ни до (apply_spec_budget).
    store.update_task(conn, task_id, budget_usd=new_budget,
                      budget_source=config.BUDGET_SOURCE_OPERATOR,
                      updated_at=store.now())
    detail = f"${old:.2f} -> ${new_budget:.2f}, израсходовано ${spent:.2f}"
    if mid_step:
        # Отложенный импорт (тот же приём, что `lease.warn_foreign_live`
        # уже применяет к `runner`): `runner.py` на уровне модуля
        # импортирует `budget` — обратный импорт на уровне модуля был бы
        # циклом.
        from . import runner
        role = runner.step_role(t)
        if role is not None:
            detail += f", во время шага {role}"
    store.journal(conn, task_id, "operator", "бюджет изменён", detail)
    print(f"[{task_id}] бюджет: ${old:.2f} -> ${new_budget:.2f} "
          f"(израсходовано ${spent:.2f})")

    if new_budget <= spent:
        print(f"  этого мало: израсходовано ${spent:.2f} — run остаётся "
              f"заблокирован")
        return
    # Задача с spent_usd >= прежнего потолка стояла заблокированной по бюджету
    # (после пересечения потолка `run` не стартует, другой эскалации взяться
    # неоткуда), и поднятие потолка эту блокировку снимает целиком: возвращаем
    # задачу в шаг, на котором её застал потолок, как это делает approve.
    if t["state"] == "escalated" and old > 0 and spent >= old:
        back = t["escalated_from"] or "in_dev"
        store.update_task(conn, task_id, escalated_from=None)
        store.set_state(conn, task_id, back, "operator",
                        expected_state=t["state"], detail="бюджет поднят, продолжаем")
        print(f"  дальше: artel.py run {task_id}")
