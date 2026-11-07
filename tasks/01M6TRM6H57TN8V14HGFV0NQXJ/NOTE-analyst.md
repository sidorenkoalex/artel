# Записка analyst

## Выяснено
- ТЗ подробное и в остальном достаточно для SPEC; эскалация батчем QUESTIONS.md (2 вопроса).
- Блокер: существующие тесты требуют «не реализовано для github» именно для job_result/job_test_report:
  tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_units.py:935-958 (test_ac16_..., параметры job_result, job_test_report);
  tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py:370-372 (GH_CALLS) + :1184-1197 (test_ac13_...). Реализация неизбежно красит 4 варианта; ТЗ запрещает правку без эскалации.
- targets._check_full_suite_source (targets.py:1299-1322) пускает full_suite: ci по наличию job_test_report в реестре — реализация у _GitHub автоматически снимет отказ загрузки GitHub-записи; test_01m5xzskk8gzteca2kwafhe029_component_fields.py::test_ac3 подменяет реестр — не краснеет.
- forge.job_test_report(target, sha, job_name) не получает компонент: ci_report_artifact адаптер найдёт по ci_job == job_name в записи.
- _GitHub.pipeline_status строит Job без id (forge.py:238) → сверка «одна попытка» в ci.job_full_suite (ci.py:1383) для GitHub пустая — вопрос 2.

## Не сработало
- Bash с `cd ...; sed` и цепочками команд отклоняется — читать Read'ом, grep одной командой с абсолютным путём.

## Где остановился
- QUESTIONS.md записан, guard прогнан. SPEC.md не писался.

## Чего не хватило
- Ничего существенного; противоречие ТЗ с тестами нашлось grep'ом «не реализовано для».
