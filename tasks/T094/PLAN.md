---
task: T094
type: plan
author_role: developer
status: draft
schema_version: 2
---

# PLAN: M1: артефактный контур — Б₃ + ULID

## Реестр точек чтения tasks/<id>/ из кодовой ветки

Требование 1/AC-1: все места системы, читающие `tasks/<id>/` живой
задачи из кодовой ветки `task/*` целевого, и план перенаправления
каждого на артефактную ветку пульта (лечение BL-1). Self/догфуд
(`config.DEFAULT_TARGET`) везде ниже исключён из редиректа — требование
16/AC-18: до A7 self читает/пишет `tasks/<id>/` прежним однобраншевым
флоу, ни одна строка ниже его не трогает.

1. **Хэш-фиксация гейтов** (`orchestrator/fixation.py`,
   `store.record_fixation`). Было: `fixation.read`/`fixation.fix`
   читали код и артефакты одного и того же клона внешнего target
   (`.artel/projects/<target>/`, легаси-адрес ADR-0005 п.4 до правки).
   Редирект: `fixation.external_code_sha` — HEAD клона-workspace
   целевого (код), `fixation.external_artifact_sha` — HEAD
   `artifact_branch.branch_name(task_id)` пульта (артефакты);
   `store.record_fixation` пишет ОБА sha в detail журнала (требование
   9, AC-10) для внешнего target, не заменяя легаси-строку. **Сделано**
   (шаг 4).
2. **Лок acceptance_tests** (`orchestrator/acceptance.py::run`,
   вызывается из `fsm_advance.tests_writing`/`in_dev`). Было и
   остаётся: `run(tdir)` берёт `acceptance_tests/` с ДИСКА `tdir`
   (worktree кодовой ветки). Редирект НЕ сделан в этой итерации —
   см. пункт 9 ниже и «Риски»: сегодня ни один задекларированный
   target (`targets.yaml`) не проходит `tests_writing`/`in_dev` как
   внешний, живая точка отказа отсутствует; редирект `run()` на
   вычитку `acceptance_tests/` из артефактной ветки пульта во временный
   каталог — план на следующую итерацию, до первого внешнего target,
   идущего через полный цикл FSM.
3. **Ветко-корректные чтения статусов и брифов**:
   - `orchestrator/brief.py` (`developer_brief`, `analyst_map_component`,
     `test_author_answer_component`) — редиректнуто: общая точка входа
     `_artifact_source_branch` возвращает ветку артефактов и `foreign=True`
     для любого target, кроме self. **Сделано** (шаг 9).
   - `orchestrator/catalog.py` (`cmd_show` → `_artifact_frontmatter`) —
     редиректнуто: frontmatter SPEC/PLAN/REVIEW/TEST_REPORT читается
     `gitcmd.show(artifact_branch.branch_name(task_id), ...)` для
     внешнего target. **Сделано** (шаг 3).
   - `orchestrator/cleanup.py` (`_journal_tz_before_cleanup`) —
     редиректнуто: TZ.md перед уборкой читается с артефактной ветки для
     внешнего target. **Сделано** (шаг 3).
   - `orchestrator/fsm.py` (`_read_branch_text_or_refuse`,
     `_answer_file_count`, `_tests_writing_ac_state`, гейт `review`,
     `verifying` и др.) и `orchestrator/fsm_advance.py` (`spec_writing`,
     `review`, `verifying`) — читают `tasks/<id>/*.md`/`acceptance_tests/`
     с `t["branch"]` (кодовая ветка). Редирект НЕ сделан в этой
     итерации — тот же довод, что у пункта 2 (`acceptance.run`): это
     одна связная группа чтений FSM-переходов, вместе с
     `runner.role_cwd`/`role_env` (см. пункт 9), и её безопасный
     редирект требует нитки помощника через десяток функций
     core-модуля с плотным существующим покрытием тестами (invariants
     25–28) и БЕЗ единого внешнего target, который прогнал бы новый
     путь вживую сегодня — риск регресса self-флоу выше пользы
     недоказанного кода. План: тем же приёмом, что `brief.
     _artifact_source_branch` — общий резолвер (ветка, foreign) на
     верхнем уровне `fsm.py`/`fsm_advance.py`, до появления первого
     реального внешнего target в `targets.yaml`, отдельной задачей.
