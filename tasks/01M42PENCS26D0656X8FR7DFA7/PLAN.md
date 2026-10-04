---
task: 01M42PENCS26D0656X8FR7DFA7
type: plan
author_role: developer
status: draft
schema_version: 5
budget_usd: 100
---

# PLAN: ADR-0021, этап 2 — клон и рабочие копии задач в области проекта

## Подход
Черновик (шаг в работе). Центральный узел — `orchestrator/workspace.py`:
клон проекта `.artel/projects/<имя>/repo` (заводится по `url` записи
`targets.yaml`, `core.hooksPath` = `<config.ROOT>/scripts/git-hooks`) и
рабочая копия задачи `.artel/projects/<имя>/worktrees/<id>/`.
`repo_context.resolve` отдаёт клон для любого проекта, включая артель;
все вызовы `gitcmd` по задаче получают репозиторий проекта явно.

Расхождение с оценкой SPEC ($50): сигналы SPEC насчитали 57 модулей с
`config.ROOT`; детектор долгоживущего теста нашёл 124 вызова `gitcmd`
без репозитория в ~40 модулях, плюс правка существующих тестов под новое
место рабочей копии. Потолок поднят до $100 (ROLE_BUDGET_CAP).

## Шаги
1. Узел области проекта (workspace/repo_context/artifact_branch).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |

## Влияние на систему
Черновик.
