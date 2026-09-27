---
task: 01M3H3T8RKTVKTJJYEAGW19BPS
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Команда ci-rerun в отдельном модуле пульта (CR-4б ревизии 26.09)

# ТЗ: Команда ci-rerun в отдельном модуле пульта (находка CR-2026-09-26-4, часть б)

Источник: docs/audits/code-revision-2026-09-26.md, находка
CR-2026-09-26-4 (рост после фазы R) и черновик Ц-4б; решение Оператора
27.09. Рефакторинг без изменения поведения. Задача вне линии провайдеров.

Факты (origin/main a6da0abe):
- Команда `ci-rerun <id> --reason "<основание>"` (SPEC
  01M3F7C2DVYCEANQ8CF1FCSD87) реализована в orchestrator/fsm.py,
  строки 1123–1328 из 1328: `cmd_ci_rerun`, `_ci_rerun_refuse`,
  `_last_red_status_sha`, `_last_ci_rerun_reason`, `_ci_rerun_outcome`,
  `_cmd_ci_rerun` (122 строки, 13 вызовов `_ci_rerun_refuse` с текстами
  отказов).
- Диспетчер команд: orchestrator/artel.py:937 зовёт `fsm.cmd_ci_rerun`;
  справка команды — там же, не меняется.
- Тесты: tests/test_ci_rerun_command.py, пять обращений к именам
  `fsm.cmd_ci_rerun`/`fsm._cmd_ci_rerun`/`fsm._ci_rerun_*` (вызовы и
  пути подмен).
- Образец выноса команды в свой модуль: orchestrator/amend.py,
  orchestrator/answer.py. В orchestrator/ci.py переносить нельзя: он не
  знает `store` (замечание ревизии).

Требуется:
1. Новый модуль orchestrator/ci_rerun.py: шесть перечисленных функций
   переносятся ДОСЛОВНО — тексты отказов, коды выхода, порядок и тексты
   записей журнала, обращения к `gh` не меняются ни символом.
2. orchestrator/artel.py зовёт `ci_rerun.cmd_ci_rerun`; справка и разбор
   аргументов не меняются.
3. В orchestrator/fsm.py остаётся алиас старого публичного имени
   `cmd_ci_rerun` на одну волну (с пометкой срока снятия); закрытые
   имена `_ci_rerun_*` и `_cmd_ci_rerun` из fsm.py уходят.
4. Тесты: в tests/test_ci_rerun_command.py меняются только импорты и
   пути подмен; ни одна проверка не меняется и не удаляется. Новый тест:
   алиас `fsm.cmd_ci_rerun` указывает на ту же функцию.
5. PLAN несёт таблицу переносов (имя, откуда, куда, число строк) и смок
   до/после: `artel.py ci-rerun` без аргументов и с несуществующим id —
   вывод и код выхода побайтно прежние.
6. Карта кодовой базы docs/codebase-map.md перегенерирована в ветке.

Зоны: orchestrator/ci_rerun.py, orchestrator/fsm.py,
orchestrator/artel.py, tests/.

Только чтение (не менять): orchestrator/ci.py, orchestrator/store.py,
orchestrator/amend.py и orchestrator/answer.py (образцы),
docs/operator-session.md, docs/audits/code-revision-2026-09-26.md,
docs/backlog.md, tests/test_invariants.py.

Не входит: изменение поведения, текстов или справки команды; разбор
`_cmd_ci_rerun` на меньшие функции; часть а находки (таблица предикатов
в orchestrator/runner.py); попутные улучшения fsm.py.

Рамка: $25.
