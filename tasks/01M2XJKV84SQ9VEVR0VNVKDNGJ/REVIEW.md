---
task: 01M2XJKV84SQ9VEVR0VNVKDNGJ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Роль запускается по абсолютному пути из манифеста, модель роли сверяется с версией CLI до старта агента

Ревью HEAD `1a2e3681` (один кодовый коммит поверх базы `56b8e043`).
SPEC.md и PLAN.md в ревью-пакет не вошли («не показан … в дереве — файл
не найден»), хотя на диске рабочего каталога оба материализованы из
головы артефактной ветки (`artifact/01m2xjkv84sq9vevr0vnvkdngj`, коммит
`612be28b`) — прочитаны инструментом чтения по адресам
`tasks/<id>/SPEC.md`, `tasks/<id>/PLAN.md`, `tasks/<id>/TZ.md` и вся
планка `tasks/<id>/acceptance_tests/` (без них не заполнить ни гейт
плана, ни таблицу соответствия; планка нужна для сверки «залочена и не
правлена»: `git diff 07270bfa artifact/... -- acceptance_tests` пуст —
после шага test_author планка не менялась).

## Фаза A: гейт плана

1. **Покрытие SPEC полно.** Таблица «Покрытие требований» PLAN несёт все
   6 требований, каждое адресовано шагом и тестом; AC-1..AC-11
   сопоставлены модулям `tests/` и планке. Расхождений с SPEC по
   существу нет; имена тестовых классов в таблице PLAN расходятся с
   фактическими (см. R1-F1, minor).
2. **Шаги — проверяемые единицы.** Три шага (код трёх модулей, тесты,
   карта) внутри одного MR — размер под монолит, который SPEC обосновал
   («не режь зону поперёк»: требования 1 и 3 — соседние строки одного
   пути запуска в `runner.py`; требования 3 и 4 обязаны давать один
   именованный исход). PLAN его не оспаривает; согласен.
3. **Подход не конфликтует с архитектурой.** Резолв внутри `role_cmd()`
   при нулевой сигнатуре (101 патч по имени модуля, AC-4); таблица и
   тексты отказа — одним источником в `stack.py` (3.9-совместимость
   сохранена, `roles` импортируется лениво); `_probe_tool` даёт
   `check_stack()` версию без второго подпроцесса; отказ — `sys.exit`
   тем же приёмом, что пауза/стоп-кран, `auto.py` не правится (SPEC «Не
   входит»). Секция «Влияние на систему» соответствует фактическому diff
   (см. «Системная целостность» ниже); путь отката — revert одного
   merge-коммита, схема БД не меняется.

