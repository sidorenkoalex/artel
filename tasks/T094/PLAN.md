---
task: T094
type: plan
author_role: developer
status: ready
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
   вызывается из `fsm_advance.review`/`verifying`). Было: `run(tdir)`
   брал `acceptance_tests/` с ДИСКА `tdir` (worktree кодовой ветки) —
   для внешнего target такого диска нет (checkpoint итерации 2 уносит
   каталог в артефактную ветку сразу по завершении шага роли).
   Редирект: `acceptance.materialize_from_branch(task_id, branch)` —
   вычитывает `acceptance_tests/` из артефактной ветки пульта во
   временный каталог перед прогоном, вызывающий код убирает его сам
   (`shutil.rmtree` в `finally`). **Сделано** (итерация 3, шаг 17;
   было отложено в итерациях 1-2 — REVIEW.md итерация 2, замечание 2).
3. **Ветко-корректные чтения статусов и брифов**:
   - `orchestrator/brief.py` (`developer_brief`, `analyst_map_component`,
     `test_author_answer_component`) — редиректнуто: общая точка входа
     `_artifact_source_branch` возвращает ветку артефактов и `foreign=True`
     для любого target, кроме self. **Сделано** (шаг 9); с итерации 3
     делегирует общему `orchestrator/artifact_source.py::resolve`
     (не плодит копию логики, см. ниже).
   - `orchestrator/catalog.py` (`cmd_show` → `_artifact_frontmatter`) —
     редиректнуто: frontmatter SPEC/PLAN/REVIEW/TEST_REPORT читается
     `gitcmd.show(artifact_branch.branch_name(task_id), ...)` для
     внешнего target. **Сделано** (шаг 3).
   - `orchestrator/cleanup.py` (`_journal_tz_before_cleanup`) —
     редиректнуто: TZ.md перед уборкой читается с артефактной ветки для
     внешнего target. **Сделано** (шаг 3).
   - `orchestrator/fsm.py` (`_read_branch_text_or_refuse`,
     `_answer_file_count`, `_answer_baseline_or_refuse`, `_cmd_approve`
     ветка `spec_gate`) и `orchestrator/fsm_advance.py` (`spec_writing`,
     `review`, `tests_writing`, `in_dev`) — читали `tasks/<id>/*.md`
     с `t["branch"]` (кодовая ветка целевого — для внешнего target в
     `config.ROOT` вообще не существующая). Редирект: общий резолвер
     `orchestrator/artifact_source.py::resolve(conn, task_id)` —
     `(ветка-источник, foreign)`, self байт-в-байт прежнее поведение,
     любой другой target — артефактная ветка пульта безусловно.
     **Сделано** (итерация 3, шаг 17; закрывает REVIEW.md итерация 2,
     замечание 2 — «Вопрос Оператору — требование 10» ниже снят,
     раздел оставлен как исторический след решения).

     Сознательно НЕ тронуто, вне буквального текста требования 10 (не
     чтения `tasks/<id>/`): `_pull_main_or_escalate` (merge `main` в
     ветку задачи, `fsm.py`) и `ci.verifying_status` (`fsm_advance.
     verifying`) — обе уже до T094 работают ИСКЛЮЧИТЕЛЬНО с `config.
     ROOT` (`workspace.ensure`/`gh api` без параметра репозитория) и
     не читают артефакты; для внешнего target — мёртвый путь уже
     сегодня (ни один target не доходит до `verifying`/branch-freshness
     гейта), топология CI/git внешнего репозитория — вопрос A7, не M1
     (SPEC «Не входит»). Подробности — «Шаги», итерация 3.
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
7. **`orchestrator/runner.py::role_cwd`/`orchestrator/checkpoint.py::
   commit_step_artifacts`** — `role_cwd` для внешнего target ПРАВИЛЬНО
   остаётся клоном ЕГО кода (`config.PROJECTS/<target>/workspace`, не
   артефактной веткой пульта — ADR-0003 §4: роль обязана видеть только
   код целевого): это не пробел, редиректить сам `role_cwd` было бы
   ошибкой. Пробел был НИЖЕ по цепочке: то, что роль пишет `tasks/<id>/`
   в этот каталог (как и в догфуде — роль не знает об артефактной
   ветке), никуда не переносилось после реального шага (не только
   `cmd_new`). **Исправлено** (REVIEW.md T094 итерация 1, замечание 2):
   `checkpoint._commit_external_step_artifacts` — новая ветка
   `commit_step_artifacts` для внешнего target — коммитит написанное
   ролью в артефактную ветку пульта плотницки (`artifact_branch.
   commit_files`) и убирает исходники из клона целевого; покрыто
   `tests/test_checkpoint_external_step_artifacts.py` (5 тестов:
   попадание в артефактную ветку, уборка из клона, накопление между
   шагами, нечего коммитить — не отказ, журнал). AC-9 (`tasks/T094/
   acceptance_tests/test_ac9_role_step_artifact_branch.py`) по-прежнему
   целится только в `cmd_new` (тест залочен T023, не переписывается
   этой правкой) — новый юнит-тест закрывает тот же критерий для
   ОСТАЛЬНЫХ шагов роли, которые AC-9 буквально не проверяет.

