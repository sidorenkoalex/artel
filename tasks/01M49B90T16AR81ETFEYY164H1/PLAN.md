---
task: 01M49B90T16AR81ETFEYY164H1
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: CI ветки задачи — полный набор один раз на sha

## Подход

В job `changes` на push ветки `task/**` запрашиваем открытые PR через GitHub API по `head=owner:branch`, затем карточку каждого найденного PR. Только явные `state=open` и `mergeable=true` в карточке ставят `open_pr=true`: при конфликте GitHub не запускает workflow `pull_request`, поэтому полный набор остаётся на push. `mergeable=null` или `false`, пустой ответ, ошибка API и таймаут также оставляют полный набор на push. Оба задания полного набора исполняются на `pull_request` независимо от этого ответа. `main` сохраняет прежний путь.

В `orchestrator/ci.py` один перечень имён проверок полного набора. Для собственного проекта пропущенная проверка из перечня не даёт зелёный статус, пока одноимённая проверка не завершилась исполненным зелёным исходом в одном из прогонов этого коммита; событие берём из индекса workflow-прогонов коммита. Неопределённое событие удерживает статус. Остальные `skipped` и внешние проекты сохраняют прежнюю оценку. Ре-ран при нескольких красных прогонах предпочитает `pull_request`, где идёт полный набор.

По `ANSWER-1.md` зелёный расклад существующего теста `CiStatusNamesRunEventTest::test_ac8_parsers_keep_outcomes_on_the_new_text` выбирает пропущенную проверку вне `ci.FULL_SUITE_CHECKS`. Ожидаемый `VERIFYING_GREEN` и прочие утверждения метода сохранены.

История Actions из наблюдения задачи 01M484RNV3 (часть 3 этапа 3 ADR-0021): три коммита вызвали шесть полных прогонов задания `python`, то есть **2 на коммит** (`push` + `pull_request`). После правки у ветки с уже открытым PR ожидается **1 на коммит** (`pull_request`); первый push до открытия PR выполняет набор на `push`, как требует SPEC. Прямой повторный запрос истории в этом окружении недоступен: `gh run list` отказал без авторизации.

## Шаги

1. Внести в `orchestrator/ci.py` перечень заданий, правило исполненного близнеца для обоих статусов и выбор прогона ре-рана.
2. Проверить пропуск полного набора, завершение PR, push без PR, прочие пропуски, внешний target, выбор ре-рана и соответствие имён `ci.yml` долгоживущими тестами задачи и тестами затронутых модулей.
3. Приложить точный diff `.github/workflows/ci.yml`, проверить `git apply --check` и `scripts/plan_appendix_ci.py --check-workflow`; проверить явную сливаемость PR, неопределённость и сбой API тестом условия workflow; прогнать планку, тесты затронутых модулей, обновить карту и запустить полный набор командой пульта.

На первой итерации затронутые тесты — 117 passed. Метод AC-8 отдельно прошёл с ранее падавшим зерном 196307456. `plank-run` — 1 passed. `python3 scripts/codebase_map.py` выполнен. Тогда полный набор `suite-run` не стартовал: замок удерживал прогон задачи 01M48WRE8BHFDY011Q0HQGQ91B.

После возврата из `verifying` прежний дополнительный тест исправлял адрес `details_url`; тогда `tests/test_invariants.py` вместе с обоими файлами тестов задачи дали 92 passed. Повторный `suite-run` из роли отказал с `PermissionError` на `/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/lock.json` (тот же ранее записанный системный пробел).

По R1-F1 ревью итерации 1 файл `tests/test_ci_full_suite_once.py` удалён: все восемь его методов дублировали свойства AC-4…AC-14 зафиксированного `tests/test_01m49b90t16ar81etfeyy164h1_full_suite_once.py`; новых свойств он не держал. Статус R1-F1 размечен `fixed` в REVIEW.md. Карта пересобрана `python3 scripts/codebase_map.py`. Тесты затронутых модулей (`test_01m49b90t16ar81etfeyy164h1_full_suite_once.py`, `test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py`, `test_ci_status.py`, `test_ci_rerun_command.py`, `test_ci_push_class.py`) — 126 passed, 126 subtests passed. `plank-run` — 1 passed. Патч текущего PLAN прошёл `git apply --check` (код 0). Повторный `suite-run` завершился до старта тестов с `PermissionError` при создании того же `/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/lock.json`.

По возврату приёмки 07.10 приложение требует явного `mergeable=true` у открытого PR. Новый `tests/test_ci_workflow_mergeable.py` исполняет шаг `open-pr` из файла с наложенным приложением: `true`, `false`, `null`, закрытый PR, отсутствие PR, сбой списка и сбой карточки; проверяет также условия двух заданий. Временная мутация удаления `.mergeable == true` дала 3 ожидаемых отказа на `false`, `null` и закрытом PR; удаление ограничения ветки `task/` покрасило второй тест. Тесты затронутых модулей с наложенным приложением — 128 passed, 135 subtests passed; карта пересобрана `python3 scripts/codebase_map.py`. `plank-run` — 1 passed, но он читает предыдущий PLAN из зафиксированной ссылки документов; новый текст приложения отдельно проверен командами ниже. `suite-run` снова завершился до старта тестов с `PermissionError` на `/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/lock.json`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1–2 | 3 |
| 3–4 | 1, 2 |
| 5 | 3 |
| 6 | 2 |
| 7 | 3 |
| 8 | 1, 2 |

