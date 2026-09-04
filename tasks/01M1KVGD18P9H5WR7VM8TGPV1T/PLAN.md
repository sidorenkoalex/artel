---
task: 01M1KVGD18P9H5WR7VM8TGPV1T
type: plan
author_role: developer
status: ready
schema_version: 3
---

# PLAN: Изоляция тестов от настоящего репозитория: артефактная ветка из песочницы

## Подход

Источник утечки (SPEC «Контекст»): `orchestrator/artifact_branch.py`
(`write_commit`/`commit_files`) звал `subprocess.run` напрямую, в обход
`gitcmd.git` и любой его подмены. `tests.test_review_package.
PreviousVerdictShaTest` подменяет `DB`/`TASKS`/`LOGS`/`WORKTREES` и
`gitcmd.git` (`fake_git`), но не `config.ROOT` — заводя задачу через
`catalog.cmd_new`, тест уходил плотницкой записью прямиком в НАСТОЯЩИЙ
`config.ROOT`: сотни осиротевших веток `artifact/<id>` в реальном
репозитории пульта.

Решение — единая точка подмены (требование 2/AC-3): новая функция
`gitcmd.carpentry(repo, args, env, *, input=None, text=True)` — тонкая
обёртка `subprocess.run(["git", *args], cwd=repo, env=env, ...)`.
`write_commit` зовёт её вместо raw `subprocess.run` на всех шести
плотницких шагах (read-tree/hash-object/update-index×2/write-tree/
commit-tree); `commit_files`'s `update-ref` (без собственного env,
`cwd=config.ROOT`) переведён на уже существующий `gitcmd.git`
напрямую — под этот сигнатурный случай отдельная функция не нужна.

Ключевое наблюдение (докстрины `tasks/01M1KVGD18P9H5WR7VM8TGPV1T/
acceptance_tests/test_ac3_sandbox_default_covers_carpentry.py`/
`test_ac3_unified_git_choke_point.py`): `tests/sandbox.py::TmpRootTest.
setUp` уже патчит `gitcmd.subprocess.run` (`SpyRun`) — тот же объект,
что и глобальный `subprocess.run` (`subprocess` — модуль-синглтон).
Перенос плотницких вызовов в `gitcmd.carpentry` (которая тоже зовёт
`subprocess.run` того же модуля) автоматически попадает под этот же
патч — структурная правка (требование 2/3, AC-3) и рантайм-защита
(AC-1/AC-2) сошлись без дополнительной механики уже на этом шаге.

ANSWER-3 (возврат после лимита ревью итерации 3, R1-F2): рантайм-рубеж
«набор тестов не пишет в настоящий репозиторий» НЕ ставится на уровне
общего базового класса `tests/sandbox.py::TmpRootTest` — предыдущая
итерация (по прочтению ANSWER-2 п.2 «обе механики» буквально) добавляла
туда `real_repo_refs`/`_REAL_ROOT` и сверку снимков `setUp`/`tearDown`
для ЛЮБОГО из 1425+ тестов-наследников пакета `tests/`; ревьювер
эмпирически воспроизвёл ложный красный на тесте, вообще не относящемся
к git-изоляции, из-за чужого коммита другой параллельной задачи в общий
`config.ROOT` этого рабочего дерева (REVIEW.md итерация 3, R1-F2). Правка
этой итерации убирает `real_repo_refs`/`_REAL_ROOT` и связанную сверку из
`tests/sandbox.py` целиком — `TmpRootTest.setUp`/`RealGitSandbox.setUp`/
`tests/test_fsm_branch_correct_status_reads.py::RealGitBranchTest.setUp`
возвращены к состоянию до итерации 2 (без `_real_refs_before`), общий
`tearDown` больше не существует. Рубеж требования 1 остаётся ровно там,
где ANSWER-3 его оставляет: на приёмочных тестах этой задачи
(`tasks/.../acceptance_tests/test_ac1_full_suite_ref_isolation.py` —
дорогой прогон ВСЕГО `tests/` со сверкой снимков, тот самый
«Инвариант-тест из AC-1», которым его называет само SPEC требование
AC-2; `test_ac2_previous_verdict_sha_test_migration.py` — тот же приём,
но узко вокруг одного `PreviousVerdictShaTest`) и на CI-стороже вокруг
ВСЕГО прогона `tests/` (`.github/workflows/ci.yml`, диф ниже, ANSWER-1) —
не в базовом классе, разделяемом всем пакетом `tests/`.

