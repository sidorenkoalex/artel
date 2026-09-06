---
task: 01M1RQ12JVHE3PQYDFV1XPSTQ3
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: бриф роли называет артефакты путём от рабочего каталога роли, не от корня пульта

## Подход

Три независимых требования SPEC закрываются точечно, без правки
`orchestrator/brief.py` — расследование показало, что оставшаяся утечка
абсолютного пути (требование 1) живёт не в `brief.py` (там пути уже
относительные, `f"tasks/{task_id}/..."`), а в
`orchestrator/review.py::artifact_text`: `FileNotFoundError` на
отсутствующем PLAN.md/REVIEW.md несёт `str(config.ROOT / rel)` целиком —
для `rel`, начинающегося с `tasks/<id>/`, это буквально
`str(config.TASKS / task_id / ...)`, и эта строка утекает в ревью-пакет,
а с ним и в промпт ревьювера (SPEC «Материалы», уже указывает на этот
файл и строку).

1. **Требование 1 (AC-1)** — `review.py::artifact_text` перестаёт
   передавать `str(FileNotFoundError)` наружу: для этого конкретного
   исключения текст причины теперь не несёт пути вовсе («файл не
   найден»), а «не показан: в ветке — …» по-прежнему называет причину со
   стороны git (`in_branch`), которая уже относительна.

2. **Требование 2 (AC-2)** — `runner.py` получает чистую функцию
   `role_cwd_path(task_id, target)`: та же формула путей, что и внутри
   `role_cwd()` (`workspace.path(task_id)` для self/артели,
   `config.PROJECTS/<target>/workspace` для внешнего target), но без
   побочных эффектов (`workspace.ensure`/материализация
   `tasks/<id>/`) — нужна ДО первой попытки агента, чтобы промпт нёс
   фактический путь буквально. `_cmd_run` считает её один раз перед
   сборкой промпта и передаёт в `role_prompt.mission_brief_package`
   (новый параметр `cwd`), которая дописывает в конец `mission` каждой
   из четырёх ролей строку «рабочий каталог шага — …» дословно по тексту
   требования 2. `role_cwd()` рефакторится на использование той же
   `role_cwd_path()` внутри (снятие дублирования формулы, поведение не
   меняется).

3. **Требования 3/4 (AC-3..AC-7)** — `runner.run_agent_once` получает
   проверку `_missing_required_artifact(role, cwd, task_id)`: смотрит на
   диск РЕАЛЬНОГО рабочего каталога роли (`cwd`, уже вычисленный этой же
   функцией через `role_cwd()`), не на артефактную ветку. Вызывается
   сразу после ветки `rc != 0` (то есть только на rc=0), ДО
   `commit_step_artifacts`/журнала «agent run finished» — иначе
   `checkpoint.commit_step_artifacts` уже стёр бы `tasks/<id>/` с диска
   (`shutil.rmtree` после переноса в артефактную ветку) и проверка
   «после» не имела бы смысла (см. докстринг AC-5 приёмочной планки).
   Артефакт отсутствует — тот же класс отказа, что и `rc != 0`:
   WIP-чекпоинт (`checkpoint.commit_abnormal_checkpoint`), запись
   «agent run FAILED» с текстом «шаг завершён без артефакта <имя>» и
   возврат `("failed", reason, None)` — дальше существующий цикл
   ретраев/эскалации `cmd_run` отрабатывает без изменений (после
   исчерпания `AGENT_ATTEMPTS` попыток задача уходит в `escalated`, как
   и при настоящем провале агента). Штатный путь (артефакт на месте)
   не меняется вовсе.

Требуемый артефакт по роли: `reviewer` — файл `REVIEW.md`; `developer` —
файл `PLAN.md`; `analyst` — файл `SPEC.md` ИЛИ `QUESTIONS.md` (ровно один
из двух — эскалация или ТЗ понятно, оба случая штатны); `test_author` —
непустой каталог `acceptance_tests/` (проверка по каталогу, не по имени
конкретного файла в нём).

## Шаги

1. `orchestrator/review.py::artifact_text` — убрать абсолютный путь из
   ветки `FileNotFoundError` (AC-1).
2. `orchestrator/runner.py` — добавить `role_cwd_path()`, перевести
   `role_cwd()` на неё же, вычислить `cwd_for_prompt` в `_cmd_run` и
   прокинуть в `role_prompt.mission_brief_package`; в
   `orchestrator/role_prompt.py` — новый параметр `cwd`, строка рабочего
   каталога в конец `mission` каждой из четырёх ролей (AC-2).
3. `orchestrator/runner.py::run_agent_once` — `_missing_required_artifact`
   плюс её вызов между веткой `rc != 0` и веткой `pump.error` (AC-3..AC-7).
