# Ревизия кодовой базы — 2026-09-13 (шестая; актуализация замечаний для фазы R)

## Сводка

Шестая ревизия по skills/code-revision.md (редакция 9fabc281); объект — origin/main 24433161 в отдельной
рабочей копии. С пятой ревизии (12.09, f3b7cd4a) смержена одна задача (01M2B6K3EM, $27.73; доска: 212 done,
16 killed, в полёте нет) и четыре операторских коммита. Полный набор: 2329 тестов + 477 подтестов, 185 с при
`-n 4` и 349 с при `-n 2` — результаты совпали, зависимости от порядка нет; stderr пуст. Главное: рост
оркестратора с 12.09 нулевой (96 функций длиннее 50 строк на обоих деревьях), поэтому отчёт — ТЗ-черновики
фазы R с замерами и вторым мнением по каждой ★; утечка тестов в пульт (CR-2026-09-12-1) повторилась в обоих
прогонах (54 каталога), перезапись карты — нет.

## Статус направлений

| # | Направление | Статус | Чем проверено |
|---|---|---|---|
| 0 | Судьба находок 12.09 | приложение: 1 исполнено, 1 закрыто отчётом, 9 живо | `git log f3b7cd4a..HEAD`, доска, повтор замеров |
| 1 | Рудименты | чисто | скан имён по дереву (4333 определений в 235 py-файлах, счётчик упоминаний по всем текстовым файлам): функций без упоминаний 0; TODO/FIXME/XXX 0 |
| 2 | Дубли | находки CR-2, CR-5 | AST-сравнение тел: orchestrator/ 0 групп; tests/ 17 групп одинаковых setUp/помощников (26 по скану второго мнения); три WIP-чекпоинта checkpoint.py построчно одинаковы |
| 3 | Мёртвые ветки | нового нет; CR-2026-09-12-6 живо | AST-скан неиспользуемых параметров: 23 в orchestrator/, список тот же |
| 4 | Переусложнение | находки CR-1, CR-3, CR-4, CR-7, CR-8 | AST-скан длин: 96 функций > 50 строк в orchestrator/ (88 без doctor/), 4 в scripts/guard.py; модулей > 500 строк 14 + guard.py; дерево f3b7cd4a тем же сценарием — 96 |
| 5 | Производительность | нового нет; CR-2026-09-12-8 живо | timeit ×20 по живой БД (чтение): шаги задачи (232 из 32 360 строк) 2.89 мс, индекса нет; `status` на 228 задачах 0.23 с |
| 6 | Согласованность | находка CR-6; CR-2026-09-12-4 живо | grep межмодульных вызовов приватных имён (56 имён, 124 места); разбор импортов — 14 двусторонних циклов; три регенерации карты голым `python3` на месте |
| 7 | Гигиена | находки CR-9, CR-12; CR-2026-09-12-7 живо | .artel/logs 167 МБ / 3843 файлов (+2, +12 МБ за 12.09); 243 сироты в worktrees главной копии; notes-pending пуст; два прогона с `--durations=5` |
| 8 | Скилы и миссии | нового нет; CR-2026-09-12-11 живо | grep `bash_guard\|PreToolUse\|ARTEL_ROLE` по скилам, roles/gates.yaml, docs/reference: role-home.md переписан 01M2B6K3EM (:23–29), хук удалён; test-authoring.md:20 «unittest», gates.yaml:19 «T085» — на месте |
| 9 | Аномалии журнала | находка CR-11 (данные) | SQL чтением: 17 done за 12.09, 12 эскалаций, 91 отклонённый переход, 14 предупреждений бюджета, 0 UNKNOWN, 0 таймаутов; 126 открытых алертов без изменений |
| 10 | Бэклог и копилка | приложение | 123 строки docs/backlog.md против доски и журнала; 13 новых строк с 12.09 — вердикт по каждой; notes-pending пуст |
| 11 | Обходные сценарии | приложение | 36 каталогов scratchpad (5 непустых), `git worktree list` (15), раздел «Запуски и рабочие копии», копилка 12–13.09; pin.py:56, canary.py:956 |

## Находки

### CR-2026-09-13-1 ★ — runner.py (R4): два шага-монолита, разбор внутри модуля
- Адрес: orchestrator/runner.py:758–1019 `run_agent_once` (262), :225–431 `_run_developer_step` (207),
  :158–222 `_cmd_run` (65, отделён 01M28NWPS3).
- Суть: `run_agent_once` — четыре фазы в одном теле: подготовка (промпт-файл, окружение, рабочий каталог,
  git-идентичность; пять однотипных блоков `journal + print + return "skipped"` с разными текстами), запуск и
  ожидание (spawn, pump, таймаут, kill группы), учёт (friction, стоимость, бюджет программы), исходы (timeout /
  rc≠0 / нет артефакта / успех). `_run_developer_step` — отказы до старта (пауза/стоп-кран/скилы через
  `sys.exit`, чужая ветка/pre-flight/инцидент через `return`), сборка промпта, цикл попыток с бэкоффом,
  эскалация. Модуль — узел: 38 тестовых файлов, 101 `patch.object(runner, …)` по публичным именам (`cmd_run`
  66, `role_env` 27, `role_cwd` 16, `run_agent_once` 4, `spawn_agent` 3) — разбор только ВНУТРИ модуля.
  Условия R4 («после стека ч.3 и P0») наступили: 01M1RDCEF0, 01M1REVEZ1 done.
