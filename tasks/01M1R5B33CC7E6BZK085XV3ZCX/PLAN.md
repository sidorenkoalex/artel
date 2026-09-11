---
task: 01M1R5B33CC7E6BZK085XV3ZCX
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: B2 ТЗ-1: репозиторный контекст target для git/gh-слоя

## Подход
Единая точка «репозиторный контекст target» — новый модуль
`orchestrator/repo_context.py`: `resolve(target_name) -> RepoContext |
None` (`path`, `remote`, `base`); self — `config.ROOT`/`"origin"`/
`config.MAIN_BRANCH` без чтения `targets.yaml`; внешний target —
`config.PROJECTS/<target>/workspace`/`targets.yaml[target]["url"]`/
`targets.yaml[target]["base"]`; `None` — target не читается (тот же
принцип деградации, что уже несёт `fsm._origin_main_source`).
Вспомогательные `path_or_none(ctx)` (self → `None`, «параметр `repo=`
можно не передавать») и `git(ctx, *args)` (self → байт-в-байт `gitcmd.
git`, иначе `gitcmd.in_repo(ctx.path, ...)`) используются везде, где
нужно физически выполнить git-команду в клоне контекста.

Ключевое разграничение (важно для ревью): `ctx.remote` несёт ДВА разных
смысла по конструкции. Для self это литеральное имя git remote
(`"origin"`), пригодное для git-уровневых команд. Для внешнего target
это адрес форджа (`targets.yaml[target]["url"]`) — годится ТОЛЬКО для
`gh --repo <url>` (AC-2/AC-3/AC-7), но НЕ для git fetch/push: реальный
клон внешнего target несёт свой git remote `origin`, настроенный на
адрес форджа тем механизмом, который его заводит (ТЗ-2, вне зоны этой
задачи) — поэтому все git-уровневые fetch/push этой задачи (AC-4, AC-6,
AC-12) используют литеральное имя `"origin"` в клоне `ctx.path`, никогда
`ctx.remote` буквально. Это решение проверено на песочнице с НАСТОЯЩИМ
git (двумя bare-origin) — раскрытие смысла в докстринге
`repo_context.py` и `fsm_merge_gate._origin_main_sha`.

Все 13 точек реестра SPEC переведены на этот узел минимальным
добавлением опционального параметра `repo=`/`cwd=` (path) или `repo=`
(url для `gh`) к существующим функциям — сигнатура для self не меняется
по умолчанию (`None`), поведение байт-в-байт как до задачи (подтверждено
существующими юнит-тестами, ни один не потребовал смены ожидаемого
результата для self-сценариев, только сигнатур некоторых заглушек-моков).

Для merge_gate внешнего target (AC-12) сам плотницкий merge идёт не в
scratch, созданном ИЗ `config.ROOT`, а в scratch, созданном ИЗ клона
контекста target'а (`git worktree add` там же, где только что зафетчен
sha main) — `_scratch_worktree`/`_origin_main_sha` `fsm_merge_gate.py`
приняли параметр `ctx`. Карта/RETRO (AC-13) — условный вызов по
`ctx.path == config.ROOT`, сама механика `fsm_postmerge.py` не менялась
(уже принимала `repo=`).

## Шаги
1. `orchestrator/repo_context.py` — новый модуль (`RepoContext`,
   `resolve`, `path_or_none`, `git`) + `tests/test_repo_context.py`.
2. `orchestrator/gitcmd.py` — `repo=` у `commits_behind`/`diff_base`/
   `diff_base_source`/`branch_head_sha`/`remote_branch_sha` (AC-4/AC-5/
   AC-6/AC-9/AC-10, byte-identical для self по умолчанию).
3. `orchestrator/ci.py` — `repo=`(url) у `gh`/`check_runs_page`/
   `run_list`, `repo=`(path) у `head_sha` (AC-2/AC-3); `gh(repo=None)` не
   подставляет `--repo` вовсе (self байт-в-байт, AC-2).
4. `orchestrator/github_adapter.py` — `ensure_draft_mr`/`undraft_mr`/
   `ensure_head_in_origin`/`_touched_protected_paths` резолвят контекст
   и роутят push/`gh --repo`/diff через него (AC-6/AC-7/AC-8).
