---
task: 01M4XVM49PP5WHSXT5S8JW85WN
type: spec_audit
author_role: spec_auditor
status: ready
verdict: pass
signals: б) мандат в ANSWER: Ослабление тестов разрешено: tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::ReadonlyDbOutcomeTest::test_ac4_readonly_db_run_reaches_same_outcome_and_report, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::JournalRedeliveryTest::test_ac5_pult_process_delivers_journal_record, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::SharedLockTest::test_ac6_role_suite_run_and_gate_share_one_lock_file, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::LimitUnchangedTest::test_ac8_readonly_db_run_keeps_profile_limit_and_timeout_outcome, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::LogPlacementTest::test_ac9_suite_run_logs_live_under_suite_run_dir / Ослабление тестов разрешено: tests/test_providers_codex.py::CuratedHomeTest::test_every_disabled_feature_is_false_in_the_curated_config; в) пути-признаки (тесты): tests/, tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py, tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py, tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py, tests/test_01m4xvm49pp5whsxt5s8jw85wn_developer_suite.py, tests/test_providers.py, tests/test_providers_codex.py, tests/test_suite_context.py, tests/test_suite_run.py; в) пути-признаки (песочница ролей): docs/reference/role-home/claude/settings.json, docs/reference/role-home/codex/config.toml, orchestrator/providers/claude.py, orchestrator/providers/codex.py, orchestrator/runner.py; в) SPEC требует приложения PLAN; г) budget_usd 45 ≥ 45
spec_sha: 731d61af4ba0c68494a7e3e85152666815cfb484
schema_version: 5
---

# SPEC-AUDIT: Полный suite-run из шага developer

## ТЗ и SPEC

Отклонений не обнаружено. Проверена именно версия `731d61af4ba0c68494a7e3e85152666815cfb484`, подтверждённая `git hash-object`. БД через `artel.py show` подтверждает состояние `spec_audit`, заданную ветку и расход $35.08/$45. Документы в ссылках далее относятся к каталогу документов задачи, код — к worktree. Полный разбор выполнен по всем разделам шаблона.

| Источник | Отражение в SPEC | Результат сверки |
|---|---|---|
| ТЗ, требование 1: воспроизведение и отказ до эффектов | Требования 1–2, AC-1/2, SPEC.md:19 | Сохранены публичный вход, подмена запуска и запрет БД-write/create, deliver, файлов, lock и PID до отказа |
| ТЗ, требование 2: оператор/гейты, developer failed/status/wait | Требования 4–5, AC-4–7/14, SPEC.md:22 | Разрешённые операции сохранены; новый инфраструктурный отказ full выделен отдельно по ANSWER-3 |
| ТЗ, требование 3: точная роль на каналах runner, провайдеры, без маскировки | Требования 3/9–12, AC-3/16–19, SPEC.md:21 | Process/lease и broker, kernel peer обеих сторон, ancestry/start identity; ENV/HOME/CLI/один PGID не удостоверяют роль |
| ТЗ, требование 4: старые тесты, инвентаризация, матрица | Требования 7–8/13, AC-9–15, SPEC.md:25; матрица :74; fixtures :147 | Старое разрешение developer меняется адресно; прочие роли, случайный ARTEL_ROLE и HOME не приравнены к developer |
| ТЗ, требование 5: отрицательные и положительные проверки | AC-1–7/16–19, SPEC.md:36 | Отказ и отсутствие эффектов проверяются отдельно от разрешённого фона и доступных операций |
| ТЗ, зоны и миссия | SPEC.md:163–171; требование 6/AC-8 | Миссия меняется только для developer. Дополнительные provider/doctor/context/fixture-зоны названы явно и следуют ANSWER-3/4 |
| ANSWER-1, пять адресных мандатов | SPEC.md:25, :84–89, :167 | Имена и строгость assertions сохраняются; замена области developer не распространена на ROLES/readonly_db/весь файл |
| ANSWER-2, ограниченная проба | SPEC.md:15, :194–196 | EPERM назван отрицательным результатом; не выдан за kernel-peer/ancestry или доказательство четырёх сред |
| ANSWER-3, один socket, UNKNOWN, live 2×2, $45 | SPEC.md:21–30, :66–72, :175–190 | Новая граница доступности явно принята; прежнее правило ANSWER-1 «не доказано — разрешить» заменено именно поздним решением |
| ANSWER-4, 1A + 2A и монолит | SPEC.md:30–32, :115–145, :147–179 | Адресная замена одного общего запрета true, точные пять fixtures и четыре новые test-зоны; риск бюджета отражён без повышения потолка |
| Возврат Оператора с гейта SPEC №1 | SPEC.md:94–113 | Failed/status/wait/UNKNOWN и свойства полного гейта разнесены; перечислены существующие адресные носители без заказа дубликатов |