4. **Guard в CI** (`.github/workflows/ci.yml`, защищённый путь —
   правит только Оператор). Было: `push` триггерится на
   `["main", "task/**"]` — артефактная ветка `artifact/**` guard'ом
   никогда не проверяется. Редирект: диф расширяет `push.branches` до
   `["main", "task/**", "artifact/**"]` — приложен к этому PLAN.md
   ниже («Дифф для Оператора»), тем же приёмом, что T046. **Дифф
   готов, применяет Оператор** (не входит в ветку задачи, требование 4
   класса «защищённый путь»).
5. **Coldstart** (`orchestrator/coldstart.py::observed_max_task_number`).
   Проверено: функция сканирует только легаси-номер `Tnnn`
   (`store.task_number`) для посева/сверки контура счётчика —
   контур заморожен как legacy требованием 6, ULID-задачи в этот
   подсчёт не входят по построению (не ошибка, дизайн). Редирект НЕ
   требуется — сканирование `tasks/` внешнего target
   (`.artel/projects/<target>/tasks`) остаётся мёртвым путём для
   не-ULID номеров и не читает содержимое артефактов задачи, только
   имена каталогов. **Не требует изменений** (подтверждено, не шаг).
6. **`orchestrator/store.py::_append_passport_line`/`resolve_task_id`** —
   новые точки записи/чтения, заведённые этой же задачей (требования
   3, 11): паспорт живой задачи пишется сразу в артефактную ветку
   (`artifact_branch.append_passport_line`), префикс-резолвер работает
   по БД (id как непрозрачная строка), с веткой не связан.
   **Сделано** (шаги 1, 5).
7. **`orchestrator/runner.py::role_cwd`/`role_env`** — рабочий каталог
   роли для внешнего target остаётся клоном ЕГО кода
   (`config.PROJECTS/<target>/workspace`), не артефактной веткой пульта:
   как именно роль пишет `tasks/<id>/` В артефактную ветку пульта из
   ЭТОГО каталога во время реального агентного шага (а не только при
   `cmd_new`) — тот же нередиректнутый кластер, что пункт 3/п.9.
   AC-9 (единственный автотест на эту тему) сознательно ограничен
   первым шагом роли — `cmd_new` (docstring
   `test_ac9_role_step_artifact_branch.py`) — редирект следующих шагов
   роли (developer/reviewer/test_author пишут PLAN/REVIEW/TEST_REPORT)
   вне охвата этой итерации по той же причине: нет живого внешнего
   target, редирект без прогона вживую — недоказанный код в
   core-модуле.

**Резюме перенаправления**: пункты 1, 3 (частично: brief.py,
catalog.py, cleanup.py), 4 (диф), 6 — сделаны и покрыты тестами
(включая `extproj` — тестовый внешний target песочницы). Пункты 2, 3
(fsm.py/fsm_advance.py), 7 — задокументированы с планом редиректа,
не реализованы в этой итерации: общий довод — единственный
задекларированный `targets.yaml` target сегодня self (требование
16/AC-18 явно исключён), редирект внутренностей FSM без прогона на
реальном внешнем target — риск регресса самотестируемого self-флоу
выше пользы. См. «Риски».

## Подход
Топология Б₃ (docs/roadmap.md §3, решения Оператора 31.08–01.09):
артефакты живой задачи — в артефактной ветке ПУЛЬТА (`artifact/<id>`,
`orchestrator/artifact_branch.py`, плотницкая запись — `hash-object`/
`update-index`/`write-tree`/`commit-tree`/`update-ref`, чтобы не
трогать чекаут главной копии пульта ни на одном шаге); снапшот при
закрытии — в несмерживаемый `refs/artifacts/<id>` ЦЕЛЕВОГО
(`orchestrator/snapshot.py`). Self/догфуд до A7 — исключение
(требование 16): однобраншевый флоу байт-в-байт как раньше.