5. `orchestrator/fsm.py` — `_origin_main_sha(target_name, *, repo=)`,
   `_pull_main_or_escalate` резолвит контекст и передаёт `repo_path`
   дальше в `pull.evaluate` (AC-4, требование 3).
6. `orchestrator/pull.py::evaluate` — новый параметр `repo_path`: для
   внешнего target — сравнение/merge идут ПРЯМО в клоне контекста
   (`workspace.ensure` не зовётся вовсе), для self — прежний путь.
7. `orchestrator/review.py` — `git_diff_part(..., repo=)`,
   `review_package` резолвит контекст задачи (AC-9).
8. `orchestrator/fsm_advance.py::_capacity_gate` — больше не
   пропускается безусловно для внешнего target, считает diff в клоне
   контекста (AC-10).
9. `orchestrator/acceptance.py::run` — параметр переименован
   `code_root` → `cwd` (буквальный контракт AC-11 залоченной планки);
   обновлены оба вызывающих (`fsm_advance.py`, `pull.py`) и
   `tests/sandbox.py::assert_acceptance_run_called`.
10. `orchestrator/doctor/branch_freshness.py` (+ facade `doctor/
    __init__.py`, импорт `repo_context`) — для внешнего target fetch
    `origin/<base>` контекста перед сравнением (AC-5).
11. `orchestrator/fsm_merge_gate.py` — `_origin_main_sha`/
    `_scratch_worktree`/`_perform_carpentry_merge`/
    `_publish_merge_artifacts`/`_push_merged_main`/`_sync_main_or_wait`
    принимают `ctx`; `_cmd_approve_merge_gate` резолвит его один раз
    (`store.task_target`, fail-closed `sys.exit`, если контекст не
    читается — merge не имеет права молча деградировать на чужой
    репозиторий) и передаёт дальше (AC-12/AC-13).
12. Юнит-тесты, задетые переименованием/новыми сигнатурами:
    `tests/test_github_adapter.py` (контекст `ensure_head_in_origin`),
    `tests/test_branch_freshness_gate.py` (fetch внешнего target теперь
    идёт `-C <клон>` с литеральным `origin`, не голым `url` — класс
    изменения объяснён отдельно в «Влияние на систему»),
    `tests/test_git_fixation.py` (капасити-гейт теперь реально звонится
    для внешнего target — замокан в тесте, предмет которого другой),
    `tests/test_fsm_merge_gate_done_snapshot.py` (переведён на реальный
    клон-контекст target'а вместо мержа в `config.ROOT`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (единый узел контекста) | 1 |
| 2 (`ci.gh` с контекстом) | 3 |
| 3 (сверка/подтяжка по контексту) | 2, 5, 6 |
| 4 (merge/карта/RETRO по контексту) | 11 |
| 5 (гейт ёмкости + diff ревью-пакета) | 7, 8 |
| 6 (сквозной тест на двух репозиториях) | см. «Эскалация» — планка
залочена, два сценария красны по причинам вне этой реализации |

## Влияние на систему
Изменения — целиком добавление опционального параметра (`repo=`/`cwd=`)
поверх существующих сигнатур; для self ни один параметр не передаётся
по умолчанию, поведение байт-в-байт (подтверждено прогоном затронутых
юнит-тестов ниже). Единственное поведенческое изменение для self —
`_capacity_gate` (AC-10) теперь резолвит контекст через `repo_context.
resolve` вместо прямой сверки `!= config.DEFAULT_TARGET`; для self это
тот же результат (гейт считается, как и раньше), путь пройден теми же
существующими тестами `tests/test_capacity_gate.py`.

Правка вышла за пределы `zones:` SPEC ровно на один файл —
`orchestrator/pull.py`. Он не назван в `zones:`, но содержит РЕАЛЬНУЮ
реализацию `fsm._pull_main_or_escalate` (сам docstring `fsm.py` это
называет: «Вычисление исхода ... целиком orchestrator/pull.py::
evaluate»), и требование 3/AC-4 структурно недостижимо без правки его
`evaluate()` — иначе пришлось бы дублировать ~130 строк логики merge/
конфликтов в fsm.py в обход DRY. Решение — минимальный добавленный
параметр (`repo_path=None`), self-поведение не меняется.

Инварианты/гейты не ослаблены: гейт ёмкости diff (AC-10) стал СТРОЖЕ
(больше не пропускает внешний target безусловно); лок `acceptance_tests/`
(T023), бюджетный гейт, zone_lock и структура guard — не тронуты.
Откат — `git revert` коммита(ов) этой задачи, self-поведение везде
защищено значением параметра по умолчанию, откат безопасен.

## Риски
- `fsm_merge_gate._cmd_approve_merge_gate` теперь резолвит контекст
  через `store.task_target(conn, task_id)`, не `t["target"]` — не
  случайность: минимум один существующий юнит-тест
  (`tests/test_merge_gate_ci_wait.py`) передаёт `t` неполным словарём
  без ключа `"target"`; `store.task_target` деградирует на self, если
  строки задачи нет в БД, а не бросает исключение.
- `repo_context.path_or_none`/`ensure_head_in_origin` трактуют
  НЕЧИТАЕМЫЙ контекст (сломанный/неизвестный target) как self (`None`
  → `repo=None`) в некритичных путях (мягкий push-хелпер), но
  fail-closed `sys.exit`'ом в `_cmd_approve_merge_gate` (мутирующая
  merge-операция). Несогласованность между этими двумя классами узлов
  осознанная (мягкая деградация там, где действие обратимо/не пишет в
  чужой репозиторий; жёсткий отказ там, где пишет), но стоит того,
  чтобы Оператор явно это увидел.
