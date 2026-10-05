---
task: 01M466ZERXQKXTR5RQCDYVDZJQ
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: приложения PLAN накладываются и на прогонах CI по pull_request веток задач

## Подход

Сценарий `scripts/plan_appendix_ci.py` различает «ссылку проверяемой
ветки» и событие:

- `tested_ref(env)` (новая) — ссылка ветки, чьё дерево проверяет прогон:
  на push — `GITHUB_REF`; на pull_request — `refs/heads/<GITHUB_HEAD_REF>`,
  если голова — `task/**` и репозиторий головы из файла события
  (`pull_request.head.repo.full_name`) совпадает с `GITHUB_REPOSITORY`;
  иначе пустая строка. Файл события читается только для головы `task/**`;
  не прочитан — `CiError` (код 1, fail-closed: «форк или нет» не
  угадывается). Git здесь не зовётся — требование 2.
- `task_branch(event, ref)` — сигнатура прежняя, отбор события расширен
  на `("push", "pull_request")`; голый префикс `refs/heads/task/` — None.
  Сохранение сигнатуры — ради двустороннего прогона «Меняемого
  поведения»: старое утверждение `task_branch("pull_request",
  "refs/heads/task/01abc-x") is None` на ветке падает `AssertionError`
  (теперь `"01abc-x"`), новое на базе — тоже.
