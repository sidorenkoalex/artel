---
task: 01M5NPKPWFEWTYMBYWVR797AM6
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: команда пульта `mutation-run` — прогон патчей мутаций против названных тестов во временной копии и таблица исходов

## Фаза A: план
- Таблица покрытия полна: требования 1–11 → шаг 1 (`orchestrator/mutation_run.py`), 12 → шаг 2 (`artel.py`, карта), 13 → шаг 3 (долгоживущий файл test_author).
- Шаги размера MR, подход — переиспользование `suite_run._base_copy`, `appendix_tree._carry_uncommitted`, `acceptance.run_full_suite`, `reporters/outcome.parse_junit`, `suite_lock.*` без правки модулей «только чтение» (diff: только `orchestrator/artel.py` и новый `orchestrator/mutation_run.py`, плюс карта).
- «Влияние на систему» сверено с diff: белый список +1 команда, запись только в хозяйство `suite-run` и временную копию, БД — `suite_run._db()` (откат на `mode=ro`). Отдельно проверил, что `acceptance.run_full_suite` не пишет в БД сигнал «близко к пределу» (`acceptance.py:2467`, `:2525`): `full_run = tuple(targets) == ("tests",)` (`acceptance.py:2414`), а команда передаёт явные файлы — ложных алертов триггера №32 от урезанного остатка предела нет. Откат — revert, модуль новый.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_parse_args`, `_patches` (диск → `refs/artifacts/<id>` через `ls_tree`/`show`), `_patch_range` (не `<a>-<b>`, обратный, за номерами набора), `_revision` (base — `gitcmd.diff_base`, head — голова ветки в клоне, worktree — HEAD рабочей копии), `_tree_files` + `_check_tests` (`normpath` сводит `tests/`, `./tests`, `tests/.` к `tests`; подкаталог — по префиксу файлов дерева; вне `tests/`, нет файла, не `test_*.py`) — всё до замка и копии (`cmd_mutation_run`). |
| 2 | OK | `_profile_refusal`: multi, `runner` ≠ `pult-pytest`, `_profile_command` не список → «профиль проекта не поддержан командой mutation-run». Проверил, что профиль самой артели (`targets.yaml:45–53`, `report: junit-xml` без `runner`) даёт список: `acceptance.reported` у pult = None (`suite_run.py:348`). |
| 3 | OK | Фоновый `Popen` с окружением без `config.ARTEL_ROLE_ENV`, `start_new_session`; `--wait` ≤ `SUITE_RUN_MAX_WAIT_MIN` = 9 (`config.py:243`); повторный вызов `mutation-run <id> --wait N`. |
| 4 | OK | `suite_run._base_copy` (контекст, убирает на любом исходе); маркер владельца в `holder`, вне дерева git — `git clean -ffdx` его не трогает (`suite_run.py:557–566`); коммит-основа после переноса незакоммиченных (`_prepare`). |
| 5 | OK | Контроль зелёный только при `classify` = «не убита»; таймаут контроля (и исчерпанный до контроля предел) → «контрольный прогон оборван по пределу N с». |
| 6 | OK | `touches_tests` по всем путям патча (`diff --git`, `---`/`+++`, rename/copy from/to), имена конфигов в любом каталоге; `git apply` отказ → «патч не применяется»; `-vv --continue-on-collection-errors --junitxml=<scratch вне копии>`; `_reset` с проверкой `git status --porcelain`. |
| 7 | OK | `_Budget`: остаток от старта, `min(seconds, ceil(left))`; CUT → `expired`, остальные «не прогнана (предел)», строки пишутся. |
| 8 | OK | `classify`: `failed` не уровня файла → «убита» с узлами; `error`/уровень файла → «ошибка сбора…»; нет/не разобран/пуст/ненулевой без падений → «итог неизвестен». |
| 9 | OK | `<id>-mutation-run-<n>.mutations.tsv` рядом с `<id>-mutation-run-<n>.log` в `suite_lock.directory()/<id>/`; шапка — источник (+ sha ссылки), sha ревизии, sha256 каждого выбранного патча; строка — сразу после мутации (`_Run.row`). |
| 10 | OK | `mutation-run.json`/`mutation-result.json`, `run.json` не трогается; БД — только чтение через `suite_run._db()`. |
| 11 | OK | `suite_lock.acquire` без ожидания, отказ с `describe(holder)`; номер в замке `m<n>` (`_lock_run`), `adopt` в фоне с тем же `m<n>`. |
| 12 | OK | `table`, блок «Команды:», перечень модулей, импорт, `_ROLE_ALLOWED_COMMANDS` и комментарий над ним — ровно разрешённые SPEC строки `artel.py`. |
| 13 | OK | Долгоживущий файл `tests/test_01m5npkpwfewtymbywvr797am6_mutation_run.py`: `test_ac<n>_…`, «Ловит мутацию:» у каждой функции, `FULL_SUITE_WORKERS` подменён на 2 в тестах, в `config.py` не тронут. Разработчик своих тестов не добавлял — повторов долгоживущего нет. |

## Замечания
Замечаний уровня blocker/major/minor к коду нет.

Наблюдения без записи в реестр (к коду разработчика не относятся):
- Заявка AC-12 (`test_ac12_unknown_outcome_is_never_not_killed`) называет «четвёртый (и третий)» для мутации «без учёта кода возврата»; временной мутацией (см. ниже) краснеет только четвёртый случай — третий (пустой отчёт) держит отдельная ветка `not records`. Тест мутацию ловит; неточность — в формулировке залоченного теста, правка — только `amend-tests`, не повод вернуть задачу.
- Время файла задачи в последнем прогоне пульта 114.9 с > порога 60 с (локально 71 с) — сведение Оператору, тесты держат настоящий git/pytest стенд.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний итерации 1 не заведено, прошлых итераций нет.

## Вердикт
approved — все требования 1–13 реализованы, реестр пуст, тесты задачи и соседние зелёные, временные мутации ловятся.

## Проверено исполнением
- `python3 -m pytest tests/test_01m5npkpwfewtymbywvr797am6_mutation_run.py -p no:cacheprovider -p timeout -o timeout=300 -q` — 17 passed, 50 subtests passed (71 с).
- `python3 -m pytest tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py -p no:cacheprovider -p timeout -o timeout=300 -q` — 30 passed, 17 subtests passed (198 с).
- Временная мутация 1: `classify` — `if not records or not green:` → `if not records:`; `…::OutcomeTest::test_ac12_unknown_outcome_is_never_not_killed` — SUBFAILED `case='только passed/skipped'`, 1 failed. Код возвращён.
- Временная мутация 2: `touches_tests` — проверка имён `_TEST_CONFIG_NAMES` выключена; `…::OutcomeTest::test_ac3_unappliable_and_test_touching_patches_are_not_run` — 8 failed (подтесты `.pytest.ini` и др. конфигов). Код возвращён, `git status --porcelain` пуст.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha` — расхождений нет (карта свежая), файл восстановлен `git checkout`.
- `artel.py plank-run 01M5NPKPWFEWTYMBYWVR797AM6` — «планки нет … pytest не запускался»: у задачи планки нет, как заявлено в PLAN.

## Предложения системе
- `orchestrator/mutation_run.py` зовёт закрытые `suite_run._db/_read_json/_write_json/_alive/_profile_command/_base_copy/_POLL_SEC` — вторая команда хозяйства `suite-run`; совпадает с предложением PLAN о выносе в общий модуль: любая правка закрытых имён `suite_run` теперь ломает соседа молча для её автора.
