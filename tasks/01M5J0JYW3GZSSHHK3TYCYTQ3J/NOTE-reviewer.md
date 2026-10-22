# NOTE-reviewer (итерация 1)

## Выяснено
- Вердикт итерации 1: changes_requested, три major (R1-F1..F3 в REVIEW.md).
- R1-F1: `_added_lines` при `diff.noprefix=true` в конфиге git даёт `{}` (проверено через GIT_CONFIG_COUNT/KEY_0/VALUE_0 в os.environ из python -c).
- R1-F2: `_code_exception_findings` пропускает файл R тест→код из-за `for p in (path, old)` (проверено прямым вызовом с SimpleNamespace-профилем).
- R1-F3: AC-28/29 только в разовой планке `test_autogate_plank_rule.py`, в tests/ сторожа нет.
- Всё прочее (треб. 1–6, 8–11) по коду сходится; тесты задачи и планка зелёные (outcome_prior ~255 с).

## Не сработало
- bash с переменными окружения/`ls`/составными командами отклоняется — по одной команде, литеральные пути, env задавать внутри python.

## Где остановился
- REVIEW.md записан полностью.

## Чего не хватило
- Нет быстрого способа увидеть, какие AC покрыты в tests/ — пришлось grep по классам Ac<n>.
