## Выяснено
- Возврат со spec_gate 17.10: шесть пунктов Оператора внесены в SPEC (status: ready, guard ок).
- Добавлено: точка advance_gates/acceptance.py:387-405 и :169 (требование 1, новый AC-12 — дописан в конец, чтобы не сдвигать номера AC-3/6/7/8, на которые ссылается Оператор).
- amend.py:715-718: у pytest-own cwd = wt_path, workdir от неё; у pult-pytest — как было.
- AC-3/6/7/8 расписаны по двум точкам каждый; AC-4 — ключ итога suite_run.py:511/:533.
- Канал: command у run/run_repeat/collect/full_suite, profile у run_plank и two_sided.run (acceptance.py:1096-1097, two_sided.py:319-320).
- pult-pytest у внешних — поведение прежнее (требование 4, AC-10, «Не входит»).
- Профиль части 2: `acceptance._task_own_profile` / `_own`; гейт мержа — `fsm_merge_gate._full_suite_command` (:804-820).

## Не сработало
- Цепочки команд через `echo` в Bash требуют подтверждения — читать файлы через Read.

## Где остановился
- Шаг завершён.

## Чего не хватило
- Полного перечня вызывающих мест запуска с каналом профиля — его дал аудит, не карта.