- Класс: $45. Риск: низкий-средний (тексты SKIPPED и исходов сверяются дословно: tests/test_agent_log.py:606,
  test_agent_prompt.py:257, test_multitarget.py:881). Не трогать: тексты, коды исхода, `finally` с
  `zone_lock.release_claim` в `_cmd_run`. Доказательство: AST-скан; grep патчей; разбор импортов.

### CR-2026-09-13-2 ★ — checkpoint.py (R7-остаток): три одинаковых WIP-чекпоинта и функция на 252 строки
- Адрес: orchestrator/checkpoint.py:534–785 `_commit_external_step_artifacts` (252, докстринг :535–649 — 115),
  :83–183 `commit_timeout_checkpoint` (101), :186–279 `_discard_out_of_mandate_changes` (94), :902–967 (66).
- Суть: тела `commit_timeout_checkpoint`:159–184, `commit_abnormal_checkpoint`:319–342,
  `commit_pause_now_checkpoint`:375–398 построчно одинаковы (target → `_commit_worktree_change` → журнал /
  `record_fixation` либо `_discard_out_of_mandate_changes` → `_commit_external_step_artifacts`), различаются
  четырьмя строками текста и флагом `timeout` — общий помощник снимает ~50 строк. Функция переноса — пять фаз
  (сбор файлов байтами с фильтром .gitignore; журнал посторонних файлов планки и корня; конфликт-гвард против
  baseline; кандидаты на удаление по `own_commit_marker`; коммит в артефактную ветку) с переплетённым
  состоянием (`files` мутируется в четырёх фазах). Вызовы только внутри модуля (:181, :341, :397, :531).
- Класс: $35. Риск: низкий. Не трогать: правила фильтра, конфликт-гвард, ранние `return ""` (:679–684,
  :771–776), ПОРЯДОК записей журнала (fsm_advance.py:459 сверяет последнюю запись визита с
  `STRAY_ACCEPTANCE_FILES_ACTION`), сигнатуру `(conn, task_id, role, target, timeout)` и строку возврата —
  контракт tests/test_checkpoint_external_step_artifacts.py:251.
- Доказательство: AST-скан; `grep -rn "_commit_external_step_artifacts(" orchestrator/`; второе мнение.

### CR-2026-09-13-3 ★ — fsm_advance.py: 1564 строки гейтов в одном файле, 28 коммитов с 06.09
- Адрес: `_zones_gate` :839 (123), `_capacity_gate` :584 (102), `_mutation_claim_gate` :1082 (93),
  `_review_rework_gate` :1177 (90), `spec_writing` :62 (87), `_acceptance_run_refuses` :1363 (74),
  `tests_writing` :511 (71), `in_dev` :1496 (69), `_acceptance_lock_refuses` :1299 (62),
  `_tests_writing_stray_plank_files_gate` :411 (59), `_apply_plan_budget` :1439 (55); 39 функций.
- Суть: R2 сделала гейты предикатами, но все семейства остались в одном модуле — самый частый файл в зонах
  задач (28 коммитов за неделю). Разрез в пакет `orchestrator/gates/`: `_base.py` (`GateRefusal`, `_run_gates`
  — нужны всем; оставить их в fsm_advance.py нельзя, цикл импортов), `zones.py`, `capacity.py` (с
  `_EMPTY_DIFF_TEXT`, `CAPACITY_GATE_REASON` — снаружи не берутся), `review.py` (`_review_escalation_sha_gate`,
  `_mutation_claim_gate`, `_review_rework_gate`, помощники дат и sha), `acceptance.py` (`_acceptance_lock_refuses`,
  `_acceptance_run_refuses` — сознательно мимо `_run_gates`, докстринг :1369), `tests_writing.py`
  (`_tests_writing_*`, `_origin_push_gate`, `_registry_gate`, `_freshness_refuses`). В fsm_advance.py остаются
  обработчики состояний, эффекты вердиктов (`_review_approved`, `_in_dev_plan_escalate`, `_apply_plan_budget`)
  и алиасы старых имён на одну волну: answer.py:31 берёт `_split_zone_paths`, `_plan_zones_extension_paths`,
  `_ZONES_MANDATE_MARKER`; 21 тестовый файл зовёт гейты напрямую (`_mutation_claim_gate` ×13, `_run_gates` ×9).
  Единственный патч через модуль — tests/test_git_fixation.py:359 (`_capacity_gate_refuses`) — не ломается:
  вызывающий `in_dev` остаётся в fsm_advance.py.
- Класс: $45. Риск: средний — конфликт-магнит, только тихое окно без живых задач в in_dev. Не трогать:
  логику гейтов (защита) — дословно, включая обход `_run_gates` у приёмки. Доказательство: `wc -l`; AST-скан;
  `git log --since=2026-09-06 -- orchestrator/fsm_advance.py`; второе мнение.

