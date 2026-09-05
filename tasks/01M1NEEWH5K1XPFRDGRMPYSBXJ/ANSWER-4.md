---
task: 01M1NEEWH5K1XPFRDGRMPYSBXJ
type: answer
author_role: operator
status: ready
schema_version: 3
---

# ANSWER-4: песочница исправлена Оператором, шаг только на PLAN

Правку песочницы по ANSWER-3 Оператор внёс сам: `_sandbox.py` подменяет
статус CI заглушкой «зелёный», потолки ожидания verifying/merge_gate —
5 секунд, `gh` в песочнице запрещён, stdin подпроцессов закрыт. Лок
планки перефиксирован. Проверено: `test_ac1_*` и `test_ac3_*`
завершаются за 5 секунд (раньше висели часами).

Задача developer на этот шаг: прогнать планку по одному файлу в
переднем плане с таймаутом (`python3 -m unittest discover -s
tasks/<id>/acceptance_tests -p "test_acN_*.py"`), починить красные по
существу (test_ac1: пул завёл 0 задач вместо k=2), записать итоги по
файлам в PLAN и поставить `status: ready`. Полный набор `tests/` не
запускать — его гоняет CI. Потолок поднят до 100; это последний шаг
developer перед решением о делении.