ULID — единственный генератор, `orchestrator/idgen.py`: время (48 бит
мс) + `os.urandom` (80 бит) в Crockford base32, без внешних
зависимостей. Остальной код обращается с id как с непрозрачной строкой;
единственное разрешённое исключение из этого правила — легаси-парсер
`orchestrator/store.py::TASK_ID`/`task_number` (требование 6, контур
счётчика заморожен, не удалён).

Ключевое архитектурное решение: НЕ трогать `orchestrator/fsm.py`/
`fsm_advance.py`/`runner.py::role_cwd` в этой итерации (см. реестр,
пункты 2/3/7) — редирект их внутренностей без единого реального
внешнего target, который прогнал бы новый путь вживую, крупный риск
регресса core-модуля с плотным существующим покрытием (invariants
25–28) ради недоказанного кода. Вместо этого редирект сделан там, где
он ПРОВЕРЯЕМ прямо сейчас: `cmd_new` (заведение задачи), `cleanup`/
`fsm_merge_gate` (закрытие: снапшот + паспорт + TZ-журнал), `brief.py`
(вход роли self читает как раньше; вход роли внешнего target — из
артефактной ветки, покрыто тестами `extproj`-песочницы), `catalog.
cmd_show`, `doctor` (ретрай снапшота, деградация счётчика).

Два sha в фиксации гейтов (требование 9) — `store.record_fixation`
добавляет detail-поля `код=`/`артефакты=` для внешнего target, не
заменяя легаси-строку `sha=`/`чисто=` (совместимость с существующими
читателями журнала).

Отдельно исправлен регресс, найденный по ходу: `orchestrator/
config.py::AGENT_TIMEOUT_SEC` был откачен на 1800 предыдущей
WIP-итерацией этой же ветки, хотя main несёт временное решение
Оператора 02.09 (2700, до мержа T094) — восстановлено дословно (см.
«Риски»).

## Шаги
1. ULID-генератор (`orchestrator/idgen.py`) + `catalog.cmd_new`
   переведён на него; `store.resolve_task_id` — префикс-резолвер
   (точное совпадение первым, иначе однозначный `LIKE`-префикс, явный
   отказ при неоднозначности); `store.get_task` зовёт резолвер.
2. Retention логов по дате закрытия из журнала
   (`orchestrator/prune.py::_kept_task_ids`/`_close_ts`), не по
   номеру; `docs/retention.md` — правка формулировки.
   `doctor.check_task_counters` деградирован в информационный статус
   «счётчик не движется» (контур `task_counters` — legacy, требование
   6), алерт `doctor.task_counter` не заводится.
3. Артефактная ветка пульта (`orchestrator/artifact_branch.py`):
   плотницкая запись/чтение/паспорт/push best-effort; `catalog.cmd_new`
   разведён на `_new_dogfood`/`_new_external_artifact_branch` по
   `target`; `catalog.cmd_show` и `cleanup._journal_tz_before_cleanup`
   читают артефакты внешнего target с артефактной ветки.
4. Два sha в фиксации (`fixation.external_code_sha`/
   `external_artifact_sha`, `store.record_fixation`).
5. Паспорт живой задачи на каждом переходе FSM
   (`store._append_passport_line` → `artifact_branch.
   append_passport_line`, вызывается из `store.set_state` — единой
   точки перехода состояния, требование 11).
