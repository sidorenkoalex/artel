---
task: 01M590GJAF0EDV4NBC4C99MFVH
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 5
---

# REVIEW: G1б — итог тестов компонента из отчёта (JUnit, отчётчик пульта Vitest, окружение и установка пультом)

## Фаза A: план

- PLAN дополнен п. 11 «Итерация 3» и шагом 9: это возврат с приёмки Оператора на `merge_gate`. Код не меняется, добавлены три сторожа. Таблица покрытия требований 1–20 по-прежнему полна.
- Пакет считает инкрементальный diff от `b1fbcddb`, поэтому в нём есть и правки итерации 2 (`acceptance.py`, `suite_run.py`), уже проверенные в прошлый раз. Фактическая итерация 3 — коммит `ea4f6698` (`git show --stat ea4f6698`). В нём только `tests/test_component_report_gates.py` (+169/−7) и карта. Удалённые строки — импорты и докстринг модуля. `orchestrator/artel.py`, `catalog.py`, `tz_check.py` в диапазоне `4d3c0ec2..ea4f6698` пришли подтяжкой main (`c186539c`) и к этой задаче не относятся.
- «Влияние на систему» сходится с диффом. Защищённые пути не тронуты, существующие утверждения тестов не ослаблены: изменён только собственный файл задачи, удалённых `assert` нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 2 |
| 2 | OK | Без изменений |
| 3 | OK | Без изменений (R1-F1 закрыт в итерации 2) |
| 4 | OK | Без изменений |
| 5 | OK | Без изменений; проба с настоящим Node — этап 2 |
| 6 | OK | Без изменений |
| 7 | OK | Без изменений |
| 8 | OK | Без изменений |
| 9 | OK | Без изменений |
| 10 | OK | Без изменений |
| 11 | OK | Без изменений |
| 12 | OK | Новый сторож `EmptyInstallTest`: `install: []` без файла блокировки не даёт ни отказа, ни каталога `deps/`. Заявка подтверждена мутацией `if profile.install is None` (`acceptance.py:480`) |
| 13 | OK | Новые сторожа `ChecksLocalFromRecordTest`: `checks_local` доходит из записи `targets.yaml` через `decide`/`_with_component_fields` до `acceptance_suite` (оба `actor`) и до тела гейта мержа без приложений (`fsm_merge_gate.py:1444`). Обе заявки подтверждены мутациями |
| 14 | OK | Без изменений |
| 15 | OK | Без изменений |
| 16 | OK | Без изменений |
| 17 | OK | Без изменений; AC-20 зелёный |
| 18 | OK | Без изменений |
| 19 | OK | Приложения не менялись (проверены в итерации 1) |
| 20 | OK | Учебные записи на подменённом раннере |

## Замечания

Новых blocker/major нет.

Наблюдение итерации 2 остаётся в силе, в реестр по-прежнему не заведено (minor): передача `reported=` в вызовах `suite_run._base`/`_run` сторожем не закреплена.

## Реестр замечаний

Все записи R1-F1…R1-F6 закрыты (`accepted`) в итерации 2, история — в git этого файла. Новых записей нет.

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

`approved`: реестр закрыт целиком, новых blocker/major нет. Три сторожа итерации 3 ловят заявленные мутации, код ветки не менялся.

## Проверено исполнением

- `python3 -m pytest tests/test_component_report_gates.py`: 13 passed, 10 subtests.
- Временные мутации; после каждой код возвращён, `git status` чист:
  - `project_profile.py:268` `checks_local=()`: `test_record_checks_local_runs_in_acceptance_suite` — 1 failed;
  - удалён вызов `_checks_local_refuse` в `fsm_merge_gate.py:1444`: `test_merge_gate_without_appendices_runs_record_checks_local` — 1 failed, на `assertEqual(self.merge(case), ("stopped",))`;
  - `acceptance.py:480` `if profile.install is None`: `EmptyInstallTest` — 1 failed.
- `artel.py plank-run 01M590GJAF0EDV4NBC4C99MFVH`: 15 passed, код выхода 0.
- `pytest tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py tests/test_suite_run.py tests/test_component_report_run.py`: 48 passed, 41 subtests.
- `python3 scripts/codebase_map.py`: с закоммиченной картой расходится только строка `built_at_sha`; карта возвращена.

## Предложения системе

- Пакет итерации строит инкрементальный diff от `b1fbcddb`, а прошлый вердикт ставили на `4d3c0ec2`. В итоге в diff попали правки уже проверенной итерации 2. Это тот же класс, что T082/T087 в review-checklist: базу инкремента стоит брать от коммита кода, который ревью видело последним.
