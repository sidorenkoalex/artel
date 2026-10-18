# Записка spec_auditor

## Выяснено
- SPEC-AUDIT.md сдан: status ready, verdict concerns, guard ок. Отклонения D1–D6.
- guard._collect_qualified_test_functions (scripts/guard.py:621,626) УЖЕ берёт AsyncFunctionDef; TEST_AC (guard.py:170) без якоря уже матчит `async def test_ac1_` (проверено python). Сломан только TEST_METHOD (guard.py:178).
- Послабление условного пропуска — только для методов, которых нет в базе; декоратор класса — всегда находка (test_integrity.py:442-449). AC-3/AC-4/AC-6 этих ограничений не называют.
- Изменённые утверждения без объявления/мандата — НАХОДКА (test_integrity.py:1105-1111), не только журнал; SPEC треб.6 сузил до наблюдения.
- Литералы «Меняемого поведения» — только из утверждений (guard.method_literal_keys, guard.py:3834): смену строки parametrize объявить нельзя.
- workdir до _compare не доходит: review.py:652, fsm_merge_gate.py:146 передают только scope-предикат.

## Не сработало
- grep с `$W`/`cd … ;` в Bash требует подтверждения — писать абсолютные пути; `cd X && cmd` работает.

## Где остановился
- Шаг закончен.

## Чего не хватило
- Где правило «послабление только новым методам» — нашёл в test_integrity._file_findings (:440-455) не сразу.
