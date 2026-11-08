# Записка ревьювера, итерация 2

## Выяснено
- R1-F1 исправлен `sandbox_sources or None` в `long_lived_errors_from_files` (`scripts/guard.py:4575`); R1-F2 — `_imported_names` и `_SandboxRefs.packages`.
- 114 тестов зелёные (два долгоживущих файла задачи + `tests/test_guard_shared_readonly_rules.py`).
- Временная мутация обеих правок — оба новых теста красные; код возвращён.

## Не сработало
- Составная bash-команда с `sed -i` и heredoc требует подтверждения — мутации делал через Edit, откат `git checkout`.

## Где остановился
- REVIEW.md итерации 2 сдан: `approved`, R1-F1/R1-F2 → accepted.

## Чего не хватило
- Ничего существенного.
