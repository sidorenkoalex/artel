# Записка analyst

## Выяснено
- Шаг 3 (возврат с spec_gate): решения гейта О-1…О-6 и мелкие внесены в SPEC.
  - О-1(а): требование 15 + AC-21, часть 2 правит `tests/sandbox.py::isolate_keychain_and_role` (подмена транспорта по умолчанию); неверный факт про тест А0 в части 2 исправлен.
  - О-2: требование 6 — статус конвейера (success/manual → можно green; failed → red; running-набор → running; canceled/иной → unknown), постраничный список конвейеров sha с `X-Total`; AC-8 расширен, AC-19 новый.
  - Трактовка: «иной → unknown» прочитал как «не названный в требовании 6»; статусы конвейера running/pending/waiting_for_resource/preparing/scheduled → running (они уже названы в ANSWER-1 п.5). Если гейт имел в виду иное — это место правки.
  - О-3: реестр в forge.py; `EXEMPT` сторожа А0 (`test_ac9_no_support_literals_outside_targets`) + одна запись forge.py — часть 1, файл в зонах части 1. Сторож ловит только `ast.Compare`, ключи словаря реестра он и так не видит.
  - О-4: отображение check runs для github — требование 2, AC-13. О-5: таблица треб. 10 (running → пустое множество, unknown → VERIFYING_NONE); у `failed_check_names` тип set (ci.py:1116), поэтому «пустой список» записан как пустое множество. О-6: AC-20.
  - Мелкие: TOKEN_EXPIRY_WARN_DAYS = 14; «сеть недоступна: <текст>» (AC-22); число задач — все, кроме killed.
- Раздел «## Матрица неослабления» добавлен в SPEC (5 строк). Строку мандата «Ослабление тестов разрешено:» в SPEC не писал: её выдаёт Оператор через `answer`.
- В зоны родителя добавлены tests/sandbox.py и тест А0 (tests/ — COMMON_ZONES, это для ясности).
- guard: ок.

## Не сработало
- Длинная heredoc-команда python в Bash — «Parser aborted (over-length)»; правил через Edit по кускам.

## Где остановился
- SPEC.md готов, status: ready, 22 AC (часть 1: AC-1…15, 19, 20, 22; часть 2: AC-12 вывод, 16–18, 21).

## Чего не хватило
- А0 лежит только в origin/main — читать через `git show origin/main:tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`.
