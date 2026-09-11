---
task: 01M27JPEGCGMDDRX5A98QWJW0Z
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: защищённые пути — единый список, гейт зон отказывает всегда, CI падает

## Подход

Один и тот же факт («список защищённых путей существует, но ни одна
проверка не блокирует правку им роли») чинится с четырёх точек контроля
одним и тем же монолитным шагом (см. «Оценка объёма и деление» SPEC —
промежуточный мерж любой части в отдельности оставляет систему в том же
дефектном состоянии):

1. `config.PROTECTED_PATHS` — единый источник: пять существующих путей
   плюс пять из требования 1.
2. Гейт зон (`fsm_advance._zones_gate`) — новая безусловная проверка
   `_protected_paths_touched(files)` на ПОЛНОМ списке файлов диффа
   (`files`, не только `out_of_zone`), вставленная РАНЬШЕ и заявленности
   в `zones` (текущая ветка кода это уже проверяла бы молча пройдя), и
   исключения «Расширение зон» (та же причина: обе ветки логики читают
   `zones`/`extension_paths`, к защищённым путям неприменимо по
   требованию 2/3). Формула сравнения — переиспользован уже
   существующий `_touches_zone` (тот же приём префикса, что несёт
   `fsm_merge_gate._touches_protected_path` — комментарий на
   `_touches_zone` уже ссылался на него ДО этой задачи), не новая копия
   формулы.
3. Гейт мержа (`fsm_merge_gate._cmd_approve_merge_gate`) — новый узел
   `_protected_path_diff_gate`, вызываемый ПЕРВЫМ шагом тела гейта (до
   публикации головы ветки и до попытки `git merge --no-ff`): дифф
   ветки задачи против той же базы сравнения (`gitcmd.diff_base`), что
   и гейт зон, — не только конфликтующие файлы `_handle_merge_conflict`
   (та проверка остаётся нетронутой как есть: после нового узла она
   физически недостижима на защищённом пути в обычном потоке, поскольку
   конфликтовать может только файл, УЖЕ входящий в дифф ветки, но
   убирать её — отдельный риск для минимального диффа, не требование
   этой задачи).
4. Именованный текст отказа (требование 4) — один текст,
   `fsm_advance._protected_path_refusal_detail`/
   `fsm_merge_gate._protected_path_refusal_detail`: две функции с
   идентичным телом (тот же приём дублирования, что уже несёт пара
   `_touches_zone`/`_touches_protected_path` — модули `fsm_advance.py`/
   `fsm_merge_gate.py` не имеют общего родителя в графе импортов без
   риска цикла, `fsm_merge_gate` уже импортирует `fsm`, а `fsm`
   импортирует `fsm_advance`). Байт-идентичность двух копий закрыта
   собственным юнит-тестом (`tests/test_protected_paths_gate.py::
   ProtectedPathRefusalDetailTest::
   test_zones_gate_and_merge_gate_texts_are_byte_identical`).
5. `.github/workflows/ci.yml` (требование 5) — защищённый путь
   (`.github/` уже в списке ДО этой задачи), правит только Оператор:
   unified-дифф приложен ниже, `git apply --check` пройден на чистом
   дереве (см. «Приложение»).

Fail-режим нового узла гейта мержа при неответившем git —
принципиально ДРУГОЙ, чем у гейта зон (тот `GateRefusal`'ит, fail-closed
по ADR-0002): `_protected_path_diff_gate` возвращает `False` (не
эскалирует), а не `sys.exit`. Открыт этот выбор итерацией на
`tests/test_merge_gate_ci_wait.py::FreshPathDefersToWaitLoopTest`
(песочница `TmpRootTest` без настоящего git) — первая версия узла
`sys.exit`'ила там же, где раньше проходил тест, что и обнажило
регрессию до сдачи. `sys.exit` здесь дублировал бы отказ, который и
так неизбежен чуть ниже по потоку того же вызова
(`_ensure_branch_head_published`/`_perform_carpentry_merge` сами не
работают без живого git) — не расширяет защиту, только двигает точку
отказа раньше без выигрыша.

## Шаги

