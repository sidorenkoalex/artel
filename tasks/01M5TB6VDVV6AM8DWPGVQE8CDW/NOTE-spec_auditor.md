# Записка spec_auditor

## Выяснено
- sha SPEC = 6a8f930d… совпал (git hash-object).
- Литералы ("done","killed") в orchestrator/: ровно 13 мест/11 файлов (AST-обход), перечень SPEC полный.
- fsm.py:1194-1336 _approve_spec_gate: до ветки деления (1333) уже пишутся zones/merge_after/budget (1310-1323), журнал declared/replaced (1292-1300), ACCEPTED_FAIL (1304). Guard на approve не перезапускается (коммент 1326-1332).
- merge_after.check (126-182) работает только по строкам БД — части до заведения через него не проверить; replace_divided (299) идёт после и может создать цикл.
- tests/test_01m45d29…_spec_gate_declared.py:463-512 требует: spawn_subtask с «Порядок: после <id>» НЕ пишет merge_after.
- Импорт: store→models, guard→zone_lock, fsm→cleanup — обратный импорт fsm даёт цикл.

## Не сработало
- grep -E со скобками требует подтверждения — использовал python ast.

## Где остановился
- Вердикт concerns, SPEC-AUDIT.md записан (status ready), guard: ок. Отклонения: Е-1 цикл через replace_divided, Е-2 место отказа, В-2 рамка на approve (инвариант 10), В-1 нет AC на «после <id>», А-1 суффикс status, Б-2 test_ac13.

## Чего не хватило
- Где approve гейта SPEC читает SPEC для деления и где перезапускается guard — искал по fsm.py:1194-1336.
