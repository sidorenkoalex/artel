## Выяснено
- Итерация 2 ревью: approved. С итерации 1 изменился только новый тест tests/test_epic_draft_promote_unsupported_project.py (возврат с merge_gate); код orchestrator/ прежний.
- Новый тест + долгоживущий + drafts + lease-линтер — 37 passed; plank-run — 1 passed.
- Временная мутация (снять проверку в catalog.py:760) → новый тест красный (2 failed); код возвращён, дерево чистое.

## Не сработало
- Ничего: мутация через Edit/Edit-назад + одиночный pytest прошла.

## Где остановился
- REVIEW.md iteration 2, status: approved, реестр пуст.

## Чего не хватило
- Инкрементального diff в пакете (база не определена) — изменение итерации выделял по PLAN.
