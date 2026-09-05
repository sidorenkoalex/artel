---
task: 01M1PNBSHR2PMFECMP7C204MF1
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 4
---

# REVIEW: Роль в своей группе процессов: таймаут, kill, pause --now бьют дерево; сторож зависших прогонов

## Фаза A: гейт плана

PLAN.md (developer, status: ready) — монолитный MR, обоснование не-разреза
дословно повторяет и подкрепляет «Оценка объёма и деление» SPEC (pgid без
group-kill нетестируем содержательно; group-kill нечем бить без заведённой
группы; сторож переиспользует тот же примитив). Таблица «Покрытие
требований» полна — каждый AC-1..AC-16 привязан к шагу. Шаги —
проверяемые единицы (общий примитив → точки вызова → сторож → тесты), не
микрооперации и не «сделать всё разом». Подход не конфликтует с
конвенциями: `liveness.py` остаётся листом графа импортов (только
stdlib), водораздел «наблюдение/действие» (`check_*` не бьёт, `--fix`
бьёт) — тот же приём, что уже применяет `check_leases`/
`_fix_ignored_artifact_files`. «Влияние на систему» и «Откат» заполнены и
соответствуют фактическому diff (аддитивная колонка `leases.pgid`,
никаких side effects вне заявленной зоны). Замечаний по плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (новая группа процессов, AC-1/AC-13) | OK | `runner.spawn_agent`: `kwargs.setdefault("start_new_session", True)`; AC-1/AC-13 acceptance-тесты зелёные. |
| 2 (group-kill на всех путях, AC-2..AC-7) | OK | `liveness.terminate_process_group`/`group_kill_detail` — общий примитив; 4 точки вызова (`runner` таймаут, `cleanup._group_kill_lease_step`, `pause.cmd_pause_now`, `release.cmd_release`) + `doctor._fix_dead_lease_groups` под `--fix` (AC-6, doctor-путь). Журнал факта добивания — везде (AC-7). |
| 3 (сторож зависших прогонов, AC-8..AC-12) | OK | `doctor.check_hung_test_runs`/`_fix_hung_test_runs`: `kind=incident` (ANSWER-1, вопрос 1), авто-ack тем же приёмом, что `_auto_ack_gone`; `--fix` гейтует снятие (AC-12). |
| 4 (существующие тесты без ослабления, AC-16) | OK | T041/T074/T044/T062 не тронуты диффом; прогнаны реально (см. «Проверено исполнением»), все зелёные. |
| AC-1..AC-16 | OK | Все 16 файлов `acceptance_tests/` этой задачи прогнаны по отдельности вживую — зелёные (см. ниже). Manual/skip-пометок в наборе нет — полное автоматическое покрытие. |

## Замечания

- minor — `orchestrator/doctor.py:1169-1170` — между новой функцией `_fix_dead_lease_groups` и существующей `check_zone_waits` нет обычных двух пустых строк (PEP8/конвенция файла — везде в файле, включая соседние новые функции этой же задачи, разделение выдержано) — читается как одно тело. Не влияет на поведение и не ловится линтом в CI (в `.github/workflows/*.yml` линт-шага нет). Разработчик правку не обязан вносить отдельным циклом — ниже закрыто вердиктом ревьювера как не блокирующее мерж.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/doctor.py:1169-1170 | нет двух пустых строк между `_fix_dead_lease_groups` и `check_zone_waits` | чистая косметика (нет лимита строк/линт-CI, поведение не меняется) — ревьювер закрывает без цикла разработчика | замечание зафиксировано, правка не требуется; поправить можно попутно при следующем touch файла |

## Вердикт

approved

Единственное замечание — minor (косметика, не влияет на поведение и не
ловится CI-линтом): 0 blocker/major → approved по правилам чеклиста.
Реестр закрыт целиком (R1-F1 сразу `accepted` — правки не требует), гейт
`review -> verifying` пройдёт.

## Проверено исполнением

- `python3 -m unittest tests.test_timeout_checkpoint tests.test_pause_now tests.test_lease tests.test_release tests.test_lease_pgid_store tests.test_liveness tests.test_doctor tests.test_kill_cleanup tests.test_agent_log -v` — 250 тестов, все зелёные (T041/T074/T044/T062 регрессия без ослабления + новые юнит-тесты `test_lease_pgid_store.py`/`test_liveness.py`).
- Все 16 файлов `tasks/01M1PNBSHR2PMFECMP7C204MF1/acceptance_tests/` прогнаны по отдельности напрямую (`python3 <файл> -v`): `test_ac1_spawn_agent_new_process_group.py`, `test_ac2_pgid_recorded_alongside_pid.py`, `test_ac3_timeout_kills_step_group.py`, `test_ac4_kill_command_kills_lease_group.py`, `test_ac5_pause_now_kills_step_group.py`, `test_ac6_dead_lease_group_cleanup.py`, `test_ac7_group_kill_count_journalled.py`, `test_ac8_hung_test_run_age_threshold.py`, `test_ac9_hung_test_run_lease_filter.py`, `test_ac10_hung_test_run_alert_lifecycle.py`, `test_ac11_doctor_fix_group_kills_hung_test_run.py`, `test_ac12_doctor_without_fix_leaves_hung_test_run_alone.py`, `test_ac13_agent_step_pgid_differs_from_pult.py`, `test_ac14_role_step_group_kill_shell_stub.py`, `test_ac15_hung_test_run_found_vs_leased_untouched.py`, `test_ac16_existing_regression_suite_stays_green.py` — все `OK`.
- `python3 scripts/codebase_map.py` в чистом дереве ветки, сравнение с закоммиченным `docs/codebase-map.md` без строки `built_at_sha` (`git diff` после регенерации) — расхождений нет, карта свежая; результат отменён (`git checkout -- docs/codebase-map.md`), код не правился.
- Просмотрен полный diff `main...task/01m1pnbshr2pmfecmp7c204mf1-rol-v-svoey-gruppe-protsessov` (13 файлов) — изменения не выходят за заявленную SPEC зону, защищённые пути (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) не тронуты, `tests/` не ослаблены (diff их не касается).

## Предложения системе

- PLAN.md, раздел «Подход», п.4: обоснование выбора `kind=incident` («не warning, которого нет в alerts.KINDS») фактически неточно — `alerts.KINDS` СОДЕРЖИТ `"warning"` (`orchestrator/alerts.py:55`). На код и вердикт это не влияет (ANSWER-1 прямо предписывает `incident` независимо от этого аргумента), но формулировка вводит в заблуждение будущего читателя PLAN.md.
