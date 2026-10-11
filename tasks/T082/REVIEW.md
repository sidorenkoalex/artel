---
task: T082
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 2
---

# REVIEW: Эвристики ошибок агента: классы отказов и бэкофф

## Гейт плана (Фаза A)

PLAN.md обновлён шагом 6, документирующим закрытие обоих major-замечаний
итерации 2 (`ci.status_kind`, `find_run_id` с `CI_RUNS_PER_PAGE` и
выбором самого свежего НЕ-зелёного завершённого прогона). Покрытие
требований по-прежнему полное, шаги остаются проверяемыми единицами.
Раздел «Влияние на систему» описывает эффект шага 6 верно и без
преувеличения: `status_kind` только СУЖАЕТ круг случаев ре-рана до
прежнего (до T082) поведения для running/unknown, инвариант 7 не
ослаблен. Раздел «Риски» честно называет свою собственную слабость
(`status_kind` решает по тем же русским подстрокам, что кладёт в `note`
`branch_status`, — рассинхронизация текста тиха) — это дисклеймер, не
дефект: альтернативой был бы третий канал из `branch_status`, а
locked-приёмочный `test_ci_flake_rerun.py` мокает её именно
двухэлементным кортежем, так что решение оправдано условиями задачи.
Новых конфликтов с конвенциями нет. Гейт плана пройден.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 2 — код не тронут (`git diff 35af54d..HEAD -- orchestrator/runner.py` пуст). |
| 2 | OK | Без изменений — код не тронут, `test_session_limit.py` зелёные. |
| 3 | OK | Без изменений — `test_transient_bundle.py` зелёные. |
| 4 | OK | Без изменений — `test_session_limit.py` AC-9 зелёный. |
| 5 | OK | Без изменений — `test_stream_broken.py` зелёные. |
| 6 | OK | Без изменений — хвостовой срез журнала, закрыто в итерации 2. |
| 7 | OK | Оба major итерации 2 закрыты кодом (см. «Замечания» — пусто) и подтверждены целевыми тестами: `orchestrator/ci.py:159-183` (`status_kind`) + `orchestrator/fsm.py:1130` (`if ci.status_kind(note) != "red": sys.exit(...)`) закрывают замечание 1 (running/unknown больше не триггерят ре-ран и не пишут «подтверждённый красный»); `orchestrator/ci.py:212-231` (`find_run_id`, `config.CI_RUNS_PER_PAGE=10`, выбор самого свежего завершённого НЕ-зелёного прогона с деградацией на «самый свежий вообще») закрывает замечание 2 (промах мимо реально упавшего прогона при двух workflow-прогонах на sha). |

## Замечания

Нет.

## Вердикт

approved — оба major замечания итерации 2 закрыты точечно и без побочных
эффектов: diff с момента предыдущего вердикта (`git diff 35af54d..HEAD`)
касается ровно `orchestrator/ci.py`, `orchestrator/fsm.py`,
`orchestrator/config.py` и соответствующих тестов — требования 1-6 не
затронуты. Оба фикса воспроизводят ровно те сценарии поломки, что были
описаны в замечаниях итерации 2 (см. «Проверено исполнением»), и
locked-приёмочный `test_ci_flake_rerun.py` (AC-14..17) остаётся зелёным
без изменения контракта `ci.branch_status` (по-прежнему двухэлементный
кортеж) — решение из PLAN «Риски» (текстовый подтип вместо нового
канала) реализовано так, как заявлено, и не потребовало ослабления
locked-теста.

## Проверено исполнением

- `git log --oneline main..HEAD` и `git log --oneline -- orchestrator/ci.py orchestrator/fsm.py orchestrator/runner.py orchestrator/config.py` — прочитаны для восстановления реальной хронологии: diff в пакете ревью (от sha `abf1a5d` — «sha предыдущего вердикта») пуст на T082-код (там только T083/докс-файлы от `T082: подтяжка main`), потому что фикс-коммит `7b6ec0c` («T082: закрытие замечаний ревью итерации 2») лежит В АНЦЕСТРИИ `abf1a5d`, не после него; итерация 2 review-коммит — `35af54d`. Поэтому проверка шла по `git diff 35af54d..HEAD`, не по diff из пакета.
- `git diff 35af54d..HEAD -- orchestrator/ci.py orchestrator/fsm.py orchestrator/config.py orchestrator/runner.py orchestrator/spend.py` — прочитан целиком: подтверждено, что фикс ограничен `ci.py` (`status_kind`, обновлённый `find_run_id`), `fsm.py` (одна новая ветка `if ci.status_kind(note) != "red"`), `config.py` (`CI_RUNS_PER_PAGE=10`); `runner.py`/`spend.py` не тронуты — требования 1-6 вне риска регрессии.
- Прочитан `orchestrator/ci.py` целиком (`status_kind` строки 159-183, `find_run_id` строки 186-231) — `status_kind` разбирает `note` по тем же подстрокам «ещё идёт»/«неизвестен», что кладёт `branch_status`, иначе возвращает `"red"`; `find_run_id` теперь запрашивает `CI_RUNS_PER_PAGE=10` прогонов, выбирает самый свежий из завершившихся НЕ-зелёных, деградирует на самый свежий вообще при отсутствии таких.
- Прочитан `orchestrator/fsm.py:1119-1163` (`_cmd_approve_merge_gate`) — подтверждена последовательность: `branch_status` → если `status_kind(note) != "red"` — немедленный `sys.exit` без `trigger_rerun`/`flake-rate` (замечание 1 закрыто); иначе — `trigger_rerun` → повторный `branch_status` → `flake-rate` с текстом «флейк»/«подтверждённый красный».
- `python3 -m unittest tests.test_ci_status tests.test_ci_status_kind_gate -v` — 40 тестов, все зелёные; в т.ч. `StatusKindTest` (3 теста: running/unknown/red-классификация), `FindRunIdTest::test_the_failed_run_is_picked_over_a_more_recent_green_one`/`test_the_most_recent_failed_run_is_picked_among_several`/`test_falls_back_to_the_most_recent_run_when_none_is_failed` (сценарий «два прогона на sha» из замечания 2 теперь покрыт), `NonRedStatusSkipsRerunTest` (2 теста) — напрямую воспроизводит фактуру замечания 1 итерации 2 (`branch_status` возвращает `(False, "CI коммита abc12345 ещё идёт: guard")`) и проверяет, что `ci.trigger_rerun` не вызывается (`side_effect=AssertionError` при вызове) и «flake-rate» не пишется.
- `python3 -m unittest tasks.T082.acceptance_tests.test_ci_flake_rerun -v` — 5 тестов (AC-14..17), все зелёные: locked-тест по-прежнему мокает `ci.branch_status` двухэлементным кортежем и подтверждает, что сценарий `RED = "не зелёный: python=failure"` (реальный failure, не running/unknown) классифицируется как `status_kind == "red"` и проходит прежний контракт ре-рана без изменений.
- `python3 -m unittest discover -s tasks/T082/acceptance_tests -p "test_*.py" -v` — 28 тестов (AC-1..AC-17), все зелёные.
- `python3 -m unittest discover -s tests -p "test_*.py"` — полный набор, 1063 теста, все зелёные (фоновый прогон, ~131с).
- `python3 scripts/codebase_map.py --check` — без вывода: карта свежая.
- `grep -n "CI_RUNS_PER_PAGE\|CI_RERUN_WAIT_SEC\|TRANSIENT_SYSTEM_BACKOFF_SEC" orchestrator/config.py` — все три константы на месте, использованы там, где заявлено в PLAN.

## Предложения системе