**Резюме перенаправления**: пункты 1-3 (целиком, включая fsm.py/
fsm_advance.py-часть и acceptance.py::run — итерация 3), 4 (диф), 6, 7
— сделаны и покрыты тестами (включая `extproj` — тестовый внешний
target песочницы). Требование 8 закрыто целиком (шаг 7); требование
10 закрыто целиком для всех точек реестра (brief.py/catalog.py/
cleanup.py/fsm.py/fsm_advance.py/acceptance.py) — детали редиректа
ядра FSM и то, что сознательно НЕ входит в буквальный текст требования
(`_pull_main_or_escalate`/`ci.verifying_status`, обе ортогональны
`tasks/<id>/`) — «Шаги», итерация 3.

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

Итерация 2 (закрытие REVIEW.md итерации 1, замечание 2): `checkpoint.
commit_step_artifacts` для внешнего target — реализовано (шаг 13 ниже,
реестр пункт 7).

Итерация 3 (закрытие REVIEW.md T094 итерации 2, замечание 2): ядро
`orchestrator/fsm.py`/`fsm_advance.py`/`acceptance.py` (реестр, пункты
2, 3) — редиректнуто общим резолвером `orchestrator/artifact_source.py`
(шаг 17 ниже). Итерации 1-2 откладывали этот кластер как «крупный
риск регресса core-модуля без реального внешнего target для живого
прогона»; по факту редиректа риск оказался ниже предполагавшегося —
все тронутые чтения (`SPEC.md`/`REVIEW.md`/`PLAN.md`/`QUESTIONS.md`/
`ANSWER-*.md`/`acceptance_tests/`) уже читаются ИЗ `config.ROOT` (тем
же репозиторием, что и self — только другое имя ветки), не из
второго/внешнего репозитория — редирект не потребовал нового
git-транспорта, только замены источника имени ветки; риск регресса
self закрыт полным прогоном `tests/` (1191 тестов, без изменений)
после правки. Операции, которые ДЕЙСТВИТЕЛЬНО работают только с
`config.ROOT` независимо от target (`_pull_main_or_escalate`'s merge,
`ci.verifying_status`'s `gh api`) — НЕ читают `tasks/<id>/` вовсе, вне
буквального текста требования 10, оставлены как есть (реестр, пункт 3).

Редирект сделан там, где он ПРОВЕРЯЕМ прямо сейчас: `cmd_new`
(заведение задачи), каждый шаг роли внешнего target (`checkpoint.
commit_step_artifacts`), `cleanup`/`fsm_merge_gate` (закрытие: снапшот
+ паспорт + TZ-журнал), `brief.py`/`fsm.py`/`fsm_advance.py`/
`acceptance.py` (вход роли self читает как раньше; вход роли внешнего
target и все чтения переходов FSM — из артефактной ветки, покрыто
тестами `extproj`-песочницы), `catalog.cmd_show`, `doctor` (ретрай
снапшота, деградация счётчика).

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
   `acceptance.py`) — НЕ редиректнуто, задокументировано в реестре выше
   (пункты 2/3) и в «Вопрос Оператору — требование 10».
   `runner.role_cwd` — правильно НЕ редиректнуто (ADR-0003 §4: роль
   обязана видеть только код целевого), пробел был не в нём, а в том,
   что происходит с написанным ролью tasks/<id>/ ПОСЛЕ шага — закрыто
   шагом 14.
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

