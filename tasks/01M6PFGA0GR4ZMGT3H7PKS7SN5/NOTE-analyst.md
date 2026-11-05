## Выяснено
- Факты ТЗ сверены с кодом: `fsm._mark_questions_answered` — fsm.py:613-626 (без QUESTIONS.md или номера ANSWER — return), вызов в approve — fsm.py:1870-1871, baseline — fsm.py:1834; `_answer_baseline_or_refuse` fsm.py:545-563 (первая эскалация — 0); `canary._pass_escalated_with_synthetic_answer` — canary.py:1445-1488.
- Второй возврат с гейта: Решение 1 — AC-1/AC-2 в двух случаях answer_baseline (0 и >0), мутация «проверка по истинности» красит AC-1 при 0; AC-3 (б) in_dev с baseline = 0. Решение 2 — два пути синтетического ANSWER в «Материалах» (подмена канала по test_canary_synthetic_answer.py:139-143, либо настоящий answer.cmd_answer + подмены commit_files и mandate._tree_files; без второй — sandbox.py:841). Утверждения сверены: mandate.py:178 зовёт ls_tree_files(code_branch, ".").

## Не сработало
- Bash с `$?`/переменными отклоняется — без расширений.

## Где остановился
- SPEC.md status: ready, guard ок.

## Чего не хватило
- Ничего существенного.