1. `orchestrator/config.py` — `PROTECTED_PATHS` incorporates пять новых
   путей (AC-1).
2. `orchestrator/fsm_advance.py` — `_protected_paths_touched`/
   `_protected_path_refusal_detail` + безусловная проверка в начале
   тела `_zones_gate` (AC-2, AC-3, AC-4 половина).
3. `orchestrator/fsm_merge_gate.py` — `_protected_path_refusal_detail`/
   `_protected_path_diff_gate` + вызов первым шагом
   `_cmd_approve_merge_gate` (AC-5, AC-4 вторая половина).
4. `tests/test_protected_paths_gate.py` — юнит-тесты чистых функций и
   граней, которые приёмочная планка (залочена) не покрывает:
   приоритет защищённого пути над обычным «вне zones» при смешанном
   диффе, скип внешнего target на гейте мержа, fail-open на
   неответившем git гейта мержа (не `sys.exit`).
5. `.github/workflows/ci.yml` — приложение unified-диффа к этому PLAN
   (защищённый путь, применяет Оператор): python-однострочник из
   `config.PROTECTED_PATHS` вместо хардкод-regex, `exit 1` вместо
   `::warning` (AC-6).
6. `docs/codebase-map.md` — регенерация (`python3 scripts/
   codebase_map.py`) тем же коммитом, что правка `*.py` (skills/
   conventions-core.md) — единственное изменение содержания:
   `built_at_sha` и список `tests/test_protected_paths_gate.py` в
   «Импортируется» затронутых модулей; новые функции — все с
   ведущим `_` (не публичные), в карте не появляются.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (единый список) | 1 |
| 2 (гейт зон отказывает независимо от zones) | 2 |
| 3 (гейт зон отказывает независимо от «Расширение зон») | 2 |
| 3 (гейт мержа отказывает не только при конфликте) | 3 |
| 4 (именованный текст, оба гейта) | 2, 3 |
| 5 (CI-задание падает, единый источник) | 5 |

## Влияние на систему

- Существующая эскалация по защищённому пути ВНУТРИ разбора конфликта
  merge (`_handle_merge_conflict`, строки 142-148 до этой задачи)
  оставлена нетронутой: в обычном потоке она теперь физически
  недостижима для защищённого пути (новый узел `_protected_path_diff_
  gate` эскалирует раньше, до самой попытки `git merge --no-ff`,
  используя ТУ ЖЕ базу сравнения `gitcmd.diff_base`, что и содержательный
  конфликт мог бы затронуть только файл, уже входящий в этот дифф) —
  оставлена как задокументированная избыточность (docstring
  `_protected_path_diff_gate`), не удалена: удаление — риск для
  минимального диффа задачи без требования SPEC на это.
- Существующие тесты защищённых путей (`tests/test_zones_gate.py`,
  20 тестов) и гейта мержа (`tests/test_fsm_merge_gate_done_snapshot.py`,
  `tests/test_merge_gate_ci_wait.py`, `tests/test_fsm_merge_conflict_
  note.py`, `tests/test_split_assessment_merge_gate.py`,
  `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`,
  `tests/test_cmd_approve_dispatch.py`, `tests/test_answer_gate.py`,
  `tests/test_zones_approve.py`, `tests/test_guard_zones.py`,
  `tests/test_advance_guard.py`, `tests/test_fsm_advance_gate_framework.
  py`, `tests/test_fsm_advance_gate_smoke.py` — 88 тестов суммарно)
  прогнаны заново, зелёные без изменения утверждений (regression
  найдена и закрыта итерацией — см. «Подход»/fail-open).
  `tests/test_invariants.py`/`tests/test_multitarget_invariants.py` (64
  теста) — тоже зелёные: число шагов между состояниями FSM не менялось
  (оба гейта остаются предусловиями существующих переходов, требование
  «Не входит» SPEC).
- Инвариант 36 (`docs/invariants.md`) не задет: FSM не получил нового
  состояния, оба узла — дополнительные предусловия существующих
  переходов `in_dev -> verifying`/`merge_gate -> done`|`escalated`.
