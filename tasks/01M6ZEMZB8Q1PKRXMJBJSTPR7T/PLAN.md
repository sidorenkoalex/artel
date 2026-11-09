---
task: 01M6ZEMZB8Q1PKRXMJBJSTPR7T
type: plan
author_role: developer
status: draft
schema_version: 5
---

# PLAN: Тёплый байткод интерпретатора в прогонах pytest пульта

## Подход
Свежий `PYTHONPYCACHEPREFIX` каждого прогона остаётся (`_pytest_env`,
`_own_env` его по-прежнему заводят и убирают); перед вызовом pytest в
него копируются допущенные файлы шаблона байткода своего интерпретатора.

- `orchestrator/config.py`: `PYCACHE_TEMPLATES_ENV = "PYCACHE_TEMPLATES_DIR"`,
  `pycache_templates_dir(environ, tmp_root, uid, root)` (AC-4),
  `PYCACHE_TEMPLATES_DIR` вычисляется при импорте от `tempfile.gettempdir()`,
  `os.getuid()`, `ROOT`; `PYCACHE_TEMPLATE_BUILD_TIMEOUT_SEC = 60`,
  `PYCACHE_TEMPLATE_RETRY_SEC = 3600`.
- `orchestrator/acceptance.py`, блок «шаблон байткода» сразу после
  `_place_env`: поверхности AC-1…AC-8 (`pycache_source`, `template_admits`,
  `template_dir`, `manifest_intact`, `publish_template`, `template_decision`,
  `command_interpreter`) и узел `_warm_prefix`:
  1. `command_interpreter` не распознал `command[0]` или он не разрешился
     (абсолютный / от `run_dir` / `shutil.which` по PATH прогона) — молча
     пусто (требование 9);
  2. место выключено или лежит под `ROOT`/`WORKTREES`/`PROJECTS` — строка;
  3. место заводится 0700 (`os.mkdir` + `chmod`), `lstat`; недоверено
     (`template_decision` → `untrusted`) — строка, в месте ничего не
     трогается, запрос даже не запускается;
  4. запрос сведений (`python -c`, пустой временный `cwd`, без префикса,
     `subprocess.run` с пределом) → ключ AC-3;
  5. шаблон читается один раз: хэши всех файлов → `manifest_intact`, байты
     допущенных AC-2 (пути интерпретатора из запроса; исключены `run_dir`,
     `WORKTREES`, `PROJECTS`) — в память; копируются в префикс эти же байты,
     поэтому «расхождение хэша при копировании» = нецелость шаблона;
  6. `template_decision`: `fill` — копия; `discard` — переименование в
     `.discard-…` и удаление, строка; `skip` — строка; `build` — пробный
     прогон `python -c "pytest.main(...)"` (argv без элемента `pytest`) в
     пустом временном `cwd` с отдельным временным префиксом, без
     `PYTHONDONTWRITEBYTECODE`, `-p xdist -n 1`, если xdist есть; отбор
     AC-2 в staging `.<имя>.XXXX` внутри места, `manifest.json`, набор без
     `_pytest` — неудача; `publish_template` (rename; проигравший удаляет
     staging и наполняет из стоящего); неудача — отметка `<имя>.failed` со
     временем, строка; успех снимает старую отметку.
  Любое исключение запроса/сборки/копирования — пустой префикс и ровно одна
  строка `шаблон байткода интерпретатора недоступен: <причина>` в stderr;
  исход прогона не меняется.
- Подключение: `_place_env` стал генератором: у раннера пульта с `run_dir`
  зовёт `_pytest_env()` без аргументов и наполняет отданное окружение
  (интерпретатор — параметр `interpreter` либо `_pytest_command(...)[0]`);
  полные прогоны (`_run_full_suite_now`, `_run_full_suite_to_log`) передают
  `argv[0]`. `_own_env` с `run_dir` наполняет сам — так покрыты `pytest-own`
  во всех местах и `_report_env`. Без `run_dir` (`two_sided`) — пусто.
  Окружение прогона pytest новых переменных не получает.
- `tests/sandbox.py` (мандат ANSWER-1): рядом с `config.MODELS_LOCAL` —
  `config.PYCACHE_TEMPLATES_DIR` на `_SANDBOX_CONFIG_DIR/pycache-templates` и
  тот же путь в `os.environ[config.PYCACHE_TEMPLATES_ENV]`; прочие строки не
  тронуты.

