# Записка аналитика

## Выяснено
- ANSWER-1: все дефолты-варианты A, кроме 2 — B. Деление на 2 части ($40, $45), белый список только при merge_gate != operator.
- Имя ветки строится только в catalog.py:912; префикс `task/` ищется только в coldstart.py:59 (других "task/" в orchestrator/ нет).
- Отправки: github_adapter.py:166,241; fsm_merge_gate.py:744,1316; cleanup.py:265,268; artifact_branch.py:427; snapshot.py:297; artifact_cleanup.py:103.
- Подтяжка in_dev→verifying: fsm._pull_main_or_escalate (fsm.py:236) → pull.evaluate (pull.py:762), merge — pull._run_merge (:535), конфликт — pull._handle_merge_failure (:543).
- Коммиты пульта с FIXATION_AUTHOR вне зон ТЗ: amend.py:799 (кодовая ветка, долгоживущие тесты), snapshot.py:272 (коммит закрытия в refs/artifacts) — внесены в зоны части 2 как следствие требования 3.
- Части деления: зависимость родителя 01M5W27CY7K7NR9347NKD8F0NX перенесена в «Порядок:» части 1 (merge_after.division_order берёт зависимости части только из её поля).

## Не сработало
- `cd …; grep` в Bash требует подтверждения — использовать абсолютные пути.

## Где остановился
- SPEC.md с делением записан (status: ready, 21 AC, budget 70, guard ок), QUESTIONS.md удалён. Раздел «Меняемое поведение» не заводился: правка test_coldstart — на усмотрение аналитика части 1 по коду.

## Чего не хватило
- Где живёт подтяжка входа в verifying (ТЗ называет fsm_advance, а merge — в pull.py/fsm.py).
