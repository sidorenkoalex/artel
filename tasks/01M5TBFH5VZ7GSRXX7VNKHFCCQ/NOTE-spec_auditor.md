# Записка spec_auditor — 01M5TBFH5VZ7GSRXX7VNKHFCCQ (визит 2, SPEC sha e7bac3bf)

## Выяснено
- Ветка задачи не содержит Э1; сверка по `git -C <wt> show|grep origin/main`.
- Ссылки SPEC на строки origin/main верны: report.py:48/:565-593/:596/:1428, board.py:39/:123, targets.py:289-294, catalog.py:786, fsm.py:1070. Неточно: board_model.py «:130-135» (assert на :141), «:264-265» (assert на :269).
- Прямые вызовы внутренностей доски в tests/ — только test_report.py:213,220,230,246,255,261 — перечень матрицы полон.
- board.build_model → waiting_on → zone_lock.queue_wait → _occupies → store.task_steps на каждую in_dev-задачу с зонами (zone_lock.py:476-484): report из модели получает запросы к steps, растущие с числом задач; свойство SPEC 01M3GKJFN90ATK2KECNDZXPPP6 (test_report.py:1018) в матрице не названо, тесты зелёные (фикстуры без зон).
- Множество проектов «на каждый проект» не определено; нынешняя доска — store.all_tasks (report.py:1440), включая незаявленные проекты.
- canary_drive.py:54 зовёт cmd_new(canary=True) в артель — ref_required артели остановит канарейку; SPEC молчит.
- Миграция external_refs на живой БД (schema.migrate :267) не требуется ни требованием, ни AC.

## Не сработало
- Bash с перенаправлением/цепочками отклоняется; только одиночные git -C … show/grep.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready.

## Чего не хватило
- Нет готового знания «какие тесты держат число запросов report к steps» — искал через set_trace_callback по tests/.
