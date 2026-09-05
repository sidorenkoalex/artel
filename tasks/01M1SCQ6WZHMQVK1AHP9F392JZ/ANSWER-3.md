# ANSWER-3

Приёмка отклонена второй раз по AC-8: планка регрессии №13
(`tasks/01M1RHFRQ2C0P4A57XJJ1WZV8N/acceptance_tests`) на коде ветки 8d590bcb
красная по трём тестам — `test_ac3_gate_refuses_when_no_developer_commit_
followed_the_verdict`, `test_ac4_gate_names_the_iteration_of_the_unresolved_
review`, `test_ac7_manual_advance_on_unchanged_code_refuses_named_not_
transitions`; на main та же планка 10/10. Второй шаг разработчика (01:37)
ничего в коде не изменил.

Диагноз Оператора (по коду ветки, `orchestrator/fsm_advance.py`):
`_reviewer_verdict_baseline` возвращает `(None, None)`, если нет ни
автокоммита шага reviewer с префиксом `_REVIEWER_STEP_AUTOCOMMIT_PREFIX`,
ни записи журнала «agent run finished» роли reviewer; дальше
`_review_rework_gate_refuses` на `review_ts is None` возвращает `False` —
рубеж ОТКРЫВАЕТСЯ. В песочнице планки №13 REVIEW.md закоммичен другим
сообщением и без журнала роли — раньше рубеж брал
`_commit_iso_date(REVIEW.md)` и отказывал. Это ослабление гейта
(fail open), запрещено принципом целостности.

Что сделать: при отсутствии опоры ревьювера — брать прежнюю опору
(`_commit_iso_date` последнего коммита REVIEW.md) и сверять как до
правки; отказ — с той же именованной причиной, что в №13
(«замечания ревью не отработаны: нет шага developer после итерации N»).
Опора ревьювера, если найдена, по-прежнему приоритетна (требование 1).
Проверка: `python3 -m unittest discover -s
tasks/01M1RHFRQ2C0P4A57XJJ1WZV8N/acceptance_tests` из корня worktree —
10/10, плюс своя планка и `tests/test_fsm_review_rework_gate.py`.
Планку №13 не править. Полный `tests/` не запускать.
