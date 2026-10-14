---
task: 01M4XRD6A00G4H5NRMV1KP9QCN
type: spec_audit
author_role: spec_auditor
status: ready
verdict: pass
signals: в) пути-признаки (тесты): tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py, tests/test_01m4xrd6a00g4h5nrmv1kp9qcn_*.py
spec_sha: 9285e0926c8018639a9042eae3c33135c7a0b870
schema_version: 5
---

# SPEC-AUDIT: CanaryLifecycleTest: устойчивое доказательство уборки после сигнала

## ТЗ и SPEC

Полный разбор. Проверен SPEC с заданным git blob SHA; рабочая кодовая версия — a37347f28dc5d9c2fff0f670d967e3c554f43322. Команда пульта `show 01M4XRD6A00G4H5NRMV1KP9QCN` подтвердила задачу, ветку и состояние spec_audit до записи артефактов. ANSWER-n.md в каталоге документов нет; решений возврата с гейта SPEC в брифе нет. Ни мандата на ослабление, ни расширения зон не предполагается.

Соответствие требований в обе стороны:

- TZ.md:21 → SPEC.md:19, SPEC.md:28: причинное воспроизведение, оба CI, seed как исходный материал, различение четырёх классов причин. SPEC.md:104 прямо сообщает, что логи аналитиком не прочитаны; диагноз не выдан за установленный факт.
- TZ.md:22 → SPEC.md:20, SPEC.md:30, SPEC.md:32, SPEC.md:34: публичный маршрут, реальные clone/origin и группы, оба сигнала, запись исхода, остальные свойства класса.
- TZ.md:23 → SPEC.md:21, SPEC.md:22, SPEC.md:36, SPEC.md:38: наблюдаемая готовность, сохранение раннего окна, конечная аварийная уборка, неизменный предел 20 секунд, запрет retries/skip/xfail и смягчения assertions.
- TZ.md:24 → SPEC.md:23, SPEC.md:40, SPEC.md:46: пятиколоночная матрица, раздельные мутации, одна и та же инъекция для базы и исправления, проверка утечек после обоих исходов.
- TZ.md:25 → SPEC.md:24, SPEC.md:97, SPEC.md:98: продуктовая правка только после доказательства и согласования минимального изменения; полный tests/ внутри роли исключён.
- TZ.md:27 и TZ.md:28 → SPEC.md:7, SPEC.md:95, SPEC.md:96: тестовая зона ограничена исходным файлом и новыми файлами задачи; общие helpers, конфиги и исключённые механизмы не включены.
- TZ.md:29 → SPEC.md:8, SPEC.md:89, SPEC.md:99: $40 ниже рамки $50; самостоятельное повышение и мерж не разрешены. Набор codex-all подтверждён карточкой БД; это параметр запуска, а не требование к коду.

Новых продуктовых требований сверх ТЗ нет. Сохранение имён методов и детализация прежних утверждений в SPEC.md:44 служат неослаблению. Отсутствие готового диагноза не заменено разрешением исправлять продукт: расследование является результатом AC-1, а обнаружение продуктового дефекта возвращает SPEC на согласование. Блокирующего вопроса Оператору для вынесения этого вердикта нет.

## Факты против кода

В дальнейшем `L` обозначает файл `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`; ссылки в матрице приведены полностью. Прочитан весь файл, включая setUp, _CHILD, stop_suites, alive, launch_signalled и assert_signal_cleanup. Его содержимое не отличается от локального main (cb8a98db33b71397b02e872ee9e1158ccb6e88a7). Карта docs/codebase-map.md:3633 согласуется с импортами теста.

