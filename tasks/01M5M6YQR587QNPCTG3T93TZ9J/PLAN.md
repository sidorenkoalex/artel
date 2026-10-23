---
task: 01M5M6YQR587QNPCTG3T93TZ9J
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Справочник ядра в брифе — только developer и test_author, предел 16 КиБ

## Подход
Одна правка значения: `orchestrator/config.py` — `CORE_REFERENCE_MAX_BYTES`
с 32 768 до 16 384, над константой — комментарий с решением Оператора
23.10 (CR-2026-10-22-11) и прежним значением. Формулы предела и
предупреждения 90 % (`brief._core_reference_part`, `projects.reference_summary`)
читают константу из `config` и не меняются. Состав по ролям уже нужный
(справочник зовут только `developer_brief` и `test_author_answer_component`) —
код не трогается. Свойства AC-1…AC-5 держит долгоживущий файл test_author
`tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`; своих
тестов не добавляю — непокрытых свойств нет.

## Шаги
1. `orchestrator/config.py:1004`–`1010`: новое значение и комментарий;
   регенерация `docs/codebase-map.md` (`python3 scripts/codebase_map.py`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 (код не меняется; держит AC-3 долгоживущего файла) |
| 3 | долгоживущий файл test_author; прогнан зелёным после шага 1 |

## Влияние на систему
Предел только ужесточается: справочник крупнее 16 384 байт в бриф не идёт
(сейчас справочник артели 14 725 байт — ниже предела и чуть ниже порога
90 % = 14 745,6 байт, предупреждения `brief.core_reference_near_limit` пока
не будет, но запас ~20 байт; `targets.yaml` Оператор уже поправил). Гейты, формулы, тексты алертов не меняются;
существующие тесты берут предел из `config` и подменяют его.
Прогон: `python3 -m pytest tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py
tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py
tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py` — 32 passed, 109 subtests.
Откат — revert одной строки константы.

## Риски
Внешние проекты со справочником 16–32 КиБ перестанут получать его в бриф
(отдельная настройка предела — вне задачи по SPEC).

## Предложения системе
