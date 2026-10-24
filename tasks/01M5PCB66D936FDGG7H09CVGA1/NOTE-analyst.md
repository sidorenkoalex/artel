# NOTE analyst — 01M5PCB66D936FDGG7H09CVGA1

## Выяснено
- ТЗ достаточно; SPEC писан по образцу SPEC волны 1а (`git show refs/artifacts/01M5NNDYGQ8G6VFDEEXYBB0W3D:tasks/01M5NNDYGQ8G6VFDEEXYBB0W3D/SPEC.md`), решения её гейта (круги 1–3) ТЗ перенесло сюда.
- Факты ТЗ сверены по рабочей копии: строки «Ловит мутацию» 28/17/13/4/6/3 = 71, строк 2271. `grep -c 'def test_'` даёт 29 и 18 у `test_doc_commit.py`/`test_doc_commit_suite_gate.py` — лишние `def test_green()`/`def test_seed_always_red()` на уровне модуля (строки 53 и 41) — это текст засеваемого набора песочницы, не тесты.
- Импорты: suite_gate ← test_doc_commit (DocCommitSandbox и константы); batch_flush_edges ← suite_gate. `test_01m4s0…` несёт `setUpModule` (строка 34), held_base-файлы и 01m4s0 — случайный выбор (`random.SystemRandom` сид), `subTest` — в batch_flush_edges:55 и 01m4s0:231,250,267.
- Нет строки «Порядок: после» → `merge_after` нет. Бюджет $70 из ТЗ.

## Не сработало
- Составные bash-команды с `cd`/циклами требуют подтверждения — только простые grep/git.

## Где остановился
- SPEC.md написан (status: ready, 13 требований, AC-1…AC-15, budget_usd 70, обоснование монолита), `scripts/guard.py` — ок. Шаг завершён.

## Чего не хватило
- Образец формата — SPEC волны 1а в refs/artifacts, нашёлся через `git log --all -- tasks/<id>/SPEC.md`.
