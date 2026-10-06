---
task: 01M49B90T16AR81ETFEYY164H1
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: CI ветки задачи — полный набор один раз на sha

## Подход

В job `changes` на push ветки `task/**` запрашиваем открытые PR через GitHub API по `head=owner:branch`. Только достоверный непустой ответ ставит `open_pr=true`; ошибка API или пустой ответ оставляют полный набор на push. Оба задания полного набора исполняются на `pull_request` независимо от этого ответа. `main` сохраняет прежний путь.

В `orchestrator/ci.py` один перечень имён проверок полного набора. Для собственного проекта пропущенная проверка из перечня не даёт зелёный статус, пока одноимённая проверка не завершилась исполненным зелёным исходом в одном из прогонов этого коммита; событие берём из индекса workflow-прогонов коммита. Неопределённое событие удерживает статус. Остальные `skipped` и внешние проекты сохраняют прежнюю оценку. Ре-ран при нескольких красных прогонах предпочитает `pull_request`, где идёт полный набор.

По `ANSWER-1.md` зелёный расклад существующего теста `CiStatusNamesRunEventTest::test_ac8_parsers_keep_outcomes_on_the_new_text` выбирает пропущенную проверку вне `ci.FULL_SUITE_CHECKS`. Ожидаемый `VERIFYING_GREEN` и прочие утверждения метода сохранены.

История Actions из наблюдения задачи 01M484RNV3 (часть 3 этапа 3 ADR-0021): три коммита вызвали шесть полных прогонов задания `python`, то есть **2 на коммит** (`push` + `pull_request`). После правки у ветки с уже открытым PR ожидается **1 на коммит** (`pull_request`); первый push до открытия PR выполняет набор на `push`, как требует SPEC. Прямой повторный запрос истории в этом окружении недоступен: `gh run list` отказал без авторизации.

## Шаги

1. Внести в `orchestrator/ci.py` перечень заданий, правило исполненного близнеца для обоих статусов и выбор прогона ре-рана.
2. Добавить юнит-тесты на пропуск полного набора, завершение PR, push без PR, прочие пропуски, внешний target, выбор ре-рана и соответствие имён `ci.yml`.
3. Приложить точный diff `.github/workflows/ci.yml`, проверить `git apply --check` и `scripts/plan_appendix_ci.py --check-workflow`; прогнать планку, тесты затронутых модулей, обновить карту и запустить полный набор командой пульта.

Затронутые тесты (`test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py`, `test_01m49b90t16ar81etfeyy164h1_full_suite_once.py`, `test_ci_full_suite_once.py`, `test_ci_status.py`, `test_ci_rerun_command.py`) — 117 passed. Метод AC-8 отдельно прошёл с ранее падавшим зерном 196307456. `plank-run` — 1 passed. `python3 scripts/codebase_map.py` выполнен. На предыдущей итерации полный набор `suite-run` не стартовал: замок удерживал прогон задачи 01M48WRE8BHFDY011Q0HQGQ91B.

После возврата из `verifying` адрес `details_url` в `tests/test_ci_full_suite_once.py:21` заменён на `http://127.0.0.1/o/r/actions/runs/{run_id}/job/1`. Проверка `tests/test_invariants.py` вместе с обоими файлами тестов задачи: 92 passed. Карта пересобрана командой `python3 scripts/codebase_map.py`. Повторный `suite-run` из роли отказал с `PermissionError` на `/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/lock.json` (тот же ранее записанный системный пробел).

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

Меняются только решение пульта о зелёности собственного CI и условие двух заданий workflow. Инвариант 36 сохранён: фильтры `paths`/`paths-ignore` не вводятся. `GREEN` для остальных проверок и внешних проектов не меняется. Сбой запроса PR оставляет полный набор на push; сбой определения события пропущенного полного набора удерживает гейт. Откат — revert коммита кода и удаление приложения из PLAN до наложения на main.

## Риски

GitHub может задержать появление `pull_request` check-run'а или индекса прогонов; до их появления пульт ждёт. Одновременный первый push и открытие PR способны дать два прогона, поскольку в момент push PR ещё не открыт; это следует из требования о первом push до `gh pr create`.

## Предложения системе

- `plank-run` для AC-1 этой задачи читает `PLAN.md` только из `refs/artifacts/<id>`: пока PLAN существует лишь в каталоге документов текущего шага, локальный прогон падает с «PLAN.md задачи в ссылке документов нет». Нужен штатный предпросмотр планки с текущим PLAN до автокоммита артефакта.
- `suite-run` в песочнице роли пытается создать `/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/lock.json` вне разрешённых корней и падает `PermissionError`. Нужна команда пульта с доступным роли замком либо явный канал запуска через Оператора.

## Приложение: условие полного набора в CI

Применимость к текущему чистому `.github/workflows/ci.yml` подтверждена `git apply --check /private/tmp/01M49B90-ci.patch` (код 0). На дереве с правкой `python3 scripts/plan_appendix_ci.py --check-workflow /private/tmp/01M49B90-ci.yml` завершился с кодом 0.

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
@@ -175,13 +176,29 @@
           # уже несёт среда Actions, BEFORE — только что заданный env).
           python3 scripts/ci_push_class.py | tee /tmp/ci-push-class.out
           grep '^code=' /tmp/ci-push-class.out >> "$GITHUB_OUTPUT"
+      - id: open-pr
+        name: открытый PR ветки задачи для выбора одного полного прогона
+        if: github.event_name == 'push' && startsWith(github.ref, 'refs/heads/task/')
+        env:
+          GH_TOKEN: ${{ github.token }}
+        run: |
+          # Неуспешный запрос оставляет output пустым: оба задания идут на
+          # push, чтобы недоступный API не снял единственный полный прогон.
+          owner=${GITHUB_REPOSITORY%%/*}
+          if count=$(timeout 30s gh api "repos/$GITHUB_REPOSITORY/pulls?state=open&head=$owner:$GITHUB_REF_NAME" --jq 'length'); then
+            if [[ "$count" =~ ^[0-9]+$ ]] && (( count > 0 )); then
+              echo 'value=true' >> "$GITHUB_OUTPUT"
+            fi
+          else
+            echo 'не удалось определить открытый PR — полный набор идёт на push'
+          fi
 
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
@@ -236,7 +253,7 @@
     # на ~110 с. Условие запуска — то же, что у `python` (ADR-0016,
     # fail-closed на пустом output `changes`).
     needs: changes
-    if: ${{ !cancelled() && needs.changes.outputs.code != 'false' }}
+    if: ${{ !cancelled() && needs.changes.outputs.code != 'false' && (github.event_name == 'pull_request' || needs.changes.outputs.open_pr != 'true') }}
     runs-on: ubuntu-latest
     timeout-minutes: 40
     steps:
```
