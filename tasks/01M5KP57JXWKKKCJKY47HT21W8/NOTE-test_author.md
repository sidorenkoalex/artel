# Записка test_author — 01M5KP57JXWKKKCJKY47HT21W8

## Выяснено
- Долгоживущий файл: tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py — AC-1, AC-2, AC-3, AC-7, AC-8 (только миссия, без приватных имён; фраза о проверках выделяется как последняя непустая строка перед правилом).
- Планка (разовый): acceptance_tests/test_reviewer_prompt_and_appendices.py — AC-4..AC-6 (промпт: миссия + скилы CODE_ROOT/skills по roles.skills("reviewer") + CODE_ROOT/templates/REVIEW.md), AC-9 (role_prompt базы через `git show DIFF_BASE:…`, загружен модулем пакета orchestrator, обе сборки в одной песочнице), AC-10 (диффы ТЗ «## Приложения PLAN» ⊂ склейка guard.plan_appendices(PLAN), apply_check каждого).
- Гейт гоняет планку в worktree с наложенными приложениями (appendix_tree.suite_tree) — CODE_ROOT указывает туда; локальный plank-run приложений не накладывает → AC-6 там красен и при правильной реализации.
- Валидация стабом (константа + правило после фразы + перечень без suite-run) и наложенными диффами ТЗ: долгоживущий 5/5, планка AC-4..6, AC-9 зелёные; AC-10 проверен отдельно (разбор PLAN из диффов ТЗ, git apply --check = 0). Мутация в миссии developer красит AC-9. Стаб и диффы откачены, дерево чистое.
- preflight: все проверки пройдены.

## Не сработало
- Bash: ls/cat не в PATH, `$VAR` отклоняется.

## Где остановился
- Готово к сдаче. Карту кода (scripts/codebase_map.py) не регенерировал: правка docs/ вне прав test_author.

## Чего не хватило
- Как гейт кладёт CODE_ROOT на дерево с приложениями — нашёл в advance_gates/acceptance.py (~:598) + acceptance.py:2047.
