## Выяснено
- ANSWER-1: все три вопроса — вариант A (гейт не повод выхода; место лимита — живой дочерний `auto`; наблюдение — выбранное при запуске, схема `observations` не меняется).
- Модуль команд эпика — `orchestrator/epics.py` (origin/main); `epic parallel`/`epic stop` нет, колонки лимита в `epics` (`schema.py` `EPICS_DDL`) нет — их вводит эта задача.
- `_cmd_stop` (`artel.py` ~1396 origin/main) сам журнала не пишет: запись остановки даёт `auto.auto_stop` (`AUTO_STOPPED_ACTION`) после SIGTERM-флага `_stop_requested`.
- Э2а SPEC (refs/artifacts/01M5TBCY…): «первый шаг роли» = запись «agent run started»; `start_after` проверяется только до первого шага — SPEC Э2б опирается на это определение.

## Не сработало
- В песочнице нет `ls`/`rm` в PATH — удалял файл через python3.

## Где остановился
- SPEC.md написан (14 AC, budget 45, merge_after Э2а, обоснование монолита — материал Оператору), guard ок; QUESTIONS.md удалён.

## Чего не хватило
- Ветка задачи старше мержа Э1 — код эпика читал через `git show origin/main:…`.