4. Регрессия существующего набора (AC-8): `tests/test_review_package.py`
   и `tests/test_agent_prompt.py` гоняли шаг developer/reviewer, не
   сажая на диск обязательный артефакт роли — раньше это было неважно
   (rc=0 всегда означал успех), с шагом 3 без него шаг честно ретраит и
   эскалирует (с реальным `time.sleep`, эти файлы не мокают `runner.
   time.sleep`). `run_agent()` в обоих файлах кладёт на диск маркер
   обязательного артефакта роли ПЕРЕД вызовом `cmd_run` — имитация «роль
   уже написала», тем же приёмом, что уже применяет `_sandbox.py`
   приёмочной планки. Один тест (`test_worktree_fallback_is_journaled`)
   ослаблен с точного порядка перечисления в `from_worktree` до проверки
   двух подстрок по отдельности — маркер `tasks/<id>/REVIEW.md` на диске
   теперь тоже честно попадает в этот список, порядок не был предметом
   проверки.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (AC-1) | 1 |
| 2 (AC-2) | 2 |
| 3 (AC-3..AC-7) | 3 |
| 4 (AC-8, регрессия) | 4 |

## Влияние на систему

Зона правки — точно три файла из `zones:` (`brief.py` не тронут —
утечка жила не там) плюс `tests/`. Новая проверка в `run_agent_once`
меняет исход ТОЛЬКО для сценария «rc=0, но обязательный файл роли
отсутствует на диске» — раньше это единственный путь давал ложный
`agent run finished`; штатный путь (артефакт на месте, доминирующий
случай в проде) байт-в-байт прежний (AC-7, отдельный тест планки).
Ретраи/бэкофф/эскалация — существующий механизм `cmd_run`, не новый:
`_missing_required_artifact` лишь классифицирует попытку как `failed` по
тому же контракту, что и `rc != 0`. Откат — правки локальны и обратимы
(`git revert`), ни один существующий тест/гейт/лимит не ослаблен и не
удалён. Полный набор `tests/` не прогонялся в шаге (правило времени
исполнения шага) — прогнаны точечно все файлы, реально пересекающиеся с
правкой (`test_brief`, `test_agent_prompt`, `test_review_package`,
`test_review_freshness`, `test_acceptance_tests_flow`,
`test_advance_refusal_history`, `test_agent_failure`, `test_agent_log`,
`test_analyst_role`, `test_auto_cycle`, `test_canary`,
`test_checkpoint_external_step_artifacts`, `test_diff_not_collected_alerts`,
`test_doctor`, `test_failure_classification`, `test_git_fixation`,
`test_invariants`, `test_lease_pgid_store`, `test_multitarget`,
`test_multitarget_invariants`, `test_step_autocommit`, `test_step_cost`,
`test_step_refixation`, `test_timeout_checkpoint`) — все зелёные.

### Правки итерации 2 (REVIEW.md итерация 1, R1-F1/R1-F2)

R1-F2 — `docs/codebase-map.md` не была регенерирована после добавления
`role_cwd_path` в `orchestrator/runner.py`: `python3
scripts/codebase_map.py` прогнан, `role_cwd_path` теперь в перечне
публичных функций модуля, `built_at_sha` обновлён.

R1-F1 — новая проверка `_missing_required_artifact` (шаг 3) ломала 26
тестов в 7 файлах существующего набора: они гоняют агентский шаг
developer/reviewer через `FakeProc` с rc=0, не сажая на диск рабочего
каталога роли обязательный артефакт — раньше это было неважно (rc=0
всегда означал успех), теперь шаг честно ретраит и эскалирует. Сидирован
маркер обязательного артефакта во всех 7 файлах, местом и приёмом,
подходящим для песочницы каждого конкретно (расхождение между
`config.TASKS`/`config.WORKTREES`/реальным git worktree в разных
классах — не единая формула):

- `tests/test_agent_failure.py::CmdRunFailureTest` — `_STEP_ARTIFACT`
  по ТЕКУЩЕМУ состоянию задачи внутри `run_agent()` (класс переключает
  state между тестами), маркер в `config.WORKTREES/<id>/tasks/<id>/`.
- `tests/test_agent_log.py::CmdRunLoggingTest`,
  `tests/test_doctor.py::PreflightBlocksMissingTokenTest`,
  `tests/test_step_cost.py::CmdRunCostTest` — класс держит один и тот
  же state='in_dev' на всём протяжении, PLAN.md сидируется один раз в
  `setUp` по тому же адресу.
