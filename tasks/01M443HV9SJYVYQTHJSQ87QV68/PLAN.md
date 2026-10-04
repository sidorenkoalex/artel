---
task: 01M443HV9SJYVYQTHJSQ87QV68
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: CI ветки задачи проверяет код вместе с приложениями PLAN

## Подход
Две независимые части, один MR.

**(а) Сценарий CI `scripts/plan_appendix_ci.py`** (требования 1–4). Запуск
без аргументов, входы — переменные Actions (`GITHUB_EVENT_NAME`,
`GITHUB_REF`), тем же контрактом, что `scripts/ci_push_class.py`.
- Не пуш `refs/heads/task/**` — код 0, git не зовётся.
- `git ls-remote --refs origin refs/artifacts/*` → ссылка документов,
  которой принадлежит ветка: id ссылки в нижнем регистре равен началу имени
  ветки до дефиса слага (самый длинный из подходящих). Формат id не
  разбирается — линт `id-format-greplint` не задет.
- `git fetch --depth=1 --no-tags origin refs/artifacts/<id>` БЕЗ имени
  назначения: ни одна ссылка раннера не заводится и не двигается (AC-4,
  сверка `refs-before`/`refs-after` job `python` не задета); PLAN.md
  читается `git show <sha>:tasks/<id>/PLAN.md` по sha из `ls-remote`.
- Нет ссылки / нет PLAN.md / нет приложений — код 0, дерево не тронуто
  (AC-2). Разбор — `guard.plan_appendices` (только чтение); ошибки разбора
  — код 1 (их не пропустили бы и ворота мержа).
- Приложения — `git apply` подряд, в порядке PLAN, файлом-патчем, как у
  ворот мержа. Отказ — код 1, в stderr «приложение N (<пути>) не
  накладывается на дерево ветки: <ответ git>» (AC-3).
- Сбой git на чтении `origin` (ls-remote/fetch) — код 1 с ответом git,
  не «приложений нет» (fail-closed, ADR-0002).
- `git commit`/`git push` не вызываются вовсе.
- Режим `--check-workflow [путь]` — сторож шага (требование 7, AC-8): в jobs
  `python` и `python-min` строка `run: python3 scripts/plan_appendix_ci.py`
  есть и стоит раньше первой строки с pytest. Разбор по отступам — тот же
  приём, что `tests/test_invariants.py::CiJobsByPushClassInvariantTest`.

**(б) Ворота мержа** (требования 5–6, `orchestrator/fsm_merge_gate.py`).
В цикле `_apply_plan_appendices` прямой `git apply` по-прежнему первым;
при отказе — новый `_appendix_already_in_main`: `git apply --reverse
--check` того же патча. Прошёл — запись журнала «приложение PLAN уже в
main: <пути>» (detail: номер приложения, пути, основание) и `continue` к
следующему приложению. Не прошёл (частично наложенное) — прежний
`_return_inapplicable_appendix`. Если после цикла применять нечего (все
уже в main) — `("ok", [])` без коммита: `git commit` на пустом индексе
сорвал бы мерж. `advance_gates/plan_appendix.git_apply` получил
необязательные `*flags` — один и тот же способ отдать патч git'у; гейт
выхода `in_dev` их не передаёт, его поведение не меняется.

**Сторож AC-8 — внутри приложения.** `tests/test_invariants.py` — путь
«только чтение» этой задачи, других защищённых файлов в `tests/` нет,
поэтому сторож — шаг job `guard` того же приложения к `ci.yml`
(`plan_appendix_ci.py --check-workflow`), а логика сторожа — в сценарии и
покрыта `tests/test_plan_appendix_ci.py` на синтетических текстах
workflow: зелёный на ветке без приложения. Настоящий `ci.yml` этот файл
намеренно не читает — на ветке без приложения такой тест был бы красным по
построению (докстринг модуля это объясняет).

