# Записка аналитика

## Выяснено
- Возврат с гейта SPEC (решения 1–7 по SPEC-AUDIT): все внесены в SPEC.md.
- Факт контекста исправлен: признак выкладки сегодня — `runner: pytest-own` (`_own`, acceptance.py:121), pult-vitest с workdir выкладку под long_lived_dir/.artel-plank получает.
- Требование 5 — порядок трёх правил (plank_layout / pytest-команда без него / не-pytest без него → отказ «… выкладка планки не определена»), решается по команде, не по runner.
- Требование 3 — четыре дословных отказа, включая «родитель с точки»; «вне workdir» по realpath как `_own_cwd` (acceptance.py:214-229).
- Требование 7 — `--ignore` только при runner pytest-own, путь через `_own_target`; pytest без pytest-own — как сейчас.
- AC-10 — `drop_from_code_copy` убирает остаток plank_layout. Раздел «Матрица неослабления» — строка про test_ac11/test_ac16 (report_outcome.py:898, :1454).

## Не сработало
- python3 heredoc через Bash требует подтверждения — правил Edit-ом.

## Где остановился
- SPEC.md status: ready, AC-1..AC-10, budget 35, guard: ок.

## Чего не хватило
- Ничего существенного: адреса взяты из причины возврата и записки spec_auditor.
