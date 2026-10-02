---
task: 01M3YCHP14179R32SFJVKQB32G
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

1. (а) Мандат на замену утверждения, как предложено: `len(config.PROTECTED_PATHS)` 17 → 18, добавить `assertIn("model_sets.yaml", config.PROTECTED_PATHS)`, обновить докстринг («плюс пять записей настроек сбора тестов и `model_sets.yaml`»). Имя метода и прочие утверждения (`[:12] == LEGACY_PROTECTED_PATHS`, пять записей настроек тестов) не менять. Основание: правка не снимает ни одной ловимой мутации и добавляет проверку новой записи.

Ослабление тестов разрешено: tests/test_protected_test_settings.py::RealProtectedPathsCompositionTest::test_real_list_keeps_legacy_entries_and_adds_test_settings
