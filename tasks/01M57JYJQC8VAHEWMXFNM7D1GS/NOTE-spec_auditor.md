# Записка spec_auditor — 01M57JYJQC8VAHEWMXFNM7D1GS

## Выяснено
- Места из SPEC «Материалы» сверены: acceptance.py run :600, collect :737, materialize_from_branch :929, drop_from_code_copy :1134, plank_in_code_copy :1146, run_plank :1166, _own_* :188/:213/:231; plank_run.py :227/:241; amend.py :550/:725; checkpoint.py:1796 `add -A`; runner.py:1218 drop на старте шага — всё подтвердилось.
- run_plank(targets, cwd, profile) не знает task_id: пути планки приходят строкой `tasks/<id>/acceptance_tests[/файл[::узел]]` (plank_run.py:238-239, _selected :66-77).
- amend-tests планку не выкладывает materialize_*: правка Оператора на диске + plank_helper_laid_out (amend.py:684) — требование 2 SPEC про «штатную выкладку» к amend буквально не подходит.
- Полный набор внешнего проекта идёт по самой рабочей копии (appendix_tree.suite_tree :260) — невидимый git-у остаток в long_lived_dir pytest соберёт; clean_tree_sha (acceptance.py:1798) при этом сочтёт дерево чистым.
- Существующие тесты узнают вызов планки по подстроке "acceptance_tests" в argv (test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py:269, :716) и проверяют «планка не прогонялась» по пути tasks/<id>/acceptance_tests (test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py:345-348) — имя каталога выкладки SPEC не задаёт.
- `**/conftest.py` — защищённый путь (config.py:763): учебный проект с backend/tests/conftest.py файлами в tests/ упрётся в гейт зон.

## Не сработало
- grep с `cd … &&`/`--include=*.py` отклонялся песочницей — нужны абсолютные пути.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns, 14 отклонений; guard.py — ок.

## Чего не хватило
- Нет готового перечня тестов, закрепляющих форму argv планки pytest-own; искал grep по "acceptance_tests" в tests/.