### CR-2026-09-13-4 ★ — canary.py: две несвязанные области в 1358 строках
- Адрес: orchestrator/canary.py:181–462 — запечатанный пул (`_pool_dir`, `sealed_path`, `guids_path`,
  `_mac_key`, `_secret_fd`, `_hmac_tag_hex`, `_openssl_encrypt/_decrypt`, `_serialize/_deserialize_pool`,
  `_authorized_pool_payload`, `restore_pool_if_missing`, `pool_drift_warning`, `cmd_pool_seal`; ~280 строк);
  :501 `_ephemeral_clone` (98), :850 `_drive_task` (104), :1187 `_run_one_task` (151) — прогон.
- Суть: общая точка областей одна — `_pool_dir()` (:181, зовётся и `cmd_canary`:1341). Вынос пула в отдельный
  модуль (имя `canary_pool.py` занято doctor/canary_pool.py — например `pool_seal.py`) уводит из canary.py
  `hashlib`, `hmac`, `struct`, `uuid`, `keychain`; цикла нет (`catalog.cmd_init` берёт `canary` ленивым
  импортом :46–50 — переключить на новый модуль). Потребители пула: artel.py:705, catalog.py:50,
  doctor/cli.py:98, doctor/canary_pool.py:61; answer.py:113 и prune.py:80 — только комментарии.
  `_run_one_task` — разбор внутри модуля: прогон в клоне / сверка с бейзлайном / диагностика и canary_runs.
- Класс: $35. Риск: низкий-средний — в tests/test_canary.py ~20 мест зовут имена пула напрямую
  (:1492–1636) и три патча `canary.keychain` (:1567, :1588; test_doctor_canary_pool.py:149) переписываются
  обязательно. Не трогать: HMAC/шифрование, авторизацию пула, рубеж `runner.in_role_environment`.
  Доказательство: `grep -n "^def " orchestrator/canary.py`; grep потребителей; второе мнение.

### CR-2026-09-13-5 ★ — R8: песочницы тестов — подмножества PATCHED_ATTRS, копии setUp, 93 планочных _sandbox.py
- Адрес: tests/sandbox.py (966 строк, 7 классов; `ALL_CONFIG_ATTRS` :63–64); собственные подмножества
  `PATCHED_ATTRS` в 10 файлах — без WORKTREES три: test_git_fixation.py:159 (регрессия коммита d692f2a6:
  список T045 заменён наследованием), test_multitarget.py:104 (там `workspace.ensure` подменён — не течёт),
  test_doctor.py:2413 (намеренно); 270 `setUp`, 17–26 групп одинаковых тел (test_agent_log.py:84 =
  test_step_cost.py:73 = test_agent_failure.py:47; test_mutation_claim_gate.py:24 =
  test_protected_paths_gate.py:87; test_invariants.py:439/733 и 635/1420 — защищённый путь); побайтно
  совпадают помощники `event`, `fake_git_config` (а `result_event` ×3, `spec_text`, `assistant_event` —
  разные сигнатуры, не дубли); в main 93 `tasks/<id>/acceptance_tests/_sandbox.py` (18 252 строки).
- Суть: пункт R8. Механизм утечки по коду: `workspace.path` строит путь от `config.WORKTREES`
  (workspace.py:21–23), вычисленного при импорте (config.py:59) — патч ROOT его не двигает;
  `RealPultGitTest` (test_git_fixation.py:724) делает настоящий `git worktree add` из временного репозитория.
  Порядок: сначала дефект CR-2026-09-12-1 отдельной задачей («рефакторинг ≠ фикс»), затем перенос
  идентичных setUp/помощников в базовые классы; исторические `_sandbox.py` планок — не трогать (уборка из
  main — очередь Оператора); шаблон будущих планок — скил test-authoring (защищённый путь).
- Класс: $25. Риск: низкий (только tests/; test_invariants.py вне зон). Доказательство:
  `grep -n "PATCHED_ATTRS = (" tests/*.py`; AST-сравнение тел; `git ls-files`; второе мнение.

### CR-2026-09-13-6 — приватные имена как межмодульный API и 14 двусторонних циклов импортов
- Адрес: 56 приватных функций вызываются из чужих модулей в 124 местах orchestrator/: `liveness._pid_alive`
  ×22, `doctor._auto_ack_gone` ×13, `liveness._age_seconds` ×10, `fsm._read_branch_text_or_refuse` ×6,
  `fsm._answer_baseline_or_refuse` ×5, `fsm_advance._split_zone_paths` (answer.py),
  `failure_classification._record_failure_classification` (runner.py:958) и др. Циклы (часто через ленивые
  импорты): runner ↔ lease, budget, pause, doctor; fsm ↔ fsm_advance, fsm_merge_gate, review; store ↔ alerts,
  artifact_branch, coldstart, fixation, schema; canary ↔ catalog; alerts ↔ failure_classification.
- Суть: подчёркивание не означает приватности. Не отдельная задача, а правило для фазы R: переносимая функция
  получает публичное имя в новом модуле, старое — алиас на одну волну; остальные — как есть.
  Класс: $0 (правило в ТЗ Р-3, Р-4). Доказательство: `grep -rhoE "\b[a-z_]+\._[a-z]\w*\(" orchestrator/`.

