# Записка аналитика

## Выяснено
- Имя ветки строится только в catalog.py:912; префикс `task/` ищется только в coldstart.py:59 (_max_from_branches). test_coldstart ветки `task/t015-…` — при шаблоне по умолчанию правка, вероятно, не нужна.
- Отправки (push): github_adapter.py:166,241 (ветка задачи на входе в verifying, forge github); fsm_merge_gate.py:744 (ветка), :1316 (в base!); cleanup.py:265,268 (--delete ветки задачи); artifact_branch.py:427, snapshot.py:297 (refs/artifacts); artifact_cleanup.py:103 (--delete); notes.py:1212,1421, pool_seal.py:303 (не проект); doctor/project_checks.py:98 (dry-run в refs/artifacts), doctor/artifact_branches.py:140.
- Подтяжка на in_dev→verifying: fsm_advance.in_dev (:771) → fsm._pull_main_or_escalate (fsm.py:236) → pull.evaluate (pull.py:762), merge — pull._run_merge (:535), конфликт — pull._handle_merge_failure (:543). pull.py и fsm.py в зонах ТЗ нет.
- А0 в origin/main (5705cfdf8), в рабочей копии ветки ещё нет: targets.unsupported_reason отказывает target-human → до Б2 живы только github+operator.
- Главный конфликт: белый список при «шаблон ≠ умолчания ИЛИ gate ≠ operator» отказывает отправке в base (fsm_merge_gate.py:1316) и удалению ветки (cleanup.py) у operator-проекта с шаблоном; ADR-0029 п.13 — только target-human.

## Не сработало
- ls в Bash недоступен (eval: command not found) — использовать Read/grep.

## Где остановился
- QUESTIONS.md записан (6 вопросов, guard ок), SPEC не писался. После ANSWER — писать SPEC и удалить QUESTIONS.md.

## Чего не хватило
- Где на самом деле живёт подтяжка входа в verifying (ТЗ называет fsm_advance, а merge — в pull.py/fsm.py).
