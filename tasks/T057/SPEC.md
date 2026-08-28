---
task: T057
type: spec
author_role: analyst
status: ready
schema_version: 2
budget_usd: 40
---

# SPEC: Дедупликация liveness-хелперов и lease-обвязки

## Контекст

Ревизия 28.08 (docs/audits/code-revision-2026-08-28.md), находки
CR-2026-08-28-3 и CR-2026-08-28-4, очередь Оператора п.2б роадмапа.
Контур параллельности T044–T053 писался разными прогонами конвейера
и наплодил дубли: `_age_seconds` определена байт-в-байт в
`orchestrator/lease.py:44` и `orchestrator/merge_lock.py:28`;
`_pid_alive` — байт-в-байт в `orchestrator/doctor.py:535` и
`orchestrator/merge_lock.py:34` (докстринг второй копии сам ссылается
на первую). Три места знают формат `heartbeat_ts`, менять его страшно.
Связка `resolve_session_id → acquire → отказ → try/finally
release-если-fresh` повторена 8 раз: `orchestrator/fsm.py` (advance,
approve, reject), `orchestrator/runner.py` (run), `orchestrator/auto.py`
(auto), `orchestrator/budget.py` (budget), `orchestrator/cleanup.py`
(kill), `orchestrator/workspace.py` (workspace) — с двумя вариациями
канала отказа (`sys.exit` против `print`+`return`). Каждая следующая
мутирующая команда клонирует восьмую копию.

## Требования

1. `_age_seconds` и `_pid_alive` получают единственное определение
   каждая — в одном модуле (`orchestrator/lease.py` либо новый
   маленький `orchestrator/liveness.py` — выбор модуля отдаётся
   разработчику в PLAN). `orchestrator/merge_lock.py` и
   `orchestrator/doctor.py` переходят на импорт вместо собственных
   копий. Дедуплицируются только идентичные куски — не более.
2. Обвязка lease мутирующих команд (`resolve_session_id → acquire →
   отказ → try/finally release-если-fresh`) сворачивается в одну общую
   точку в `orchestrator/lease.py` (контекст-менеджер или эквивалент)
   с параметром поведения отказа (`sys.exit` против `print`+`return`).
3. Все 8 прежних вызывателей обвязки — `orchestrator/fsm.py` (advance,
   approve, reject), `orchestrator/runner.py` (run), `orchestrator/auto.py`
   (auto), `orchestrator/budget.py` (budget), `orchestrator/cleanup.py`
   (kill), `orchestrator/workspace.py` (workspace) — переходят на общую
   точку из требования 2.
4. Семантика каждого из 8 вызывателей сохраняется в точности: тот же
   текст отказа, тот же канал отказа (exit-код либо печать+return),
   release вызывается только для lease, взятого с нуля этим же вызовом
   (`fresh`), поведение `kill` (инвариант 14) не меняется.
5. Наблюдаемые поверхности не меняются: CLI-вывод и тексты отказов всех
   8 команд, журнал (`store.journal`), схема БД, вывод `doctor` —
   байт-в-байт как до задачи.
6. Существующие тесты не меняют сценарии и ассерты; допустимы только
   правки импортов и путей патчей (`mock.patch.object`), адресующих
   новый дом хелперов и общей точки обвязки.
7. Затронуты только `orchestrator/`, тесты (импорты/пути патчей) и
   карта кодовой базы (`python3 scripts/codebase_map.py` тем же
   коммитом — правятся `*.py` в `orchestrator/`).

## Критерии приёмки

AC-1. `_age_seconds` определена ровно один раз в репозитории (вне
`tasks/*/acceptance_tests`) — grep по репозиторию подтверждает
отсутствие второго определения.

AC-2. `_pid_alive` определена ровно один раз в репозитории (вне
`tasks/*/acceptance_tests`) — grep по репозиторию подтверждает
отсутствие второго определения.

AC-3. Обвязка `acquire`/`release` мутирующих команд вызывается из одной
общей точки в `orchestrator/lease.py`; все 8 прежних вызывателей
(`orchestrator/fsm.py`: advance, approve, reject; `orchestrator/runner.py`:
run; `orchestrator/auto.py`: auto; `orchestrator/budget.py`: budget;
`orchestrator/cleanup.py`: kill; `orchestrator/workspace.py`: workspace)
используют эту точку — grep прямых пар `acquire`+`release` по этим
вызывателям не находит остаточных самостоятельных копий обвязки.

AC-4. Полный набор unittest зелёный после изменений; число тестов не
уменьшилось относительно текущего HEAD.

AC-5. Тексты отказов lease и вывод `doctor` не изменились: существующие
тесты, сверяющие эти тексты, проходят зелёными без правок ассертов.

## Не входит

- CR-2 (тестовая копипаста FakeProc/claude-only/TmpRootTest) —
  следующая задача очереди, не смешивать с этой.
- Изменение семантики `lease`/`merge_lock`/`doctor`, порогов
  (`config.LEASE_STALE_AFTER_SEC` и т.п.), текстов отказов и журнала.
- Новые возможности lease (release-команда, изменение порога) —
  отдельная строка очереди (P3).

## Материалы

- docs/audits/code-revision-2026-08-28.md — находки CR-2026-08-28-3,
  CR-2026-08-28-4.
- orchestrator/lease.py, orchestrator/merge_lock.py,
  orchestrator/doctor.py — текущие дубли (`_age_seconds`, `_pid_alive`).
- orchestrator/fsm.py:389,892,963,988; orchestrator/runner.py:78;
  orchestrator/auto.py:79; orchestrator/budget.py:248;
  orchestrator/cleanup.py:119; orchestrator/workspace.py:106 —
  8 точек обвязки `resolve_session_id → acquire → release`.