- Публичный маршрут подтверждён L:54 и L:56: argv с canary, затем artel.main(). Подменяются запуск ведения, cmd_init, домашний каталог и признак окружения роли (L:50). Реальный git clone остаётся в orchestrator/canary.py:1182, локальный bare origin — в orchestrator/canary.py:1194, назначение remote — в orchestrator/canary.py:1200. SPEC не обещает запуск настоящих моделей.
- Suite создаётся отдельной сессией с DEVNULL на L:36; PID публикуется на L:41. Переадресация config в клон происходит в orchestrator/canary.py:1207, поэтому run.json действительно находится в хозяйстве клона. Drive получает параметры продуктового Popen (L:44), в том числе start_new_session=True из orchestrator/canary.py:2335.
- Observation пишется на L:46 до return drive на L:49; родитель отправляет сигнал на L:135. В продукте присваивание proc на orchestrator/canary.py:2333 предшествует защищённому wait на orchestrator/canary.py:2338. Обработчик уже установлен: orchestrator/canary.py:2806 оборачивает запуск задачи; orchestrator/canary.py:2744 поднимает CanaryInterrupted. Раннее окно действительно возможно, но его наличие не доказывает причинную цепочку до TimeoutExpired из ТЗ.
- Вывод drive идёт в файл (orchestrator/canary.py:2331 и orchestrator/canary.py:2334), suite — в DEVNULL (L:38). У child два PIPE (L:122). Поэтому утверждение SPEC.md:105, что жизнь drive сама по себе не доказывает удержание этих pipe, корректно. Seed на L:65 используется для диагностики; явная фикстура задаётся через --template на L:55. Seed нельзя объявлять источником гонки.
- Уборка suite вызывается в finally клона (orchestrator/canary.py:1238), удаление clone/origin — orchestrator/canary.py:1249 и orchestrator/canary.py:1250. Уборка drive при таймауте и BaseException находится в orchestrator/canary.py:2340 и orchestrator/canary.py:2344. Запись точного сигнала и red — orchestrator/canary.py:2813. Эти адреса подтверждают разделение проверяемых обязанностей.
- Утверждения после сигнала — L:141, L:143, L:145, L:147; записи в БД — L:175, L:179, L:180, L:182, L:183. Остальные сценарии normal/timeout/exception находятся на L:191; создание suite и его отсутствие проверяются на L:235 и L:236, распространение исключения — L:229. Маркер ищется во время ведения на L:251; точный PID с границами цифр — L:255, распространение исключения и положительное наблюдение — L:265 и L:268.
- Границы существующего доказательства не преувеличены: alive проверяет PID через poll/kill(pid, 0) (L:104 и L:107), а не всех членов многопроцессной группы. Сейчас каждая сигнальная фикстура создаёт по одному спящему процессу на группу. AC-2 требует отсутствие групп, поэтому сохранение проверки только лидера не заменяет это требование при расширении фикстуры.
- Аварийная уборка сейчас неполна: child.kill() на L:125 не сопровождается wait; stop_suites ждёт только Popen из suite_procs на L:98; сигнальные PID и пути регистрируются лишь после чтения observation на L:131. Матрица SPEC.md:78 не утверждает уже существующего ожидания child. Требование AC-6 усиливает этот участок, включая аварийный выход до полноценного наблюдения ресурсов.

Несовпадений заявленных фактов SPEC с кодом не найдено. Причина известных CI в рамках аудита не устанавливалась: их номера и симптомы проверены как данные TZ.md:14, а не как самостоятельно прочитанные логи.

## Проверяемость критериев

Критерии проверяемы, но таблица ниже описывает обязательное доказательство реализации, а не результаты ещё не созданных тестов. Для AC-1 чтение объяснения само по себе недостаточно: необходимы исполнимая инъекция и результаты обеих сторон.

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | Да: одинаковое детерминированное воздействие на базу и исправление, наблюдения стадий и состояния процессов/pipe; CI-материалы дополнительно проверяются по отчёту | Откат исправленной синхронизации к отправке сигнала сразу после observation (L:127, L:135) должен вернуть установленный исходный отказ. Конкретную причинную точку обязан обосновать результат расследования; произвольная пауза более 20 секунд не доказывает AC |
| AC-2 | Да: два сигнала, публичный маршрут, реальные ресурсы, проверка результата продуктовой уборки | Пропуск terminate_process_group для suite (orchestrator/canary.py:1244), drive (orchestrator/canary.py:2348), либо одного rmtree (orchestrator/canary.py:1249, orchestrator/canary.py:1250) оставляет соответствующий ресурс |
| AC-3 | Да: запись именно прерванного запуска, оба сигнала и оба ограничения вердикта | Удаление insert_canary_run, замена имени SIGHUP на SIGTERM, verdict на green или неизвестное значение (orchestrator/canary.py:2813) |
| AC-4 | Да: три способа окончания и наблюдение маркера до окончания ведения | Уборка suite только в сигнальной ветке вместо finally; поглощение RuntimeError; удаление либо перенос записи owner PID после yield (orchestrator/canary.py:1269). Все перечисленные свойства имеют отдельное покрытие |
| AC-5 | Да: наблюдение готовности и сохранённая проверка раннего окна | Барьер становится безусловно открытым либо основанным на sleep; сигнал переносится только за возврат Popen и ранний сценарий исчезает. Проверка эквивалентности должна различать эти варианты |
| AC-6 | Да: наблюдение ресурсов после нормального результата, исходной красноты и аварии ожидания; проверка лимитов в коде | Удаление ожидания завершения child из будущей уборки, забытый drive при сбое чтения observation, незакрытый pipe; увеличение timeout=20 или добавление retry. Первые ловятся аварийным сценарием, последние — проверкой изменений лимитов и запретов |
| AC-7 | Да: пять отдельных запусков мутаций с подтверждением отказа соответствующей проверки и последующей уборкой | Каждая из четырёх пропущенных уборок из AC-2 и неверное имя сигнала из AC-3. Формальный ненулевой код от постороннего исключения не доказывает обнаружение этих нарушений |