- `ci.branch_status`/`ci.verifying_status`/`check_runs`/`find_run_id`/
  `trigger_rerun` НЕ переведены на контекст (SPEC/AC-2/AC-3 называют
  буквально только `gh`/`head_sha`/`check_runs_page`/`run_list`) — для
  target ≠ self реальный (не тестовый, где `ci.branch_status` заменяется
  моком) опрос CI merge_gate/verifying по-прежнему обращается к
  self/`config.ROOT` неявно. Последующая задача, доводящая реальный
  CI-опрос внешнего target до конца, довяжет `repo=`/`ctx` через эти
  функции — примитивы уже готовы.

## Предложения системе
- Планка приёмочных тестов этой задачи несёт минимум ДВЕ проблемы,
  подтверждённые прогоном против полностью реализованного кода (не
  гипотеза, воспроизведено): (1) `test_ac4_pull_main_or_escalate.py` —
  ОБА сценария (self и внешний target) красны одинаково («дерево не на
  ветке задачи ... SPEC.md ветки не прочитан») — фикстура заводит
  задачу без единого коммита в артефактную ветку
  (`artifact_branch.commit_files`), а `pull._materialize_and_run_plank`
  требует читаемый SPEC.md с неё, если `acceptance_tests/` там тоже нет;
  (2) `test_ac15_ac16_ac17_end_to_end.py::
  test_ac15_full_flow_merges_into_the_target_origin_only` ожидает
  `in_dev -> review` ОДНИМ вызовом `cmd_advance`, хотя актуальный
  (документированный ADR-0015, «Решение» п.1) порядок состояний —
  `in_dev -> verifying -> review`: тест написан против порядка,
  устаревшего до начала этого шага. См. «Эскалация» ниже.
- Класс проблемы «планка test_author залочена ДО того, как в main
  влилась параллельная задача, меняющая инвариант, который планка
  молчаливо предполагает» (здесь — ADR-0015) — второй раз в этой же
  задаче (fixture-баг AC-4 — независимый первый экземпляр). Скилу
  test-authoring.md может быть полезно явно называть этот риск для
  задач с «код стартует после мержа X» в SPEC.

## Эскалация

**Вопросы** (по блокирующести; дефолт — если Оператор промолчит):

