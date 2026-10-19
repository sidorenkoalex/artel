# Записка analyst — 01M590GJAF0EDV4NBC4C99MFVH (G1б)

## Выяснено
- Шаг 4 (возврат из spec_gate, последний): Оператор решил 9 пунктов SPEC-AUDIT (concerns) без новых вопросов — правка SPEC по ним, QUESTIONS.md не нужен.
- Узел приёмки, общий для `approve` (`fsm.py:1294`) и автогейта (`fsm_autogate.py:326`), — `acceptance.acceptance_suite` (`acceptance.py:2393`); туда `checks_local` (решение 5).
- «Не начат» в `full_suite` возвращается до записи лога (`acceptance.py:2363-2366`) — для «неизвестно» лог обязан сохраняться (решение 8). Подсказка гейта мержа для NOT_STARTED — `fsm_merge_gate.py:996-1005`.
- Места прогона планки: `acceptance.run` из `advance_gates/acceptance.py:405,408`, `pull.py:668,671`, `amend.py:554,728`; `run_repeat` из `advance_gates/acceptance.py:169`.

## Не сработало
- В оболочке нет `ls`/`wc` без подтверждения — смотреть каталог через `python3 -c os.listdir`.

## Где остановился
- SPEC.md поправлен по 9 решениям гейта (треб. 2, 3, 7, 12, 13; AC-2, 4, 5, 9, 10, 15, 17, 19; «Не входит» — черновик sled в ADR на этапе 2), status: ready, guard ок. Нумерация AC прежняя (AC-1…AC-21).

## Чего не хватило
- Смысл «Вариант A» ANSWER-1 — только в удалённом QUESTIONS.md (`git show 08c69578:tasks/<id>/QUESTIONS.md` в ссылке документов).
