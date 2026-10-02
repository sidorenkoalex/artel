---
task: 01M3XTF5506GF43HD51ECE230T
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

1. Вариант А. Проверка изоляции Codex в `orchestrator/doctor/isolation.py` (`codex_isolation_smoke`, около строки 298) дополнительно проверяет напрямую, что `config.ARTEL_ROLE_ENV` в собранном окружении шага непуст; при пустом — красная строка с текстом, что окружение шага роли не несёт маркер роли. Тот же прямой контроль — в `isolation_smoke` Claude (около строки 94), для симметрии. Существующий тест `tests/test_providers_codex.py::IsolationSmokeTest::test_missing_role_marker_in_assembled_codex_env_is_red` не менять: он должен снова стать зелёным за счёт этой проверки.
2. Признак роли по `HOME` (требование 2 SPEC) остаётся как есть; маркер `ARTEL_ROLE` остаётся обязательным для шага роли и проверяется смоком `doctor` отдельно от признака.
3. Других правок в `orchestrator/doctor/` не делать. Затем `PLAN.md` — `status: ready`, раздел эскалации снять.

Расширение зон разрешено: orchestrator/doctor/isolation.py
