# Записка analyst — 01M5XZ9Z68V75VXF5Z66C708T4

## Выяснено
- ТЗ — часть 1 деления родителя 01M5XXA2HY73D3WTXDR19Z5SWW; SPEC родителя — в refs/artifacts родителя.
- Возврат из spec_gate 27.10 (п. 1–8) закрыт в SPEC: mr_assignee целым (треб. 3, строка матрицы),
  `targets.delivery_policy` + столбцы `mr_iid`/`mr_url` (треб. 2, 16), формы отправки — AC-5…AC-8,
  amend-tests в amend.py (треб. 19, AC-9; amend.py добавлен в zones), kill с in_dev после первой отправки (AC-18),
  AC-12/AC-17 названы «защита от регрессии», мандат на перечни тестов (треб. 22, вкл. tests/test_report.py),
  AC-14 показ ссылки MR на доске/status, AC-20 зелёные operator-тесты.
- Адрес merge_after исправлен: `merge_after.py:769` (гейт мержа, `s != "done"`) и `:792` (status); `:55` — это STATUS_WAIT_STATES.

## Не сработало
- Составные Bash-команды (`;`, переменные, heredoc с `{`) требуют подтверждения — только одиночные grep/скрипты по абсолютным путям.

## Где остановился
- SPEC.md переписан: 22 требования, AC-1…AC-20, budget 45, status ready; guard — ок.

## Чего не хватило
- Ничего существенного.
