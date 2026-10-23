# Записка developer — 01M5KP57JXWKKKCJKY47HT21W8

## Выяснено
- Код готов в worktree: `orchestrator/role_prompt.py` — константа `REVIEWER_FULL_SUITE_RULE`, вставка в миссию ревьювера через пробел после `_reviewer_checks_note`, перечень внешнего проекта без `suite-run`. Карта кода регенерирована.
- Долгоживущий tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py — 5/5 зелёные.
- Красны ровно два метода требования 8: `test_01m5hdb1gs…::MissionTest::test_ac7_external_reviewer_mission_keeps_suite_run`, `test_01m56g23zq…::Ac8ReviewerChecksTest::test_ac8_external_reviewer_lists_pult_check_commands`. Мандата в ANSWER нет → PLAN status: escalate, вопрос — мандат. Замены утверждений расписаны в PLAN «Эскалация».
- Приложения: guard разбирает только разделы `## Приложение…` (уровень 2, слово «Приложение»); заголовок `## Приложения` + `###` даёт пустой список. Оба диффа из PLAN проходят `git apply --check` (0).
- plank-run: AC-4, AC-5, AC-9 зелёные; AC-6 локально красен (plank-run не накладывает приложения — гейт накладывает); AC-10 красен, пока PLAN.md нет в ссылке документов (artifact_text читает ревизию ссылки, не диск) — позеленеет после автокоммита шага.

- Прогнаны и зелёные файлы, собирающие миссии: role_missions, note_mission, note_brief, knowledge_hint, profile_mission, external_brief, template_hints, author_mission, role_templates, role_prompt_test_author_mission, role_outputs, docs_dir_layout, codebase_map (133 теста). model_sets/suite_run(01m462…) не гонял — общий прогон с ними не уложился в 10 минут.

## Не сработало
- `ls`/`cat` нет в PATH; составные команды с find/awk требуют подтверждения.

## Где остановился
- Ждём мандат. После ANSWER: правка двух тестов (шаг 3 PLAN), снять escalate → ready.

## Чего не хватило
- Формат разделов приложений PLAN — нашёл в scripts/guard.py `plan_appendices` / `_appendix_section_bodies`.
