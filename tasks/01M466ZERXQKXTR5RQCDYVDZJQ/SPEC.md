---
task: 01M466ZERXQKXTR5RQCDYVDZJQ
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: scripts/plan_appendix_ci.py, tests/
budget_usd: 40
---

# SPEC: приложения PLAN накладываются и на прогонах CI по pull_request веток задач

## Контекст
Пульт считает голову ветки задачи зелёной, только когда зелены check-run'ы
обоих прогонов её sha — по push и по pull_request чернового PR
(`orchestrator/ci.py::branch_status`/`verifying_status`). Шаг приложений
PLAN в jobs `python` и `python-min` `.github/workflows/ci.yml` идёт только
при `github.event_name == 'push'`, а `scripts/plan_appendix_ci.py::task_branch`
для pull_request отдаёт `None`: прогон по pull_request идёт без приложений
и краснеет там, где прогон по push зелёный (эскалация
01M45FJVGQT1K0P8HDEXZX6HS7, 05.10 — 14 падений `tests/test_invariants.py`).
Задача стоит в `verifying`; части 2 и 3 этапа 3 ADR-0021 упрутся в то же.

Решение SPEC о дереве прогона pull_request (требование 1 ТЗ). На
pull_request `actions/checkout` выкладывает merge-коммит PR с базой
(`GITHUB_REF=refs/pull/<N>/merge`), а не голову ветки. Приложения
накладываются на это дерево как есть, без перевыкладки головы ветки:
дерево «ветка, слитая с базой, плюс приложения PLAN» — ровно то, на чём
ворота мержа накладывают приложения перед мержем в main, поэтому
неприменимость приложения на нём — та же находка, которую иначе принесли
бы только ворота мержа. Отличие от push сводится к этому: приложение,
легшее на голову ветки, может не лечь на merge-коммит, если база после
отведения ветки поменяла строки, которые приложение трогает, — тогда
прогон pull_request красный (код 1), как и на push при неприменимом
приложении. Порядок наложения, источник PLAN (ссылка документов задачи в
`origin`) и fail-closed на сбое git — те же, что на push.

## Требования
1. На прогоне pull_request, чья ветка источника — `task/**` того же
   репозитория, `scripts/plan_appendix_ci.py` (запуск без аргументов)
   накладывает приложения PLAN задачи этой ветки тем же сценарием и тем
   же порядком, что на push; имя ветки задачи берётся из
   `GITHUB_HEAD_REF` (вид `task/<id в нижнем регистре>-<слаг>`).
   Приложения накладываются на дерево чекаута прогона (merge-коммит PR с
   базой) — см. «Контекст». Неприменимое приложение — код 1 с номером и
   путями приложения в выводе, как на push; сбой git на чтении `origin` —
   код 1, как на push.
2. Прогон pull_request из ветки не `task/**` и прогон pull_request из
   форка (в том числе из ветки форка с именем `task/**`) не меняются:
   сценарий ничего не делает, git не зовёт, код 0.
3. Прогоны push не меняются: пуш `task/**` накладывает приложения, как
   раньше; пуш `main` и прочих веток — ничего не делается, git не зовётся,
   код 0.
4. Приложением к PLAN — `.github/workflows/ci.yml`: условие шага
   приложений в jobs `python` и `python-min` пропускает, кроме пуша
   `task/**`, и прогоны pull_request из веток `task/**`.
5. Сторож `--check-workflow` проверяет и условие шага: шаг приложений,
   чьё условие `if:` допускает только событие push (сравнивает
   `github.event_name` с `'push'` и не упоминает `pull_request`), —
   нарушение с именем job. На `.github/workflows/ci.yml` с приложением
   требования 4 сторож зелёный (код 0). Шаг без условия `if:` или с
   условием, не сравнивающим событие, нарушением по условию не считается
   (существующие синтетические тексты сторожа остаются без нарушений).
6. Свойства требований 1-3 и 5 закреплены тестами в `tests/` с заявками
   «Ловит мутацию»; существующие тесты не ослабляются. Долгоживущие
   приёмочные тесты автора тестов в `tests/` это требование покрывают —
   повторять их отдельными тестами не нужно.

## Критерии приёмки
AC-1. Прогон pull_request (`GITHUB_EVENT_NAME=pull_request`,
`GITHUB_REF=refs/pull/<N>/merge`, `GITHUB_HEAD_REF=task/<id>-<слаг>`, ветка
того же репозитория) при ссылке документов `refs/artifacts/<id>` в
`origin` с PLAN, несущим применимые приложения: сценарий накладывает их
все в порядке PLAN на дерево чекаута, ничего не коммитит, код 0.

AC-2. Тот же прогон pull_request, но приложение PLAN не накладывается на
дерево чекаута: код 1, в выводе — номер приложения и его пути.

