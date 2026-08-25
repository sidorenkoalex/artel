---
task: T032
type: review
author_role: reviewer
status: changes_requested        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: doctor: check_base_branch — догфуд-skip и тесты

## Фаза A — гейт плана

Покрытие: все три требования SPEC покрыты единственным шагом PLAN
(таблица «Покрытие требований» полна). Шаг — одна проверяемая единица
размера MR (правка одной функции + один тестовый класс), не микро- и
не «сделать всё». Подход (`name == config.DEFAULT_TARGET` в начале
тела, до `shutil.which`/`subprocess.run`) прямо повторяет образец
`check_remote_empty`/`recovery_check`, конфликтов с конвенциями нет.
План аппрувится без замечаний.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/doctor.py:490-493` — ранний `skip` для `name == config.DEFAULT_TARGET`, причина содержит «догфуд» и явно исключает трактовку «сверка базовой ветки». Проверено: `check_base_branch(config.DEFAULT_TARGET, entry)` → `skip`, `subprocess.run` не вызывается (см. ниже). |
| 2 | OK | `tests/test_doctor.py:464-522`, класс `BaseBranchCheckTest`, 5 тестов: догфуд-skip (AC-2) + `forge != github`, `gh` не найден, `ok`/`warn` для внешнего target — сверх минимума SPEC. Прогнано: `python3 -m unittest tests.test_doctor.BaseBranchCheckTest -v` — 5/5 ok. |
| 3 | OK | Ветки внешнего target ниже early-return не тронуты байт-в-байт (diff подтверждает — единственная правка это 4 добавленные строки). Приёмочные тесты AC-3 (`tasks/T032/acceptance_tests/test_check_base_branch.py::ExternalTargetUnchangedTest`) и дублирующие в `tests/test_doctor.py` зелёные. |

## Замечания

- minor — `docs/roadmap.md:216` — строка беклога `doctor: check_base_branch | ... | в подметалку` не убрана и не отмечена выполненной, хотя T032 закрывает её содержательно (skip на догфуде + тесты — ровно то, что описано в столбце «Суть»). По прецеденту в истории файла строки с классом «в подметалку» снимаются из таблицы в момент, когда фактически исполняются (см. `git log -p -- docs/roadmap.md`: строка «Дрейф README vs design | ... | $15 в подметалку» исчезла из отдельной строки, когда её content поглотила `Подметалка minor`; сама `Подметалка minor` пополняется по мере разбора). Оставленная строка вводит в заблуждение будущего оператора/agента «Подметалка minor»: тот по-прежнему увидит `check_base_branch` как открытый пункт и либо продублирует работу, либо потратит цикл на проверку, что она уже сделана. Предложение: убрать строку `| doctor: check_base_branch | ... |` из таблицы P3 в этом же MR (SPEC формально это не декларирует, но PLAN «Влияние на систему» не заявляет docs/roadmap.md вне зоны — правка тривиальна и не расширяет объём задачи по существу).

## Проверено исполнением

- `python3 -m unittest tests.test_doctor.BaseBranchCheckTest -v` — 5 passed.
- `python3 -m unittest tests.test_doctor -v` — полный набор `tests/test_doctor.py`, 41 passed (регрессий нет).
- `python3 -m unittest tasks.T032.acceptance_tests.test_check_base_branch -v` — 6 passed (AC-1..AC-3, приёмочные тесты T032 не редактировались).
- `python3 scripts/guard.py tasks/T032/SPEC.md tasks/T032/PLAN.md` — ок (2 файлов).
- Ручная сверка diff `orchestrator/doctor.py`: правка — ровно 4 добавленные строки перед существующей веткой `forge != "github"`, сигнатура и порядок вызова в `all_checks()` (`orchestrator/doctor.py:543`) не менялись.
- `docs/codebase-map.md` регенерирован тем же коммитом (`9d24b01`), что и правка `orchestrator/doctor.py` — конвенция соблюдена.

## Вердикт

`changes_requested` — единственное замечание minor (`docs/roadmap.md:216`,
неубранная строка беклога). Само изменение в `orchestrator/doctor.py` и
тесты корректны, SPEC выполнен полностью (AC-1..AC-3), регрессий нет —
после правки строки роадмапа задача готова к аппруву.
