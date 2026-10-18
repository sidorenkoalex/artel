# Записка developer

## Выяснено
- Режим несёт `guard.TestModules(load, external=False, workdir="", in_scope=None)`:
  `module_path` (перевод имени с workdir + сверка с областью), `import_path`
  (путь без workdir для относительного импорта); `_HelperScope.function` у
  внешнего пускает функцию любого модуля области.
- `test_integrity._external_helpers(conn, task_id, scope)` на `_evaluate`;
  `_compare(helpers=…)` → `_side_modules`, `_helper_callers(everywhere=…)`.
- Долгоживущий файл задачи — 5/5 зелёный после правки.

## Не сработало
- Составные Bash-команды (`sed && pytest`) требуют подтверждения — по одной.

## Где остановился
- Код готов; дальше — свои тесты guard, тесты затронутых модулей, карта, guard.py.

## Чего не хватило
- Нет.
