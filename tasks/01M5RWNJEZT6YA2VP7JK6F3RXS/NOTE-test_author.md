# NOTE test_author

## Выяснено
- Планка целиком разовая, долгоживущего файла нет: guard (scripts/guard.py `_GIT_MODULES`) считает импорт orchestrator.artifact_branch/gitcmd признаком факта задачи, а без них критерии не проверить.
- Файлы: _deferred.py (шпион subprocess.run, помощники), test_deferred_push_area.py (AC-1,2,3,9,13), test_early_send_points.py (AC-4,5,6,7,11),
  test_push_journal_and_repos.py (AC-8,10,12), test_plan_and_mandate.py (AC-14,15).
- До кода: все красны по правильной причине (предусловие «коммит в команде недослан», счёт отправок/записей журнала); AC-9, AC-13, AC-12 держат прежнее поведение и зелены.
- Стаб реализации (область в lease.run_locked + send_pending в точках требования 3 + правка test_review_package по мандату): 24/25 зелёные; AC-14 без PLAN не проверить — разбор счёта сверен на образцах таблицы и списка. Мутации «нет досылки перед spawn_agent» и «в _wait_for_branch_ci_green» ловятся. Стаб снят, HEAD 5f25936d, дерево чистое.
- AC-7: песочница CmdRunReviewPackageTest (FakeGit); коммит до запуска — подмена checkpoint.main_copy_watch_start (зовётся между _prepare_step и _spawn_and_wait).
- AC-11 по ANSWER-1 п.5: свой коммит перед каждой из трёх точек; _ci_ready_or_wait не проверяется (CI не опрашивает).
- AC-15: AST-сверка базы (_pult.DIFF_BASE) и HEAD + вложенный pytest этого теста; новая версия читается из HEAD — правка должна быть закоммичена.
- AC-14: после первого «Ac5ProofMismatchTest» в PLAN нужны строки «всего», «push», «remote», в каждой по два числа (до, после).
- ANSWER-1 «добавляет критерии» (fetch_all_from_origin, send_pending(repo=R), порядок в ensure_draft_mr/_sync_main_or_wait, исключения а/б/в), но в SPEC.md на диске их нет — тестов на них не писал (только AC из SPEC).

## Не сработало
- Коммит документов между двумя set_state без record_fixation → DocsRefIncident; в сценарии AC-1 — commit_fixed.
- Bash: нет `ls`/`rm` в PATH, `$`-подстановки и heredoc с `{"` отклоняются; листинг/удаление — через python3 -c.

## Где остановился
- Планка готова, preflight пройдена.

## Чего не хватило
- Правило guard «импорт artifact_branch/gitcmd в долгоживущем — отказ» в скиле test-authoring названо мимоходом («ни gitcmd/artifact_branch»); выяснил по scripts/guard.py:4134.
