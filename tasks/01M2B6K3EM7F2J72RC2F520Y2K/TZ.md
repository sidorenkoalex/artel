---
task: 01M2B6K3EM7F2J72RC2F520Y2K
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Признак роли в окружении и conftest вместо хука роли

Источник: решение Оператора 12.09 по анализу хуков: запреты клиента
конкретной модели переводятся в LLM-независимые механизмы (планируется
отвязка от конкретной LLM). Копилка/ADR: docs/reference/role-home.md,
хук `docs/reference/role-home/claude/hooks/bash_guard.py`.

Факты:
- Курируемый слой роли `docs/reference/role-home/claude/` (settings.json
  с `permissions.deny` и `hooks.PreToolUse` -> `hooks/bash_guard.py`)
  разворачивается в `.artel/home/.claude/` (`catalog.
  _deploy_role_home_reference`, orchestrator/catalog.py:59–80, только если
  дома ещё нет); `doctor` (orchestrator/doctor/preflight.py:130–142,
  проверка `role-home-reference`) предупреждает о расхождении дома с
  референсом.
- `bash_guard.py` отклоняет полный прогон тестов внутри шага роли
  (`python3 -m unittest` голый/discover по всему дереву, `pytest` без
  путей или с `tests`/`.`); по собственному докстрингу — временная мера
  до потестового таймаута; `pytest-timeout` уже стоит (pyproject.toml
  `timeout = 120`, планка и CI на pytest), но хук остался (возвращён
  01M1SG9WPV после снятия dea8016b). Механизм хука — протокол PreToolUse
  Claude Code, под другим клиентом не работает.
- `permissions.deny` роли: git clone, gh repo clone, git remote add,
  `artel.py init`, `artel.py doctor --restore`, openssl enc -d, security
  find-generic-password, Read ~/.artel-canary/**. Тоже механизм клиента.
- Окружение роли собирает `runner.role_env` (orchestrator/runner.py:
  ~544–590): allowlist переменных, `HOME=config.ROLE_HOME`,
  `CLAUDE_CONFIG_DIR=config.ROLE_CONFIG_DIR`; признака «это процесс роли»
  в окружении нет.
- Диспетчер команд — orchestrator/artel.py (~745–772: `"init"`,
  `"doctor"` с `--restore`, `"canary"` -> `_cmd_canary`, `pool-seal` ~686).
- pytest читает `conftest.py` корня репозитория при любом запуске из
  корня (rootdir по pyproject.toml).

Требуется:
1. `runner.role_env` добавляет в окружение роли переменную
   `ARTEL_ROLE=<имя роли>` и `ARTEL_TASK=<id>` (имена — константы в
   config.py). Ничего больше в окружении не меняется.
2. Корневой `conftest.py`: под `ARTEL_ROLE` в окружении сбор pytest
   отказывает (`pytest.exit` с текстом причины, код выхода ненулевой),
   если среди аргументов запуска нет ни одного пути к конкретному файлу
   или каталогу ниже `tests/`/`tasks/<id>/acceptance_tests/` — то есть
   голый `pytest`, `pytest tests`, `pytest .` — теми же критериями, что
   `bash_guard._pytest_verdict`. Без `ARTEL_ROLE` (Оператор, CI, автогейт
   пульта) conftest не вмешивается. Текст отказа — прежний REASON хука,
   с заменой «python3 -m unittest» на pytest-формулировки.
3. Диспетчер `artel.py`: под `ARTEL_ROLE` команды `init`, `doctor --restore`,
   `canary pool-seal` отказывают до выполнения текстом «команда
   недоступна процессу роли <роль>» (частичная замена `permissions.deny`).
4. Курируемый слой: из `docs/reference/role-home/claude/settings.json`
   убирается `hooks.PreToolUse` и файл `hooks/bash_guard.py`; `permissions.
   deny` остаётся как есть (страховка для клиента, где она работает).
   Развёрнутый дом `.artel/home/.claude` пульт не переписывает (как
   сегодня) — расхождение покажет `doctor role-home-reference`, Оператор
   переразвернёт; это назвать в PLAN «Влияние на систему».
5. Тесты: (а) tests/test_conftest_role_guard.py — subprocess `pytest`
   с `ARTEL_ROLE=developer` без путей / с `tests` — ненулевой код и
   текст причины; с путём к файлу — сбор идёт; без переменной —
   прежнее поведение (мутация «conftest не смотрит ARTEL_ROLE» — красный);
   (б) tests/test_runner_*.py — `role_env` несёт ARTEL_ROLE/ARTEL_TASK;
   (в) диспетчер под ARTEL_ROLE отказывает трём командам, без — нет;
   (г) тесты хука `bash_guard` (tests/test_role_hook* / T058 планка)
   — если они проверяют наличие файла хука, адаптировать к его снятию
   без ослабления смысла (изоляция роли проверяется conftest-путём);
   (д) существующие тесты runner/catalog/doctor — без ослабления.

Зоны: orchestrator/runner.py, orchestrator/artel.py, orchestrator/config.py,
conftest.py, docs/reference/role-home/, tests/.

Приложением: docs/reference/role-home.md (описание курируемого слоя —
если требует правки текста, unified diff приложением), orchestrator/
doctor/preflight.py (проверка role-home-reference, в зону не входит),
tasks/T058 и 01M1SG9WPV (история хука).

Не входит: песочница шага роли (sandbox/Dockerfile — отдельный ADR);
правка doctor/; снятие `permissions.deny`; правка pyproject.toml.

Рамка: $30.
