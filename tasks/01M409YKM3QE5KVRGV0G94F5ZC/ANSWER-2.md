---
task: 01M409YKM3QE5KVRGV0G94F5ZC
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

---
task: 01M409YKM3QE5KVRGV0G94F5ZC
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

1. **Мандат на замену утверждений — вариант (а).** Основание: тесты
   утверждали прежнее устройство (документы в рабочей копии кода),
   главное утверждение методов сохранено, замена прямо требуется
   ADR-0021.

Ослабление тестов разрешено: tests/test_timeout_checkpoint.py::CommitAbnormalCheckpointTest::test_materialized_spec_is_absent_from_the_code_branch_after_abnormal_end, tests/test_timeout_checkpoint.py::CommitPauseNowCheckpointTest::test_materialized_spec_is_absent_from_the_code_branch_after_pause_now, tests/test_timeout_checkpoint.py::RoleCwdMaterializationSurvivesTimeoutCheckpointTest::test_materialized_spec_is_absent_from_the_code_branch_after_timeout, tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package

2. **`codex exec --add-dir` — вариант (а).** Проверка Оператора на
   установленной codex-cli 0.157.1 принимается; других версий на машине
   нет. Подъём `min_cli_version` — вне задачи, отдельным решением
   Оператора.

3. **Правило HOME роли — вариант (б), только один файл.** Зоны задачи
   расширяются на `docs/reference/role-home/claude/CLAUDE.md`:
   developer заменяет правило «пиши `tasks/<id>/…` относительным путём»
   на запись документов задачи по пути каталога документов из миссии
   шага (код — в рабочей копии, документы — в каталоге документов,
   открытом `--add-dir`). Прочие файлы `docs/reference/role-home/` не
   трогать. Копию в `.artel/home/.claude/` Оператор обновит руками
   после мержа (`docs/reference/role-home.md`).

Расширение зон разрешено: docs/reference/role-home/claude/CLAUDE.md
