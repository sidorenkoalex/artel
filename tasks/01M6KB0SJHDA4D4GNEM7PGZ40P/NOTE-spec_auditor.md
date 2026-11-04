# Записка spec_auditor — 01M6KB0SJHDA4D4GNEM7PGZ40P (аудит 2, spec_sha ffd6d54c)

## Выяснено
- Девять пунктов прошлого аудита закрыты решением Оператора №1 и SPEC. Факты о коде верны; три диффа ТЗ с правкой «шестью полями» и переводом строки в конце проходят `git apply --check` на 8fa671cc0.
- SPEC не называет AST-линтеры `cmd_reject`: tests/test_lease_run_task_command.py:133–157 и tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py:225–257. Они требуют ровно один `lease.run_task_command` и запрещают `store.db` в теле команды; два вызова обвязки по ветке decision_file ломают оба.
- Требование 5 различает «k.n» и «k» по заголовку «# Решение Оператора на гейте SPEC», а требование 2 этот заголовок не обязывает — обход сверки.
- Не заданы: что считать номером в «Прежних решениях», уникальность n, набор вложенных заглушек (`<n>`, `<строка мандата>`).
- `mandate.elements` (решение) против `line_elements`/`id_elements` у answer (answer.py:264–267) — расходится с ТЗ п. 3.
- `brief._spec_gate_reasons` узнаёт возврат по actor/предыдущему состоянию (brief.py:1347–1355).

## Не сработало
- `cd X; sed …` и `ls` в оболочке отклоняются или не находятся; работают Read, grep и `cd X && python3 …`.

## Где остановился
- SPEC-AUDIT.md: concerns, 6 пунктов, status ready; guard ок.

## Чего не хватило
- Второй AST-тест сигнатуры `cmd_reject` (test_01m5mhvrs39…_run_task_command.py) нашёлся только grep `cmd_reject` по tests/.
