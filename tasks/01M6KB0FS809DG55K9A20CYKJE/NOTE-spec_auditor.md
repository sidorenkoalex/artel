# Записка spec_auditor

## Выяснено
- Аудит №5 (spec_sha 9b5a0f16…), вердикт concerns, две находки.
- П-1. Ни один AC не проверяет, что шаг (cmd_run → _run_attempts → run_agent_once → _spawn_and_wait) передаёт в spawn_agent аргумент nproc_limit. AC-1 и AC-2 зовут spawn_agent напрямую. Вызов runner.py:1805 без аргумента проходит все AC.
- П-2. В tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py:111 список PROCESS_INFO_TOOLS содержит "sysctl", а :553–556 пропускают его к настоящему subprocess.run. Значит, утверждение SPEC «песочница бросает FileNotFoundError на sysctl» неверно, и тест не проверяет живучесть строки doctor при FileNotFoundError.
- Подтверждено: auto.py:971/:1017 (остановка с alert=True; в её подсказке «budget/kill»). lease.run_task_command пропускает SystemExit наружу. run_agent_once зовёт только runner.py:902. Тесты, подменяющие run_agent_once (test_git_fixation.py:1186, zone_queue_start.py:476), дают подмене любые kwargs — mock совместим. Дифф skills/test-authoring.md ложится: blob 5757841ad, контекст на :364–367.
- SpyRun (tests/sandbox.py:1308) отвечает пустым успехом на любую команду. При счёте процессов это даёт запись-предупреждение на каждый cmd_run под SpyRun, в том числе на CI. Это принято решением Оператора (возврат 4, п. 3), отклонением не считается.

## Не сработало
- В Bash отклоняются ls и awk; работают grep и sed.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Ничего существенного.
