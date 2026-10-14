---
task: 01M4XVM49PP5WHSXT5S8JW85WN
type: spec_audit
author_role: spec_auditor
status: ready
verdict: fail
signals: б) мандат в ANSWER: Ослабление тестов разрешено: tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::ReadonlyDbOutcomeTest::test_ac4_readonly_db_run_reaches_same_outcome_and_report, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::JournalRedeliveryTest::test_ac5_pult_process_delivers_journal_record, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::SharedLockTest::test_ac6_role_suite_run_and_gate_share_one_lock_file, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::LimitUnchangedTest::test_ac8_readonly_db_run_keeps_profile_limit_and_timeout_outcome, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::LogPlacementTest::test_ac9_suite_run_logs_live_under_suite_run_dir; в) пути-признаки (тесты): tests/, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py, tests/test_01m4xvm49pp5whsxt5s8jw85wn_developer_suite.py, tests/test_providers.py, tests/test_providers_codex.py, tests/test_suite_context.py; в) пути-признаки (песочница ролей): docs/reference/role-home/claude/settings.json, docs/reference/role-home/codex/config.toml, orchestrator/providers/claude.py, orchestrator/providers/codex.py, orchestrator/runner.py; в) SPEC требует приложения PLAN; г) budget_usd 45 ≥ 45
spec_sha: 4a08c32089ebd79a1fc35f620cc5983340c49254
schema_version: 5
---

# SPEC-AUDIT: Полный suite-run из шага developer

## ТЗ и SPEC

Полный независимый разбор версии 4a08c32089ebd79a1fc35f620cc5983340c49254. `git hash-object` файла SPEC дал этот SHA. Команда пульта `show` подтвердила задачу в `spec_audit`, заданную ветку и расход $25.09/$45. Кодовое дерево до проверки чистое. Обозначения `SPEC.md`, `TZ.md`, `ANSWER-n.md` ниже относятся к каталогу документов задачи, указанному в миссии, а не к отсутствующему tasks/ в worktree.

Требования ТЗ о воспроизведении, раннем отказе, сохранении разрешённых путей, точной роли, миссии и инвентаризации перенесены в SPEC.md:19–30 и AC-1–AC-19 (SPEC.md:34–70). Мандат пяти методов из ANSWER-1.md:17 сохранён адресно в SPEC.md:25 и :78–83; запрет менять helpers/общий ROLES не снят. Свойства отчётов, журнала, замка, предела и логов перечислены отдельными AC-9–AC-13.

Изменение прежнего разрешения при недостаточном контексте на UNKNOWN/refusal, добавление broker, provider-зон и исключения одного socket имеют основание в ANSWER-3.md:15–21. Поэтому отказ оператору при outage, новые платформенные адаптеры и четыре live-среды не являются самовольным расширением ТЗ. ANSWER-3 заменяет соответствующие прежние ограничения ANSWER-1/2; повторно требовать решения по UNKNOWN не нужно. Ограниченная проба ANSWER-2 и debug-успехи ANSWER-3 не выданы за выполненную приёмку: SPEC.md:29, :66, :149 прямо требуют настоящие маршруты.

Решение возврата с гейта о раздельных носителях failed/status/wait, full gates, timeout, lock, reuse и метриках выполнено в SPEC.md:88–107. Прежнее замечание к этим строкам не возобновляется. Новая объединённая строка конфигурационной матрицы SPEC.md:113 имеет отдельный дефект F3 ниже.

Оценка монолита и остатка есть в SPEC.md:126–132; потолок $45 сохранён. Приведённые $22.08 — прямо обозначенный исторический снимок до аналитического шага, а не ошибка относительно нынешних $25.09. Риск четырёх live-проверок в остатке бюджета раскрыт; это предмет гейта, не разрешение урезать проверки. Требование проверить CI main оставлено пульту/Оператору (SPEC.md:143), что соответствует роли аудитора.

Отклонения относятся к исполнимости заявленных зон и оформлению миграции тестов, а не к уже принятым продуктовым решениям: F1–F3 в вердикте.

