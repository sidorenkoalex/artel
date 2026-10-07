---
task: 01M48WT5X7ZC7332DRH85VY19D
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: повторное использование итога полного прогона tests/ на гейтах для того же дерева

## Фаза A: план
- Таблица покрытия PLAN.md охватывает требования 1–17 (1–3, 7–9 — шаг 1; 4–6, 10–11, 14 — шаги 1–2; 12–13, 15 — шаги 1, 3; 16–17 — шаг 3), плюс шаг 5 под возврат из verifying. Шаги размером с MR.
- Требование 13: причина названа с местом в коде. `_RUN_SUMMARY` (`acceptance.py:136–139` на базе) не распознавал категорию `N subtests passed`, поэтому `suite_run.parse` ставил `finished=False`, и `_base` пропускал сохранение. Исправлено расширением `_RUN_CATEGORY`, сторож — `tests/test_full_suite_reuse.py::SuiteSummaryTest`.
- Подход не конфликтует с архитектурой: вся механика сосредоточена в узле `acceptance.full_suite`, гейты получают только проводку флага. Раздел «Влияние на систему» соответствует diff. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `suite_tree_hash` строит хеш дерева через временный индекс (копия индекса + `add -u`), исходный индекс не меняется. `suite_result_key` включает tree, `sys.version`, пакеты `importlib.metadata` и собранную команду `_pytest_command("tests", command)+-n/-p xdist`. |
| 2 | OK | Запись `save_suite_result`: key, tree, source, finished_at, outcome, summary, failed, digest, log_path. |
| 3 | OK | `config.FULL_SUITE_REUSE_MAX_AGE_SEC = 86400`. |
| 4 | OK | Повтор проверяется до `_machine_lock` и до `run_full_suite`. |
| 5 | OK | Отказ гейта и `--accept-red` строятся по `run.detail`/`digest`, так же как при свежем прогоне (`fsm.py:1146–1172`). |
| 6 | OK | Фраза добавляется в `detail`. Пути журнала: `approve` (run_detail), гейт мержа (`run.detail` в обеих ветках), автогейт (красный — `run.detail`, зелёный — добавка в `fsm_autogate.py:312`). |
| 7 | OK | `save_suite_result` отбрасывает исходы вне green/red и вывод без итоговой строки. Читатель проверяет то же самое. |
| 8 | OK | Неотслеживаемые файлы вне `tasks/` дают `None`: нет ни сохранения, ни повтора. |
| 9 | OK | Каждый шаг git → `None`. Сбой пакетов или окружения → `None`. Нечитаемая или неполная запись → `None`. Исключения в `full_suite` перехватываются, после чего идёт обычный прогон. |
| 10 | OK | Флаг `--fresh-suite` есть в `artel.py` (строка использования, разбор sha), `cmd_approve` → acceptance/merge_gate (ContextVar на цикл). |
| 11 | OK | Записи разведены префиксом `gate-`/`base-`, читатель проверяет `source == kind`. Прогон ветки в `suite_run` идёт через `run_full_suite` и записи гейта не пишет. |
| 12 | OK | Для базы используются `worktree=False`, `read-tree <sha>`, `git rm --cached` по `config.FULL_SUITE_BASE_EXCLUDED_PATHS`; из команды убираются `-vv`, `-n N`, `-p xdist`, пути tests. Режим `--failed` идёт тем же путём `_base`. |
| 13 | OK | См. фазу A. Тот же путь держит `test_ac14_finished_base_has_result_file`. |
| 14 | OK | Долгоживущие `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py` (AC-1…AC-13) и `_base_reuse.py`, плюс `tests/test_full_suite_reuse.py`. |
| 15 | OK | После сохранения записи гейта `full_suite` пишет запись `base` по `suite_tree_hash(root, base=True)`. |
| 16 | OK | `tests/test_01m48wt5x7zc7332drh85vy19d_excluded_reads.py`. |
| 17 | OK | В `setUp` и `set_timeout` подполе вырезается регуляркой, утверждения не тронуты. |

Изменённые существующие тесты:
- `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py:880`: ровно одна правка вызова гейта, авторизована мандатом ANSWER-2. Утверждения и докстринг не менялись.
- `tests/test_full_suite_profile_timeout.py`: правка только в `setUp`/`set_timeout`, как требует требование 17.

Удалённых строк `assert` в диффе `tests/` нет.

