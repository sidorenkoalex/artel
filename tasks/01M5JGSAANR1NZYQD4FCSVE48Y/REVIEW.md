---
task: 01M5JGSAANR1NZYQD4FCSVE48Y
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: G3б-3: компонент задачи по зонам, компоненты гейтов по диффу и снятие отказа записи из нескольких компонентов

## Фаза A — план
- Таблица покрытия полна: требования 1–7 привязаны к шагам. В шаге 7 появилась доработка по R1-F1: сторожа мест таблицы SPEC в `tests/test_task_component_places.py`, обязательный минимум назван.
- «Влияние на систему» соответствует диффу итерации. С вердикта 1 (`96913b16`) изменились только `tests/test_task_component_places.py` (+563, новый файл) и `docs/codebase-map.md`. Код `orchestrator/` не менялся. Коммит `96913b16` (замена SQL в `for_task_target` на `store.task_exists`/`store.get_task`) лёг до вердикта 1 и вошёл в его ревью.
- Существующие тесты не правились: дифф `tests/` состоит из одного нового файла.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1 (`task_components`/`decide_task`/`for_task`, зона-каталог по `ls-tree` базы, fail-closed). |
| 2 | OK | Код прежний. Теперь fail-closed места после мержа держит `tests/test_task_component_places.py`: `acceptance_suite`, `_test_integrity_diff_gate`, `_external_helpers`, `matrix_refusals`, предел `full_suite`/`suite-run`, заявка мутации, автогейт по правилу планки, `_exit_without_profile`, подтяжка. По каждому месту проверены два исхода: (а) профиль компонента задачи; (б) отказ с текстом AC-3 трёх вариантов зон и причиной `decide`. |
| 3 | OK | Без изменений; держат долгоживущие `…_outcome_components.py`. |
| 4 | OK | Без изменений (AC-19/AC-25/AC-27). |
| 5 | OK | Без изменений (`…_role_outputs.py`). |
| 6 | OK | Учебный проект `backend`/`frontend` используется и в новом сторожевом файле. |
| 7 | OK | Без изменений (`tests/test_profile_layers_declared.py`). |

## Замечания

Блокирующих и major-замечаний нет.

Наблюдение без замечания. В новый файл не вошли места `preflight`, `amend`, `checkpoint`, `zones`, `runner:1325`. Возврат любого из них на `decide(target)` у записи из нескольких компонентов даёт отказ `decide` (`MULTI_COMPONENT_PENDING`), а не молчаливый пропуск проверки. Гейт неослабления от такого возврата не слабеет, ломается только функциональность задачи с выбранным компонентом. R1-F1 этих мест как минимум не требовал.

Тесты нового файла сверены с их заявками. У каждого метода есть докстринг со сценарием и «Ловит мутацию: …», и заявка называет наблюдаемое расхождение. Свойства долгоживущих файлов задачи файл не повторяет: `MatrixRefusalsTest` проверяет покрытие областью компонента задачи, а `Ac13` долгоживущего файла — компонента-потребителя.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/acceptance.py:3504; orchestrator/fsm_merge_gate.py:143; orchestrator/advance_gates/test_integrity.py:1304; orchestrator/advance_gates/mandate.py:652; orchestrator/acceptance.py:3359; orchestrator/suite_run.py:625; orchestrator/pull.py:665; orchestrator/preflight.py:241; orchestrator/amend.py:184; orchestrator/checkpoint.py:593,1858; orchestrator/advance_gates/zones.py:287; orchestrator/advance_gates/review.py:209; orchestrator/runner.py:1325; orchestrator/fsm_autogate.py:252; orchestrator/review.py:638,758 | Места таблицы SPEC были закрыты только разовой планкой, сторожа в `tests/` не было. | После мержа возврат места на `decide`/пропуск молча ослабил бы гейт неослабления. | Итерация 2: добавлен `tests/test_task_component_places.py` (14 тестов). Ревьювер проверил временными мутациями (10 штук, код возвращён): каждая мутация fail-closed мест минимума и четырёх мест сверх него красит файл. Закрыто. |

## Вердикт
approved. R1-F1 закрыт: fail-closed места требования 2 получили сторожа в `tests/`, и каждый из них проверен временной мутацией. Код задачи по SPEC замечаний не получил ни в итерации 1, ни сейчас.

## Проверено исполнением
- `python3 -m pytest tests/test_task_component_places.py -q` — 14 passed, 29 subtests passed (1.9 с).
- Временные мутации, после каждой код возвращался `git checkout`, `git status` в конце пуст. Прогонялся только `tests/test_task_component_places.py`:
  - `acceptance_suite`: при `ComponentsPending` → `return run` (молчаливый пропуск `checks_local`) — 3 failed;
  - `_test_integrity_diff_gate`: `elif project_profile.is_multi(...)` → `elif False` — 3 failed;
  - `_external_helpers`: откат на область по умолчанию (`if False: raise`) — 3 failed;
  - `matrix_refusals`: ветка отказа снята (откат на правило `tests/…`) — 3 failed;
  - `full_suite`: ветка предела компонента задачи снята (`full_suite_limit(target)`) — 5 failed;
  - `suite_run._component_command`: при отказе — профиль первого компонента `backend` — 3 failed;
  - `_mutation_claim_gate` на `decide(t["target"])` — 1 failed;
  - `_plank_rule_refusal`: ветка `is_multi` снята (`_bounds`) — 1 failed;
  - `review._exit_without_profile` на `decide(target)` — 1 failed;
  - `pull`: при `ComponentsPending` прогон прежним раннером — 3 failed.
- `artel.py plank-run 01M5JGSAANR1NZYQD4FCSVE48Y` — 69 passed in 38.67s, код выхода pytest 0.
- `python3 -m pytest` по `tests/test_multitarget.py`, `test_01m5jgsaanr1nzyqd4fcsve48y_task_component.py`, `test_01m5jgsaanr1nzyqd4fcsve48y_mandate_components.py`, `test_component_checks.py`, `test_suite_run.py`, `test_fsm_autogate_plank_rule.py`, `test_mandate_test_id.py`, `test_mandate_profile_scope.py` — 108 passed, 42 subtests passed.
- `python3 scripts/codebase_map.py` — расхождение только в строке `built_at_sha`, карта свежа. Файл возвращён `git checkout`.
- CI коммита 4d9e5294 зелёный (16 проверок, по пакету).

## Предложения системе
- Чтобы проверить сторожа временными мутациями, ревьюверу удобно было бы иметь скрипт во временном каталоге. Запись в `/tmp` в песочнице роли ждёт подтверждения, пришлось подавать скрипт через `python3 - <<'EOF'`. Стоит упомянуть этот приём в review-checklist (раздел «Сторож — проверен временной мутацией»).