- `run` не меняется по сути: дерево — чекаут прогона как есть
  (merge-коммит PR на pull_request), порядок и fail-closed те же; сообщения
  «не пуш ветки…» → «не прогон ветки task/** того же репозитория…»,
  «на дерево ветки» → «на дерево чекаута».
- Сторож `--check-workflow` (требование 5): у шага сценария в
  `python`/`python-min` берётся условие `if:` его элемента списка
  (`_step_condition`: и `- if:` на строке дефиса, и продолжение на более
  глубоких строках); `condition_push_only` — сравнение
  `github.event_name == 'push'` без упоминания `pull_request`. Шаг без
  `if:` или без сравнения события — не нарушение.
- Сторож на прогоне ветки задачи (ANSWER-1, вариант А):
  `check_workflow_on_run(path, env)` — на прогоне ветки задачи (тот же
  отбор, что у шага приложений: `tested_ref` + `task_branch` — пуш
  `task/**` или pull_request `task/**` того же репозитория) сначала
  накладывает приложения PLAN тем же `run` на дерево чекаута, затем
  `check_workflow` проверяет ci.yml — job `guard` видит workflow, с
  которым ветка смержится. Вне CI (нет `GITHUB_*`) и на прочих прогонах —
  файл как есть, `run` не зовётся. Отказ `run` (неприменимое приложение)
  и `CiError` (сбой git, нечитаемый файл события) — код 1 без проверки
  файла. Ничего не коммитится, ссылки не заводятся (свойства `run`).
  `main(["--check-workflow", …])` зовёт его с `os.environ`.

Приложение 1 — `.github/workflows/ci.yml` (требование 4): условие шага в
обоих jobs пропускает пуш `task/**` и pull_request из `task/**` того же
репозитория (форк отсекается и условием, и сценарием).
`git apply --check` приложения на чистом дереве ветки — код 0 (проверено
перед сдачей); `--check-workflow` на ci.yml с приложением — код 0, без
приложения — код 1 с нарушением в обоих jobs.

## Шаги

1. Сценарий: `tested_ref`, расширение `task_branch`, сторож условия шага;
   юнит-тесты в `tests/test_plan_appendix_ci.py`; карта
   `docs/codebase-map.md` регенерирована. Сделано.
2. Приложение 1 к `.github/workflows/ci.yml` (ниже). Сделано, проверено
   `git apply --check`.
3. Доставка правки workflow так, чтобы job `guard` ветки был зелёным
   (ANSWER-1, вариант А): `check_workflow_on_run` + тесты
   `CheckWorkflowOnRunTest` (2 метода) в `tests/test_plan_appendix_ci.py`;
   карта регенерирована. Сделано.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`tested_ref` + `task_branch`; долгоживущий AC-1, AC-2) |
| 2 | 1 (`tested_ref`: не `task/**` и форк — без git; AC-3, AC-4) |
| 3 | 1 (push — `GITHUB_REF` как раньше; AC-5) |
| 4 | 2 (приложение 1) |
| 5 | 1 (`_step_condition`, `condition_push_only`; AC-6) |
| 6 | 1 (тесты с заявками «Ловит мутацию»; долгоживущие не тронуты) |

Прогоны в шаге (передний план, таймаут 120 с на тест):
`tests/test_plan_appendix_ci.py`,
`tests/test_01m466zerxqkxtr5rqcdyvdzjq_plan_appendix_ci_pr.py`,
`tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py`,
`tests/test_codebase_map.py` — 55 passed. Временные мутации сценария
(событие только push; снят отбор события; снята сверка форка; pull_request
по `GITHUB_REF`; сторож без условия; без склейки продолжения `if:`) —
каждая красит `tests/test_plan_appendix_ci.py`.

Итерация после ANSWER-1: те же три файла сценария — 23 passed;
`tests/test_plan_appendix_ci.py` + `tests/test_codebase_map.py` — 47
passed. Мутации `check_workflow_on_run`: наложение не зовётся (условие
`False`) и код `run` игнорируется — оба метода `CheckWorkflowOnRunTest`
красные. `artel.py plank-run` — «планки нет» (у задачи только
долгоживущие файлы в `tests/`, прогнаны выше). `git apply --check`
Приложения 1 на дереве ветки — код 0.

## Влияние на систему

- Существующий метод `TaskBranchTest::test_only_task_push_is_processed`:
  меняется ровно утверждение из раздела SPEC «Меняемое поведение»
  (`None` → `"01abc-x"`), остальные три утверждения на месте, имя метода
  то же. Прочие методы не тронуты; добавлены
  `TaskBranchTest::test_other_events_and_bare_prefix_are_skipped`,
  `TestedRefTest` (3 метода),
  `WorkflowErrorsTest::test_push_only_condition_in_dash_and_multiline_forms`,
  `CheckWorkflowOnRunTest` (2 метода).
- Сторож шага строже: добавлено нарушение, ни одно прежнее не снято.
- **Job `guard` в CI ветки задачи** (ANSWER-1, вариант А). Его шаг
  `--check-workflow .github/workflows/ci.yml` на прогонах веток задач
  теперь сначала накладывает приложения PLAN: появляется git
  (`ls-remote`/`fetch` ссылки документов из `origin`) в job `guard` на
  ветках `task/**`; неприменимое приложение или сбой git красят и
  `guard` — как и `python`/`python-min`. На `main` и прочих прогонах
  сторож прежний. Модифицированный ci.yml остаётся только в дереве
  раннера; шаг сторожа — последний в job `guard`.
- Откат: revert merge-коммита задачи (сценарий, тесты и ci.yml вместе).

## Риски

- pull_request из ветки задачи, где база поменяла строки приложения, —
  красный прогон pull_request (решение SPEC, «Контекст»): находка ворот
  мержа раньше.

## Предложения системе

- Сторож защищённого файла, который сам меняется приложением PLAN
  (`--check-workflow` в job `guard`), проверяет файл без приложений:
  любая задача, ужесточающая такой сторож вместе с правкой файла,
  красит CI своей ветки по построению. Аналитику SPEC стоит сверять это
  (скил spec-authoring: «сторож защищённого пути + приложение — где
  сторож видит приложение?»).

## Приложение 1: условие шага приложений PLAN в jobs python и python-min

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index 8b4b4583..63bc280f 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -197,11 +197,13 @@ jobs:
       - name: зависимости из файла закреплённых версий (01M1REVEZ1HESMJ7AFD5A9MEJ8, требование 3)
         run: python3 -m pip install -r requirements.lock
       - name: приложения PLAN задачи на дереве ветки (01M443HV9SJYVYQTHJSQ87QV68, требование 1)
-        # Только пуш task/**: тесты идут на дереве «код ветки плюс
-        # приложения её PLAN» (PLAN — из ссылки документов задачи в
-        # origin). Ничего не коммитит и не пушит; шаг стоит до снимка
+        # Пуш task/** и pull_request из ветки task/** того же репозитория
+        # (01M466ZERXQKXTR5RQCDYVDZJQ): тесты идут на дереве «код ветки
+        # плюс приложения её PLAN» (PLAN — из ссылки документов задачи в
+        # origin); на pull_request — на merge-коммите PR с базой, как у
+        # ворот мержа. Ничего не коммитит и не пушит; шаг стоит до снимка
         # ссылок ниже и сам ссылок не заводит.
-        if: github.event_name == 'push' && startsWith(github.ref, 'refs/heads/task/')
+        if: (github.event_name == 'push' && startsWith(github.ref, 'refs/heads/task/')) || (github.event_name == 'pull_request' && startsWith(github.head_ref, 'task/') && github.event.pull_request.head.repo.full_name == github.repository)
         run: python3 scripts/plan_appendix_ci.py
       - run: python3 -m py_compile orchestrator/artel.py scripts/guard.py
       - name: снимок ссылок репозитория до прогона тестов (SPEC 01M1KVGD18P9H5WR7VM8TGPV1T, требование 1)
@@ -248,7 +250,7 @@ jobs:
       - name: зависимости из файла закреплённых версий для минимальной версии Python (01M29BANMM8X8JWJ5GDTJWKB0Z)
         run: python3 -m pip install -r requirements.lock
       - name: приложения PLAN задачи на дереве ветки (01M443HV9SJYVYQTHJSQ87QV68, требование 1)
-        if: github.event_name == 'push' && startsWith(github.ref, 'refs/heads/task/')
+        if: (github.event_name == 'push' && startsWith(github.ref, 'refs/heads/task/')) || (github.event_name == 'pull_request' && startsWith(github.head_ref, 'task/') && github.event.pull_request.head.repo.full_name == github.repository)
         run: python3 scripts/plan_appendix_ci.py
       - name: tests.test_invariants на минимальной объявленной версии Python (AC-2)
         run: |
```

