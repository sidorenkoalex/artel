---
task: 01M3SE87R3M7HGWX8HG1ANAKR0
type: plan
author_role: developer
status: escalate
schema_version: 5
question: Разрешить расширение зоны на orchestrator/notes.py для отказа note из шага роли?
---

# PLAN: Признак процесса шага роли для всех провайдеров

## Подход

Расширить единый `runner.in_role_environment(env=None)`: непустой `ARTEL_ROLE` распознаётся для любого провайдера, прежняя пара `HOME`/`CLAUDE_CONFIG_DIR` остаётся достаточной. Потребители сохраняют вызовы функции. Оба офлайн-смока проверяют распознавание собранного окружения. Обычные тесты операторских команд изолируют свой процесс от унаследованного `ARTEL_ROLE`, а тесты отказов устанавливают маркер явно; корневой сторож сбора pytest не меняется.

## Шаги

1. Расширить `orchestrator/runner.py::in_role_environment`, добавить проверку результата в `orchestrator/doctor/isolation.py` и описать признак и паритет в `docs/stack.md`.
2. Обеспечить независимость обычных тестов команд от ambient `ARTEL_ROLE` в `tests/`, добавить поведенческие тесты только для свойств, отсутствующих в залоченном долгоживущем файле; проверить заявленную мутацию нового сторожа.
3. Прогнать залоченную планку задачи и тесты затронутых модулей с `ARTEL_ROLE` и без него; регенерировать `docs/codebase-map.md`, проверить `scripts/guard.py` и закоммитить код.

Шаг 2 выполнен в разрешённых файлах. Закрытие отказа `note` из шага 1 требует расширения зоны и ожидает решения Оператора.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1, 2 |
| 3 | 1, 2 |
| 4 | 1 |
| 5 | 2, 3 |
| 6 | 2, 3 |

## Влияние на систему

Рубеж отказа расширяется на шаги codex. Существующая альтернатива для claude и логика потребителей сохраняются. Сторож `conftest.py` продолжит читать ambient `ARTEL_ROLE` при сборе. Изоляция обычных тестов действует только внутри тестовых сценариев, не в коде пульта. Изменение откатывается revert одного кодового коммита.

## Риски

Новый признак может покраснить тесты операторских команд, если они наследуют маркер pytest. Проверить целевые модули при `ARTEL_ROLE=test_author`, включая `ZonesExtendCommandTest` и `CanaryPoolDriftCheckTest`.

## Проверка

- `ARTEL_ROLE=test_author` для семи модулей из AC-6, залоченного долгоживущего файла и нового теста: 210 passed, 1 failed. Единственный отказ: `RoleCommandRefusalTest.test_ac5_codex_answer_note_and_pool_decryption_refuse` — `notes.cmd_note(["--flush"])` не поднимает `SystemExit`.
- `tests/test_stack_parity_table.py`, `tests/test_stack_codex_section.py`, `tests/test_doctor.py`, `tests/test_providers_codex.py`, `tests/test_provider_scoped_step_env.py`, новый тест: 205 passed.
- Приёмочный `test_documentation_and_ambient_suite.py`: 2 passed.
- Временная мутация `if env is None` → `if not env` покраснила новый тест; исходный код восстановлен.
- `ARTEL_ROLE=test_author` для `tests/test_doc_commit.py` и `tests/test_doc_commit_suite_gate.py`: 45 passed после изоляции обычных сценариев от ambient маркера.
- `git diff --check` — чисто; `python3 scripts/guard.py tasks/01M3SE87R3M7HGWX8HG1ANAKR0/PLAN.md` — `GUARD: ок`.
- `git add` не выполнился: `index.lock` в общем `/Users/al.sidorenko/projects/artel/.git/worktrees/01M3SE87R3M7HGWX8HG1ANAKR0/` недоступен для записи (`Operation not permitted`). Кодовая ветка осталась без коммита из этого шага.

## Предложения системе

- Песочница шага с доступной на запись только рабочей копией не даёт разработчику исполнить обязательный `git add`/commit: gitdir worktree расположен в общем `.git/worktrees/` вне разрешённого корня. Нужен штатный доступ к gitdir задачи либо коммит кода средствами пульта.

## Эскалация

- **Вопросы** — 1. Расширить `zones` SPEC на `orchestrator/notes.py`, чтобы добавить в `cmd_note` отказ при `runner.in_role_environment()`? Варианты: A) да, расширить зону и сохранить AC-5 (предпочтительно); B) изменить AC-5 так, чтобы `note` был доступен роли. Дефолт при отсутствии ответа по существу: A, но до явного разрешения зоны файл не правлю.
  2. Как обеспечить кодовый коммит в этом worktree при запрете записи в общий gitdir? Варианты: A) открыть запись в gitdir задачи для следующего шага (предпочтительно); B) оставить обязательный автокоммит пульта по окончании шага с записью дефекта. Дефолт при отсутствии ответа по существу: B для уже подготовленных изменений.
- **Контекст** — `orchestrator/notes.py:1177` (`cmd_note`) не вызывает `in_role_environment`; текущий рубеж есть лишь в `cmd_doc_commit` на строке 1291. Залоченный тест `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py:144` требует отказа `note --flush` и падает. Разрешённые зоны SPEC: `orchestrator/runner.py`, `orchestrator/doctor/`, `docs/stack.md`, `tests/`.
- **Блокирует** — AC-5 и полностью зелёную планку задачи; `PLAN.md` нельзя поставить в `ready`, пока не разрешена правка `orchestrator/notes.py` либо не изменён SPEC с планкой. Отдельно запись в gitdir worktree заблокирована песочницей: разработчик не может выполнить обязательный коммит кодовой ветки.
