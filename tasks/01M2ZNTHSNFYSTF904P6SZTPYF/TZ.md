---
task: 01M2ZNTHSNFYSTF904P6SZTPYF
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Интерфейс исполнителя роли, часть 1: команда, окружение, дом, предполётные проверки

Источник: план провайдеров ролей, принятый Оператором 20.09
(docs/research/providers-codex-plan.md, задача 1). Первый шаг к запуску
ролей на Codex CLI: выделить всё, что в пульте знает про Claude Code
как исполнителя роли, в интерфейс провайдера — без изменения поведения.
Парная задача 0 (01M2ZNJX2N, курс и сверка) идёт параллельно, зоны не
пересекаются.

Факты:
- Argv шага собирает `orchestrator/runner.py::role_cmd()` (без
  параметров, AC-4 задачи 01M2XJKV84): абсолютный путь `claude` из
  `_resolve_declared_tools`, `-p`, `--permission-mode acceptEdits`,
  `--output-format stream-json --verbose`, `--allowedTools
  Bash(git:*),Bash(python3:*)`, `--setting-sources
  config.AGENT_SETTING_SOURCES`, `--strict-mcp-config`; `--model`
  добавляет `run_agent_once` по `_resolved_role_model`. Промпт — на
  stdin. Ту же `role_cmd()` читает офлайн-смок изоляции
  `orchestrator/doctor/isolation.py::isolation_smoke` (структурная
  сверка флагов), живой смок `doctor/live_smoke.py` зовёт `role_env`.
- Окружение роли — `runner.role_env(role, task_id)`: белый список
  `stack.ROLE_ENV_ALLOWLIST`/`_PREFIXES`, PATH из каталогов объявленных
  инструментов (`_role_path_dirs`), `HOME=config.ROLE_HOME`
  (`.artel/home`), `CLAUDE_CONFIG_DIR=config.ROLE_CONFIG_DIR`,
  `CLAUDE_CODE_OAUTH_TOKEN` из `role_token` (слоты keychain по
  roles.yaml), интерпретатор venv. `in_role_environment()` — рубеж для
  команд пульта.
- Курируемый дом роли: референс `docs/reference/role-home/claude/`
  (CLAUDE.md, settings.json, hooks/bash_guard.py) разворачивает
  `orchestrator/catalog.py::_deploy_role_home_reference` при `init`;
  `doctor/preflight.py::check_role_home_reference` сверяет развёрнутый
  слой с референсом.
- Манифест стека `orchestrator/stack.py`: `REQUIRED_TOOLS` с `claude`,
  `MODEL_MIN_CLI_VERSION`, `installed_cli_version`, `model_cli_verdict`,
  `_model_checks`; предполётные проверки `doctor/preflight.py`
  (`check_cli_found`, `check_cli_version`, `check_token`,
  `check_role_home_reference`) и `runner._refuse_before_start`
  (отказ до старта агента по модели/CLI/токену).
- roles.yaml несёт у роли `executor: agent | system | none` и `model`;
  провайдера не называет. Разбор — `orchestrator/roles.py`
  (`load`, `token_slots`, `skills`, `model`).
- Разбор вывода (`agent_log.OutputPump`, `spend`), классификация
  провалов (`failure_classification`) и тарифы — часть 2 интерфейса
  (задача 3 плана), здесь не трогаются.

Требуется:
1. Пакет `orchestrator/providers/`: базовый интерфейс провайдера
   исполнителя роли (`providers/base.py`) с методами: `command(model)`
   — argv шага; `environment(role, task_id)` — переменные окружения,
   специфичные для провайдера (HOME/конфиг/секрет), поверх общего
   белого списка runner; `home_reference()` — путь к референсу дома
   роли и имя развёрнутого каталога; `preflight(role)` — список
   проверок до старта (CLI найден, версия, секрет, дом роли) в форме
   `doctor.Check`/`StackCheck`, как сегодня; `cli_tool()` — имя
   инструмента манифеста и минимальная версия; `model_verdict(model)`
   — вердикт совместимости модели с установленным CLI. Провайдер
   `providers/claude.py` реализует всё это ровно сегодняшними значениями
   и вызовами (те же функции runner/stack/preflight переезжают или
   вызываются из него).
