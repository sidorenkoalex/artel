---
task: T088
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: Авто-ack алертов: непокрытые источники doctor

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `live_smoke` зовёт `_auto_ack_gone(conn, "doctor.live_smoke", lambda _msg: check.status != "ok")` безусловно после каждого прогона (`orchestrator/doctor.py:377`). |
| 2 | OK | `recovery_check` вводит `sha_mismatch` (побитово та же булева логика, что была в `if`) и зовёт `_auto_ack_gone(..., target=target)` (doctor.py:444-453). Случай «у target больше нет задачи с зафиксированным sha» (`latest is None`) корректно даёт `sha_mismatch=False` → ack; покрыт тестом `test_ac2_no_fixed_task_left_is_auto_acked`. |
| 3 | OK | `dirty = clean is False`, `_auto_ack_gone(..., target=target)` (doctor.py:456-463). |
| 4 | OK | `fsck_failed = fsck.returncode != 0`, `_auto_ack_gone(..., target=target)` (doctor.py:466-475). |
| 5 | OK | `check_task_counters`: `is_behind = next_number < observed`, `_auto_ack_gone(..., target=target)` на каждой итерации цикла, с фиксацией `is_behind` через default-arg лямбды (doctor.py:806-815) — верно избегает позднего биндинга. |
| 6 | OK | `_auto_ack_gone` получил `target: str | None = None`, фильтрует `row["target"] != target` только когда `target is not None` (doctor.py:491-513). Проверено: `test_ac6_*` (4 сценария, sled/crate) в acceptance_tests + `test_target_filter_leaves_other_targets_alone`, `test_ac6_task_counter_other_target_unaffected` в test_doctor.py. |
| 7 | OK | Пока условие живо (лямбда возвращает True) — ack не проставляется; проверено сквозными циклами `test_ac7_*` (3 повторных прогона на каждый из 5 источников). |
| 8 | OK | `alerts.py` не изменён (`git diff main...HEAD -- orchestrator/alerts.py` пуст) — `_auto_ack_gone` вызывает тот же `alerts.auto_ack` без изменений. |
| 9 | OK | `alerts.py` нетронут → `raise_alert`/дедуп/`cmd_alert_ack` не меняются. Булевы переменные (`sha_mismatch`, `dirty`, `fsck_failed`, `is_behind`) — дословная замена исходных `if`-выражений, логика идентична посимвольно (сверено построчно с diff). |
| 10 | OK | `git diff --stat main...task/t088-avto-ack-alertov-nepokrytye-is` — только `orchestrator/doctor.py`, `tests/test_doctor.py`, `docs/codebase-map.md`, артефакты `tasks/T088/`; ни один защищённый путь (`gates.yaml`/`roles.yaml`/`.github/`/`templates/`/`skills/`) не задет. Условия `raise_alert` в трёх местах побитово те же, только обёрнуты в именованные переменные. |

Дополнительно сверено требование «ни одного непокрытого incident-источника
сверх пяти»: `grep -n 'raise_alert' orchestrator/doctor.py` даёт 10 вызовов
(376, 448, 459, 470, 568, 582, 595, 707, 743, 811); `grep -n
'_auto_ack_gone' orchestrator/doctor.py` показывает, что все десять строк
теперь имеют соответствующий вызов `_auto_ack_gone` рядом (шесть
существующих + пять новых, live_smoke/sha/dirty/fsck/task_counter) — SPEC
«Контекст»/«Не входит» подтверждены кодом, не только текстом.

## Замечания

(пусто — 0 blocker/major/minor)

## Вердикт
approved

## Проверено исполнением
- `python3 -m unittest discover -s tests -v` — 1102 теста, все зелёные
  (полный набор, включая новые `AutoAckGoneTargetFilterTest` и
  `test_catching_up_target_is_auto_acked_without_touching_a_lagging_target`
  в `tests/test_doctor.py`).
- `python3 -m unittest tasks.T088.acceptance_tests.test_auto_ack_uncovered_doctor_sources -v`
  — 20 тестов, все зелёные (AC-1..AC-7, включая независимость target
  AC-6 на реальных git-репо `sled`/`crate`).
- `python3 -m py_compile orchestrator/doctor.py tests/test_doctor.py
  tasks/T088/acceptance_tests/test_auto_ack_uncovered_doctor_sources.py`
  — без ошибок.
- `python3 scripts/guard.py tasks/T088/SPEC.md tasks/T088/PLAN.md
  tasks/T088/TZ.md` — «ок (3 файлов)».
- `git diff main...task/t088-avto-ack-alertov-nepokrytye-is --
  orchestrator/alerts.py` — пусто, подтверждает требования 8/9 (ручной
  ack, дедуп, `raise_alert` не тронуты).
- `grep -n 'raise_alert\|_auto_ack_gone' orchestrator/doctor.py` —
  сверка, что все 10 incident-источников `doctor.py` (6 старых + 5 из
  T088) имеют парный вызов `_auto_ack_gone`; иных непокрытых источников
  нет — подтверждает SPEC «Контекст» и «Не входит» кодом.
- `python3 scripts/codebase_map.py` — перегенерировал файл локально,
  сравнил с закоммиченным: тело карты идентично, различается только
  строка `built_at_sha` (ожидаемо — HEAD ветки продвинулся мерж-коммитом
  «подтяжка main» после того, как карта была закоммичена); откатил
  локальную перегенерацию (`git checkout -- docs/codebase-map.md`), в
  ветке изменений не оставил.

## Предложения системе
(пусто)