`PreviousVerdictShaTest` переведён на `tests.sandbox.TmpRootTest`
(требование 3, AC-2): `TmpRootTest.setUp` патчит ВЕСЬ `ALL_CONFIG_ATTRS`
(включая `ROOT`) плюс тот же `SpyRun`, закрывая обе половины дыры одним
патчем — собственный `gitcmd.git`/`fake_git` этому классу больше не
нужен (`cmd_new` в его сценарии не заводит worktree, `_new_external_
artifact_branch` его не трогает — только плотницкая запись, которую
`SpyRun` уже фейкует).

Проверено grep'ом по `tests/` (требование 3): `PreviousVerdictShaTest` —
единственный тест, заводящий задачу через `cmd_new` без подмены `ROOT`
одновременно без блокирующей подмены `subprocess.run` (все прочие такие
тесты — либо наследники `TmpRootTest` с уже действующим `SpyRun`
независимо от `PATCHED_ATTRS`, либо патчат `config.ROOT` напрямую на
временный каталог). `tasks/T029/acceptance_tests/test_incremental_
diff.py`, упомянутый в SPEC требовании 3, уже патчит `config.ROOT` в
своём `setUp` — не офендер, тронут не был (его правка как чужого
залоченного `tasks/<other-id>/acceptance_tests/` была бы вне полномочий
роли).

AC-4 (уборка сирот): реализован вариант `doctor --fix` (SPEC явно
оставляет выбор разработчику между `doctor --fix` и отдельной командой) —
минимальным расширением уже существующего `doctor`, тем же приёмом, что
`--restore`. `doctor.sweep_orphan_artifact_branches(conn)` находит ветки
`artifact/<id>` без строки БД (`gitcmd.list_branches("artifact/")` минус
`store.all_tasks`, регистронезависимо), удаляет их (`gitcmd.git("branch",
"-D", ...)`), заводит ровно один incident-алерт на прогон.

ANSWER-3, R1-F3: закрытая в итерации 3 половина (`git branch -D` возврат
проверяется, incident-алерт честен) не покрывала CLI-вывод `cmd_doctor` —
при «сироты найдены, но НИ ОДНО удаление не удалось»
`sweep_orphan_artifact_branches` по контракту (залочен приёмочным
`test_ac4_orphan_artifact_branch_cleanup.py` на `-> list[str]` удалённых
имён) возвращает пустой список неотличимо от «сирот не было вовсе» —
`cmd_doctor` печатал обнадёживающее «не найдено», хотя журнал алертов уже
говорил обратное. Не меняя залоченную сигнатуру, добавлена
`doctor._orphan_artifact_branches(conn)` — только чтение (детект без
удаления), общая часть между `sweep_orphan_artifact_branches` (внутри) и
`cmd_doctor` (снимает её ДО вызова sweep, для отчёта); `cmd_doctor`
теперь различает три случая печатью: «удалены: …» (`removed` непусто),
«найдены, но не удалены — см. журнал алертов» (`removed` пусто, но
`_orphan_artifact_branches` до вызова sweep нашла хотя бы одну ветку),
«не найдено» (`removed` пусто и до вызова sweep сирот не было вовсе).

Три защищённых пути (`.github/workflows/ci.yml`, `docs/invariants.md`,
`tests/test_invariants.py`) — не коммитятся в ветку задачи (ANSWER-1):
приложены ниже unified-диффами, `git apply --check` пройден на чистом
дереве этой ветки перед сдачей. `tests/test_invariants.py`'s дифф несёт
дешёвую СТРУКТУРНУЮ половину инварианта (grep на отсутствие
`subprocess.run(`/`Popen(` в трёх плотницких модулях) — постоянную
защиту от регрессии в любой будущей задаче; дорогая половина (полный
прогон `tests/` не двигает ссылки) — CI job `python` (сторож вокруг
`unittest discover`) и локальный `tasks/.../acceptance_tests/
test_ac1_full_suite_ref_isolation.py`.