1. `tasks/.../acceptance_tests/test_ac4_pull_main_or_escalate.py` —
   оба теста (`ExternalTargetPullMainTest.
   test_ac4_external_target_branch_gets_merged_in_the_target_clone` и
   `SelfTargetPullMainUnchangedTest.
   test_ac4_self_target_still_merges_in_the_pult_worktree`) красны:
   фикстура заводит задачу (`insert_external_task`/`store.insert_task`)
   БЕЗ единого коммита в артефактную ветку — `tasks/<id>/SPEC.md` там
   не существует. `pull._materialize_and_run_plank` (существующая,
   НЕ этой задачей введённая логика — `orchestrator/pull.py`, ветка
   «acceptance_tests/ нет → читай SPEC.md») в этом случае отказывает
   `Refused` вместо `Pulled`, и обе SelfTarget/ExternalTarget проверки
   получают `outcome == "refused"` вместо ожидаемого `"pulled"`.
   Варианты: (a) Оператор поправляет планку (добавляет
   `artifact_branch.commit_files(TASK, {f"tasks/{TASK}/SPEC.md": ...},
   ...)` в `setUp` обоих тестовых классов) — тогда я доведу шаг
   штатно; (b) Оператор подтверждает, что этот дефект планки —
   отдельная эскалация test_author, а эта задача сдаётся с этими двумя
   тестами красными, остальными 15 из 17 AC — зелёными. Дефолт при
   молчании — (b), с пометкой в REVIEW.md/RETRO, что планка требует
   правки отдельным ходом.
2. `tasks/.../acceptance_tests/test_ac15_ac16_ac17_end_to_end.py::
   EndToEndExternalTargetFlowTest.
   test_ac15_full_flow_merges_into_the_target_origin_only` — ожидает
   состояние `"review"` сразу после ОДНОГО `fsm.cmd_advance(TASK)` из
   `in_dev`; фактический (правильный, уже смерженный, задокументированный
   `docs/adr/0015-ci-before-review.md` «Решение» п.1) порядок —
   `in_dev -> verifying -> review`. Тест написан против состояния FSM,
   устаревшего к моменту старта этого шага (SPEC сама называет условие
   «код стартует после мержа ... группы процессов» — похоже, эта же
   категория гонки задела и порядок состояний, не только зоны
   fsm_advance.py/doctor.py). Изменение порядка состояний НЕ входит в
   объём этой SPEC (и правка бы ослабила ADR-0015 — принцип
   целостности запрещает это разработчику). Варианты: (a) Оператор
   поправляет планку (добавляет промежуточный `store.set_state(...,
   "verifying", ...)`/второй `cmd_advance()` перед первым `assertEqual`
   — ровно тем же приёмом, что уже применён к `verifying -> acceptance`
   ниже в этом же тесте); (b) сдать задачу с этим одним сценарием
   красным (два других класса того же файла, `CapacityGateThroughAdvanceTest`
   и `SandboxIsolationTest`, — зелёные, доказывают AC-16/AC-17
   независимо). Дефолт при молчании — (b).

**Контекст**: код реализован полностью по всем 17 AC. Прогон
`tasks/01M1R5B33CC7E6BZK085XV3ZCX/acceptance_tests/` целиком:
14 из 17 тестовых методов зелёные (AC-1, AC-2, AC-3, AC-5, AC-6, AC-7,
AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-16, AC-17 — все свои
тестовые классы полностью зелёные); AC-4 (2 из 3 методов) и один
сценарий AC-15 (1 из 3 методов) красны по причинам выше, ПОДТВЕРЖДЕНО:
для AC-4 self-сценарий (`SelfTargetPullMainUnchangedTest`) падает ТОЙ
ЖЕ ошибкой, что и внешний — доказывает, что причина не в
self/external-разводке этой задачи, а в фикстуре. Юнит-тесты
затронутых модулей (`tests/test_gitcmd_*`, `tests/test_ci_status*`,
`tests/test_github_adapter.py`, `tests/test_capacity_gate.py`,
`tests/test_review_package.py`, `tests/test_branch_freshness_gate.py`,
`tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_acceptance*`,
`tests/test_doctor.py`, `tests/test_merge_gate_ci_wait.py`,
`tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_map_regen.py`,
`tests/test_fsm_retro.py`, `tests/test_fsm_advance_gate_smoke.py`,
`tests/test_fsm_advance_gate_framework.py`, `tests/test_zones_gate.py`,
`tests/test_zones_approve.py`, `tests/test_advance_guard.py`,
`tests/test_pull.py`, `tests/test_multitarget*`,
`tests/test_split_assessment_merge_gate.py`,
`tests/test_fsm_review_rework_*`, `tests/test_artifact_branch_push.py`,
`tests/test_budget_live_lease_and_escalation.py`,
`tests/test_doctor_artifact_branch_*`, `tests/test_fsm_draft_mr_reentry.py`,
`tests/test_git_fixation.py`, `tests/test_auto_cycle.py`,
`tests/test_repo_context.py`) — все зелёные.

