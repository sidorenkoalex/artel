---
task: 01M5RWNJEZT6YA2VP7JK6F3RXS
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Скорость пульта, git 2: одна отправка ссылки документов на команду пульта

# Скорость пульта, git 2: одна отправка ссылки документов на команду пульта

## Решения Оператора

Решение Оператора 25.10.2026 (дословно): «по git 2 ок по рекомендациям». Рекомендации, принятые этим решением:
1. ADR-0021 п.3 поправлен Оператором (`docs/adr/0021-project-area-and-immutable-pult.md`, пункт о записи ссылки документов): внутри команды пульта, меняющей задачу, ссылка отправляется один раз при выходе из команды и раньше — в точках требования 3; вне команды — сразу после коммита.
2. Шаг цикла `auto` (`fsm.cmd_advance`, `runner.cmd_run`) считается отдельной командой: досылка — в конце каждого шага (требование 1г).
3. Досылка также перед ожиданием CI и перед полным прогоном набора тестов на гейте мержа (требование 3е).
4. Мандат на правку `tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package` по перечню ниже.

## Факты

Решение Оператора 24.10.2026 (дословно): «Заводи рекомендованный набор: быстрая задача по full_suite_lock и doctor_duration сейчас, задачи по git 1, 5, 2, 3, 4 — по очереди между волнами; шаблон песочниц и подделку pytest — отложить.»

Повод — исследование вызовов git в командах пульта 24.10 (шпион процессов на 9c0e8b8c, то есть подмена запуска процессов, которая считает каждый вызов git). Каждый коммит документов (`write_commit` → `update-ref` → `_send`) делает около 11 вызовов git и свою отправку в `origin`. В тесте `merge_outcome_gate::Ac5ProofMismatchTest` 33 коммита документов, из них 15 — строки паспорта из `store.set_state`, и каждый отправляется отдельно. Оценка исследования: в этом тесте примерно на 12 `push` и на 24 `remote` меньше; в работе — примерно на 3 отправки меньше на один `approve` и на 0,5 на переход.

Сверено с origin/main f58576de. На пине 09ded609 и на origin/main различаются `orchestrator/artifact_branch.py` и `tests/test_review_package.py`: для них ссылки даны по именам функций и тестов. Остальные названные ниже файлы совпадают, и номера строк в них верны для пина.

Как устроено сейчас:

- `orchestrator/artifact_branch.py`:
  - `_write` — общий узел записи для `commit_files` и `commit_change`. После удачного `update-ref` со сверкой прежнего значения он сразу зовёт `_send(task_id, repo)`. `repo` берётся из `repo_for_target(target)`, если `target` задан (`cmd_new` пишет первый коммит до строки задачи в БД), иначе из `task_repo(task_id)`.
  - `_send`: `_origin_configured` (`git remote get-url origin`) → `_attempt_push(…, origin_checked=True)` (`git push -q origin refs/artifacts/<id>:refs/artifacts/<id>`; при ответе сервера 5xx — повтор до `PUSH_SERVER_RETRY_ATTEMPTS` раз с паузой `PUSH_SERVER_RETRY_PAUSE_SEC`).
  - Правила журнала в `_send`: запись `_journal_push_outcome` делается при отказе; при успехе — только после повтора в этом же вызове (`attempts > 1`) или при досылке после записанного раньше отказа (`_last_send_failed`). Без `origin` — `False` без записи.
  - `push(task_id)` — отправка с журналом любого исхода. Зовёт только `doctor --fix` (`orchestrator/doctor/artifact_branches.py:165`, `_fix_unsent_closed_ref` `:149`).
  - `origin_sync_refusal(task_id)`: сначала `gitcmd.remote_ref_state`; если локальная ссылка есть и расходится с `origin` — `_send`, затем повторная сверка. Зовут гейт мержа (`orchestrator/fsm_merge_gate.py:1349`) и `kill` (`orchestrator/cleanup.py:681`).
  - `fetch_from_origin` (`orchestrator/docs_fetch.py:61`) и `fetch_all_from_origin` (`orchestrator/docs_fetch.py:135`, `orchestrator/workspace.py:140`) сдвигают локальную ссылку только вперёд. Если локальная ссылка впереди `origin`, исход — `FETCH_DIVERGED`.
  - `append_passport_line` ← `store._append_passport_line` (`orchestrator/store.py:975`, `:991`) ← `store.set_state` (`:905`): одна строка паспорта = один коммит = одна отправка.