Потребности, добавленной без ТЗ/ANSWER, не выявлено. Broker, оба адаптера, UNKNOWN и точечное изменение изоляции — явно согласованное развитие первоначального ТЗ, а не самовольное расширение. ANSWER-4 принимает монолит и риск остановки; текущая разница расхода с историческим снимком SPEC.md:177 не является неверной оценкой задним числом: снимок помечен «до начисления текущего шага». Реальные проверки не выполнены этим аудитом и остаются условием реализации по SPEC.md:29, :68, :72. Новый ответ для вынесения вердикта не нужен.

## Факты против кода

Снимки: worktree HEAD `0fe640c3a9c21e11af94b0c565918787ff44ea83`, локальный main `15515df76e89af7a329a227f99cf59a830c771c2`. SPEC.md:80 прямо привязывает адреса матрицы к этому main. `git diff HEAD main` для затронутого кода и тестов показывает различия в lease, метриках и новых timeout-тестах; остальные проверенные носители матрицы совпадают. Новые `orchestrator/suite_context.py` и `tests/test_suite_context.py` ещё отсутствуют и в SPEC корректно названы будущими зонами.

1. Исходная дыра подтверждается порядком кода: `orchestrator/suite_run.py:729` вызывает `_db`, :734 — `deliver_journal`; :767 берётся lock, :774 создаётся log, :781–788 удаляется ARTEL_ROLE и запускается отделённый Popen. `_db` (:158–167) сначала пробует пишущую `store.db`, затем readonly fallback. Поэтому одного отказа перед Popen недостаточно; требование 2 правильно требует более раннюю границу. Внешняя команда остаётся разрешена роли в `orchestrator/artel.py:1877–1880` и направляется в публичный обработчик на :2007.
2. Разрешённые развилки существуют: `suite_run.py:735–737` — wait, :747–756 — условия failed, :757–763 — статус без второго запуска; mode выбирается на :772. `background` (:586–614) уже отделён от публичного решения и завершает отчёт/освобождение замка. Это соответствует требованию не переносить новый запрет в общий runner тестов.
3. Runner даёт агенту новую сессию (`orchestrator/runner.py:74–92`), формирует маркеры по роли/задаче (:1042–1045) и сохраняет agent PID как pgid lease (:1570–1583). `in_role_environment` (:1051–1068) проверяет HOME/ARTEL_ROLE, причём сам комментарий предупреждает об обходе; точную роль и start identity эта функция не удостоверяет. SPEC не приписывает существующему runner готового broker.
4. Конфликт миссии и скила реален: `orchestrator/role_prompt.py:240–247` предлагает полный запуск, `skills/coding-standards.md:107–115` его запрещает. Но `S::MissionTest::test_ac25_developer_mission_names_suite_run_with_pult_path` (:1441–1444) проверяет лишь полный путь команды и наличие wait/failed. Сохранение этих assertions совместимо с новой формулировкой миссии.
5. Пять readonly_db-носителей и оба lock-helper сверены полностью: R:303–512, helpers :377–405. `ROLES` и случайный выбор `self.role` в R:155 остаются общими; новый helper не вправе заменять выбранную developer-роль разрешённой. Для положительной области разрешены изменения только пяти методов по ANSWER-1. Контекст `role_process` (:217–222) нужен также прямому вызову из lock-helper, поэтому подготовка только в `start_run` действительно была бы недостаточна.
6. S:193–231 копирует отдельный пульт и держит собственную БД; S:313–339 запускает CLI отдельным процессом. Все 11 наследников SuiteRunSandbox совпали с таблицей SPEC.md:153. B:29/45/63/125, P:483/506/513 и `tests/test_suite_run.py:228–269` тоже требуют положительного контекста перед новым full. ANSWER-4 и таблица fixtures теперь покрывают эти точки, сохраняя подмены тяжёлого запуска и измеряемые результаты.
7. Provider-assertions сверены адресно: C:318–323 — 11 feature=false и отдельный общий запрет true; C:265–282/:342–352 — паритет; C:385–441 — HOME, ключи, точный состав ENV и отсутствие keychain-чтения; C:1011–1034/:1053–1082/:1111–1124 — повреждения защиты. V:199–209 сохраняет точный argv Claude. Новые проверки эффективности не выдаются за уже существующие. Codex `never` находится в `orchestrator/providers/codex.py:145–146`, Claude `acceptEdits` — в `orchestrator/providers/claude.py:158`; doctor сейчас сверяет наличие сетевого параметра и disable (:208–219).
8. Полный гейт действительно вызывает `acceptance.full_suite` из `orchestrator/fsm_merge_gate.py:958–967`; общий runner под lock — `orchestrator/acceptance.py:1761–1774`. CI запускает `pytest tests` с прежними параметрами на `.github/workflows/ci.yml:245`. Таймаут, reuse и метрики сверены по отдельным носителям матрицы ниже. На main `SuiteObservationTest` (:179–189) теперь проверяет только green/red; timeout/unknown count находятся в новых `SeparateSuiteScenarios` (:127–228). SPEC учитывает это изменение, не выдаёт устаревший worktree за main.
9. Поиск `rg -l 'suite-run|suite_run' orchestrator tests skills templates docs/reference` дал 42 файла; каждый назван в SPEC. В templates и docs/reference совпадений нет. Прямые `cmd_suite_run(` в тестах находятся в перечисленных S/R/B/P, `tests/test_suite_run.py` и новой планке. Командный subprocess-маршрут S проверен отдельно. `SPLIT_SIGNAL_BUDGET_USD` действительно равен 60 (`orchestrator/config.py:587`).