Оценка бюджета SPEC ($50) не пересматривается.

## Шаги
1. config: константы и `pycache_templates_dir`.
2. acceptance: поверхности AC-1…AC-8, узел `_warm_prefix`, сборка, подключение
   в `_place_env`/`_own_env`/полные прогоны.
3. `tests/sandbox.py`: подмена места.
4. Прогон долгоживущих файлов задачи, залоченного
   `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py` и соседних модулей
   acceptance; замер требования 12; карта `scripts/codebase_map.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 (`_warm_prefix_from_template`, `_place_ready`) |
| 2 | 3 |
| 3 | 2 (`template_dir`, `_interpreter_info`) |
| 4 | 2 (`manifest_intact`, `_read_template`) |
| 5 | 2 (`_build_template`, `_helper_run`, `publish_template`) |
| 6 | 2 (шаблон не обновляется; удаление каталога — пересборка) |
| 7 | 2 (`_place_env`, `_own_env`, `_copy_into`) |
| 8 | 2 (`template_decision`, `_discard_template`, `_failed_age`) |
| 9 | 2 (`command_interpreter`, `_resolve_interpreter`) |
| 10 | 2 (`_pytest_env()` без аргументов; helpers без `pytest` в argv, до вызова pytest) |
| 11 | 4 |
| 12 | 4 (замер ниже) |

## Свидетельства
Тесты (в переднем плане, `python3 -m pytest … -p no:cacheprovider -p timeout`):
- `tests/test_01m6zemzb8q1pkrxmjbjstpr7t_template_rules.py` — 66 passed;
- `tests/test_01m6zemzb8q1pkrxmjbjstpr7t_template_runs.py` — 22 passed (62 с);
- `tests/test_01m6zemzb8q1pkrxmjbjstpr7t_sandbox_place.py`,
  `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`,
  `tests/test_acceptance_pycache.py`,
  `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py`,
  `tests/test_full_suite_profile_timeout.py`, `tests/test_acceptance.py` —
  43 passed.

Замер (`tasks/…/measure_warm.py`, `run_full_suite` проекта из трёх тестов,
`FULL_SUITE_WORKERS=1`, 5 прогонов, медиана; машина роли под нагрузкой
параллельного прогона тестов): холодный префикс 1,190 с; первый прогон со
сборкой 1,758 с; тёплый префикс 0,652 с. Доли наполнения
(`measure_parts.py`): запрос 0,025 с, чтение+хэш шаблона 0,031 с, копия
234 файлов (5,3 МБ) ≈0,05 с.

## Влияние на систему
- Затронуты все прогоны pytest пульта с каталогом прогона: в них до вызова
  pytest появляются процесс запроса (каждый прогон) и, один раз на
  интерпретатор, процесс сборки. Оба — через `subprocess.run` модуля
  `acceptance`, без элемента `pytest` в argv, ограничены 60 с, любой их
  сбой — пустой префикс и строка, исход прогона прежний.
- Свойства SPEC 01M3Y7G6T3MK7A899521VF9N7B: префикс по-прежнему свой новый
  каталог на прогон, убирается на выходе; байткод `cwd`/рабочих копий в него
  не попадает (AC-2 с исключениями) — ac6 залоченного теста зелёный без
  правки.
- Доверие к шаблону: место 0700, владелец — текущий uid, манифест sha256 на
  каждый файл; умышленная подмена тем же uid — риск принят Оператором
  (ANSWER-1, ответ 2).
- Двусторонний прогон (`place_env(profile)` без `run_dir`) не меняется.
- Откат — revert merge-коммита; кеш шаблонов в системном временном каталоге
  после отката просто не читается.

## Риски
- Тесты, подменяющие `subprocess.run` модуля `acceptance` целиком, теперь
  видят лишний вызов запроса до pytest; ответ подмены, не похожий на JSON,
  даёт строку о сбое в stderr, исход прогона тот же.
- Существующий тест, требующий пустого префикса в момент запуска полного
  набора, противоречит требованию 7 — см. «Эскалация».

## Предложения системе
- SPEC требование 10 перечисляло тесты, чьи подмены `subprocess` задевает
  новая механика, но не нашло утверждение «префикс пуст в момент запуска»
  в `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py:65`:
  аудиту SPEC, меняющей свойство прежней SPEC, полезен grep по утверждениям
  этого свойства во всём `tests/` (класс «меняемое свойство держит чужой
  тест»).