- Кто пишет документы через `_write`:
  - `catalog.py:816` (`cmd_new`);
  - `answer.py:331`, `:555`;
  - `checkpoint.py:1424` (`_commit_step_artifacts_to_branch` ← `commit_step_artifacts` ← `runner.py:1950`);
  - `snapshot.py:138` (`commit_closing` — коммит закрытия RETRO);
  - `amend.py:494`, `:1333`;
  - `orchestrator/advance_gates/tests_writing.py:556`;
  - `orchestrator/doctor/ignored_artifacts.py:61`;
  - строки паспорта из `store.set_state`.
  - Свои прямые отправки, без `_send`, есть у `snapshot.py:294` (исторические снимки) и у `orchestrator/doctor/artifact_branches.py:137`. Эта задача их не трогает.
- Общая обвязка команд задачи — `lease.run_locked` (`orchestrator/lease.py:334`; тело `body(sid)` исполняется в `try`, `release` — в `finally`, `:371`–`375`). Через неё напрямую или через `lease.run_task_command` (`:378`) идут:
  - `fsm.cmd_advance` (`fsm.py:741`), `cmd_approve` (`:951`), `cmd_reject` (`:1685`), `cmd_spec_audit` (`:1771`);
  - `runner.cmd_run` (`runner.py:163`);
  - `answer.cmd_answer` (`answer.py:317`), `cmd_zones_extend` (`:498`);
  - `cleanup.cmd_kill` (`cleanup.py:502`);
  - `amend.cmd_amend_tests` (`amend.py:66`, `:70`);
  - `budget.cmd_budget` (`budget.py:451`);
  - `pull_main.cmd_pull_main` (`pull_main.py:44`);
  - `ci_rerun.cmd_ci_rerun` (`ci_rerun.py:61`);
  - `workspace.cmd_workspace` (`workspace.py:267`);
  - `auto.cmd_auto` (`auto.py:640`) — весь цикл одним `run_locked`. Каждый его шаг (`fsm.cmd_advance`, `runner.cmd_run`) — вложенный `run_locked` в том же процессе.
  - Сам код `auto.py` документов не пишет (только журнал и алерты): все коммиты цикла делаются внутри вложенных команд.
