# Записка analyst

## Выяснено
- Шаг 8: пятый возврат с гейта SPEC, решения 1–2. Ссылки сверены: acceptance.py:889-905 (_compose_call — Popen, start_new_session, ppid docker = pid дочернего прогона), :1306-1327 (_compose_teardown), targets.py:98-102 (раннеры pult-pytest, pytest-own, compose — `pytest` нет), tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py:409-423 (stop_everything добирает pid по calls_file, не по run.json).
- Р1 → AC-14: подменённый docker пишет вызовы с pid/ppid по порядку; down -v от дочернего прогона раньше docker ps исполнителя; мутация «снять группу ребёнка без ожидания» красная.
- Р2 → AC-26 на pytest-own с командой-заглушкой; имя раннера заменено и в треб. 1, 7, AC-20, матрице; AC-3/AC-15 — pid из файла вызовов заглушек; AC-4 — вторая пара «прогон не прерван, повтори --wait» (закрывает В3 аудита).

## Не сработало
- grep с обратными кавычками в Bash требует подтверждения — не прогнал проверку остатков `pytest`, заменял по Read.

## Где остановился
- SPEC сдан (status ready, 26 AC, budget 70), guard ок. Карта решений — «Материалы», пункт «пятый возврат».

## Чего не хватило
- —
