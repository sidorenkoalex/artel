# Записка developer

## Выяснено
- Возврат из verifying (CI 40230886175): `test_merge_outcome_module::test_ac14…` — `ensure` отказывал
  «обвязка … не исключена: контекст проекта не разрешён» для проекта без записи в targets.yaml.
- Исправлено в `workspace._exclude_wrapper`: при `ctx is None` — `targets.wrapper_paths()` (только
  стандартные маркеры, без agent_wrapper) + `_note_unresolved_wrapper`: журнал задачи
  `wrapper_markers_only` (одна запись на одинаковый текст), без строки задачи в БД — stderr.
  `_exclude_wrapper` теперь принимает `task_id`.
- Новый тест `tests/test_workspace_wrapper_excludes.py::test_unresolved_entry_excludes_standard_markers_without_refusal`,
  мутация (возврат отказа) — красный.
- `test_merge_outcome_module.py` — 19 passed.
- Ранее: реализация задачи готова (см. PLAN.md), планка 5/5, долгоживущие 50/50.

## Не сработало
- `pytest -n` (xdist) в шаге — воркеры падают; гонять последовательно.
- В Bash шага нет `cat`/`ls`; `$(...)` и цепочки `&&` требуют подтверждения — по одному вызову.

## Где остановился
- Сдано: 38 файлов затронутых модулей — 551 passed, планка 5/5, guard ок, PLAN.md `ready`,
  карта регенерирована, код в worktree незакоммичен (коммитит пульт).

## Чего не хватило
- Полный набор разработчику недоступен (suite-run отказывает) — регрессию вне тестов задачи
  ловит только CI; поиск вызовов `workspace.ensure` на проектах без записи — grep по tests/.
