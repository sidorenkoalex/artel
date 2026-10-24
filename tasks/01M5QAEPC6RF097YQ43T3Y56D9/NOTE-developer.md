# Записка developer

## Выяснено
- Свод сделан и закоммичен (9b29a735): 42 теста — функции в tests/test_outcome_gate_module.py, исходник удалён, карта обновлена. plank-run test_module_form.py — 34/34; модуль целиком 53 passed за 173 с. git status чист.
- Набор — 63 патча. 001–030 из refs/artifacts/01M5PHK9K0YQCTPA6CK94BBZ33; там альтернативы заявок слиты/пропущены → 031–063 новые, 006/008/015/016/018 сужены. Все правки патчей — только через `patch_tool.py` (PATCHES[n]; `python3 patch_tool.py 6,8,…` пишет diff, проверяет apply и compile).
- «До» готово: №1 = 1-15 (СТАРЫЕ 006/008/015 — нужен перепрогон 6-15), №2 = 16-30 (уже новые 016/018). Все 30 убиты.
- PLAN.md генерируется: `python3 plan_tool.py "<№ до через запятую>" "<№ после>"` из plan_head.txt (править шапку, не PLAN.md); таблицы — из mutation-run-<n>.tsv, строки падений — из логов патчей. Сейчас сгенерирован с "1,2" "" , status: draft.
- Сверка планки по диску (plank-run видит PLAN только из ссылки): `python3 check_tool.py test_mutation_tables.py` (подмена `_pult.py` рядом). test_mutation_patches — 3/3 зелёный.

## Не сработало
- Часть 31-45 «до»: замок держал suite-run 01M5PT190RWC6984CDQVZ242GN, --wait-lock 4 истёк → по требованию 5 повтор в этом шаге не делал.

## Где остановился
- Осталось «до»: 31-45, 46-60, 61-63, перепрогон 6-15 (каждую часть — сразу в PLAN через plan_tool до старта следующей). Если какой-то новый патч «не убита» — переписать в patch_tool и перепрогнать его диапазоном, либо записать находкой.
- Затем «после» (--ref worktree --tests tests/test_outcome_gate_module.py --copy-table --wait-lock 4) частями 1-15, 16-30, 31-45, 46-60, 61-63; перед каждой — `git status --porcelain -- orchestrator/` (пусто). plan_tool "<до>" "<после>", check_tool test_mutation_tables.py, guard, status: ready.
- В конце удалить из каталога документов: patch_tool.py, plan_tool.py, plan_head.txt, check_tool.py, _pult.py и любые __pycache__.

## Чего не хватило
- Слова «подготовк»/«setUp»/«находк» нельзя в строках PLAN со ссылкой на мутацию (планка считает их отметками) — не сказано нигде, кроме кода планки (_setup_lines).
