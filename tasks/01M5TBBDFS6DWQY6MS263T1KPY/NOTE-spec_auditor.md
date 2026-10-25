# Записка spec_auditor — 01M5TBBDFS6DWQY6MS263T1KPY (визит 4, spec_sha 526d8aee…)

## Выяснено
- Находки визита 3 закрыты решением гейта №3 (BEGIN IMMEDIATE, amend-tests для AC-29, проверка эпика до lease, --as-epic только с частями, epic show без журнала, pin = watch._pin_head).
- Новое (вердикт concerns):
  - AC-36: пример «Деление не проходит проверку формата» — на approve такой мягкой проверки нет: fsm.py:1326-1336 только распознаёт секцию, guard.parse_division_subsections (guard.py:5987) не валидирует.
  - lease по id эпика, кроме lease.py:226: doctor/leases.py:96 get_task → doctor падает на мёртвом lease эпика; lease.py:320 warn_foreign_live → release живого чужого lease эпика падает; lease.acquire журналирует «lease взят» без target → target=artel (store.py:780-786), против решения гейта №2 п.10.
  - AC-17 для status вырожден, если в БД нет ни одной задачи с эпиком (требование 13 — вывод прежний).
  - Требование 1: BEGIN IMMEDIATE на каждом store.db() (store.py:409) — замечание, не отклонение.

## Не сработало
- Составные команды Bash (`;`, echo) требуют подтверждения — по одной команде.

## Где остановился
- SPEC-AUDIT.md написан; guard прогнан.

## Чего не хватило
- Перечня мест, зовущих store.get_task по строке leases (doctor/leases.py:96, lease.py:226/320) — искал grep'ом.