## Факты против кода

- Публичный маршрут подтверждён: `orchestrator/artel.py:1877` разрешает suite-run процессам роли, :2007 вызывает `cmd_suite_run`. В `orchestrator/suite_run.py:729` вызывается `_db`, :734 — `deliver_journal`; :767 берётся замок, :774 создаётся лог, :781–788 удаляется ARTEL_ROLE и запускается отделённый фон. `_db` (:158) сначала использует обычное подключение, затем fallback только на чтение. Следовательно, проверки только перед Popen недостаточно для AC-2.
- `orchestrator/runner.py:74–92` создаёт отдельную сессию, :1553 запускает агента, :1581–1583 записывает agent pid как pgid в lease, :1602–1614 сохраняет timeout/kill. `in_role_environment` (:1051) узнаёт окружение роли, но не удостоверяет точную роль живого потомка. Нового `orchestrator/suite_context.py` в рабочем дереве ещё нет; SPEC корректно называет его новой зоной, а не существующей возможностью.
- `orchestrator/role_prompt.py:239–247` действительно предлагает developer новый full, что противоречит `skills/coding-standards.md:107–115`. Старый тест миссии `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py:1441–1444` проверяет полный путь команды и формы --wait/--failed, а не разрешение нового full. Его assertions совместимы с новой миссией без правки.
- Пять readonly_db-методов и их строки подтверждены. Однако их `role_process` (:217–222) моделирует ENV и readonly DB, а не регистрацию живого шага; `ROLES` (:60) включает developer/test_author/reviewer. Сохранение этих носителей не доказывает новый process/lease-контекст: он требует отдельных AC-2–AC-7/16–18, как и записано в SPEC.
- Базовый `SuiteRunSandbox` в `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py:193–231` копирует пульт в временный корень, а :313–339 запускает его CLI напрямую. Runner/lease/broker там не готовятся. Это существенная неполнота плана совместимости при обязательном broker, F2; одно сохранение имён/assertions не обеспечивает прежние разрешённые маршруты.
- Тела носителей full gate, timeout, reuse и метрик сверены: `orchestrator/acceptance.py:1761–1774`, `orchestrator/fsm_merge_gate.py:958–967`, `.github/workflows/ci.yml:239–245`; соответствующие методы приведены в матрице ниже. Они не вызывают публичный cmd_suite_run для своего основного гейтового прогона, поэтому запрет можно ограничить публичным входом.
- Codex: `orchestrator/providers/codex.py:121–144` содержит 11 выключенных функций и network_access=false; `orchestrator/doctor/isolation.py:208–219` проверяет реальные аргументы команды. У `tests/test_providers_codex.py:322–323` запрет действительно распространяется на ЛЮБОЙ true в файле. Политика паритета :265/:342 и smoke :1011 совпадают с описанием SPEC. Планируемая смена представления не получает автоматически мандат гейта, F1.
- Claude: `docs/reference/role-home/claude/settings.json:1–15` содержит permissions.deny, но не явную сетевую sandbox-политику. `orchestrator/providers/claude.py:122–177` собирает CLI-ограничения инструментов/настроек/MCP. Эти файлы сами по себе не доказывают эффективные TCP/UDP/IPv6/Unix/process отказы. SPEC требует живое доказательство AC-17; считать описание запретов фактом всех четырёх сред до него нельзя.
- Инвентаризация `rg -l 'suite-run|suite_run' orchestrator tests skills templates docs/reference` дала 42 файла; каждый назван в SPEC полностью или именем в списке tests. В templates/ и docs/reference/ текстовых совпадений suite-run/suite_run нет. Совпадения в provider/configuration-файлах дополнены отдельно, как указано в SPEC.
- `config.PROTECTED_PATHS` (:754–760) и `SPLIT_SIGNAL_BUDGET_USD = 60` (:587) сверены. Вопрос рассинхронизации порога шаблона уже записан аналитиком; аудит не меняет ни шаблон, ни бюджет. ADR-0024/0025 доступны в локальном main, их относящиеся к контексту ограничения прочитаны; приоритет последующего ANSWER-3 учтён.

