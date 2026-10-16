---
task: 01M52EEDEYV14658X8VFNHCW8K
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: в) пути-признаки (тесты): tests/, tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py, tests/test_network_address_gate.py, tests/test_project_profile_gates.py; в) пути-признаки (гейты): orchestrator/advance_gates/two_sided.py; в) пути-признаки (песочница ролей): orchestrator/providers/__init__.py; д) ТЗ ссылается на ADR: ADR-0023
spec_sha: 83adc25bf7c95a3757ea2b70ba38628e156f692c
schema_version: 5
---

# SPEC-AUDIT: D0-1: профиль test_profile — подполя runner, workdir, env и фиксация мест запуска

## ТЗ и SPEC

ТЗ → SPEC:
- ТЗ п.1 `runner` (`pult-pytest` по умолчанию | `pytest-own`, иное — отказ) — требование 2, AC-3, AC-5.
- ТЗ п.1 `workdir` (отказ абсолютному и пути с `..`) — требование 3, AC-2; уточнено решением Оператора №2 п.3 (`..` — сегмент, `a..b` проходит) — внесено в требование 3, AC-2, AC-6.
- ТЗ п.1 `env` (вид `mapping`, `yamlmini` не меняется, точный перечень секретов `secret_env_names()` + `GITHUB_TOKEN`, `GH_TOKEN`, сверка по точному имени) — требование 4, AC-1; решения №1 п.3 (перечень из реестра, случай подмены) и №1 п.4 (не-отображение, не-строка — отказ) внесены в AC-1, AC-6.
- ТЗ п.1 `workdir`/`env` только при `pytest-own`, отказ при `pult-pytest` и по умолчанию — требование 5, AC-4.
- ТЗ п.1 «Поле `sandbox` не вводится» — «Не входит».
- ТЗ п.2 доставка в `Profile`, потребители не меняются — требование 6, AC-5, AC-6; решение №1 п.5 (значения по умолчанию, kwargs-построения в тестах `:210`, `:178` без правки) — внесено.
- ТЗ п.3 восемь мест запуска, оба пути команды — требование 7, AC-7; сужение путей у `run_plank`/`_run_side` и подача `command` через `run_full_suite` — по решению №1 п.1; точное равенство argv/cwd и разница окружения — решения №1 п.2, №2 п.1-2 — внесены дословно по смыслу (AC-7: литералы, запрет `_pytest_command`/`_pytest_env` в ожидании, наборы переменных по местам).
- ТЗ «Не входит» (acceptance.py, two_sided.py, вызывающие модули; targets.yaml только чтение) — «Не входит».
- Решение №1 п.6 (текст отказа по образцу `targets.py:281`, строка матрицы) — требование 8, AC-8, строка матрицы.

SPEC → ТЗ: требований сверх ТЗ и решений Оператора нет. «Не входит» добавляет запрет правки `orchestrator/providers/` и `yamlmini.py` — следует из ТЗ («`yamlmini` не меняется», перечень только читается), не расширение.

Расхождений нет.

## Факты против кода

