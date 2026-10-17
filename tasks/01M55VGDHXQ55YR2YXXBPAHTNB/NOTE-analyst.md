# NOTE-analyst

## Выяснено
- Гейт зон: `orchestrator/advance_gates/zones.py::_zones_gate`, общие зоны — строка 274 (`is_artel`), отказ «вне заявленных zones» — 305-334.
- Профиль: `project_profile.decide(target)` / `for_task` (project_profile.py:140-163), `Profile.is_long_lived` (116). Выход из tests_writing берёт профиль через `decide(target)`.
- Сверка зон с диффом вне zones.py есть только в `checkpoint.py`: `_zone_paths`/`_stray_staged_paths` (1564-1603) и `_commit_worktree_change` (1770-1773). Для test_author свои долгоживущие файлы уже покрыты `own_zones` (checkpoint.py:448-454), удаления — `_role_may_delete` (528). Гейт мержа и ревью-пакет зоны с диффом не сверяют (grep `zones`/`_touches_zone` пуст). Вывод: правка вне зон не нужна, эскалации нет.
- Существующий тест `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py::CommonZonesTest` берёт `tests/test_<слово>.py` без id задачи — правкой не задет.

## Не сработало
- `cd ...; grep` в Bash требует подтверждения — использовать абсолютные пути.

## Где остановился
- Шаг 3 (возврат 18.10, Д5): из AC-7 и примера требования 1 убран путь `…_x/conftest.py` (маска `**/conftest.py` в no_paths даёт отказ «защищённый путь» раньше гейта зон); в AC-7 остался `backend/tests/test_<id>_x.json`. guard — ок, status: ready.
- Шаг 2 (возврат из spec_gate 18.10): решения Оператора Д1–Д4 внесены. Д1 — требование 1 явно признаёт новый файл по шаблону от developer (паритет с артелью); Д2 — требование 1 «полный шаблон, не префикс» + AC-7 (`…/test_<id>_x/conftest.py`, `…_x.json`); Д3 — AC-6 с путём `tests/test_<id>_x.py`; Д4 — требование 2 «у задачи внешнего проекта», требование 3 и AC-8 — артель с непрочитанным test_profile, тексты прежние. 8 AC, budget 25 (рамка ТЗ), guard — ок.
- Шаг 1: SPEC.md написан, status: ready, 6 AC, budget 25; guard — ок. Guard сначала отказал по сигналу «число модулей» (считает пути, упомянутые в тексте), закрыто секцией «Оценка объёма» с обоснованием монолита и «Прогноз диффа: 12 КиБ».

## Чего не хватило
- Ничего существенного; дольше всего искал, кто ещё сверяет зоны с диффом (ответ — только checkpoint.py).
