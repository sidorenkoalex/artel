# Записка spec_auditor — 01M6EZXVFGXC6WBDA9QJESAZRW

## Выяснено
- Аудит 4 (spec_sha e33f5134…): решение Оператора №3 (ensure_forge_draft_mr, шов-читатель) перенесено — требование 13, AC-19/20, требования 1/12. Отклонения аудита 3 сняты.
- people_entry зовут только fsm_merge_gate.py:1516 и github_adapter.py:431 (grep по orchestrator/ и tests/); тестов на people_entry напрямую нет.
- Новое (мелкое): «people_entry для артели запись не читает» — на main читает; targets.py:865 не запрещает артели merge_gate target-human.
- «Ветка не отправлена» решения №3 SPEC сузил до «ensure_forge_draft_mr не отправляет» (публикация головы идёт раньше, tests_writing.py:71-74) — проверяемой мутации нет.

## Не сработало
- cd + git/grep в одной команде требуют подтверждения — абсолютные пути.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready.

## Чего не хватило
- Нет запрета target-human для артели в targets.check — искал в targets.py:860-893.