Итерация 2 (закрытие REVIEW.md T094 итерации 1):
13. Систематическая правка резолва префикса id (AC-3, замечание 1 —
    blocker): `task_id = store.resolve_task_id(conn, task_id)` теперь
    вызывается ОДИН РАЗ на самом верху каждой из 15 id-принимающих
    CLI-команд (`catalog.cmd_show`/`cmd_log`, `cleanup.cmd_kill`,
    `workspace.cmd_workspace`, `fsm.cmd_advance`/`cmd_approve`/
    `cmd_reject`, `runner.cmd_run`, `auto.cmd_auto`, `budget.cmd_budget`,
    `answer.cmd_answer`, `release.cmd_release`, `pause.cmd_pause`/
    `cmd_resume`/`cmd_pause_now`), ДО lease/CAS/путей на диске/журнала —
    прежде резолв срабатывал только внутри `store.get_task` и терялся
    для остального тела вызывающей функции (живые репро ревью:
    зависающий `kill`, теряющий строки `log`, ложно отказывающий
    `advance`, необработанный `CasConflict` в `reject`). Регресс-тесты
    — `tests/test_task_id_prefix_regression.py` (kill/log/advance/
    reject/workspace, 5 тестов, каждый проверен и на то, что ловит
    реверт правки).
14. `checkpoint._commit_external_step_artifacts` (требование 8,
    замечание 2 — major): см. реестр выше, пункт 7. Тесты —
    `tests/test_checkpoint_external_step_artifacts.py` (5 тестов).
15. Тестовое покрытие пути `done` для AC-13 (замечание 3 — major):
    `tasks/T094/acceptance_tests/` залочен (T023) — новый акцептанс-тест
    добавить нельзя (правка залоченного набора = эскалация, не
    разработческая правка); закрыто юнит-тестом `tests/
    test_fsm_merge_gate_done_snapshot.py` (2 теста, симметрично AC-13/
    AC-14 приёмочным тестам `killed`-пути): `_cmd_approve_merge_gate`
    прогоняется через НАСТОЯЩИЙ git (пульт с bare-`origin`, целевой
    workspace + bare-`origin` целевого — тот же приём, что `_sandbox.
    py::ExternalTargetGitSandbox`) до фактического перехода в `done`,
    проверяется появление `refs/artifacts/<id>` в origin целевого с
    RETRO (operator/model/artel_sha) и уборка артефактной ветки пульта.
    Оба теста проверены и на то, что ловят регресс (временное удаление
    снапшот-блока из `fsm_merge_gate.py` красит оба теста, не только
    один).

Итерация 3 (закрытие REVIEW.md T094 итерации 2, оба major):
16. `checkpoint._commit_external_step_artifacts` больше не теряет
    не-UTF8/бинарные файлы (замечание 1 — major): читает `path.
    read_bytes()` вместо `read_text(encoding="utf-8")`, `artifact_branch.
    write_commit` принимает `files[rel]` и как `str`, и как `bytes`
    (хэширует байты напрямую, `str` кодирует UTF-8 сама) — тем же
    способом, что self-путь (`_commit_worktree_change`, настоящий
    `git add -A`) уже не терял ничего. Тесты — `tests/
    test_checkpoint_external_step_artifacts.py`, два новых
    (`test_binary_file_is_not_lost`, `test_all_files_binary_still_
    commits_and_clears_the_dir`) закрывают оба случая из замечания:
    смесь текст+бинарник и каталог целиком из нечитаемых-как-текст
    файлов.