### CR-2026-09-13-7 — auto.py после R1 снова 969 строк
- Адрес: orchestrator/auto.py:655 `_pre_advance_step` (136), :875 `_cmd_auto` (94), :793 `_role_run_step`
  (80), :275 `_role_step_since_state_entry` (68), :91 `_wait_for_zone` (60). R1 (01M1SC40NT) разобрала
  `_cmd_auto` 246 → 94, но буксование, ожидание зоны, конфликт подтяжки и гейт переделки нарастили
  `_pre_advance_step` и `_role_run_step`. Кандидат Р-6: `_pre_advance_step` → «переход выполнен» / «отказ
  advance и его класс» / «стоп-краны цикла» с тем же `Stop|Advanced|Refused`. Класс: $25. Риск: низкий.

### CR-2026-09-13-8 — второй эшелон длинных функций: что брать, что «не трогать: защита»
- `lease.acquire` lease.py:28 (173) — протокол перехвата lease, инвариант параллельности: не трогать;
  `schema.migrate` :94 (152) — линейный реестр миграций; `review.review_package` :197 (214) — сборка пакета,
  кандидат Р-7 ($25); `pause.cmd_pause_now` (108), `role_prompt.mission_brief_package` (109),
  `fsm_autogate._autogate_conditions` (97), `spend.charge_missing_result` (87), `fsm.confirm_fixation` (86) —
  ниже порога боли; scripts/guard.py (1856 строк, 60 функций; `main` 96, `_content_errors` 93) — валидатор
  артефактов, правила = защита; вне волны. Класс: $25 (только Р-7). Доказательство: AST-скан длин.

### CR-2026-09-13-9 — здоровье набора тестов: две 45-секундные проверки инвариантов; утечка повторяется
- Адрес: tests/test_invariants.py `MergeOnlyFromMergeGateTest::test_no_other_state_and_no_other_command_merges`
  45.31 с, `AgentRunsOnlyFromRunTest::test_run_starts_the_agent_only_in_working_states` 45.10 с; далее 15.1 с ×3.
- Суть: 2329 + 477 (12.09: 2322 + 511; снят test_role_bash_guard.py, добавлены test_conftest_role_guard.py и
  test_artel_role_restricted_commands.py); 185.3 с при `-n 4` (12.09: 174 с), 348.7 с при `-n 2`; результаты
  идентичны — строка копилки 12.09 о зависимости от порядка не воспроизвелась. Два теста по 45 с — четверть
  стены на одном воркере (защищённый путь: сигнал Оператору). Оба прогона оставили `.artel/worktrees` с 54
  каталогами (`gitdir: …/T/tmp…`), `.artel/projects`, `.artel/session-id`; docs/codebase-map.md чист оба
  раза; следы убраны. Класс: $0 (данные для CR-2026-09-12-1). Доказательство: `--durations=5`; `ls`.

### CR-2026-09-13-10 — граница гейта pin-update при ровно N мержах: не дефект, а формулировка
- Адрес: pin.py:56 `age >= CANARY_MAX_MERGES_SINCE_GREEN`, doctor/canary_pool.py:187 (тот же `>=`),
  canary.py:956, gitcmd.py:90 (`--first-parent --merges`); tasks/01M1NGFK3N…/ANSWER-1.md п.3.
- Суть: ANSWER-1 п.3 определяет «не старше N» ⇔ «возраст < N», config.py:342–348 — «достигает порога»,
  tests/test_doctor.py:746 ловит мутацию `>=` → `>`. Двухшаговый pin-update при десяти мержах — проектное
  поведение ADR-0013: волна из N и более мержей всегда требует канарейки на целевом sha. Расходится только
  текст отказа pin.py:57–60 и artel.py:142 («не старше N мержей» читается как «≤ N») — заменить на «меньше N».
  Класс: $0 (правка текста Оператором). Доказательство: код, ANSWER-1, tests/test_doctor.py:701–760.

### CR-2026-09-13-11 — журнал 12–13.09 (данные, не код)
- 17 задач done за 12.09, $371.65 (среднее $21.86, максимум $39.70 — 01M297HF), 9 итераций ревью;
  эскалаций 12 (красная планка после подтяжки 2, лимит ревью 1, конфликты подтяжки 2, батч вопросов 1);
  отклонённых переходов 91 («дерево не на ветке задачи» 32 — класс с 05.09 без имени); «бюджет:
  предупреждение» 14; «нет шага developer после…» 8; UNKNOWN 0, таймаутов 0. Канарейка: прогон 13 на
  27ddceb3 — red/killed 12.09 12:03Z ($6.85); всего 13, зелёных 5. Алерты: 126 открытых без изменений
  (github_adapter 88, spend.unknown_cost 22, checkpoint 5, amend_tests 3, 8 по одному), архив пуст. Расход
  $5575.84 (+$0.97); ADR-0010 без дополнения, роадмап §5 — срез 06.09. Класс: $0 (CR-2026-09-12-2 живо).

### CR-2026-09-13-12 — «Граница волны 4» исполнена на две трети; пульт на пине без `note --flush`
- Адрес: очередь docs/backlog.md; .claude/hooks/guard-artel-bg.py и settings.json:16 главной копии (вне git).
- Суть: сделаны flush удержанных строк (notes-pending пуст, 13 строк в файле) и коммит operator-gates.md
  (5fe4cb1f); хук клиента на месте, хотя 01M2B6JWGS смержена. Мерж 01M2B6JS2B (`note --flush`) — не предок
  пина: команда в главной копии недоступна, flush исполнен обходом — ещё довод к pin-update. Класс: $0
  (снять хук; pin-update). Доказательство: `ls .claude/hooks`; `git merge-base --is-ancestor`.

