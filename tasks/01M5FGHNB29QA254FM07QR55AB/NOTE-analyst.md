## Выяснено
- Круг 2 (возврат с spec_gate, 4 решения Оператора) внесён в SPEC.md, status: ready, guard: ок.
- П.1: причина записи выхода = `Stop.reason` выхода (`_STOP_COMMAND_REASON` auto.py:116, `_ZONE_WAIT_CEILING_REASON` :100, `f"{_ZONE_WAIT_LEASE_LOST_REASON}: {lease_refusal}"` :110/:202); минуты `int(elapsed_sec // 60)` (:216). AC-1 требует точное число минут при ненулевом потолке (кратном ZONE_WAIT_POLL_SEC) и 0 при потолке 0.
- П.2: имена в требованиях 1–3 и AC-1/AC-5: `wait_interrupted_action(reason, minutes, holder)`, `AUTO_START_ACTION`, `AUTO_STOPPED_ACTION`, `CYCLE_ABORTED_ACTION`; AC-5 дополнен поведенческой подменой константы.
- П.3: AC-8 и требование 4 — прежнего хвоста «снять заявленную может только Оператор: мандат … (artel.py answer <id> <файл>)» нет; первое `answer` после `reject`, есть `escalated`.
- П.4: в «Оценке объёма» записано «Монолит принят Оператором 21.10.2026» со ссылкой на причину возврата.
- Stop во время сна: `elapsed_sec` к этому моменту не увеличен за прерванный сон (auto.py:195-197) — минуты по счётчику как есть.

## Не сработало
- Ничего в этом круге.

## Где остановился
- Готово.

## Чего не хватило
- Ничего.