PLAN.md:38–66 подтверждает запись прежнего воспроизведения с подменой Popen и остановку реальной пробы на connect/EPERM. Это исторический материал, а не повторный прогон аудитора; записки других ролей не читались. Полный tests/, планка и live-пробы в этом аудите не запускались.

## Проверяемость критериев

Все 19 критериев имеют наблюдаемый результат. «Да» ниже означает проверяемость требования, а не зелёный результат ещё не реализованного продукта. Для AC-17/19 нужны именно реальные среды; моки не закрывают эти строки.

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | Да, исходный публичный маршрут с подменой тяжёлого запуска | Воспроизведение зовёт сразу background или использует только self-claimed ENV вместо подтверждённого developer: наблюдение не доказывает исходный публичный обход |
| AC-2 | Да, отдельно контрактный и инфраструктурный отказ | Проверка поставлена после `_db`, deliver, mkdir/log/lock либо Popen; отказ печатается уже после побочного эффекта |
| AC-3 | Да, process/IPC-тесты и live shell | Роль берётся из ARTEL_ROLE, FSM запрошенной задачи или одного PGID; снятие маркера/другая задача/setsid дают full |
| AC-4 | Да, UNKNOWN и ошибки канала при full и разрешённых операциях | Исключение IPC трактуется как внешний оператор; либо общий отказ лишает клиента status/wait/failed |
| AC-5 | Да, положительные внешние и иные роли, ветка и база фона | Общий HOME блокирует внешнего клиента; in_dev target заменяет роль вызывающего; фон повторно классифицируется и отказывает |
| AC-6 | Да, прежние nodeid и ошибки исходного состояния | Failed подменяется full при пустом/отсутствующем перечне; запускается база; outage запрещает допустимый повтор |
| AC-7 | Да, счётчик запусков, состояние, отчёт и предел ожидания | Status запускает второй процесс; wait без результата запускает full; истечение ожидания убивает идущий прогон; предел 9 минут обходится |
| AC-8 | Да, сформированная миссия | Сохраняется предложение нового full, исчезает явный запрет/планка/адресные тесты либо одна из трёх форм команды с путём пульта |
| AC-9 | Да, тот же R::ReadonlyDbOutcomeTest и отдельный отказ | Ошибка readonly journal обрывает зелёный прогон или зелёный/красный отчёт получает неверный код; контекст скрыто даёт запись в БД |
| AC-10 | Да, тот же R::JournalRedeliveryTest и отказ | Отложенная запись теряется либо досылается запрещённым full developer до отказа |
| AC-11 | Да, обе стороны общей блокировки | Для роли выбран другой lock; отказ UNKNOWN подменяет отказ занятого lock; developer берёт lock прежде отказа |
| AC-12 | Да, прежний предел/источник для ветки и базы | Используется запасной timeout вместо профиля, поднят предел 3 секунды, изменены код/текст превышения |
| AC-13 | Да, новые логи и пути в отчёте | Лог базы остаётся вне suite-run; отчёт указывает несуществующий файл; запрещённый full создаёт пустой log |
| AC-14 | Да, адресные прежние носители и проверка границы | Broker-проверка внесена в общий full runner; исчезает timeout/lock; reuse использует один HEAD либо игнорирует команду/возраст/незавершённость; теряются метрики |
| AC-15 | Да, проверка diff и независимых сценариев | Helper всем ролям выдаёт разрешение, заранее создаёт отчёт/full-result, использует внешний broker; ослаблены assertions/readonly_db/ROLES либо изменён незаявленный fixture |
| AC-16 | Да, отрицательные IPC/process-сценарии | Принимается поддельный endpoint/self-claimed PID; сравнивается лишь PID без start-time; старый ответ или завершённый lease разрешает следующий full |
| AC-17 | Да, четыре реальные среды и отдельные отрицательные пробы | Разрешены соседний Unix/TCP/UDP/IPv6/domain/process; debug-профиль или смена имени провайдера в моке засчитаны как live. Недоступная среда не становится skip |
| AC-18 | Да, зависание/обрыв/размер/глубина и teardown | Нет deadline/лимита чтения или ancestry; error/timeout оставляет регистрацию либо endpoint; уборка убивает разрешённый фон или меняет lease |
| AC-19 | Да, старые assertions, новые повреждения политики и live | Общий запрет true удалён без точного исключения; parser прячет ключи; обе стороны паритета одновременно разрешают эскалацию/сеть/лишнюю запись; doctor не видит отсутствующий фильтр |

