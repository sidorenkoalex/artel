## Выяснено
- Факты ТЗ сверены с кодом: `fsm._mark_questions_answered` — fsm.py:613-626 (без QUESTIONS.md — печать и return, без номера ANSWER — return), вызов в approve — fsm.py:1870-1871; `canary._pass_escalated_with_synthetic_answer` — canary.py:1445-1488; `QUESTIONS_SKIPPED_ACTION` — fsm_advance.py:94.
- Возврат с гейта (решение 1): AC-3/AC-4 переписаны — отрицательные сценарии при всём остальном условии AC-1 (QUESTIONS.md + новый синтетический ANSWER); AC-3 (а) spec_writing + baseline None, (б) in_dev + baseline не None; мутации «вызов безусловный», «только escalated_from», «только answer_baseline» красят AC-3. AC-4 — без QUESTIONS.md, но с новым ANSWER.
- Образец формулировки: tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py:424-444.

## Не сработало
- Составная команда Bash с переменной отклонена — читать файлы через Read.

## Где остановился
- SPEC.md status: ready, guard ок. Решение 1 отмечено в «Материалах».

## Чего не хватило
- Ничего существенного.