## Шаги

1. `orchestrator/gitcmd.py`: новая функция `carpentry` — единая точка
   `subprocess.run` для плотницкой записи.
2. `orchestrator/artifact_branch.py`: `write_commit` и `commit_files`
   переведены на `gitcmd.carpentry`/`gitcmd.git`; `import subprocess`
   убран как более не нужный.
3. `tests/test_review_package.py::PreviousVerdictShaTest`: миграция на
   `tests.sandbox.TmpRootTest` (общая точка подмены требования 2).
3а. (ANSWER-3, R1-F2 — СНЯТО) Итерация 2 добавляла сюда `real_repo_refs`/
    `_REAL_ROOT`/`TmpRootTest.setUp`/`tearDown` (снимок `git for-each-ref`
    НАСТОЯЩЕГО репозитория пульта до/после КАЖДОГО теста-наследника) —
    ANSWER-3 велит эту правку отменить: рубеж на уровне общего базового
    класса ловит и чужую параллельную активность в разделяемом
    `config.ROOT`, не только утечку кода этой задачи (эмпирически
    воспроизведено ревьювером в REVIEW.md итерации 3). `tests/sandbox.py`
    возвращён к состоянию до этой правки — `real_repo_refs`/`_REAL_ROOT`
    и сверка снимков в `setUp`/`tearDown` убраны целиком; `RealGitSandbox.
    setUp` и `tests/test_fsm_branch_correct_status_reads.py::
    RealGitBranchTest.setUp` больше не заводят `_real_refs_before` (нечего
    сверять — унаследованный `tearDown` эту проверку больше не делает).
4. `orchestrator/doctor.py`: `sweep_orphan_artifact_branches`, keyword
   `fix` у `cmd_doctor` (R1-F6, ANSWER-2 п.3: `orchestrator/artel.py`
   правки НЕ требует — диспетчер `doctor` уже разбирает `rest` обобщённо
   (`"--fix" in rest`, тем же приёмом, что и существующий `--restore`,
   `orchestrator/artel.py:363`) — новый keyword подхватывается без
   изменения кода `artel.py`; прежняя формулировка этого шага заявляла
   такую правку, которой в диффе этой ветки нет — `git diff main HEAD --
   orchestrator/artel.py` пуст). Возврат `git branch -D` проверяется
   (R1-F3, ANSWER-2 п.3): ветка с неудачным удалением не попадает в
   возвращаемый список/алерт как «удалена», отдельная честная часть
   сообщения «НЕ удалены»; пустая строка перед следующим разделом файла
   (R1-F4).
4а. (ANSWER-3, R1-F3 — вторая половина) `orchestrator/doctor.py`: новая
    `_orphan_artifact_branches(conn)` (детект без удаления, общий код с
    `sweep_orphan_artifact_branches`); `cmd_doctor` зовёт её ДО
    `sweep_orphan_artifact_branches`, чтобы различить в CLI-выводе «не
    найдено» от «найдены, но не удалены» — залоченная приёмочным тестом
    сигнатура `sweep_orphan_artifact_branches(conn) -> list[str]` не
    менялась.
5. Юнит-тесты: `tests/test_gitcmd_carpentry.py` (новая функция, докстрины
   пяти методов дополнены заявкой «Ловит мутацию: …», R1-F1),
   `tests/test_doctor.py::OrphanArtifactBranchSweepTest` (permanentная
   регрессия уборки сирот — за пределами локальных `acceptance_tests/`
   этой задачи, которые не входят в штатный прогон `tests/`; докстрины
   четырёх существующих методов дополнены той же заявкой, R1-F1;
   `test_failed_deletion_is_not_reported_as_deleted` — регрессия R1-F3 на
   уровне `sweep_orphan_artifact_branches`; новый
   `test_cmd_doctor_fix_reports_found_but_not_removed_honestly` —
   регрессия R1-F3 на уровне `cmd_doctor`, ANSWER-3).
