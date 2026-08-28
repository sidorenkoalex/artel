---
task: T054
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: Авто-ack алертов lease и merge_lock

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `check_leases` (orchestrator/doctor.py:585) собирает `rows_by_task` из свежего `store.all_leases` и зовёт `_auto_ack_gone(conn, "doctor.leases", ...)` на каждом прогоне, не только при находке. `_lease_alert_live` (doctor.py:557) закрывает условие ровно по трём путям SPEC: строки нет, `session_id` другой, pid жив — проверено юнит- и приёмочными тестами (AC-1). |
| 2 | OK | `check_merge_lock` (doctor.py:625) зовёт `_auto_ack_gone(conn, "doctor.merge_lock", ...)` перед единственным `return`, включая ветки «свободен»/«чужой host»/«pid жив». `_merge_lock_alert_live` (doctor.py:572) закрывает условие по замку-пустышке, смене держателя (task_id/session_id) и живому pid — проверено (AC-2), включая отдельный тест на смену держателя с сохранением мёртвого pid у нового (test_doctor.py:926). |
| 3 | OK | `raise_alert` вызывается с теми же аргументами, что и до правки; `alerts.py` не тронут; auto-ack закрывает алерт только когда `is_live` возвращает `False` — то есть строго по факту исчезновения условия. Нераспознанное сообщение → `is_live=True` (безопасный отказ), тот же приём, что у `_branch_alert_live`/`_dir_alert_live`/`_worktree_alert_live`. |
| 4 | OK | Diff ограничен `orchestrator/doctor.py`, `tests/test_doctor.py`, `tasks/T054/*`, `docs/codebase-map.md` — `ci/`, `.github/`, `gates.yaml`, `roles.yaml`, `templates/`, `skills/` не тронуты. Условия завода алерта (`dead`, ветки `check_merge_lock`) переставлены в if/elif ровно с той же семантикой, что и раньше (early-return → накопление в переменную) — проверено прогоном полного набора тестов, поведение не изменилось нигде, кроме добавленного авто-ack. |
| 5 | OK | `python3 -m unittest discover -s tests -v` — 782/782 зелёных. `python3 -m unittest tasks.T054.acceptance_tests.test_auto_ack_leases_merge_lock` — 9/9 зелёных. `python3 scripts/guard.py --all` — 172 файла ок. `python3 scripts/codebase_map.py` без диффа по существу (только `built_at_sha`, что соответствует принятому в репо паттерну "родительский коммит на момент генерации" — см. историю `docs/codebase-map.md` по предыдущим задачам). |

## Замечания

Пусто. Проверено:
- `leases.task_id` — `PRIMARY KEY` (orchestrator/store.py:50), поэтому
  `rows_by_task = {row["task_id"]: row for row in rows}` в
  `check_leases` не теряет строки при коллизии ключа — коллизий нет.
- `merge_locks` хранит не более одной строки одновременно
  (`store.set_merge_lock` делает `DELETE` перед `INSERT`,
  orchestrator/store.py:575) — использование единственного `row` в
  `check_merge_lock`/`_merge_lock_alert_live` корректно во всех четырёх
  ветках функции, включая «чужой host» (проверено на сценарии смены
  держателя с чужого host).
- Regex `_LEASE_ALERT_RE`/`_MERGE_LOCK_ALERT_RE` вручную сверены с
  фактическим форматом сообщений `check_leases`/`check_merge_lock` —
  совпадают.
- Мысленный мутационный тест: заменил `not _pid_alive` на `_pid_alive`
  в `_lease_alert_live`/`_merge_lock_alert_live` — тесты
  `test_dead_pid_still_present_is_not_auto_acked`/
  `test_dead_holder_remains_is_not_auto_acked` и AC-1/AC-2 в
  acceptance_tests обязаны упасть (не запускал руками, но логика теста
  строит ассерт именно на этой ветке — падение гарантировано сменой
  инвертированного условия).

## Вердикт

approved

## Предложения системе

Ни у одного из пяти `_*_alert_live`-предикатов (`_branch_alert_live`,
`_dir_alert_live`, `_worktree_alert_live`, и теперь `_lease_alert_live`,
`_merge_lock_alert_live`) нет юнит-теста на ветку «сообщение не
распознано регуляркой → безопасный отказ, `is_live=True`». Приём
консистентен и задокументирован докстрокой `_auto_ack_gone`, но ветка
деградации при дрейфе формата сообщения ни разу не проверена
исполняемым тестом ни в одном из T035/T054. Не блокер для этой задачи
(AC-3 требует того же приёма, что уже есть — приём воспроизведён верно),
но стоит когда-нибудь закрыть отдельной задачей на весь класс
предикатов сразу.
