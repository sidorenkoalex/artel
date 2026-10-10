---
task: 01M4K2767FXKZ8EW7AME81SZ9N
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Полный прогон — предел notes из профиля, сигнал «длительность близка к пределу»

## Фаза A: план
- Покрытие: требования 1–6 есть в таблице PLAN; шаги 1–6 — проверяемые единицы
  (suite_lock / acceptance / notes / docs / тесты / приложение Оператора).
- Подход — одна точка `acceptance.run_full_suite` для гейта, `suite-run` и
  `notes`: `suite_run.py` (только чтение) не тронут; задача прогона берётся из
  замка машины (`suite_lock.my_task_id`), сигнатуры вызовов не меняются. С
  архитектурой не конфликтует; зона `suite_lock.py` нужна сигналу (ANSWER-1 п.1).
- «Влияние на систему» сходится с diff: 4 файла кода/доков + новый
  `tests/test_suite_near_limit.py` + карта; путь отката описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `notes._suite_limit_kwargs` (notes.py:986) берёт `project_profile.full_suite_limit(DEFAULT_TARGET)`, печатает «предел L с (источник: …)»; «config» не передаётся явно, подставит `run_full_suite` (acceptance.py:1167) — шпион `spy_suite(root)` не сломан; `TargetsError` → запасной предел с причиной в выводе. |
| 2 | OK | `_signal_near_limit`: `duration >= SUITE_NEAR_LIMIT_RATIO * seconds`; строка вывода, `store.journal` задачи держателя замка, `alerts.raise_alert(kind="trigger", source="suite.near_limit")`. Константа в acceptance.py, не в config.py. `green`/`output` не трогаются; сбой записи — в строку, не исключение. |
| 3 | OK | Дедуп по `source` + `target` среди `open_alerts(conn, "trigger")`, не по тексту; после ack открытого нет → новый. |
| 4 | OK | docs/triggers.md строка №32: условие с `SUITE_NEAR_LIMIT_RATIO`, источник данных, реакция при ack, где виден. |
| 5 | OK | Пределы прежние; замок — только новое чтение `my_task_id`; `timed_out` → отказ, как раньше (AC-5 зелёный). |
| 6 | OK | Существующие методы `tests/` не изменены (diff `tests/` — только новый файл). |

## Замечания

Дефектов кода уровня blocker/major/minor не найдено. Наблюдения без записи в реестр:

- Ветка в нынешнем виде даёт красный `tests/test_invariants.py::DeterministicTestsLintTest::test_tests_tree_has_no_wall_clock_waits_or_live_file_reads`
  (воспроизведено локально, pytest и unittest): `GateNearLimitTest.threshold_constant`
  долгоживущего файла test_author читает живой `docs/triggers.md`. Это не дефект
  разработчика: `tests/test_invariants.py` в SPEC — только чтение, AC-10 прямо
  требует строку триггера в живом документе. Приложение PLAN проверено:
  `git apply --check` проходит, с ним `tests/test_invariants.py` — 79 passed.
  **Оператору перед merge**: применить приложение PLAN (или эквивалентную
  запись `_EXCEPTIONS`), иначе полный набор на ветке/после мержа красный.
  Пакет сообщает «CI 98016f62 зелёный» — с локальным воспроизведением это не
  сходится; стоит сверить, гонял ли CI этот коммит целиком.
- `_signal_near_limit` срабатывает и на прогоне, оборванном таймаутом
  (длительность ≥ предела) — задокументировано в PLAN, SPEC этого не запрещает,
  исход «отказ» сохраняется.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved. Условие мержа вне зоны разработчика — приложение PLAN к
`tests/test_invariants.py` применяет Оператор (см. «Замечания»).

## Проверено исполнением
- `pytest tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py tests/test_suite_near_limit.py` — 15 passed, 4 subtests passed.
- `artel.py plank-run 01M4K2767FXKZ8EW7AME81SZ9N` — отказ «планки нет» (в `refs/artifacts/…` нет test_*.py; все тесты задачи — долгоживущие в `tests/`).
- `pytest tests/test_invariants.py -k DeterministicTestsLint` и `python3 -m unittest tests.test_invariants.DeterministicTestsLintTest` — 1 failed (живое чтение `docs/triggers.md` в `threshold_constant`).
- Приложение PLAN: `git apply --check` — OK; временно применено → `pytest tests/test_invariants.py` — 79 passed, 215 subtests; откат `git checkout -- tests/test_invariants.py`, дерево чистое.
- Затронутые модули: test_doc_commit, test_doc_commit_held_base, test_doc_commit_suite_gate, test_full_suite_profile_timeout, test_full_suite_reuse, test_suite_lock, test_suite_run — 80 passed; test_01m462qa…_suite_run, test_01m46c776…_suite_run_appendix, test_01m46d5t8…_full_suite_lock, test_01m48wre8…_full_suite_limit_runs, test_01m49b90…_full_suite_once, test_01m4araxf…_doctor_duration, test_01m4araxf…_suite_observation, test_approve_acceptance_full_suite — 88 passed, 72 subtests; test_acceptance — 21 passed.
- Временная мутация: условие `if tuple(targets) == ("tests",)` → `if True` в acceptance.py — `FailedRerunTest::test_failed_rerun_gives_no_signal_full_run_does` красный (заявка подтверждена); код возвращён.
- `python3 scripts/codebase_map.py` — содержимое карты (без `built_at_sha`) совпадает с закоммиченным.

## Предложения системе
- Пакет ревью заявил «CI зелёный», а линт `tests/test_invariants.py` на той же голове красный локально — стоит, чтобы пакет называл, какие джобы CI реально прошли полный набор на коммите (orchestrator/review-пакет).
- Поддерживаю предложение PLAN: test_author, чей долгоживущий тест читает живой документ, должен готовить запись `_EXCEPTIONS` сам (или линт стоит гонять на выходе `tests_writing`) — иначе каждый такой случай доходит до мержа красным.