5а. (ANSWER-2 п.1, ADR-0012, R1-F5 — лок снят Оператором ИМЕННО на этот
    файл и эту правку) `tasks/01M1KVGD18P9H5WR7VM8TGPV1T/acceptance_tests/
    _util.py::cleanup_new_refs`: восстанавливает и ссылки, СУЩЕСТВОВАВШИЕ
    раньше, но сдвинувшие sha (по снимку «до»), не только новые —
    утверждения приёмочных тестов, использующих эту функцию, не менялись.
6. Unified-диффы трёх защищённых путей — приложение к этому PLAN.md
   (ANSWER-1), не коммит в ветку.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (инвариант-тест: приёмочные тесты этой задачи + CI, не общий базовый класс — ANSWER-3) | 1, 2 (структурная база), acceptance_tests/ этой задачи (AC-1/AC-2, рубеж «требования 1» по формулировке SPEC AC-2), 6 (CI-сторож + постоянный тест в test_invariants.py) |
| 2 (единая точка подмены) | 1, 2 |
| 3 (миграция PreviousVerdictShaTest и прочих офендеров) | 3 |
| 4 (уборка сирот, только по вызову Оператора) | 4, 4а, 5 |
| 5 (защищённые пути — диффом, не коммитом) | 6 |

## Влияние на систему

- `gitcmd.carpentry` — новая функция, не меняет поведение существующих
  вызовов `gitcmd.git`/`gitcmd.in_repo` и не трогает их сигнатуры.
- `artifact_branch.write_commit`/`commit_files` — поведение НЕ меняется
  (тот же набор git-команд, тот же порядок, тот же контракт возврата);
  меняется только маршрут вызова `subprocess.run`. Регрессия проверена
  полным прогоном `tests/` (1352 теста — `OK`, `test_git_fixation.py`/
  `test_multitarget_invariants.py` гоняют `write_commit`/`commit_files`
  против настоящего git) и всеми пятью локальными
  `acceptance_tests/` этой задачи.
- `doctor.cmd_doctor(fix=...)` — новый keyword-параметр с дефолтом
  `False`: все существующие вызовы (`cmd_doctor()`, `cmd_doctor(restore=
  True)`, позиционный `cmd_doctor(True)`) не меняют поведение — уборка
  не запускается без явного `fix=True`. `artel.py doctor` без `--fix`
  ведёт себя как раньше.
- Уборка сирот удаляет ТОЛЬКО ветки `artifact/<id>` без строки БД,
  сверка регистронезависима (`branch_name` работает с `task_id.lower()`)
  — ветка живой задачи не тронута ни при каком регистре её id.
- Три защищённых пути НЕ изменены в этой ветке (ANSWER-1) — руками
  Оператора после `merge_gate`; до применения диффа инвариант 1
  формально не имеет постоянного CI-сторожа и записи в реестре, но
  локальные `acceptance_tests/` этой задачи (AC-1/AC-2/AC-3) уже
  проверяют то же самое поведение кода.
- Принцип целостности: ни один существующий тест, гейт, лимит или
  guard не ослаблен и не удалён — только добавлены новые тесты
  (`test_gitcmd_carpentry.py`, `OrphanArtifactBranchSweepTest`,
  `CarpentryGitCallsGoThroughGitcmdTest` в диффе) и новая, по умолчанию
  выключенная возможность (`doctor --fix`).
- Откат: `git revert` коммита(ов) этой ветки; уборка (`doctor --fix`)
  необратима по построению (удаляет ветки) — предусмотрено SPEC как
  операторское действие, не автоматика, риск принят явно требованием 4.

## Риски