## Зоны

Зоны SPEC.md:7, :163–171 покрывают заявленную реализацию и точную подготовку тестов. Три исходных product-модуля ограничены прежними обязанностями; новый suite_context несёт broker/client и оба адаптера. Provider/референсы/doctor открыты только для одного socket-допуска по ANSWER-3. Четыре добавленных test-файла и R-fixture совпадают с ANSWER-4; новые helpers допустимы в уже заявленном tests/test_suite_context.py. Для них не разрешены изменения assertions по аналогии.

`config.PROTECTED_PATHS` (`orchestrator/config.py:754–760`) проверен: указанные provider и два референса не защищены этой константой, тогда как skills/templates/ADR/CI/conftest и общие конфиги защищены. SPEC.md:171, :187 требует для необходимых защищённых изменений приложение PLAN; прямой правки не разрешает. Изменение скила coding-standards не требуется: его контракт уже соответствует цели. Матрица только читает timeout/reuse/CI-носители вне zones, не даёт права их переписывать. Генерируемая карта названа отдельно.

Расширение IPC названо явно и имеет мандат; открытия прочей сети, process-доступа или новых writable paths нет. Живой дом роли/Оператора не является рабочей зоной developer. Нужда в иной политике, версии, доступной live-среде или дополнительном изменении assertions заканчивается штатной эскалацией; SPEC не выдаёт несуществующее разрешение заранее.

## Матрица неослабления

Пять столбцов соответствуют `docs/operator-gates.md:61–84`. Адресные сокращения ниже обозначают точные файлы:

- S — `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`.
- R — `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`.
- U — `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py`.
- B — `tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py`.
- P — `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`.
- C — `tests/test_providers_codex.py`; V — `tests/test_providers.py`.
- O — `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py` на main.
- T — `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py` на main.
- N — заявленная планка `tests/test_01m4xvm49pp5whsxt5s8jw85wn_developer_suite.py`, пересматриваемая test_author; K — будущий `tests/test_suite_context.py`.

