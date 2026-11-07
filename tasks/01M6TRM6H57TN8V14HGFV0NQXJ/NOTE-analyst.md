# Записка analyst

## Выяснено
- Шаг 6 (четвёртый возврат со spec_gate, решения 1–2): SPEC дополнен, не переписан.
- Решение 1 → AC-3, случай предела размера: возврат раньше подменённого CI_REPORT_DOWNLOAD_TIMEOUT_SEC, сон gh ≤ 5 с, pid снят; мутация `subprocess.run(capture_output, timeout)` + сверка длины по TimeoutExpired красная. Прежняя фраза «так ловится чтение целиком» убрана.
- Решение 2 → AC-6: вымышленная запись GitLab с report+full_suite:ci — список имён строк project_entry_checks + component_checks прежний; мутация «строка добавлена любой записи» красная. Сверено: gitlab_doctor_lines.py:152-161 — компонент с report/full_suite: ci есть.
- Материалы: пункт о четвёртом возврате.

## Не сработало
- `cd … && python3 …` в Bash отклоняется — guard звать абсолютным путём.

## Где остановился
- Готово: SPEC.md, status ready, guard ок. AC-1..AC-9, budget 50 без изменений.

## Чего не хватило
- —
