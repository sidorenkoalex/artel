## Выяснено
- Факты ТЗ сверены с кодом: `fsm._mark_questions_answered` — fsm.py:613, вызов в approve — fsm.py:1870-1871 (baseline = t["answer_baseline"], fsm.py:1834); `canary._pass_escalated_with_synthetic_answer` — canary.py:1445-1488; `QUESTIONS_SKIPPED_ACTION` — fsm_advance.py:94.
- `answer.cmd_answer` не трогает answer_baseline/escalated_from — строку задачи можно читать после записи ANSWER (как уже делает canary.py:1482).
- `_mark_questions_answered` пишет актором "operator"; без QUESTIONS.md печатает сообщение и выходит, не падает.
- SPEC написан: 4 AC, budget 25, зоны canary.py, codebase-map, tests/.

## Не сработало
- Ничего.

## Где остановился
- SPEC.md status: ready, guard прогнан.

## Чего не хватило
- Ничего существенного.
