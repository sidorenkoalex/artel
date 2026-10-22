# Записка spec_auditor

## Выяснено
- Все якоря мутаций SPEC совпадают с кодом (canary.py 3334/3349/3372/3406/3449/3450/3457/3594/3667, artel.py 1573); worktree = f55b3ce1 по orchestrator/ и tests/.
- Планки на d4533906 есть; Coordinator/_rescue/signal_parent — _harness.py:200–280, run_cli :508 (без зависаний — сигнал _FINISHED + неблокирующее открытие FIFO).
- Строка :3406 общая для SIGTERM и SIGKILL — под M20 внук переживает и SIGKILL.
- Под мутацией AC-15 (.upper()) запись дочернего несёт set_name «DEFAULT» → live_run_note(default_set_only) = None.
- Вердикт: pass.

## Не сработало
- Команды bash с `$(...)`/циклами отклоняются — только простые grep.

## Где остановился
- SPEC-AUDIT.md готов (status: ready, verdict: pass).

## Чего не хватило
- Ничего существенного.
