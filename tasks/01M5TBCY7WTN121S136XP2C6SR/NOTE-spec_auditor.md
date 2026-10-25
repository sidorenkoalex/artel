# Записка spec_auditor — 01M5TBCY7WTN121S136XP2C6SR (аудит 4, редакция 4, sha 14ab1f92)

## Выяснено
- Э0/Э1 в main по-прежнему нет (HEAD 761b646e); снято решением гейта №3 п. 1.
- Решения №3 (порядок после Э1, watch «до события», start_after только на первом шаге) внесены: «Порядок разработки», треб. 4/15, AC-7, AC-27, AC-28.
- Ссылки runner.py:323/:341/:353/:1608/:1824/:1839/:1843, pause.py:154, auto.py:966-968, budget.py:251/:321, spend.py:22, merge_after.py:126/:158/:173/:185/:197/:299/:320, fsm.py:978/:981 верны.
- Действия журнала начисления: agent cost KNOWN (spend.py:557), PARTIAL (:824), ESTIMATED (:834); без начисления — LOST/UNKNOWN/UNCHARGED.
- Подсказки auto — константы config.py (AUTO_STOP_PAUSE :935, AUTO_STOP_WAVE_BREAKER :979), а config.py read-only.

## Не сработало
- Составные bash-команды через `;` требуют подтверждения — одиночные `git -C <W> grep`/sed.

## Где остановился
- SPEC-AUDIT.md: status ready, verdict concerns, 2 мелочи («алерт 100 %» в треб. 10; события начисления для watch не названы).

## Чего не хватило
- Кода Э1 (board.py, epics.py, new --epic/--after).
