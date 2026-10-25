# Записка spec_auditor — 01M5TBCY7WTN121S136XP2C6SR

## Выяснено
- Э1 (01M5TBBDFS6DWQY6MS263T1KPY) и Э0 (01M5TB6VDVV6AM8DWPGVQE8CDW) в main нет: `orchestrator/epics.py`, `board.py`, `closed_as` отсутствуют (grep по orchestrator/ пуст). Э1 «Порядок: после Э0» — зависимость от Э0 транзитивна.
- Факты SPEC сверены: budget.py:251, spend.py:22, merge_after.py:126/:299 верны; стоп-кран — runner.py:353 (SPEC пишет :352 — строка комментария).
- Шаг роли в журнале: единственный маркер старта — «agent run started» (runner.py:1608); отказы паузы/стоп-крана пишутся актором роли (runner.py:344, :360) — «шаг роли» по актору дал бы обход.
- merge_after.check (merge_after.py:173) строит граф только из merge_after; деление: fsm.py:978-981 (родитель → killed, replace_divided).
- Э1 уже показывает «потрачено / конверт» в status/epic show (ТЗ Э1, требования 5-6) — перекрытие с требованием 13.

## Не сработало
- Составные bash-команды с `;`/`|` требуют подтверждения — только одиночные команды.

## Где остановился
- SPEC-AUDIT.md записан (status ready, verdict concerns, 9 отклонений); guard: ок.

## Чего не хватило
- Нет кода Э1 — сверка модуля эпиков и формулы «потрачено» в board.py невозможна.