**`docs/operator-session.md`** — по ANSWER-1 (вариант а) правкой в ветке
задачи, не приложением: два пункта в «Запуски и рабочие копии» после
«Лог полного набора».

Бюджет SPEC ($40) не переоценивается.

## Шаги
1. `scripts/plan_appendix_ci.py` + `tests/test_plan_appendix_ci.py`;
   долгоживущий `tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py`
   зелёный (4/4).
2. `orchestrator/fsm_merge_gate.py::_appendix_already_in_main` + `*flags`
   в `orchestrator/advance_gates/plan_appendix.py::git_apply`;
   долгоживущий `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`
   зелёный (2/2).
3. `docs/operator-session.md` — описание обеих механик.
4. Приложение 1 к `.github/workflows/ci.yml` (ниже), `docs/codebase-map.md`
   регенерирована.

Проверки шага (передний план, `-p no:cacheprovider -p timeout -o
timeout=120`): оба долгоживущих файла — 6 passed; `tests/test_plan_appendix_ci.py`
+ `tests/test_plan_appendix.py` — 36 passed; `tests/test_merge_gate_ci_wait.py`,
`tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_id_format_guard.py`
вместе с новым — 43 passed; `tests/test_codebase_map.py` — 34 passed;
`tests/test_invariants.py -k CiJobs` на `ci.yml` С наложенным приложением —
9 passed; `--check-workflow` на `ci.yml` с приложением — код 0.
Мутации сторожей проверены временно: `startswith(id.lower())` без дефиса —
`DocsRefForBranchTest` красный; снятая сверка порядка с pytest —
`test_missing_or_late_step_is_named` красный; код возвращён.

Приложение 1 проверено `git apply --check` на чистом дереве ветки (HEAD
b971a7d4) — и сырым диффом, и блоком, извлечённым из этого PLAN.md
`guard.plan_appendices`: применяется.

Код закоммичен в ветку задачи (97997320). Планка `artel.py plank-run`: 1
passed (правка `docs/operator-session.md` в диффе ветки), 2 failed только
на чтении PLAN.md из `refs/artifacts/<id>` — PLAN попадёт туда
автокоммитом пульта по итогам шага. Те же два теста (AC-7 приложение,
AC-8 сторож) прогнаны с PLAN, подставленным с диска каталога документов, —
зелёные.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 4 (шаг в jobs `python`, `python-min` только для пуша `task/**`) |
| 2 | 1 (`task_branch`, выходы без ссылки/PLAN/приложений) |
| 3 | 1 (код 1, номер и пути приложения в stderr) |
| 4 | 1 (fetch без имени назначения, нет commit/push) |
| 5 | 2 (`--reverse --check`, запись журнала, `continue`) |
| 6 | 2 (частичное — прежний возврат в `in_dev`) |
| 7 | 3, 4 (сторож — шаг `--check-workflow` job `guard` в приложении) |
| 8 | 1, 2 (долгоживущие файлы + `tests/test_plan_appendix_ci.py`) |

## Влияние на систему
- CI: до мержа приложения поведение CI не меняется вовсе. После — на пуше
  `task/**` в `python`/`python-min` добавляется шаг; `main`, PR и прочие
  ветки — шаг `skipped` по условию шага (не job: инвариант 36 и сторож
  `CiJobsByPushClassInvariantTest` смотрят условия job — проверено, 9
  passed). Шаг стоит до снимка ссылок и ссылок не заводит — сверка
  `refs-before/after` не ослаблена.
- Ворота мержа: новый исход только там, где раньше был отказ, и только при
  проходящем `--reverse --check`; частично наложенное и неприменимое —
  прежний исход. Полный прогон после приложений по-прежнему идёт, если
  наложено хоть что-то из `_FULL_SUITE_APPENDIX_PREFIXES`.
- Гейт применимости на выходе `in_dev` не тронут (SPEC «Не входит»).
- Ни один тест, гейт, лимит не ослаблен; существующие тестовые методы не
  менялись.
