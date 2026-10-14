# Записка spec_auditor — 01M4VKZR1VE6KS2HECJ05ABCYR

## Выяснено
- Третий аудит (SPEC sha 88c6a515…): решения Оператора №1 (О-1..О-3) и №2 (К-1..К-3) отражены полностью (треб. 3 SPEC.md:47-58, AC-3, AC-5, AC-6, AC-7, AC-8).
- Код: `cmd_admit` models.py:1838-1893, `_parse_admit_args` :1821-1835 (отказ разбора печатает ADMIT_USAGE :1828), `ADMIT_USAGE` :1054, пустой --basis тоже печатает ADMIT_USAGE :1854-1855, `set_admitted` :1241-1281, `pair_suspension_refusal` :1593. Справка artel.py:177, :252-264.
- Тесты admit: tests/test_model_sets.py:190-244, текст ADMIT_USAGE не утверждают.
- Вердикт concerns: К-1 — «байт в байт» одной пары (AC-1) против смены ADMIT_USAGE в stderr отказов; К-2 — у «проверки роли и модели каждой пары» (треб. 2) нет AC, мутация «проверяется только первая пара» проходит.

## Не сработало
- Bash: `cd …;` и переменные (`$W`) требуют подтверждения, sed -i отклонён — только абсолютные пути, правки через Edit.

## Где остановился
- SPEC-AUDIT.md готов (status ready, verdict concerns), guard ок.

## Чего не хватило
- —