2. Выбор провайдера: `roles.py` получает `provider(role)` — по полю
   `provider:` роли в roles.yaml, по умолчанию `claude` при отсутствии
   поля (roles.yaml в этой задаче не меняется; сам файл — защищённый
   путь). Реестр провайдеров — словарь в `providers/__init__.py`;
   неизвестное имя — именованный отказ `run`/`auto` до старта агента
   («провайдер <имя> роли <роль> не зарегистрирован») и красная строка
   `doctor`.
3. Runner зовёт провайдера, а не литералы: `role_cmd()` и `role_env()`
   сохраняют сигнатуры и результат байт-в-байт (тест сравнивает argv и
   env до и после через зафиксированный ожидаемый список), но внутри
   берут провайдерские части из `providers.get(roles.provider(role))`.
   `_refuse_before_start` и `_resolved_role_model` — вердикт модели
   через провайдера. `role_cmd()` остаётся без параметров: провайдер
   роли берётся из активного шага (текущая роль известна вызывающему
   коду — передать через существующий контекст, не через глобальную
   переменную окружения).
4. Стек и doctor: `stack.REQUIRED_TOOLS` — инструмент провайдера
   объявляется провайдером (для `claude` — как сегодня, обязательный);
   `check_cli_found`/`check_cli_version`/`check_token`/
   `check_role_home_reference` идут через `preflight()` провайдера
   каждой agent-роли (сегодня — один провайдер, результат тот же набор
   проверок без дублей); `isolation_smoke` и `live_smoke` берут argv и
   окружение через провайдера. Вывод `doctor` дополняется строкой
   «провайдеры ролей: <роль → провайдер>».
5. Дом роли: `catalog._deploy_role_home_reference` разворачивает
   референс по `home_reference()` провайдера (для `claude` — тот же
   каталог и то же имя); `check_role_home_reference` — через провайдера.
6. Документация: `docs/stack.md` — раздел «Провайдер исполнителя роли»
   (что входит в интерфейс, что остаётся общим у runner); карта кодовой
   базы обновляется генератором как обычно.
7. Тесты (tests/): argv `role_cmd()` для роли на `claude` совпадает с
   зафиксированным списком до задачи; `role_env()` — тот же набор
   ключей и значений (кроме заведомо динамических PATH/интерпретатора,
   которые сравниваются по составу); роль без поля `provider` — `claude`;
   неизвестный провайдер — именованный отказ до старта и строка
   `doctor`; `isolation_smoke` и `live_smoke` (в офлайн-части) зелёные;
   `catalog` разворачивает тот же дом. Существующие
   `tests/test_runner_role_model.py`, `tests/test_runner_model_preflight.py`,
   `tests/test_stack.py`, `tests/test_doctor.py`,
   `tests/test_doctor_canary_pool.py` остаются зелёными.

Зоны: orchestrator/providers/, orchestrator/runner.py,
orchestrator/stack.py, orchestrator/roles.py, orchestrator/doctor/,
orchestrator/catalog.py, docs/stack.md, tests/.

Только чтение (не менять): orchestrator/agent_log.py,
orchestrator/spend.py, orchestrator/failure_classification.py (часть 2
интерфейса — задача 3 плана), orchestrator/config.py (`ROLE_HOME`,
`ROLE_CONFIG_DIR`, `AGENT_SETTING_SOURCES` как есть),
orchestrator/keychain.py (слоты как есть), orchestrator/canary.py,
orchestrator/acceptance.py, orchestrator/answer.py, orchestrator/notes.py
(зовут `role_env`/`in_role_environment` — сигнатуры не меняются),
roles.yaml (поле `provider` появится приложением позже, при первом
провайдере кроме `claude`), docs/reference/role-home/ (референс не
меняется), docs/research/providers-codex-plan.md (источник).

Не входит: провайдер `codex` (задача 4 плана); разбор вывода,
стоимость и классы провалов у провайдера (задача 3); ярусы и каталог
моделей (задача 2); изменение флагов, окружения или дома роли для
`claude` — любое отличие argv/env от сегодняшних является дефектом.

Рамка: $45.
