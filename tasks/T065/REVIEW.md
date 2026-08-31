---
task: T065
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 2
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: К3-канарейка: команда canary, метрики, бейзлайн

## Гейт плана

`git diff 443c35ba890c10e1f4433201f54fc8177449979f..HEAD -- tasks/T065/PLAN.md`
— пусто, PLAN.md не менялся с одобренной iteration 1. Полный разбор из
iteration 1 остаётся в силе без изменений: покрытие SPEC → PLAN полное,
шаги — проверяемые единицы, подход (отдельный кодовый путь в
`canary.py` вместо вызова `cmd_approve`/`auto`) согласован Оператором и
задокументирован. Замечаний к плану нет.

## Соответствие SPEC

Между sha предыдущего (approved, iteration 1) вердикта
`443c35ba890c10e1f4433201f54fc8177449979f` и текущим HEAD (`86aec49`)
ветка получила одну «подтяжку main» (merge-коммит `86aec49`, родители
`443c35b` и `94dfa3f` — tip main на момент подтяжки), принёсшую в main
работу T063 («RETRO: полное первое предложение сути, killed из ТЗ»).
Это НЕ доработка кода T065: сам `orchestrator/canary.py`, `catalog.py`,
`store.py`, `artel.py`, `fsm.py`, `auto.py`, `budget.py`,
`tasks/T065/PLAN.md/SPEC.md/acceptance_tests/`, `tests/test_canary.py`
не тронуты вовсе. Проверено самостоятельно на этой итерации:

- `git diff 443c35b..HEAD -- orchestrator/canary.py orchestrator/catalog.py
  orchestrator/store.py orchestrator/artel.py orchestrator/fsm.py
  orchestrator/auto.py orchestrator/budget.py tasks/T065/
  tests/test_canary.py` — 0 строк: код требований T065, приёмочные тесты
  и юнит-тесты `canary.py` не менялись.
- `git diff 443c35b..HEAD --name-only` — ровно 10 файлов, все из зоны
  T063 (`orchestrator/retro.py`, `tasks/T063/*`, `tests/test_retro.py`,
  `docs/retro/T063.md`, `docs/codebase-map.md`) — совпадает с diff,
  приложенным в пакете ревью.
- `git show --no-patch --format="%H %P" 86aec49` — merge-коммит с
  родителями `443c35b` (предыдущий approved-HEAD T065) и `94dfa3f`
  (tip main) — чистый merge, не отдельный коммит T065 поверх.
- `git merge-base --is-ancestor main HEAD` — true: ветка содержит весь
  main, подтяжка полная.
- `git diff 443c35b..HEAD -- gates.yaml docs/invariants.md` — пусто:
  защищённые пути этим диффом не затронуты вовсе (T063 их не трогал).
- `python3 -m unittest discover -s tests` — **901 тест, OK** (рост с
  867 на iteration 1 — вклад T063 в main, не T065; дрейфа в зоне T065
  нет).
- `python3 -m unittest discover -s tasks/T065/acceptance_tests -p
  "test_*.py"` — **5/5 OK** (AC-1..AC-5 подтверждены).
