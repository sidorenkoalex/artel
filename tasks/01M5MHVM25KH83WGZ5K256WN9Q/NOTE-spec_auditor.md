# Записка spec_auditor

## Выяснено
- Факты SPEC подтверждены: artel.py:950–958, artel.py:1066–1071, watch.py:320–326, config.py:82–83; watch.py:27 импортирует `datetime` по имени.
- Других `fromisoformat` с "last_seen_at" в orchestrator/ нет.
- tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py:157 уже подменяет watch.datetime; после правки это затронет и свежесть artel.py (там artel.main только для observe stop — безвредно).
- Вердикт concerns: линтер AC-3 обходится промежуточной переменной; «время берётся один раз» в AC-4 без способа проверки.

## Не сработало
- sed/cat через cd в Bash отклоняется правилом — читать файлы через Read, grep работает.

## Где остановился
- SPEC-AUDIT.md готов (status ready, verdict concerns), guard ок.

## Чего не хватило
- Ничего существенного.