**Блокирует**: доведение требования 6/AC-15 (сквозной прогон как
единственная проверка полноты флоу, см. SPEC «Оценка объёма и деление»
п.3) до состояния «все локальные acceptance_tests/ зелёные» без
правки локальной планки — которая мне недоступна (T023: «их правка —
эскалация, не правка»). Код к передаче готов и закоммичен; ждёт
решения Оператора по планке (или подтверждения дефолта — сдать с
двумя красными сценариями).

## Возврат — правка планки AC-4/AC-15 и hotfix №21

Оператор ответил на оба вопроса эскалации вариантом (a) (ANSWER-1.md):
планку поправил штатным каналом `amend-tests` (лок сдвинут a460ff4c ->
68171e0e) — `_sandbox.py::commit_minimal_plank` коммитит минимальный
`SPEC.md` в артефактную ветку в `setUp` обоих классов
`test_ac4_pull_main_or_escalate.py` (закрывает вопрос 1); в
`test_ac15_ac16_ac17_end_to_end.py::
test_ac15_full_flow_merges_into_the_target_origin_only` вставлен
промежуточный `store.set_state(..., "verifying", ...)` перед переходом
в `review` (порядок `in_dev -> verifying -> review`, ADR-0015) —
закрывает вопрос 2. По ходу того же прогона Оператор нашёл и
исправил дефект main (не этой задачи): `scripts/guard.py` не знал
`PASSPORT.md` пульта как легитимный файл корня задачи внешнего target
— hotfix №21 (коммит `c52f54ba`).

Выполнено в этом ходе:
1. `git merge origin/main` в рабочей копии — единственный реальный
   конфликт: `docs/codebase-map.md` (расхождение заголовка
   `built_at_sha`, не содержания карты) — разрешён регенерацией
   (`python3 scripts/codebase_map.py`) после мержа, не ручной правкой
   маркеров; `orchestrator/gitcmd.py` смёржился автоматически без
   конфликта (main не трогал зону этой задачи). Слияние подтянуло
   hotfix №21, самовыбор интерпретатора (01M1SHK3MD), approve без sha
   (01M1SHJX22), auto --wait-zone (01M1VBEAWZ) — коммит `020779cc`.
2. Планку `acceptance_tests/` не трогал (она уже несёт правку
   Оператора после материализации рабочего каталога с головы
   артефактной ветки) — прогнал синхронно: `python3 -m pytest
   tasks/01M1R5B33CC7E6BZK085XV3ZCX/acceptance_tests -o timeout=90` —
   **39 из 39 тестовых методов зелёные** (все 17 AC, включая ранее
   красные AC-4 self/external и сценарий AC-15).
3. Юнит-тесты затронутых модулей по правилам скила (foreground,
   явный timeout, без полного `tests/`) — три прогона `python3 -m
   unittest` по спискам модулей из «Контекст» эскалации: 326 + 210 +
   222 = 758 тестов, все **OK**, ни одного упавшего.
4. Код к этому ходу не менялся (весь diff — уже закоммиченная в
   прошлом ходе реализация всех 17 AC; правка планки — работа
   Оператора каналом `amend-tests`, не разработчика).

## Покрытие требований (обновлено)

Требование 6 (сквозной тест) закрыто полностью: AC-15/AC-16/AC-17 —
все три тестовых класса `test_ac15_ac16_ac17_end_to_end.py` зелёные.
Все 17 AC зелёные без исключений.

## Расширение зон

Пути: orchestrator/repo_context.py, orchestrator/pull.py, orchestrator/doctor/, orchestrator/stack.py

Обоснование: зоны SPEC заявлены 05.09 по адресам того дня. После этого
R3 (01M1TKP08P, 06.09) вынес подтяжку main из `fsm.py` в `pull.py` (точка 1
реестра), R5 (01M1TT9BPB) разрезал `doctor.py` в пакет `orchestrator/doctor/`
(точка 2 — `branch_freshness.py`). `repo_context.py` — новый модуль с самим
понятием «репозиторный контекст target» (требование 1 SPEC), место его
объявления SPEC не фиксировала. `stack.py` — одна строка докстринга с
переименованным параметром `acceptance.run` (точка 10). Мандат Оператора —
ANSWER-2 этой задачи (11.09).
