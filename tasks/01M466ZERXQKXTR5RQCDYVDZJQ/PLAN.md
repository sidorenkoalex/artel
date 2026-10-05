---
task: 01M466ZERXQKXTR5RQCDYVDZJQ
type: plan
author_role: developer
status: escalate
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
3. Доставка правки workflow так, чтобы CI ветки был зелёным, — см.
   «Эскалация» (блокирует сдачу).

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

## Влияние на систему

- Существующий метод `TaskBranchTest::test_only_task_push_is_processed`:
  меняется ровно утверждение из раздела SPEC «Меняемое поведение»
  (`None` → `"01abc-x"`), остальные три утверждения на месте, имя метода
  то же. Прочие методы не тронуты; добавлены
  `TaskBranchTest::test_other_events_and_bare_prefix_are_skipped`,
  `TestedRefTest` (3 метода),
  `WorkflowErrorsTest::test_push_only_condition_in_dash_and_multiline_forms`.
- Сторож шага строже: добавлено нарушение, ни одно прежнее не снято.
- **Job `guard` в CI ветки задачи.** Его шаг `plan_appendix_ci.py
  --check-workflow .github/workflows/ci.yml` идёт по ci.yml ветки — без
  приложений (их накладывают только jobs `python`/`python-min`, и
  определение workflow прогона берётся из закоммиченного файла). С новым
  сторожем этот шаг на ветке задачи красный и на push, и на pull_request,
  пока правка ci.yml не в main; `ci.verifying_status`/`branch_status`
  считают все check-run'ы — задача не пройдёт `verifying` и ворота мержа.
  Это и есть предмет эскалации.
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

## Эскалация

**Вопросы** (один, блокирующий):

1. Как сделать зелёным job `guard` в CI ветки задачи, если требование 5
   (и долгоживущий AC-6) делает `--check-workflow` красным на ci.yml без
   приложения, а job `guard` всегда проверяет ci.yml ветки без приложений?
   - **А (дефолт при молчании)** — в зоне задачи: режим
     `--check-workflow` на прогоне ветки задачи (тот же отбор, что у
     наложения: пуш `task/**` или pull_request `task/**` того же
     репозитория) сначала накладывает приложения PLAN задачи на дерево
     чекаута тем же `run`, затем проверяет ci.yml — сторож видит ровно тот
     workflow, с которым ветка смержится. Вне CI (нет `GITHUB_*`, как в
     AC-6) и на прочих прогонах — проверка файла как есть. Цена: git в
     job `guard` на ветках задач; неприменимое приложение красит и
     `guard`.
   - **Б** — Оператор отдельным MR вносит Приложение 1 в main до мержа
     задачи (правка безопасна и без нового кода: старый сценарий на
     pull_request отвечает «не пуш» с кодом 0); после подтяжки main я
     убираю Приложение 1 из PLAN (иначе push-прогон ветки упадёт на уже
     наложенном приложении). Отходит от формулировки требования 4
     («приложением к PLAN»).
   - **В** — другое решение Оператора (например, шаг наложения приложений
     и в job `guard` — тоже только через main, как Б).

**Контекст.** Код и тесты сделаны (шаги 1-2), долгоживущие тесты задачи
зелёные; диагноз — `.github/workflows/ci.yml:48-49` (шаг сторожа в job
`guard` без наложения приложений), `orchestrator/ci.py:383,499` (все
check-run'ы, не только `python`/`python-min`, должны быть в `GREEN`).
Проверено: `--check-workflow` на ci.yml без приложения — код 1 (оба jobs),
с приложением — код 0.

**Блокирует.** Сдачу `ready`: с нынешним кодом CI ветки красный в
`guard`, `verifying` и ворота мержа не пройдут. При ответе А — правка
`scripts/plan_appendix_ci.py::main`/`check_workflow` и тест на неё; при Б
— только удаление Приложения 1 после подтяжки main.
