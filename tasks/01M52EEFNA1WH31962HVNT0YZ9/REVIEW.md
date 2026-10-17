---
task: 01M52EEFNA1WH31962HVNT0YZ9
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: D0-2: раннер pytest-own в местах запуска — команда, workdir, чистое окружение, группа процессов

## Фаза A: план
- Таблица покрытия полна: требования 1–9 сопоставлены шагам 1–4 (9 — долгоживущий файл test_author). ANSWER-1 п.1–2 отражены шагом 4.
- Шаги — размер MR (помощники + ветки мест; two_sided; тест acceptance_suite; ANSWER-1), не микрооперации.
- Подход не конфликтует с архитектурой: профиль идёт каналом `command`, путь `pult-pytest` сведён к прежнему коду (`_head` → `_pytest_command`/`_pytest_env`/`subprocess.run`); новые параметры необязательные. «Влияние на систему» соответствует diff: тронуты ровно `orchestrator/acceptance.py`, `orchestrator/advance_gates/two_sided.py` и два новых файла `tests/` (зоны SPEC), карта свежа.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `run`/`collect`/`run_repeat`/`run_full_suite`/`full_suite`/`suite_result_key` — профиль каналом `command`; `run_plank(profile=)`, `two_sided.run(profile=)` → `_run_side(profile)`; `_run_full_suite_now`/`_to_log` получают собранный argv и `profile=own`. `acceptance_suite` читает профиль (`_task_own_profile`), при `pult-pytest`/непрочитанном — прежняя форма вызова (`tests/test_acceptance.py` зелёный, `tests/test_acceptance_suite_profile.py` держит обе формы). |
| 2 | OK | `_place_command` (`acceptance.py` ~:135): команда профиля как есть + аргументы места + `-p no:cacheprovider`; без `-p timeout`, `-n`, `-p xdist`. |
| 3 | OK | `_own_cwd` сверяет `realpath` с деревом; отказ `WORKDIR_REFUSAL` во всех восьми местах до запуска; в полном наборе текст начинается с `FULL_SUITE_NOT_STARTED` → `full_suite` уходит в существующую ветку «не запущен» без лога и итога; повторная сверка после взятия замка. |
| 4 | OK (см. R1-F1) | `_own_target` переводит пути от корня к `workdir`, id с `::` и флаги — как есть; `tests` → `long_lived_dir`; `test_ids` (ANSWER-1 п.1) без перевода; предпроверка по `long_lived_dir`, условие полного прогона — `full_run` до перевода, base-ключ вычищает цель `long_lived_dir`. Перевод лексический — ломается на `workdir`-ссылке внутри дерева (minor). |
| 5 | OK | `_own_env`: `PATH`, `LANG`/`LC_ALL`, `TMPDIR`, `profile.env`, новые `HOME` и `PYTHONPYCACHEPREFIX`, оба убираются в `finally`; `PYTHONUNBUFFERED` у прогона в лог, плагин/отчёт у двустороннего (без `PYTHONPATH` пульта). |
| 6 | OK | `_run_in_session`: `start_new_session`, `killpg` по таймауту и `BaseException`; точечные места и `_run_full_suite_now` без `observe` идут через него; observe/лог — прежний Popen в своём сеансе. |
| 7 | OK | `_own_suite_result_key`: argv прогона + `runner`/`workdir`/`env`; путь `pult-pytest` — прежний код на `_head(command)` (тест равенства ключей в долгоживущем файле). |
| 8 | OK | Фиксация части 1 `tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py` и планка (`test_ac1_artel_unchanged`) зелёные. |
| 9 | OK | Учебные проекты во временных каталогах песочницы, без сети и `uv`, обёртка порождает дочерний процесс. |
| ANSWER-1 п.1 | OK | `run_full_suite(test_ids=)`, без перевода; `tests/test_pytest_own_result_ids.py::test_full_suite_test_ids_passed_untranslated`. |
| ANSWER-1 п.2 | OK | `--rootdir` дерева + `_root_form` в `_run_side`; `RedTest.node` от корня; тесты `test_two_sided_verdict_by_method_from_workdir`, `test_run_repeat_red_node_from_root`; зафиксированные тесты не правились. |

