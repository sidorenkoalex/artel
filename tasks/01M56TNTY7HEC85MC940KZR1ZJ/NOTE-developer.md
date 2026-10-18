# Записка developer

## Выяснено
- Режим несёт `guard.TestModules(load, external=False, workdir="", in_scope=None)`:
  `module_path` (перевод имени с workdir + сверка с областью), `import_path`
  (путь без workdir для относительного импорта); `_HelperScope.function` у
  внешнего пускает функцию любого модуля области.
- `test_integrity._external_helpers(conn, task_id, scope)` на `_evaluate`;
  `_compare(helpers=…)` → `_side_modules`, `_helper_callers(everywhere=…)`;
  вызывающие отсеиваются по области в цикле `_compare`.
- Шаг 2: долгоживущий файл 5/5, свои тесты guard 6/6, тесты затронутых
  модулей (test_integrity_gate, helper_heirs, guard_*) зелёные.

## Не сработало
- Составные Bash-команды (`sed && pytest`, пайпы с grep) требуют подтверждения.
- `guard.py` с файлом tests/ в аргументах считает его артефактом — гнать только PLAN.

## Где остановился
- PLAN.md status: ready, guard ок. Карта свежая (изменилась только built_at_sha).

## Чего не хватило
- Нет.