Ссылка «тот же» означает сохранение названного носителя с теми же assertions. Для нового покрытия указаны обязательный AC и будущая зона, без вымышленных строк ещё не написанных тестов. Условие нового покрытия уже является требованием SPEC, поэтому это не строка «остаётся, не покрыто» без замены.

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Новый full developer | R:303/341/407/435/473 разрешают запуск | Нет, ранний отказ вместо разрешения | N, AC-1/2; отдельно положительные носители ниже | Адресный мандат ANSWER-1/ADR-0024 |
| Green/red при readonly БД | R::ReadonlyDbOutcomeTest:303, assertions :329–336 | Да, разрешённые клиенты | Тот же R:303; AC-9 | Сохранить; подготовка 2A не даёт БД-write |
| Отложенный журнал | R::JournalRedeliveryTest:341, :364 | Да | Тот же R:341; AC-10 | Сохранить отсутствие записи из readonly процесса |
| Досыл процессом пульта | R:368–372 | Да | Тот же R:341; AC-10 | Сохранить; forbidden full не досылает |
| Lock гейта блокирует suite-run | R::SharedLockTest::gate_holds_role_refused:377–393 | Да | Тот же helper из R:407; AC-11 | Держатель назван; UNKNOWN не подменяет lock-отказ |
| Lock suite-run блокирует гейт | R::SharedLockTest::role_holds_gate_waits:395–405 | Да | Тот же helper из R:407; AC-11 | FULL_SUITE_NOT_STARTED и отсутствие pytest прежние |
| Профильный предел ветки и базы | R::LimitUnchangedTest:450–459 | Да | Тот же R:435; AC-12 | Предел и источник неизменны |
| Исход превышения 3 секунд | R:461–468 | Да | Тот же R:435; AC-12 | Код 1, текст и источник прежние |
| Место логов ветки/базы | R::LogPlacementTest:473–505 | Да | Тот же R:473; AC-13 | Новые логи только под suite-run |
| Существующие пути логов в отчёте | R:507–512 | Да | Тот же R:473; AC-13 | Не заменить проверку наличия текстом пути |
| Запуск внешнего клиента при HOME/случайном маркере | S::RoleEnvironmentTest::test_ac22_role_process_is_not_refused:579–601 | Да при доказанной классификации | Тот же S:579 и N AC-5 | Не менять ожидание на UNKNOWN; 2A готовит внешний процесс |
| Прочие точные роли | R:155/217 и пять методов мандата | Да | Те же положительные методы; N AC-5 | Роль удостоверяется process/lease |
| Отделённый фон и очистка ARTEL_ROLE | S::RoleEnvironmentTest::test_ac5_runs_have_no_artel_role_in_environment:549–577 | Да | Тот же S:549; N AC-5 | Не применять новый запрет повторно к разрешённой ветке/базе |
| Только прошлые упавшие nodeid | S::FailedRerunTest::test_ac19_failed_reruns_exactly_last_failures:1147–1210 | Да | Тот же S:1147; N AC-6 | Без tests/--lf, без нового прогона базы |
| Failed без прошлого запуска | S::FailedRerunTest::test_ac20_failed_without_previous_run_is_refused:1212–1232 | Да | Тот же S:1212; N AC-6 | Отказ, не full |
| Failed без упавших | `orchestrator/suite_run.py:753–756` | Да | N AC-6 требует прежний отказ | Новое покрытие обязательно |
| Адресные тесты и планка developer | `skills/coding-standards.md:107–115`; `orchestrator/artel.py:1879` | Да | N AC-6/8 и неизменные маршруты | Не расширять запрет на эти операции |
| Статус и один запуск | S::BackgroundTest::test_ac7_second_launch_reports_running_run:650–672 | Да | Тот же S:650; N AC-7 | Тот же лог и один запуск |
| Wait: исчерпание и завершение | S::BackgroundTest::test_ac8_wait_reports_finished_or_still_running:674–721 | Да | Тот же S:674; N AC-7 | Отчёт, живой процесс, отсутствие повторного запуска |
| Wait без прогона | S::BackgroundTest::test_ac9_wait_without_any_run_is_refused:723–742 | Да | Тот же S:723; N AC-7 | Не запускать full |
| Предел wait | S::BackgroundTest::test_ac10_wait_above_limit_is_refused_without_waiting:744–767 | Да | Тот же S:744; N AC-7 | Прежние 9 минут и живой прогон |
| Новый full при UNKNOWN | Прежний `suite_run.py:726–788` не удостоверяет клиента | Нет, вводится инфраструктурный отказ | N/K AC-2/4/16 | Прямое решение ANSWER-3, включая Оператора |
| Status/wait/failed при outage | Прежние развилки `suite_run.py:735–763` не требуют IPC | Да | N/K AC-4/6/7 после отключения канала | Не навязывать broker читающим операциям/допустимому повтору |
| Первичное решение до эффектов | Сейчас `_db`/deliver/lock/log/Popen: suite_run.py:729–788 | Усиливается | N AC-2/4/16, наблюдение каждой категории эффектов | Отказ до write/create, не только до Popen |
| Точная роль вместо ENV/HOME/PGID | runner.py:1042–1068/1570–1583 | Усиливается | N/K AC-3/16/17 | Kernel peer, ancestry и start identity |
| Актуальность lease и отсутствие replay | runner.py:1583 и существующий lease-контекст | Усиливается | K/N AC-16: expiry, смена, PID reuse, подмена, новый вызов | Не доверять старой регистрации/ответу |
| Ограниченность IPC/ancestry | Новый канал, прежнего носителя нет | Новое свойство | K/N AC-18: зависание, обрыв, размер, глубина | Deadline и пределы проверяются наблюдаемо |
| Teardown и прежний timeout/kill | runner.py:1601–1610; spawn :74–92 | Да, плюс cleanup канала | K/N AC-18, success/error/timeout | Не менять lease/kill/lock и разрешённый фон |
| Полный внутренний гейт | acceptance.py:1761–1774; fsm_merge_gate.py:958–967 | Да | `tests/test_suite_run.py::GateArgvTest:332–345`; AC-14 | Broker не переносится в общий full runner |
| Полный CI | `.github/workflows/ci.yml:239–245` | Да | Тот же шаг CI; AC-14 | Состав, timeout и обязательность сохраняются |
| Профильный timeout полного гейта | `tests/test_full_suite_profile_timeout.py::FullSuiteProfileTimeoutTest:76–92` | Да | Тот же метод; AC-14 | 1500, FULL_SUITE_TIMEOUT и источник прежние |
| Reuse одинакового дерева | U::SuiteReuseTest::test_ac4_same_uncommitted_tree_in_scratch_reuses_green_result:48–66 | Да | Тот же U:48; AC-14 | Содержимое дерева, включая незакоммиченное |
| Правка дерева инвалидирует reuse | U::SuiteReuseTest::test_ac5_tracked_change_invalidates_result:33–46 | Да | Тот же U:33; AC-14 | Не заменить дерево HEAD |
| Команда в ключе reuse | U::SuiteReuseTest::test_ac6_command_change_invalidates_result:68–82 | Да | Тот же U:68; AC-14 | Смена команды требует нового прогона |
| Возраст reuse | U::SuiteReuseTest::test_ac7_age_boundary:84–99 | Да | Тот же U:84; AC-14 | Обе стороны границы возраста |
| Незавершённый результат не reuse | U::SuiteReuseTest::test_ac8_incomplete_runs_are_not_reused:101–123 | Да | Тот же U:101; AC-14 | Timeout/not-started/no-tests/no-summary |
| Timeout гейта не подменяет базу | S::BaseTimeoutTest::test_ac16_timed_out_gate_run_saves_nothing:1001–1026 | Да | Тот же S:1001; AC-14 | База всё равно запускается |
| Метрики green/red | O::SuiteObservationTest::test_ac1_gate_writes_each_outcome_with_metrics:171–189 | Да | Тот же O:171 и assert_record_fields:103; AC-14 | Одна запись с прежними полями |
| Timeout убивает группу, cleanup ограничен | T::SeparateSuiteScenarios::test_ac3_timeout_kills_group_and_failure_cleanup_is_bounded:127–203 | Да | Тот же T:127; AC-14 | 4 секунды, SIGKILL, закрытый stdout, timeout-метрики |
| Задержка старта и unknown count | T::SeparateSuiteScenarios::test_ac4_real_start_delay_is_timeout_with_unknown_count:205–228 | Да | Тот же T:205 и assert_metrics:93–111; AC-14 | Workers 1/2, tests/seconds_per_test=None |
| Сигнал near-limit различает failed/full | `tests/test_suite_near_limit.py::FailedRerunTest::test_failed_rerun_gives_no_signal_full_run_does:63–74` | Да | Тот же метод; AC-14 | Повтор не сигналит, полный сигналит |
| Миссия и полный путь команд | S::MissionTest::test_ac25_developer_mission_names_suite_run_with_pult_path:1413–1444 | Да; предложение full заменяется запретом | Тот же S:1413; N AC-8 | Старые три assertions сохраняются |
| Общий запрет любого true | C::CuratedHomeTest::test_every_disabled_feature_is_false_in_the_curated_config:322–323 | Только точное socket-исключение | Тот же метод C:307, AC-19 | Мандат ANSWER-4 1A только на этот assertion |
| Все 11 feature=false | C:318–321 | Да | Те же assertions C:307; AC-19 | Без исключений |
| Все 11 disable в argv | C::StepCommandTest::test_every_disabled_feature_of_the_curated_home_is_in_the_command:208–220 | Да | Тот же C:208 | Не менять перечень/число |
| Паритет argv/reference | C::StepCommandTest:265–282 и C::CuratedHomeTest:342–352 | Да | Те же два метода, AC-19 | `_toml_pairs` не скрывает входные данные |
| Один Unix socket | Прежний EPERM, PLAN.md:47; ANSWER-3 | Прежний тотальный запрет заменён адресным допуском | Live AC-17 и PLAN для четырёх сред; K | Ок при обязательном новом покрытии |
| Соседний Unix socket запрещён | Сетевая изоляция Codex: providers/codex.py:143–144; ANSWER-3 | Да | Отдельная live sibling-socket проба AC-17 | Writable-каталог не доказательство IPC |
| Прямой TCP запрещён | Та же сетевая граница; ANSWER-3 | Да | Отдельная live raw TCP проба AC-17 | Proxy403 её не заменяет |
| UDP запрещён | Та же сетевая граница; ANSWER-3 | Да | Отдельная live UDP проба AC-17 | Не выводить из TCP |
| IPv6 запрещён | Та же сетевая граница; ANSWER-3 | Да | Отдельная live IPv6 проба AC-17 | Не выводить из IPv4 |
| Внешние domains запрещены | ANSWER-3 и прежняя закрытая сеть | Да | Отдельная live domain-проба AC-17 | Пустого списка в конфиге недостаточно |
| Process/ps ограничения | ANSWER-3; broker-introspection по ADR-0025 вне роли | Да | Отдельная live process/ps проба AC-17 | Роли не выдаётся process-доступ |
| Doctor видит отсутствие sandbox | C::IsolationSmokeTest:1020–1023 | Да | Тот же C:1011; AC-19 | Fail и workspace-write сохраняются |
| Doctor видит отсутствие сетевой защиты | C:1025–1029; doctor/isolation.py:212–215 | Да | Те же assertions; AC-19 добавляет утрату фильтра/несовместимость | Не подменять одним здоровым smoke |
| Doctor видит отсутствие disable | C:1031–1034 | Да | Те же assertions C:1011 | Fail и computer_use прежние |
| HOME/CODEX_HOME заменяют ambient | C::EnvironmentTest::test_home_and_codex_home_overwrite_ambient_values:385–399 | Да | Тот же C:385 | Не наследовать дом Оператора |
| Doctor видит чужой HOME | C::IsolationSmokeTest::test_inherited_ambient_home_is_red:1111–1124 | Да | Тот же C:1111 | Fail/HOME прежние |
| API keys не доходят до шага | C::EnvironmentTest:421–441 | Да | Тот же C:421 и IsolationSmokeTest:1053–1082 | Каждый запрещённый ключ остаётся проверен |
| Нет лишнего keychain-чтения | C::EnvironmentTest:418–419 | Да | Тот же метод C:401 | slots=[] и secret_env_names=() |
| Точный состав provider ENV | C::EnvironmentTest:417 | Да | Тот же метод C:401 | HOME/CODEX_HOME/ZDOTDIR; endpoint не разрешает смену assertion |
| Нет model/MCP-инъекции Codex | C::CuratedHomeTest::test_config_toml_carries_no_model_and_no_mcp_server:291–305 | Да | Тот же C:291, все три assertions | Сохранить |
| MCP/settings-изоляция Claude | V::StepCommandTest::test_role_cmd_matches_the_pre_task_argv:199–209 | Да | Тот же V:199; AC-19 | Прежний точный argv, strict-mcp-config/setting-sources |
| Codex approvals | providers/codex.py:145–146, reference config.toml:28 | Да | Прямое значение never и live запрет эскалации AC-19 | Одного паритета C:265/342 недостаточно |
| Claude permissions | providers/claude.py:158 | Да | V:199 и live AC-19 | acceptEdits и эффективные ограничения |
| Файловый режим Codex | C::StepCommandTest:193–206, C:1020–1023 | Да | Те же assertions; AC-19 | workspace-write сохраняется |
| Эффективные writable paths | Прежняя песочница роли; ANSWER-4 | Да | Live AC-19: разрешённая запись и отказ за границами | Новые writable paths ради socket запрещены |
| Изоляция/cleanup пяти fixtures | S:193/313, R:150/217/224/269, tests/test_suite_run.py:228, B:29, P:483/506 | Да | Те же сценарии и N/K AC-15 | Только подготовка своего контекста; без результатов full заранее |
| Lock до Popen и передача держателя | `tests/test_suite_run.py::LockTest::test_command_takes_lock_before_background_start:252–269` | Да | Тот же метод; AC-15 | Точные значения holder и обе попытки T1/T2 |
| Reuse базы и различение документов | B::BaseReuseTest:45/63/125 | Да | Все три прежних метода; AC-14/15 | Счётчики запусков 2/3/5 и ключи прежние |
| Прогресс по nodeid | P::ProgressCountTest::test_ac4_progress_count_is_by_test_nodeids:513–550 | Да | Тот же метод; AC-15 | Начальный full удостоверен, подсчёт и wait прежние |
| Бюджет и последовательность гейтов | ANSWER-3/4, SPEC.md:175–190 | Да | Действующий гейт бюджета, обычные audit/tests/review/acceptance/merge | $45; риск остановки не даёт пропуска проверки |

