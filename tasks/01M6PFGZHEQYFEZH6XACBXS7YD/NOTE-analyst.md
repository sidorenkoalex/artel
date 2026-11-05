## Выяснено
- Факты ТЗ подтверждены по коду: `orchestrator/spec_gate_decision.py:186-192` (`isdigit` + `int`), `orchestrator/artel.py:2650-2675` (`DECISION_FLAG`, `_cmd_reject`).
- Сейчас `--decision a --decision b` отказывает текстом «не сочетается с позиционной причиной (--decision b)» — ТЗ требует для двух ключей указание на повтор.
- `tests/test_01m6kb0sjhda4d4gnem7pgz40p_decision_reject.py::test_ac8_help_names_decision_form` ждёт в `--help` строку «reject <id> --decision <файл>» — дополняя справку формой с «=», её не убирать.
- SPEC: 9 AC, 4 зоны, budget 25 (рамка ТЗ), сигналов деления нет; guard ок.

## Не сработало
- нет

## Где остановился
- SPEC.md сдан со status: ready.

## Чего не хватило
- нет
