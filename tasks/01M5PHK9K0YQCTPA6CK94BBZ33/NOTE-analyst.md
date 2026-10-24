# Записка analyst

## Выяснено
- ТЗ достаточно, SPEC.md написан (status: ready, budget_usd 70 из ТЗ, 17 требований, AC-1…AC-18, монолит по сигналам budget ≥ 30 и AC ≥ 10). guard — ок.
- На ed38d987 факты ТЗ сходятся: строк 2493/609/160; grep «Ловит мутацию» 43/4/8 (43 и 4 включают литералы CLAIM :91 и :69 — заявок 42/3/8 = 53).
- Импорт `from tests.test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate import` — ровно в трёх импортёрах (merge :60, prior :56, components :40); других импортов трёх исходных файлов в tests/, orchestrator/, scripts/ нет.
- `tests/test_mandate_test_id.py:3` — только текстовая ссылка в докстринге на `test_01m5d02n3b428v8bwc3pam9qct_*.py`; в «Не входит», правки нет.
- Образец формы — SPEC волны 1б (`git show refs/artifacts/01M5PCB66D936FDGG7H09CVGA1:tasks/01M5PCB66D936FDGG7H09CVGA1/SPEC.md`).

## Не сработало
- guard: ссылка «AC-6.» в начале строки внутри текста AC-18 считается повтором номера — ссылки на критерии не ставить в начало строки.

## Где остановился
- Шаг завершён: SPEC.md ready, guard ок.

## Чего не хватило
- Ничего существенного; форму взял из SPEC 1б.
