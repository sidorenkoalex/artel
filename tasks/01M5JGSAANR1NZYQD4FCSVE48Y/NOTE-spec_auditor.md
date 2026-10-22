# Записка spec_auditor (круг 2, spec_sha 5bde9f09)

## Выяснено
- Пункты круга 1 (матрица, маркеры мандата, таблица рубежей, _profile_refusal_exit, review.py:691, layers: []) в SPEC закрыты.
- Таблица мест снова не закрыта: вне таблицы decide() в контексте задачи — advance_gates/review.py:209 (_mutation_claim_gate; таблица ошибочно относит заявку мутации к tests_writing.py/zones.py), advance_gates/acceptance.py:73/:111/:561, advance_gates/zones.py:287, advance_gates/test_integrity.py:1299 (_external_helpers: profile None → прежняя область, не отказ), fsm_advance.py:318, fsm_merge_gate.py:1093 (full_suite_limit → TargetsError у записи из нескольких компонентов при таймауте).
- fsm_merge_gate.py:912 (_gate_profiles) — только checks_local, не «перечень долгоживущих» (он — :1393 через for_task). :858/:912 у записи из нескольких компонентов недостижимы (_selected_components раньше) — тест AC-22 их не ловит.
- Мандат: AC-13/14 не ловят «любой компонент записи» без условия границы.
- Подслучай «г» Ac14 и Ac5 совместимы с SPEC.

## Не сработало
- bash: ls нет, $(...)/${...} в команде требуют подтверждения — python3 -c для выборок.

## Где остановился
- SPEC-AUDIT.md: status ready, verdict concerns.

## Чего не хватило
- Полного перечня decide()-мест: grep `project_profile\.decide(` по orchestrator/ — главный инструмент.
