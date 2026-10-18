# Записка spec_auditor — 01M56T94ZJE6H973HEBTM0Q0TD

## Выяснено
- Ссылки SPEC на код верны: suite_run.py:439 (render, id в начале строки), :579-581 (run_full_suite ветки), acceptance.py:1538-1540 (_run_full_suite_now → _to_log), :1598 (proc.wait(timeout=limit[0])); тест :119-120 standalone, :164 task_id, :515 COPY_LIMIT, :592-622 метод, :601-604 мутации, :606-614 реальные часы.
- Python CI = 3.13 (stack.CURRENT_STABLE_PYTHON), локально 3.13.12: Popen._wait — цикл с subprocess._time, подмена часов из дифа ТЗ рабочая; на версии с другим _wait (kqueue/pidfd) — нет.
- docs/codebase-map.md в config.COMMON_ZONES (config.py:803) — регенерация карты зону не нарушит.
- Классы файла (SuiteRunLimitSandbox/ProbeSandbox) больше нигде в tests/ не наследуются — changed_classes гейта неослабления вне файла ничего не найдёт.
- Вердикт: concerns (см. SPEC-AUDIT.md): AC-1/AC-2 без названной детерминированной проверки; обёртка Popen.wait в дифе против «proc.wait настоящий»; AC-3 и путь мутации по потолку --wait.

## Не сработало
- —

## Где остановился
- SPEC-AUDIT.md написан, guard прогнан.

## Чего не хватило
- Нет прямого правила, считается ли обёртка над настоящим Popen.wait «подменой» в смысле требования 2 ТЗ.
