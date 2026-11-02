# Записка spec_auditor — 01M6EZXVFGXC6WBDA9QJESAZRW

## Выяснено
- Аудит 2 (spec_sha 0616c5df…): пять отклонений первого аудита сняты решением Оператора №1 и перенесены в SPEC (требования 1–7, 12; AC-5, AC-8, AC-12).
- Новое: между resolve (fsm_merge_gate.py:1508) и people_entry (:1516) стоит _profile_refusal_exit (:1514). Он читает targets.target через project_profile.decide → repo_context.resolve/profile_of и при TargetsError даёт sys.exit + MERGE_PROFILE_REFUSAL_ACTION. Шов AC-1 «после resolve» туда и попадает.
- AC-6 маскируется: отказ требования 1 на :1516 той же формы и с той же причиной срабатывает раньше _awaiting_limit_refuses (:1630).
- forge.MergeRequest.state по умолчанию None (forge.py:71) — в AC-13 не назван.
- Гейт неослабления сравнивает только утверждения (guard.py:2286, :5909), смена входа заглушки допустима.

## Не сработало
- `ls`, `$(...)` и пайпы в Bash требуют подтверждения: читать через Read и grep без подстановок.

## Где остановился
- SPEC-AUDIT.md записан: verdict concerns, status ready, 4 отклонения + 1 для сведения.

## Чего не хватило
- Нет перечня чтений targets.target на пути гейта мержа до people_entry: собирал по коду (project_profile.decide, repo_context.profile_of).
