---
task: 01M4VC31NFCS6JZ0VE8HNJ7FYM
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Чистый прогон канарейки учитывает эскалацию аудитора SPEC по той же ловушке

## Подход
Роли эскалаций вычисляет пульт из `steps` результата клона, не код клона:
`_DRIVE_METRIC_FIELDS` и разбор результата не меняются (требование 1, AC-4).

- `orchestrator/canary.py::escalation_roles(steps)` — один проход по
  журналу: текущее состояние-источник (стартовое `spec_writing`)
  обновляется каждым `state -> X` кроме `escalated`; на каждом
  `state -> escalated` ищется маркер `fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER`
  среди записей до следующего `state -> …`. Есть маркер — роль состояния
  (`spec_writing` → `analyst`, прочие по `config.STATE_ROLE`, вне карты —
  `unknown`); нет — `unknown`. Сравнивается только `action`.
- `_run_one_task` передаёт `escalation_roles(steps)` в `_record_canary_run`
  (новый именованный параметр, по умолчанию `None`), тот — в
  `store.insert_canary_run(escalation_roles=…)`. Строки
  `_report_drive_failure` и оборванного сигналом прогона не меняются —
  `NULL` по умолчанию.
- `store.py`: колонка `escalation_roles TEXT` в `CREATE TABLE` и
  `add_column` без DEFAULT (старые строки — `NULL`, требование 4);
  запись — `",".join(roles)`, `[]` → `''`, `None` → `NULL`.
- `models.unclean_reason`: после проверки «ожидаемой с верным исходом нет»
  (неизменна — требование 3) при данных о ролях — первая по порядку роль
  вне `{analyst, spec_auditor}` или с повтором даёт причину
  `эскалаций роли <роль>: <число>`; без данных о ролях (`NULL` или ключа
  нет: `KeyError`/`IndexError`) — прежняя ветка `escalations > 1`.
  `pair_admission` читает `unclean_reason` — правка не нужна (требование 5).

## Шаги
1. `store.py` — колонка, миграция, параметр `insert_canary_run`.
2. `canary.py` — `escalation_roles`, прокладка в `_record_canary_run`.
3. `models.py` — правило ролей в `unclean_reason`.
4. Свой тест `tests/test_canary_escalation_roles_storage.py` (`[]` → `''`,
   по умолчанию `NULL`) — свойство, не покрытое долгоживущим файлом;
   проверен мутацией `roles or None` (красный), код возвращён.
5. Карта `python3 scripts/codebase_map.py`.
6. Итерация 2 (R1-F1): сторож связки `_run_one_task` → колонка
   `escalation_roles` в `tests/test_canary_escalation_roles_storage.py`
   (`RunOneTaskRecordsEscalationRolesTest`): подменён только
   `_run_task_in_ephemeral_clone`, строка несёт `analyst,spec_auditor`,
   `escalations = 2`. Мутация `escalation_roles=None` в `canary.py:2633` —
   тест красный, код возвращён.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2, 4, 6 |
| 2 | 3 |
| 3 | 3 (проверка `expected_escalation_met` стоит раньше ветки ролей) |
| 4 | 1 (без DEFAULT), 3 (`None` → прежняя ветка) |
| 5 | 3 (`pair_admission` берёт причину из `unclean_reason`) |
| 6 | долгоживущий `tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py`, планка, шаг 4 |

Проверено: долгоживущий файл задачи (12 тестов) и планка (`plank-run`,
3 passed) зелёные; `tests/test_model_sets.py`,
`tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`,
`tests/test_canary_drive.py`, `tests/test_canary_codex_clone_auth.py`,
`tests/test_store_schema_migration_parity.py` — 80 passed.

## Влияние на систему
- Критерий чистоты смягчается только для строк с данными о ролях и
  только на шаблоне с выполненной ожидаемой эскалацией: допускается по
  одной эскалации `analyst` и `spec_auditor` вместо одной любой. Эскалация
  пульта (без маркера) даёт `unknown` и пачкает прогон — строже прежнего.
  Пороги допуска ADR-0019 п.5 и прочие условия (вердикт, итерации ревью,
  отказ автогейта) не тронуты.
- Схема: новая nullable-колонка, миграция идемпотентна (`add_column`),
  прежние строки остаются `NULL` и разбираются прежним правилом.
- `_record_canary_run` получил параметр с умолчанием — прежние вызывающие
  (`tests/test_canary_drive.py`, подмена в `test_canary_codex_clone_auth.py`)
  работают без изменений.
- Откат — revert коммита задачи; колонка в БД остаётся и не мешает.

## Риски
- Журнал клона, где маркер пишется после иного действия, чем ожидается,
  не влияет: граница поиска — только следующий `state -> …`.

## Предложения системе
- Bash-обёртка роли просит подтверждения на `sed -i`/`awk`/`find` после `cd`
  — временная мутация сторожа удобнее через Edit; стоит упомянуть это в
  coding-standards.md рядом с правилом проверки сторожа мутацией.