Динамический full и live capability-пробы аудитор не запускал. Проверка фактов — чтение кода, AST и документов; она не является подтверждением будущей реализуемости IPC.

## Проверяемость критериев

Критерии содержат наблюдаемые исходы. «Да» означает возможность содержательного теста, а не наличие уже написанной/прошедшей новой планки. Для live AC нужны фактические четыре среды, для старых положительных сценариев сначала надо устранить F2. Воспроизведение AC-1 относится к исходной версии и фиксируется отдельно от зелёного поведения исправленной версии.

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | Да, baseline с перехватом процесса | Проверка ошибочно обходит публичный cmd_suite_run и вызывает background напрямую: перехват публичного запуска не сработает; исходное удаление ARTEL_ROLE и full-mode должны наблюдаться без запуска полного tests/. |
| AC-2 | Да | Отказ перенесён после `_db`, deliver_journal, создания лога либо lock; наблюдатели вызовов/записей ловят эффект даже при последующей уборке файла. Убрана подсказка разрешённых команд — проверка сообщения красная. |
| AC-3 | Да, включая live | Классификация по ENV, CLI-имени, целевой задаче либо одному PGID вместо ancestry: очищенное окружение, другая задача или setsid позволяют full и ломают ожидаемый отказ. |
| AC-4 | Да | Ошибка connect/version/proxy преобразована в «внешний оператор»; новый full стартует. Обратная мутация — инфраструктурный отказ перенесён перед status/wait/failed, и разрешённые команды ломаются. |
| AC-5 | Да, после подготовки разрешённого контекста F2 | Любой in_dev target/HOME роли блокируется; либо разрешённый фон повторно проверяется как developer и база не выполняется; либо ARTEL_ROLE доходит до pytest. |
| AC-6 | Да | `--failed` передаёт tests вместо прежних nodeid, запускает базу, заменяет отсутствующий список full либо блокируется при outage. |
| AC-7 | Да | Обычный status создаёт второй процесс; wait запускает первый, убивает идущий по сроку, возвращает успех при исчерпании или снимает предел 9 минут. |
| AC-8 | Да | В миссии оставлено предложение нового full или потеряны полный путь/--wait/--failed/планка/адресные тесты. Старые три assertions сохраняются. |
| AC-9 | Да | Ошибка readonly journal превращает зелёный итог в красный, выбрасывает исключение либо меняет код красного отчёта. |
| AC-10 | Да | Отложенная запись теряется, не досылается штатным пультом; либо новый запрет developer сам досылает очередь. |
| AC-11 | Да | Роль и гейт используют разные lock paths; не проверяется одно из направлений; developer достигает lock до отказа. |
| AC-12 | Да | Предел профиля заменён дефолтом/увеличен, потерян источник; превышение прежних 3 секунд даёт иной текст/код. |
| AC-13 | Да | Основной или базовый лог пишется вне suite-run, отчёт содержит несуществующий путь; отказ developer создаёт файл. |
| AC-14 | Да | Запрет помещён в acceptance.full_suite; timeout/метрика исчезли; reuse ключ заменён HEAD, игнорирует команду/возраст или принимает незавершённый результат. |
| AC-15 | Да, структурная сверка и поведенческие тесты | Developer просто исключён из общего ROLES; изменён helper/удалён метод; сохранение отчёта заявлено без достижимого положительного маршрута. Для последнего уже найден F2. |
| AC-16 | Да | Кэш старого разрешения действует после смены lease, PID reuse принят за тот же процесс, чужой endpoint или self-claimed PID принимается без kernel peer. |
| AC-17 | Да, только live 2×2 | Применяется debug policy или разрешены соседний socket/TCP/UDP/IPv6/domain/process; одна среда подменена моковым CLI. PLAN без фактического случая не выполняет AC. |
| AC-18 | Да | recv без срока/лимита, бесконечная ancestry, усечённый ответ принимается; регистрация/endpoint переживают success/error/timeout либо уборка убивает разрешённый фон. |
| AC-19 | Да, с уточнениями F1/F3 | Убран отдельный feature=false, parity проверяет копию вместо argv, doctor пропускает потерю фильтрации, socket-допуск расширяет файловые/сетевые права. Миграция самих assertions дополнительно проверяется машинным гейтом. |