## Влияние на систему

Меняются только решение пульта о зелёности собственного CI и условие двух заданий workflow. Инвариант 36 сохранён: фильтры `paths`/`paths-ignore` не вводятся. `GREEN` для остальных проверок и внешних проектов не меняется. Сбой запроса PR или отсутствие явного `mergeable=true` оставляют полный набор на push; сбой определения события пропущенного полного набора удерживает гейт. Откат — revert коммита кода и удаление приложения из PLAN до наложения на main.

## Риски

GitHub может задержать появление `pull_request` check-run'а или индекса прогонов; до их появления пульт ждёт. Если GitHub отдаёт `mergeable=null` во время асинхронного расчёта сливаемости или PR конфликтует с базой (`mergeable=false`), набор остаётся на push: возможен лишний прогон после устранения конфликта, зато коммит не зависнет в `verifying` без единственного полного прогона. Каждый запрос API ограничен 30 секундами; сбой или таймаут сохраняет набор на push. Одновременный первый push и открытие PR способны дать два прогона, поскольку в момент push PR ещё не открыт; это следует из требования о первом push до `gh pr create`.

## Предложения системе

- `plank-run` для AC-1 этой задачи читает `PLAN.md` только из `refs/artifacts/<id>`: пока PLAN существует лишь в каталоге документов текущего шага, локальный прогон падает с «PLAN.md задачи в ссылке документов нет». Нужен штатный предпросмотр планки с текущим PLAN до автокоммита артефакта.
- `suite-run` в песочнице роли пытается создать `/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/lock.json` вне разрешённых корней и падает `PermissionError`. Нужна команда пульта с доступным роли замком либо явный канал запуска через Оператора.

## Приложение: условие полного набора в CI

Применимость к текущему чистому `.github/workflows/ci.yml` подтверждена `git apply --check /private/tmp/01M49B90-ci-mergeable.patch` (код 0). На дереве с правкой `python3 scripts/plan_appendix_ci.py --check-workflow /private/tmp/01M49B90-ci-check/.github/workflows/ci.yml` завершился с кодом 0.

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -150,6 +150,7 @@
     runs-on: ubuntu-latest
     outputs:
       code: ${{ steps.classify.outputs.code }}
+      open_pr: ${{ steps.open-pr.outputs.value }}
     steps:
       - name: дерево репозитория — классификатор читается из scripts/ci_push_class.py (01M28NWK5X10J139Z8TD69HFAC)
         uses: actions/checkout@v4
@@ -175,13 +176,40 @@
           # уже несёт среда Actions, BEFORE — только что заданный env).
           python3 scripts/ci_push_class.py | tee /tmp/ci-push-class.out
           grep '^code=' /tmp/ci-push-class.out >> "$GITHUB_OUTPUT"
+      - id: open-pr
+        name: открытый PR ветки задачи для выбора одного полного прогона
+        if: github.event_name == 'push' && startsWith(github.ref, 'refs/heads/task/')
+        env:
+          GH_TOKEN: ${{ github.token }}
+        run: |
+          # Только явно сливаемый открытый PR гарантирует прогон pull_request.
+          # При конфликте GitHub его не запускает: полный набор идёт на push.
+          owner=${GITHUB_REPOSITORY%%/*}
+          if ! numbers=$(timeout 30s gh api --paginate "repos/$GITHUB_REPOSITORY/pulls?state=open&head=$owner:$GITHUB_REF_NAME" --jq '.[].number'); then
+            echo 'не удалось найти PR — полный набор идёт на push'
+            exit 0
+          fi
+          for number in $numbers; do
+            if [[ ! "$number" =~ ^[0-9]+$ ]]; then
+              echo 'некорректный номер PR — полный набор идёт на push'
+              exit 0
+            fi
+            if ! mergeable=$(timeout 30s gh api "repos/$GITHUB_REPOSITORY/pulls/$number" --jq 'select(.state == "open" and .mergeable == true) | .number'); then
+              echo 'не удалось определить сливаемость PR — полный набор идёт на push'
+              exit 0
+            fi
+            if [[ "$mergeable" == "$number" ]]; then
+              echo 'value=true' >> "$GITHUB_OUTPUT"
+              break
+            fi
+          done
 
   python:
     name: Синтаксис и тесты оркестратора
     needs: changes
     # ADR-0016: `!= 'false'`, не `== 'true'` — упавший или отменённый
     # `changes` даёт пустой output, и тесты ИДУТ (fail-closed).
-    if: ${{ !cancelled() && needs.changes.outputs.code != 'false' }}
+    if: ${{ !cancelled() && needs.changes.outputs.code != 'false' && (github.event_name == 'pull_request' || needs.changes.outputs.open_pr != 'true') }}
     runs-on: ubuntu-latest
     # Страховка от зависшего раннера (01M29BANMM8X8JWJ5GDTJWKB0Z) — не
     # рабочий ориентир для длительности job, реальные прогоны много короче.
@@ -236,7 +264,7 @@
     # на ~110 с. Условие запуска — то же, что у `python` (ADR-0016,
     # fail-closed на пустом output `changes`).
     needs: changes
-    if: ${{ !cancelled() && needs.changes.outputs.code != 'false' }}
+    if: ${{ !cancelled() && needs.changes.outputs.code != 'false' && (github.event_name == 'pull_request' || needs.changes.outputs.open_pr != 'true') }}
     runs-on: ubuntu-latest
     timeout-minutes: 40
     steps:
```
