---
task: 01M28NWK5X10J139Z8TD69HFAC
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: класс пуша (ADR-0016) не маскирует красный main — документный пуш наследует итог тестов родителя

## Подход

Классификатор пуша (job `changes` в `.github/workflows/ci.yml`) выносится
из inline bash в `scripts/ci_push_class.py` — stdlib-скрипт с чистой
функцией `classify(event_name, ref, before, head, changed_files=None)`,
которую напрямую зовут юнит-тесты. Точка входа скрипта запускается БЕЗ
аргументов командной строки — залоченный контракт вызова из
`tasks/01M28NWK5X10J139Z8TD69HFAC/acceptance_tests/test_ci_push_class.py`
(обнаружено при первом прогоне приёмки: черновик шага 1 сначала читал
вход через `argparse`, приёмка это отвергла): все входы читаются из
переменных окружения `GITHUB_EVENT_NAME`, `GITHUB_REF`, `GITHUB_SHA`
(HEAD), `BEFORE` (родитель, то же имя, что нёс bash в ci.yml) —
`GITHUB_TOKEN`/`GITHUB_REPOSITORY` отдельно не читаются, `gh` сам
находит их в окружении процесса. Список изменённых файлов скрипт считает
сам через `git diff --name-only $BEFORE $GITHUB_SHA` в ТЕКУЩЕМ каталоге
(requirement 1) — ни один вызов `git`/`gh` не переопределяет `cwd`:
рабочий каталог наследуется от процесса, которым скрипт запущен (чекаут
`actions/checkout` в CI, временный git-репозиторий в приёмочных тестах).

