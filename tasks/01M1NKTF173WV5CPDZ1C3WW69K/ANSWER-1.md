---
task: 01M1NKTF173WV5CPDZ1C3WW69K
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Возврат из эскалации «конфликт подтяжки main». Подтяжку origin/main
в ветку задачи выполнить самостоятельно: конфликт смысловой.
Смерженная сегодня задача 01M1NBWTSXEJB24PXR417YF1VA (WIP-чекпоинт
по зоне роли) уже реализовала исключение `tasks/<id>/` из
WIP-коммита параметром `exclude` функции `_commit_worktree_change`
и мандатами ролей (developer — код, остальные — откат вне мандата,
`_discard_out_of_mandate_changes`). Принять эту реализацию из main
как базовую, убрать дубль с параметром `task_id` и три его вызова,
сохранить конфликт-гвард автокоммита (`materialized_artifact_sha`,
AC-6/AC-7) и лок удаления `acceptance_tests/` до фиксации
(AC-13..AC-15). В `store.py` — обе миграции колонок. В
`tests/test_timeout_checkpoint.py` — взять версию main и оставить
тест `test_dirty_task_dir_alone_is_not_committed_to_the_code_branch`,
если он проходит на реализации main. Карту перегенерировать. Планка и
полный `tests/` до итоговых строк в PLAN. Бюджет поднят до 60.
