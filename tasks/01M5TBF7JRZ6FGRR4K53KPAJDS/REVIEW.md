---
task: 01M5TBF7JRZ6FGRR4K53KPAJDS
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Эпики Э2б — надзирающий процесс эпика `auto --epic`

## Фаза A: план

- Таблица покрытия полна (требования 1–15), шаги — размер MR, подход в рамках
  архитектуры (своя таблица блокировки, лимит пульта через
  `parallel_limit.busy_other_tasks`, `runner.py`/`config.py` не тронуты).
- PLAN шага 5 описывает добавленный `PriorGenerationChildTest` — совпадает с diff.

## Что изменилось с итерации 1

Итерация 1 (approved, коммит 71c49622) учтена пультом; эта итерация — повторный
прогон вердикта. `git log 71c496229..HEAD`:
- `81e090f8f` — правка Оператора теста задачи 01M5T18K1YFBYA7MM1BBRV869A
  (`test_ac4`, фикстура), пришла подтяжкой main (`d2522e20a`); коммит есть в
  `origin/main`, разработчиком не делалась — вне зоны ревью этой задачи.
- `5d1ef54ac` — `tests/test_epic_supervisor_units.py`: новый
  `PriorGenerationChildTest` (+64 строки) и регенерация карты. Код
  `orchestrator/` не менялся.

Примечание к пакету: diff пакета построен от устаревшего локального `main` и
несёт файлы смерженных Э1/Э2а/Э3 (`board.py`, `catalog.py`, `fsm.py`, …).
Фактический diff задачи — `git diff origin/main...HEAD`: `artel.py`, `auto.py`,
`epics.py`, `lease.py`, `schema.py`, `store.py`, `watch.py`, долгоживущий файл
задачи, `tests/test_epic_supervisor_units.py`, карта — всё в `zones` SPEC.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Предпроверка живой блокировки с pid в отказе (`artel._launch_epic_supervisor`); окончательный захват — `auto._take_supervisor_lock` под `BEGIN IMMEDIATE`. |
| 2 | OK | `epic_supervisors` с `session_id`; живость — `lease.process_alive` (хост, pid, `process_start_time <= started_at`, `None` → мёртв); мёртвая снимается с записью. |
| 3 | OK | `epics.cmd_parallel`: только целое > 0; колонка `epics.parallel`, умолчание 1. |
| 4 | OK | `auto._operator_actions` — перечень записей команд Оператора; записи цикла `auto` и запуска дочернего не входят. |
| 5 | OK | `epics.cmd_retry`: задача вне эпика — отказ без записи. |
| 6 | OK | `_epic_view` + `_child_holds`; отказ глобального лимита — не остановка. |
| 7 | OK | Живость дочерних по pid (`epic_children`), места `min(parallel − живые, MAX − живые − прочие lease)`; дочерние прежнего поколения учитываются (новый unit-тест). |
| 8 | OK | `approve`/`reject` надзор не зовёт; гейт — `_WAITING`. |
| 9 | OK | `_epic_observation` (а)/(б)/(в), отказ до блокировки; неокончательные задачи — в набор до спавна; отказ `_launch_observation` → завершение с алертом. |
| 10 | OK | `watch`: записи `EPIC_SUPERVISOR_ACTOR` и алерты с `target` = id эпика. |
| 11 | OK | `epic stop`: надзор → ожидание снятия блокировки → SIGTERM живым дочерним; мёртвая — без сигнала. |
| 12 | OK | `view.live`, протягивание блокировки по `start_after`. |
| 13 | OK | `_end_supervision` — запись + `raise_attention_alert`. |
| 14 | OK | Сверка Э2а в PLAN. |
| 15 | OK | Существующие тесты `tests/` разработчиком не правились (правка `test_ac4` — Оператора, из main). |

## Замечания

Blocker/major не найдено.
- Новый `PriorGenerationChildTest`: докстринг описывает сценарий и свойство,
  заявка «отбор дочерних по `started_at` текущей блокировки» правдоподобна и
  наблюдаема (`view.running`/`view.free` меняются). Временной мутацией не
  подтверждён — правка кода в шаге требует подтверждения (см. ниже).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет (итерация 1 записей не заводила).

## Вердикт

approved.

## Проверено исполнением

- `timeout 500 python3 -m pytest tests/test_epic_supervisor_units.py tests/test_01m5tbf7jrz6fgrr4k53kpajds_epic_supervisor.py -p no:cacheprovider -q` — 50 passed за 9.75 с.
- `timeout 300 python3 -m pytest tests/test_detached_cycle.py tests/test_store_schema_migration_parity.py -p no:cacheprovider -q` — 29 passed (разрез `_launch_detached`, паритет схемы).
- `git log/diff 71c496229..HEAD`, `git branch -a --contains 81e090f8f` (коммит в `origin/main`), `git diff --stat origin/main...HEAD` — состав изменений задачи.
- Временная мутация `auto._epic_view` (отбор дочерних по `started_at` блокировки) для `PriorGenerationChildTest` — не запущена: правка `orchestrator/auto.py` потребовала подтверждения, в шаге его не дать; рабочее дерево не изменено (`git status` чистый).
- CI коммита 5d1ef54a — зелёный (16 проверок, из пакета).

## Предложения системе

- Ревью-пакет строит diff от локального `main`, отстающего от `origin/main`: в
  пакет попали файлы трёх уже смерженных задач (~6 тыс. строк лишнего). Базой
  diff пакета стоит брать `origin/main` (или `merge-base` с ним).
- Временная мутация из скила review-checklist в шаге ревью недоступна: любая
  запись в `orchestrator/` ждёт подтверждения. Либо разрешить её в курируемом
  слое роли, либо убрать из скила обязательность приёма.