Раздела «Меняемое поведение» со скалярными заменами в SPEC нет. Это допустимо: две разновидности изменения тестов здесь имеют прямые адресные мандаты ANSWER-1/4, а не объявлены парами литералов. Поэтому отсутствуют строки со словами/контейнерами вместо литералов, неподтверждённым «было» или замаскированной сменой вида assertion. Мандат на общий запрет true не открывает остальные assertions метода. Имена, skip/xfail/retries, пределы и readonly_db явно сохранены.

## Пути обхода гейтов

Проверены следующие способы получить формальную зелень при потере смысла контракта. Лазейки, разрешённой буквальным текстом текущего SPEC, не обнаружено:

1. Поставить guard после пишущего `_db`/deliver или lock: исходный порядок `suite_run.py:729–788` делает это правдоподобной ошибкой, но SPEC.md:20 и AC-2 требуют наблюдения всех эффектов до отказа.
2. Удалить ARTEL_ROLE, сменить HOME/endpoint/task_id/PGID либо назвать клиент Оператором: SPEC.md:21, :66 и AC-3/16 требуют kernel peer, start identity, актуальный lease и отказ при нестабильности. Discovery не зависит исключительно от маркера.
3. Исключить developer из общего ROLES или выдать всему helper разрешённый контекст: SPEC.md:25, :32, :64, :149–157 запрещает это, сохраняет отрицательные сценарии отдельно и допускает только пять адресных изменений области.
4. Старые full-тесты оставить без broker и принять UNKNOWN за прежний lock/profile-отказ: теперь пять fixtures прямо обеспечивают доверенный положительный маршрут; прежние assertions не меняются (SPEC.md:147–169). Отдельно сохраняется потребитель lock-helper, который не вызывает start_run.
5. Заранее записать зелёный результат, журнал или lock в подготовке либо использовать внешний broker: SPEC.md:32 и AC-15 запрещают оба способа; изоляция и cleanup принадлежат тестовому пульту.
6. Изменить обе стороны паритета или parser так, чтобы открытая сеть/approvals выглядели согласованными: SPEC.md:30, :72 и адресные строки матрицы сохраняют входные данные и требуют предметной эффективной проверки, включая never, запись за границами и отсутствие фильтра.
7. Засчитать debug sandbox/мок провайдера или только TCP за все платформы и запреты: SPEC.md:29, :68 требует реальные четыре маршрута и отдельные UDP/IPv6/domains/process/sibling probes. Недоступность означает эскалацию, не skip.
8. Перенести запрет в общий full runner и сломать гейты/failed/фон: SPEC.md:22–23, :42–48, :62 прямо сохраняет эти маршруты; существующие носители не заменяются новым тестом отказа.
9. Применить старый ответ broker к следующему вызову или оставить регистрацию после timeout: SPEC.md:21, :28, :66, :70 требует актуальной регистрации и teardown, отдельные отрицательные AC-16/18.
10. Уложиться в бюджет отменой live-проверок/гейтов или поднятием лимитов: SPEC.md:177–190 и ANSWER-4 прямо принимают остановку вместо такого упрощения.

