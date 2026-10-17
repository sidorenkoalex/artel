# Записка developer — 01M55VGDHXQ55YR2YXXBPAHTNB

## Выяснено
- Правка — только `orchestrator/advance_gates/zones.py::_zones_gate`: после `out_of_zone`, у не-артели, `project_profile.decide(target)`; profile → фильтр `is_long_lived`, refusal → причина дописывается к detail («— свои долгоживущие файлы задачи зоной не признаны: <причина>»), skip → ничего.
- Долгоживущий файл задачи 8/8 зелёный; test_zones_gate, in_dev_gates, external_flow, zone_mandate_commit, gate_framework/smoke, answer_mandate — зелёные.
- Карта регенерирована (docs/codebase-map.md — в COMMON_ZONES).

## Не сработало
- —

## Где остановился
- PLAN.md ready, guard ок. Полный набор НЕ прогнан: `suite-run` дважды отказал — машину занимал прогон задачи 01M55VDVVDVWW2MTJ01F88N5FM; его держат CI и гейт приёмки. plank-run: «планки нет» (acceptance_tests/ пуст — ожидаемо).

## Чего не хватило
- —
