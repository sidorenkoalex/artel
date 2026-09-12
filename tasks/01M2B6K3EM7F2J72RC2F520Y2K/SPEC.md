---
task: 01M2B6K3EM7F2J72RC2F520Y2K
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/runner.py, orchestrator/artel.py, orchestrator/config.py, conftest.py, docs/reference/role-home/, tests/
budget_usd: 30
---

# SPEC: Признак роли в окружении и conftest вместо хука роли

## Контекст

Хук `docs/reference/role-home/claude/hooks/bash_guard.py` (PreToolUse
Claude Code, подключён в `docs/reference/role-home/claude/settings.json`)
не даёт роли внутри шага запустить полный набор тестов — временная мера
до появления потестового таймаута. `pytest-timeout` уже стоит
(`timeout = 120` в pyproject.toml), но хук остался после возврата
задачей 01M1SG9WPVN8P3S4X7975N9T69. Механизм хука — протокол PreToolUse
конкретного клиента, под другим не работает; та же клиент-специфичность
у части `permissions.deny` (`artel.py init`, `artel.py doctor --restore`).
Решение Оператора 12.09: перевести эти запреты на LLM-независимый
механизм — признак процесса роли в окружении, который читает сам CLI
(корневой `conftest.py` для pytest, диспетчер `artel.py` для трёх команд),
а не клиентский хук.

## Требования

1. `runner.role_env` добавляет в окружение процесса роли `ARTEL_ROLE=<имя
   роли>` и `ARTEL_TASK=<id задачи>`; имена обеих переменных — константы
   `orchestrator/config.py`. Остальной состав окружения не меняется.
   Существующие вызовы `role_env()` без указания задачи (`orchestrator/
   doctor/*`, часть тестов) продолжают работать без правки — зона задачи
   не включает `orchestrator/doctor/`.
2. Корневой `conftest.py`: при наличии `ARTEL_ROLE` в окружении сбор
   pytest отказывает (`pytest.exit` с текстом причины, ненулевой код
   выхода), если среди аргументов запуска нет ни одного пути к
   конкретному файлу или каталогу ниже `tests/` или
   `tasks/<id>/acceptance_tests/` — то есть голый `pytest`, `pytest
   tests`, `pytest .` — теми же критериями, что `bash_guard._pytest_
   verdict`. Без `ARTEL_ROLE` в окружении (Оператор, CI, автогейт пульта)
   `conftest.py` в сбор не вмешивается. Текст отказа — прежний REASON
   хука, с заменой формулировки «python3 -m unittest» на pytest-
   формулировки.
3. Диспетчер `artel.py`: при наличии `ARTEL_ROLE` в окружении команды
   `init`, `doctor --restore`, `canary pool-seal` отказывают до
   выполнения текстом «команда недоступна процессу роли <роль>» —
   частичная замена `permissions.deny`. Без `ARTEL_ROLE` три команды
   выполняются как прежде.
4. Курируемый слой: из `docs/reference/role-home/claude/settings.json`
   убирается `hooks.PreToolUse`, файл `hooks/bash_guard.py` удаляется;
   `permissions.deny` остаётся без изменений. Уже развёрнутый
   `.artel/home/.claude` пульт не переписывает (текущее поведение
   `_deploy_role_home_reference` — разворачивает только при отсутствии
   каталога); расхождение с референсом покажет проверка `doctor
   role-home-reference`, переразворачивает Оператор — это называется в
   PLAN.md разделом «Влияние на систему».
5. Тесты покрывают требования 1–4 (см. «Критерии приёмки»); тесты хука
   `bash_guard`, проверяющие наличие файла/подключения хука,
   адаптируются к его снятию без ослабления проверяемой гарантии
   изоляции роли; существующие тесты runner/catalog/doctor остаются
   зелёными без ослабления.

## Критерии приёмки

