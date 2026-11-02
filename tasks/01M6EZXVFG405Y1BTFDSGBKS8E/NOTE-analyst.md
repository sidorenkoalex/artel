# Записка analyst

## Выяснено
- Итерация 3 (возврат со spec_gate, решения по аудиту):
  - Треб. 3: причина `unsupported_reason` БЕЗ префикса «проект <имя>: » — его ставят вызывающие (catalog.py:858, runner.py:188-189, doctor/cli.py:44). Текст: `гейт мержа <gate> не поддержан для хостинга <forge> (поддержаны: github + operator, gitlab + target-human)`. AC-2/AC-3 требуют в выводе действий префикс `проект <имя>: ` ровно один раз; AC-4 — причина не начинается с `проект `.
  - Новый раздел SPEC «Существующие тесты сторожа А0»: мандат поимённо на ac1, ac7, ac8; ac2–ac6, UNSUPPORTED/UNSUPPORTED_IDS не меняются; меняются только значения констант GITLAB_REASON/TARGET_HUMAN_REASON; ac9 не трогается (WATCHED_VALUES уже содержит все 4 значения, targets.py исключён SUPPORT_MODULE).
  - Вызывающие добавлены в «Не входит» (guard требовал классификации doctor/cli.py).
- merge_after — три части: 01M6EZXVFGXC6WBDA9QJESAZRW, 01M6EZXVFGCHB1S4W45AWJ0QH6, 01M6EZXVFGH5Z2876XWMQG35FP.

## Не сработало
- `cd … && …` в Bash блокируется («simple_expansion») — звать guard абсолютным путём.

## Где остановился
- SPEC сдан status: ready; guard ок.

## Чего не хватило
- Ничего.
