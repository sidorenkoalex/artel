---
task: 01M2XJKV84SQ9VEVR0VNVKDNGJ
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Роль запускается по абсолютному пути из манифеста, модель роли сверяется с версией CLI до старта агента

## Подход

Три модуля зоны, одна механика на каждый; `orchestrator/doctor/`,
`orchestrator/version.py`, `orchestrator/auto.py`, `orchestrator/config.py`
не трогаются (SPEC «Не входит», AC-4/AC-10). Приёмочная планка
`tasks/01M2XJKV84SQ9VEVR0VNVKDNGJ/acceptance_tests/` залочена — код
подгоняется под неё, тексты отказов берутся дословно из SPEC.

**Требование 1 — argv[0].** `runner.role_cmd()` (`orchestrator/runner.py:778`)
начинает список с `_resolve_declared_tools()["claude"]` вместо литерала
`"claude"` — тот же резолв, из которого `role_env` собирает PATH роли
(`_role_path_dirs`), поэтому затенение тёзкой из каталога другого
инструмента (инцидент 06.09) невозможно по построению. Сигнатура
`role_cmd()` остаётся нулевой (AC-4, 101 патч по имени модуля), состав и
порядок флагов после argv[0] не меняется (AC-2), `--model` по-прежнему
довеском в `_spawn_and_wait`. `_resolve_declared_tools` бросает `OSError`
при отсутствии любого инструмента манифеста — обе точки вызова
`role_cmd()` стоят ПОСЛЕ успешного `role_env()` (`_prepare_step` →
`_spawn_and_wait`; `doctor.isolation_smoke:70` → `:112`), то есть резолв
там уже прошёл; необработанного исключения новых не появляется.

Тестовый слой сверяет «это запуск CLI роли, а не git» по базовому имени
(`Path(argv[0]).name == "claude"`), как решено в «Материалах» SPEC:
`tests/sandbox.py::claude_only_run`/`claude_only_popen`,
`tests/test_doctor.py:326,361`, `tests/test_git_fixation.py:492,943`.
Без этого `claude_only_popen` пропустил бы абсолютный путь в НАСТОЯЩИЙ
`subprocess.Popen` — тесты запускали бы живой CLI.

**Требование 2 — таблица.** `stack.MODEL_MIN_CLI_VERSION = {"claude-fable-5-1":
(2, 1, 251)}` рядом с `REQUIRED_TOOLS`; рядом же три текста SPEC
константами (`MODEL_UNSUPPORTED_PREFIX`, `MODEL_NOT_IN_TABLE_WARNING`,
`CLI_UPGRADE_HINT`) — один источник для runner, check_stack и отказа
после попытки. Чистая функция `stack.model_cli_verdict(model, installed)
-> (status, detail)`: `warn` для модели вне таблицы (без обращения к
CLI), `warn` при неопределившейся версии, `ok`/`fail` по сравнению
кортежей. Модуль остаётся 3.9-совместимым (`Optional[...]`, без `X | None`);
`roles` импортируется лениво внутри функции строк моделей, не на уровне
модуля (`roles.py` несёт `str | None` в сигнатурах — импорт при 3.9 упал
бы до проверки версии интерпретатора в `artel.py`).

**Требование 3 — предполёт.** В `runner._refuse_before_start` сразу после
чтения `roles.model(role)`: модель задана → `stack.model_cli_verdict(model,
stack.installed_cli_version())`, где `installed_cli_version()` — один
вызов `claude --version` через общий с `_tool_check` разбор
(`_probe_tool`), и ТОЛЬКО если модель есть в таблице (для модели вне
таблицы версия не нужна — подпроцесс не заводится, существующие
песочницы с `claude-opus-5`/`claude-sonnet-5` новых subprocess не
получают). `fail` → запись журнала действием `run отклонён: модель не
поддерживается CLI` и деталью «модель роли не поддерживается CLI:
<модель> требует claude ≥ X, установлен Y», `sys.exit` с тем же текстом
и подсказкой «обнови CLI либо смени model роли в roles.yaml» — `auto`
ловит `SystemExit`, печатает текст и останавливает цикл (AC-7) без
правки `auto.py`. `warn` → одна запись `model WARNING` на шаг, запуск как
сегодня (AC-8). Проверка стоит до `_build_prompt`/`_run_attempts`, агент
не стартует (AC-6), эскалации нет.

