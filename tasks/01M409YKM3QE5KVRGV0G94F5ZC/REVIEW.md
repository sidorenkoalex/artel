---
task: 01M409YKM3QE5KVRGV0G94F5ZC
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: ADR-0021, этап 1 (б1) — документы вне рабочей копии кода и доступ ролей

## Фаза A: план
- Таблица покрытия полна (требования 1–7 → шаги 1–7). Новый раздел PLAN
  «Замечания ревью итерации 1 и их исполнение» описывает правки
  R1-F1..R1-F3, и они совпадают с инкрементальным diff 340a3ad1..ea3ccb09
  (`orchestrator/checkpoint.py`, `orchestrator/role_prompt.py`,
  `tests/test_docs_dir_layout.py`). Сверх заявленного в diff ничего нет.
- Защищённые пути в ветке не тронуты. Приложения 1–4 не менялись с
  итерации 1: тогда `git apply --check` давал rc=0, а с приложениями 1+2
  было 78 passed.
- Откат описан: revert merge-коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Выкладка в `.artel/projects/<проект>/tasks/<id>/`, автокоммит из каталога документов. После R1-F2 удаление или переименование ролью в каталоге документов не отменяется копией из рабочей копии кода (`checkpoint._merge_code_copy_docs:1015`). |
| 2 | OK | Без изменений с итерации 1: `--add-dir` у claude и у `codex exec`, cwd — рабочая копия кода. Долгоживущий файл задачи зелёный. Миссия больше не противоречит сама себе (R1-F3, `role_prompt.py:142-148`). |
| 3 | OK | `plank_in_code_copy`/`finally` во всех четырёх местах вызова. Теперь это сторожится в `tests/` на уровне гейтов (R1-F1). |
| 4 | OK | Без изменений: сверка фиксации усилена, лок и перечень сумм не ослаблены. |
| 5 | OK | `docs/stack.md` — без изменений с итерации 1. |
| 6 | OK | Приложения 1–4 — без изменений с итерации 1. |
| 7 | OK | Все четыре свойства имеют постоянных сторожей в `tests/`. Уборку планки гейтами держит `GatesDropPlankAfterRunTest`, заявки подтверждены мутацией (ниже). |

## Замечания
Новых замечаний blocker/major нет. Сверены изменённые утверждения
`tests/` против base: в этой итерации существующие методы не менялись
(в diff только добавленные методы и класс `tests/test_docs_dir_layout.py`).
Четыре метода из «Изменённых утверждений» покрыты мандатом ANSWER-2 п.1.

Наблюдение, не замечание. Если выкладка из ссылки на старте не
состоялась (git не ответил), каталог документов несёт только
`_place_harvested_docs`. В этом случае путь ссылки, записанный ролью
только в рабочую копию кода, `_merge_code_copy_docs` сочтёт удалённым.
Но это та же ветка деградации «git не ответил», в которой и коммит в
ссылку не состоится, поэтому предсказуемой поломки на штатном пути нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_docs_dir_layout.py:312-481 (`GatesDropPlankAfterRunTest`) | Уборку планки гейтами после прогона сторожила только разовая планка | Регресс уборки прошёл бы CI после мержа | Принято. Сторожа на уровне гейтов: `_acceptance_run_refuses` (зелёный/красный/исключение), `tests_writing` (пройден/отклонён/исключение), `_review_approved` внешнего target, `amend._check_code_head_long_lived`. Каждая заявка проверена временной мутацией, тесты красные (см. «Проверено исполнением») |
| R1-F2 | accepted | orchestrator/checkpoint.py:1009-1035 | `_merge_code_copy_docs` воскрешал путь, удалённый ролью в каталоге документов | Удаление или переименование планки молча отменялось | Принято. При наличии каталога документов путь ссылки, которого там нет, из рабочей копии кода не берётся; это пишется в журнал. Новые пути (прежнее правило HOME) по-прежнему переносятся. Сторож `test_plank_deleted_in_docs_dir_is_not_revived_from_code_copy` краснеет на мутации «условие снято» |
| R1-F3 | accepted | orchestrator/role_prompt.py:139-149 | Миссия запрещала запись вне рабочего каталога и тут же открывала каталог документов | Роль могла не записать артефакт | Принято. При `docs_dir` строка называет оба каталога, без него остаётся прежняя. `test_agent_prompt`, `test_role_prompt_test_author_mission` зелёные |

## Вердикт
approved: R1-F1..R1-F3 закрыты, новых blocker/major нет.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tasks/01M409YKM3QE5KVRGV0G94F5ZC/acceptance_tests tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py tests/test_docs_dir_layout.py tests/test_checkpoint_external_step_artifacts.py tests/test_step_autocommit.py tests/test_timeout_checkpoint.py tests/test_review_package.py tests/test_agent_prompt.py tests/test_role_prompt_test_author_mission.py tests/test_acceptance_tests_flow.py tests/test_amend.py tests/test_amend_long_lived.py tests/test_fsm_advance_tests_writing_dry_collect.py` — 382 passed, 30 subtests passed.
- Временные мутации. Каждый раз запускался только `tests/test_docs_dir_layout.py`, после прогона файл восстанавливался, итоговый `git diff` пуст:
  - M1: `checkpoint._merge_code_copy_docs`, условие `own is None and docs_dir_present and rel in known` → `False`. Красный `test_plank_deleted_in_docs_dir_is_not_revived_from_code_copy`.
  - M2: `advance_gates/acceptance._acceptance_run_body` (self-target), `cleanup.enter_context(plank_in_code_copy(...))` → `materialize_from_branch(...)`. Красные 3: `test_acceptance_run_drops_plank_on_green/red/exception`.
  - M3: `fsm_advance.tests_writing`, `finally: drop_from_code_copy` → `pass`. Красные 3 подтеста: пройден/отклонён/исключение.
  - M4: `fsm_advance._review_approved` внешнего target без `plank_in_code_copy`. Красные 2 подтеста.
  - M5: `amend._check_code_head_long_lived` с `materialize_from_branch` вместо `plank_in_code_copy`. Красные 2 подтеста.
- Чтение `orchestrator/checkpoint.py:905-1192`. Зачем: проверить формат `existing` (пути от корня ссылки, как ключи `files`/`stray_files`) и что удаление доходит до ссылки через `_step_artifact_deletion_candidates`. Расхождения нет.
- После прогонов в `.artel/projects/artel/tasks/` рабочей копии не осталось каталогов.

## Предложения системе
- Шаг ревью: однострочник мутаций через `python3 - <<EOF` с кавычками внутри отклоняется фильтром оболочки («brace with quote»). Временный скрипт в рабочем каталоге работает, но `rm` в оболочке роли нет, и удалять его приходится через `python3 -c os.remove`. Приём «временная мутация» из `skills/review-checklist.md` стоит снабдить готовым шаблоном.