## Зоны

Основные продуктовые узлы перечислены явно: suite_run, runner, role_prompt, новый suite_context с macOS/Linux, оба provider, doctor/isolation и два референса (SPEC.md:116–122). Это соответствует добавлениям ANSWER-3; изменение песочницы не скрыто. Общая генерируемая карта названа отдельно. Миграция БД, общий демон, FSM, общий OS perimeter не заказаны.

Ни один из 14 путей zones сам по себе не совпадает с `config.PROTECTED_PATHS` (:754–760). Skills, templates, ADR, CI и conftest защищены; SPEC.md:124, :140 допускает нужные согласования только приложением PLAN. Требование сохранить сторож в приложении и применимость патча не разрешает править эти пути в worktree. Живой дом роли отдельно исключён из правки SPEC.md:120.

Однако test zones неполны для нового fail-closed: SPEC.md:122 перечисляет пять методов readonly_db, планку, новый test_suite_context и provider-тесты, а :124 оставляет остальные носители только для чтения. Положительные старые subprocess-фикстуры suite-run не имеют обязательного доверенного канала и не получают разрешённой зоны его подготовки (F2). Зона provider-файла также не равна разрешению поменять его старое утверждение (F1).

## Матрица неослабления

Адресные сокращения ниже: S = `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`; R = `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`; U = `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py`; C = `tests/test_providers_codex.py`; P = `tests/test_providers.py`. Число после сокращения — строка этого файла. Эти обозначения не расширяют зоны или мандаты. Для новых тестов строки ещё не существуют: указан AC и предусмотренный SPEC носитель (планка developer_suite либо test_suite_context), без выдуманных адресов.

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Новый full developer | R:303,341,407,435,473 разрешают сценарий роли | Нет, ранний отказ | AC-1/2, новая планка developer_suite | Только пять методов ANSWER-1; отдельные отрицательные проверки обязательны |
| Green при readonly DB | R:329–332 | Да | R::ReadonlyDbOutcomeTest::test_ac4_readonly_db_run_reaches_same_outcome_and_report:303, AC-9 | Сохранить код/отчёт, подготовить разрешённый контекст |
| Red при readonly DB | R:329,334–336 | Да | Тот же метод R:303, AC-9 | Сохранить отсутствие исключения и код 1 |
| Deferred journal | R::JournalRedeliveryTest::test_ac5_pult_process_delivers_journal_record:341 | Да | Тот же метод, AC-10; новый отказ AC-2 | Не создавать/досылать запись запрещённым вызовом |
| Гейт держит замок | R::SharedLockTest::gate_holds_role_refused:377 | Да | R::SharedLockTest::test_ac6_role_suite_run_and_gate_share_one_lock_file:407, AC-11 | Прежний id держателя и отсутствие запуска; helper не открыт |
| Suite-run держит замок | R::SharedLockTest::role_holds_gate_waits:395 | Да | Тот же метод R:407, AC-11 | Прежний NOT_STARTED и отсутствие pytest; helper не открыт |
| Предел профиля и источник, ветка/база | R:450–459 | Да | R::LimitUnchangedTest::test_ac8_readonly_db_run_keeps_profile_limit_and_timeout_outcome:435, AC-12 | Не поднимать предел и не заменять дефолтом |
| Timeout 3 секунды | R:461–468 | Да | Тот же метод R:435, AC-12 | Сохранить текст, источник, код 1 |
| Логи ветки и базы | R::LogPlacementTest::test_ac9_suite_run_logs_live_under_suite_run_dir:473 | Да | Тот же метод, AC-13; отсутствие файлов AC-2 | Все пути внутри suite-run и существуют |
| Точная роль вместо ENV/HOME | runner.py:74,1583; R:217 лишь моделирует ENV | Усиливается | AC-3/16, новые developer_suite/test_suite_context; AC-17 live | Не считать старый ENV-тест удостоверением |
| UNKNOWN/outage | suite_run.py:726 до изменения не требует broker | Нет, отказ нового full | AC-2/4/16/18 | Прямое решение ANSWER-3; без fallback |
| Полный внешний/иной-role запуск | S::RoleEnvironmentTest::test_ac22_role_process_is_not_refused:579 | Да при доказанном контексте | S:579 и AC-5 | F2: без подготовки broker прежняя фикстура не представляет разрешённый маршрут |
| Отсутствие ARTEL_ROLE у разрешённого фона | S::RoleEnvironmentTest::test_ac5_runs_have_no_artel_role_in_environment:549 | Да | Тот же метод, AC-5 | Очистка после первичного решения; ветка и база |
| Точный перечень --failed | S::FailedRerunTest::test_ac19_failed_reruns_exactly_last_failures:1147 | Да | S:1147, AC-6 | Без full/base и без --lf; обновлять перечень |
| --failed без прошлого списка | S::FailedRerunTest::test_ac20_failed_without_previous_run_is_refused:1212 | Да | S:1212, AC-6 | Отказ без запуска |
| --failed с пустым списком | suite_run.py:753–756 | Да | AC-6: отдельный исход отсутствия упавших | Ок при выполнении новой проверки; не подменять full |
| Status идущего | S::BackgroundTest::test_ac7_second_launch_reports_running_run:650 | Да | S:650, AC-7 | Тот же лог, один запуск, без изменения прогона |
| Wait завершения/исчерпания | S::BackgroundTest::test_ac8_wait_reports_finished_or_still_running:674 | Да | S:674, AC-7 | Процесс жив после срока, правильный отчёт/код |
| Wait без прогона | S::BackgroundTest::test_ac9_wait_without_any_run_is_refused:723 | Да | S:723, AC-7 | Не начинать full |
| Предел wait | S::BackgroundTest::test_ac10_wait_above_limit_is_refused_without_waiting:744 | Да | S:744, AC-7 | 9 минут, без прерывания прогона |
| Доступ failed/status/wait при outage | Новая граница broker; старые ветки suite_run.py:735–763 | Да | AC-4/6/7, новая планка developer_suite | Проверять каждый режим при сбое, а не только full refusal |
| Планка/адресные тесты | skills/coding-standards.md:107–118; artel.py:2005 | Да | AC-6 и неизменный plank-run | Не переносить запрет в общий запуск тестов |
| Полный гейт | acceptance.py:1761–1774, fsm_merge_gate.py:958–967 | Да | tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged:332, AC-14 | Команда tests с xdist сохраняется, контекстный запрет не в этом узле |
| Полный CI | .github/workflows/ci.yml:239–245 | Да | Тот же CI-шаг; AC-14 | Не менять состав/120-секундный per-test timeout; F2 касается работоспособности старых сценариев внутри набора |
| Timeout полного гейта | tests/test_full_suite_profile_timeout.py:76–92 | Да | FullSuiteProfileTimeoutTest::test_gate_runner_uses_profile_limit_and_names_source:76 того же файла | 1500, FULL_SUITE_TIMEOUT и источник сохраняются |
| Reuse равного дерева | U::SuiteReuseTest::test_ac4_same_uncommitted_tree_in_scratch_reuses_green_result:48 | Да | Тот же метод, AC-14 | Не запускать повторно равное дерево |
| Изменение дерева | U::SuiteReuseTest::test_ac5_tracked_change_invalidates_result:33 | Да | Тот же метод, AC-14 | Не использовать только HEAD |
| Изменение команды | U::SuiteReuseTest::test_ac6_command_change_invalidates_result:68 | Да | Тот же метод, AC-14 | Команда входит в ключ |
| Возраст reuse | U::SuiteReuseTest::test_ac7_age_boundary:84 | Да | Тот же метод, AC-14 | Обе стороны границы возраста |
| Незавершённый итог | U::SuiteReuseTest::test_ac8_incomplete_runs_are_not_reused:101 | Да | Тот же метод, AC-14 | Timeout/NOT_STARTED/no tests/no summary непригодны |
| Timeout гейта не подменяет базу | S::BaseTimeoutTest::test_ac16_timed_out_gate_run_saves_nothing:1001 | Да | Тот же метод, AC-14 | Сохранить отдельный прогон базы; подготовка full также затронута F2 |
| Метрики green/red/timeout | tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py:139 | Да | SuiteObservationTest::test_ac1_gate_writes_each_outcome_with_metrics:139 того же файла | Прежние поля и одна запись на исход |
| Сигнал близости предела | tests/test_suite_near_limit.py:63 | Да | FailedRerunTest::test_failed_rerun_gives_no_signal_full_run_does:63 того же файла | Различать full и failed |
| Миссия developer | role_prompt.py:239–247 | Меняется совет, команды сохраняются | S::MissionTest::test_ac25_developer_mission_names_suite_run_with_pult_path:1413 плюс AC-8 | Старые assertions совместимы без правки |
| Единственный socket | codex.py:143–144, config.toml:71 запрещают сеть | Только это исключение | AC-17/19, live 2×2 и test_suite_context | ANSWER-3 по существу разрешает, F1 — оформление assertions |
| Прямой TCP | Сетевая политика Codex, эффективный исход до live не доказан для всех сред | Запрет обязателен | AC-17 отдельный TCP denied | Не засчитывать proxy403 вместо прямого connect |
| UDP | То же ограничение, не доказано debug-пробой ANSWER-3 | Запрет обязателен | AC-17 отдельный UDP denied | Не выводить из TCP |
| IPv6 | То же ограничение | Запрет обязателен | AC-17 отдельный IPv6 denied | Не выводить из IPv4 |
| Соседний Unix socket | Полный прежний запрет IPC в проверенной Codex-среде | Да | AC-17 отдельный sibling denied | Не разрешать весь каталог |
| Внешние domains | Требование ANSWER-3.md:17 | Запрет обязателен | AC-17 отдельный domain denied | Не подменять только конфигом domains={} |
| Process/ps | Ограничения настоящей среды, не доказательство ENV | Да | AC-17 отдельные реальные проверки | Не переносить чтение ancestry внутрь роли |
| Паритет argv/reference | C::StepCommandTest::test_overrides_repeat_the_curated_config_pair_for_pair:265; C::CuratedHomeTest::test_curated_config_repeats_the_command_overrides_pair_for_pair:342 | Да | Те же носители, AC-19 | Любое изменение assertions требует легального маршрута F1 |
| 11 disabled features | C::StepCommandTest::test_every_disabled_feature_of_the_curated_home_is_in_the_command:208; C::CuratedHomeTest::test_every_disabled_feature_is_false_in_the_curated_config:307 | Да | Те же feature assertions, AC-19 | Не выключать метод целиком |
| Общий запрет любого true | C:322–323 | Может меняться только адресно | AC-19 требует замену свойства, но машинный мандат отсутствует | F1: до оформления не считать правку разрешённой гейтом |
| Doctor ловит утрату защиты | doctor/isolation.py:208–219; C::IsolationSmokeTest::test_green_on_the_regular_command_and_red_on_each_missing_piece:1011 | Да | Тот же smoke и AC-19 (версия/фильтрация) | Удержать независимые повреждения sandbox/network/feature |
| HOME/CODEX_HOME | C::EnvironmentTest::test_home_and_codex_home_overwrite_ambient_values:385; C::IsolationSmokeTest::test_inherited_ambient_home_is_red:1111 | Да | Те же методы, AC-19 | SPEC:113 следует назвать их адресно (F3) |
| Секреты и отсутствие лишнего keychain | C::EnvironmentTest::test_environment_is_only_the_role_home_and_never_asks_the_keychain:401; test_no_api_key_name_reaches_the_step_whatever_the_ambient_value:421 | Да | Те же методы; C::IsolationSmokeTest::test_any_api_key_name_in_the_step_env_is_a_named_failure:1053, AC-19 | Не добавлять доставку endpoint ценой секретов или скрытого изменения состава ENV; F3 |
| MCP/config injection | C::CuratedHomeTest::test_config_toml_carries_no_model_and_no_mcp_server:291; P::StepCommandTest::test_role_cmd_matches_the_pre_task_argv:199 | Да | Те же методы, AC-19 | Сохранить strict-mcp-config/setting-sources; перечислить в SPEC, F3 |
| Approvals | codex.py:145–146; claude.py:158 | Да | C:265,342 держат паритет, P:199 — старый argv; AC-19 требует сохранить политику | Паритет сам по себе не доказывает безопасное значение при синхронной правке двух сторон; адресная проверка значения в матрице SPEC не названа, F3 |
| Файловая изоляция | C::StepCommandTest::test_argv_carries_the_resolved_tool_model_sandbox_and_stdin_prompt:193; C:1011 | Да | Те же носители режима и AC-19 | Наличие workspace-write не равно проверке всех эффективных файловых прав; F3 требует назвать сохранённые свойства и покрытие |
| Lease/start identity, teardown, bounded IPC | runner.py:1581–1614 сохраняет нынешние spawn/kill; нового broker нет | Усиливается без ослабления lifecycle | AC-16/18, test_suite_context; AC-17 live | PID reuse/чужой endpoint/старый ответ/истёкший lease не разрешают full |
| Бюджет и гейты | SPEC.md:8 — 45; обычная последовательность пульта | Да | Бюджетный гейт, AC-17 и штатные SPEC/tests/review/acceptance/merge | Нехватка среды/денег не разрешает skip, увеличение лимита или обход |