## Замечания

- minor — orchestrator/acceptance.py `_own_target` (~:183; то же в `orchestrator/advance_gates/two_sided.py::_root_form`, обратное преобразование) — перевод пути от корня к `workdir` лексический (`os.path.relpath(path, profile.workdir)`), а процесс работает в `realpath` каталога. Сценарий (проверен исполнением): `workdir: link`, где `link` — ссылка внутри дерева на `real/inner`; цель `real/inner/checks/test_a.py` переводится в `../real/inner/checks/test_a.py`, из реального `cwd` такого файла нет — `run_plank` вернул код 4, точечный и полный прогон корректного проекта будут красными. Fail-closed (ложного зелёного нет), профили с обычным каталогом `workdir` не затронуты. Предложение (на усмотрение, не к этой итерации): переводить через `os.path.relpath(realpath(tree/path), realpath(cwd))`, а в `_root_form` — от `realpath`.
- minor — orchestrator/advance_gates/two_sided.py `_run_side` (~:247-252) — ветка `if own: acceptance._run_in_session(...) else: subprocess.run(...)` дублирует уже существующий `acceptance._run_pytest(profile, cmd, cwd, env, timeout)`. Последствие — две копии развилки раннера, при следующей правке разойдутся. Предложение — звать `_run_pytest`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/acceptance.py `_own_target`; two_sided.py `_root_form` | лексический перевод путей при `workdir`-ссылке внутри дерева | прогон корректного проекта красный (код 4), fail-closed | minor, принято как есть: SPEC такой случай не требует, поведение безопасное; при желании — перевод от `realpath` в следующей задаче |
| R1-F2 | accepted | orchestrator/advance_gates/two_sided.py `_run_side` | дубль развилки `_run_pytest` | две копии развилки раннера | minor (вкус), принято как есть |

## Вердикт
approved — blocker/major нет; два minor приняты как есть (реестр закрыт).

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py tests/test_acceptance_suite_profile.py tests/test_pytest_own_result_ids.py` — 25 passed, 150 subtests passed (56.8 с).
- `python3 orchestrator/artel.py plank-run 01M52EEFNA1WH31962HVNT0YZ9` (пульта) — 3 passed, код выхода 0.
- `python3 -m pytest -q -p no:cacheprovider tests/test_acceptance.py tests/test_suite_run.py tests/test_suite_near_limit.py tests/test_plank_run_edges.py -x` — 48 passed, 8 subtests passed (в т.ч. `AcceptanceSuiteTreeFailureTest` без правки).
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py tests/test_acceptance_collect.py tests/test_acceptance_file_time.py tests/test_acceptance_pycache.py tests/test_acceptance_seed_repeat.py tests/test_approve_acceptance_full_suite.py tests/test_acceptance_tests_flow.py tests/test_mutation_claim_gate.py` — 141 passed, 49 subtests passed.
- `python3 scripts/codebase_map.py` — расхождение только в строке `built_at_sha` (карта свежа по содержимому); рабочая копия возвращена `git checkout -- docs/codebase-map.md`.
- Сценарий R1-F1 скриптом во временном каталоге: `_own_cwd` пропускает ссылку внутри дерева, `_own_target` даёт `../real/inner/checks/test_a.py` (файла нет), `run_plank(..., profile=p)` → 4.
- Сверка `tests/` по diff: только два новых файла, существующие тесты не изменены и не удалены; оба новых теста несут «Ловит мутацию» с наблюдаемым расхождением.

## Предложения системе
- Записка разработчика верно заметила: SPEC не назвал имя нового параметра профиля у `run_plank`/`two_sided.run`, долгоживущий тест угадывал его по сигнатуре (`via_new_param`). Имена новых параметров публичных мест стоит фиксировать в SPEC (skills анализа).