Замечаний по плану, требующих правки до реализации, нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (argv[0] из резолва манифеста, AC-1..AC-4) | OK | `runner.role_cmd()` (`orchestrator/runner.py:879`) — `_resolve_declared_tools()["claude"]`, тот же резолв, что даёт `_role_path_dirs`; флаги после argv[0] не тронуты, `--model` довеском в `_spawn_and_wait`. `role_env` не менялся — PATH роли прежний (планка AC-2 зелёная). Обе точки вызова `role_cmd()` стоят после успешного `role_env()`: `_prepare_step:1055` → `_spawn_and_wait:1135`; `doctor/isolation.py:70` → `:112` — `OSError` резолва там уже обработан. `orchestrator/doctor/` в diff нет. Тесты: `StepCommandArgv0Test` (в т.ч. сценарий затенения — тёзка `claude` в каталоге `gh` раньше по PATH роли), планка `test_ac1_ac2_ac3_step_command.py`, `test_ac4_role_cmd_single_source.py`. |
| 2 (таблица `MODEL_MIN_CLI_VERSION`, AC-5) | OK | `orchestrator/stack.py:103` рядом с `REQUIRED_TOOLS`, запись `"claude-fable-5-1": (2, 1, 251)`; все три точки читают её через `model_cli_verdict` — подмена таблицы меняет вердикт (`test_verdict_reads_the_table_not_a_literal`, `test_minimum_comes_from_the_table_not_from_a_literal`, планка AC-5). Модель вне таблицы — `warn`, не отказ, в трёх точках (`test_model_outside_the_table_is_a_warning_regardless_of_version`, `ModelOutsideTheTableTest`, `test_ac5_model_outside_the_table_is_not_a_refusal`). |
| 3 (предполёт до агента, AC-6..AC-8) | OK | `_refuse_before_start:404-427` сразу после `roles.model(role)`, до `_build_prompt`/`_run_attempts`; `claude --version` только для модели из таблицы (`test_unknown_model_warns_once_and_the_step_runs_without_probing_cli` считает вызовы — 0). Текст записи дословно по SPEC: действие `run отклонён: модель не поддерживается CLI`, деталь «модель роли не поддерживается CLI: <модель> требует claude ≥ X, установлен Y; обнови CLI либо смени model роли в roles.yaml». `sys.exit` ловится `auto._role_run_step:838`, текст с подсказкой печатается, цикл останавливается (AC-7 — `test_auto_stops_on_the_refusal_and_prints_the_upgrade_hint`). Захват зоны при таком отказе снимается `_cmd_run` (`claimed_but_not_started` истинен — «agent run started» не записан). Одна запись `model WARNING` на шаг для модели вне таблицы (AC-8). |
| 4 (класс «модель не поддерживается CLI», AC-9) | OK | `failure_classification.classify_attempt_failure:75` проверяет сигнатуру первой, до `CLASS_1A`/`1B`/якоря «API Error:»; класс не в `TRANSIENT_SYSTEM_CLASSES`, подпись в `CLASS_LABELS`. `_run_attempts:541` обрывает цикл без «agent run retry» и без `time.sleep`; `_run_developer_step:253` даёт тот же именованный отказ через `_model_unsupported_after_attempt` (та же запись `MODEL_UNSUPPORTED_REFUSAL_ACTION`, тот же префикс и подсказка), задача остаётся `in_dev`. Контроль: «API Error: 500» — по-прежнему «системный кандидат» с полными попытками и эскалацией (`test_other_api_errors_still_retry_as_system_candidates`). См. R1-F2 (minor) о разборе требуемой версии из хвоста лога. |
| 5 (`check_stack` — строки моделей ролей, AC-10) | OK | `_model_checks` (`stack.py:275`): по строке `model-<роль>` на роль с `executor: agent` и полем `model`; `ok` дословно «модель роли developer claude-fable-5-1: CLI 2.1.267 ≥ 2.1.251 — ok», `fail` при заниженной, `warn` вне таблицы, `warn` при нечитаемом `roles.yaml` (не исключение). Версия `claude` — из уже сделанного `_probe_tool`, ровно один `claude --version` на `check_stack()` (`test_model_lines_reuse_the_tool_probe_without_extra_subprocesses`); имя строки без «venv» — фильтр `runner._venv_interpreter_bin:694` её не задевает (`test_model_line_names_do_not_match_the_venv_filter`). Печать — существующая: `version.py:27`, `doctor/cli.py:58`; `doctor/cli.py:16` (`checks[-1]`) смотрит на `check_cli_found`, к порядку `check_stack` не привязан — проверено чтением. |
| 6 (тесты в `tests/`, AC-11) | OK | Новый `tests/test_runner_model_preflight.py` (8 тестов на полном `cmd_run`/`cmd_auto`), новые классы в `tests/test_stack.py` (14) и `tests/test_failure_classification.py` (4); `tests/test_runner_role_model.py`, `tests/test_stack.py`, `tests/test_stack_ci.py` зелёные; `tests/test_invariants.py` не тронут; удалённых `assert` в `tests/` — 0. У каждого нового/изменённого теста заявка «Ловит мутацию» (проверено разбором AST — пропусков нет); заявки сверены с кодом: таблица vs литерал, порядок проверки сигнатуры, счёт подпроцессов, фильтр «venv», `None` вместо кортежа — мутации правдоподобны, тесты их ловят. |

