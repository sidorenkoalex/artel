# Записка analyst

## Выяснено
- ANSWER-2: все 7 вопросов — вариант A (дефолты батча). Шаг: переписать SPEC.md по ответу + пункты аудита 1, 5, 6, 8, 12, матрица неослабления; удалить QUESTIONS.md; status ready.
- Код сверен: `components_full_suite` порядок «не начат/неизвестно» раньше красного (acceptance.py:3358-3359); `UNKNOWN_PREFIX` :355, `is_unknown` :384; путь CI артели :3421-3448 (дерево гейта = дерево головы, свежесть origin/MAIN_BRANCH, fresh); `approve` отказывает на FULL_SUITE_NOT_STARTED до `--accept-red` (fsm.py:1573-1582); `in_outcome_bounds` advance_gates/acceptance.py:213; `_replacement_findings` :739, `_Prepare` :753-756; `_component_key` :813, `_proven` :897, `_judge` :925-981.

## Не сработало
- `ls`/`sed` с `cd` в Bash недоступны — только Read.

## Где остановился
- SPEC.md переписан по ANSWER-2 (все A) и пунктам аудита: 21 AC (часть 1 — AC-1…13, часть 2 — AC-14…21), добавлена «Матрица неослабления», деление 2 частей ($40/$30) сохранено. QUESTIONS.md удалён, guard — ок, status ready.
- Не делал: «Матрица неослабления» — раздел вне шаблона SPEC; guard его пропустил.

## Чего не хватило
- Карточки «как approve --accept-red отличает неизвестно от красного» (fsm.py:1573 + acceptance.is_unknown).
