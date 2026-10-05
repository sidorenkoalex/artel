---
task: 01M44EP0D47F498TEE08MNGBYT
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Порядок мержей по зависимостям задач: поле merge_after

## Фаза A — план
- Таблица покрытия полна: требования 1–7 привязаны к шагам 1–3. Требование 3 (эскалация роли) закрыто приложением к `skills/escalation-rules.md`, без кода, как и требует SPEC.
- Шаги размером в MR. Подход — один модуль `orchestrator/merge_after.py` плюс точки вызова в существующих узлах — не конфликтует с архитектурой. SQL вынесен в `store.py` (`task_state`, `task_id_matches`), инвариант `SqlOnlyInStoreTest` соблюдён.
- «Влияние на систему» сходится с диффом: 11 файлов, все в зонах SPEC (`orchestrator/`, `scripts/guard.py`, `tests/`). Защищённые пути не тронуты, тесты в `tests/` не удалены и не изменены — добавлен только `tests/test_merge_after.py`. Путь отката описан.
- Приложение (требование 7): `git apply --check -v -` на диффе, извлечённом из PLAN.md, проходит по всем четырём файлам.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `guard.spec_merge_after_errors` вызывается из `_content_errors` для `type: spec` любой версии и только при наличии поля. Форма проверяется через `idgen.is_task_id_form`, повтор и самоссылка — по полю `task:`. `SUPPORTED_SCHEMA_VERSION` не тронут (5). |
| 2 | OK | `fsm._approve_spec_gate` вызывает `merge_after.spec_gate_value` сразу после сверки путей тем же мягким путём (журнал «approve отклонён», `return`) до `update_task`. Значение пишется тем же `update_task`, что `zones`, полными id в порядке SPEC. Колонка есть и в DDL, и в `add_column`. Проверки (а)–(д) — в `merge_after.check`; цикл ищется обходом в глубину по графу всех задач с новым значением. |
| 3 | OK | PLAN: `apply_plan` вызывается сразу после `_apply_plan_budget`. Без поля — молча; совпадение после разрешения — молча; без обоснования или при негодном значении — «merge_after из PLAN отклонён», переход продолжается. Мандат: маркер добавлен в `MANDATE_MARKERS`, проверка по БД стоит в `mandate.refusals` до `_commit_answer`. `merge_gate` принят с рубежом `in_role_environment`, файл без строки там отказывается. Запись «было → стало (канал: …)» делает `rewrite`. |
| 4 | OK | `merge_gate_refuses` стоит в `fsm._approve_merge_gate` до `_cmd_approve_merge_gate_cycle`, то есть до мьютекса и очереди. Отказ по убитой зависимости и отказ по незавершённой — разные действия журнала с разными текстами. Другого пути `merge_gate -> done`, кроме `fsm.cmd_approve`, нет: в `auto.py` и `fsm_autogate.py` его нет, проверено grep. |
| 5 | OK | `status_suffix` — последняя добавка строки, только в `acceptance`/`merge_gate`, строится из БД на каждый вызов. `show_line` выводит все зависимости и не выводится при пустом поле. |
| 6 | OK | В карте есть «Назначение» модуля `orchestrator/merge_after.py` с `merge_after`. Регенерация `scripts/codebase_map.py` расходится с закоммиченной картой только строкой `built_at_sha`. |
| 7 | OK | Приложение на четыре защищённых файла применяется (`git apply --check`). |

## Замечания
Блокирующих замечаний и замечаний уровня major нет. Ниже — наблюдения уровня вкуса; в реестр они не заведены, исправлять их не требуется:
- `orchestrator/merge_after.py::rewrite` пишет в журнал «— → —», если строка `Зависимости мержа: нет` пришла при уже пустой колонке. Это шумная, но правдивая запись.
- Докстринг `orchestrator/answer.py::_has_mandate_lines` по-прежнему говорит «мандата зон или тестов», хотя функция знает и третий маркер.
- `tests/test_merge_after.py::MigrationTest` глотает `sqlite3.Error` от `migrate`. Мутацию из заявки тест всё равно ловит, потому что ассерт идёт по `table_columns`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: в итерации 1 замечаний уровня blocker или major не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m44ep0d47f498tee08mngbyt_*.py tests/test_merge_after.py tests/test_answer_mandate.py tests/test_answer.py tests/test_task_id_prefix_regression.py tests/test_store_schema_migration_parity.py tests/test_guard_schema.py tests/test_multitarget.py tests/test_fsm_spec_gate_reject.py tests/test_catalog_status_log.py` — 216 passed, 74 subtests passed, 54.6 с.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M44EP0D47F498TEE08MNGBYT` — 2 passed, код выхода pytest 0.
- Временная мутация `merge_after.merge_gate_refuses`: `MISSING_STATE` убран из перечня «мёртвых» состояний. `tests/test_merge_after.py` покраснел ровно на `test_dependency_missing_from_db_refuses_with_answer_channel` (1 failed, 8 passed). Код возвращён, `git status` чистый.
- `python3 scripts/codebase_map.py` и `git diff -- docs/codebase-map.md` — расходится только `built_at_sha`, содержимое свежее. Карта возвращена через `git checkout`.
- Извлечённый из PLAN.md дифф приложения прогнан через `git apply --check -v -` — все 4 файла проходят проверку.
- `grep` по `orchestrator/` — `_cmd_approve_merge_gate_cycle` вызывается только из `fsm._approve_merge_gate`, обходного пути мержа нет.

## Предложения системе
- Песочница Bash шага ревью не даёт сделать временную мутацию одной командой (`cp` и heredoc требуют подтверждения), и приходится править файл через Edit туда и обратно. Пригодилась бы команда пульта `mutate-check <id> <файл> <старое> <новое> <тесты>`, которая вносит мутацию, гоняет тесты и возвращает код сама.