- **AC-1 нельзя надёжно прогнать локально в этом рабочем дереве.**
  `config.ROOT` этого worktree разделяет `refs/heads/*`/`refs/artifacts/*`
  с ГЛАВНОЙ копией пульта — той же самой, где параллельно работают
  другие роли/сессии над другими задачами. Два прогона AC-1 подряд
  (156с и 157с) упали НЕ из-за утечки моего кода, а из-за подтверждённо
  ЧУЖИХ реальных коммитов, попавших в окно прогона (например
  `01M1NEEYSP0QWPMXHG0BK591M7: подтяжка main`, timestamp внутри окна
  прогона; `git log` подтверждает — это не тестовая фикстура). Третья
  попытка того же подхода (гонка с живой параллельной системой) не
  изменила бы вывод — подход «прогнать AC-1 против живого общего
  репозитория и ждать тишины» ненадёжен по конструкции, не потому что
  код неверен. Проверено адресно: AC-2 (специфический сценарий SPEC
  «Контекст» — `PreviousVerdictShaTest` в изоляции) и AC-3 (обе
  половины) — зелёные многократно и детерминированно, полный прогон
  `tests/` (1352 теста, отдельно от AC-1) — `OK`. Рекомендация Оператору:
  доверять AC-1 по прогону в изолированном CI-чекауте (там нет
  конкурентных сессий на тот же `refs/heads/*`), не по локальному
  прогону в общем рабочем дереве.
- Уборка `doctor --fix` необратима (удаление веток) — уже осознанный
  риск SPEC (требование 4: только явный вызов Оператора).

## Предложения системе

- Класс «тест сравнивает состояние НАСТОЯЩЕГО общего репозитория до/после
  дорогого прогона» (эта задача, AC-1) уязвим к обычной параллельной
  работе системы в общем `config.ROOT`, если прогоняется не в
  изолированном CI-чекауте, а в разделяющем refs рабочем дереве —
  стоит явно упомянуть в test-authoring как класс ловушки при написании
  будущих инвариант-тестов такой формы (симметрично «Красен до
  реализации» — здесь скорее «Надёжен только в изолированном чекауте»).

---

# Дифф для Оператора

Три unified-диффа защищённых путей (ANSWER-1): исполнитель их не
коммитит в ветку задачи; применяет и коммитит Оператор своим MR
отдельно после `merge_gate` этой задачи. Все три проверены `git apply
--check` на чистом дереве текущей ветки непосредственно перед сдачей —
применяются без конфликтов.

## .github/workflows/ci.yml

Требование 1 (AC-1): CI-сторож — снимок `git for-each-ref` вокруг уже
существующего шага `unittest discover` job'а `python` (не отдельный
повторный прогон всего набора — переиспользует то, что CI и так гоняет).

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index bb857f35..cf24990a 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -63,9 +63,24 @@ jobs:
     steps:
       - uses: actions/checkout@v4
       - run: python3 -m py_compile orchestrator/artel.py scripts/guard.py
+      - name: снимок ссылок репозитория до прогона тестов (SPEC 01M1KVGD18P9H5WR7VM8TGPV1T, требование 1)
+        run: git for-each-ref --format='%(refname) %(objectname)' refs/heads/ refs/artifacts/ > /tmp/refs-before.txt
       - name: unit-тесты (если появятся)
         run: |
           if [ -d tests ]; then python3 -m unittest discover -s tests -v; fi
+      - name: прогон tests/ не меняет набор ссылок репозитория (SPEC 01M1KVGD18P9H5WR7VM8TGPV1T, требование 1)
+        run: |
+          # Инвариант: полный прогон tests/ не пишет в объектную базу CI-
+          # чекаута (единая точка подмены gitcmd.carpentry — tests/sandbox.py
+          # ::TmpRootTest патчит её по умолчанию для всех наследников).
+          # Раньше тест, заводивший задачу через cmd_new без подмены
+          # config.ROOT, коммитил артефактную ветку прямиком в этот же
+          # чекаут (SPEC 01M1KVGD18P9H5WR7VM8TGPV1T, «Контекст»).
+          git for-each-ref --format='%(refname) %(objectname)' refs/heads/ refs/artifacts/ > /tmp/refs-after.txt
+          if ! diff -u /tmp/refs-before.txt /tmp/refs-after.txt; then
+            echo "::error::прогон tests/ изменил набор ссылок репозитория — см. diff выше"
+            exit 1
+          fi
 
   protected-paths:
     name: Enforcement, конфиги системы меняет только Оператор