- Команды вне `run_locked`: `new`, `doctor`, `docs`, `note`, `doc-commit`, `artifact-history-snapshots`, `pin-update` и прочие. В них поведение остаётся прежним.
- Тесты зовут команды напрямую (`fsm.cmd_approve(t.id)`, `runner.cmd_run`, `cleanup.cmd_kill`), а не через `artel.main`. Поэтому обёртка только в `artel.main` выигрыша в тестах не даёт. Многие тесты подменяют `lease.run_locked` простой функцией (`tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py:53`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py:468` и другие) — у них отправка остаётся немедленной.
- Кто читает ссылку документов из `origin` во время работы задачи:
  - сверка `origin_sync_refusal`;
  - `docs`/`fetch_*`;
  - `doctor` (`artifact-ref-sync`, только команда `doctor`);
  - CI. Сценарий `scripts/plan_appendix_ci.py` (`.github/workflows/ci.yml:235`, `:282`) на пуше ветки `task/**` и на pull_request читает PLAN.md из `refs/artifacts/<id>` в `origin` (`scripts/plan_appendix_ci.py:186`). Если отправить кодовую ветку раньше документов, CI может прочитать старый PLAN.
- Где пульт отправляет кодовую ветку задачи:
  - `github_adapter.ensure_draft_mr` (`github_adapter.py:114`, отправка `:160`);
  - `github_adapter.ensure_head_in_origin` (`:205`, отправка `:234`; зовут `fsm_advance.py:478`, `pull_main.py:93`, `fsm_merge_gate.py:698`);
  - подтяжка на гейте мержа `_sync_main_or_wait` (`fsm_merge_gate.py:708`, отправка `:739`).
  - Отправка `main` (`fsm_merge_gate.py:1310`) PLAN не читает.
- Гейт мержа после отправки `main` делает по порядку (`fsm_merge_gate.py:1537`–`1543`):
  1. `_finalize_done_state` (строка паспорта `done`);
  2. `cleanup._commit_closing` (`:1539`, коммит закрытия);
  3. уборку;
  4. `_await_main_ci` — ожидание CI `main`, долгое;
  5. `_rebuild_core_reference`.
- Запуск процесса роли — `runner._spawn_and_wait` (`runner.py:1626`, вызов `spawn_agent` `:1674`). Шаг роли длится до часов. Коммиты документов в `cmd_run` идут после завершения роли (`runner.py:1950`). До запуска роли пульт коммитит документы только на путях отказа, которые сразу завершают команду (`runner.py:454`).
- Восстановление после обрыва процесса между коммитом и отправкой (SIGKILL) уже есть:
  - любая следующая отправка ссылки задачи отправляет её целиком, вместе с недосланными коммитами. У живой задачи это строка паспорта на следующем переходе, а гейт мержа и `kill` сами досылают её в `origin_sync_refusal`;
  - у закрытой задачи коммит закрытия досылает `doctor --fix` (`_fix_unsent_closed_refs`, `orchestrator/doctor/artifact_branches.py:180`), если голова ссылки равна коммиту закрытия;
  - до досылки `doctor` сообщает «нет в origin / расходится» — так же, как сейчас при отказе отправки.
- Параллельно идут волны сведения тестов. Их ТЗ требуют повторить таблицу мутаций «до», если подтяжка main изменила `orchestrator/`; изменение этой задачи это вызовет.

Сверка существующих тестов: 100 файлов, в которых встречаются `push`, `get-url`, `update-ref`, `refs/artifacts`, `ls-remote`, списки записанных вызовов (`raw_calls`, `calls`, `call_args_list`), шпионы `gitcmd.in_repo`/`SpyRun`, а также команды под `run_locked` вместе с сверкой `origin`.

- Затронуты два теста:
  1. `tests/test_review_package.py`, `CmdRunReviewPackageTest::test_developer_step_has_no_package`. Точный список вызовов git во время `runner.cmd_run`: вызовы `["-C", clone, "remote", "get-url", "origin"]` и `["-C", clone, "push", "-q", "origin", f"{ref}:{ref}"]` стоят сразу после `update-ref`. После задачи они уйдут в конец, после трёх завершающих `rev-parse --verify --quiet`. Нужна правка по мандату (перечень ниже).
  2. `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py:442`, `ArtelCodeMergeTest::test_ac11_rebuild_is_last_step_from_final_sha_without_commits`. Подмена `get_reference` посреди `approve` снимает состояние `origin`: проверяются RETRO в `origin` (`has_retro`, `:351`; проверка `:490`) и неизменность ссылок `origin` после `approve` (`:496`). Тест остаётся зелёным без правки, если коммит закрытия отправляется сразу (требование 3д).
- Остальные 98 файлов не затронуты. Причины:
  - запись идёт вне команды (`store.set_state`, `commit_files`, `snapshot.commit_closing` напрямую);
  - команда не под `run_locked`;
  - шпион считает только отправки кодовой ветки, вызовы `gh` или `fetch`;
  - шпион, роняющий git по кадрам стека, ловит только `worktree add`, `ls-tree`, `clone`, `archive` и `fetch main`;
  - `origin` читается после возврата из команды;
  - записи об отправке при работающем `origin` не появляются и сейчас.
- Отдельно проверены:
  - `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py` — хук отклоняет только ветку кода, шпион стоит на `ensure_head_in_origin`;
  - `tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_remote_base.py` — `ensure_draft_mr` зовётся напрямую;
  - `tests/test_auto_cycle.py:450` — считает вызовы `ensure_head_in_origin`, не отправки;
  - `tests/test_prune_abolished_rules.py:115` — `prune` не под `run_locked`;
  - `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:784` — роняет только `worktree add`;
  - `tests/test_01m4xv9xpjzd29py0ntnz98m02_commands.py:35` — проверяет только `force=True`;
  - `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py` — шпион роняет выписку, `ls-tree` и `fetch main`, но не отправку.

## Требования

1. **Область отложенной отправки** (дальше — «область»). Так называется время исполнения тела одной команды пульта под `lease.run_locked`.
   - а) В `orchestrator/artifact_branch.py` появляется менеджер контекста области (имя выбирает разработчик, например `deferred_send()`) и открытая функция досылки `send_pending(task_id=None, repo=None)`: досылка одной задачи, всех задач одного репозитория или всех.
   - б) Внутри области `_write` после удачного `update-ref` не зовёт `_send`, а запоминает пару (задача, репозиторий записи) в наборе недосланных. Набор хранится в памяти процесса, порядок — порядок первой записи, повтор пары не добавляется.
   - в) Вне области (нет ни одной открытой) — прежнее поведение байт в байт: `_send` сразу после `update-ref`.
   - г) Области вкладываются (вложенный `run_locked` в том же процессе: шаги `auto`, `cmd_run_and_advance`). Досылка всего набора делается при выходе из области на любом уровне вложенности, в том числе из вложенной. Поэтому шаг цикла `auto` (`cmd_advance`, `cmd_run`) досылает свои коммиты в конце шага, а не в конце цикла.
   - д) `lease.run_locked` открывает область вокруг `body(sid)` внутри `try`. Досылка идёт до `release` в `finally`, то есть пока lease ещё держится. При отказе `acquire` (тело не исполнялось) область не открывается.
2. **Досылка — это вызов прежнего `_send(task_id, repo)` по одному разу на каждую пару из набора, в порядке набора.**
   - Пара удаляется из набора до вызова `_send`, поэтому повторной досылки той же пары нет.
   - Правила журнала (`_journal_push_outcome`, `_last_send_failed`) действуют на каждую досылку так же, как сейчас на каждый коммит: отказ — одна запись на досылку; успех — запись только после повтора или после записанного раньше отказа.
   - Без `origin` — ни отправки, ни записи, ни исключения.
   - Пустой набор — ни одного вызова git и ни одного обращения к БД.
3. **Досрочная досылка, до выхода из области:**
   - а) `origin_sync_refusal(task_id)` первым действием досылает эту задачу (`send_pending(task_id)`), затем идёт прежняя логика. Тексты отказов и `None` прежние. Число отправок за вызов не больше прежнего: после досылки ссылки совпадают, и второй отправки нет.
   - б) `fetch_from_origin(task_id)` досылает эту задачу, `fetch_all_from_origin(repo)` — все задачи этого репозитория. Обе — до `git fetch`, чтобы своя недосланная голова не дала `FETCH_DIVERGED`.
   - в) Перед отправкой кодовой ветки задачи досылается эта задача, и только когда отправка кодовой ветки действительно идёт: в `github_adapter.ensure_draft_mr` перед `:160`, в `github_adapter.ensure_head_in_origin` перед `:234` (после сверки «голова уже в origin» — при совпадении досылки нет), в `fsm_merge_gate._sync_main_or_wait` перед `:739`. Так CI ветки `task/**` читает PLAN не старше кода.
   - г) В `runner._spawn_and_wait` перед вызовом `spawn_agent` (`:1674`) досылается весь набор, чтобы недосланные документы не ждали конца шага роли.
   - д) В `snapshot.commit_closing` после записанного коммита закрытия (`:138`, sha не пуст) досылается эта задача — вместе со строкой паспорта `done`/`killed`. Коммит закрытия оказывается в `origin` до уборки, ожидания CI `main` и пересборки справочника, как сейчас.
   - е) Перед долгими этапами гейта мержа досылается весь набор: первым действием `fsm_merge_gate._wait_for_branch_ci_green` (`orchestrator/fsm_merge_gate.py:332`, ожидание CI ветки), `fsm_merge_gate._ci_ready_or_wait` (`:756`, ожидание первых проверок CI) и `fsm_merge_gate._await_main_ci` (`:642`, ожидание CI `main`), а в `fsm_merge_gate._full_suite_or_refuse` (`:1053`) — после проверки «прогон нужен» и до запуска прогона. Так документы не отстают в `origin` на время этих этапов (15–20 минут).
4. **Исключения.**
   - Тело области завершилось исключением (в том числе `SystemExit` отказа и `KeyboardInterrupt`) — досылка всё равно делается, затем наружу выходит то же исключение тела.
   - Исключение самой досылки при уже летящем исключении тела его не заменяет: оно печатается одной строкой в stderr, а досылка остальных пар продолжается.
   - При нормальном выходе тела исключение досылки поднимается после попытки дослать остальные пары.
5. **Неизменные части.**
   - `push(task_id)`, `_attempt_push`, `_classify_push_failure`, `_journal_push_outcome`, `_origin_configured`, тексты журнала, `write_commit`, `commit_files`/`commit_change` (имена, сигнатуры, возвращаемые значения) не меняются.
   - Прямые отправки `snapshot.py:294` и `orchestrator/doctor/artifact_branches.py:137` не меняются.
   - Строка документации модуля `artifact_branch.py` и `_send` приводятся в соответствие: «отправка — при выходе из команды пульта и в точках досрочной досылки», а вне команды — сразу.
6. **Тесты.** Новый файл `tests/test_<id>_one_push_per_command.py` в стиле pytest (ADR-0027). В документации каждой функции — «Ловит мутацию:». Песочница — настоящий git с локальным bare-origin (`tests/sandbox.py`, `tests/fixtures.py`); счёт отправок ведёт подмена `gitcmd.subprocess.run`, которая записывает argv с `git push … refs/artifacts/<id>`.
   - а) Названный сценарий: внутри одного `lease.run_locked` тело делает три `store.set_state` и один `commit_files`. В конце тела отправок 0, после возврата — ровно одна; голова в `origin` равна локальной. Тот же сценарий вне `run_locked` даёт 4 отправки (прежнее поведение).
   - б) Вложенность: внешний `run_locked` и два вложенных подряд, в каждом коммит. После выхода из первого вложенного отправка уже сделана, и `origin` равен локальной голове до входа во второй. Всего две отправки, у внешнего выхода — ни одной лишней.
   - в) Исключения: тело коммитит и бросает `RuntimeError` и `SystemExit("отказ")`. Отправка сделана, наружу выходит тот же объект исключения, lease снят. Досылка, бросившая исключение при летящем исключении тела, его не подменяет.
   - г) Сверка до проверки: внутри области коммит, затем `origin_sync_refusal` даёт `None`, отправка одна за всю область. Внутри области коммит, затем `fetch_from_origin` даёт `FETCH_SAME`, а не `FETCH_DIVERGED`.
   - д) Кодовая ветка: внутри области коммит документов, затем `ensure_head_in_origin` для ветки, которой нет в `origin`. Отправка `refs/artifacts/<id>` в записанных argv стоит раньше `push -u origin <ветка>`. Если голова кодовой ветки уже в `origin`, досылки в этом вызове нет.
   - е) Закрытие: внутри области `set_state` и `snapshot.commit_closing`. Отправка одна и сделана до возврата из `commit_closing`; RETRO есть в `origin` сразу после неё.
   - ж) Запуск роли: в момент вызова `runner.spawn_agent` набор недосланных пуст при недосланном коммите, сделанном до запуска (образец песочницы — `CmdRunReviewPackageTest` в `tests/test_review_package.py`; коммит до запуска — подменой шага подготовки, которая зовёт `commit_files`).
   - з) Журнал на досылку: `origin` отвергает запись (хук `pre-receive`), внутри области три коммита — ровно одна запись «push артефактной ветки FAILED» с прежним текстом. В следующей области с исправленным `origin` — одна запись об успехе после отказа. Ответ сервера 5xx на первой попытке — повтор и запись «попыток 2», как у `_send`.
   - и) Без `origin` (remote удалён): коммиты внутри области — ни одной отправки, ни одной записи, без исключения. Пустой набор при выходе из области — ни одного вызова git, в том числе без `remote get-url`.
   - к) Две задачи в одной области (в том числе запись с `target=` до строки задачи в БД): по одной отправке на каждую, в порядке первой записи, каждая — в `origin` своего репозитория.
   - л) Долгие этапы гейта мержа: внутри области коммит документов, затем `_wait_for_branch_ci_green`, `_ci_ready_or_wait`, `_await_main_ci` (опрос CI подменён) и `_full_suite_or_refuse` с нужным прогоном (прогон подменён): в момент первого опроса CI и в момент запуска прогона ссылка в `origin` равна локальной. При ненужном прогоне `_full_suite_or_refuse` не досылает.
   - м) Обрыв: досылка подменена так, что ничего не делает (процесс «умер» до отправки), — `origin` отстаёт. Затем `store.set_state` вне области отправляет ссылку целиком (голова в `origin` равна локальной), `origin_sync_refusal` досылает и даёт `None`. У закрытой задачи `doctor --fix` (`_fix_unsent_closed_refs`) досылает коммит закрытия.
7. **Число вызовов.** В PLAN — счёт вызовов git всего и по подкомандам `push`, `remote` на тесте `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac5ProofMismatchTest` (или его наследнике после сведения) до и после. Счёт снимается шпионом процессов во временной копии, файл тестов не меняется. Ожидание исследования — около 12 отправок меньше (досрочные досылки требования 3е его немного уменьшают). Если сокращение меньше 6, в PLAN — разбор по точкам досылки (требование 3), где тратятся отправки.
8. **Существующие тесты** остаются зелёными. Правится только тест из перечня ниже и только по мандату. Покраснел любой другой тест — эскалация с его именем и причиной, а не правка.

### Перечень правок существующих тестов, требующих мандата Оператора

1. `tests/test_review_package.py`, `CmdRunReviewPackageTest::test_developer_step_has_no_package`:
   - в ожидаемом списке перенести два элемента — `["-C", clone, "remote", "get-url", "origin"]` и `["-C", clone, "push", "-q", "origin", f"{ref}:{ref}"]` — из места сразу после `["-C", clone, "update-ref", ref, "f" * 40, "0" * 40]` в самый конец списка, после последнего `["-C", clone, "rev-parse", "--verify", "--quiet", ref]`;
   - в комментарии перед списком поправить фразу о порядке («запись ссылки и её отправка в `origin`, затем чтение головы…»): отправка — при выходе из команды;
   - остальное не трогать.

Зоны: orchestrator/artifact_branch.py, orchestrator/lease.py, orchestrator/snapshot.py, orchestrator/github_adapter.py, orchestrator/fsm_merge_gate.py, orchestrator/runner.py, docs/codebase-map.md, tests/

Ограничение зон по смыслу:
- в `orchestrator/artifact_branch.py` — `_write`, `_send` (строка документации), `origin_sync_refusal`, `fetch_from_origin`, `fetch_all_from_origin`, строка документации модуля и новые помощники области и досылки рядом с `_send`;
- в `orchestrator/lease.py` — только тело `run_locked` (открытие области вокруг `body(sid)`, отложенный импорт `artifact_branch`);
- в `orchestrator/snapshot.py` — только досылка в `commit_closing` после записанного коммита;
- в `orchestrator/github_adapter.py` — только досылка перед отправками `:160` и `:234`;
- в `orchestrator/fsm_merge_gate.py` — только досылка перед отправкой `:739` и в начале `_wait_for_branch_ci_green`, `_ci_ready_or_wait`, `_await_main_ci`, а также перед прогоном в `_full_suite_or_refuse` (требование 3е);
- в `orchestrator/runner.py` — только досылка перед `spawn_agent` в `_spawn_and_wait`;
- в `docs/codebase-map.md` — только строки, отражающие новые помощники и новый импорт;
- в `tests/` — новые файлы и правка из перечня по мандату.

Только чтение: docs/adr/0021-project-area-and-immutable-pult.md, .github/workflows/ci.yml, orchestrator/gitcmd.py, orchestrator/store.py, orchestrator/fsm.py, orchestrator/fsm_advance.py, orchestrator/auto.py, orchestrator/cleanup.py, orchestrator/answer.py, orchestrator/amend.py, orchestrator/catalog.py, orchestrator/checkpoint.py, orchestrator/pull_main.py, orchestrator/docs_fetch.py, orchestrator/workspace.py, orchestrator/doctor/artifact_branches.py, orchestrator/advance_gates/tests_writing.py, scripts/plan_appendix_ci.py, tests/sandbox.py, tests/fixtures.py, tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py, tests/test_artifact_ref_sync.py, tests/test_artifact_branch_server_retry.py, tests/test_01m5qr7kgyznvwdp5h86s9py04_origin_push_checks.py, scripts/guard.py.

Не входит:
- прочий код orchestrator/ вне зон и вне перечня «Только чтение»;
- одна строка паспорта на команду вместо коммита на каждый `set_state` (только через ADR);
- область для команд вне `run_locked` (`new`, `doctor`, `docs`, `note`, `doc-commit`, `artifact-history-snapshots`);
- обёртка в `artel.main`;
- прямые отправки `snapshot.py:294` и `orchestrator/doctor/artifact_branches.py:137`;
- правка `doctor`;
- одна проверка `origin` (git 1, смержена);
- пакетное чтение (git 5, смержена);
- перевод прямых вызовов git в `gitcmd` (git 3);
- память чтений в контексте команды (git 4);
- одно получение origin/main на `approve`.

Бюджет: $60.
