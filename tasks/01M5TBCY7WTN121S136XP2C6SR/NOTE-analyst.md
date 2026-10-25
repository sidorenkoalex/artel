# Записка analyst — 01M5TBCY7WTN121S136XP2C6SR (Э2а), шаг 3 (возврат с гейта по аудиту 2, 26.10)

## Выяснено
- Кода Э1/Э0 в main по-прежнему нет (`epic_id|closed_as|start_after` — grep по orchestrator/ пуст).
- Начисление в runner: `charge_missing_result` :1824 и `charge_step` :1839, общий хвост `budget.check_program_spend` :1843; в pause — `charge_missing_result` :154.
- `auto.py:966-968` — неузнанный отказ run → подсказка «budget … или kill» + alert=True; тексты остановок AUTO_STOP_* лежат в config.py (только чтение) — тексты конверта/start_after должны жить вне config.
- `merge_after.check` отказывает killed на :158 — отсюда подстановка поделённой ДО check (решение 4). Журнал деления «поделена на: …» — fsm.py:978.
- Мандат: `value_refusals` :358, `mandate_value` :382.

## Не сработало
- В Bash нельзя `; echo rc=$?` (отказ «simple_expansion») — запускать guard без него.

## Где остановился
- SPEC редакция 3: 20 требований, AC-1…AC-26, зоны +pause.py, +auto.py (13 модулей + tests/); все 7 решений аудита 2 внесены; guard: ок; status ready; budget 50; монолит — решение Оператора.

## Чего не хватило
- Кода Э1 (`board.py`, `epics.py`) для сверки имён и формулы «потрачено».