17. Требование 10 для ядра FSM закрыто реализацией, не эскалацией
    (замечание 2 — major, «Вариант А» из «Вопрос Оператору — требование
    10» ниже — раздел оставлен в PLAN.md как исторический, вопрос снят):
    общий резолвер `(ветка, foreign)` вынесен в новый модуль
    `orchestrator/artifact_source.py::resolve` (тот же приём, что уже
    нёс `brief._artifact_source_branch` — та теперь делегирует ему,
    не плодит копию логики) и применён к `orchestrator/fsm.py`
    (`_answer_file_count`, `_answer_baseline_or_refuse`, `_cmd_approve`
    ветка `spec_gate`) и `orchestrator/fsm_advance.py` (`spec_writing`,
    `review`, `tests_writing`, `in_dev`) — вместо `t["branch"]`
    (кодовая ветка, для внешнего target в `config.ROOT` вообще не
    существующая) везде читается резолвленная ветка-источник
    `tasks/<id>/` (артефактная ветка пульта для любого не-self target).

    `acceptance.py` получил `materialize_from_branch(task_id, branch)`
    (реестр выше, пункт 2 — «лок acceptance_tests», был отложен в
    итерациях 1-2): для внешнего target `acceptance_tests/` не лежит
    ни на каком диске (checkpoint итерации 2 переносит его в
    артефактную ветку сразу по завершении шага роли) — функция
    материализует его во временный каталог перед прогоном
    (`fsm_advance.review`/`verifying`, оба чистят каталог `finally`);
    self-путь (реальный worktree на диске) не тронут ни строкой.

    Сознательно НЕ тронуто (не входит в буквальный текст требования 10
    — «чтения из реестра требования 1», не тот же класс, что текстовые
    чтения tasks/<id>/): `_pull_main_or_escalate`'s merge `config.
    MAIN_BRANCH` в ветку задачи и `ci.verifying_status` — обе уже до
    этой задачи операции ИСКЛЮЧИТЕЛЬНО `config.ROOT` (`workspace.
    ensure`/`gh api repos/{owner}/{repo}/...` без параметра репозитория)
    и НЕ читают `tasks/<id>/`; для внешнего target это не регресс
    (граница CI/git-репозитория внешнего target — вопрос топологии A7,
    не M1, SPEC «Не входит»), только заведомо мёртвый путь, пока
    `targets.yaml` не объявляет ни одного target, доходящего до
    `verifying`/branch-freshness гейта. `_autogate_conditions`'s
    `acceptance.run_full_suite(wt_root)` (полный `tests/` НЕ `tasks/<id>/`)
    для внешнего target остаётся `wt_root is None` (worktree пульта не
    заводится для внешнего target) — автогейт корректно отказывает и
    ждёт Оператора, деградация безопасна, не крах.

    Лок acceptance_tests (`in_dev`, сверка `tests_locked_sha`) резолвит
    правильную ветку-источник для `lock_ref`, но сама сверка для
    внешнего target и после этой правки не может пройти успешно:
    `tests_locked_sha`/`fixed_sha` остаются на легаси-схеме фиксации
    (`fixation._fix_external`, коммит `.artel/projects/<target>/`,
    требование 9 — «не заменяя легаси-строку», реестр пункт 1) — sha
    ИЗ ЭТОГО репозитория `config.ROOT` не знает независимо от выбора
    ветки. Не новый регресс этой правки (лок и раньше не мог сверить
    легаси-sha с `config.ROOT`), а незакрытый остаток легаси-схемы
    `fixed_sha`, документированный inline в `fsm_advance.in_dev`.

    Регресс self: 1191 тестов `tests/` зелёные без изменений (полный
    прогон после правки), self-путь ни в одной из тронутых функций не
    меняет ветвление (условие на `target != config.DEFAULT_TARGET` или
    эквивалентное `foreign`, вычисленное тем же кодом, что и раньше для
    self — `artifact_source.resolve` для self буквально повторяет
    прежнюю формулу `brief._artifact_source_branch`). Три существующих
    юнит-теста, симулировавших внешний target ЛЕГАСИ-схемой (`tasks/
    <id>/` прямо на диске `.artel/projects/<target>/tasks/<id>/`,
    предшествующей топологии Б₃), обновлены под артефактную ветку
    (`tests/test_git_fixation.py::ExternalTargetAdvanceIgnoresDirtyCheckTest`,
    `ExternalApproveDoesNotCommitOthersWorkInProgressTest`,
    `tests/test_answer_branch_reads.py::AnswerFileCountOnForeignBranchTest`
    — сигнатура `_answer_file_count` поменялась на `(conn, task_id, tdir)`)
    — это адаптация фикстур под уже принятую топологию задачи (T094
    итерация 1: `catalog._new_external_artifact_branch` уже пишет
    `tasks/<id>/` внешнего target ТОЛЬКО в артефактную ветку, не на
    легаси-адрес), не ослабление проверяемого инварианта (сам сценарий
    «approve не коммитит чужой WIP» — `ExternalApproveDoesNotCommit
    OthersWorkInProgressTest` — помечен НЕОСЛАБЛЯЕМЫМ в докстринге
    файла, ADR-0002; assertions ни одного теста не менялись, только
    подготовка данных).

## Покрытие требований
| Требование | Шаг |
|---|---|
| 1 | реестр выше (первый раздел этого PLAN.md) |
| 2 | 1 |
| 3 | 1, 13 |
| 4 | 11 |
| 5 | 2 |
| 6 | 1, 2 |
| 7 | 3 |
| 8 | 3, 9, 14 (self исключён — требование 16; закрыто целиком: и `cmd_new`, и последующие шаги роли) |
| 9 | 4 |
| 10 | 3, 9, 17 — целиком: brief.py/catalog.py/cleanup.py (итерации 1-2) + fsm.py/fsm_advance.py/acceptance.py (итерация 3, `artifact_source.resolve`) |
| 11 | 5 |
| 12 | 6 |
| 13 | 6, 7, 15 (путь `killed` — приёмочными тестами; путь `done` — юнит-тестом, `acceptance_tests/` залочен) |
| 14 | 8 |
| 15 | 10 |
| 16 | 1–12 целиком (self исключён из редиректа везде) |

## Влияние на систему
Self/догфуд (`config.DEFAULT_TARGET`) — единственный сегодня
задекларированный target (`targets.yaml`) — поведенчески НЕ меняется
ни одной строкой: каждая точка редиректа (catalog.cmd_new/cmd_show,
brief.py, cleanup.py, fixation.py, store.set_state/record_fixation,
checkpoint.py, fsm.py/fsm_advance.py/acceptance.py — итерация 3) явно
ветвится по `target == config.DEFAULT_TARGET` (или эквивалентному
`foreign`, вычисленному тем же кодом, что и раньше для self —
`artifact_source.resolve`) и для self исполняет прежний код байт-в-байт
(проверено полным прогоном `tests/` — 1191 passed, регресса на
self-флоу нет). Инварианты 25–28
(docs/invariants.md) остаются в силе — их тестовые модули
(`test_git_fixation`, `test_acceptance_tests_flow`,
`test_gitcmd_branch_reads`, `tasks/T031/.../test_branch_correct_reads.py`,
`tasks/T047/.../test_branch_correct_status_reads.py`) прогнаны без
изменений и зелёные (AC-11). Три теста, симулировавшие внешний target
дореформенной (пре-Б₃) легаси-схемой (`test_git_fixation.py::
ExternalTargetAdvanceIgnoresDirtyCheckTest`/
`ExternalApproveDoesNotCommitOthersWorkInProgressTest`,
`test_answer_branch_reads.py::AnswerFileCountOnForeignBranchTest`) —
обновлены под артефактную ветку (итерация 3, «Шаги»); ни один assertion
инварианта не ослаблен, только подготовка данных теста.

Новый код (`artifact_branch.py`, `artifact_source.py`, `idgen.py`,
`retro_corpus.py`, `snapshot.py`) не ослабляет ни один существующий
гейт/лимит/guard:
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
1. **Лок acceptance_tests внешнего target не сверяется** (не новый
   регресс этой задачи — `fsm_advance.in_dev`, комментарий inline):
   `tests_locked_sha`/`fixed_sha` для внешнего target остаются на
   легаси-схеме фиксации (`fixation._fix_external`, коммит `.artel/
   projects/<target>/`, требование 9 — «не заменяя легаси-строку»);
   `config.ROOT` этот sha не знает независимо от того, какая ветка
   подставлена вторым аргументом `gitcmd.diff_paths` — сверка уходит в
   существующий fail-closed отказ («лок не проверен»), не пропускает
   несверенное. Полное закрытие требует переноса `fixed_sha`/
   `tests_locked_sha` на схему из требования 9 (`external_artifact_sha`)
   — отдельная задача, вне мандата этой (требование 9 сформулировано
   как «не заменяя легаси-строку» этой же итерацией).
2. **AC-15, подтест `test_ac15_retried_by_doctor_after_origin_recovers`
   red в среде без реальных учётных данных claude CLI/keychain**:
   `doctor.cmd_doctor()` агрегирует ВСЕ проверки. По ANSWER-2 (диагноз
   Оператора живым прогоном) `isolation-smoke` падал ENOENT — песочница
   `tasks/T094/acceptance_tests/_sandbox.py::ExternalTargetGitSandbox`
   не несла реальных `skills/*.md` под патченным `config.ROOT`; исправлено
   тем же приёмом, что `tests/test_doctor.py::_DoctorTmpRootTest`
   (`shutil.copytree(REPO_ROOT / "skills", self.root / "skills")` в
   `setUp`) — `isolation-smoke` теперь честно `[ok]` (проверено живым
   прогоном, 27/28 приёмочных). Остаток красноты — `token`/`live-smoke`:
   в песочнице ЭТОЙ разработческой сессии нет keychain-слотов
   `artel-developer`/`artel-reviewer`/`artel-test_author` и `claude` не
   залогинен (`security find-generic-password`, `claude setup-token` —
   операторские действия вне этой сессии, не код задачи). Сама механика
   ретрая снапшота внутри `doctor` работает верно — видно по её
   собственному `[ok] snapshot-pending:...` в выводе прогона;
   `sys.exit(1)` из `cmd_doctor` наступает от НЕСВЯЗАННЫХ с T094
   проверок. Два других подтеста той же AC-15 (`...on_next_command...`,
   `...transition_completes...`) зелёные — они не зависят от полного
   `cmd_doctor`. Ослаблять `check_token`/`live_smoke` для обхода —
   запрещено принципом целостности; на машине с настоящими credentials
   (Оператор/verifier, где Оператор и наблюдал исходные «провалов 1»)
   этот подтест должен идти зелёным — 28/28.
3. **Диф `.github/workflows/ci.yml` не применён** — greplint (AC-4) и
   guard на `artifact/**` начнут реально работать только после того,
   как Оператор применит приложенный диф отдельным MR (тот же
   организационный риск, что и в T046).

## Вопрос Оператору — требование 10 (чтения ядра FSM) — СНЯТ итерацией 3

Раздел ниже — исторический след итерации 2 (REVIEW.md T094 итерация 1,
замечание 2 назвало неправильным сужение объёма требований 8/10 без
явного решения Оператора). Итерация 3 (REVIEW.md T094 итерация 2,
замечание 2) закрыла требование 10 РЕАЛИЗАЦИЕЙ — «Вариант А» ниже, как
и было в нём описано: общий резолвер вынесен в `orchestrator/
artifact_source.py::resolve`, применён к `fsm.py`/`fsm_advance.py`/
`acceptance.py`. Оценка риска «Варианта А» подтвердилась по факту
работы: чтения `tasks/<id>/` ядра FSM действительно не требовали
второго репозитория (все идут через `config.ROOT`, только другое имя
ветки), полный прогон `tests/` (1191, self-путь) остался зелёным без
изменений. Вопрос был предметно закрыт разработчиком реализацией — не
тем же способом, каким закрываются ANSWER-1/ANSWER-2 (батч вопросов
Оператору), потому что реализация — один из двух легитимных исходов,
которые сама формулировка вопроса ниже и предлагала. Детали — «Шаги»,
итерация 3; «Реестр» пункты 2-3 выше.

REVIEW.md T094 итерация 1, замечание 2 (major) назвало неправильным то,
что прошлая редакция этого PLAN.md сузила объём требований 8/10 до
`cmd_new`/brief.py/catalog.py без явного решения Оператора — «не право
разработчика принимать в одностороннем порядке». Требование 8 закрыто
полностью итерацией 2 (шаг 14, `checkpoint._commit_external_step_
artifacts`). Требование 10 закрыто для всего, что уже проверяемо сегодня
(brief.py, catalog.cmd_show, cleanup.py — сделано и покрыто тестами
`extproj`-песочницы), но НЕ для ядра FSM-переходов: `orchestrator/
fsm.py` (`_read_branch_text_or_refuse`, `_answer_file_count`,
`_tests_writing_ac_state`, ветка `spec_gate` в `_cmd_approve`),
`orchestrator/fsm_advance.py` (`spec_writing`, `review`, `verifying`) и
`orchestrator/acceptance.py::run` — все они сегодня читают
`tasks/<id>/`/`acceptance_tests/` c кодовой ветки `t["branch"]`/
`config.TASKS`, не с артефактной ветки пульта, для ЛЮБОГО target.

**Вопрос**: закрывать ли этот остаток требования 10 в текущей итерации
задачи, или подтвердить его перенос в отдельную задачу ДО подключения
первого реального внешнего target?

- **Вариант А (закрыть здесь)** — ВЫБРАН итерацией 3: тот же приём, что
  уже применён к brief.py (`_artifact_source_branch` → общий резолвер
  `(ветка, foreign)`) — вынесен в отдельный модуль `orchestrator/
  artifact_source.py`, чтобы не плодить копию логики в четырёх местах,
  и применён механически к перечисленным функциям. `gitcmd.show`/
  `ls_tree_files`/`on_foreign_branch` в этом пакете всегда работают
  против `config.ROOT` (репозиторий пульта), артефактная ветка внешнего
  target тоже там — редирект не потребовал чтения ВТОРОГО репозитория,
  только выбора другого имени ветки и принудительного `foreign=True`,
  риск оказался ниже, чем предполагала итерация 1. Минус, оставшийся в
  силе: фактическая проверка живым прогоном по-прежнему невозможна (нет
  ни одного внешнего target, доведённого до `tests_writing`/`in_dev`/
  `review`/`verifying`) — доказательство «не сломал self» осталось на
  юнит-тестах и синтетическом `extproj`, без реального сквозного
  прогона; первый реальный внешний target остаётся первой живой
  проверкой этого пути.
- Вариант Б (перенос в отдельную задачу) — НЕ выбран.

**Контекст**: реестр выше (пункт 3, fsm.py-часть), «Шаги» итерация 3;
прецедент решения того же класса — ANSWER-1/ANSWER-2 этой же задачи.

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