Корректность за пределами таблицы, что проверял отдельно:
- Порядок в `_refuse_before_start`: пауза → стоп-кран → workspace →
  pre-flight → фиксация → скилы → модель. Отказ модели стоит после
  `workspace.ensure` (worktree уже создан) — безвредно, повторный `run`
  после обновления CLI идёт штатно; `zone_lock.claim` для той же задачи
  (`_occupies`) не отказывает.
- Модель из таблицы, версия CLI не определилась (`claude --version`
  упал/не распознан) — `warn`, шаг идёт; SPEC этот случай не оговаривает,
  fail-open согласован с «модель вне таблицы — не отказ» и с тем, что
  последующий `spawn_agent` честно даст «claude CLI не найден».
- `_probe_tool` возвращает версию и при `warn` «ниже минимальной
  инструмента» — сверка модели получает реальное число, не `None`.
- `tests/sandbox.py::is_claude_call` — сверка по базовому имени, как
  решено в «Материалах» SPEC; `claude_only_run`/`claude_only_popen` и
  четыре копии фильтра в `test_doctor.py`/`test_git_fixation.py`
  переведены на неё — без этого абсолютный путь ушёл бы в настоящий
  `Popen`. `_stub_which` песочницы падает на стаб только при отсутствии
  бинарника на машине — тест AC-1 сравнивает argv[0] с тем же `which`.
- `orchestrator/stack.py` разбирается грамматикой 3.9 (`ast.parse(...,
  feature_version=(3, 9))` — ок); `Optional`/`namedtuple` импортированы.
- Безопасность: секретов нет; подпроцессы — фиксированный argv
  (`claude --version`), `roles.yaml` читается локально (инвариант 35,
  `test_no_network_calls` зелёный); недоверенный текст попытки идёт
  только в `re.search`/подстроку, в команды не попадает.
- Системная целостность (ADR-0002): тесты/гейты/лимиты не ослаблены —
  `test_ok_scenario_reports_ok_for_every_tool` отсекает строки `model-`
  по имени, прежние ассерты (счёт 6, статусы `{"ok"}`) сохранены;
  `config.AGENT_ATTEMPTS`/бэкоффы прочих классов не тронуты (инвариант
  3: новый класс обрывает цикл раньше лимита, как `session_limit`).
  `skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`,
  `orchestrator/doctor/`, `orchestrator/version.py`, `orchestrator/
  auto.py`, `orchestrator/config.py`, `orchestrator/roles.py`,
  `tests/test_invariants.py` — diff пуст. Пометок `AC-n: manual|skip` в
  планке нет. Файлов `ANSWER-n.md` у задачи нет.

## Замечания

- minor — `tasks/01M2XJKV84SQ9VEVR0VNVKDNGJ/PLAN.md:125,127` (таблица
  покрытия) и `:76` («Требование 4») — PLAN называет тестовые классы
  `StepCommandTest`/`ModelPreflightTest` и функцию
  `_refuse_model_unsupported`, которых в коде нет (фактически
  `StepCommandArgv0Test`, `ModelBelowCliMinimumTest`/
  `ModelOutsideTheTableTest`, `_model_unsupported_after_attempt`).
  Последствие: PLAN как навигация по MR ведёт на несуществующие имена —
  verifier/Оператор ищут их и не находят. Предложение: поправить имена в
  PLAN (артефакт, не код) либо принять как есть — на поведение не
  влияет. Класс один, оба места перечислены.
