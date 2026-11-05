# Записка spec_auditor

## Выяснено
- Факты SPEC о коде сходятся: fsm.py:613-626, 1834, 1870-1871; fsm_advance.py:97; canary.py:1445-1488; answer.py не трогает escalated_from/answer_baseline.
- Опыт в памяти (функция подменена в процессе, файлы не правились): tests/test_canary_synthetic_answer.py 11/11 зелёные с вызовом признака; test_return_restores... (answer_baseline="whatever", spec_writing) зовёт _mark_questions_answered, без QUESTIONS.md — печать и возврат.
- Отклонение: AC-3 не требует QUESTIONS.md и ANSWER в отрицательных сценариях — мутация «условие убрано, вызов безусловный» не ловится (в SPEC 01M4R4... AC-2 это оговорено: «всё остальное условие AC-1 выполнено»).
- Детали возврата канарейки нет в auto._ESCALATED_RETURN_DETAILS (auto.py:382) — её запись становится анкером, шаг аналитика после неё засчитывается; AC-2 выполним.

## Не сработало
- Запись в /tmp и heredoc в Bash отклонены — опыт гонял через python3 -c.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready.

## Чего не хватило
- —
