# Записка analyst — 01M56KCVCTW5BV9TWTH54TW9Q9

## Выяснено
- ANSWER-1: треб. 4 ТЗ (Claude `--add-dir` логов suite-run) исключено (B); PATH — вариант A (PATH вызывающего, затем dir(command[0]), затем /usr/bin,/bin,/usr/sbin,/sbin, без дублей; PATH из profile.env перекрывает).
- SPEC написан: 5 AC, zones `orchestrator/acceptance.py, tests/`, budget 25, status ready; QUESTIONS.md удалён.
- PATH: `_own_env` (acceptance.py:152-172) — одна правка покрывает все места через `_place_env`, включая two_sided.py:242.
- Сводка: достаточно добавить `deselected` в `_RUN_CATEGORY` (acceptance.py:292); `suite_run._SUMMARY_COUNT` (suite_run.py:98) уже считает passed/failed/skipped.
- FileNotFoundError: в acceptance не перехвачен; two_sided ловит OSError с текстом «pytest не запустился: …» — вне зон, в «Не входит».

## Не сработало
- Первый прогон guard: сигнал «число файлов» (считает упомянутые пути) — добавлена секция оценки с монолитом и «Прогноз диффа: 20 КиБ».

## Где остановился
- SPEC сдан, guard ок.

## Чего не хватило
- Ничего; в окружении шага нет `ls`/`rm` — удалял файл через python3.
