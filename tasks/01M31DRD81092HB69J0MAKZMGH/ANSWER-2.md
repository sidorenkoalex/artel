---
task: 01M31DRD81092HB69J0MAKZMGH
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

Решение Оператора по конфликту подтяжки main (гейт мержа, 21.09).

В main смержена часть 2 линии провайдеров (01M300A14KRHCFB0DQXVCBJEKF):
она внесла `models.yaml` в `config.PROTECTED_PATHS` и переписала абзац
комментария над списком. Конфликт — только в тексте этого комментария и
в сгенерированной карте; значения кода не конфликтуют.

Как разрешить:

1. `orchestrator/config.py`, комментарий над `PROTECTED_PATHS`: взять
   абзац из main (models.yaml В СПИСКЕ, SPEC 01M300A14K, требование 12)
   и заменить в нём последнее предложение («CI-джоб `protected-paths`
   … читает этот список из ВЕТКИ PR, поэтому ветка … покрасила бы
   собственный PR») на описание поведения после этой задачи: джоб читает
   список из БАЗЫ сравнения PR (`scripts/ci_protected_paths.py`, SPEC
   01M31DRD81092HB69J0MAKZMGH, требования 1-4), поэтому следующий новый
   защищённый путь вносится тем же изменением, что создаёт файл. Абзац
   ветки про «ПОКА НЕТ» и срок устаревания — не брать: оба условия уже
   исполнены. Сам кортеж `PROTECTED_PATHS` — как в main (с `models.yaml`).
2. `docs/codebase-map.md` — не править руками, перегенерировать
   `scripts/codebase_map.py`.
3. Прочие части `config.py` из main (удалённая `TOKEN_RATES`,
   `MODEL_TARIFF_MAX_AGE_DAYS`, потолок гейта ёмкости) принять как есть;
   калибровочная таблица и комментарии ветки — как в ветке.

После разрешения прогнать `tests/test_budget_calibration_table.py`,
`tests/test_capacity_gate_map.py`, `tests/test_ci_protected_paths.py`,
`tests/test_review_package.py`, `tests/test_review_package_map.py`,
`tests/test_protected_paths_gate.py` и приёмочные тесты задачи. Остальные
требования SPEC и приложения к PLAN не менять.