- `python3 scripts/guard.py --all` — ок, 225 файлов.
- Регенерация карты: `python3 scripts/codebase_map.py --check` даёт
  diff только по строке `built_at_sha` (закоммичено `443c35b...` — sha
  предыдущего approved-HEAD, локальный прогон сейчас даёт `86aec49...`
  — текущий HEAD) — тот же ожидаемый допуск, что и в предыдущей
  итерации и в аналогичной ситуации T063 iteration 5. Содержимое карты
  вне этой строки не отличается. Рабочее дерево после проверки
  возвращено в чистое состояние (`git checkout --
  docs/codebase-map.md`, подтверждено `git status --short` пустым).

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/canary.py` не менялся с iteration 1 (diff пуст) — `cmd_canary` на месте. |
| 2 | OK | Без изменений с iteration 1 — путь `_pass_spec_gate`/`_pass_acceptance_gate` через `store.set_state(actor="canary")`, не через `cmd_approve`/`auto`. |
| 3 | OK | Без изменений — `_kill_at_merge_gate` зовёт `cleanup.cmd_kill`, не approve. |
| 4 | OK | Без изменений — `_task_metrics`/`_summary`/`_write_report`. |
| 5 | OK | Без изменений — `_read_baseline`/`_write_baseline`/`_baseline_warnings`. |
| 6 | OK | Без изменений — `tasks.is_canary`, пометка в `cmd_status`/`retro.build_done`/`build_killed`; `retro.py` получил в этом диффе несвязанную правку (T063, извлечение «Сути»), но сам факт и способ пометки canary (по колонке, не по title/тексту) эта правка не касается — пометка вставляется тем же условием до и после diff. |
| 7 | OK | Без изменений — `orchestrator/budget.py` не импортируется и не трогается `canary.py`. |
| 8 | OK | Без изменений — гейт-переходы живут только в `canary.py`; `fsm.py`/`auto.py` по-прежнему не изменены ни строкой в накопленном diff от исходного review iteration 1. AC-5 (`ManualGatesNeedTheOperatorTest`, `MergeOnlyFromMergeGateTest`, `AutoNeverPassesAGateTest`) — зелёные. |

AC-1..AC-5 выполняются (прогнаны заново на этой итерации, см. выше).

## Замечания

Те же два нерешённых minor из iteration 1, перенесены без изменений
(код `canary.py` со времён iteration 1 не менялся, повод для их
закрытия не появился):

- minor — `orchestrator/canary.py:52` (`_pass_acceptance_gate`) —
  по-прежнему использует `fsm._pull_main_or_escalate`, внутреннюю
  (`_`-префикс) деталь реализации `fsm.py`, без сигнала в `fsm.py` о
  внешнем вызывателе. Не blocker (решение осознанное, обосновано в
  PLAN), но стоит держать в уме при следующей правке
  `_pull_main_or_escalate`.
- minor — `orchestrator/canary.py:24-30` (`_spec_gate_next_state`) —
  по-прежнему копирует ветвление `fsm._cmd_approve` вместо вызова общей
  функции; расхождение (если оно появится) всплывёт только на реальном
  прогоне, не на тестах этой задачи. Предложение на будущее не
  изменилось: общий предикат в `fsm.py` либо тест, сверяющий оба пути
  на матрице meta-комбинаций.

## Вердикт

approved — с sha предыдущего (approved, iteration 1) вердикта
(`443c35ba890c10e1f4433201f54fc8177449979f`) до текущего HEAD
(`86aec49`) сам код требований T065 (`orchestrator/canary.py` и все
затронутые им модули, `tasks/T065/PLAN.md/SPEC.md/acceptance_tests/`,
`tests/test_canary.py`) не менялся ни строкой; единственное изменение —
подтяжка main, принёсшая T063 (правку `orchestrator/retro.py`,
несвязанную с зоной T065; защищённые `gates.yaml`/`docs/invariants.md`
этим диффом не затронуты вовсе). Независимая перепроверка на этой
итерации (полный набор — 901 тест, OK; все 5 приёмочных тестов T065 —
OK; `guard.py --all` — ок, 225 файлов; карта свежа с точностью до
ожидаемой строки `built_at_sha`; ветка полностью содержит main) не
выявила регрессий. AC-1..AC-5 выполняются. Два minor (внутренние
зависимости `canary.py` от приватных деталей `fsm.py`) остаются не
блокирующими мерж, как и на предыдущей итерации.

## Проверено исполнением
Ретроактивная пометка при миграции корпуса под evidence-контракт (T072, 2026-08-30): это ревью прошло до появления обязательной секции «Проверено исполнением» (SPEC T072, guard.py:review_evidence_errors). Факт исполнения проверок этим ревью, если они проводились, восстановить задним числом нельзя — что реально оценивалось, отражено выше, в разделах «Соответствие SPEC»/«Замечания» этого файла. Секция добавлена постфактум одним коммитом по всему корпусу только для соответствия новому структурному правилу guard.py, содержательно не переписывает исходное ревью.

## Предложения системе

- `docs/invariants.md`, раздел инварианта 18 — наблюдение из iteration 1
  остаётся актуальным без изменений: паттерн «отдельный узкий кодовый
  путь вместо вызова публичной команды approve/auto» стоит зафиксировать
  рядом с инвариантом 18 для будущих задач класса «детерминированная
  автоматизация поверх конвейера».
