# Записка spec_auditor (круг 3, spec_sha 3c6483ea)

## Выяснено
- Все места decide()/profile_of() в контексте задачи теперь в таблице SPEC (grep по orchestrator/).
- Ошибка прошлого круга аудита: fsm_merge_gate.py:1093 у записи из нескольких компонентов НЕДОСТИЖИМА — _full_suite_command отдаёт кортеж профилей (:853–856), таймаут идёт веткой :1086–1091 (предел компонента). TargetsError там нет; AC-27 стоит на ложной посылке.
- fsm_advance.py:609 — FAIL_TO_PASS добавляется только при in_outcome_bounds профиля задачи: чужой файл X в границе у задачи Y вне границы не проверяется.
- mandate._outcome_profile канарейку не проверяет («как сейчас» в SPEC неверно).
- matrix_refusals (mandate.py:584, _covered/_component_covered) — покрытие только по профилю задачи: строка «остаётся, покрыто frontend:…» у задачи backend получит отказ на answer.
- review.py:691 фильтр по границе профиля задачи: у задачи вне границы строки потребителя скрыты.

## Не сработало
- Команда bash с `cd … &&` и `$?` — отказ «simple_expansion»; guard гонять абсолютным путём без $.

## Где остановился
- SPEC-AUDIT.md: status ready, verdict concerns, 7 отклонений; guard ок.

## Чего не хватило
- Ветвление по типу command в _merge_full_suite (isinstance tuple, :1069/:1086) — без него :1093 кажется достижимой.