6. Снапшот закрытия (`orchestrator/snapshot.py`): артефакты
   артефактной ветки + RETRO (frontmatter `operator`/`model`/
   `artel_sha`) → `refs/artifacts/<id>` целевого, идемпотентно, ДО
   уборки веток; `cleanup._publish_snapshot_if_pending` (путь
   `killed`) и `fsm_merge_gate._cmd_approve_merge_gate` (путь `done`,
   возвращает `("done",)` без уборки, пока снапшот не подтверждён) —
   единый узел на оба терминальных перехода, исключая канарейку.
7. Ретрай недоставленного снапшота: `snapshot.pending`/
   `publish_and_cleanup` вызываются повторно при следующей команде
   задачи (следующий `kill`/`approve`) И при `doctor`
   (`doctor.check_pending_snapshots`, `store.closed_external_tasks`).
8. Локальный кэш ретро-корпуса (`orchestrator/retro_corpus.py`):
   `rebuild_cache` — проход по ЛОКАЛЬНЫМ `refs/artifacts/*` уже
   существующих клонов target'ов (`git for-each-ref`/`git show`, без
   сети) — прочтение ANSWER-1 (`tasks/T094/ANSWER-1.md`), разводящее
   буквальное «fetch'ем» требования 14 на M1 (локально)/M2 (сетевой
   fetch, вне объёма).
9. Ветко-корректные чтения брифов/статусов для внешнего target:
   `brief._artifact_source_branch` — общая точка входа
   `developer_brief`/`analyst_map_component`/
   `test_author_answer_component`. Глубже (`fsm.py`/`fsm_advance.py`/
   `runner.role_cwd`) — НЕ редиректнуто, задокументировано в реестре
   выше (пункты 2/3/7) и в «Риски».
10. `docs/adr/0005-data-preservation-and-memory.md` — правка пп. 1, 2,
    4, 5 под топологию Б₃ (мандат — SPEC требование 15, подтверждается
    Оператором на `spec_gate`).
11. Диф `.github/workflows/ci.yml` (защищённый путь, правит
    Оператор): job `id-format-greplint` (AC-4, требование 4) + `push`
    триггер на `artifact/**` (реестр, пункт 4) — приложен к этому
    PLAN.md, см. «Дифф для Оператора».
12. `docs/codebase-map.md` регенерирована (`scripts/codebase_map.py`)
    тем же коммитом — новые модули `artifact_branch.py`, `idgen.py`,
    `retro_corpus.py`, `snapshot.py` и их связи учтены.

## Покрытие требований
| Требование | Шаг |
|---|---|
| 1 | реестр выше (первый раздел этого PLAN.md) |
| 2 | 1 |
| 3 | 1 |
| 4 | 11 |
| 5 | 2 |
| 6 | 1, 2 |
| 7 | 3 |
| 8 | 3, 9 (self исключён — требование 16) |
| 9 | 4 |
| 10 | 3, 9 |
| 11 | 5 |
| 12 | 6 |
| 13 | 6, 7 |
| 14 | 8 |
| 15 | 10 |
| 16 | 1–12 целиком (self исключён из редиректа везде) |

## Влияние на систему
Self/догфуд (`config.DEFAULT_TARGET`) — единственный сегодня
задекларированный target (`targets.yaml`) — поведенчески НЕ меняется
ни одной строкой: каждая точка редиректа (catalog.cmd_new/cmd_show,
brief.py, cleanup.py, fixation.py, store.set_state/record_fixation,
checkpoint.py) явно ветвится по `target == config.DEFAULT_TARGET` и
для self исполняет прежний код байт-в-байт (проверено полным прогоном
`tests/` — 1203 passed, регресса на self-флоу нет). Инварианты 25–28
(docs/invariants.md) остаются в силе — их тестовые модули
(`test_git_fixation`, `test_acceptance_tests_flow`,
`test_gitcmd_branch_reads`, `tasks/T031/.../test_branch_correct_reads.py`,
`tasks/T047/.../test_branch_correct_status_reads.py`) прогнаны без
изменений и зелёные (AC-11).

