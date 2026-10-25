# Записка developer — 01M5SCGSQN0AT0B07H7M9803RA

## Выяснено
- Требования 1–14 реализованы ранее (0366c1c8, 8ede83b8).
- Возврат из verifying (CI 40193672834, 53 failed) закрыт по ANSWER-3:
  - tests/sandbox.py `RealGitSandbox.setUp`: TARGETS песочницы → `root/.artel/repo-targets.yaml`;
  - строка unlink ANSWER-2 в project_area снята (файл равен main);
  - `targets.target()` теперь берёт запись из `load()` (подмена load в тестах token_slot видна).
- Прогоны: 151 passed (token/gh/project_area/suite_run/долгоживущие), 221 passed (targets*/multitarget*/
  in_dev_gates/main_copy_watch/invariants и др.). Карта перегенерирована.

## Не сработало
- `$(...)` в Bash шага запрещён — списки файлов передавать литералом.

## Где остановился
- PLAN.md status: ready. Полный набор (ANSWER-3 п. 4) роли developer недоступен — за CI/гейтом.
- ANSWER-3: сверка диффа sandbox.py и project_area сессией при Операторе до approve merge_gate.

## Чего не хватило
- Список 51 упавшего теста CI — в брифе только число; проверял выборкой файлов на RealGitSandbox.
