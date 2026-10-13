# Записка spec_auditor — 01M4VKZR1VE6KS2HECJ05ABCYR

## Выяснено
- `cmd_admit` models.py:1838-1893, разбор `_parse_admit_args` models.py:1821-1835 (argparse, позиционные role/model), `ADMIT_USAGE` — models.py:1054 (не artel.py, как в ТЗ; SPEC это верно поправил). Справка artel.py:177 и абзац artel.py:252-261 (докстринг модуля).
- `set_admitted` (а) models.py:1260-1266 включает и `pair_suspension_refusal` (приостановку пультом), SPEC треб. 3 сужает (а) до записи `pairs:` — главное отклонение.
- Ноль позиционных (чётно) SPEC не оговорил; сейчас argparse отказывает.
- Отказ «две пары одной роли при --set» без AC.
- `ADMIT_USAGE` в tests/ буквально не сверяется — «Меняемое поведение» не нужен.
- docs/stack.md:845-857 описывает admit — вне зон и вне ТЗ, не отклонение.

## Не сработало
- —

## Где остановился
- SPEC-AUDIT.md написан, вердикт concerns; guard прогнан.

## Чего не хватило
- —
