# Записка developer — 01M5NNDYGQ8G6VFDEEXYBB0W3D

## Выяснено
- Шаг 2 (возврат из merge_gate 24.10): помощник origin_backlog разделён — `silence_origin_backlog`
  (литерал `docs/backlog.md`, как NoteSilenceSandbox.origin_backlog в tests/test_notes.py:309 базы) для
  тестов silence_box (window_ac5/6/7/8_closed); `origin_backlog` с notes.BACKLOG_REL остался для apply_box
  (так в исходном ApplySandbox, tests/test_notes_apply.py:145). Коммит 6dee632d; 99 passed; 1798 строк; карта
  перегенерирована; PLAN — раздел «Возврат из merge_gate (24.10)», guard ок.
- Таблицы «после» в PLAN — прогоны №4/№5 на 7ea8ae48 (до правки); по причине возврата их перепроверяет сессия,
  mutation-run повторно не запускал.
- Шаг 1: 72 патча mutation-001..072; «до» прогоны №1-3, «после» №4-5, все 72 убиты.

## Не сработало
- Bash: `sed -i` и команды с `$var` требуют подтверждения — правки через Edit.

## Где остановился
- Шаг завершён, PLAN status: ready; дальше — независимая проверка сессией при Операторе.

## Чего не хватило
- Ничего существенного; причина возврата указала строку точно.
