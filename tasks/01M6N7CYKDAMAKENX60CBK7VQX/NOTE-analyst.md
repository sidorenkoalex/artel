# Записка analyst — 01M6N7CYKDAMAKENX60CBK7VQX

## Выяснено
- Часть 1 (904cb6ed) в ветке. Факты ТЗ сверены с кодом ветки (HEAD 2b62f8a03), номера строк совпадают: targets.py:25-33 (пары), :292-313 (`unsupported_reason`), :622 (`_check_delivery`), :1137-1160 (`_check_full_suite_source`, признак `getattr(_hosting_registry().get(hosting), "job_test_report", None)`); doctor/project_checks.py:37-75 (`project_entry_checks`), :668/:740-750 (`CI_FILE`, `check_ci_file_no_paths`); ci.py:1793-1837 (`trigger_rerun`, отказ GitLab через `_pipeline_project`/`_forge_refusal`); cleanup.py:245 (`_close_project_pr`), :296-333 (`_forge_of(target) == "github"` — литерал в cleanup, условие закрытия PR).
- ci_rerun.py: путь зависшей проверки зовёт `ci.check_run_workflow_run` (это `gh`) ДО `trigger_rerun` (ci_rerun.py:220-231) — отказ «без gh» для проекта людей не наследуется из `trigger_rerun` целиком, нужен ранний отказ в ci_rerun (зона ТЗ это позволяет).
- Прогон «ожидаются зелёными» на ветке до правок: awaiting_holds, awaiting_human_units, gitcmd_push_point, push_hook_stand, mr_delivery_units — 91 passed.
- Кроме трёх файлов ТЗ, тесты части 1 (`test_01m6m1799..._github_mr_gate.py:367`, `_github_mr_units.py:151`) и `test_01m6f3dkm3..._verify_flow.py:243` подменяют `SUPPORTED_PAIRS` объединением — после открытия пары остаются зелёными.
- Правка трёх файлов из ТЗ — перенос параметра из отказных в поддержанные (удаление параметра/смена вида) + тексты в модульных константах: в «Меняемое поведение» не оформляется → вопрос 1 батча (мандат).
- Сигналы объёма: 11 критериев, 8+ файлов зоны, рамка $40 ≥ $30; таблица калибровки на этот класс — ~$85 → вопрос 2.

## Не сработало
- grep|xargs и подстановки в Bash отклоняются политикой — искать через python3 -c.

## Где остановился
- Написан QUESTIONS.md (2 вопроса), SPEC.md не создавался.

## Чего не хватило
- Правила, можно ли в SPEC сослаться на мандат, который ТЗ сам откладывает («решает Оператор»), — нашёл в docs/operator-gates.md:115-122 («выносятся вопросом до гейта SPEC»).