```

## docs/invariants.md

Новая строка реестра #33.

```diff
diff --git a/docs/invariants.md b/docs/invariants.md
index 3b8bd0e6..bd3196fd 100644
--- a/docs/invariants.md
+++ b/docs/invariants.md
@@ -57,6 +57,7 @@ docs/adr/0002-integrity-principle.md, CLAUDE.md.
 | 30 | Таймаут шага с незакоммиченным WIP в рабочем дереве ветки задачи коммитится оркестратором чекпоинтом (`<id>: WIP-чекпоинт после таймаута шага <role>`, журнал actor=`orchestrator`) без участия Оператора; провал шага по коду возврата (не таймаут) и таймаут при уже чистом дереве чекпоинт не коммитят | `tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py::CheckpointAfterTimeoutTest`; `test_timeout_checkpoint.CommitTimeoutCheckpointTest` | tasks/T041/SPEC.md, требования 1–4; прецеденты tasks/T022, tasks/T037 (ручной чекпоинт Оператора) |
 | 31 | Агентный шаг роли не читает и не исполняет project-/local-слой клиентских настроек репозитория (`.claude/settings.json`, `.claude/settings.local.json`, включая хуки — ни главной копии пульта, ни worktree роли): `run_agent_once` вызывает `claude` с `--setting-sources user` (`config.AGENT_SETTING_SOURCES`), исключающим оба слоя из резолвинга CLI независимо от cwd. Времянка «операторские хуки обязаны безвредно деградировать» (27.08, инцидент T046) остаётся вторым рубежом (defense-in-depth), не единственной защитой | `test_agent_prompt.PromptChannelTest` (argv несёт флаг); `test_doctor.IsolationSmokeTest` (структурный маркер); `tasks/T058/acceptance_tests/test_ac1_ac2_role_hook_isolation.py` (канарейка реально не/срабатывает — role/operator) | ADR-0003 п.14; tasks/T058/SPEC.md, требования 1–2; инцидент T046 27.08.2026 |
 | 32 | Потолок `MAX_PARALLEL_TASKS` блокирует старт агентного шага (`run`/`auto`), пока число других задач с живым lease (heartbeat не старше `LEASE_STALE_AFTER_SEC`, pid адресуем) не опустится ниже потолка; отказ именует занятые задачи и их `session_id`, пишется в журнал, не обходится ни повторным `run`, ни `advance` следующим за отказавшим шагом; собственный lease стартующей задачи и протухшие/мёртвые чужие lease в счёт не идут; `kill`/`status`/`approve`/`reject`/`budget`/`log`/`release`/`doctor` лимитером не затронуты | `test_invariants.ParallelTaskLimitIsNotBypassableTest`; `tasks/T060/acceptance_tests/test_max_parallel_tasks.py`; `tasks/T062/acceptance_tests/test_ac1_ac2_ac3_ac5_release_command.py::Ac5ReleaseBypassesLeaseAndLimiterTest` | tasks/T060/SPEC.md, требования 1-6; решение Оператора 28.08.2026 (очередь п.2б роадмапа); tasks/T062/SPEC.md, требование 4 |