**Требование 4 — класс провала.** `failure_classification.
MODEL_UNSUPPORTED_SIGNATURE = "does not support this model"`, класс
`model_unsupported` с подписью в `CLASS_LABELS`, проверяется ПЕРВЫМ в
`classify_attempt_failure` (детерминированный отказ сильнее любой
эвристики повторов; общий якорь «API Error:» и списки 1а/1б/2 не меняются
— `test_ac9_the_general_api_error_anchor_still_works`). В
`_run_attempts` класс обрывает цикл на текущей попытке (как
`session_limit`): без «agent run retry», без `time.sleep`. В
`_run_developer_step` перед `_escalate_after_attempts` — новая ветка
`_refuse_model_unsupported`: та же запись журнала и тот же `sys.exit` с
подсказкой, что в требовании 3 (требуемая версия вытаскивается из текста
попытки «version X or newer is required», если есть; установленная —
`stack.installed_cli_version()`), задача остаётся в своём состоянии
(AC-9). Число попыток `config.AGENT_ATTEMPTS` и паузы прочих классов не
меняются.

**Требование 5 — check_stack.** `_tool_check` разложен на `_probe_tool`
(подпроцесс + разбор версии, возвращает `(StackCheck, Optional[tuple])`)
и прежнюю обёртку; `check_stack()` берёт версию `claude` из уже
сделанной проверки инструмента и добавляет по строке `model-<роль>` на
каждую роль `roles.yaml` с `executor: agent` и полем `model` — ноль
дополнительных подпроцессов (наблюдение «Материалов»: `check_stack()`
зовётся `runner._venv_interpreter_bin` на каждом шаге). Имя строки не
содержит «venv», фильтр `_venv_interpreter_bin` её не задевает. Детали:
`модель роли developer claude-fable-5-1: CLI 2.1.267 ≥ 2.1.251 — ok`;
`fail` с текстом отказа и подсказкой; `warn` «модель не в таблице
совместимости». `roles.yaml` нечитаем — одна строка `warn`, не
исключение. Строки доезжают до `version`/`doctor` существующей печатью
`check_stack()` (`version.py:27`, `doctor/cli.py:58`).

**Расхождение с оценкой SPEC** — нет: 3 файла кода + 4 файла тестов, шаг
один, `budget_usd` не переоценивается.

## Шаги

1. **Код** (`orchestrator/stack.py`, `orchestrator/runner.py`,
   `orchestrator/failure_classification.py`) — таблица и вердикт модели,
   `_probe_tool`/строки моделей в `check_stack`, argv[0] из резолва,
   предполётная проверка, класс `model_unsupported` без повторов и
   именованный отказ после попытки.
2. **Тесты** — новый `tests/test_runner_model_preflight.py` (AC-1, AC-3,
   AC-6, AC-7, AC-8, AC-9 на полном `cmd_run`/`cmd_auto` в песочнице
   `DeveloperBriefTmpRootTest`), новые классы в `tests/test_stack.py`
   (AC-5, AC-10, ноль лишних подпроцессов, 3.9-совместимость вердикта) и
   `tests/test_failure_classification.py` (AC-9, классификация);
   правка сверок по базовому имени в `tests/sandbox.py`,
   `tests/test_doctor.py`, `tests/test_git_fixation.py`; в
   `tests/test_stack.py::test_ok_scenario_reports_ok_for_every_tool`
   строки моделей отсекаются по имени `model-` — счёт 6 инструментов и
   статус `ok` проверяются прежним ассертом.
3. **Карта** — `python3 scripts/codebase_map.py` тем же коммитом.

Один MR; шаги — единицы проверки внутри него.

## Покрытие требований