AC-1 и AC-5 намеренно не фиксируют внутреннюю функцию будущего барьера: причина ещё не установлена. Это не разрешает обойти причинное доказательство; конкретизация после расследования не должна навязываться тестом сверх SPEC.

## Зоны

SPEC.md:7 покрывает исходный тест и новые тесты задачи. Исправление тестовой синхронизации и локальных помощников возможно внутри этой зоны. Продуктовые файлы имеют условный режим в TZ.md:27; SPEC.md:24 явно запрещает менять их до нового согласования с доказанным дефектом. Это соответствует ТЗ, а не потеря продуктовой ветви решения.

Проверен config.PROTECTED_PATHS (orchestrator/config.py:754): исходный тест и маска новых файлов не включают защищённые конфиги, conftest.py, tests/test_invariants.py, skills/ или templates/. Общая песочница tests/sandbox.py не разрешена и не требуется к изменению текстом SPEC. Защищённая правка не может быть внесена ролью напрямую; при отдельном решении остаётся механизм приложения PLAN. Правила песочницы и запрет чтения настоящего пула не расширяются: фикстура использует временный home (L:81 и L:83).

Регенерация docs/codebase-map.md после будущей правки Python остаётся штатной обязанностью разработчика; в аудите Python не менялся. Расширять зоны по предположению о причине не требуется.

## Матрица неослабления

Проверены все 38 строк SPEC.md:48–85 по коду, а не только два сигнальных метода. Форма соответствует docs/operator-gates.md:61; отдельные свойства записи исхода, остальных методов и аварийных помощников не объединены в одну строку «класс сохранён». Ниже указано покрытие после как обязательство SPEC. Существующие адреса показывают проверяемое свойство до правки; номера строк ещё не созданных проверок не выдуманы.

