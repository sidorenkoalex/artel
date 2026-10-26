# Записка analyst — 01M5WCXBM7WCMRWCBWNCHMAR3T

## Выяснено
- Возврат гейта SPEC №2 (3 пункта) закрыт правкой SPEC:
  1. `ci_required_jobs`: требование 5 — чтение из плоской записи
     `targets.target(<имя>)` как `entry.get("ci_required_jobs") or []`;
     новый AC-23 — подмена загрузчика `targets.target`, не словарь в
     функцию. Загрузчик targets.yaml сегодня отказывает неизвестному полю
     policy (targets.py:441), `_flatten` переносит поля policy на
     targets.py:585-588 — поэтому сквозная проверка от yaml отнесена к Б1
     (01M5WDB7F14SQ30QVWJY2XYBG2) в «Не входит», с требованием той же формы.
  2. AC-21/требование 1: запрет сравнения результата функции forge с
     литералом forge в ci.py; членство в реестре в forge.py разрешено.
  3. AC-24…AC-32: по одному AC на open_mr, undraft_mr, assign_mr,
     mr_status, token_user, token_expiry, protections, сведения проекта,
     последний конвейер ветки — пара метод/путь + разбор ответа.
- Всего 32 AC, budget 50 (рамка Оператора), guard: ок.

## Не сработало
- `ls` в Bash недоступен; составные команды с `cd` — нет.

## Где остановился
- SPEC.md: status ready, guard ок. Шаг завершён.

## Чего не хватило
- Id Б1.1 из причины возврата не нашёл отдельно — сослался на Б1
  (01M5WDB7F14SQ30QVWJY2XYBG2).
