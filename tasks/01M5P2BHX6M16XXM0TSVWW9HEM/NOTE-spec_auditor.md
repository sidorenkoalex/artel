# Записка spec_auditor

## Выяснено
- Существующий тест tests/test_01m5npkpwfewtymbywvr797am6_mutation_run.py:1122
  (IsolationTest.test_ac6_copy_removed_and_repositories_untouched) сверяет
  снимок содержимого каталога документов до/после прогона (:1107, :1119, :1170);
  каталог там есть (write_patches, :398) — копия mutation-run-<n>.tsv красит
  тест. Противоречие с SPEC треб. 7 / ТЗ 5 (существующие не правятся и зелены).
- Автокоммит шага после коммита удаляет каталог документов
  (orchestrator/checkpoint.py:1422, :1428); выкладка на старте шага удаляет
  файлы, которых нет в ссылке (orchestrator/artifact_branch.py:728-734).
  Прогон мутаций обычно переживает шаг (mutation_run.py:7-9; --wait ≤ 9 мин,
  config.py:243) — копия после конца шага не пишется/теряется. SPEC это не
  оговаривает.
- Предел: CUT не обрывает прогон — дальше строки NOT_RUN и штатный конец
  (mutation_run.py:546-561); AC-2 не ловит «копия целиком в конце».
- guard.py:3470 подтверждён; .tsv первого уровня не посторонний.

## Где остановился
Вердикт fail, SPEC-AUDIT.md записан.

## Чего не хватило
Как фон прогона соотносится с жизнью каталога документов — искал в checkpoint.py
(_commit_step_artifacts_to_branch) и artifact_branch.materialize_task_dir.