Подтвердилось:
- `orchestrator/targets.py:41-53` — `PROFILE_FIELDS`, `PROFILE_OPTIONAL`; `_check_profile` `:262`, `_profile_value_error` `:284`; текст отказа `:281` «подполе 'test_profile.<подполе>' — …»; вид `dir` `:299-303`, сегментная проверка `..` `:300-301`.
- `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:103` — неизвестное подполе из `["timeout", "runner", "lang", "paths"]` со значением `"x"`; `:151-152` — `assertIn("test_profile")`, `assertIn(field)`. При `runner` известном отказ по значению `"x"` с текстом `:281` содержит `test_profile.runner` — тест остаётся зелёным, как утверждает матрица.
- `orchestrator/project_profile.py:63-85` — frozen `Profile`, `from_values`; других построений `Profile(` кроме `tests/test_project_profile_gates.py:210`, `tests/test_network_address_gate.py:178` (именованные аргументы) нет.
- `orchestrator/providers/__init__.py:36-39` — `PROVIDERS`; `secret_env_names()` — `base.py:256`, `claude.py:213` (→ `SECRET_ENV_NAMES`, `claude.py:50`), `codex.py:500` (пусто). Пакет на уровне модуля тянет только stdlib (`providers/__init__.py:10-13`), импорт реестра из `targets.py` цикла не создаёт.
- `targets.yaml:46` — `command: [python3, -m, pytest]`.
- Места запуска: `acceptance.run` `:384` (subprocess `:447-450`), `collect` `:512` (`:555-559`), `run_repeat` `:649` (`:664-669`), `run_plank` `:923` (`:931-934`, параметра `command` нет), `run_full_suite` `:1115` (argv `:1175`, `observe` из `_observe_full_suite` `:1168`), `_run_full_suite_now` `:1313` (observe — Popen `:1323-1325`, без — run `:1344-1346`; при `log` уходит в `_run_full_suite_to_log`), `_run_full_suite_to_log` `:1361` (`PYTHONUNBUFFERED` `:1372`); `_pytest_env` — `PYTHONPYCACHEPREFIX` `:86`, каталог `tempfile.mkdtemp` вне cwd; `two_sided._run_side` `two_sided.py:222` (окружение `:230-232`, `REPORT_ENV = "ARTEL_TWO_SIDED_REPORT"` `:55`). Девятого места запуска pytest в `orchestrator/` нет (`suite_result_key` `acceptance.py:1615` только строит ключ).
- `_pytest_command` `acceptance.py:59-62`: `python3` заменяется интерпретатором venv — оба пути команды дают одинаковый argv, ожидание через `stack.pytest_python_executable()` корректно. `FULL_SUITE_WORKERS = "auto"` (`config.py:226`), `PER_TEST_TIMEOUT_SEC = 120` (`stack.py:95`) — литералы, от машины не зависят.
- `yamlmini.mapping` разбирает `test_profile.env` третьего уровня — проверено разбором образца: `{'A': 'x', 'B': 1, 'C': None, 'D': ''}`.

Не подтвердилось:
- О1. Требование 4 (`SPEC.md`, требование 4) ссылается «int, bool и `None`, которые даёт разбор `yamlmini.scalar`, `orchestrator/yamlmini.py:57-62`»: в `yamlmini.py:57-62` — bool (`:57-58`), int (`:59-60`), float (`:61-62`); `None` даёт `:54-55`. Ссылка пришла из решения Оператора №1 п.4. Поведение описано верно (не-строка — отказ, включая float), неточна только ссылка; float в перечне AC-6 не назван, но покрыт формулировкой «не являющемуся строкой» требования 4.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | секреты литералом в `targets.py` или вычисленные при импорте (ловит подмена `secret_env_names()`); сверка без учёта регистра / по префиксу или подстроке (ловит «имя, отличающееся регистром или суффиксом, проходит»); пропуск `GITHUB_TOKEN`/`GH_TOKEN` |
| AC-2 | да | отсутствие проверки абсолютного пути; подстрочная проверка `".." in value` (ловит `a..b` — проходит); отсутствие проверки сегмента (`a/../b`) |
| AC-3 | да | `runner` принимает любую строку |
| AC-4 | да | проверка «только при pytest-own» читает `profile.get("runner")` без значения по умолчанию — `workdir` при отсутствующем `runner` проходит |
| AC-5 | да | `Profile.runner` по умолчанию `""`/`None`; новые поля без умолчаний — kwargs-построение падает `TypeError` |
| AC-6 | да | `from_values` не переносит `workdir`/`env`; `env` принимает строку/список; значение-int/None проходит; текст отказа без `env` |
| AC-7 | да | удаление `-p no:cacheprovider`/`-o timeout=…`/`-n auto` из argv, смена `cwd` (точное равенство с литералом); `PYTHONUNBUFFERED` вне `_run_full_suite_to_log`, утечка `REPORT_ENV`/`PYTHONPATH` в другие места, `PYTHONPYCACHEPREFIX` внутри cwd (набор «ровно такой» по значениям); тавтология ожидания запрещена явно |
| AC-8 | да | текст отказа нового подполя без `test_profile` или имени подполя — красный `test_profile.py:151-152` |

О2 (уточнение AC-7, не блокирует). argv `acceptance.run` с `file_times` и `acceptance.run_repeat` несёт `--junitxml=<путь>` во временном каталоге, который создаёт КОД (`tempfile.TemporaryDirectory(prefix="artel-file-times-")` `acceptance.py:443`, `prefix="artel-seed-repeat-"` `:661`), а не тест. AC-7 разрешает вычислять в ожидании «временные каталоги теста»; литеральное точное равенство достижимо, только если тест подменит `tempfile.mkdtemp` своим каталогом. Иначе исполнитель может взять путь отчёта из фактического argv — для этого элемента ожидание станет тавтологией. Стоит назвать допустимый приём (подмена `tempfile.mkdtemp`/`tempfile.tempdir` тестом) или явно разрешить сверку этого элемента по шаблону `<tmp>/junit.xml`.

