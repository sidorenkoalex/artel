# Записка developer

## Выяснено
- Реализация: artel.py `_approve_note_kwargs` + `NOTE_FLAG` в `_approve_reason_indices`; fsm.py `SPEC_GATE_NOTE_FLAG/ACTION`, `_spec_gate_note_text` (до lease), повтор в `_cmd_approve`, запись после `set_state` tests_writing в `_approve_spec_gate`; brief.py `spec_gate_note`, `_spec_gate_note_component`; review.py `_spec_gate_note_part`.
- Долгоживущий файл 25/25 и планка AC-13 зелёные.
- Приложения skills/* в PLAN проверены `git apply --check` (из stdin, т.к. запись в /tmp требует подтверждения).
- `artifact_source.resolve` всегда даёт foreign=True — чтение SPEC до lease как в `_as_epic_goal`.

## Где остановился
- Шаг завершён: docs/operator-gates.md дополнен, карта регенерирована, свой сторож tests/test_approve_note_call_shape.py (мутации проверены), соседние тесты зелёные, guard ок, PLAN status: ready. Код не закоммичен — коммитит пульт.

## Не сработало
- Перенаправление вывода в /tmp — нужна approval; ls/cat в шелле недоступны.

## Чего не хватило
- Формат приложений PLAN (раздел «## Приложение …» с блоком ```diff) — нашёл в `guard.plan_appendices`.