Раздела «Меняемое поведение» в SPEC нет. Для пяти методов это корректно: ANSWER-1 разрешает изменение области сценария, а не скалярные пары было/стало. Для миграции `assertEqual([…], [])` с новым фильтром такой раздел тоже не подходит: меняется форма выражения, а ожидаемый контейнер `[]` не является допустимой скалярной парой. Отсутствие недопустимых строк «Меняемого поведения» не закрывает F1.

## Пути обхода гейтов

1. **F1: принять прозу ANSWER-3 за машинный мандат.** Исполнитель может предметно заменить запрет любого true на исключение IPC и сослаться на SPEC.md:111. Но `_answer_mandate` в `orchestrator/advance_gates/test_integrity.py:867–891` читает только строки формального префикса. Проверка в памяти через `guard.assertion_changes` для замены фильтра `value == "true"` на `value == "true" and key != "network.enabled"` вернула «ослабление или иная смена». Это иллюстрация классификатора, не предложение production-конфига; файлы не менялись. У ANSWER-1 парсер нашёл пять readonly_db-элементов, у ANSWER-2/3 — ноль. Подмена `_toml_pairs`, чтобы он скрывал допустимый ключ и старый assert формально остался, обошла бы смысл проверки; она не является исправлением отсутствующего мандата.
2. **F2: сделать старые full-тесты зелёными через неаутентифицированный fallback.** В их изолированном пульте broker не подготовлен. Разрешать full при отсутствии socket/lease, на тестовом HOME/target или после снятия ENV нельзя: это нарушает AC-3/4 и открывает именно закрываемый маршрут. Автозапуск broker из отказавшего клиента также нарушает SPEC.md:20. Зависимость этих тестов от случайного внешнего broker или от порядка выполнения нового test_suite_context не является сохранением изолированных носителей. Нужна явная подготовка доверенного тестового контекста с разрешённой зоной, а не обход production-проверки.
3. **F3: отчитаться одной зелёной проверкой конфигурации за шесть свойств.** Ссылка на два файла в SPEC.md:113 допускает такой отчёт без указания, чем проверены HOME, секреты, MCP, approvals и файловые ограничения. Общий AC-19 перечисляет свойства, но не устраняет неоднозначность старых носителей/замен в матрице. Например, два синхронно изменённых approval значения пройдут parity; наличие workspace-write не доказывает отсутствие лишних writable paths.

