# Записка spec_auditor

## Выяснено
- Визит 2 (spec_sha 26748fcb…): все 11 решений гейта SPEC и ANSWER-1 в SPEC отражены.
- Сжатие и rebase на fsm_advance.py:771 стоят раньше рубежа переделки ревью (fsm_advance.py:816). Рубеж смотрит на дату коммиттера %cI коммитов, кроме подтяжки (advance_gates/review.py:110-129). Переписанная ветка проходит его без шага developer — путь обхода.
- Части деления заводятся циклом в fsm.py:1070; атомарность невозможна в зонах части 1 без fsm.py. При feature/{ref} имя части = имя родителя (родитель ещё в БД в spec_gate) — отказ гарантирован, AC-8 слабый.
- ensure_head_in_origin состояние не меняет (github_adapter.py:226-229); эскалация AC-16 требует advance_gates/tests_writing.py:_origin_push_gate — не в зонах части 2.
- В gitcmd пять точек запуска git (git, carpentry, read, read_env, read_stream); при нечитаемом targets.yaml _declared_targets → {} → белый список не включится (fail-open).
- A0 уже на origin/main: targets.unsupported_reason отказывает new/run/auto/approve проектам target-human и gitlab.

## Не сработало
- Составные bash-команды и `for … $(…)` песочница не пропускает — построчные проверки делал через python3 -c.

## Где остановился
SPEC-AUDIT.md сдан: verdict concerns, 11 отклонений.

## Чего не хватило
Дольше всего искал, какие гейты опираются на историю ветки (затрагивает сжатие и rebase): advance_gates/review.py:_latest_developer_commit_iso_date.
