## Выяснено
- `_bound_names`/`_walk_own` уже есть в test_lint.py (:104, :192) — на них опирается `_medium_findings`.
- В guard правила размера стоят после `continue` у labelled-файлов (scripts/guard.py:4467-4487), это совпадает с PLAN.
- Долгоживущие тесты задачи и tests/test_size_marks_sources.py — 94 passed; мутация `_size_rules_apply` краснит AC-7/AC-9.
- Итерация 1: approved, одна запись minor R1-F1 сразу закрыта (accepted).

## Не сработало
- `plank-run` — «планки нет»: разовых файлов у задачи нет, это штатно.

## Где остановился
- REVIEW.md записан, approved.

## Чего не хватило
- Ничего существенного.
