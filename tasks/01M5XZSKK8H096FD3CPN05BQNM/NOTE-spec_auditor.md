## Выяснено
- SPEC (sha d7e14b37) точно переносит требования 5–7 и AC-14…AC-24 SPEC родителя (`git show refs/artifacts/01M5XX9PW3K206Q3EKQCT649QF:tasks/01M5XX9PW3K206Q3EKQCT649QF/SPEC.md`). Все строки в outcome_integrity.py, fsm_advance.py и fsm_merge_gate.py сверены с кодом (вызов обёртки — :1518, `_ci_ready_or_wait` — :1522).
- `forge.JobResult` не несёт `allow_failure`, оно есть только в `pipeline_status().jobs` (`forge.Job`). `gitlab_adapter._last_attempt` :449 выбирает наибольший id. Повтор ключа в отчёте адаптер сам превращает в None.
- Части 1 (01M5XZSKK8GZ…) в main нет: полей `full_suite`/`ci_job` в project_profile.py нет.
- Вердикт — concerns, пункты К1–К7. Главный — К1: неоднозначный тест базы молча выпадает из PASS_TO_PASS, хотя строка матрицы SPEC.md:214 говорит обратное.
## Не сработало
- `artel.py show` из рабочего каталога отказывает (нужна главная копия). Проверить в БД start_after и merge_after задачи не удалось.
## Где остановился
- SPEC-AUDIT.md написан, guard ок, status: ready.
## Чего не хватило
- Как division проставляет start_after частям (merge_after.division_order) — не дочитал. Отсюда К4 сформулирован как вопрос Оператору.