AC-1. `orchestrator/config.py` несёт именованные константы для имён
переменных `ARTEL_ROLE`/`ARTEL_TASK`; `runner.role_env` кладёт в
окружение процесса роли `ARTEL_ROLE=<имя роли>` и `ARTEL_TASK=<id
задачи>` через эти константы; остальной состав окружения не меняется.
Тест(ы) `tests/test_runner_*.py` подтверждают наличие обеих переменных
в результате `role_env`.

AC-2. Корневой `conftest.py`, при наличии `ARTEL_ROLE` в окружении,
отказывает сбору pytest (`pytest.exit`, ненулевой код выхода, текст
причины) для нецелевого запуска — голого `pytest`, `pytest tests`,
`pytest .` и эквивалентных форм без пути к конкретному файлу/каталогу
ниже `tests/` или `tasks/<id>/acceptance_tests/` — по тем же критериям,
что `bash_guard._pytest_verdict`; при указании такого пути сбор идёт.
Текст причины воспроизводит прежний REASON хука `bash_guard.py` с
заменой формулировки «python3 -m unittest» на pytest-формулировки.

AC-3. Без `ARTEL_ROLE` в окружении (Оператор, CI, автогейт пульта)
`conftest.py` в сбор pytest не вмешивается — ни для целевого, ни для
нецелевого запуска.

AC-4. `tests/test_conftest_role_guard.py` — новый файл: subprocess-
прогон `pytest` с `ARTEL_ROLE=developer` в окружении без путей и с
`tests` даёт ненулевой код выхода и текст причины в выводе; с путём к
конкретному файлу — сбор идёт; без переменной `ARTEL_ROLE` в окружении
— прежнее поведение (мутация «`conftest.py` не смотрит `ARTEL_ROLE`»
красит этот тест).

AC-5. Диспетчер `orchestrator/artel.py`, при наличии `ARTEL_ROLE` в
окружении, отказывает командам `init`, `doctor --restore`, `canary
pool-seal` до их выполнения текстом «команда недоступна процессу роли
<роль>»; без `ARTEL_ROLE` эти три команды выполняются как прежде (без
отказа). Тесты диспетчера покрывают оба случая для всех трёх команд.

AC-6. `docs/reference/role-home/claude/settings.json` не несёт больше
ключа `hooks.PreToolUse`; файл `docs/reference/role-home/claude/hooks/
bash_guard.py` удалён; список `permissions.deny` в `settings.json`
сохранён без изменений и без потерь ни одной записи.

AC-7. Тесты хука `bash_guard` (`tests/test_role_bash_guard.py`, планка
задачи T058), проверяющие наличие файла хука или его подключения в
`settings.json`, адаптированы к его снятию без ослабления проверяемой
гарантии изоляции роли — гарантия проверяется через `conftest.py`
(AC-2–AC-4) и диспетчер (AC-5).

AC-8. PLAN.md этой задачи в разделе «Влияние на систему» называет факт:
уже развёрнутый `.artel/home/.claude` не переписывается пультом при
этом изменении (разворачивается только при отсутствии каталога);
расхождение с референсом покажет проверка `doctor role-home-reference`,
переразворачивает Оператор.

AC-9. Существующие тесты runner/catalog/doctor проходят без ослабления:
ни один тест не удалён без замены на равноценную проверку, ни один
ассерт не смягчён.

## Не входит

- Песочница шага роли (sandbox/Dockerfile) — предмет отдельного ADR.
- Правка `orchestrator/doctor/`.
- Снятие `permissions.deny`.
- Правка `pyproject.toml`.

## Материалы

- `docs/reference/role-home.md` — описание курируемого слоя; если
  требует правки текста после снятия хука — приложением к PLAN.md
  unified diff.
- `orchestrator/doctor/preflight.py` (проверка `role-home-reference`,
  ~строки 130–150) — сверка развёрнутого дома с референсом; в зону
  задачи не входит.
- `tasks/T058`, `tasks/01M1SG9WPVN8P3S4X7975N9T69` — история хука
  (заведение, снятие коммитом dea8016b, восстановление).