- `tests/test_multitarget.py::RoleEnvTest` — этот класс подменяет
  `workspace.ensure` на `lambda: (self.root, None)`, рабочий каталог
  роли — `config.TASKS/<id>/`, не `config.WORKTREES/…`.
- `tests/test_invariants.py::FsmTest` — новый общий хелпер
  `seed_worktree_plan()`: маркер в `config.WORKTREES/<id>/tasks/<id>/`,
  ОТДЕЛЬНО от `self.tdir` (`config.TASKS/<id>/`, откуда читает
  FSM/бриф через `disk_backed_show`) — вызван в двух местах
  (`ExhaustedBudgetIsNotBypassableTest`/`ParallelTaskLimitIsNotBypassableTest`),
  где реально не хватало артефакта.
- `tests/test_git_fixation.py` (`ExternalIntegrityIncidentBlocksRunTest`,
  `RealPultGitTest`) — PLAN.md добавлен в СОДЕРЖИМОЕ коммита
  артефактной ветки (`artifact_branch.commit_files`/
  `_seed_artifact_branch`), а не только на диск репо фиксации: у этих
  классов `runner.role_cwd` — настоящий git, `materialize_task_dir`
  стирает с диска на каждом вызове любой файл, которого нет в ветке —
  сидирование мимо ветки не пережило бы материализацию.

Побочная находка при починке `test_agent_log.py`: тест
`test_environment_fingerprint_is_journaled_on_start_and_finish` патчит
`agent_log.subprocess.run` — тот же объект модуля `subprocess`, что и у
`gitcmd.check_ignore`, а не только у сборщика fingerprint. Раньше это
было незаметно (автокоммиту шага нечего было коммитить, `check_ignore`
не вызывался); с сидированным PLAN.md автокоммит стал реально находить
файл и звать `check_ignore`, попадая под чужой мок теста (текстовый
`CompletedProcess` вместо байтового) и падая `TypeError`. Не дефект
продакшен-кода — сузил `fake_run` этого теста до точного совпадения
`["git", "--version"]`/`["claude", "--version"]`, всё остальное
делегируется в `self.git_spy` (тот же `SpyRun`, что уже ставит
`TmpRootTest.setUp`).

Реестр замечаний REVIEW.md: R1-F1 и R1-F2 размечены `fixed`.

Проверено исполнением: `python3 -m pytest` по каждому из 19
файлов из первой итерации — все зелёные, включая полный перечень из 26
тестов замечания R1-F1 (`test_agent_failure`, `test_agent_log`,
`test_doctor`, `test_git_fixation`, `test_invariants`,
`test_multitarget`, `test_step_cost`); `tasks/01M1RQ12JVHE3PQYDFV1XPSTQ3/
acceptance_tests/` — 7/7 зелёные; `python3 scripts/guard.py
tasks/01M1RQ12JVHE3PQYDFV1XPSTQ3/{SPEC,PLAN}.md` — «GUARD: ок (2
файлов)»; `python3 scripts/codebase_map.py` — карта перегенерирована.

## Риски

- Список обязательных артефактов по роли зашит в `runner.py`
  (`_missing_required_artifact`), а не читается из `roles.yaml` — при
  появлении новой агентской роли с обязательным выходом её нужно будет
  добавить сюда руками; для четырёх существующих ролей (не входит в эту
  задачу расширение) это не проблема.
- `role_cwd_path()` — чистая формула без побочных эффектов; если формула
  внутри `role_cwd()` когда-нибудь разойдётся с ней (кто-то поправит одну
  функцию и забудет другую), строка «рабочий каталог шага» в промпте
  может разойтись с реальным cwd. Смягчено рефакторингом `role_cwd()` на
  переиспользование `role_cwd_path()` — общая точка истины, не дубль.

## Предложения системе

- Класс «тест гоняет агентский шаг через `FakeProc`, не сажая на диск
  обязательный артефакт роли» — до этой задачи было неважно (rc=0 =
  успех), теперь может молча превращать лёгкий unit-тест в ретраи с
  реальным `time.sleep` (минуты вместо миллисекунд), если файл не мокает
  `runner.time.sleep`. Разошлось с практикой в `tests/test_agent_prompt.py`
  и `tests/test_review_package.py` — почини выявляется только прогоном
  полного времени, не при чтении диффа.

## Расширение зон

Пути: orchestrator/review.py

Обоснование: требование 1 SPEC (AC-1) — `review.py::artifact_text` при
`FileNotFoundError` возвращал текст исключения с абсолютным путём корня
пульта, и этот путь утекал в пакет ревью, а из него в промпт ревьювера.
Без правки в `review.py` критерий AC-1 недостижим; аналитик файл в `zones`
не включил. Мандат Оператора — ANSWER-2.md.
