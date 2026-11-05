# Записка spec_auditor

## Выяснено
- Второй визит (после возврата Оператора, решения 1–3): все решения внесены в SPEC (тр. 3–5, AC-4..AC-7).
- Факты подтверждены: spec_gate_decision.py:186-190, artel.py:2650-2675, fsm.py:2079-2081 ловит только DecisionError; numbered() (spec_gate_decision.py:307) тоже через parse.
- Опыт python3: '²' isdigit True/int ValueError; '３','١' isdecimal True, int ок, != str(i) → «не по порядку».
- Тексты «не сочетается»/«без значения» в tests/ только в докстрингах; assert_refused без names — не ломаются.
- Вердикт pass.

## Не сработало
- `ls` в оболочке недоступен (command not found) — пользоваться grep/sed.

## Где остановился
SPEC-AUDIT.md сдан (status: ready, verdict: pass), guard прогнан.

## Чего не хватило
Ничего существенного.
