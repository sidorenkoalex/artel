---
task: 01M590GJAF0EDV4NBC4C99MFVH
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: G1б — итог тестов компонента из отчёта (JUnit, отчётчик пульта Vitest, окружение и установка пультом)

## Фаза A: план

- В PLAN появился п. 10 «Итерация 2» и шаг 8. Оба покрывают R1-F1…F6 по одному. Таблица покрытия требований 1–20 по-прежнему полна.
- «Влияние на систему» сходится с инкрементальным диффом:
  - правки `orchestrator/acceptance.py` (замок установки, `is_pytest_command`, `acceptance_suite`);
  - правки `orchestrator/suite_run.py` (`parse(..., reported=)`, делегирование `_is_pytest`);
  - новый `tests/test_component_report_gates.py`;
  - регенерированная карта.

  Защищённые пути в ветке не тронуты.
- R1-F6 вынесен Оператору готовым предложением задачи-продолжения с адресом `test_integrity.py:1770-1793` и правкой (PLAN, «Предложения системе», и «Риски»). Код вне зон не тронут. Этого достаточно: прогон закрыт на узле `two_sided.run` (AC-11), а правка вызывающего вне зон SPEC.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Итог из отчёта; argv по отчёту без pytest-аргументов у не-pytest команды (R1-F2 закрыт) |
| 2 | OK | Без изменений с итерации 1 |
| 3 | OK | `acceptance_suite`: проваленный `checks_local` понижает до RED только зелёный итог. «Неизвестно» сохраняется, и `--accept-red` ему отказывает (R1-F1 закрыт, проверено мутацией) |
| 4 | OK | `runner` компонента больше не определяет argv `pult-vitest`. Pytest-аргументы `pytest-own` добавляются только к pytest-команде (`is_pytest_command`) |
| 5 | OK | Без изменений (проба с настоящим Node — этап 2) |
| 6 | OK | Без изменений |
| 7 | OK | Точный argv `pult-vitest` с `workdir` закреплён `ReportArgvTest` |
| 8 | OK | Узлы прогона ветвятся на `_reported`. Вызывающий `test_integrity.py` вне зон вынесен Оператору (R1-F6) |
| 9 | OK | `_is_pytest` делегирует `acceptance.is_pytest_command` — тело прежнее, отказ для записи без `report` прежний (AC-12 п. 2 зелёный) |
| 10 | OK | Сторожа выбора компонентов (дифф + пути приложений) и предела по компоненту — в `tests/` |
| 11 | OK | Без изменений |
| 12 | OK | `fcntl.flock` на `deps/<компонент>/<сумма>.lock`, отметка перепроверяется под замком (R1-F3 закрыт) |
| 13 | OK | `checks_local` в `acceptance_suite` на обоих `actor` и на гейте мержа; сторожа в `tests/` |
| 14 | OK | Без изменений |
| 15 | OK | Сторож `SuiteRunKeyTest`: ключ `suite-run` равен ключу гейта, с `tools` |
| 16 | OK | Без изменений |
| 17 | OK | Прежний разбор не тронут: `parse` без `reported` — прежнее тело; AC-20 зелёный |
| 18 | OK | `suite_run.parse(..., reported=True)` не читает строки хода сырого вывода (R1-F5 закрыт) |
| 19 | OK | Приложения не менялись (проверены в итерации 1) |
| 20 | OK | Учебные записи на подменённом раннере |

## Замечания

Новых blocker/major нет.

Наблюдение без записи в реестр: проводка `reported=` в вызовах `suite_run._base` и `suite_run._run` (`suite_run.py:563`, `:612`) стражем не закреплена. Мутация `reported=False` в обоих вызовах не роняет `tests/test_component_report_gates.py`: `SuiteRunParseReportedTest` зовёт `parse` напрямую. Последствие то же, что у исходного R1-F5 (minor), сама правка верна — запись не завожу.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/acceptance.py:3220-3229 | `checks_local` перекрашивал «неизвестно» в RED | — | Исправлено: незелёный исход сохраняется, к детали дописывается текст проверки. Временная мутация (`if not run.green` → `if False`) роняет 3 теста `AcceptanceSuiteChecksLocalTest`, в том числе цепочку `fsm._acceptance_full_suite_ok` с `--accept-red` |
| R1-F2 | accepted | orchestrator/acceptance.py:742-745 | pytest-аргументы `pytest-own` у не-pytest команды | — | Исправлено. Мутация `own = _own(profile)` роняет 2 теста `ReportArgvTest` |
| R1-F3 | accepted | orchestrator/acceptance.py:495-530 | Установка без замка | — | Исправлено: `flock` вокруг проверки отметки и установки, перепроверка под замком. Мутация «без `LOCK_EX`» роняет `InstallLockTest` |
| R1-F4 | accepted | tests/test_component_report_gates.py | Свойства 10, 13, 15 и `--accept-red` стерегла только разовая планка | — | Сторожа в `tests/` с заявками «Ловит мутацию»; заявки F1/F2/F3/F5 подтверждены временными мутациями (см. ниже) |
| R1-F5 | accepted | orchestrator/suite_run.py:365-375 | `parse` читал строки хода сырого вывода | — | Исправлено: `reported=True` их не читает. Мутация роняет `SuiteRunParseReportedTest` (проводка в вызовах не стерегётся — см. наблюдение в «Замечаниях») |
| R1-F6 | accepted | orchestrator/advance_gates/test_integrity.py:1770-1793 | Двусторонний прогон гейта не по отчёту для компонента без `runner` | — | Вынесено Оператору предложением задачи с адресом и правкой (PLAN, «Предложения системе»); файл вне зон SPEC, код не тронут — путь, предложенный итерацией 1 |

## Вердикт

`approved`. Все записи реестра R1-F1…R1-F6 — `accepted`, новых blocker/major нет.

## Проверено исполнением

- `artel.py plank-run 01M590GJAF0EDV4NBC4C99MFVH`: 15 passed, код выхода 0.
- `pytest tests/test_component_report_gates.py tests/test_component_report_run.py`: 15 passed, 8 subtests.
- `pytest` на 7 файлах: `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`, `test_suite_run.py`, `test_component_checks.py`, `test_full_suite_reuse.py`, `test_pytest_own_result_ids.py`, `test_01m58fnwbv25ff26e7az9q9912_components.py`, `test_01m58pg72pg64gs790xm2ews61_doctor_components.py`. Итог: 86 passed, 209 subtests.
- Временные мутации, прогон `tests/test_component_report_gates.py`; код после каждой возвращён, `git status` чист:
  - F1 (`if not run.green` → `if False`): 3 failed;
  - F2 (`own = _own(profile)` всегда): 2 failed;
  - F3 (без `fcntl.flock LOCK_EX`): 1 failed;
  - F5 (`statuses = _progress(output)` всегда): 1 failed;
  - F5b (`reported=False` в вызовах `_base`/`_run`): 0 failed — см. наблюдение в «Замечаниях».
- `python3 scripts/codebase_map.py`: кроме строки `built_at_sha`, расхождений с закоммиченной картой нет; карта возвращена.

## Предложения системе

- Сторож свойства «узел X получает новый признак» стоит писать через публичного вызывающего, а не прямым вызовом узла с признаком. Иначе проводка признака в местах вызова остаётся без сторожа (здесь `suite_run._run`/`_base` → `parse(reported=)`).