Остальные рассмотренные обходы текстом SPEC закрыты: blanket deny всей suite-run ловится AC-5–7; проверка только ENV/PGID — AC-3/16; повторное использование старого разрешения — AC-16; один успешный debug connect вместо четырёх сред — AC-17; утрата timeout/lock/reuse/метрик — AC-11/12/14. Подмена live моками или skip обязательной среды прямо запрещены. Произвольный самостоятельный pytest вне прежнего сторожа исключён ТЗ и не объявляется новой находкой.

## Вердикт

**fail** — текущий SPEC нуждается в возврате аналитику до реализации. Статус **ready**: фактов достаточно для вердикта; запрос решения не нужен, чтобы признать описанные пробелы. Уже принятые UNKNOWN и один socket не оспариваются.

- **F1 — не оформлен машинный маршрут адресной миграции конфигурационных assertions.** SPEC.md:110–112, :122 и AC-19 (:70) разрешают замену представления socket-политики, в частности общего запрета true. ANSWER-3.md:17 даёт содержательное разрешение, но не строку мандата; единственная строка ANSWER-1.md:17 содержит пять других методов. `tests/test_providers_codex.py:322–323` и `orchestrator/advance_gates/test_integrity.py:889–891` подтверждают конфликт, AST-проба его воспроизводит. Устранение: либо сохранить эти assertions без изменения формы и скрывающих helpers, либо до кода оформить точные методы/свойства/замены штатным ANSWER. Вопрос полномочий разрешает Оператор; широкое исключение всего provider-файла не требуется и не обосновано.
- **F2 — обязательный broker не согласован с изолированными старыми full-фикстурами и их зонами.** SPEC.md:20–23, :42 и :88–107 требуют fail-closed и сохранение положительных носителей; SPEC.md:122–124 не даёт зоны подготовки этих носителей. `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py:193–231`, :313–339, :579–601 создают отдельную копию пульта и вызывают публичный CLI без runner/broker. В чистой среде такой сценарий не представляет доказанного внешнего клиента; по новому контракту он должен получить UNKNOWN. Та же фикстура нужна сохранённым status/wait/failed-тестам для их начального full. Устранение: явно определить подготовку доверенного контекста для старых положительных сценариев, инвентаризировать затронутые fixtures и включить необходимые точные test zones, сохранив assertions и изоляцию. Нельзя лечить это разрешением при отсутствии broker, зависимостью от порядка тестов или отключением проверок. Это разрыв спецификации, а не утверждение о уже наблюдённом падении ещё не написанной реализации.
- **F3 — новая конфигурационная часть матрицы не доведена до отдельных свойств и адресных носителей.** SPEC.md:113 объединяет HOME, секреты, MCP, approvals и файловую изоляцию, указывая только `tests/test_providers_codex.py` / `tests/test_providers.py` и «прежние носители». Это не выполняет правило строки на свойство `docs/operator-gates.md:65–76` и требования самой задачи к пятиколоночной матрице. Адресные примеры: C:385/401/421/291/193 и P:199 приведены выше; отдельно нужно обозначить, где эффективные approvals/файловые права подтверждены старым тестом, а где требуется проверка AC-19. Исправление не требует дублировать существующие тесты. Прежнее закрытое замечание к failed/status/wait/reuse не возобновляется.

Проверка артефакта: `python3 scripts/guard.py <каталог документов>/SPEC-AUDIT.md` — «GUARD: ок (1 файлов)», код 0. Повторный hash-object SPEC совпал с проверяемым SHA; `git status --short` пуст. SPEC, ТЗ и код не изменялись; полный tests/ и живые provider-пробы не запускались.

## Предложения системе

Класс «содержательный мандат есть, машинного префикса нет»: ANSWER-3.md:17 и SPEC.md:111 допускают адресную миграцию, которую `test_integrity._answer_mandate` не распознаёт. Полезна проверка согласованности при подготовке SPEC/ANSWER до developer: точный старый assertion, машинный маршрут его изменения и обязательное покрытие свойства. Обход гейта не предлагается.