### CR-2026-09-13-13 — двойной прогон CI одного коммита (push + pull_request) вешает merge_gate
- Адрес: .github/workflows/ci.yml (триггеры `push: task/**` и `pull_request`), orchestrator/ci.py (ожидание
  всех проверок коммита, потолок 3600 с); копилка 13.09 (01M2B6K3EM: 20+ минут, push зелёный за 5 мин,
  pull_request — два задания в queued).
- Суть: класс копилки 06.09 «CI дважды» (новая строка — дубль по механике); обход — `gh run cancel` +
  `gh run rerun`. Кандидаты: (а) печать застрявшего прогона и события в ожидании; (б) зелёный прогон того же
  workflow на том же sha по любому событию засчитывается — orchestrator/ci.py + tests/test_ci_status.py ($10);
  (в) снять `pull_request` для task/** — .github/ защищён, решение Оператора. Класс: $10. Риск: низкий.

## Переоткрытия известного (в счёт не идут)

- Одноимённые помощники tests/ мимо sandbox (CR-2026-08-31-2) — материал R8 (CR-5); уборка исторических
  `tasks/` и `docs/retro/` из main — очередь Оператора (добавляет 93 `_sandbox.py` планок).
- Реестр CLI-команд artel.py (840 строк) — конфликт-магнит №2; .artel/artel.db 0 байт — не удалён.

## Сверка с фазой R роадмапа (§3)

| Пункт | Вердикт | Факт на 24433161 |
|---|---|---|
| R0 | исполнено (12.09) + этот отчёт | roadmap:494 велит «уточнить фазу по отчёту» — уточнение: ТЗ Р-1…Р-7 |
| R1 auto | смержено 05.09; модуль вырос снова | 969 строк; CR-7 → Р-6 |
| R2 fsm_advance | смержено 06.09; устарело по отчёту | 1564 строки — CR-3 → Р-3 |
| R3 fsm/pull | смержено 06.09 | fsm.py 901 (было 1027), pull.py 456 |
| R4 runner | живо, условия наступили | CR-1 → Р-2; «`_cmd_run` 219» устарело: 65, зато `_run_developer_step` 207 |
| R5 doctor | смержено 06.09 (01M1TT9BPB); roadmap:38 «в работе» — стухло | пакет doctor/; функций > 50 — 8, максимум isolation_smoke 110 |
| R6 store | смержено 06.09 | 951 строка / 60 функций, > 50 — одна (51) |
| R7 checkpoint | остаток живо | CR-2 → Р-1; часть fsm_merge_gate смержена (`_cmd_approve_merge_gate` 177 → 54 + 54) |
| R8 песочницы | живо | CR-5 → Р-5, после фикса CR-2026-09-12-1 |
| «~$300» | актуализировано | ядро Р-1…Р-5 $185; с Р-6, Р-7 $235; плюс фикс утечки $15 |

## Топ-★ со вторым мнением

| ★ | Находка | Почему первой | Второе мнение (агент без контекста) |
|---|---|---|---|
| 1 | CR-2 checkpoint.py | самая дешёвая и изолированная: один патч в тестах, дубль трёх WIP-чекпоинтов построчный | подтверждено с оговорками: докстринг 115 из 252 строк; сохранить сигнатуру, ранние return и порядок журнала (fsm_advance.py:459); маркер `own_commit_marker` продублирован литералами fsm_advance.py:760/1038 |
| 2 | CR-1 runner.py | R4 — ядро каждого шага; условия наступили; разбор внутри модуля не трогает 101 патч | подтверждено в главном, оспорено в деталях: блоков SKIPPED пять, не четыре; `sys.exit`/`return` неоднородны; `attempt` нужен после цикла; циклов импортов четыре (ещё doctor) |
| 3 | CR-3 fsm_advance.py | конфликт-магнит волны 5: 28 коммитов за неделю | подтверждено с уточнениями: нужен `gates/_base.py` для `GateRefusal`/`_run_gates` (иначе цикл); семь гейтов не были распределены — распределены; единственный патч через модуль не ломается |
| 4 | CR-4 canary.py | две несвязанные области, чистая граница (`_pool_dir`), без цикла | подтверждено с уточнениями: answer.py/prune.py — только комментарии; патчей в test_canary.py 126, имён пула ~20; три патча `canary.keychain` переписать обязательно |
| 5 | CR-5 R8 | закрывает класс утечки тестов и копии setUp; только tests/ | подтверждено с уточнениями: без WORKTREES три подмножества, у git_fixation — регрессия d692f2a6 (довод за отдельный фикс); групп setUp 26; одноимённые помощники с разными сигнатурами — не дубли |

## ТЗ-черновики класса «рефакторинг» (правила T015; для `new "..." --tz`)

Общая рамка. Поведение не меняется — поверхности: вывод команд пульта (stdout/stderr, коды выхода), тексты
и порядок записей журнала, алерты, схема БД, имена и пути файлов на диске и в артефактной ветке; зелёность
полного набора tests/ (2329 + 477) = неизменность. Тесты: ассерты не меняются — только импорты и пути патчей
(ревьюер сверяет по диффу); test_invariants.py не трогать. Никаких попутных улучшений; дедупликация — только
побайтно идентичных кусков. PLAN: таблица переносов, откат revert'ом одного merge, смоук до/после на живых
данных (`status`, `report`, `doctor` без `--fix`). Зоны — каждый файл, который задача правит или создаёт.

**Р-1. checkpoint.py — общий WIP-чекпоинт и фазы переноса артефактов (R7-остаток).** $35. Зоны:
orchestrator/checkpoint.py, tests/test_timeout_checkpoint.py, tests/test_checkpoint_external_step_artifacts.py,
tests/test_pause_now.py, tests/test_step_autocommit.py, tests/test_checkpoint_zone_filter.py (правки тестов
ожидаются нулевые). Содержание: (1) `_wip_checkpoint(conn, task_id, role, message, action, discard_action,
discard_detail, timeout)` для трёх одинаковых тел (:159–184, :319–342, :375–398); три публичных имени
остаются (test_pause_now.py:61 патчит `commit_pause_now_checkpoint`); (2) `_commit_external_step_artifacts`
— пять фаз приватными функциями с явными аргументами (`files`, `existing`, `baseline_sha`,
`own_commit_marker`, строка задачи); сигнатура, строка возврата, ранние `return ""`, порядок журнала —
дословно; докстринг переносится к фазам. Не трогать: фильтр посторонних файлов, конфликт-гвард, критерий
удаления. Порядок: первая, зависимостей нет.

**Р-2. runner.py — фазы шага роли внутри модуля (R4).** $45. Зоны: orchestrator/runner.py (новый модуль не
создаётся — 101 патч по именам `runner.*` остаётся в силе). Содержание: `run_agent_once` → `_prepare_step`
(пять исходов SKIPPED с прежними текстами), `_spawn_and_wait` (открытие промпта, `spawn_agent`, pump,
таймаут, kill группы; возвращает proc/pump/rc/timed_out/killed_group), `_account_step` (friction, `spend.*`,
`budget.check_program_spend`), исходы `_finish_timeout` / `_finish_failed` / `_finish_missing_artifact` /
`_finish_ok`; `_run_developer_step` → `_refuse_before_start` (`sys.exit` и `return` как есть, помощник
возвращает признак), `_build_prompt`, `_run_attempts` (возвращает `attempt, reason, failure_class`),
`_escalate_after_attempts`. Имена `run_agent_once`, `spawn_agent`, `role_env`, `role_cwd`, `role_cmd`,
`cmd_run`, `_cmd_run`, `step_role`, `wave_breaker_alerts_open` остаются глобалами модуля (их патчат тесты).
Не трогать: `finally` с `zone_lock.release_claim`, тексты, коды исхода, циклы импортов. Порядок:
параллельно Р-1 (зоны не пересекаются); тихое окно без живых задач в in_dev.

**Р-3. fsm_advance.py → пакет orchestrator/gates/.** $45. Зоны (создаёт): orchestrator/gates/__init__.py,
orchestrator/gates/_base.py, orchestrator/gates/zones.py, orchestrator/gates/capacity.py,
orchestrator/gates/review.py, orchestrator/gates/acceptance.py, orchestrator/gates/tests_writing.py;
(правит): orchestrator/fsm_advance.py, docs/codebase-map.md (регенерация), tests/test_zones_gate.py,
tests/test_capacity_gate.py, tests/test_mutation_claim_gate.py, tests/test_fsm_review_rework_gate.py,
tests/test_fsm_review_rework_sha_gate.py, tests/test_protected_paths_gate.py,
tests/test_fsm_advance_gate_framework.py, tests/test_fsm_advance_gate_smoke.py,
tests/test_review_registry_gate.py (только импорты/пути). Содержание: перенос дословно по семействам из
CR-3; `_base.py` — `GateRefusal`, `_run_gates`; в fsm_advance.py — обработчики состояний, эффекты
вердиктов и алиасы старых имён (answer.py:31 не правится и в зонах нет); литералы префиксов :760 и :1038 —
как есть. Не трогать: логику гейтов, обход `_run_gates` у приёмки, тексты отказов. Порядок: после Р-1 и Р-2,
тихое окно (магнит); ёмкость диффа: ~1100 строк ≈ 60 КБ < 256 КиБ.

**Р-4. canary.py — вынос запечатанного пула.** $35. Зоны (создаёт): orchestrator/pool_seal.py (или иное
незанятое имя); (правит): orchestrator/canary.py, orchestrator/catalog.py (:46–50), orchestrator/artel.py
(:705), orchestrator/doctor/__init__.py (:96), orchestrator/doctor/cli.py (:98),
orchestrator/doctor/canary_pool.py (:61), docs/codebase-map.md, tests/test_canary.py,
tests/test_doctor_canary_pool.py (импорты и пути патчей, включая три `canary.keychain`). Содержание:
функции :181–462 дословно; `_pool_dir` живёт в новом модуле и импортируется canary.py; из canary.py уходят
`hashlib`, `hmac`, `struct`, `uuid`, `keychain`; докстринг :48–55 — ссылки на место; `_run_one_task` —
три фазы внутри canary.py. Не трогать: HMAC/openssl, авторизацию пула, рубеж роли. Порядок: независимо от
Р-1…Р-3 (зоны не пересекаются).

**Р-5. tests/ — общая песочница (R8).** $25. Предусловие: задача-фикс CR-2026-09-12-1 смержена ($15:
WORKTREES в tests/test_git_fixation.py:159 и сверка остальных подмножеств; критерий — полный прогон не
создаёт каталогов в `.artel/worktrees`, замер до: 54). Зоны: tests/sandbox.py, tests/test_git_fixation.py,
tests/test_multitarget_invariants.py, tests/test_multitarget.py, tests/test_acceptance_tests_flow.py,
tests/test_agent_failure.py, tests/test_agent_log.py, tests/test_analyst_role.py,
tests/test_catalog_new_race.py, tests/test_doctor.py, tests/test_step_cost.py,
tests/test_mutation_claim_gate.py, tests/test_protected_paths_gate.py, tests/test_merge_lock.py,
tests/test_fsm_map_regen.py, tests/test_canary.py, tests/test_answer_branch_reads.py, tests/test_pull.py,
tests/test_doctor_artifact_branch_sync.py, tests/test_artifact_branch_push.py,
tests/test_doctor_fix_ignored_artifacts.py, tests/test_gitcmd_check_ignore.py,
tests/test_fsm_branch_correct_status_reads.py. Содержание: побайтно одинаковые setUp/помощники — в базовые
классы sandbox.py; подмножества `PATCHED_ATTRS` — обоснованные остаются с комментарием, необоснованные —
`TmpRootTest` целиком; ассерты не меняются; test_invariants.py и `tasks/*/acceptance_tests/_sandbox.py` —
вне задачи. Порядок: последняя, после Р-1…Р-4.

**Р-6 (опционально). auto.py — `_pre_advance_step` тремя функциями.** $25; зоны orchestrator/auto.py,
tests/test_auto_cycle.py, tests/test_watch.py; после Р-2. **Р-7 (опционально). review.py — `review_package`
по частям пакета.** $25; зоны orchestrator/review.py, tests/test_review_package.py; независимо.
Итог: ядро $185 (Р-1…Р-5) + фикс утечки $15; с Р-6/Р-7 — $235. Порядок: Р-1 ∥ Р-2 ∥ Р-4 → Р-3 (тихое окно)
→ Р-5; фикс утечки — до Р-5, можно первым.

## Не влезло (приоритет следующей ревизии)

- Нагрузочный замер `doctor` (по мандату не запускался; `status` 0.23 с); CLI-принты тестов в stdout
  (CR-2026-08-26-9, xdist глушит вывод); ревизия scripts/guard.py как отдельного объекта — вне фазы R.

# Приложения (вне капа)

## Направление 0 — судьба находок ревизии 12.09

| Якорь | Вердикт | Факт |
|---|---|---|
| CR-2026-09-12-1 тесты текут в пульт | живо | 54 каталога за каждый из двух прогонов 13.09; перезапись карты не повторилась; фикс — предусловие Р-5 |
| CR-2026-09-12-2 стоп-лосс 186 %, 126 алертов | живо | $5575.84; 126 открытых; ADR-0010 без дополнения; роадмап §5 — срез 06.09 |
| CR-2026-09-12-3 рабочие файлы и .pyc в main | исполнено | коммит 24433161: 18 файлов сняты, .gitignore `/_*`; `git ls-files \| grep -E '^_\|\.pyc$'` пуст |
| CR-2026-09-12-4 три копии регенерации карты | живо | brief.py:277, fsm_postmerge.py:89, pull.py:147 — голый `python3` |
| CR-2026-09-12-5 рост оркестратора, R4/R7/R8 | живо → этот отчёт | ТЗ Р-1…Р-7 с замерами; рост с 12.09 нулевой |
| CR-2026-09-12-6 неиспользуемые параметры 23 | живо | тот же список |
| CR-2026-09-12-7 retention не исполняется | живо | logs 3843 файлов / 167 МБ; prune не вызывался |
| CR-2026-09-12-8 steps без индекса | живо | индексов нет; 2.89 мс на 232 строках |
| CR-2026-09-12-9 журнал волн 3–4 | закрыто отчётом (данные) | продолжение — CR-2026-09-13-11 |
| CR-2026-09-12-10 роадмап и бэклог отстали | живо | roadmap:38 «R5 в работе»; таблица вердиктов 12.09 не применена (строки на месте) |
| CR-2026-09-12-11 дрейф скилов | живо | test-authoring.md:20, gates.yaml:19 без изменений |

## Направление 10 — актуализация docs/backlog.md (24433161) и удержанных строк

Таблица 12.09 (110 строк) не применена — все её вердикты в силе без изменений; ниже только 13 строк,
добавленных 12–13.09, и строки, чей статус изменился за сутки. Применяет Оператор изолированным
коммитом. notes-pending на 13.09 пуст (проверено).

| Строка | Вердикт | Что сделать |
|---|---|---|
| Копилка 13.09 «Цикл merge_gate 01M2B6K3EM висел 20+ минут (push + pull_request)» | дубль (класс = копилка 06.09 «CI дважды») | слить в одну строку П2 с фактурой обеих; кандидат — CR-2026-09-13-13 |
| Копилка 12.09 «reviewer не смог удалить guard_probe.py: rm нет в PATH» | дубль (= 06.09 «PATH роли затеняет инструменты», вердикт 12.09) | слить; roles.yaml деклараций инструментов не несёт — уточнить носитель (stack.REQUIRED_TOOLS: git, gh, claude) |
| Копилка 12.09 «zones-extend требует шага разработчика» | живо | кандидат: `zones-extend` дописывает раздел «## Расширение зон» сам |
| Копилка 12.09 «Роль гоняет планку сама в среде ≠ гейт», «Планка читает артефакты с диска» | дубль (одна механика; вердикт 12.09) | слить в строку П2 «команда `plank <id>`» |
| Копилка 12.09 «amend-tests расходится с гейтом tests_writing по источнику пометок» | живо | П2, задача после волны |
| Копилка 12.09 «В main отслеживаются .pyc старой планки» | закрыто | 24433161; снять |
| Копилка 12.09 «Старые планки в tasks/ текут в рабочее дерево» | живо | остаток — уборка старых планок из main (очередь п. 6) |
| Бэклог «Триггер №22 считает пульт, не память Оператора» | живо | задача doctor/report ($10); эта ревизия — по счёту Оператора |
| Бэклог «Зоны сверяет пульт: new --tz и spec_gate отказывают по неклассифицированному пути» | живо, П1 | не пересекается зонами с Р-1…Р-5 (кроме docs/codebase-map.md) — можно до фазы R |
| Очередь «Правка skills/code-revision.md по ревизии скила» | закрыто | 9fabc281; снять |
| Очередь «ADR: песочница шага роли» | живо | решение Оператора |
| Очередь «Граница волны 4» | условие наступило, исполнено на 2/3 | остаток: снять хук .claude/hooks/guard-artel-bg.py и строку settings.json:16; затем pin-update по зелёной канарейке (CR-12) |
| Копилка 12.09 «Нет команды note --hold» | закрыто (01M2B6JS2B done; вердикт 12.09) | снять; команда недоступна на пине до pin-update |
| Копилка 12.09 «Тест зависит от порядка прогона (test_acceptance_tests_flow…)» | живо, сузить | два прогона с `-n 4`/`-n 2` на 24433161 совпали; оставить до воспроизведения с указанием seed/порядка |
| Бэклог «Ревизия №5 и R2–R8» | условие наступило | заменить на ссылку: ТЗ Р-1…Р-7 этого отчёта; заводить в порядке Р-1 ∥ Р-2 ∥ Р-4 → Р-3 → Р-5 |

## Направление 11 — обходные сценарии сессий Оператора (новое за сутки + статус прежних)

| Обход | Что обходит | Применений (источник) | Команда/режим, который снимает | Задача |
|---|---|---|---|---|
| `gh run cancel` + `gh run rerun` застрявшего прогона pull_request | ожидание всех проверок коммита без различения дубля по событию | 1 (копилка 13.09) | CR-2026-09-13-13 (б): зелёный прогон того же workflow на sha засчитывается; (а) печать застрявшего прогона | нет |
| Двухшаговый pin-update при ровно 10 мержах (канарейка на целевом sha → pin-update) | ничего не обходит: проектное поведение ADR-0013, `возраст < N` (CR-10) | 1 (13.09) | — (текст отказа уточнить: «меньше N мержей») | нет (правка текста Оператором) |
| `hold_note.py` — JSON в notes-pending руками | удержание строк копилки во время циклов | flush 13.09 (13 строк) | `note --flush` (01M2B6JS2B) — смержена, но не в пине 27ddceb3 | pin-update |
| Ревизия в отдельной рабочей копии `git worktree add --detach … origin/main` | главная копия на пине отстаёт от origin/main | 2 (12.09, 13.09) | штатно по скилу (раздел «Объект и среда», 9fabc281) | — |
| Уборка мусора полного прогона (`rm -rf .artel` копии ревизии) | утечка тестов в `.artel/worktrees` (CR-2026-09-12-1) | 2 (13.09, после каждого прогона) | фикс CR-2026-09-12-1 (предусловие Р-5) | нет — заводить |
| Прежние 12 сценариев таблицы 12.09 | — | без новых применений за сутки (журнал до 12.09 21:08Z; scratchpad сессий без новых файлов после 12.09 20:00) | вердикты 12.09 в силе | — |

## Строка индекса docs/audits/README.md

| 13.09 | skills/code-revision.md | code-revision-2026-09-13.md | ревизия кодовой базы (шестая; актуализация замечаний для фазы R по редакции скила 9fabc281): 12 направлений (0–11), два полных прогона с разным `-n`, AST-замеры на 24433161, второе мнение субагентов по каждой ★ | 13 находок (5★ — все ТЗ-черновики фазы R: Р-1 checkpoint $35, Р-2 runner $45, Р-3 fsm_advance → gates/ $45, Р-4 canary пул $35, Р-5 песочницы R8 $25; ядро $185 + фикс утечки $15); направление 0: 1 исполнено, 9 живо; pin-update при 10 мержах — не дефект (ANSWER-1 п.3); решения Оператора — ниже по мере разноса |
