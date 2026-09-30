---
task: 01M3SE87R3M7HGWX8HG1ANAKR0
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Признак «процесс — шаг роли» для всех провайдеров

## Соответствие SPEC

Фаза A: покрытие требований в PLAN полное, шаги проверяемы и соразмерны MR. Расширение зоны `orchestrator/notes.py` авторизовано ANSWER-1.md и ANSWER-2.md; фактический diff соответствует заявленному влиянию и не ослабляет существующие проверки.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `in_role_environment(env=None)` принимает явное окружение, проверяет непустой `ARTEL_ROLE` и сохраняет legacy-пару Claude. |
| 2 | OK | Существующие потребители продолжают вызывать единый предикат; `note` получает ранний отказ согласно мандату Оператора. |
| 3 | Не реализовано полностью | Claude-smoke проверяет результат реального `role_env`, но codex-smoke самостоятельно дописывает маркер в реконструированную среду и потому не контролирует сборку этого маркера раннером. |
| 4 | OK | Документация описывает оба достаточных условия и таблица паритета содержит отказ команд для Claude и Codex. |
| 5 | OK | Долгоживущая планка и обычные тесты покрывают окружения обоих провайдеров, границу Оператора и отказы `answer`, `note`, восстановления пула. |
| 6 | OK | Затронутые сценарии зелёны при ambient `ARTEL_ROLE`; обычные операторские сценарии явно очищают маркер, сторож сбора не менялся. |

## Замечания

- major — orchestrator/doctor/isolation.py:294-297 — `codex-isolation-smoke` формирует `step_env` вручную и затем безусловно присваивает ему `ARTEL_ROLE=role`, прежде чем вызвать предикат. Если `runner.role_env()` перестанет класть этот маркер в реальное окружение шага Codex, этот offline-smoke останется зелёным и не выполнит AC-3; текущий тест предиката этого свойства смока не заменяет. Собирайте для этой проверки фактическое окружение шага через общий путь `runner.role_env` либо сделайте реконструкцию зависимой от единого механизма установки общих меток, не присваивая проверяемый маркер в самом смоке.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/doctor/isolation.py:294-297 | Codex-smoke сам создаёт проверяемый `ARTEL_ROLE`, а не получает его из фактически собранного окружения шага. | Регрессия установки маркера в `runner.role_env` не будет выявлена offline-smoke; AC-3 нарушен. | Проверять результат фактической сборки окружения общим путём либо устранить локальное присваивание, связав его с единым механизмом общих меток. |

## Вердикт

changes_requested: исправить R1-F1, чтобы `codex-isolation-smoke` проверял распознавание реального собранного окружения шага, включая поставку `ARTEL_ROLE` из общего механизма.

## Проверено исполнением

- `python3 -m pytest tasks/01M3SE87R3M7HGWX8HG1ANAKR0/acceptance_tests tests/test_runner_role_environment.py tests/test_notes.py tests/test_notes_apply.py tests/test_notes_row_format.py tests/test_answer.py tests/test_doc_commit.py tests/test_doctor_canary_pool.py tests/test_doctor.py tests/test_stack_parity_table.py tests/test_stack_codex_section.py tests/test_provider_scoped_step_env.py tests/test_providers_codex.py -q -p no:cacheprovider -p timeout -o timeout=120` — 343 passed, 127 subtests passed.
- `ARTEL_ROLE=reviewer python3 -m pytest tasks/01M3SE87R3M7HGWX8HG1ANAKR0/acceptance_tests/test_documentation_and_ambient_suite.py tests/test_answer.py tests/test_doc_commit.py tests/test_doctor_canary_pool.py tests/test_notes.py tests/test_notes_apply.py tests/test_notes_row_format.py -q -p no:cacheprovider -p timeout -o timeout=120` — 138 passed, 26 subtests passed.
- `git diff --check 9c5981e138066cd6e77200f2513e1f693c9389f1...HEAD` — чисто.
