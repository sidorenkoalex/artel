---
task: 01M52EEFNA1WH31962HVNT0YZ9
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: D0-2: раннер pytest-own в местах запуска — команда, workdir, чистое окружение, группа процессов

## Подход
Профиль `project_profile.Profile` идёт в места запуска каналом `command`
(`run`, `collect`, `run_repeat`, `run_full_suite`, `full_suite`,
`suite_result_key`); у `run_plank` и `two_sided.run` — новый
необязательный параметр `profile` (до `two_sided._run_side`). Профиль
`pult-pytest` сводится к его команде (`_head`) — путь артели проходит
прежним кодом: `_pytest_command`, `_pytest_env`, `subprocess.run`, тот же
`cwd`. Ветка `pytest-own` распознаётся `_own(command)` и в каждом месте
меняет ровно четыре вещи через общие помощники `acceptance.py`:

- `_place_command` — команда профиля как есть + аргументы места +
  `-p no:cacheprovider` (без интерпретатора пульта, `-p timeout`,
  `-o timeout=…`, `-n`/`-p xdist`);
- `_own_cwd` — `cwd` = `<дерево>/workdir`, сверка `realpath` с деревом
  прогона перед прогоном (у полного набора — ещё раз после взятия замка);
  наружу или не каталог — именованный отказ `WORKDIR_REFUSAL`, pytest не
  запускается; в полном наборе текст начинается с
  `FULL_SUITE_NOT_STARTED`, и `full_suite` уже по существующей ветке
  возвращает «не запущен» без лога и без итога;
- `_own_env` — `PATH`, `LANG`/`LC_ALL`, `TMPDIR`, `test_profile.env`, свой
  `HOME` и `PYTHONPYCACHEPREFIX` (новые каталоги, удаляются в `finally`);
  служебные переменные места (`PYTHONUNBUFFERED`, плагин/отчёт
  двустороннего) дописывает место, как у `_pytest_env`;
- `_run_in_session` — Popen со `start_new_session`, по таймауту и любому
  исключению `killpg` группы; контракт исходов как у `subprocess.run`
  (`TimeoutExpired` с выводом), поэтому обработка в местах не меняется.
  Прогон полного набора с наблюдением и в лог уже шёл своим сеансом — там
  меняются только окружение и `cwd`.

Пути: `_own_target` переводит путь от корня в путь из `workdir`
(абсолютные, флаги и id с `::` — как есть; узлы двустороннего прогона,
собранные пультом из путей от корня, переводятся частью пути, `--rootdir`
остаётся деревом — id отчёта от корня, как ждёт `_verdict`). Полный
набор: цель — `long_lived_dir` (и при `targets=("tests",)`), предпроверка
— каталог `long_lived_dir`, условие сигнала близости к пределу — флаг
`full_run`, вычисленный до перевода. Ключ итога `pytest-own` —
`_own_suite_result_key`: argv его прогона (base вычищает цель
`long_lived_dir` и пути под ней) плюс `runner`, `workdir`, `env`; ключ
`pult-pytest` — прежний код на `_head(command)`.

`acceptance_suite` читает профиль проекта задачи (`_task_own_profile`:
`store.task_target` → `repo_context.profile_of`); `pytest-own` —
`full_suite(..., command=<профиль>)`, иначе (и при непрочитанной строке
задачи или профиле) — прежняя форма вызова.

Код отказа `run_plank` — `REFUSED_EXIT_CODE = 4` (код pytest «ошибка
запуска»): `None` у `run_plank` уже значит таймаут.

ANSWER-1 (итерация 2):
- п.1: `run_full_suite(..., test_ids=())` — новый необязательный параметр
  для id упавших тестов (`--failed`): идут в argv после целей без
  перевода к `workdir` (у `pult-pytest` — тем же местом после целей).
  Цель `tests` у `pytest-own` заменяется на `long_lived_dir` в любом
  наборе целей. Пока вызывающий (часть 3) параметр не передаёт, прежняя
  передача id через `targets` тоже без перевода (id с `::` — как есть).
- п.2: `two_sided._root_form` приводит nodeid и путь места утверждения
  отчёта стороны `pytest-own` к форме от корня дерева, если pytest назвал
  их от `workdir` (страховка поверх `--rootdir` дерева: команда-обёртка
  проекта вправе задать pytest свой корень). `run_repeat` уже отдаёт
  `RedTest.node` от корня (`_junit_node` сопоставляет `classname` с
  хвостом пути файла от корня) — закреплено тестом.