Новый код (`artifact_branch.py`, `idgen.py`, `retro_corpus.py`,
`snapshot.py`) не ослабляет ни один существующий гейт/лимит/guard:
`scripts/guard.py` не правился (не требуется — новые артефакты
проходят существующие правила structure-валидации без изменений
схемы). Контур `task_counters` не удалён (требование 6, «не входит»
— полное удаление отдельной мелочью) — только его doctor-сверка
деградирована из блокирующей в информационную, ЧТО И ТРЕБУЕТ SPEC
(AC-7); сам контур продолжает сеяться и обновляться как раньше, просто
больше не может провалить `doctor`.

`AGENT_TIMEOUT_SEC` — восстановлен на 2700 (см. «Риски») после того,
как предыдущая WIP-итерация этой же ветки его откатила на 1800 без
основания (main несёт временное решение Оператора 02.09, действующее
до мержа этой задачи) — без восстановления собственный шаг
`developer` этой задачи рисковал повторить таймаут, которым и
объясняются три предыдущих WIP-чекпоинта в истории коммитов ветки.

Откат: любой шаг обратим стандартным `git revert` в ветке задачи —
новых миграций схемы БД, кроме уже присутствующих в `store.migrate`
(таблицы не создаются, колонки не добавляются этой задачей), нет.
Диф `.github/workflows/ci.yml` не применён к main этой веткой —
откатывать нечего до заявки Оператора; применённый Оператором диф
откатывается его собственным `git revert`.

## Риски
1. **Незавершённый редирект core FSM-чтений** (реестр, пункты 2/3/7):
   `fsm.py`/`fsm_advance.py`/`runner.role_cwd` продолжают читать
   `tasks/<id>/` кодовой ветки для ЛЮБОГО target, включая
   гипотетический внешний. Пока `targets.yaml` объявляет только self
   (требование 16 исключает его явно), этот путь мёртв и безопасен;
   первый реальный внешний target, доведённый до `spec_writing`/
   `tests_writing`/`in_dev` через `run`/`auto`, упрётся в этот
   пробел — сегодня это НЕ регресс (такого target нет), но это
   технический долг, который нужно закрыть ДО подключения первого
   реального внешнего target (роадмап: после M1, ориентировочно
   вместе с «двухоператорным экспериментом», SPEC «Не входит»).
2. **AC-15, подтест `test_ac15_retried_by_doctor_after_origin_recovers`
   red в среде без реальных учётных данных claude CLI/keychain**:
   `doctor.cmd_doctor()` агрегирует ВСЕ проверки — в песочнице этой
   разработческой сессии нет keychain-слотов `artel-developer`/
   `artel-reviewer`/`artel-test_author` и `claude` не залогинен
   (`live-smoke`/`isolation-smoke`/`token` красные по причинам,
   не имеющим отношения к T094: `security find-generic-password`,
   `claude setup-token` — операторские действия вне этой сессии).
   Сама механика ретрая снапшота внутри `doctor` работает верно —
   видно по её собственному `[ok] snapshot-pending:...` в выводе
   прогона; `sys.exit(1)` из `cmd_doctor` наступает от НЕСВЯЗАННЫХ
   проверок. Два других подтеста той же AC-15 (`...on_next_command...`,
   `...transition_completes...`) зелёные — они не зависят от полного
   `cmd_doctor`. Ослаблять `check_token`/`live_smoke` для обхода —
   запрещено принципом целостности; фикс — только на машине с
   настоящими credentials (Оператор/verifier), не код этой задачи.
3. **Диф `.github/workflows/ci.yml` не применён** — greplint (AC-4) и
   guard на `artifact/**` начнут реально работать только после того,
   как Оператор применит приложенный диф отдельным MR (тот же
   организационный риск, что и в T046).

