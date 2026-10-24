## Выяснено
- Итерация 2: возврат из merge_gate — помощник origin_backlog стенда окна тишины брал notes.BACKLOG_REL вместо литерала docs/backlog.md исходного NoteSilenceSandbox.
- Правка 6dee632d (от 7ea8ae48): только новый silence_origin_backlog (литерал) и 4 вызова в test_window_ac5/ac6/ac7/ac8_closed; ассерты прежние. Все вызовы с silence_box теперь на литерале, apply_box — на BACKLOG_REL (как ApplySandbox).
- orchestrator/, fixtures.py, sandbox.py между 549e997e и HEAD одинаковы; ни один патч мутаций не переопределяет BACKLOG_REL — таблица «после» (7ea8ae48) по смыслу не устаревает.
- 99 passed; plank-run 26 passed, rc 0.

## Не сработало
- Составные bash-команды (`;`, `$?`) отклоняются — гонял по одной.

## Где остановился
- REVIEW.md итерации 2 записан: approved, реестр пуст.

## Чего не хватило
- Инкрементального diff в пакете не было (база не определена) — сравнивал 7ea8ae48..6dee632d вручную.
