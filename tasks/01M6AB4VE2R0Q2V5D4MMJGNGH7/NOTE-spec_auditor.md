# NOTE spec_auditor (визит 2, SPEC ea47b343)

## Выяснено
- Решения гейта №1 (А1, А2, Б1, Б2/В1, Г1, Д1, Е1–Е4) в SPEC внесены.
- Мандат HINT записан в SPEC, но гейт неослабления читает мандат только из ANSWER-n.md (test_integrity.py:1061-1085); ANSWER-файлов у задачи нет.
- gitlab 404 -> reason «не найдено (404)» (gitlab_adapter.py:204, :498): строка 1 таблицы («отказ forge» -> неизвестно) поглощает строку 2 «MR не найден».
- `git cherry` печатает коммиты ветки задачи, не базы: «найденный в базе коммит» (треб. 4, AC-6) им не получить.
- merge-base(голова, origin/base) не меняется от чужих коммитов в base — AC-3 не ловит пересчёт; меняется после вливания (= голова).
- `auto <id>` выходит в awaiting_human (auto.py:72-73, _final_stop_raises_alert) — «надзор auto раз в N минут» не определён.
- Approve из escalated (fsm.py:1705-1770) не идёт через гейт мержа — запись «принятой головы» требует правки _approve_escalated.
- `_docs_ref_unsynced` (def :1351; :1596 — вызов в target-human, done-путь :1512) печатает подсказку `approve`.

## Не сработало
- `ls` в shell недоступен — использовать find.

## Где остановился
SPEC-AUDIT.md написан (concerns, ready), guard прогнан.

## Чего не хватило
Где пульт читает строку мандата ослабления — нашлось в advance_gates/test_integrity.py::_answer_mandate.
