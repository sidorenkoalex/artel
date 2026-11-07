# Записка analyst

## Выяснено
- ТЗ достаточно; SPEC.md написан (7 AC, budget 40, монолит), guard ок.
- Факты ТЗ сверены с кодом: `_refuse_if_main_red` fsm_merge_gate.py:607-650, `_await_main_ci` :653-692, вызовы :1547/:1570.
- Существующий `tests/test_main_ci_line.py::AwaitMainCiUnknownTest` ждёт «не дождался» в записи при неизвестном исходе после мержа — текст надо сохранить.
- `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py:491-494` ждёт запись MAIN_CI_AFTER_MERGE_ACTION после мержа.
- Ни один тест гейта мержа по grep не подаёт `ci.MAIN_RUNNING` в `main_line_status` (только pin_update, main_ci_line, ci_event) — новое ожидание их не должно задеть.

## Не сработало
- sed после cd в Bash отклонён правилом — читать через Read.

## Где остановился
- Шаг закончен: SPEC status: ready.

## Чего не хватило
- Ничего существенного.
