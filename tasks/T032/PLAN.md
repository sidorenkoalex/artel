---
task: T032
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: doctor: check_base_branch — догфуд-skip и тесты

## Подход
Добавить в `check_base_branch` (`orchestrator/doctor.py:487`) ранний
`return` для догфуд-target — по образцу уже существующих ранних
выходов в `check_remote_empty` (`orchestrator/doctor.py:473-476`) и
`recovery_check` (`orchestrator/doctor.py:339-348`): сравнение
`name == config.DEFAULT_TARGET` в самом начале тела функции, до любого
обращения к `shutil.which`/`subprocess.run`. Причина skip — одной
строкой, с явным словом «догфуд», объясняющим, что для пульта сверка
базовой ветки с форджем не имеет смысла (тот же смысл, что у соседних
проверок, без привязки к отдельному ADR — chore-уровня изменение).

Тесты — по образцу `RecoveryCheckTest` в `tests/test_doctor.py`
(`tests/test_doctor.py:396-460`): новый класс `BaseBranchCheckTest`,
без реального git/CLI — `check_base_branch` чистая функция, не требует
`TmpRootTest`-песочницы. Обязательный тест — skip на догфуде с
проверкой, что `subprocess.run` не вызывается (иначе тест мог бы
случайно пройти при поломанной проверке, которая просто ловит
отсутствие `gh`). Дополнительно — по одному тесту на оставшиеся ветки
внешнего target (`forge != github`, `gh` не найден, `ok` при
совпадении, `warn` при расхождении) с тем же приёмом подмены
`doctor.subprocess.run`, что уже применяется в `LiveSmokeTest`
(`tests/test_doctor.py:638-666`) — воспроизводимо в песочнице без
сети, закрывает требование 2 SPEC с запасом сверх минимума.

Изменение сигнатуры и порядка вызовов в `all_checks()` не требуется —
задача не создаёт новых веток исполнения `check_base_branch`, только
одну добавляемую.

## Шаги

1. `orchestrator/doctor.py`: ранний skip-return в `check_base_branch`
   для `name == config.DEFAULT_TARGET`. `tests/test_doctor.py`:
   класс `BaseBranchCheckTest` — skip на догфуде (обязателен по
   AC-2) + тесты внешнего target (forge не github, gh не найден,
   ok/warn при сверке).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |

## Влияние на систему
Изменение локально в одной функции `orchestrator/doctor.py:487-513`,
вызываемой только из `all_checks()` (`orchestrator/doctor.py:518+`) —
единственного потребителя. Новая ветка исполнения (early-return для
догфуда) не убирает и не ослабляет существующие проверки: для
внешнего target все ветки (`forge != github`, `gh` не найден,
ok/warn при сверке) остаются как есть — AC-3 требует это явно, и
новые тесты это фиксируют. Тестов не убавляется — только добавляется
покрытие функции, которая раньше не была протестирована напрямую в
`tests/test_doctor.py`. Приёмочные тесты T032
(`tasks/T032/acceptance_tests/test_check_base_branch.py`) залочены
(T023) — не редактируются, код подгоняется под них. Откат —
`git revert` коммита с этим PLAN, изменение не затрагивает схему БД,
конфиги target'ов или FSM.

## Риски
Нет — правка функции без сайд-эффектов вне возвращаемого значения,
без сетевых вызовов на новом пути.
