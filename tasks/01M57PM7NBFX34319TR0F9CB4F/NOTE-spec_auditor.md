# Записка spec_auditor — 01M57PM7NBFX34319TR0F9CB4F (визит 2, spec_sha 41435264)

## Выяснено
- Прежние отклонения О-1…О-5 закрыты решениями гейта и правкой SPEC (треб. 3, 8, 10, 11; матрица 5 строк).
- Факты подтверждены: store.py:701-707/1235/1249/1264, merge_lock.py:56-122, merge_queue.py:41-94, notes.py:281-294, leases.py:162-194, lease_alerts.py:36-49, fsm_merge_gate.py:355/631/1456-1474, fsm.py:1385.
- Неточность: :631 — это `_await_main_ci` (fsm_merge_gate.py:613-631), не «повтор после сдвига main» (SPEC.md:62).
- Сигнатура `touch_heartbeat` с проектом/задачей/сессией не задана; `_wait_for_branch_ci_green` без sid, тесты зовут её 5 аргументами (tests/test_merge_gate_ci_wait.py:91).
- Нормализация проекта (пустой/NULL target, нет строки задачи → DEFAULT_TARGET, store.task_target) не закреплена AC.
- Зоны doctor/* на гейте SPEC задаёт SPEC (answer.py:227-228) — мандат ANSWER не нужен.
- Вердикт: concerns.

## Не сработало
- `ls`/`cd`+git в шелле: ls нет, cd+git требует подтверждения — `git hash-object <абс.путь>` и `git grep` из рабочего каталога работают.

## Где остановился
- SPEC-AUDIT.md записан (concerns, 6 пунктов), guard ок. Шаг завершён.

## Чего не хватило
- Правила, нужен ли мандат ANSWER на расширение зон, сделанное решением гейта SPEC: нашёл в orchestrator/answer.py:219-239.
