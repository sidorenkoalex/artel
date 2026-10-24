# Записка spec_auditor — 01M5NPVRRK9R6S6SD40CBJZYPT (круг 2)

## Выяснено
- SPEC 463f9b7e: все 4 пункта и 2 мелочи решения Оператора №1 внесены (треб. 1–3, AC-3, AC-6).
- Факты подтверждены: pull.py:592/616/618/620/622–676/679–692/833–839; advance_gates/acceptance.py:34, :598–615; fsm_autogate.py:417; plan_appendix.py:28/:40; acceptance.py:2027–2044, :2008; test_pull.py:240; appendix_tree.py:236–292.
- `suite_tree(branch=None)` копирует неотслеживаемые файлы wt (appendix_tree.py:133–166), `tasks/` не игнорируется — выкладка из wt_path попадёт в дерево; безвредно: materialize_from_branch чистит лишнее (acceptance.py:1790–1844).
- Вердикт pass, guard ок.

## Не сработало
- `ls` в Bash недоступен (zsh eval) — пользоваться Read/grep.

## Где остановился
- SPEC-AUDIT.md записан (pass, ready), guard прогнан.

## Чего не хватило
- Ничего существенного; прошлый SPEC-AUDIT.md в каталоге документов дал перечень пунктов для сверки.
