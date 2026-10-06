# ТЗ: красный CI на verifying — вердикт по прогонам ветки и подтяжка main без возврата роли

Порядок: после группы 3.

Источник: копилка, приоритет 1 (30.09, 26.09, 27.09): задача застревает на
verifying на коммите, красном из-за main (красный унаследован от main, а не
внесён веткой); main красный из-за приложения после CI ветки; снять это
можно только reject → in_dev, то есть ещё одним шагом роли.
Решение Оператора 05.10: сделать после группы 3.

Факты (пин f7a46d84, сверка кода 05.10):
- `orchestrator/ci.py::verifying_status` (~486-549) и `branch_status`
  (~627) строят вердикт по всем check-run'ам коммита; индекс прогонов уже
  есть — `_commit_workflow_runs` (~347), `_run_of` (~384) (01M46D5ZZQ:
  событие и номер прогона в тексте статуса).
- Подтяжка main перед шагом роли — `runner.py` (~572, 01M443BPQE);
  `pull.py::_doc_only_main_advance` (~610) пропускает подтяжку, если дифф
  main только документный, а `scripts/ci_push_class.py:42` (`_DOC_PATTERN`)
  считает документным и `tasks/` — исправление main, снимающее красноту,
  может быть пропущено.
- Команды Оператора «подтянуть main в verifying» нет (список команд
  `orchestrator/artel.py` ~1616); `fsm._pull_main_or_escalate` существует.

Требуется:
1. Вердикт CI на verifying и на ожидании CI гейта мержа — по прогонам этой
   ветки задачи (head_branch — ветка задачи; оба события push и
   pull_request по-прежнему обязательны), а не по всем check-run'ам коммита.
2. Тот же упавший check красный на вершине main — статус говорит об этом
   отдельной фразой («красный унаследован от main <sha>») и подсказывает
   команду из п. 3.
3. Команда Оператора подтягивает main в ветку задачи на verifying без
   возврата к роли (тем же узлом `fsm._pull_main_or_escalate`), журналирует
   событие и оставляет задачу на verifying ждать CI новой головы.
4. При красном main подтяжка не пропускает документный дифф main
   (исправление, снимающее красноту, доезжает).
5. Тесты в `tests/` с заявками «Ловит мутацию» на пп. 1-4; существующие
   тесты не ослабляются; смена текста статуса — разделом «Меняемое
   поведение».

Зоны: orchestrator/ci.py, orchestrator/pull.py, orchestrator/fsm.py,
orchestrator/artel.py (команда), scripts/ci_push_class.py, tests/,
docs/codebase-map.md.

Только чтение: conftest.py, tests/test_invariants.py, docs/invariants.md,
docs/adr/, docs/roadmap.md, docs/backlog.md, docs/operator-session.md,
templates/, skills/, CLAUDE.md, models.yaml, roles.yaml, targets.yaml,
.github/workflows/ci.yml.

Не входит: ре-ран CI; закрытие черновых PR; полный прогон на дереве с
приложениями (01M46C776S).

Рамка: $45.
