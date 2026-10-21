# Записка test_author — 01M5ENWTDD8NP9SMPFX3JN08J9

## Выяснено
- Долгоживущие файлы (tests/test_01m5enwtdd8np9smpfx3jn08j9_*.py):
  author_mission (AC-1, AC-2, AC-5 задание); vitest_summary (AC-3..AC-6 через runner.run_agent_once
  + шпион OutputPump); watch_report (AC-7: watch.cmd_watch + patch_sleep, report.cmd_report);
  plank_run_summary (AC-8, AC-9: cmd_plank_run с подменой acceptance.run_plank/plank_in_code_copy).
- Разовые в acceptance_tests: test_template_hints_untouched (AC-2, зелёный с рождения),
  test_skills_appendix (AC-10, красен до PLAN).
- Валидация стабом сделана (шаг 2): стаб в orchestrator/{role_prompt,agent_log,runner,watch,report,plank_run}.py —
  21 тест долгоживущих файлов + template_hints зелёные; стаб откатан `git checkout -- orchestrator/`.
  AC-10: временная правка skills/ → git diff → откат; PLAN с двумя приложениями + подставной `_pult` — 3/3 зелёные.
- До реализации: красны vitest_summary AC-3/AC-4/AC-5(vitest-подтест), watch_report, plank_run AC-8,
  author_mission AC-2 — все из-за отсутствия кода задачи; AC-1/AC-5/AC-6/AC-9 зелены (прежнее поведение).

## Не сработало
- preflight отказал: литерал `tasks/` в author_mission (заменён на {TASKS_DIR}), импорт
  `artifact_branch` в plank_run_summary («git-модуль»; заменён на config.PROJECTS/<проект>/tasks/<id>).
  После правки preflight пройден целиком.

## Где остановился
Готово: preflight пройден, plank-run по обоим файлам планки — ожидаемый исход.

## Чего не хватило
Правило долгоживущего файла запрещает даже импорт `artifact_branch` (признак «git-модуль») — путь
каталога документов пришлось собирать от config.PROJECTS вручную.