| Что меняется | Какое свойство сейчас держит (файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) | Решение |
|---|---|---|---|---|
| Синхронизация _CHILD | Публичный вход artel.main() с командой canary — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:54` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — launch_signalled; AC-2 | Сохранить; проверить по AC-2 |
| Подготовка сигнального сценария | Настоящий локальный clone, наблюдаемый из cwd — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:35` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — launch_signalled; AC-2 | Сохранить; проверить по AC-2 |
| Подготовка сигнального сценария | Настоящий локальный origin, полученный через git remote — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:42` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — launch_signalled; AC-2 | Сохранить; проверить по AC-2 |
| Подготовка suite | Suite — реальный процесс отдельной сессии — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:36` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — launch_signalled; AC-2 | Сохранить; проверить по AC-2 |
| Подготовка suite | PID suite опубликован в хозяйстве клона для продуктовой уборки — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:39` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — launch_signalled; AC-2 | Сохранить; проверить по AC-2 |
| Подготовка drive | Реальный процесс drive с параметрами публичного маршрута — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:44` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — launch_signalled; AC-2 | Сохранить; проверить по AC-2 |
| Сигнальное ожидание | SIGTERM удаляет clone — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:141` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac1_sigterm_cleans_clone_origin_and_both_process_groups; AC-2 | Сохранить; проверить по AC-2 |
| Сигнальное ожидание | SIGTERM удаляет origin — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:143` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac1_sigterm_cleans_clone_origin_and_both_process_groups; AC-2 | Сохранить; проверить по AC-2 |
| Сигнальное ожидание | SIGTERM снимает suite — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:145` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac1_sigterm_cleans_clone_origin_and_both_process_groups; AC-2 | Сохранить; проверить по AC-2 |
| Сигнальное ожидание | SIGTERM снимает drive — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:147` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac1_sigterm_cleans_clone_origin_and_both_process_groups; AC-2 | Сохранить; проверить по AC-2 |
| Сигнальное ожидание | SIGHUP удаляет clone — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:141` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac2_sighup_cleans_clone_origin_and_both_process_groups; AC-2 | Сохранить; проверить по AC-2 |
| Сигнальное ожидание | SIGHUP удаляет origin — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:143` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac2_sighup_cleans_clone_origin_and_both_process_groups; AC-2 | Сохранить; проверить по AC-2 |
| Сигнальное ожидание | SIGHUP снимает suite — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:145` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac2_sighup_cleans_clone_origin_and_both_process_groups; AC-2 | Сохранить; проверить по AC-2 |
| Сигнальное ожидание | SIGHUP снимает drive — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:147` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac2_sighup_cleans_clone_origin_and_both_process_groups; AC-2 | Сохранить; проверить по AC-2 |
| Сценарий записи исхода | После каждого из двух сигналов есть строка БД — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:175` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac3_signal_records_non_green_existing_verdict; AC-3 | Сохранить; проверить по AC-3 |
| Сценарий записи исхода | Запись содержит «оборвана сигналом» — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:179` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac3_signal_records_non_green_existing_verdict; AC-3 | Сохранить; проверить по AC-3 |
| Сценарий записи исхода | Запись содержит точное имя каждого сигнала — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:180` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac3_signal_records_non_green_existing_verdict; AC-3, AC-7 | Сохранить; проверить по AC-3, AC-7 |
| Сценарий записи исхода | Вердикт не green — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:182` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac3_signal_records_non_green_existing_verdict; AC-3 | Сохранить; проверить по AC-3 |
| Сценарий записи исхода | Вердикт из прежнего допустимого набора green/red/ceiling — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:183` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac3_signal_records_non_green_existing_verdict; AC-3 | Сохранить; проверить по AC-3 |
| Общие помощники класса | Suite действительно создан для каждого normal/timeout/exception — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:235` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac4_suite_run_stops_on_normal_timeout_and_exception; AC-4 | Сохранить; проверить по AC-4 |
| Общие помощники класса | Suite снят при normal — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:236` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac4_suite_run_stops_on_normal_timeout_and_exception; AC-4 | Сохранить; проверить по AC-4 |
| Общие помощники класса | Suite снят при timeout — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:236` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac4_suite_run_stops_on_normal_timeout_and_exception; AC-4 | Сохранить; проверить по AC-4 |
| Общие помощники класса | Suite снят при exception — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:236` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac4_suite_run_stops_on_normal_timeout_and_exception; AC-4 | Сохранить; проверить по AC-4 |
| Общие помощники класса | RuntimeError ведения не поглощается — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:229` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac4_suite_run_stops_on_normal_timeout_and_exception; AC-4 | Сохранить; проверить по AC-4 |
| Общие помощники класса | Маркер содержит точный pid владельца во время ведения, с границами цифр — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:255` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac5_live_clone_contains_owner_pid_marker; AC-4 | Сохранить; проверить по AC-4 |
| Общие помощники класса | Исключение после наблюдения маркера выходит наружу — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:265` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — test_ac5_live_clone_contains_owner_pid_marker; AC-4 | Сохранить; проверить по AC-4 |
| Барьер перед сигналом | Сигнал мог попасть между публикацией observation и возвратом Popen; детерминированного покрытия сейчас нет — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:46` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — launch_signalled и проверка раннего окна в том же файле; AC-5 | Сохранить; проверить по AC-5 |
| Ожидания launch_signalled | Ожидание observation ограничено 20 секундами — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:126` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — launch_signalled; AC-6 | Сохранить; проверить по AC-6 |
| Ожидания launch_signalled | Ожидание communicate после сигнала ограничено 20 секундами — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:136` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — launch_signalled; AC-6 | Сохранить; проверить по AC-6 |
| Ожидания launch_signalled | Диагностическое communicate ограничено 2 секундами — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:130` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — launch_signalled; AC-6 | Сохранить; проверить по AC-6 |
| Аварийная уборка | Child зарегистрирован для аварийного завершения — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:125` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — launch_signalled и аварийная проверка в том же файле; AC-6 | Сохранить; проверить по AC-6 |
| Аварийная уборка | Группа suite зарегистрирована для аварийного снятия — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:93` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — stop_suites; AC-6 | Сохранить; проверить по AC-6 |
| Аварийная уборка | Группа drive зарегистрирована для аварийного снятия — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:93` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — stop_suites; AC-6 | Сохранить; проверить по AC-6 |
| Аварийная уборка | Известные suite_procs ожидаются с конечным пределом — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:98` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — stop_suites; AC-6 | Сохранить; проверить по AC-6 |
| Аварийная уборка | Clone зарегистрирован для аварийного удаления — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:100` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — stop_suites, launch_signalled; AC-6 | Сохранить; проверить по AC-6 |
| Аварийная уборка | Origin зарегистрирован для аварийного удаления — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:134` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — stop_suites, launch_signalled; AC-6 | Сохранить; проверить по AC-6 |
| Наблюдение процессов | Известные Popen проверяются через poll — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:104` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — alive; AC-2, AC-4 | Сохранить; проверить по AC-2, AC-4 |
| Наблюдение процессов | Остальные PID проверяются на существование, а не предполагаются снятыми — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py:107` | Остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py` — alive; AC-2, AC-4 | Сохранить; проверить по AC-2, AC-4 |

Ссылки на launch_signalled, stop_suites и alive в колонке покрытия обозначают помощники исполняемых тестов, а не самостоятельные test-методы. Для раннего окна и аварийной уборки SPEC.md:74 и SPEC.md:78 требует дополнительные проверки, явно связанные с AC-5/AC-6; это не строка «остаётся, не покрыто» без замены. Матрица не обещает, что текущая случайная доставка сигнала уже является детерминированным воспроизведением.

Раздела «Меняемое поведение» нет. Смена вида утверждений, удаление/переименование методов, skip и смягчение запрещены SPEC.md:22 и SPEC.md:44; разрешённых замен скалярных литералов нет, поэтому проверять пары «было → стало» на main не требуется. Совпадение исходного тестового файла с main проверено. Матрица не даёт мандата на обход гейта неослабления: guard учитывает потерю утверждений помощников (scripts/guard.py:1169), а гейт проверяет и вызывающих вне диффа (orchestrator/advance_gates/test_integrity.py:740).

## Пути обхода гейтов

Проверены следующие способы получить внешне зелёный результат; каждый уже исключён совокупностью требований SPEC:

- Дождаться поздней стадии и убрать окно до возврата Popen. Одних прежних зелёных сигнальных тестов недостаточно: SPEC.md:21 и AC-5 сохраняют раннее окно и запрещают такой барьер как замену покрытия.
- Убить процессы и удалить каталоги аварийным помощником до утверждений, затем предъявить это как продуктовую уборку. Существующий порядок L:139 проверяет результат до addCleanup; требования 2 и 5 вместе с AC-7 требуют красноты при каждой пропущенной продуктовой уборке. Маскирующая уборка дала бы зелёного мутанта и не выполнила SPEC.
- Сделать базу красной искусственным sleep дольше таймаута, назвать причину нагрузкой или показать только повторный зелёный запуск с тем же seed. SPEC.md:19, SPEC.md:28 требуют причинную цепочку исходного отказа, разные классы причин и одинаковое воздействие на обе стороны.
- Измерить только отсутствие PID лидера при сохранении других созданных процессов. AC-2 требует отсутствие групп, AC-6 — всех созданных процессов; проверка alive на L:107 сама по себе не даёт права сузить эти требования.
- Поймать любой отказ мутанта вместо проверяемой потери уборки либо очистить только успешный исход. SPEC.md:23 и AC-7 требуют отдельного обнаружения пяти нарушений и отсутствие утечек после красных результатов.
- Поднять 20 секунд, добавить повторы или заменить процессы моками; изменить продукт/общий helper вне зон. Это прямо запрещено SPEC.md:22, SPEC.md:24 и SPEC.md:96. Поскольку assertions могут остаться текстуально прежними при смягчении помощника, одного зелёного структурного гейта недостаточно; обязательные поведенческие и мутационные проверки сохраняют самостоятельный смысл.

Пути, позволяющего выполнить SPEC буквально и при этом легально обойти перечисленные проверки, не найдено. Перечисленные нарушения — ориентиры проверки реализации, а не разрешённые интерпретации и не новые требования.

## Вердикт

**pass**. Перечень отклонений пуст: требования ТЗ сохранены, факты о коде подтверждены, критерии проверяемы, зоны ограничены, матрица охватывает прежние свойства и требует недостающее покрытие раннего окна/аварийной уборки.

Вердикт относится только к SPEC `9285e0926c8018639a9042eae3c33135c7a0b870`. Он не подтверждает найденную причину CI, готовое исправление или выполненные мутационные прогоны: эти результаты ещё требуются по SPEC.md:28, SPEC.md:36, SPEC.md:38 и SPEC.md:40. Решение о монолите остаётся за Оператором на гейте (SPEC.md:91). SPEC, ТЗ и код не изменялись; полный tests/ и воспроизводитель в аудите не запускались.
