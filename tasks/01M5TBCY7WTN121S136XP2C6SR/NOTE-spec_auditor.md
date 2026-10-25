# Записка spec_auditor — 01M5TBCY7WTN121S136XP2C6SR (аудит редакции 2, sha 565327fa)

## Выяснено
- Э1/Э0 в main по-прежнему нет (grep closed_as/epic_id/envelope_usd по orchestrator/ и tests/ пуст); `new --after` тоже нет — его вводит Э1 (ADR-0028:33, :104).
- Факты SPEC редакции 2 сверены: runner.py:323/:341/:353/:1608/:1839, budget.py:251, spend.py:22, merge_after.py:126/:173/:185/:197/:299/:320/:358, fsm.py:981 — верны.
- Начисление стоимости в runner — ДВЕ ветки: charge_missing_result (:1824, таймаут/обрыв) и charge_step (:1839); общий хвост — budget.check_program_spend (:1843). Ещё начисление — pause.py:154 (pause --now). Требование 4 привязано только к :1839.
- auto.py:966-968: отказ run, не узнанный как пауза/зона/стоп-кран, → Stop с подсказкой «artel.py budget <id> <usd> или kill» и alert=True (алерт attention). auto.py вне зон ТЗ/SPEC.
- merge_after.check отказывает killed (:158) до любой подстановки — поделённый родитель тоже killed; источник «последней части» в БД на main — только текст журнала «поделена на: …» (fsm.py:978).
- watch — поток журнала с режимами (--tasks/--mine/--observation/--until); где и когда печатать предупреждение 80 %, SPEC не говорит.

## Не сработало
- `ls` в этой оболочке нет (command not found) — git ls-files/grep.

## Где остановился
- SPEC-AUDIT.md записан (sha 565327fa, status ready, verdict concerns, 7 отклонений); guard: ок. Все 9 отклонений аудита редакции 1 закрыты редакцией 2.
- Главные новые: AC-20 не называет функцию для подмены (тест-навязывает-устройство); алерт 80 % только на ветке charge_step; auto.py вне зон даёт ложную подсказку «budget».

## Чего не хватило
- Кода Э1 (board.py, epics.py) — сверка формулы «потрачено» и модуля команд невозможна.
