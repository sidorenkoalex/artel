---
task: 01M5HJ4ZWRTB9481JC7SVYQ07B
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Б-1б (--parallel): постоянные тесты защиты части А и итога прогона

## Фаза A — план
- Таблица покрытия PLAN полна (требования 1–6 → шаги 1–2); шаги — проверяемые единицы (файл тестов; таблица мутаций).
- Подход (подмена `_child_argv`, учёт `_start_child`, FIFO + `wait()` без срока, запрещающие заглушки клона/профиля/origin) совпадает с образцом `tests/test_canary_parallel.py` и требованием 4.
- «Влияние на систему» = фактический diff: `tests/test_canary_parallel_protection.py` (+685) и `docs/codebase-map.md`; `orchestrator/`, `scripts/`, существующие `tests/`, `conftest.py`, `pyproject.toml` не тронуты (`git diff --stat 379f2343...HEAD`). Откат — revert коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Один новый файл; из `tests/` импортирует только `tests.sandbox` (`ALL_CONFIG_ATTRS`, `InitializedTmpRootTest`); песочница `_ProtectionSandbox` + `_CHILD`/`_GRANDCHILD` собственные. |
| 2 | OK | AC-1 (`SequentialPathTest`: литерал, строки, файл результата, реестр во время ведения/после, `argvs`/`started` пусты), AC-3 (`DetachTest`: `--parallel`×1, `--result-file`×1, без `--detach`, «результат:»×1), AC-10/AC-12 (`BaselineTest`, сравнение всей таблицы `canary_baseline`), AC-15 (`CANARY_DEFAULT_SET`, `--set` из хвоста настоящего argv, удаление записи родителя, метка с pid пожатого процесса, `live_run_note(default_set_only=True)`), AC-16 (`cmd_canary_live(drop=…)`, `gamma` без drive/clone, одна красная строка с полями `_report_child_failure`). |
| 3 | OK | M14 (код 3 + своя строка → `SystemExit` «красный», «завершён» есть, заголовок с кодом 3), M18 (проверка обработчика SIGINT до `os.kill`, `SystemExit(130)`, исход ловится `BaseException`, `rescue()` снимает группы SIGKILL, обработчики восстановлены), M20 (пустой обработчик SIGTERM до внука, внук без новой сессии, pid через FIFO, нет «снят SIGKILL», `os.kill(pid, 0)` → `ProcessLookupError`, уборка внука с подавлением). |
| 4 | OK | Нет `time.sleep`/`select`/циклов по часам; `cmd_canary` в главном потоке; `PARALLEL_STOP_GRACE_SEC` не трогается; `tests/test_invariants.py` не менялся, `DeterministicTestsLintTest` зелёный. Зависание согласующего потока при исчезнувшем дочернем/внуке снимается открытием FIFO с другой стороны (`run_cli`, блок `unblock`). |
| 5 | OK | У всех 9 методов «Сценарий» и «Ловит мутацию:» с наблюдаемым расхождением; таблица мутаций PLAN — 10 строк, все красные, `git status --porcelain orchestrator/` пуст. Независимо подтверждено планкой `test_ac2_mutations.py` (мутации на копии, 11 тестов зелёные). |
| 6 | OK | 9 passed отдельно и 45 passed вместе с соседями; самый длинный новый тест < 1 с; число тестов до/после (6468 → 6477) в PLAN. |

## Замечания

Замечаний blocker/major/minor нет.

Проверено и признано не дефектом:
- `DetachTest` наследует `InitializedTmpRootTest`, а не `_ProtectionSandbox`, и не ставит запрещающие заглушки клона/профиля: `canary.cmd_canary` подменён отказом, `Popen` подменён — путь к клону/профилю в этом тесте недостижим; изоляция конфигурации — через `InitializedTmpRootTest`.
- `docs/codebase-map.md`: после `python3 scripts/codebase_map.py` расходится только строка `built_at_sha` — карта свежа.
- Группы планки: все четыре файла `Группа: разовый`, все проверяют факты задачи (diff, мутации на копии, PLAN, зелёность) — граница верна; долгоживущие свойства держит новый файл в `tests/`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: в итерации 1 замечаний не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest tests/test_canary_parallel_protection.py tests/test_canary_parallel.py tests/test_canary_run_task.py "tests/test_invariants.py::DeterministicTestsLintTest" -p no:cacheprovider -q --durations=5` — `45 passed, 140 subtests passed in 12.54s`; среди 5 самых долгих нет ни одного нового теста (порог 0.39 с).
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M5HJ4ZWRTB9481JC7SVYQ07B` — `16 passed in 101.06s; код выхода pytest: 0` (включая `test_ac2_mutations.py`: контроль без мутаций и каждая мутация требования 5 краснит свой тест).
- `git diff --stat 379f2343...HEAD` — только `tests/test_canary_parallel_protection.py` и `docs/codebase-map.md`.
- `python3 scripts/codebase_map.py` + `git diff -U0 -- docs/codebase-map.md` — расходится только `built_at_sha`; правка откачена `git checkout`, `git status --porcelain` пуст.

## Предложения системе
- Пакет ревью исключает `docs/codebase-map.md` из diff, но в стате ветки она есть; ревьюверу приходится каждый раз руками гонять генератор, чтобы убедиться, что расхождение только в `built_at_sha` — пакет мог бы сам нести итог такой сверки.
