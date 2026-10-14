---
task: 01M4XRD6A00G4H5NRMV1KP9QCN
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py, tests/test_01m4xrd6a00g4h5nrmv1kp9qcn_*.py
budget_usd: 40
---

# SPEC: CanaryLifecycleTest: устойчивое доказательство уборки после сигнала

## Контекст

CanaryLifecycleTest минимум дважды остановил verifying чужих задач: CI 38527483950 и pull_request CI 38545242663 (PR #286). Для второго случая ТЗ фиксирует sha `436281bb`, seed `574122182` и `subprocess.TimeoutExpired` на `child.communicate(timeout=20)` после SIGTERM; push того же sha зелёный, повтор pull_request дал 5485 passed. Причина пока не установлена: задержка нагрузки, гонка готовности и удержание pipe остаются гипотезами. Требуется причинное воспроизведение и исправление без потери проверки жизненного цикла.

## Требования

1. Установить причину падения, используя оба известных CI и seed `574122182` как исходные материалы, а не объявляя seed причиной. Детерминированным воздействием на установленную точку гонки или задержки воспроизвести исходное падение. Различить задержку старта, потерю или обработку сигнала, зависание удаления/git и открытые pipe; вывод о причине связать с наблюдениями, а не только с чтением кода или повторным зелёным запуском.
2. Сохранить настоящий публичный маршрут команды canary, настоящий локальный clone и origin, реальные отдельные группы suite и drive и подмену ведения без моделей. Для SIGTERM и SIGHUP сохранить снятие обеих групп, удаление обоих каталогов и запись незелёного исхода с точным сигналом. Все прежние свойства класса и прямых помощников из матрицы ниже сохраняются.
3. Исправить тестовую синхронизацию: готовность к отправке сигнала определяется наблюдаемым условием, а не случайной паузой. Барьер не исключает ранее покрываемое окно раннего сигнала: требуется эквивалентное покрытие этого окна либо отдельная проверка установленного дефекта в нём. Один факт появления observation.json до возврата из подмены Popen сам по себе не доказывает готовность всей уборки.
4. Все ожидания конечны. После успешного и упавшего прогона аварийная уборка завершает созданные процессы, дожидается их завершения и не оставляет сирот или блокирующих pipe. Предел `child.communicate(timeout=20)` не увеличивается; retries, skip, xfail, замена реальных групп заглушками и ослабление assertions запрещены. Продуктовое время остановки не расширяется.
5. Под одним и тем же установленным воспроизводимым воздействием база должна быть красной по исходной причине, а исправление — зелёным. После обоих исходов проверить отсутствие утечек процессов и каталогов и блокирующих pipe. Проверки после исправления должны ловить мутации пропущенной уборки suite, drive, clone, origin и неправильной записи сигнала.
6. Производственные ограничения сохраняются. Изменения `orchestrator/canary.py` и `orchestrator/liveness.py` допустимы только при доказанном продуктовом дефекте, обосновании дефекта и минимальной правки аналитиком в SPEC и согласовании такого SPEC. На момент составления документа продуктовый дефект не доказан, поэтому эти файлы не включены в разрешённые зоны изменения. Обнаружение такого дефекта требует возврата на согласование SPEC до продуктовой правки; изменение продукта только ради удобства теста запрещено.

## Критерии приёмки

AC-1. Представлено детерминированное воспроизведение исходного падения: указаны точка и способ воздействия, команда, наблюдения, объясняющие причинную цепочку, и результаты базы и исправления. Разобраны оба известных CI и seed `574122182`; различены задержка старта, потеря/обработка сигнала, задержка удаления/git и удержание pipe. База падает именно по установленной исходной причине, исправление проходит при том же воздействии (требования 1, 5).

AC-2. Для каждого из SIGTERM и SIGHUP через настоящий публичный маршрут canary с локальными clone/origin и реальными отдельными группами suite/drive проверяются отсутствие обеих групп и обоих каталогов после сигнала. Ведение остаётся подменённым без запуска моделей (требование 2).

AC-3. Для каждого сигнала после прерванного прогона есть запись в БД; её outcome/kill_note содержит `оборвана сигналом` и точное имя полученного сигнала. Вердикт не равен `green` и принадлежит прежнему набору `green`, `red`, `ceiling` (требование 2).

AC-4. Сохраняются проверки всего остального поведения класса: suite действительно создан и снят при normal, timeout и exception; RuntimeError в сценарии exception не поглощается; во время ведения клона наблюдается маркер с точным pid владельца, а исключение после наблюдения маркера распространяется наружу. Покрытие каждого свойства соответствует отдельной строке матрицы (требование 2).

AC-5. Наблюдаемый критерий готовности заменяет зависимость от случайного планирования. Проверка раннего сигнала остаётся эквивалентной прежнему покрытию либо отдельно проверяет установленный дефект раннего окна; барьер готовности не является способом исключить это окно из проверки (требование 3).

AC-6. Успешный прогон, детерминированно упавший прогон базы и аварийный выход из ожидания завершаются конечной уборкой всех созданных процессов с ожиданием завершения. Проверка после уборки не находит сирот, оставшихся clone/origin или блокирующих pipe. Предел 20 секунд не увеличен, все ожидания конечны, retries/skip/xfail не добавлены, assertions не ослаблены, продуктовый срок остановки не расширен (требования 4, 5).

AC-7. Мутационные проверки дают красный результат для каждого из пяти нарушений отдельно: не снята группа suite; не снята группа drive; не удалён clone; не удалён origin; записано неправильное имя сигнала. После этих проверок также не остаётся утечек (требование 5).

## Матрица неослабления

Адреса и свойства «сейчас» сверены по рабочему дереву задачи. Колонка «после» задаёт обязательное покрытие исправления, а не отчёт об уже выполненных прогонах. Все ссылки на методы ниже относятся к классу CanaryLifecycleTest. Имена существующих методов и строгость утверждений сохраняются; новые проверки дополняют их. Мандата на ослабление эта матрица не даёт.

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

## Оценка объёма и деление

Сигнал: budget_usd ≥ $30. Семь критериев, один существующий тестовый файл и относящиеся к задаче новые тесты; бюджет $40 по классу до десяти критериев и четырёх файлов, с двумя итерациями ревью, ниже рамки ТЗ $50. Новые тесты в зоне с идентификатором задачи проверяют недостающие свойства; повторно заказывать уже существующее покрытие отдельным дубликатом не требуется.

Обоснование монолита: причинное воспроизведение, исправление синхронизации и доказательство сохранения раннего окна относятся к одному сценарию и его помощникам. Отдельное включение воспроизводителя оставило бы планку красной; отдельный барьер без проверки раннего окна мог бы скрыть дефект. Деление по этим частям не даёт самостоятельного завершённого исправления с зелёной планкой. Решение о монолите принимает Оператор на гейте SPEC.

## Не входит

- SuiteObservationTest, общий механизм canary-stop, уборка всех сирот вне теста, общая песочница ролей и остальные пункты копилки.
- Изменения общих helpers, конфигов и защищённых файлов без отдельного решения.
- Изменения `orchestrator/canary.py` и `orchestrator/liveness.py` до доказательства продуктового дефекта и согласования SPEC с обоснованием минимальной правки (требование 6).
- Полный прогон tests/ внутри шагов ролей; обязательные гейты и непревышение бюджета держит пульт, отдельными AC они не становятся.
- Самостоятельное повышение рамки $50 и мерж: запуск доводится до ручного гейта SPEC, мерж — отдельной командой Оператора.

## Материалы

- Источник требований: TZ.md этой задачи, пункты 1–5 и границы зон.
- Исходные материалы расследования из ТЗ: CI 38527483950 (задача 01M4VKZR1VE6KS2HECJ05ABCYR); pull_request CI 38545242663 (PR #286, sha 436281bb, seed 574122182). Логи этих CI в шаге аналитика не читались; их содержимое выше передано по ТЗ, причина падения не подтверждена.
- Кандидат на исследование, не диагноз: публикация observation в тесте:46–49 предшествует возврату Popen; `orchestrator/canary.py:2333` присваивает proc перед защищённым wait. Вывод drive направлен в файл (`orchestrator/canary.py:2331`), поэтому удержание pipe child этим процессом нельзя считать установленным только по факту его жизни.

## Предложения системе

В окружении роли cat отсутствует в PATH (exit 127); чтение выполнено через pathlib штатного python3. Полезно явно перечислить доступные утилиты чтения в брифе.
