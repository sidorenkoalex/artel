---
task: 01M3SE87R3M7HGWX8HG1ANAKR0
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Признак процесса шага роли для всех провайдеров

## Подход

Единый `runner.in_role_environment(env=None)` распознаёт непустой `ARTEL_ROLE` для любого провайдера и сохраняет прежнюю пару `HOME`/`CLAUDE_CONFIG_DIR` как альтернативу. Оба офлайн-смока проверяют собранное окружение. По мандату Оператора `cmd_note` отказывает шагу роли до разбора аргументов и любых побочных действий. Обычные тесты операторских команд изолируют свой процесс от унаследованного `ARTEL_ROLE`, а тесты отказов задают маркер явно; корневой сторож сбора pytest не меняется.

## Шаги

1. Расширить `orchestrator/runner.py::in_role_environment`, добавить проверку результата в `orchestrator/doctor/isolation.py` и описать признак и паритет в `docs/stack.md`.
2. Добавить в `orchestrator/notes.py::cmd_note` ранний отказ роли для всех форм команды по `ANSWER-1.md`.
3. Изолировать обычные тесты команд от ambient `ARTEL_ROLE` в `tests/`, добавить поведенческие тесты только для свойств, отсутствующих в залоченном долгоживущем файле; проверить заявленные мутации новых сторожей.
4. Прогнать залоченную планку задачи и тесты затронутых модулей под маркером роли; регенерировать `docs/codebase-map.md` и проверить `scripts/guard.py`. Кодовые изменения перенесёт штатный автокоммит пульта по решению Оператора.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 3 |
| 2 | 1, 2, 3 |
| 3 | 1, 3 |
| 4 | 1 |
| 5 | 2, 3, 4 |
| 6 | 3, 4 |

## Влияние на систему

Рубеж отказа расширяется на шаги codex и команду `note` у всех провайдеров. Существующая альтернатива для claude и логика других потребителей сохраняются. Сторож `conftest.py` продолжит читать ambient `ARTEL_ROLE` при сборе. Изоляция обычных тестов действует только внутри тестовых сценариев, не в коде пульта. Изменение откатывается revert кодовых коммитов этой задачи.

## Расширение зон

Пути: orchestrator/notes.py

Мандат — `tasks/01M3SE87R3M7HGWX8HG1ANAKR0/ANSWER-1.md`, строка «Расширение зон разрешено: orchestrator/notes.py». Файл нужен для раннего отказа `note`, которого не было в исходном списке зон SPEC; тест `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py::RoleCommandRefusalTest` проверяет этот отказ.

## Риски

Новый признак может покраснить тесты операторских команд, если они наследуют маркер pytest. Проверить целевые модули при `ARTEL_ROLE=test_author`, включая `ZonesExtendCommandTest` и `CanaryPoolDriftCheckTest`.

## Проверка

- `ARTEL_ROLE=test_author python3 -m pytest tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py tests/test_notes.py tests/test_notes_apply.py tests/test_notes_row_format.py -q -p no:cacheprovider -p timeout -o timeout=120`: 76 passed, 34 subtests passed.
- `ARTEL_ROLE=test_author python3 -m pytest tasks/01M3SE87R3M7HGWX8HG1ANAKR0/acceptance_tests/test_documentation_and_ambient_suite.py -q -p no:cacheprovider -p timeout -o timeout=120`: 2 passed; второй сценарий запускает семь модулей из AC-6 с тем же маркером.
- `ARTEL_ROLE=test_author python3 -m pytest tests/test_doc_commit.py tests/test_doc_commit_suite_gate.py tests/test_doctor.py tests/test_stack_parity_table.py tests/test_stack_codex_section.py tests/test_runner_role_environment.py tests/test_provider_scoped_step_env.py tests/test_providers_codex.py -q -p no:cacheprovider -p timeout -o timeout=120`: 250 passed, 101 subtests passed.
- Временная мутация `if env is None` → `if not env` из прошлого шага покраснила тест признака. Временная мутация отключения нового отказа `cmd_note` покраснила все пять вариантов нового теста; исходный код восстановлен.
- `python3 scripts/codebase_map.py` выполнился; `git diff --check` и `python3 scripts/guard.py tasks/01M3SE87R3M7HGWX8HG1ANAKR0/PLAN.md` — чисто.

## Предложения системе

- Песочница шага не даёт разработчику записать gitdir worktree для обязательного `git add`/commit. `ANSWER-1.md` предписал завершить код штатным автокоммитом пульта без обхода песочницы.
