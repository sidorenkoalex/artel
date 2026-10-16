# Записка analyst — 01M51YKZNES22DZQY13D3QKF89

## Выяснено
- ТЗ достаточно для SPEC, вопросов нет.
- Зона ТЗ — 8 элементов (sandbox.py, acceptance.py, targets.py, config.py,
  fsm_autogate.py, fsm.py, orchestrator/doctor/, tests/) → уровень
  BUDGET_CALIBRATION_TABLE $85 (config.py:629) > рамки ТЗ $60 → по самому ТЗ
  деление на D1а-1 (пп. 1–4, 8 для run/collect/run_repeat/run_plank) и
  D1а-2 (полный набор, пп. 5–7).
- Подраздел D1а-2 без targets.py (поля профиля проверяет D1а-1) → 7 зон,
  уровень $45. Фиксация argv/cwd/env всех семи мест артели (п.1) — в D1а-1.

## Не сработало
- Составные bash-команды (`;`, `|`, `cd &&`) требуют подтверждения — звать по одной.

## Где остановился
- SPEC.md (15 AC, status: ready, budget_usd 60) с секцией «## Деление»
  (D1а-1 $45, D1а-2 $45 после части 1) написан; guard: ок.

## Чего не хватило
- Формат деления пришлось искать в scripts/guard.py:3912-4050 и
  docs/operator-gates.md:136-152 — в брифе примера готового SPEC с делением нет.
