---
task: 01M466ZERXQKXTR5RQCDYVDZJQ
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Приложения PLAN на прогонах CI по pull_request веток задач

# ТЗ: приложения PLAN накладываются и на прогонах CI по pull_request веток задач

Источник: эскалация разработчика 01M45FJVGQT1K0P8HDEXZX6HS7 (этап 3
ADR-0021, часть 1) 05.10: код задачи по её SPEC краснеет без приложений
PLAN, прогон CI по push головы ветки зелёный (приложения наложены), а
прогон по pull_request того же sha красный (14 падений
tests/test_invariants.py) — шаг приложений его пропускает. Пульт считает
голову ветки зелёной только при зелёных check-run'ах обоих прогонов, и
задача стоит в verifying. Разово обойдено закрытием чернового PR
(решение Оператора 05.10). Части 2 и 3 этапа 3 упрутся в то же.
Решение Оператора 05.10: отдельная задача, приоритет 1.

Факты (пин b9f3dba3, сверка кода 05.10):
- `.github/workflows/ci.yml`: триггеры `push` (ветки `main`, `task/**`) и
  `pull_request` (~3-15). Шаг «приложения PLAN задачи на дереве ветки» в
  jobs `python` (~199-205) и `python-min` (~250-252) идёт только при
  `github.event_name == 'push' && startsWith(github.ref,
  'refs/heads/task/')`.
- `scripts/plan_appendix_ci.py`: входы — `GITHUB_EVENT_NAME`, `GITHUB_REF`
  (`main` ~236-245); `task_branch` (~75-80) отдаёт имя ветки только для
  push `refs/heads/task/**`, для pull_request — `None`, сценарий ничего не
  делает. PLAN читается из `refs/artifacts/<id>` в origin
  (`docs_ref_for_branch` ~83-95), приложения — `git apply` подряд,
  fail-closed на сбое git. `--check-workflow` (`check_workflow` ~221,
  `workflow_errors`) проверяет, что шаг приложений есть в jobs
  `python`, `python-min`.
- На прогоне pull_request Actions ставит `GITHUB_REF=refs/pull/<N>/merge`,
  имя ветки источника — в `GITHUB_HEAD_REF`; чекаут — merge-коммит PR с
  базой, а не голова ветки.
- Тест `tests/test_plan_appendix_ci.py::TaskBranchTest::
  test_only_task_push_is_processed` (~57-70) закрепляет
  `task_branch("pull_request", "refs/heads/task/01abc-x") is None`.
- Пульт: `orchestrator/ci.py::branch_status`/`verifying_status` читают
  все check-run'ы sha головы; черновой PR заводит
  `orchestrator/github_adapter.py::ensure_draft_mr` (~101).
- `.github/workflows/ci.yml` — защищённый путь (`config.PROTECTED_PATHS`).

Требуется:
1. На прогоне pull_request, чья ветка источника — `task/**` того же
   репозитория, шаг приложений накладывает приложения PLAN этой задачи
   тем же сценарием и тем же порядком, что на push; ветка задачи берётся
   из `GITHUB_HEAD_REF`. Чем прогон pull_request отличается от push
   (дерево merge-коммита с базой, а не голова ветки) и как это влияет на
   наложение приложений — решение SPEC с обоснованием; неприменимое
   приложение — код 1, как на push.
2. Прогоны pull_request из веток не `task/**` и из форков не меняются:
   сценарий ничего не делает, код 0.
3. Приложением к PLAN — `.github/workflows/ci.yml`: условие шага
   приложений в jobs `python` и `python-min` пропускает и pull_request
   веток `task/**`. `--check-workflow` остаётся зелёным и проверяет новое
   условие (если SPEC решит, что проверка условия нужна).
4. Смена ожидания `test_only_task_push_is_processed` (pull_request ветки
   задачи отдаёт имя ветки) — по разделу SPEC «Меняемое поведение»;
   мандат Оператора на эту смену дан (решение 05.10). Остальные
   утверждения теста (main, прочие ветки) сохраняются.
5. Тесты в `tests/` с заявками «Ловит мутацию»: pull_request ветки задачи
   накладывает приложения; pull_request прочей ветки — нет; push — как
   раньше. Существующие тесты не ослабляются.

Зоны: scripts/plan_appendix_ci.py, tests/.

Приложением: .github/workflows/ci.yml (п. 3).

Только чтение (не менять): orchestrator/, scripts/guard.py, conftest.py,
tests/test_invariants.py, docs/invariants.md, docs/adr/, docs/roadmap.md,
docs/backlog.md, docs/operator-session.md, templates/, skills/,
CLAUDE.md, models.yaml, roles.yaml, targets.yaml.

Не входит: отказ от триггера pull_request или от черновых PR; изменение
гейта CI пульта (`orchestrator/ci.py`); повторное открытие PR части 1.

Рамка: $100.