Логика ADR-0016 (artifact/** → false без диффа; task/**, pull_request →
всегда true; main — документный дифф false, иначе/сомнение true)
переносится дословно. Поверх неё для документного пуша в `main`
добавляется запрос к GitHub API (`gh api
repos/{owner}/{repo}/actions/runs?head_sha=<before>&branch=main`,
тот же приём вызова `gh`, что `orchestrator/ci.py::find_run_id`):
берётся последний завершённый прогон workflow с именем `ci`
(отличать от возможных прогонов других workflow на том же sha —
фильтр по `name == "ci"` и `status == "completed"`), `code=false`
только если его `conclusion == "success"`. Любое сомнение (нет прогона,
`conclusion` иной, ошибка/исключение при вызове `gh`, битый JSON) —
`code=true`, тот же fail-closed принцип, что и остальная классификация.

`.github/workflows/ci.yml` и `docs/adr/0016-ci-jobs-by-push-class.md` —
защищённые пути (`orchestrator/config.py::PROTECTED_PATHS`), зона
задачи (SPEC frontmatter) их не включает: правки 6–7 сдаются как
unified-диффы приложением ниже, оба проверены `git apply --check` на
чистом дереве непосредственно перед сдачей (после подготовки диффов
рабочее дерево возвращено в исходное состояние — `git checkout --` по
обоим файлам, `git status` подтверждает, что вне зоны задачи изменений
не осталось).

Job `changes` сегодня делает `actions/checkout@v4` условно (только на
push в main, ради `git diff`/`git cat-file`) — на остальных классах
пуша (artifact/**, task/**, pull_request) checkout не происходит вовсе,
потому что вся логика была inline-bash без обращения к файлам
репозитория. После выноса в `scripts/ci_push_class.py` шагу нужен сам
файл скрипта на диске при ЛЮБОМ классе пуша — диф добавляет
безусловный shallow checkout первым шагом и оставляет прежний условный
`fetch-depth: 0` вторым шагом только для push в main (там, где
классификатору действительно нужна история для диффа и для
`git cat-file -e $BEFORE`). Так job остаётся дешёвым на artifact/**/
task/** (49+32 прогона из выборки ADR-0016) и не расширяет объём задачи
за пределы job `changes` («Не входит»: набор job'ов не меняется).

## Шаги

1. `scripts/ci_push_class.py` — классификатор (требования 1–5, AC-1..AC-5):
   `classify()` (чистая функция) + `main()` без аргументов командной
   строки (вход — переменные окружения), только stdlib (`json`, `os`,
   `re`, `subprocess`, `sys`). `tests/test_ci_push_class.py` — юнит-тесты
   веток ADR-0016 дословно и наследования итога родителя (требование 9,
   AC-8/AC-9).
2. Unified-диффы (приложение к этому PLAN.md, ниже) — правка
   `.github/workflows/ci.yml` (job `changes` зовёт скрипт, требование 6,
   AC-6) и `docs/adr/0016-ci-jobs-by-push-class.md` (абзац «наследование
   итога родителя», требование 7, AC-7). Оба проверены `git apply
   --check` на чистом дереве.
3. `python3 scripts/codebase_map.py` — регенерация карты (новые модули
   `scripts/ci_push_class.py`, `tests/test_ci_push_class.py`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 2 |
| 7 | 2 |
| 8 | 2 |
| 9 | 1 |

## Влияние на систему

- `orchestrator/ci.py` не трогается: `verifying_status`/`branch_status`
  продолжают читать check-runs головы кодовой ветки задачи — эта задача
  меняет только служебный job `changes` self-репозитория, не путь
  чтения статуса CI пультом.
- Логика ADR-0016 не ослабляется, а дополняется: `artifact/**` и
  `task/**`/`pull_request` — те же ответы байт-в-байт (юнит-тесты
  `AdrClassificationTest` сверяют это явно); документный пуш main
  становится СТРОЖЕ (раньше — безусловный `code=false`, теперь —
  только при подтверждённо зелёном родителе), что закрывает найденную
  копилкой 11.09 маскировку красного main, а не открывает новую дыру.
  Фактически это правка гейта CI, но в рамках уже принятого ADR-0016:
  сам ADR дополняется абзацем («наследование итога родителя»), а не
  переписывается заново, и правки защищённых путей сдаются как diff-
  приложение Оператору (шаг 2), не коммитятся ролью напрямую.
- Расход GitHub API: один дополнительный вызов `gh api .../actions/runs`
  ТОЛЬКО когда дифф пуша в main целиком документный (docs/tasks/*.md
  в корне) — на artifact/**, task/**, pull_request и кодовых пушах main
  скрипт вообще не трогает `gh`; юнит-тест `test_artifact_branch_is_
  code_false_without_touching_git_or_gh` это фиксирует явно.
- Стоимость checkout job `changes`: безусловный shallow checkout
  добавляется на все классы пуша (см. «Подход»), `fetch-depth: 0`
  остаётся условным (только push в main) — секунды, не минуты; job
  `python` (семь минут) по-прежнему пропускается ровно там же, где и
  раньше, наблюдаемого расширения объёма CI-времени по классам, для
  которых ADR-0016 это время сокращал, нет.
- Откат: `git revert` коммита правки `scripts/ci_push_class.py`/
  `tests/`, плюс возврат Оператором `.github/workflows/ci.yml` и ADR к
  состоянию до диффов шага 2 (оба диффа — приложение ниже, обратное
  применение `git apply -R` тоже проверяемо).

## Риски

- Диффы к `.github/workflows/ci.yml` и `docs/adr/0016-ci-jobs-by-push-
  class.md` — приложение Оператору, не собственная правка: применяет
  и коммитит их только Оператор (защищённый путь). До этого момента
  workflow на ветке `main` продолжает работать по старой inline-bash
  логике — новый скрипт не подключён, регресс не возникает.
- `gh api .../actions/runs?head_sha=...&branch=main` может вернуть
  несколько прогонов (в т.ч. других workflow) на одном `head_sha`;
  скрипт фильтрует по `name == "ci"` и берёт первый завершённый —
  покрыто тестом `test_ignores_run_of_other_workflow`.

## Предложения системе
(нет)

## Приложение: диффы защищённых путей (шаг 2, требование 8/AC-6/AC-7)

Оба диффа сняты `git diff` на рабочем дереве после правки файлов и
подтверждены `git apply --check <файл>` на чистом дереве (без правок)
непосредственно перед сдачей; рабочее дерево затем возвращено `git
checkout --` к исходному состоянию — эти пути вне зоны задачи (SPEC
`zones: scripts/ci_push_class.py, tests/`), правит и коммитит их
Оператор.

### `.github/workflows/ci.yml` — job `changes` зовёт `scripts/ci_push_class.py`

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index d76d87fd..90fd07f1 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -161,40 +161,30 @@ jobs:
     outputs:
       code: ${{ steps.classify.outputs.code }}
     steps:
-      - uses: actions/checkout@v4
+      - name: дерево репозитория — классификатор читается из scripts/ci_push_class.py (01M28NWK5X10J139Z8TD69HFAC)
+        uses: actions/checkout@v4
+      - name: полная история — дифф и родительский коммит на main нужны только этой ветке (ADR-0016)
         if: github.event_name == 'push' && github.ref == 'refs/heads/main'
+        uses: actions/checkout@v4
         with: { fetch-depth: 0 }
       - id: classify
+        name: классификация пуша (01M28NWK5X10J139Z8TD69HFAC — наследование итога родителя для документного пуша main)
         env:
+          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
           BEFORE: ${{ github.event.before }}
         run: |
-          # ADR-0016: job `python` (семь минут) идёт только там, где может
-          # что-то найти. Fail-closed: любое сомнение — `code=true`.
-          #   artifact/**  — только tasks/<id>/, код равен родителю: false.
-          #   main         — документный пуш (все файлы под docs/, tasks/
-          #                  или *.md в корне): false; нет базы диффа,
-          #                  принудительный пуш, пустой дифф: true.
-          #   task/**, PR  — всегда true (этот sha ждёт пульт).
-          code=true
-          ref="${GITHUB_REF#refs/heads/}"
-          if [ "$GITHUB_EVENT_NAME" = "push" ]; then
-            case "$ref" in
-              artifact/*)
-                code=false ;;
-              main)
-                if [ -n "$BEFORE" ] \
-                   && [ "$BEFORE" != "0000000000000000000000000000000000000000" ] \
-                   && git cat-file -e "$BEFORE" 2>/dev/null; then
-                  files=$(git diff --name-only "$BEFORE" HEAD)
-                  if [ -n "$files" ] \
-                     && ! printf '%s\n' "$files" | grep -Ev '^(docs/|tasks/|[^/]+\.md$)' >/dev/null; then
-                    code=false
-                  fi
-                fi ;;
-            esac
-          fi
-          echo "класс пуша: ref=$ref event=$GITHUB_EVENT_NAME code=$code"
-          echo "code=$code" >> "$GITHUB_OUTPUT"
+          # Классификация вынесена в scripts/ci_push_class.py (stdlib,
+          # юнит-тесты tests/test_ci_push_class.py) — ADR-0016 дословно
+          # плюс правило «документный пуш main наследует итог CI
+          # родителя»: `code=false` только если последний завершённый
+          # прогон workflow `ci` для коммита `before` на ветке main
+          # закончился `success` (01M28NWK5X10J139Z8TD69HFAC). Скрипт
+          # печатает две строки: `code=true|false` в $GITHUB_OUTPUT,
+          # причину — в лог задания. Без аргументов — входы берутся из
+          # переменных окружения (GITHUB_EVENT_NAME/GITHUB_REF/GITHUB_SHA
+          # уже несёт среда Actions, BEFORE — только что заданный env).
+          python3 scripts/ci_push_class.py | tee /tmp/ci-push-class.out
+          grep '^code=' /tmp/ci-push-class.out >> "$GITHUB_OUTPUT"
 
   python:
     name: Синтаксис и тесты оркестратора
```

Проверка: `git apply --check <файл-с-этим-диффом>` на чистом дереве —
успех (прогнано перед сдачей).

### `docs/adr/0016-ci-jobs-by-push-class.md` — абзац «наследование итога родителя»

```diff
diff --git a/docs/adr/0016-ci-jobs-by-push-class.md b/docs/adr/0016-ci-jobs-by-push-class.md
index bf621be4..fc4a1679 100644
--- a/docs/adr/0016-ci-jobs-by-push-class.md
+++ b/docs/adr/0016-ci-jobs-by-push-class.md
@@ -94,6 +94,22 @@ Workflow `ci.yml` запускается на каждом пуше в `main`, `
    не несёт условия, исключающего `refs/heads/task/`; job `guard` не
    несёт условия, исключающего `refs/heads/artifact/`. Тест читает
    YAML файла и проверяет структуру, не текст.
+6. **Наследование итога родителя** (дополнение 11.09.2026,
+   01M28NWK5X10J139Z8TD69HFAC; копилка 11.09 «Main красный, а CI main
+   зелёный»). П.3 в исходной редакции присваивал документному пушу
+   `main` `code=false` безусловно — это маскировало красный CI
+   родительского коммита: операторский коммит, уронивший тест, и два
+   следующих документных коммита поверх него все получали зелёную
+   плашку, хотя код с тех пор не прошёл проверку ни разу. Job `changes`
+   (логика вынесена в `scripts/ci_push_class.py`) для документного пуша
+   в `main` присваивает `code=false` только если последний завершённый
+   прогон workflow `ci` для коммита `before` на ветке main
+   (`gh api repos/{owner}/{repo}/actions/runs?head_sha=<before>&branch=main`)
+   закончился `conclusion == success`. Отсутствие прогона для `before`,
+   `conclusion != success` или ошибка запроса к API — `code=true`, тот
+   же fail-closed, что и остальная классификация п.3: документный
+   коммит поверх красного или неизвестного main всегда получает
+   собственный прогон `python`, а не наследует чужую зелёную плашку.
 
 ## Последствия
 
```

Проверка: `git apply --check <файл-с-этим-диффом>` на чистом дереве —
успех (прогнано перед сдачей).
