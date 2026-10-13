## Выяснено
- Второй аудит (SPEC sha 09ecd797…): все 6 пунктов решения Оператора №1 отражены; вердикт pass.
- Имена записок: scripts/guard.py:1907-1924 (STEP_NOTE_ROLES, is_step_note — первый уровень, parent.parent == "tasks").
- Выкладка: runner.role_cwd (runner.py:1089-1162) -> artifact_branch.materialize_task_dir (:604-654); запасной путь runner.py:1160-1161 _place_harvested_docs; при сбое чтения диск не трогается.
- Единственный путь шага: run_agent_once (runner.py:749) -> _prepare_step (:1380) -> role_cwd (:1466), отказ OSError -> "agent run SKIPPED" (:1465-1473). doctor/isolation.py:102 зовёт role_cwd(None, None, target).
- Автокоммит записки не удаляет: checkpoint.py:184 (_DELETABLE_ARTIFACT_TYPES = questions), :1129-1143.
- docs/codebase-map.md в COMMON_ZONES (config.py:799).

## Не сработало
- Bash с переменной/`;` требует подтверждения — только одиночные команды с абсолютными путями.

## Где остановился
- SPEC-AUDIT.md записан, guard ок, status ready, verdict pass (с замечанием о трактовке условия отказа AC-4).

## Чего не хватило
- Нет.
