# Записка analyst — 01M590GJAF0EDV4NBC4C99MFVH (G1б)

## Выяснено
- Шаг 3 (после ANSWER-1): Оператор ответил на все 8 вопросов — 1–4, 6–8 вариант A; 5 — без правки `fsm.py`: «неизвестно» выдаётся исходом `acceptance.FULL_SUITE_NOT_STARTED` с деталью «итог неизвестен: <причина>», `approve --accept-red` отказывает ему через существующую ветку `fsm.py:1304`.
- Пункты «Закрывается в SPEC без вопроса» (А1, Г3, Е2, Г2, Б1) приняты — внесены в SPEC.
- Места прогона планки на гейтах: `acceptance.run` (`:713`) из `advance_gates/acceptance.py:405,408`, `pull.py:668,671`, `amend.py:554,728`; `run_repeat` (`:1032`) из `advance_gates/acceptance.py:169`.
- `repo_context.profile_of` (только чтение) у записи с одним компонентом отдаёт только подполя `PROFILE_FIELDS` (`repo_context.py:164-172`) — `report_args`/`checks_local`/`failure_errors` компонента надо брать через `project_profile.components`.

## Не сработало
- Первый SPEC: различитель «report и runner ≠ pult-pytest» не покрыл компоненты без `runner` из черновика ADR.

## Где остановился
- SPEC.md переписан по ANSWER-1 (20 требований, AC-1…AC-21, status: ready), guard ок; QUESTIONS.md удалён. В оболочке шага нет `rm`/`ls` — файлы удалял через `python3 -c os.remove`.

## Чего не хватило
- Порядка шагов в теле гейта мержа (`fsm_merge_gate.py:1320-1360`): профиль → неослабление → приложения → прогон.
