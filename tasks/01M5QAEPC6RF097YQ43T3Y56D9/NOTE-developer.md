# Записка developer

## Выяснено
- Свод сделан и закоммичен (9b29a735): 42 теста — функции в tests/test_outcome_gate_module.py, исходник удалён, карта обновлена.
- Набор — 63 патча; правки только через `patch_tool.py` (PATCHES[n]; `python3 patch_tool.py 31` пишет diff и проверяет apply).
- «До» ГОТОВО: прогоны №1 (1-15), №2 (16-30), №3 (31-45), №4 (46-60), №5 (61-63), №6 (6-15, перепрогон 006/008/015), №7 (31-31, перепрогон переписанного 031). Все убиты, кроме 060 — находка в plan_head (эквивалентна: вход `ordered` уже отсортирован, :943).
- 031 переписан: был в `acceptance.in_outcome_bounds` → валил выход из tests_writing (только in_dev_task); теперь в `outcome_integrity._bounds` — `reported()` вместо `in_outcome_bounds`.
- PLAN.md генерируется: `python3 plan_tool.py "1,2,3,4,5,6,7" "<№ после>"` из plan_head.txt (править шапку, не PLAN.md).
- Сверка планки по диску: `python3 check_tool.py test_mutation_tables.py`.

## Где остановился
- «После»: №8 (1-15), №9 (16-30), №10 (31-45), №11 и №13 (46-60), №12 (61-63) готовы. Подтяжка main 11a3d23a orchestrator/ не меняла — «до» не перепрогоняется.
- Единственный красный планки test_mutation_tables: мутация 051 «до» убил и test_ac8_flaky_on_base_no_refusal, «после» (№11, №13) — нет. Причина — случай: тест берёт `rng.choice(("failed","error"))` для базы, мутация 051 считает `error` зелёным → убивает только при выборе `error` (½). Лечение — перепрогон 46-60 «после» тем же диапазоном, пока не выпадет (последняя строка в тексте действует); plan_tool с номерами «после» через запятую по порядку.
- test_branch_diff по check_tool красный ложно: `_pult.py` локальной копии держит DIFF_BASE=579a3819, после подтяжки main дифф надо мерить plank-run'ом пульта.
- Дальше «после» (--ref worktree --tests tests/test_outcome_gate_module.py --copy-table --wait-lock 4) частями 1-15, 16-30, 31-45, 46-60, 61-63 (пары диапазонов — как у частей «до»); перед каждой — `git status --porcelain -- orchestrator/` (пусто). Затем plan_tool, check_tool, guard, status: ready.
- В конце удалить из каталога документов: patch_tool.py, plan_tool.py, plan_head.txt, check_tool.py, _pult.py и __pycache__.

## Чего не хватило
- Слова «подготовк»/«setUp»/«находк» в строках PLAN со ссылкой на мутацию планка считает отметками (_setup_lines / _mentioned_as_finding).
