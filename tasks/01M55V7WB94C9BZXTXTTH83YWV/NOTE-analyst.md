# Записка analyst

## Выяснено
- Итерация 2 (возврат из spec_gate 18.10, пять решений Оператора по аудиту) — все пять внесены в SPEC:
  (1) требование 2: прежняя форма вызовов ci.gh/head_sha/check_runs/run_list/find_run_id/trigger_rerun у артели (ci._repo_kwargs, ci.py:83-95), перечень подмен в тестах (test_invariants.py:326-328, test_ci_status.py:160/367/372/798, test_main_ci_line.py:62, test_merge_gate_ci_wait.py:82); «Материалы» исправлены;
  (2) accepted_full_suite в AC-1;
  (3) GH_REPO и без token_slot — в требовании 1, новый AC-8;
  (4) разбор url по gitcmd.url_key (gitcmd.py:44-46), учебный проект AC-2 с url на .git или /;
  (5) сценарии AC-2/AC-3: _inherited_from_main, _commit_workflow_runs с check_suite.id, find_run_id при ≥2 красных, check_run_workflow_run; run_list без проверок.
- Ссылки на код сверены по рабочему каталогу (ci.py:39-95, gitcmd.py:44-46, тесты).

## Не сработало
- Bash с несколькими cat по каталогу документов просит подтверждения — читать Read'ом.

## Где остановился
- SPEC.md: status ready, 8 AC, budget_usd 35 (рамка ТЗ), обоснование монолита; guard ок.

## Чего не хватило
- Ничего.
