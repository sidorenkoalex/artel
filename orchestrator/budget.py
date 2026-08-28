"""Потолок задачи: значение из SPEC, блокировка `run`, реакция после шага."""
import sqlite3
import sys

from . import alerts, config, lease, retro, spend, store


def spec_budget(meta: dict) -> tuple[float | None, str]:
    """Потолок из frontmatter SPEC: (сумма, причина отказа).

    Исходов три, а не два. Поля нет — (None, ""), и это не событие: задача
    работает по дефолту, как работала (требование 2). Поле есть, но взять
    его нельзя — (None, причина): аналитик что-то имел в виду, и молчать об
    этом нельзя. Иначе (сумма, "").

    Число разбирается тем же `cli_number`, что и аргумент команды `budget`:
    одно правило на оба входа в потолок, включая отсев nan/inf.

    Причин отказа две, и они разные по смыслу: «не сумма» — значение
    непонятно, «выше дефолта» — значение понятно, но применить его значило
    бы поднять потолок задачи без Оператора (инвариант 10). Сравнение —
    строгое и именно с DEFAULT_BUDGET_USD, а не с текущим потолком задачи:
    у задач из старых БД потолок $5–$10 от прежних дефолтов, и сравнение с
    ним отвергло бы у них разрешённые SPEC суммы.
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
    if value > config.DEFAULT_BUDGET_USD:
        return None, (f"${value:.2f} выше дефолта "
                      f"${config.DEFAULT_BUDGET_USD:.2f} — "
                      f"поднятие потолка только командой budget")
    return value, ""


def apply_spec_budget(conn, t: sqlite3.Row, meta: dict) -> None:
    """Ставит задаче потолок из SPEC — один раз и никогда поверх ручного.

    Вызывается на переходе spec_writing -> spec_gate: SPEC к этому моменту
    прочитан и признан готовым, а денег задача ещё не потратила (агент
    запускается только из in_dev и review).

    Кто задал потолок, помнит `budget_source`: с ним значение из SPEC не
    применяется ни повторно, ни поверх поднятия Оператора — в какую бы
    сторону ни шёл порядок (требование 4).

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
    if source is not None:
        why = ("уже применён" if source == config.BUDGET_SOURCE_SPEC
               else "потолок задан Оператором")
        detail = f"${value:.2f} — {why}, остаётся ${old:.2f}"
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


def budget_block(t: sqlite3.Row) -> str | None:
    """Сообщение, почему `run` не стартует по бюджету, или None.

    Потолок ≤ 0 (или NULL в БД прошлых версий) — потолка нет: иначе задача
    без бюджета эскалировалась бы на первом же шаге при нулевом расходе.
    """
    budget, spent = t["budget_usd"] or 0.0, t["spent_usd"] or 0.0
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
    budget, spent = t["budget_usd"] or 0.0, t["spent_usd"] or 0.0
    if budget <= 0:
        return False

    if spent >= budget:
        # Точка возврата (T006): шаг мог отработать успешно, и возвращать
        # задачу из escalated надо туда, где она стояла, а не в разработку.
        store.update_task(conn, task_id, escalated_from=state)
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
    вокруг `_cmd_budget`, см. `orchestrator/lease.py`.
    """
    conn = store.db()
    sid = lease.resolve_session_id(session_id)
    refusal, fresh = lease.acquire(conn, task_id, sid)
    if refusal is not None:
        sys.exit(refusal)
    try:
        _cmd_budget(conn, task_id, raw_usd)
    finally:
        if fresh:
            lease.release(conn, task_id, sid)


def _cmd_budget(conn, task_id: str, raw_usd: str) -> None:
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
    store.journal(conn, task_id, "operator", "бюджет изменён",
                  f"${old:.2f} -> ${new_budget:.2f}, израсходовано ${spent:.2f}")
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
