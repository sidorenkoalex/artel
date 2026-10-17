## Выяснено
- ANSWER-1: вопрос 1 → B (конвенции проекта у developer — замена CLAUDE.md пульта; analyst/spec_auditor/test_author — новый компонент; reviewer/review.py — «Не входит»), budget ~$40 (потолок $50). Вопрос 2 → A (фиксированно CLAUDE.md + AGENTS.md корня базовой ветки).
- Места: developer_brief `brief.py:871-942` (карта :912-913, CLAUDE.md :914/:932, алерт размера :915); spec_auditor_brief :961-1002 (карта :994-997); analyst_map_component :1261-1300 (карта :1282/:1288, компоненты через `_journal_component`); test_author_answer_component :1303-1324 (`None` без добавок). Миссия developer — `role_prompt.py:95-97` (ТЗ называет :104-106).
- Миссия analyst (`role_prompt.py:42-43`) говорит «Карта кодовой базы … в БРИФЕ» — для внешнего проекта это станет неверно, но в ТЗ этого нет; отметил в «Материалы» SPEC, требованием не делал.

## Не сработало
- Ничего.

## Где остановился
- SPEC.md записан (10 AC, budget 40, обоснование монолита), QUESTIONS.md удалён; guard — см. итог шага.

## Чего не хватило
- Сводки «компонент брифа × роль» — собирал по brief.py/role_prompt.py.
