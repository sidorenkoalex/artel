---
task: T060
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 2
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: Лимитер параллельных задач: MAX_PARALLEL_TASKS=2

## Фаза A: проверка плана

PLAN.md «Подход» синхронизирован со SPEC требованием 2: формулировка
теперь дословно несёт квалификатор «на своём host» (PLAN.md, раздел
«Подход», второй абзац), с явной отсылкой на приём
`doctor.check_leases`/`check_merge_lock`/`merge_lock._holder_is_dead` —
замечание из итерации 1 закрыто. Остальное по Фазе A не изменилось
относительно итерации 1: таблица покрытия полна, шаги — единицы размера
MR, подход не заводит новый конечный автомат.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `config.MAX_PARALLEL_TASKS = 2` (без изменений с итерации 1). |
| 2 | OK | `orchestrator/parallel_limit.py:28-33` — `busy_other_tasks` теперь гейтит `liveness._pid_alive` по `row["hostname"] == host` (строка 32), для чужого host `_pid_alive` не зовётся, строка считается занятой; heartbeat по-прежнему host-независим (строка 30). Совпадает буквально с приёмом `doctor.py:610-613`/`merge_lock.py:38-39`. |
| 3 | OK | Без изменений с итерации 1. |
| 4 | OK | Без изменений с итерации 1. |
| 5 | OK | Без изменений с итерации 1. |
| 6 | OK | `test_invariants.ParallelTaskLimitIsNotBypassableTest` без изменений с итерации 1 — не ослаблен, сеет занятые задачи на своём host (для host-гейта достаточно юнит-покрытия в `test_parallel_limit.py`, дублировать не обязательно). |
| 7 | OK | `python3 -m unittest discover -s tests` — 820/820 зелёных (прогнано вручную; было 818, +2 новых теста на чужой host). |

## Замечания

Замечаний нет. Блокер итерации 1 (`orchestrator/parallel_limit.py:23`,
отсутствие host-гейта перед `_pid_alive`) устранён точно предложенным
способом: `row["hostname"] == host and not liveness._pid_alive(...)`
(`orchestrator/parallel_limit.py:32`), докстринг модуля дополнен
объяснением приёма (строки 10-16), PLAN.md синхронизирован со SPEC.
Добавлены два целевых теста в `tests/test_parallel_limit.py`:
`test_foreign_host_counts_even_with_locally_dead_pid` (чужой host с
локально мёртвым pid всё равно считается занятым — прямая проверка
исправленного сценария поломки из итерации 1) и
`test_foreign_host_with_stale_heartbeat_is_still_excluded` (heartbeat
по-прежнему host-независим и решает первым). Мутационный тест: откат
строки 32 к `if not liveness._pid_alive(row["pid"]):` уронит именно
`test_foreign_host_counts_even_with_locally_dead_pid` — тест ловит
регрессию класса, а не только конкретный экземпляр.

`docs/codebase-map.md` перегенерирована тем же коммитом
(`built_at_sha` = HEAD `1971947...`), правок `*.py` в orchestrator/,
scripts/ или tests/ без обновления карты нет.

Ранее известный дефект (не блокер этой итерации, тот же диагноз, что и
в итерации 1 и в PLAN.md «Риски»): `tasks/T060/acceptance_tests/
test_max_parallel_tasks.py::Ac5GateAndReadonlyCommandsIgnoreLimiterTest::
test_ac5_kill_ignores_the_limiter` красный (перепроверено вручную,
11/12 в файле зелёные). Ассерт ожидает удаления строки `tasks` из БД —
поведение, которого `cleanup.cmd_kill` никогда не имел
(`orchestrator/cleanup.py:150-178`, состояние переводится в `killed`,
строка остаётся историей; `tests/test_kill_cleanup.py` целиком проверяет
именно это как штатное). Файл теста залочен (T023), правка вне
полномочий разработчика и вне зоны SPEC T060. Требование 5 (лимитер не
блокирует `kill`) подтверждено тремя другими сценариями AC-5
(approve/reject/status), зелёными.

## Вердикт

approved — блокер итерации 1 устранён именно предложенным способом
(host-гейт `_pid_alive` по образцу `doctor.py`/`merge_lock.py`), PLAN.md
синхронизирован со SPEC, добавлены целевые тесты на чужой host, карта
кодовой базы актуальна. Все 820 тестов `tests/` прогнаны вручную и
зелёные (кроме независимого от лимитера, ранее известного и вне-зонного
дефекта локнутого acceptance-теста AC-5/kill, см. замечания выше —
задокументирован в PLAN.md «Риски» и не блокирует требования T060).

## Предложения системе

- Правка итерации 1 подтверждает наблюдение прошлого REVIEW: тот же
  класс «забыли гейтить `liveness._pid_alive` по хосту» теперь решён
  верно в четырёх местах (`doctor.py` x2, `merge_lock.py`,
  `parallel_limit.py` — после правки), но каждый раз как отдельный
  ручной прецедент, а не общий хелпер. Стоит вынести
  `liveness.pid_alive_on_own_host(row)` — тогда пятый читатель
  `leases`/`merge_locks` не сможет забыть проверку структурно, а не
  дисциплиной ревью.
