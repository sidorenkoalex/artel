---
task: 01M2CN465WEDCF6D77V37FJ82E
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Эскалация не по существу: краснота планки после подтяжки main — дефект
самой планки, не кода. Тест AC-4 (test_ac4_invariants_diff_attachment.py)
читал tasks/<id>/PLAN.md с диска, а пульт при прогоне на выходе in_dev
материализует из артефактной ветки только acceptance_tests/ — PLAN.md на
диске нет, первый assert падал. Оператор поправил планку командой
amend-tests: текст PLAN.md берётся из артефактной ветки (gitcmd.show), диск —
запасной источник; проверки самого критерия (diff-блок, git apply --check
на чистом main) не менялись. Продолжай с in_dev: код ветки (WORKTREES и
BACKUP_MARKER в PATCHED_ATTRS, регенерированная карта) и PLAN.md с
приложенным диффом остаются; ничего переделывать не нужно — цикл сам
перепроверит планку на выходе. Приложенный дифф tests/test_invariants.py
Оператор применит отдельным коммитом в main до мержа.