- minor — `orchestrator/runner.py:454` (`_model_unsupported_after_attempt`:
  `required_cli_version(reason)`) — требуемая версия разбирается из
  `reason`, а это `rc=…; хвост <лог>:\n{log_tail}` (`_finish_failed:1281`,
  `config.LOG_TAIL_LINES=15`/`LOG_TAIL_CHARS=1000`), тогда как сам класс
  определяется по ПОЛНОМУ тексту попытки (`_attempt_output_text`, `:1290`).
  Сценарий: строка «does not support this model; version X or newer is
  required» лежит выше последних 15 строк/1000 символов лога — отказ
  назван верно (класс из полного текста), но деталь теряет «требует
  claude ≥ X», остаётся только «установлен Y». В инциденте 19.09 строка
  API-ошибки — последняя в выводе, хвост её несёт; ущерб — неполная
  подсказка, не ложный исход. Предложение (не для этой задачи): брать
  число из того же полного текста, которым классифицируется попытка
  (вернуть его из `_record_failure_classification` либо хранить
  `log_path` в исходе `run_agent_once`).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tasks/01M2XJKV84SQ9VEVR0VNVKDNGJ/PLAN.md:76,125,127 | PLAN называет `StepCommandTest`, `ModelPreflightTest`, `_refuse_model_unsupported` — в коде имена иные | Навигация по MR из PLAN ведёт на несуществующие имена; на поведение не влияет | minor, только артефакт: покрытие требований по существу верно (каждое требование адресовано реальными тестами, перечисленными в таблице соответствия выше). Закрыто ревьювером на месте как наблюдение; `accepted` — чтобы гейт `review -> verifying` не отклонил `approved` |
| R1-F2 | accepted | orchestrator/runner.py:454 | Требуемая версия CLI разбирается из хвоста лога (`log_tail`), класс — из полного текста попытки | Если строка API-ошибки вне последних 15 строк/1000 символов, отказ верен, но деталь без «требует claude ≥ X» | minor, правки в рамках задачи не требует: SPEC требование 4 предписывает «тот же именованный отказ» — он есть; число требуемой версии для модели вне таблицы — дополнение разработчика сверх SPEC. Закрыто на месте как наблюдение для будущей правки (см. «Замечания») |

## Вердикт
approved

## Проверено исполнением

Рабочий каталог `.artel/worktrees/01M2XJKV84SQ9VEVR0VNVKDNGJ`, HEAD
`1a2e3681`; CI коммита зелёный (7 проверок, по пакету).

- `python3 -m pytest tasks/01M2XJKV84SQ9VEVR0VNVKDNGJ/acceptance_tests -q
  -p no:cacheprovider` — 22 passed, 5 subtests passed (2.0 s): AC-1..AC-11
  планки, в том числе AC-4 (`orchestrator/doctor/` не изменён относительно
  базы ветки) и AC-11 (методы названных файлов не удалены,
  `tests/test_invariants.py` байт-в-байт с базой).
- `python3 -m pytest tests/test_runner_model_preflight.py tests/test_stack.py
  tests/test_stack_ci.py tests/test_failure_classification.py
  tests/test_runner_role_model.py tests/test_doctor.py tests/test_git_fixation.py
  tests/test_agent_failure.py tests/test_agent_prompt.py
  tests/test_alerts_wave_breaker.py tests/test_sandbox.py tests/test_version.py
  -q -p no:cacheprovider` — 300 passed, 19 subtests passed (67 s):
  затронутые модули плюс держатели инвариантов 3 и 31
  (`CmdRunFailureTest`, `PromptChannelTest`, `IsolationSmokeTest`).
- `python3 scripts/codebase_map.py`, затем `git diff -- docs/codebase-map.md`
  — единственная изменившаяся строка `built_at_sha`; карта по содержимому
  свежая; перегенерация отменена `git checkout -- docs/codebase-map.md`.
- `python3 scripts/guard.py tasks/<id>/SPEC.md tasks/<id>/PLAN.md` —
  `GUARD: ок (2 файлов)`; `python3 scripts/guard.py tasks/<id>/REVIEW.md`
  на этом файле — ок (прогнан перед сдачей).
- `python3 -c "ast.parse(open('orchestrator/stack.py').read(),
  feature_version=(3, 9))"` — разбирается: 3.9-совместимость модуля
  (`artel.py` читает `REQUIRED_PYTHON` до проверки интерпретатора).