## Замечания
- minor — `orchestrator/fsm_merge_gate.py:1235` — у `_cmd_approve_merge_gate` появился параметр `fresh_suite`, но цикл его не передаёт: флаг фактически идёт только через `_fresh_suite_for_cycle`. Мёртвый параметр создаёт два канала одного флага. Сценарий: будущий читатель передаст флаг параметром и решит, что ContextVar лишний, или наоборот. Предложение: оставить один канал.
- minor — `orchestrator/fsm.py:1143`, `orchestrator/fsm_merge_gate.py:925–931` — условные двойные вызовы `full_suite(..., fresh=True) if fresh_suite else full_suite(...)` вместо `fresh=fresh_suite`. Видимо, так сохранена форма вызова для существующих `assert_called_with`. Это ветвление ради тестов. Предложение: при следующей правке передавать `fresh=fresh_suite` и обновить ожидания.
- minor — `tests/test_full_suite_reuse.py:14,30,39,52,63` — докстринги состоят из одной строки «Ловит мутацию: …» без сценария (PLAN объясняет это сокращением проекции карты). Заявки при этом наблюдаемы (число вызовов, равенство ключей, `[True, False]`). Предложение: при следующей правке добавить сценарий.
- minor — `orchestrator/appendix_tree.py:60` (контекст, файл не менялся) — автогейт накладывает приложения `git apply` без `--index`. Приложение, создающее новый файл, оставляет его неотслеживаемым, и `suite_tree_hash` даёт `None`: повтора нет (fail-closed, корректно), но экономии для таких задач тоже нет. Читал файл, чтобы проверить AC-4 для приложений с новыми файлами. Предложение: учесть при следующей задаче о повторном использовании.
- minor — `orchestrator/acceptance.py:1296`, `orchestrator/fsm.py:1339`, `orchestrator/fsm_merge_gate.py:1330–1332` — сбитые отступы продолжений строк. Только косметика.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/fsm_merge_gate.py:1235 | мёртвый параметр `fresh_suite` рядом с ContextVar | два канала одного флага, путаница при сопровождении | minor, принято без правки в этой задаче |
| R1-F2 | accepted | orchestrator/fsm.py:1143; orchestrator/fsm_merge_gate.py:925–931 | двойные условные вызовы вместо `fresh=fresh_suite` | лишнее ветвление ради формы вызова в тестах | minor, принято без правки |
| R1-F3 | accepted | tests/test_full_suite_reuse.py:14,30,39,52,63 | докстринги без сценария, только заявка | хуже читается назначение теста | minor, принято без правки |
| R1-F4 | accepted | orchestrator/appendix_tree.py:60 | новые файлы приложений неотслеживаемы, повтор отключён | упущенная экономия (fail-closed), не ошибка | наблюдение, вне объёма задачи |
| R1-F5 | accepted | orchestrator/acceptance.py:1296; orchestrator/fsm.py:1339; orchestrator/fsm_merge_gate.py:1330–1332 | сбитые отступы | косметика | minor, принято без правки |

## Вердикт
approved: blocker и major нет, все пять замечаний minor и приняты без правки.

## Проверено исполнением
- `python3 -m pytest tests/test_full_suite_reuse.py tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py tests/test_01m48wt5x7zc7332drh85vy19d_excluded_reads.py tests/test_01m48wt5x7zc7332drh85vy19d_profile_timeout.py tests/test_full_suite_profile_timeout.py tests/test_suite_run.py -p no:cacheprovider -q` — 42 passed, 11 subtests passed.
- `python3 -m pytest tests/test_acceptance.py tests/test_fsm_autogate.py tests/test_merge_gate_ci_wait.py tests/test_full_suite_profile_timeout.py -p no:cacheprovider -q` — 68 passed, 7 subtests passed. Сюда входят тесты, чьё ожидание держит fail-closed по требованию 9 (SPEC, «Материалы»).
- `python3 -m pytest "tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py::BaseComparisonTest"` — 4 passed (в том числе `test_ac13_gate_full_suite_result_is_reused_as_base` после правки по ANSWER-2).
- `artel.py plank-run 01M48WT5X7ZC7332DRH85VY19D`: отказ «в источнике нет файлов test_*.py». Планка задачи — долгоживущие файлы `tests/test_01m48wt5x7zc7332drh85vy19d_*.py`, они прогнаны выше и зелёные.
- `git diff 158aa0da...HEAD -- tests/ | grep '^-\s+self\.assert'`: пусто, удалённых утверждений нет.
- CI коммита abf10ed1 зелёный (16 проверок), по данным пакета.
- Не выполнено: временная мутация `if key and not fresh:` → `if key:` для проверки AC-11. Запуск `sed -i` в шаге требовал подтверждения, которого в шаге нет. Чувствительность `test_ac11` оценена по коду: без флага второй вызов взял бы сохранённый красный итог, `run.call_count` остался бы равен 1 и состояние осталось бы `acceptance`.

## Предложения системе
- Скил review-checklist требует проверять тесты временной мутацией, но профиль прав ревьювера отклоняет `sed -i`/правку кода без подтверждения. Нужен штатный канал временной мутации, например команда пульта по образцу `plank-run`, иначе этот пункт скила невыполним.