- Откат: revert merge-коммита задачи и коммита приложений Оператора.

## Расширение зон
Пути: docs/operator-session.md

Обоснование: `docs/operator-session.md` — не защищённый путь, приложение
к нему невозможно; ANSWER-1 (вариант а) переносит описание обеих механик
в правку ветки задачи и даёт мандат «Расширение зон разрешено:
docs/operator-session.md». AC-7 сверяет эту правку в диффе ветки.

## Риски
- Шаг CI зовёт `git ls-remote/fetch origin` с учётными данными
  `actions/checkout` (persist-credentials по умолчанию) — при их отключении
  шаг красный с ответом git (fail-closed), не тихо зелёный.
- Приложение, одновременно проходящее прямой и обратный `--check`
  (вырожденный дифф), идёт прямым — прежний порядок.

## Приложение 1: шаг приложений PLAN в jobs python и python-min и его сторож в job guard

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index d29fced7..8b4b4583 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -45,6 +45,8 @@ jobs:
           else
             echo "артефактов пока нет — ок"
           fi
+      - name: сторож шага приложений PLAN в jobs python и python-min (01M443HV9SJYVYQTHJSQ87QV68, требование 7)
+        run: python3 scripts/plan_appendix_ci.py --check-workflow .github/workflows/ci.yml
 
   id-format-greplint:
     name: Линт — новый парсинг формата id задачи вне генератора
@@ -194,6 +196,13 @@ jobs:
           python-version: ${{ steps.stack-python.outputs.version }}
       - name: зависимости из файла закреплённых версий (01M1REVEZ1HESMJ7AFD5A9MEJ8, требование 3)
         run: python3 -m pip install -r requirements.lock
+      - name: приложения PLAN задачи на дереве ветки (01M443HV9SJYVYQTHJSQ87QV68, требование 1)
+        # Только пуш task/**: тесты идут на дереве «код ветки плюс
+        # приложения её PLAN» (PLAN — из ссылки документов задачи в
+        # origin). Ничего не коммитит и не пушит; шаг стоит до снимка
+        # ссылок ниже и сам ссылок не заводит.
+        if: github.event_name == 'push' && startsWith(github.ref, 'refs/heads/task/')
+        run: python3 scripts/plan_appendix_ci.py
       - run: python3 -m py_compile orchestrator/artel.py scripts/guard.py
       - name: снимок ссылок репозитория до прогона тестов (SPEC 01M1KVGD18P9H5WR7VM8TGPV1T, требование 1)
         run: git for-each-ref --format='%(refname) %(objectname)' refs/heads/ refs/artifacts/ > /tmp/refs-before.txt
@@ -238,6 +247,9 @@ jobs:
           python-version: ${{ steps.stack-python-min.outputs.version }}
       - name: зависимости из файла закреплённых версий для минимальной версии Python (01M29BANMM8X8JWJ5GDTJWKB0Z)
         run: python3 -m pip install -r requirements.lock
+      - name: приложения PLAN задачи на дереве ветки (01M443HV9SJYVYQTHJSQ87QV68, требование 1)
+        if: github.event_name == 'push' && startsWith(github.ref, 'refs/heads/task/')
+        run: python3 scripts/plan_appendix_ci.py
       - name: tests.test_invariants на минимальной объявленной версии Python (AC-2)
         run: |
           # Литерал timeout=120 дублирует stack.PER_TEST_TIMEOUT_SEC —
```

## Предложения системе
- `skills/spec-authoring.md` «Границы» требует сторожа внутри приложения,
  но когда единственный защищённый тест (`tests/test_invariants.py`) объявлен
  ТЗ «только чтение», внутри приложения остаётся лишь самопроверка в самом
  `ci.yml` — правило стоит дополнить этим случаем.
- В шаге роли `cat`/`ls` недоступны в PATH оболочки (`command not found`),
  а `/bin/ls` по каталогу документов требует подтверждения — мелкое трение
  на ориентировании.