AC-3. Прогон pull_request из ветки не `task/**` (например
`GITHUB_HEAD_REF=feature/x`): код 0, git не вызывается ни разу.

AC-4. Прогон pull_request из форка с `GITHUB_HEAD_REF=task/<id>-<слаг>`:
код 0, git не вызывается ни разу.

AC-5. Прогоны push не изменились: пуш `refs/heads/task/<id>-<слаг>`
накладывает приложения PLAN задачи, как раньше (код 0 при применимых);
пуш `refs/heads/main` и `refs/heads/feature/x` — код 0 без вызова git.

AC-6. `scripts/plan_appendix_ci.py --check-workflow <файл>`: на тексте
workflow, где в job `python` или `python-min` условие шага приложений
`github.event_name == 'push' && startsWith(github.ref, 'refs/heads/task/')`
(прежнее, без `pull_request`), — код 1 и нарушение с именем этого job; на
тексте, где условие шага в обоих jobs пропускает и pull_request веток
`task/**`, — код 0.

## Меняемое поведение
- `tests/test_plan_appendix_ci.py::TaskBranchTest::test_only_task_push_is_processed`: `task_branch("pull_request", "refs/heads/task/01abc-x") is None` → `pull_request ветки задачи того же репозитория (GITHUB_HEAD_REF task/01abc-x) отдаёт имя ветки "01abc-x"` (требование 1)

Остальные утверждения метода (пуш `task/**` отдаёт `"01abc-x"`, пуш
`refs/heads/main` и `refs/heads/feature/task` — `None`) сохраняются; мандат
Оператора на эту смену — решение 05.10 (ТЗ, п. 4).

## Оценка объёма и деление
Сработавший сигнал: `budget_usd` ≥ $30 (6 критериев, зона — один модуль
`scripts/plan_appendix_ci.py` и `tests/`, плюс приложение к защищённому
`.github/workflows/ci.yml`; рамка ТЗ — $100).

Материал для решения «монолит» (решение — за Оператором на гейте SPEC):
резать нечего. Смена сценария (требования 1-3, 5) без приложения к
workflow (требование 4) ничего не чинит — шаг на pull_request не
запускается; приложение к workflow без смены сценария даёт на pull_request
код 0 «не пуш ветки task/**» — тоже ничего не чинит. Обе половины
мержатся вместе: приложение PLAN едет только с кодовой веткой своей задачи
через ворота мержа, отдельной задачей без кода его не провести.

## Не входит
- Отказ от триггера `pull_request` или от черновых PR
  (`orchestrator/github_adapter.py::ensure_draft_mr`).
- Изменение гейта CI пульта (`orchestrator/ci.py`).
- Повторное открытие PR части 1 этапа 3 (01M45FJVGQT1K0P8HDEXZX6HS7).
- Перевыкладка головы ветки вместо merge-коммита на pull_request — решено
  накладывать на дерево чекаута (см. «Контекст»).
- Терпимость к приложению, уже наложенному в базе (`git apply --reverse
  --check`, как у ворот мержа в `orchestrator/fsm_merge_gate.py`): ТЗ её
  не требует, на push сценарий ведёт себя так же.
- Только чтение (ТЗ): `orchestrator/`, `scripts/guard.py`, `conftest.py`,
  `tests/test_invariants.py`, `docs/invariants.md`, `docs/adr/`,
  `docs/roadmap.md`, `docs/backlog.md`, `docs/operator-session.md`,
  `templates/`, `skills/`, `CLAUDE.md`, `models.yaml`, `roles.yaml`,
  `targets.yaml`.
- `.github/workflows/ci.yml` правится только приложением к PLAN
  (защищённый путь, `config.PROTECTED_PATHS`); применимость приложения
  проверяет разработчик `git apply --check` перед сдачей.
- Зелёный полный набор `tests/`, зелёный CI ветки, неизменность
  защищённых путей и непревышение бюджета — их держит пульт.

## Материалы
- ТЗ: `tasks/01M466ZERXQKXTR5RQCDYVDZJQ/TZ.md`.
- Сценарий: `scripts/plan_appendix_ci.py` (`task_branch` ~75-80, `run`
  ~142-176, `workflow_errors` ~199-218, `main` ~236-244).
- Workflow: `.github/workflows/ci.yml` — триггеры ~3-15, шаг приложений
  в `python` ~199-205 и `python-min` ~250-252, сторож в job `guard` ~48-49.
- Тест: `tests/test_plan_appendix_ci.py::TaskBranchTest` ~55-81; сквозной
  долгоживущий — `tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py`.
- Исходная задача сценария: SPEC 01M443HV9SJYVYQTHJSQ87QV68.