Прямой вызов внутренних Python-функций произвольным кодом не объявлен отдельной новой OS-песочницей; предел задачи указан в SPEC.md:185–186. Наличие внутренних full-маршрутов само по себе не противоречит публичному контракту и требованию сохранить гейты.

## Вердикт

**pass**. Перечень отклонений пуст. Вердикт относится только к SPEC `731d61af4ba0c68494a7e3e85152666815cfb484`.

Прежние F1/F2/F3 закрыты: адресный мандат на общий запрет true — ANSWER-4 и SPEC.md:30/:115; точные fixtures и зоны — SPEC.md:147–169; раздельные носители provider/изоляции — SPEC.md:115–145 и AC-19 (:72). Исправлены timeout-носители по текущему main (SPEC.md:110–112). Причина возврата Оператора с гейта также учтена в адресной матрице SPEC.md:94–113.

Это заключение о согласованности и проверяемости SPEC. Оно не подтверждает работоспособность socket-политики, реализацию broker или прохождение приёмки. Четыре обязательные реальные среды и эффективные запреты AC-17/19 ещё должны быть доказаны; недоступность требует предусмотренной SPEC эскалации. Принятый риск бюджета не снимает этих условий.

Проверка артефакта: `python3 scripts/guard.py <каталог документов>/SPEC-AUDIT.md` — `GUARD: ок (1 файлов)`, код 0. После записи SHA SPEC остался заданным; `git status --short` пуст. SPEC, ТЗ и код не изменены; коммиты не создавались.

## Предложения системе

В этом шаге обычная команда чтения `cat templates/SPEC-AUDIT.md` оказалась недоступна (`command not found`) при штатном PATH роли; файл прочитан Python без изменения окружения. Для диагностики курируемого PATH полезно явно указывать доступный набор базовых утилит. На вердикт SPEC это не влияет.