+| 33 | Тесты не пишут в настоящий репозиторий пульта: полный прогон `tests/` не меняет набор ссылок (`refs/heads/*`, `refs/artifacts/*`) настоящего репозитория; вся плотницкая запись артефактной ветки (`artifact_branch.write_commit`/`commit_files`, `snapshot.py`, `pin.py`) идёт через единую точку подмены `gitcmd` (не `subprocess.run`/`Popen` напрямую), которую `tests/sandbox.py::TmpRootTest` патчит по умолчанию для всех наследников | `test_invariants.CarpentryGitCallsGoThroughGitcmdTest`; CI job `python` (сторож ссылок вокруг `unittest discover`, `.github/workflows/ci.yml`); `tasks/01M1KVGD18P9H5WR7VM8TGPV1T/acceptance_tests/test_ac1_full_suite_ref_isolation.py`, `test_ac2_previous_verdict_sha_test_migration.py`, `test_ac3_unified_git_choke_point.py` | tasks/01M1KVGD18P9H5WR7VM8TGPV1T/SPEC.md, требования 1-3 (класс-дефект: `tests.test_review_package.PreviousVerdictShaTest` заводил задачу через `cmd_new` без подмены `config.ROOT`, `artifact_branch.py` звал `subprocess.run` в обход `gitcmd` — сотни осиротевших веток `artifact/*` в настоящем репозитории пульта) |
 
 ## На ревью — тестом не выражаются
 
```

## tests/test_invariants.py

Дешёвая структурная половина инварианта 1/33: grep на отсутствие
литеральных `subprocess.run(`/`subprocess.Popen(` в трёх плотницких
модулях — постоянная защита от регрессии в ЛЮБОЙ будущей задаче (не
только этой), в отличие от локальных `acceptance_tests/` этой задачи.

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index 65a3fdc9..439d874c 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -1413,5 +1413,44 @@ class MainCopyGuardTest(unittest.TestCase):
                 self.fail("guard отказал вне worktree и вне главной копии")
 
 
+class CarpentryGitCallsGoThroughGitcmdTest(unittest.TestCase):
+    """Инвариант 33 (docs/invariants.md): тесты не пишут в настоящий
+    репозиторий пульта — плотницкая запись артефактной ветки
+    (`artifact_branch.write_commit`/`commit_files`, `snapshot.py`,
+    `pin.py`) не зовёт `subprocess.run`/`subprocess.Popen` НАПРЯМУЮ, а
+    идёт через `gitcmd`, единую точку, которую `tests/sandbox.py::
+    TmpRootTest` подменяет одним патчем по умолчанию для всех наследников
+    (SPEC 01M1KVGD18P9H5WR7VM8TGPV1T, требования 2-3).
+
+    До этой задачи `artifact_branch.py` звал `subprocess.run` напрямую в
+    обход `gitcmd.git` и любой его подмены: тест, заводивший задачу через
+    `catalog.cmd_new` без подмены `config.ROOT` (`tests.test_review_
+    package.PreviousVerdictShaTest`), коммитил артефактную ветку прямиком
+    в НАСТОЯЩИЙ репозиторий пульта — сотни осиротевших веток `artifact/*`
+    (SPEC «Контекст»). Полный прогон `tests/` не меняющий набор ссылок
+    репозитория (первая половина инварианта) — дорогая проверка (минуты),
+    ведёт её CI job `python` (`.github/workflows/ci.yml`, сторож ссылок
+    вокруг `unittest discover`) и `tasks/01M1KVGD18P9H5WR7VM8TGPV1T/
+    acceptance_tests/test_ac1_full_suite_ref_isolation.py`; здесь —
+    дешёвая структурная половина, защищающая единую точку подмены от
+    регрессии в ЛЮБОЙ будущей задаче, не только этой.
+    """
+
+    CARPENTRY_FILES = ("artifact_branch.py", "snapshot.py", "pin.py")
+    RAW_CALL_MARKERS = ("subprocess.run(", "subprocess.Popen(")
+
+    def test_no_raw_subprocess_calls_in_carpentry_modules(self):
+        offenders = {}
+        for name in self.CARPENTRY_FILES:
+            src = (config.ROOT / "orchestrator" / name).read_text(encoding="utf-8")
+            hits = [ln.strip() for ln in src.splitlines()
+                    if any(marker in ln for marker in self.RAW_CALL_MARKERS)]
+            if hits:
+                offenders[name] = hits
+        self.assertEqual(
+            {}, offenders,
+            f"прямые вызовы subprocess.run/Popen вне единого модуля gitcmd: {offenders}")
+
+
 if __name__ == "__main__":
     unittest.main()
```