## Зоны

- Требования 1-5, 8 — `orchestrator/targets.py`; требование 6 — `orchestrator/project_profile.py`; требование 7 и AC — `tests/`. Все в зонах SPEC (`zones: orchestrator/targets.py, orchestrator/project_profile.py, tests/`).
- `docs/codebase-map.md` (регенерация при правке `*.py`) — в `config.COMMON_ZONES`.
- `targets.yaml`, `orchestrator/acceptance.py`, `two_sided.py`, `providers/`, `yamlmini.py` — только чтение, запись не требуется: запись артели не несёт новых подполей и проходит без правки.
- Защищённые пути (`config.PROTECTED_PATHS`) не затронуты. Песочница ролей не расширяется: `providers/__init__.py` лишь читается (`secret_env_names()`); поле `sandbox` не вводится.

Расхождений нет.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `runner` становится известным подполем `test_profile` | отказ неизвестному подполю `runner`=`"x"` с текстом `test_profile`/`runner` — `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:103`, `:151-152` | остаётся: `"x"` — неверное значение `runner` (требование 2), текст по образцу `targets.py:281` (требование 8) | тот же тест без правки; AC-3, AC-8 | ок — строка SPEC верна |
| `workdir`, `env` становятся известными подполями | отказ неизвестным подполям `targets.py:268-272`; в тестах `workdir`/`env` как неизвестные не встречаются (перечень `:103` — `timeout`, `runner`, `lang`, `paths`) | для прочих имён остаётся; для `workdir`/`env` заменяется проверкой вида и условием `pytest-own` | AC-2, AC-4, AC-6 | ок — существующих тестов не трогает, строки не требует |
| `Profile` получает три поля | kwargs-построения `tests/test_project_profile_gates.py:210`, `tests/test_network_address_gate.py:178` | остаётся (значения по умолчанию) | те же тесты без правки; AC-5 | ок |

Раздела «Меняемое поведение» в SPEC нет — смены утверждений существующих тестов задача не объявляет и, по сверке выше, не требует. Ослаблений нет.

## Пути обхода гейтов

- Тавтологическое ожидание AC-7 через `_pytest_command`/`_pytest_env` закрыто запретом (AC-7); остаточная щель — путь junit-отчёта, созданный кодом (О2).
- Подмена `subprocess.run`/`Popen` в фиксирующих тестах — законный приём: вызов идёт через настоящие `_pytest_command`/`_pytest_env` мест запуска, наблюдаются фактические `argv`/`cwd`/`env`. Подмена самих `_pytest_command`/`_pytest_env` в тесте обошла бы фиксацию — SPEC этого прямо не запрещает, но точное равенство argv с литералом, содержащим `-p no:cacheprovider -p timeout -o timeout=120`, такую подмену делает красной, если подмена не возвращает тот же литерал; ловится ревью. Отдельного отклонения не поднимаю.
- Перечень секретов литералом вместо реестра закрыт случаем подмены в AC-1.
- Проверка `workdir` подстрокой закрыта `a..b` в AC-2/AC-6.

## Вердикт

concerns — отклонения мелкие, решаемы Оператором на гейте без возврата аналитику:

1. О1 — `SPEC.md`, требование 4: ссылка `orchestrator/yamlmini.py:57-62` для «int, bool и `None`» неточна — `None` даёт `orchestrator/yamlmini.py:54-55`, `:57-62` — bool/int/float. Ссылка пришла из решения Оператора №1 п.4; поведение описано верно.
2. О2 — `SPEC.md`, AC-7: путь `--junitxml` в argv `acceptance.run` (с `file_times`) и `acceptance.run_repeat` лежит во временном каталоге кода (`orchestrator/acceptance.py:443`, `:661`), а не теста; формулировка «временные каталоги теста» не называет, как получить его без чтения из фактического argv — возможная частичная тавтология ожидания. Предложение: разрешить подмену `tempfile.mkdtemp` тестом либо сверку этого элемента по шаблону.

Все решения Оператора на гейте SPEC (№1 п.1-6, №2 п.1-3) внесены; ТЗ отражено полностью; ссылки SPEC на код, кроме О1, подтвердились.