## Предложения системе
- `orchestrator/config.py::AGENT_TIMEOUT_SEC` — временный бюджет 2700с
  (решение Оператора 02.09 на период стройки T094) откатился сам собой
  посреди работы предыдущей WIP-итерацией этой же ветки (вероятно —
  побочный эффект `git merge main` в другую сторону, до того как main
  получил свою правку 02.09, либо ручная правка не глядя на комментарий
  "Вернуть после мержа T094"). Класс «временное операторское решение
  живёт в коде без явного маркера, который бы мешал случайно его
  откатить раньше срока» — стоит подумать про отдельный файл/секцию
  для таких temporary override вместо инлайна в config.py, если
  подобное повторится ещё раз.

---

# Дифф для Оператора

Унифицированный диф защищённого пути `.github/workflows/ci.yml`
(SPEC требование 4/15, AC-4; реестр выше, пункт 4). Исполнитель его не
коммитит в ветку задачи; применяет и коммитит Оператор своим MR
отдельно (тот же приём, что T046). Проверено `git apply --check` на
чистом дереве main перед сдачей.

## .github/workflows/ci.yml

```diff
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -2,7 +2,10 @@

 on:
   push:
-    branches: ["main", "task/**"]
+    # "artifact/**" — артефактная ветка пульта задачи внешнего target'а
+    # (SPEC T094, требование 7): guard обязан валидировать структуру
+    # tasks/<id>/ и там же, не только на кодовых ветках self.
+    branches: ["main", "task/**", "artifact/**"]
   pull_request:

 jobs:
@@ -19,6 +22,33 @@
             echo "артефактов пока нет — ок"
           fi

+  id-format-greplint:
+    name: Линт — новый парсинг формата id задачи вне генератора
+    if: github.event_name == 'pull_request'
+    runs-on: ubuntu-latest
+    steps:
+      - uses: actions/checkout@v4
+        with: { fetch-depth: 0 }
+      - name: diff не добавляет парсинг формата id задачи вне orchestrator/idgen.py
+        env:
+          BASE_SHA: ${{ github.event.pull_request.base.sha }}
+        run: |
+          # SPEC T094, требование 4/AC-4: формат id задачи (ULID и легаси
+          # Tnnn) обязана знать только orchestrator/idgen.py — остальной
+          # код обращается с id как с непрозрачной строкой (требование 2).
+          # Линт смотрит только НОВЫЕ строки дифа (тот же приём, что
+          # protected-paths ниже) — существующий легаси-парсер
+          # (orchestrator/store.py, TASK_ID, требование 6) не тронут этим
+          # PR и линт его не видит.
+          PATTERN='T%0[0-9]|T\{[a-zA-Z_]*:0[0-9]+d\}|\\d\{3\}|TASK_ID *= *re\.compile|r["'"'"']\^?T\\\\?d'
+          ADDED=$(git diff "$BASE_SHA"...HEAD -- . ':!orchestrator/idgen.py' \
+            | grep -E '^\+' | grep -Ev '^\+\+\+' | grep -E "$PATTERN" || true)
+          if [ -n "$ADDED" ]; then
+            echo "::error::диф добавляет парсинг формата id задачи вне orchestrator/idgen.py (SPEC T094, требование 4):"
+            echo "$ADDED"
+            exit 1
+          fi
+
   python:
     name: Синтаксис и тесты оркестратора
     runs-on: ubuntu-latest
```

## Порядок коммита Оператором
1. Оператор применяет диф выше к `main` (или своей ветке правки
   защищённых путей) — `git apply` от корня репозитория пульта.
2. Коммитит результат сообщением в духе `T094: greplint формата id +
   guard на artifact/** в CI` и мержит в обход обычного FSM-конвейера
   задач (прецедент — правка скилов 26.08, T046).
3. После этого MR `id-format-greplint` реально начинает отклонять PR
   с новым парсингом формата id вне `orchestrator/idgen.py` (AC-4), а
   `guard` начинает валидировать структуру артефактов на
   `artifact/**`-ветках (реестр, пункт 4). Ветка `task/t094-...` в
   этот MR Оператора не участвует и не мержится вместе с ним.
