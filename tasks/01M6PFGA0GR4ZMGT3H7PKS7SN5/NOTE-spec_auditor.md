# Записка spec_auditor

## Выяснено
- Повторный аудит SPEC sha 859f5860: AC-3/AC-4 переписаны по Решению 1 Оператора — прежнее отклонение снято.
- Факты сходятся: fsm.py:613-626 (618-624 без батча/номера — return), 1834, 1870-1871; fsm_advance.py:97; canary.py:1445-1488; answer.py не трогает escalated_from/answer_baseline.
- Detail возврата канарейки не в auto._ESCALATED_RETURN_DETAILS (auto.py:382) — анкер, AC-2 выполним.
- Существующие тесты: test_canary.py/test_canary_budget_ceiling.py подменяют функцию; test_canary_synthetic_answer без QUESTIONS.md — только печать.

## Не сработало
- grep после cd отклоняется — использовать абсолютные пути.

## Где остановился
- SPEC-AUDIT.md: verdict pass, status ready.

## Чего не хватило
- —
