# Записка spec_auditor

## Выяснено
- Пуши от клона (`repo_context.clone_path`), не от рабочей копии: `gitcmd.git` не знает задачу — «своя/чужая ветка» (AC-11 «feature/PROJ-8 — ветка чужой задачи») не различима без нового контекста у вызывающих (github_adapter.py:166/241, fsm_merge_gate.py:744 — только чтение).
- coldstart сканирует ветки только для артели (coldstart.py:33) и только ради номера Tnnn (`_BRANCH_NUMBER_RE`, coldstart.py:24) — AC-10 по смыслу пуст.
- В SPEC нет разделов «Меняемое поведение» и матрицы, хотя AC-21 на них ссылается.
- Хук pre-push уже есть: scripts/git-hooks/pre-push; scripts/ не в зонах части 1.
- Merge-коммиты подтяжки — идентичность Оператора (workspace.inherit_identity, workspace.py:78), не commit_author.
- spawn_subtask: имя ветки строится в _new_task_row (catalog.py:912) ДО копирования ссылок (catalog.py:1032).
- `push_options` — исполнитель (добавка `-o`) не назначен ни одной части.

- Конфликт подтяжки сейчас — `escalated` + метка (pull.py:575,589), не прямой возврат в in_dev.
- `_pull_main_or_escalate` зовут ещё fsm.py:1577 и fsm_merge_gate.py:727 — AC-20 их не покрывает.

## Не сработало
- Составные bash-команды (`;`, `echo`, `cd`) песочница не пропускает — по одной команде.

## Где остановился
SPEC-AUDIT.md сдан: verdict concerns, 11 отклонений, guard ок.

## Чего не хватило
Дольше всего искал место отправки на рубеже in_dev: advance_gates/tests_writing.py:_origin_push_gate → github_adapter.ensure_head_in_origin (общий для всех forge, не только github).
