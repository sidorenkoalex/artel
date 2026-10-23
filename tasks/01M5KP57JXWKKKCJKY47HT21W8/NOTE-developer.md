# Записка developer — 01M5KP57JXWKKKCJKY47HT21W8

## Выяснено
- Код готов: `orchestrator/role_prompt.py` — константа `REVIEWER_FULL_SUITE_RULE`, вставка в миссию ревьювера после `_reviewer_checks_note`, перечень внешнего проекта без `suite-run`. Карта кода регенерирована (после подтяжки main — только built_at_sha).
- Шаг 2 (после ANSWER-2, мандат по обоим методам): правлены два теста требования 8, имена методов прежние:
  - `test_01m5hdb1gs…::MissionTest::test_ac7_external_reviewer_mission_keeps_suite_run` — assertIn правила, `plank-run <id>`, `guard <id>` с путём пульта; `bare_full_run == []`.
  - `test_01m56g23zq…::Ac8ReviewerChecksTest::test_ac8_external_reviewer_lists_pult_check_commands` — цикл по guard/plank-run, «Права не сужены» нет, регулярка как `bare_full_run` (добавлен `import re`).
  - Мутация (возврат `suite-run {task_id}` в перечень) краснит оба; код возвращён.
- Три файла (два правленых + долгоживущий задачи): 16 passed, 58 subtests.
- Приложения 1 и 2: `guard.plan_appendices` без ошибок, `git apply --check` = 0 у обоих.
- PLAN.md: status ready, раздел «Эскалация» снят.
- plank-run (прошлый шаг): AC-6 локально красен — plank-run не накладывает приложения (ANSWER-1 п.1: ожидаемо).

## Не сработало
- `ls`/`cat` нет в PATH; составные команды с `$VAR`/`cp`+heredoc требуют подтверждения — мутацию делал через Edit.

## Где остановился
- Сдано ready.

## Чего не хватило
- `guard.plan_appendices` возвращает `(list[PlanAppendix], errors)`, у PlanAppendix поля `paths`, `diff`.