| Требование | Шаг | Где |
|---|---|---|
| 1 (argv[0] из резолва, AC-1..AC-4) | 1, 2 | `runner.role_cmd`; `test_runner_model_preflight.StepCommandTest` |
| 2 (таблица, AC-5) | 1, 2 | `stack.MODEL_MIN_CLI_VERSION`, `model_cli_verdict`; `test_stack.ModelCliVerdictTest` |
| 3 (предполёт, AC-6..AC-8) | 1, 2 | `runner._refuse_before_start`, `_model_refusal_exit`; `test_runner_model_preflight.ModelPreflightTest` |
| 4 (класс провала, AC-9) | 1, 2 | `failure_classification.classify_attempt_failure`, `runner._run_attempts`/`_run_developer_step`; `test_failure_classification.ModelUnsupportedClassTest`, `test_runner_model_preflight.ModelUnsupportedAttemptTest` |
| 5 (check_stack, AC-10) | 1, 2 | `stack.check_stack`/`_model_checks`; `test_stack.CheckStackModelLinesTest` |
| 6 (тесты, AC-11) | 2 | перечисленные файлы; `test_invariants.py` не трогается |

## Влияние на систему

- **Инвариант 3** (лимит цикла; после лимита — Оператор, не ретрай): новый
  класс обрывает цикл РАНЬШЕ лимита (как класс 2 `session_limit`), число
  `config.AGENT_ATTEMPTS` и бэкоффы остальных классов не меняются;
  `tests/test_agent_failure.py::CmdRunFailureTest` — держатель инварианта —
  не правится.
- **Инвариант 31** (флаги изоляции в argv шага): меняется только `argv[0]`,
  `--setting-sources`/`--strict-mcp-config` на месте; держатели
  `test_agent_prompt.PromptChannelTest`, `test_doctor.IsolationSmokeTest`
  зелёные, `doctor.isolation_smoke` не правится.
- **Инвариант 35** (`check_stack()` без сети): добавлено чтение локального
  `roles.yaml`, подпроцессов не прибавилось; `test_stack.test_no_network_calls`
  остаётся.
- **Гейты/guard/лимиты**: не ослабляются. `doctor` начнёт возвращать код 1
  при модели роли ниже минимальной версии CLI — это требование 5 (FAIL),
  осознанное усиление, не ослабление.
- **`_venv_interpreter_bin`** (`role_env` на каждом шаге): `check_stack()`
  теперь ещё читает `roles.yaml`; строки моделей не содержат «venv» в
  имени и в его фильтр не попадают; подпроцессов не прибавляется.
- **Существующие тесты**, сравнивающие `argv[0] == "claude"`: переведены на
  базовое имя (решение «Материалов» SPEC); ни один тестовый метод не
  удалён (AC-11). `tests/test_invariants.py` не трогается.
- **Откат** — revert одного merge-коммита; данных/схемы БД задача не
  меняет.

## Риски

- `doctor` в окружении Оператора с моделью роли из таблицы и старым CLI
  станет красным (FAIL) — это и есть цель требования 5; подсказка в
  строке называет, что делать.
- Реальный `roles.yaml` сегодня несёт `claude-opus-5`/`claude-sonnet-5` вне
  таблицы — `doctor`/`version` получат четыре строки WARN «модель не в
  таблице совместимости», пока Оператор не дополнит таблицу (состав
  таблицы — его правка приложением, SPEC требование 2).
- Отказ после попытки (требование 4) оставляет захват зоны задачи, как и
  любой шаг, дошедший до «agent run started»; задача остаётся в `in_dev`,
  повторный `run` после обновления CLI идёт штатно.

## Предложения системе

- `tests/sandbox.py::claude_only_run`/`claude_only_popen` и четыре копии
  фильтра `c.args[0][0] == "claude"` в `tests/test_doctor.py`/
  `tests/test_git_fixation.py` — один и тот же признак «вызов CLI роли»
  жил в шести местах и правился одной задачей шесть раз; кандидат на общую
  функцию песочницы `is_claude_call(argv)`.
- `docs/stack.md` описывает манифест человекочитаемо, но вне зон задачи —
  таблица `MODEL_MIN_CLI_VERSION` там не упомянута; строка для Оператора.
