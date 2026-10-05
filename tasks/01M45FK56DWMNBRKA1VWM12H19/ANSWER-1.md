---
task: 01M45FK56DWMNBRKA1VWM12H19
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ответ Оператора (05.10, после мержа части 1 01M45FJVGQT1K0P8HDEXZX6HS7 и 01M46C776SZEMYPBQGPNJN1TXY в main).

1. AC-9, половина «с профилем тестов»: вариант (а), но сейчас, в этом шаге, без отложенной правки планки. Часть 1 смержена: форма поля задана в main — запись проекта в targets.yaml несёт `test_profile` с полями command, long_lived_dir, long_lived_name, weakening_scope, mutation_claim_scope (необязательные report, install); разбор и решение — orchestrator/project_profile.py (`decide`). Профиль артели в targets.yaml main:
       test_profile:
         command: [python3, -m, pytest]
         long_lived_dir: tests
         long_lived_name: test_<id>_<name>.py
         weakening_scope: [tests/**/*.py]
         mutation_claim_scope: [tests/test_*.py]
   Напиши тест половины «с профилем»: любое применённое приложение запускает полный прогон командой профиля; красный прогон — отказ мержа.

2. AC-12: вариант (а) — разовый файл планки зовёт обёртки гейтов напрямую для задачи с неразрешённым контекстом и сверяет причину (проект + «контекст не разрешён») и отсутствие отказа гейта ёмкости. Критерий не сужается.

3. Обязательно, во всех пяти долгоживущих файлах tests/test_01m45fk56dwmnbrka1vwm12h19_*.py: фикстура targets.yaml описывает артель без `test_profile`. После мержа части 1 пульт проекту без профиля отказывает (fail-closed) — проверено Оператором на копии «ветка + текущий main»: `merge_gate.py::ArtelFullSuiteClassesTest::test_ac9_…` красный («у проекта artel нет поля test_profile»), остальные тесты, красные до реализации, упрутся в то же после неё. Добавь блок профиля (как выше, слово в слово) ТОЛЬКО записи артели; внешнему проекту профиль не добавляй — его поведение без профиля часть тестов проверяет. Проверенный образец: константа `ARTEL_PROFILE` с этим блоком рядом с `TARGET_ENTRY` и `text += ARTEL_PROFILE` / `+ ARTEL_PROFILE` сразу после записи артели (merge_gate.py, in_dev_gates.py, draft_mr.py, spec_zones.py); в no_paths_mirror.py блок — в конец `ENTRY` (там одна запись, артели). Проверки (assert) и ожидаемые значения не меняй. С этой правкой набор красных тестов на копии «ветка + main» совпал с набором на исходной ветке.

Прогоняй тесты интерпретатором пульта (`.artel/venv/bin/python3`).
