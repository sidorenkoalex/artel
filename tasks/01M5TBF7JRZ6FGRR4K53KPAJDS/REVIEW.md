---
task: 01M5TBF7JRZ6FGRR4K53KPAJDS
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Эпики Э2б — надзирающий процесс эпика `auto --epic`

## Фаза A: план

- Таблица покрытия полна: требования 1–15 привязаны к шагам; 14 — к сверке Э2а
  в «Подходе» (маркер `merge_after.role_step_started`, `start_after_pending`,
  `budget.epic_spent`); 15 — существующие тесты не правились (подтверждено:
  в diff `tests/` только новый `tests/test_epic_supervisor_units.py`).
- Шаги — размер MR (схема/запросы, надзор, CLI, watch, тесты), не микрооперации.
- Подход не конфликтует с архитектурой: блокировка — своя таблица (не `leases`,
  решение Оператора), лимит пульта — тем же `parallel_limit.busy_other_tasks`,
  `runner.py`/`config.py`/`parallel_limit.py` не тронуты (сверено по diff --stat).
- «Влияние на систему» = diff: 7 модулей из `zones` SPEC + новый тест; карта
  регенерирована; откат — revert, таблицы безвредны.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `artel._launch_epic_supervisor` — предпроверка живой блокировки с pid в отказе; окончательный захват — `auto._take_supervisor_lock` под `BEGIN IMMEDIATE` своим `os.getpid()`, проигравший гонку выходит с записью. |
| 2 | OK | `schema.EPIC_SUPERVISION_DDL` (`epic_supervisors` с `session_id`), в `SCHEMA` и `migrate`; живость — `lease.process_alive` (хост, `_pid_alive`, `process_start_time <= started_at`, `None` → мёртв); мёртвая снимается с записью (`drop_dead_supervisor_lock`, `target` = проект). |
| 3 | OK | `epics.cmd_parallel`: `int`, `<=0` и неразборное — отказ до записи; колонка `epics.parallel` + `add_column`; умолчание `EPIC_DEFAULT_PARALLEL = 1`. |
| 4 | OK | `auto._operator_actions`: сверил источники записей — `state -> …` (set_state актором `operator` в fsm/budget), «ANSWER создан…» (answer.py:465–474, 562 zones-extend), «бюджет изменён» (budget.py:576), `AMEND_ACTION` (amend.py:1124), `CI_RERUN_ACTION` (ci_rerun.py:185), `pause`/`pause --now…` (pause.py:90, 218–265), `resume` (pause.py:115 — пишется только при снятии паузы). Записи цикла `auto` («auto старт», «auto остановлен», «цикл оборван») под перечень не попадают. |
| 5 | OK | `epics.cmd_retry`: эпик — `_existing`, задача — `store.get_task` (sys.exit на несуществующую), чужая — отказ без записи. |
| 6 | OK | `_epic_view` + `_child_holds`: гейты/escalated, чужой lease, `start_after` и конверт только для неначатых; удержание после «auto остановлен» в рабочем состоянии / «цикл оборван» / выхода без записи (помечается один раз); отказ глобального лимита (литерал runner.py:229) — не остановка. |
| 7 | OK | Живость дочерних — `epic_children` + `process_alive`; места `min(parallel − живые, MAX_PARALLEL_TASKS − живые − прочие lease)`, lease собственных живых дочерних из «прочих» исключены. |
| 8 | OK | `approve`/`reject` надзор не зовёт; задача на гейте — `_WAITING`, держит надзор. |
| 9 | OK | `artel._epic_observation` — (а)/(б)/(в), чужая сессия и неактивное — отказ до блокировки; неокончательные задачи — в набор до спавна; перед каждым дочерним — `add_observation_tasks` (re-enable после `stop`); отказ `_launch_observation` → `_end_supervision`. |
| 10 | OK | `watch._observation_events`: записи автора `EPIC_SUPERVISOR_ACTOR` по эпикам задач набора без фильтра классов, алерты с `target` = id эпика. |
| 11 | OK | `epics.cmd_stop`: SIGTERM надзору → ожидание снятия блокировки (`EPIC_STOP_WAIT_SEC`) → SIGTERM живым из `epic_children`; мёртвая — снятие без сигнала; `auto` Оператора в `epic_children` нет. |
| 12 | OK | `view.live` — есть задача не в `_BLOCKED`; `can_finish` протягивает блокировку по цепочке `start_after`. |
| 13 | OK | `_end_supervision` — запись + `raise_attention_alert(conn, epic_id, …)` (target = id эпика). |
| 14 | OK | Сверка в PLAN, расхождений не заявлено; использованы функции Э2а. |
| 15 | OK | Существующие тесты не тронуты. |

## Замечания

Blocker/major не найдено. Проверенные и снятые подозрения:
- Остановка `auto` на занятой зоне: `config.AUTO_WAIT_ZONE_DEFAULT = True` — дочерний ждёт зону сам, удержания «не на гейте» нет (auto.py:979–988).
- Формат детали «auto остановлен» — `f"{state}: {reason}"` (auto.py:612–613), разбор `split(":", 1)[0]` в `_child_holds` ему соответствует.
- `busy_other_tasks` отбрасывает lease мёртвого pid на этом хосте (parallel_limit.py:33) — AC-18б/AC-33 «pid не жив» не держат место чужим lease.
- `_migrate_epics` не пересоздаёт `epics`, `add_column` после него колонку не теряет.
- `epic` под ролью закрыт белым списком (`_ROLE_ALLOWED_*`), `auto --epic … --attach` — отдельным условием.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт

approved.

## Проверено исполнением

- `timeout 500 python3 -m pytest tests/test_epic_supervisor_units.py tests/test_01m5tbf7jrz6fgrr4k53kpajds_epic_supervisor.py -p no:cacheprovider -q` — 49 passed за 6.05 с.
- `artel.py plank-run 01M5TBF7JRZ6FGRR4K53KPAJDS` — отказ «планки нет: в refs/artifacts нет test_*.py», pytest не запускался; долгоживущий файл задачи — в `tests/` и прогнан выше.
- grep-сверки источников записей перечня требования 4 (fsm/answer/budget/amend/ci_rerun/pause), `auto_stop` (формат детали), `parallel_limit.busy_other_tasks`, `config.AUTO_WAIT_ZONE_DEFAULT`, `_role_allowed_command`.
- Временную мутацию (`_GLOBAL_LIMIT_REFUSAL_ACTION` выключен → AC-32) запустить не удалось: правка кода через `sed` потребовала подтверждения, в шаге его не дать. Заявки долгоживущего файла сверены чтением, сторож мутацией не проверен.
- CI коммита 71c49622 — зелёный (16 проверок, из пакета).

## Предложения системе

- `auto._GLOBAL_LIMIT_REFUSAL_ACTION` повторяет литерал `runner.py:229`, и долгоживущий тест задачи пишет его своей константой — переименование записи в `runner` сломает надзор (отказ лимита станет «остановкой не на гейте») при зелёных тестах. Нужна общая константа в `runner`/`refusal_classes` (разработчик предлагает то же).
- После `epic stop` и нового `auto --epic` задачи, чьи дочерние остановил `epic stop`, ждут `epic retry` по одной (SPEC так и требует: остановка `stop` — «не на гейте»). Стоит решить на уровне ADR-0028, считать ли перезапуск надзора действием Оператора для этих задач.
