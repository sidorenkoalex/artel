---
task: 01M4VC31NFCS6JZ0VE8HNJ7FYM
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Чистый прогон канарейки учитывает эскалацию аудитора SPEC по той же ловушке

## Фаза A — план
- Таблица покрытия полна (требования 1–6), шаги размера MR, подход совпадает
  с SPEC: роли считает пульт из `steps`, `_DRIVE_METRIC_FIELDS` не тронут.
- «Влияние на систему» соответствует diff: `canary.py`, `models.py`,
  `store.py`, новый тест; путь отката описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK, но без сторожа в `tests/` | `canary.py::escalation_roles`: источник — последний `state -> X` (старт `spec_writing`), маркер ищется до следующего `state -> …`, сравнивается только `action`; колонка и `add_column` без DEFAULT; `None` → `NULL`, `[]` → `''`. Передача из `_run_one_task` (`canary.py:2633`) не охранена ни одним тестом `tests/` — см. R1-F1 |
| 2 | OK | `models.py::_excess_escalation_role` — первая роль по порядку перечня вне `{analyst, spec_auditor}` либо с повтором; причина `эскалаций роли <роль>: <n>` |
| 3 | OK | ветка ролей стоит после `escalations != 0 and not expected_escalation_met` — без ожидаемой любая эскалация не чистая (AC-8 зелёный) |
| 4 | OK | `_escalation_roles_of` даёт `None` и на `NULL`, и на отсутствующий ключ (`KeyError`/`IndexError`) → прежняя ветка `elif escalations > 1`; миграция оставляет у старых строк `NULL` (AC-9) |
| 5 | OK | `pair_admission` берёт причину из `unclean_reason`, пороги не тронуты |
| 6 | OK | долгоживущий файл задачи + `tests/test_canary_escalation_roles_storage.py` |

## Замечания

- major — `orchestrator/canary.py:2633` (`escalation_roles=escalation_roles(steps)`
  в `_run_one_task`) — связку «результат клона → `escalation_roles(steps)` →
  колонка строки `canary_runs`» (требование 1, AC-1 вторая часть, AC-4)
  проверяет только планка `acceptance_tests/test_run_one_task_escalation_roles.py`,
  а она помечена `Группа: разовый`. После мержа её не гоняет ни CI, ни автогейт
  (ADR-0018 п.3), поэтому это свойство кода остаётся без сторожа. Проверено временной мутацией:
  `escalation_roles=None` вместо `escalation_roles(steps)` → `tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py`,
  `tests/test_canary.py`, `tests/test_canary_drive.py`,
  `tests/test_canary_codex_clone_auth.py`, `tests/test_canary_template_flag.py`,
  `tests/test_canary_escalation_roles_storage.py` — 172 passed, ни одного
  красного. Сценарий: рефакторинг `_run_one_task`/`_record_canary_run` теряет
  аргумент — все новые строки пишутся с `NULL` и молча читаются по старому правилу
  (`escalations > 1` — не чистый). Пары на шаблонах с ловушкой снова не
  проходят `admit`, и ни один тест этого не покажет. Предложение: в `tests/`
  (например в `tests/test_canary_escalation_roles_storage.py` либо рядом с
  тестами `_run_one_task` в `tests/test_canary_drive.py`, которые уже подменяют
  процесс клона) добавить тест: `_run_one_task` с подменённым результатом клона,
  в `steps` которого эскалации `analyst` и `spec_auditor` с маркерами, пишет
  строку с `escalation_roles == "analyst,spec_auditor"`. Заявка — «Ловит мутацию:
  `_run_one_task` не передаёт роли в `_record_canary_run` — колонка `NULL`».
  Мутацию проверить так же, как выше. Долгоживущий файл задачи сам эту связку
  не держит (его заявки — про функцию и критерий), так что повтором не будет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/canary.py:2633 | передачу ролей из `_run_one_task` в строку `canary_runs` проверяет только разовая планка, сторожа в `tests/` нет (мутация `escalation_roles=None` — 172 passed) | после мержа потеря аргумента молча вернёт все строки к `NULL` и старому правилу чистоты, `admit` на шаблонах с ловушкой снова блокируется без красного теста | тест в `tests/` на `_run_one_task` с подменённым результатом клона: строка несёт `analyst,spec_auditor`; проверить временной мутацией |

## Вердикт
changes_requested — закрыть R1-F1 (сторож в `tests/` для связки
`_run_one_task` → колонка `escalation_roles`). Сама логика `escalation_roles`,
хранения и критерия чистоты замечаний не имеет.

## Проверено исполнением
- `pytest tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py tests/test_canary_escalation_roles_storage.py tests/test_model_sets.py tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py tests/test_canary_drive.py tests/test_store_schema_migration_parity.py` — 57 passed, 32 subtests passed.
- `artel.py plank-run 01M4VC31NFCS6JZ0VE8HNJ7FYM` — 3 passed, код выхода 0.
- Временная мутация `canary.py` (`escalation_roles=None` в вызове `_record_canary_run` из `_run_one_task`) + шесть файлов `tests/` про канарейку и роли — 172 passed, 38 subtests (мутация не поймана → R1-F1); код возвращён `git checkout`, `git status` чист.
- `python3 scripts/codebase_map.py` → diff `docs/codebase-map.md` только в строке `built_at_sha`, карта свежая; файл возвращён.

## Предложения системе
- Планка, которая подменяет закрытые имена `canary`, уходит в группу «разовый» из-за запрета таких подмен в долгоживущем файле. Тогда свойство кода (связка пульта) остаётся без сторожа после мержа, если разработчик не добавит свой тест. Стоит, чтобы test-authoring/PLAN явно передавали такую связку разработчику пунктом «сторож в `tests/` за тобой».
