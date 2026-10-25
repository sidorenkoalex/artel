# Записка analyst — 01M5TB6VDVV6AM8DWPGVQE8CDW

## Выяснено
- Редакция 2 SPEC по возврату с гейта 26.10 (Е-1, Е-2, В-1, В-2, А-1, Б-2; монолит, budget 70): 12 требований, AC-1..AC-17.
- Е-2: первые записи approve гейта SPEC — fsm.py ~1288 (журнал declared/replaced), ~1304 (ACCEPTED_FAIL), ~1310 (zones/merge_after), ~1323 (потолок); проверки деления должны стоять до ~1288. «БД без изменений» трактовано как снимок всех таблиц, кроме записей журнала «approve отклонён» (так отказывают прочие проверки гейта, ~1242-1287).
- Е-1: merge_after.check строит граф только по строкам БД (merge_after.py:173) — для частей нужен виртуальный граф; ссылка части на родителя — отказ «мёртвая зависимость».
- Существующие тесты не задеты: «[поделена: ids]» родителя тестами не держится (test_parent_task_division держит только «[часть N/M родителя]»); division-фикстуры test_merge_after_module/test_division_parent_cleanup — цепочки «после части N» без ссылок на родителя; test_guard_division_section — «Рамка: $15».
- Чистые перечисления ("done","killed"): models.py:1413, zone_lock.py:538, cleanup.py:543, prune.py:209, watch.py:41, doctor/branch_freshness.py:40, doctor/ignored_artifacts.py:36, doctor/orphans.py:188, doctor/artifact_branches.py:85,97,230.

## Не сработало
- `ls` в shell недоступен; составные grep с `\|` и `;` иногда требуют подтверждения — дробить на одиночные команды.

## Где остановился
- SPEC.md записан (status: ready), guard ок, spec_unclassified_paths пуст. Шаг закончен.

## Чего не хватило
- Где approve гейта SPEC делает первую запись — искал по fsm.py:1194-1336.
