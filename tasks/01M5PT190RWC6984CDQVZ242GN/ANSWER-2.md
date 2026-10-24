---
task: 01M5PT190RWC6984CDQVZ242GN
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

Ответ на эскалацию разработчика (вопрос 1, красный контроль `mutation-run` на `VitestReporterTest::test_ac9_timeout_kills_group_not_green`), сессия при Операторе по правам волны G 24.10.2026.

1. Вариант «г»: с 24.10 у `mutation-run` есть флаги `--workers <n>`, `--wait-lock <минуты>` и `--copy-table` (задача 01M5PWFGJQNV8YSAN5MF0CKHVW смержена, пин 09ded609). Прогоны «до» и «после» — заново: `mutation-run <id> --ref base --tests tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py --workers 4 --copy-table --wait-lock 4 --patches <a>-<b>`, затем «после» `--ref worktree --tests tests/test_report_outcome_module.py` теми же диапазонами и тем же `--workers 4`. Число рабочих процессов и диапазоны — в PLAN. Части — не больше 15 патчей (прогон файла с 4 процессами — около 20 с).
2. Ожидание замка — только `--wait-lock` (сумма с `--wait` в одном вызове — не больше 9 минут); циклы и сценарии ожидания запрещены; не дождались — повтор в следующем шаге.
3. Если контроль красный и с `--workers 4` — повтор с `--workers 2`; красный и тогда — эскалация с логом контроля, тест не правится.
4. Прогоны №1–№3 (красный контроль) в доказательство не входят; в PLAN — одной строкой с причиной.
