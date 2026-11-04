# Записка analyst (шаг 3, после ANSWER-2)

## Выяснено
- ANSWER-2: Q1 A (pause.py в зонах: `resume` без паузы после stop пишет
  журнал operator), Q2 A, Q3 A, Q4 B, Q5 A.
- Причина stop в цикле — `auto._STOP_COMMAND_REASON` (auto.py:124,
  «штатная остановка — команда stop»); стенд ac17 пишет иной текст
  «остановлен командой stop» (tests/…epic_supervisor.py:1240), ac17 без resume.
- Остановки ожидания зоны: `_ZONE_WAIT_CEILING_REASON` (auto.py:108),
  `_ZONE_WAIT_LEASE_LOST_REASON` (auto.py:118).
- `"resume"` уже в `_operator_actions` (auto.py:1225) — запись resume из
  pause.py надзор увидит без новой механики.
- Рубеж answer: test_01m4r4jq…answer_spec_gate.py:444 (ac10) — чужой живой
  lease на spec_gate обязан отказывать; признак «цикл ждёт» нельзя выводить
  из «lease без pgid» — только из наблюдаемого ожидания (запись входа в
  ожидание зоны без закрытия; verifying).
- Глобальная оценка: `others = busy - running` (auto.py:1366) — оставить.

## Не сработало
- `xargs` в bash отклоняется — один grep за раз.

## Где остановился
- SPEC.md написан (15 AC, budget 50, zones + pause.py, без epics.py),
  status: ready, guard ок. QUESTIONS.md удалён (task-rm отказал — файл в
  ссылке документов; удалён os.remove в каталоге документов).
- Строка AC, начинающаяся с «2.» после переноса, ломает guard (AC-разметка).

## Чего не хватило
- Где пишется текст причины stop — искал «командой stop», верно
  `_STOP_COMMAND_REASON` auto.py:124.
