# Записка spec_auditor — 01M6HVPMYY2Q56JZ64KD28FTWK

## Выяснено
- `pause.cmd_resume` (orchestrator/pause.py:111-113) у задачи не на паузе журнала не пишет — «resume после stop» (треб. 1) надзору не виден без правки pause.py, а pause.py вне зон.
- `answer` с указанием (без строк мандата) в in_dev/review lease уже не берёт (answer.py:313-316; тест 01m443bp… ac8) — AC-13 с указанием зелёный на main.
- ac18 вариант «запись CYCLE_ABORTED» — запись остановки есть, а треб. 3 называет аварией только выход БЕЗ записи; ac13[лимит шагов] (без мандата) пишет CYCLE_ABORTED после остановки.
- `epic["state"]` open/closed уже есть (epics.py:250, 268).
- `_child_holds` 1235, `_epic_view` 1365-1368, `_supervise` 1430, `_end_reason` 1386 — сверены.

## Не сработало
- grep с `--include` и `xargs` отклоняются песочницей — `grep -rl … tests`.

## Где остановился
- Вердикт fail, SPEC-AUDIT.md записан; guard прогнан.

## Чего не хватило
- Где пишется запись «resume» без паузы — искал в pause.py; ответ: нигде.
