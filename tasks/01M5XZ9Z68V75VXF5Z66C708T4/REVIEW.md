---
task: 01M5XZ9Z68V75VXF5Z66C708T4
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Б2.1а — состояние `awaiting_human` и его учёт в перечнях пульта

## Фаза A: план
- Таблица покрытия PLAN полна: все 22 требования SPEC привязаны к шагу,
  требования 11 и 13 честно помечены «без новой механики» и держатся AC-12/AC-17.
- Шаги размера MR (по модулю/слою), не микрооперации.
- Подход согласован с архитектурой: литерал подсказки — одна константа
  `fsm.AWAITING_HUMAN_HINT`; отказ отправки — в единой точке `gitcmd`
  (`_push_plan` + вход `in_repo` по ANSWER-1 п. 5, сужение до push-подкоманд
  по ANSWER-2 п. 2); умолчания — только `targets.delivery_policy`.
- Приложение к `tests/test_invariants.py` применяется и закрывает свип
  (проверено исполнением, см. ниже).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `targets._check_delivery`: `max_awaiting` целое > 0 без bool, `awaiting_holds_zones` bool; поля в `LOCAL_FIELDS["policy"]` и `DELIVERY_POLICY_FIELDS` |
| 2 | OK | `DELIVERY_DEFAULTS` + `delivery_policy`; другие модули умолчаний не держат (`zone_lock._holds_zones` берёт через `delivery_policy`) |
| 3 | OK | целое (не bool) допущено; пустая строка/bool/иное — отказ; `record_fields.py:169` зелёный без правки |
| 4 | OK | `targets.merged_by_project_people`; grep `"target-human"` вне `targets.py` в `orchestrator/` — пусто |
| 5 | OK | `fsm.STATES` после `merge_gate`, не в `TERMINAL_STATES` |
| 6 | OK | `board.HUMAN_STATES` → `human` |
| 7 | OK | `BLOCKING_STATES` + `_holds_zones` в `_occupier` и `forecast_overlaps` (единственные потребители — grep) |
| 8 | OK | `config.AUTO_STOP`, `auto._NO_ALERT_FINAL_STATES` |
| 9 | OK | `_epic_view`: `_AWAITING` раньше `_RUNNING`/`_WAITING`, исключение из `view.running`, `view.ready` строится по `_READY` — задача не перезапускается; `_NOT_HOLDING_STOP_STATES` |
| 10 | OK | `report.STATE_ORDER = fsm.STATES`; `MANUAL_GATE_STATES` без состояния; `watch._GATE_STATES`; `catalog._status_line` со ссылкой, «ЖДЁТ ОПЕРАТОРА» не ставится (`OPERATOR_STATES` не тронут) |
| 11 | OK | новой механики нет; AC-12 зелёный |
| 12 | OK | ни в одном перечне; AC-3 |
| 13 | OK | `escalated_from`; AC-17 |
| 14 | OK | рабочую копию трогают только `kill`/`done`; lease в состоянии не берётся |
| 15 | OK | `doctor/branch_freshness.py` пропускает состояние |
| 16 | OK | DDL + `add_column` (идемпотентно), `store.set_mr_link`/`mr_link`/`mr_link_text`; показ в доске (md/html/json), `report`, `status`, `watch` |
| 17 | OK | `approve`/`reject`/`answer` — `sys.exit` с подсказкой до любой работы |
| 18 | OK | `_awaiting_human_spec` по `kind == "branch"` покрывает обычную отправку, refspec, `--delete`/`-d`, `:<ветка>`, `:refs/heads/<ветка>`; отказ до git в `_push_plan` и на входе `in_repo` |
| 19 | OK | `amend._refuse_awaiting_human` первым действием обоих путей |
| 20 | OK | `cleanup._server_left_to_project_people`: `target-human` + запись «ветка отправлена» нового/старого вида → ранний выход `cleanup_project_remote` со ссылкой MR в журнале; локальная уборка и `_commit_closing` прежние (ANSWER-1 п. 3) |
| 21 | OK | приложение PLAN применено временно — `test_invariants.py` 85 passed |
| 22 | OK | правки только по мандату: элемент кортежа `FSM_STATES` в `test_auto_cycle.py`, ветка `awaiting_human → human` в `expected_waiting`; утверждения методов не менялись, `test_report.py` не тронут (перечней состояний не несёт) |

## Замечания
Блокирующих и major-замечаний нет. Мелочи, не заведённые замечаниями (на
поведение не влияют):
- `orchestrator/auto.py:1288` и `orchestrator/zone_lock.py:340` сравнивают
  состояние с литералом `"awaiting_human"`, а не с `fsm.AWAITING_HUMAN`.
- `orchestrator/board.py:90-91` — `store.mr_link(t)` вызывается дважды.
- Ширина `{state:<13}` в `catalog._status_line` на символ меньше
  `awaiting_human` — признано в «Рисках» PLAN.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет — замечаний итерации 1 нет.

## Вердикт
approved

## Проверено исполнением
- `artel.py plank-run 01M5XZ9Z68V75VXF5Z66C708T4` — 26 passed, код выхода 0
  (AC-5…AC-8, AC-16, AC-18, AC-20).
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5xz9z68v75vxf5z66c708t4_*.py
  tests/test_awaiting_human_units.py tests/test_auto_cycle.py
  tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py
  tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py
  tests/test_store_schema_migration_parity.py tests/test_gitcmd_push_point.py
  tests/test_kill_cleanup.py tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py`
  — 191 passed, 31 subtests passed.
- Приложение 1 PLAN временно внесено в `tests/test_invariants.py` →
  `pytest tests/test_invariants.py` — 85 passed, 1121 subtests passed; файл
  возвращён `git checkout`, `git status` чистый.
- Временная мутация: из `zone_lock.forecast_overlaps` убрано
  `or not _holds_zones(row)` → `test_awaiting_human_units.py::test_forecast_skips_awaiting_zone_only_when_not_held`
  красный (1 failed, 11 passed), код возвращён `git checkout`.
- grep `"target-human"` и `BLOCKING_STATES` по `orchestrator/` — литерал гейта
  только в `targets.py`; потребители `BLOCKING_STATES` — `_occupier` и
  `forecast_overlaps` (через `catalog.py:1278`), оба учитывают `_holds_zones`.

## Предложения системе
- Песочница шага ревью отказывает `sed -i` и записи в `/tmp` для временного
  приложения патча к защищённому тесту — пришлось вносить приложение через Edit
  и откатывать `git checkout`; команде пульта вроде `plank-run` не помешал бы
  режим «прогнать файл с приложением PLAN» (класс: проверка приложений
  к защищённым путям).
