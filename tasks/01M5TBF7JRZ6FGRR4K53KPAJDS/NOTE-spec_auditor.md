# NOTE spec_auditor

## Выяснено
- Рабочий каталог старше Э1: orchestrator/epics.py нет на HEAD ветки; сверял по origin/main (Э1 смержен, f909b7dd). MAX_PARALLEL_TASKS на origin/main — config.py:414 (в worktree :409).
- epics.cmd_epic (origin/main epics.py:359) — new/show/edit/close/add/remove; EPICS_DDL (schema.py:113) без колонки лимита — подтверждено.
- _launch_detached (artel.py:977) делает sys.exit при живом lease/отказе наблюдения; _launch_observation (artel.py:922) требует задачу в наборе названного наблюдения и свежую связь watch.
- auto останавливается в агентских состояниях (пауза, стоп-кран, бюджет, лимит шагов, отказ advance) — auto.py:714,889,902,944-967; SPEC готовность (треб. 3) таких не исключает → перезапуск по кругу.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns, 8 отклонений; guard ок.
- Главные: перезапуск по кругу после не-гейтовой остановки auto; место блокировки/журнала надзора; счёт MAX_PARALLEL_TASKS; гонка epic stop; порядок разработки после Э2а.

## Чего не хватило
- Факт, что ветка задачи до мержа Э1, — пришлось искать merge в origin/main.
