---
task: 01M5JPEHY8HY70R5T5AQ0EDSH1
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Зависимость merge_after с общей зоной держит старт последователя в любом незавершённом состоянии

## Фаза A — план
- Покрытие: все 5 требований есть в таблице PLAN; шаги (zone_lock / doctor / прогон+карта) — проверяемые единицы размера MR.
- Подход согласован с архитектурой: `_waiting_dependency` переведена на тот же обход `_ancestors`, что у `queue_order`, и то же правило пересечения `_shared_zone`/`_own_paths`; порядок «держатель → зависимость → очередь» в `_start_conflict` сохранён.
- Отклонение от узкого ограничения зон SPEC («в zone_lock.py — только `_waiting_dependency` и её вызовы…»): правка `_ancestors` (`orchestrator/zone_lock.py:799-813`). Заявлена в PLAN («Подход», абзац 2), нужна AC-2 (зависимость, которой нет в БД, не держит старт): `store.get_task` на отсутствующем id завершает процесс (`SystemExit`), и прежняя проверка `if dep_row is not None` была мёртвой. Для существующих задач поведение прежнее (`store.task_exists` → тот же `get_task`). Не замечание: это минимальная правка, без которой требование 1 («нет в БД — старт не держит») не выполнить, и она убирает падение `queue_order`.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `zone_lock.py:541-562`: `_ancestors` (транзитивно) → отсев отсутствующих/`done`/`killed`/чужого проекта → `_shared_zone` с `own`. `_start_conflict` (`:595-600`) проверяет `_occupier` раньше — «занята» главнее. `_reason` (`:617`) называет состояние. |
| 2 | OK | `_holds_queue` (`:578`) и `_start_conflict` зовут одну функцию; `queue_wait` (→ `status`, `doctor`) берёт тот же `_start_conflict`/`_holds_queue` без своих правок. Правило «эскалированная не-зависимость очередь не держит» не тронуто (`_queue_members` — только `in_dev`); тест AC-4 сценарий 2 зелёный. |
| 3 | OK | `hung_test_watchdog.py:310-321`: держатель из `blocking_conflict`, проверка `row["id"] in _ancestors(holder)` (транзитивно), прямой `answer` в `escalated/in_dev/review/merge_gate`, иначе с оговоркой «после перехода держателя в merge_gate: …»; `zone-release <ждущая>` всегда; уровень `warn`. |
| 4 | OK | `claim`/транзакция, `zone-release`, `queue_order`, `merge_gate`, `answer` не тронуты (diff — два файла). Существующие тесты не правились: `git diff 7824ab3c..HEAD --stat -- tests/` — только новый долгоживущий файл задачи; планка AC-8 зелёная. |
| 5 | OK | Долгоживущий `tests/test_01m5jpehy8hy70r5t5aq0edsh1_zone_dependency_start.py` покрывает AC-1…AC-7 и AC-9, песочница — `InitializedTmpRootTest`, без сети; заявки «Ловит мутацию» у каждого метода наблюдаемы (меняется исход `claim` или текст `doctor`/`status`). |

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved — 0 blocker/major. Требования 1–5 реализованы, существующие тесты не ослаблены, заявленные мутации ловятся (проверено временными мутациями).

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m5jpehy8hy70r5t5aq0edsh1_zone_dependency_start.py tests/test_zone_lock.py tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py tests/test_01m5fghnb29qa254fm07qr55ab_wait_minutes.py tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py tests/test_auto_cycle.py tests/test_catalog_status_log.py tests/test_zone_lock_forecast.py tests/test_checkpoint_zone_mandate.py` — 160 passed, 106 subtests passed (10.8 с).
- `artel.py plank-run 01M5JPEHY8HY70R5T5AQ0EDSH1` — 1 passed, код выхода 0 (AC-8, `Группа: разовый`, форма «Зелёный с рождения» с названным свойством — законна).
- Временные мутации (код возвращён `git checkout`, `git status` чист):
  1. `check_zone_waits`: `_ancestors(conn, holder_row)` → `_dependencies(holder_row)` (без транзитивности) и одновременно 2. `_FINISHED_STATES = ("done",)` (`killed` держит старт) — долгоживущий файл задачи: 3 failed — `test_ac2…[killed]`, `test_ac7_mutual_block_holder_in_answerable_state[merge_gate, транзитивно=True]`, `test_ac9…[killed-зависимость держит старт]`. Обе заявки подтверждены.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md | grep -v built_at_sha` — 0 содержательных строк, карта свежа (изменение откатано).

## Предложения системе
- Шаг ревью не может прогнать серию временных мутаций одной Bash-командой: составная команда (`sed -i` + pytest + `git checkout` подряд, либо shell-функция) упирается в запрос подтверждения, которого в шаге никто не даст. Приходится мутировать через Edit по одной. Адрес: `.artel/home/.claude/settings.json` (allow-правила) или штатная команда пульта «mutation-run <id> <патч>».