- Разбор AST `tests/test_runner_model_preflight.py`, новых классов
  `tests/test_stack.py`, `tests/test_failure_classification.py`,
  изменённых тестов `tests/test_doctor.py`: тестов без строки «Ловит
  мутацию» среди новых/изменённых — `[]`.
- `git diff 56b8e043 HEAD -- tests/ | grep -E '^-\s*(self\.assert|assert)'`
  — пусто (удалённых/изменённых ассертов нет);
  `git diff 56b8e043 HEAD --stat -- skills/ templates/ gates.yaml roles.yaml
  .github/ orchestrator/doctor/ orchestrator/version.py orchestrator/auto.py
  orchestrator/config.py orchestrator/roles.py tests/test_invariants.py
  docs/invariants.md` — пусто.
- `grep -rnE "AC-[0-9]+: *(manual|skip)" tasks/<id>/acceptance_tests/` —
  пусто.
- `git diff --stat 07270bfa artifact/01m2xjkv84sq9vevr0vnvkdngj --
  tasks/<id>/acceptance_tests` — пусто: планка после шага test_author не
  правилась.
- Прочитаны точечно (причины — в тексте выше): `orchestrator/runner.py`
  `_cmd_run:185-222`, `_run_developer_step`, `_refuse_before_start:264-429`,
  `_run_attempts`, `_escalate_after_attempts`, `_resolve_declared_tools`,
  `_venv_interpreter_bin`, `_prepare_step:1040-1074`, `_spawn_and_wait:
  1104-1153`, `_finish_failed:1272-1301`; `orchestrator/stack.py:185-214`
  (`_probe_tool`, except-ветка и таймаут); `orchestrator/roles.py:56-93`;
  `orchestrator/zone_lock.py:382-444`; `orchestrator/auto.py:816-895`
  (обработка `SystemExit`); `orchestrator/doctor/cli.py:13-60`
  (`checks[-1]`, печать `check_stack`); `tests/sandbox.py:95-139`
  (`_stub_which`, стаб `check_stack`); `scripts/guard.py:915-1044` (форма
  реестра); `roles.yaml` (поля `model`, `executor`).

## Предложения системе

- Ревью-пакет снова не нашёл `tasks/<id>/SPEC.md`/`PLAN.md` («в ветке —
  не существует; в дереве — файл не найден»), хотя в рабочем каталоге
  шага они материализованы из артефактной ветки. То же наблюдение сделал
  ревьювер 01M2XMCG167615YS9EZD9TYJWV — класс подтверждён дважды: сборщик
  пакета (`orchestrator/review.py`/`context_package.py`) ищет артефакты
  в кодовой ветке, а не в `artifact/<id>`/на диске `role_cwd`.
- `auto._role_run_step:875` на отказ модели даёт общий
  `Stop("run отказался стартовать", "artel.py budget … или artel.py kill …",
  alert=True)`: подсказка про бюджет/kill противоречит только что
  напечатанной подсказке отказа («обнови CLI…»), и открывается алерт
  буксования. SPEC сознательно вынес `auto.py`/`AUTO_STOP_*` за зоны —
  строка Оператору: `config.AUTO_STOP_MODEL_UNSUPPORTED` + детектор по
  действию `runner.MODEL_UNSUPPORTED_REFUSAL_ACTION` тем же приёмом, что
  `_run_paused_refusal`.
- Версия CLI за один шаг роли разбирается до трёх раз тремя копиями
  логики: `doctor.preflight.cli_version` (pre-flight), `stack.
  installed_cli_version` (сверка модели), `stack._probe_tool` внутри
  `check_stack()` из `role_env` на каждую попытку. Ни одна не переиспользует
  другую (границы зон трёх задач). Кандидат на один источник версии на шаг.
- Реальный `roles.yaml` несёт `claude-opus-5`/`claude-sonnet-5` вне таблицы
  — с этого MR `doctor`/`version` печатают четыре строки WARN «модель не в
  таблице совместимости» до правки таблицы Оператором (PLAN «Риски» это
  назвал); `docs/stack.md` таблицу не упоминает (PLAN уже отметил).