- Откат: `git revert` трёх файлов зоны + приложенного диффа `ci.yml`
  (Оператор) возвращает прежнее (дефектное) поведение факта 11.09 без
  побочных эффектов — оба гейта самодостаточны, не меняют формат БД/
  артефактов.
- Текст `docs/invariants.md` (строки 34, 79 по SPEC «Оценка объёма»)
  расходится с новым поведением после мержа этой задачи — правка
  текста самих инвариантов явно вне зоны (SPEC «Не входит»), Оператор
  актуализирует отдельно.

## Риски

- `_protected_path_diff_gate` резолвит `repo_context.resolve` дважды за
  вызов `_cmd_approve_merge_gate` (уже резолвился ДО этого узла — `ctx`
  передаётся параметром, не второй резолв) — риска нет, `ctx` один и
  тот же объект, вызов `resolve` не повторяется.
- Гейт мержа теперь читает диф ВЕТКИ до публикации её головы в origin
  (`_ensure_branch_head_published` идёт ПОСЛЕ нового узла) — на
  локальный `git merge-base`/`diff --name-only` это не влияет (оба
  используют локальные refs, не origin), проверено `tests/
  test_protected_paths_gate.py` и приёмочным AC-5 (реальный git,
  origin ветки задачи НЕ настроен вовсе на момент вызова — тест прошёл).

## Приложение: unified-дифф .github/workflows/ci.yml (AC-6)

Защищённый путь — применяет Оператор. Проверено `git apply --check`
на чистом дереве перед сдачей (журнал шага: `APPLIES CLEANLY`).

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index be352d00..d76d87fd 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -248,19 +248,21 @@ jobs:
     steps:
       - uses: actions/checkout@v4
         with: { fetch-depth: 0 }
-      - name: diff не трогает защищённые пути (кроме PR Оператора)
+      - name: diff не трогает защищённые пути (SPEC 01M27JPEGCGMDDRX5A98QWJW0Z, требование 5)
         env:
-          PR_AUTHOR: ${{ github.event.pull_request.user.login }}
           BASE_SHA: ${{ github.event.pull_request.base.sha }}
         run: |
-          # Фаза 0: один аккаунт => проверка деградирует до предупреждения.
-          # При разделении токенов заменить exit 0 на exit 1 (см. ADR-0001).
-          PROTECTED='^(gates\.yaml|roles\.yaml|targets\.yaml|CLAUDE\.md|\.github/|templates/|skills/|tests/test_invariants\.py|docs/invariants\.md)'
-          CHANGED=$(git diff --name-only "$BASE_SHA"...HEAD | grep -E "$PROTECTED" || true)
+          # Единый источник списка — config.PROTECTED_PATHS (python-
+          # однострочник, не отдельный хардкод-regex): требование 5/AC-6.
+          # Падает (не предупреждает) безусловно на pull_request — Фаза 0,
+          # один PAT, авторство PR не различается (см. «Не входит» SPEC
+          # 01M27JPEGCGMDDRX5A98QWJW0Z).
+          PROTECTED=$(python3 -c "from orchestrator import config; import re; print('|'.join(re.escape(p) for p in config.PROTECTED_PATHS))")
+          CHANGED=$(git diff --name-only "$BASE_SHA"...HEAD | grep -E "^($PROTECTED)" || true)
           if [ -n "$CHANGED" ]; then
-            echo "::warning::PR от $PR_AUTHOR меняет защищённые пути:"
+            echo "::error::PR меняет защищённые пути (config.PROTECTED_PATHS) — их правит только Оператор коммитом в main:"
             echo "$CHANGED"
-            echo "Фаза 0 (один токен): warning. После разделения PAT — fail."
+            exit 1
           fi
 
   codebase-map:
```

## Предложения системе

- `docs/invariants.md:34,79` устаревают текстово этой задачей (строка
  34 описывает исключение «Расширение зон» гейта зон как более широкое,
  чем оно теперь есть для защищённых путей; строка 79 описывает
  `protected-paths` CI-задание как деградирующее до warning) — вне зоны
  этой задачи (SPEC «Не входит»), но актуализация текста нужна, чтобы
  инвариант не расходился с реальным поведением для следующего
  читателя.
