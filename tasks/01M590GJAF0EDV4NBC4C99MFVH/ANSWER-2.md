---
task: 01M590GJAF0EDV4NBC4C99MFVH
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

# Ответ Оператора на вопросы автора тестов (G1б)

В1. **Вариант A.** В `orchestrator/project_profile.py` — публичная таблица `VITEST_VERSION_FLAGS`: «главная версия Vitest → {флаг кэша, принимает ли `--expect.requireAssertions`}». Разработчик заполняет её кандидатом для Vitest 4 (`--cacheDir`, `--expect.requireAssertions` — принимает) с пометкой «не подтверждено пробой»; проба этапа 2 правит значение. Подготовка `pult-vitest` идёт по версии из таблицы и отказывает для версии, которой в таблице нет. Планка: положительные сценарии — версия из таблицы (подменённый раннер отвечает ею на `--version` или она в `tools`), отказ — версия вне таблицы.

В2. **Вариант A** — форма JSON отчётчика пульта фиксируется как в вопросе: `{"tests": [{"file", "name", "state", "mode", "fails", "retry_count", "error_name", "timeout", "hook", "duration_ms"}]}`; `file` — путь от `workdir` (идентификатор теста пульт строит от корня репозитория).

В3. **Вариант A** — новое поле `acceptance.FullSuiteRun.tests` (кортеж записей: `id`, `outcome`, `failure`, `skip_reason`, `time`; у `pult-vitest` ещё `mode`, `fails`, `retries`); узел — `acceptance.full_suite(root, task_id, command=<профиль>)`.

В4. **Вариант A.**

В5. **Вариант A.**