## Шаги
1. `orchestrator/acceptance.py`: помощники `_own`, `_head`,
   `_place_command`, `_place_env`, `_own_env`, `_own_cwd`, `_own_target`,
   `_run_in_session`, `_run_pytest`; ветки `pytest-own` в `run`,
   `collect`, `run_repeat`, `run_plank(profile=)`, `run_full_suite`,
   `_run_full_suite_now`/`_run_full_suite_to_log` (`profile=`),
   `suite_result_key`, `acceptance_suite`.
2. `orchestrator/advance_gates/two_sided.py`: `run(profile=)` →
   `_run_side(profile=)` — `cwd` из `workdir`, перевод узлов, окружение и
   сеанс `pytest-own`.
3. `tests/test_acceptance_suite_profile.py` — свойство, не покрытое
   долгоживущими файлами задачи: `acceptance_suite` передаёт профиль
   `pytest-own` полному набору и зовёт прежней формой при `pult-pytest` и
   непрочитанном профиле. Карта `docs/codebase-map.md` регенерирована.
4. ANSWER-1: `run_full_suite(test_ids=)`, `two_sided._root_form`;
   `tests/test_pytest_own_result_ids.py` — двусторонний прогон учебного
   проекта с `workdir` ≠ корня (и своим `pytest.ini`) выносит вердикт по
   методу, а не «узел не найден»; `RedTest.node` `run_repeat` — от корня;
   `test_ids` в argv без перевода (`pytest-own`) и после целей
   (`pult-pytest`). Зафиксированные тесты не правились.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2, 3 |
| 2 | 1, 2 |
| 3 | 1, 2 |
| 4 | 1, 2, 4 |
| 5 | 1, 2 |
| 6 | 1, 2 |
| 7 | 1 |
| 8 | 1, 2 |
| 9 | долгоживущий `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py` (test_author) |

Проверка: долгоживущий файл задачи (12 тестов) и фиксация части 1
`tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py` — 20 passed;
планка `plank-run` — 3 passed; `test_acceptance*.py`, `test_plank_run_edges`,
`test_project_profile`, `test_suite_near_limit`, `test_suite_run`, оба
файла двустороннего прогона — 136 passed. Свой тест проверен мутацией
(`acceptance_suite` без чтения профиля — 6 подтестов красные). Полный
набор `suite-run` №1 — зелёный: прошло 5538, упало 0, пропущено 2.

Итерация 2 (ANSWER-1): затронутые модули с новым
`tests/test_pytest_own_result_ids.py` — 149 passed; каждый из его тестов
покраснел на своей мутации (снятие `--rootdir` и `_root_form` — «узел не
найден»; `_junit_red_tests` по путям от `workdir`; перевод `test_ids`);
планка — 3 passed; полный набор `suite-run` №2 — зелёный: прошло 5542,
упало 0, пропущено 2.

## Влияние на систему
- Путь артели (`pult-pytest`) не меняется: профиль сводится к команде,
  вызовы идут прежними `_pytest_command`/`_pytest_env`/`subprocess.run`
  с прежним `cwd`; это держат фиксация части 1 (argv, `cwd`, окружение,
  форма вызова `run`/`Popen` восьми мест на обоих путях команды), тест
  `AcceptanceSuiteTreeFailureTest` без правки и планка (ключ итога артели
  байт в байт по формуле до задачи).
- Защита не ослаблена: `-p timeout` у `pytest-own` снят по решению
  Оператора 16.10.2026 (SPEC, требование 6) и заменён пределом прогона и
  снятием группы процессов; отказ `workdir` — fail-closed (не зелёный, в
  полном наборе «не запущен», без лога и итога).
- Вызывающие мест вне двух модулей профиль пока не передают (часть 3 D0)
  — для них поведение прежнее.
- Сигнатуры: новые параметры только необязательные (`profile=None`);
  подмены тестами `_run_full_suite_now`/`_pytest_env` совместимы.
- Откат — revert коммита задачи.

## Риски
- Потомок команды профиля, ушедший в собственный сеанс, группой не
  снимается; дочитывание вывода после `killpg` ограничено
  `_OWN_DRAIN_SEC`, чтобы гейт не повис.
- `realpath` сверяется перед запуском: подмена ссылки между сверкой и
  `Popen` не ловится (окно — микросекунды, песочница — вне задачи).

## Предложения системе
- Имя параметра профиля у мест без `command` SPEC не называл (записка
  test_author) — долгоживущий тест угадывал его по сигнатуре; такие имена
  стоит фиксировать в SPEC.
