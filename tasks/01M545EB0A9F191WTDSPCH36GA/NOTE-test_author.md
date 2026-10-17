# Записка test_author — 01M545EB0A9F191WTDSPCH36GA

## Выяснено
- Планка: долгоживущий tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py (AC-1, 2, 3, 4, 6, 8), разовые acceptance_tests/test_main_parity.py (AC-1, AC-5 — сверка с деревом базы через `git archive DIFF_BASE` + подпроцесс `_parity_scenario.py`), acceptance_tests/test_main_head_skills.py (AC-2/AC-3: голова main против диска пульта).
- AC-7 — `# AC-7: escalate`: SPEC не называет точку вызова проверки project_skills (аудит В-2). Предложено: А) `brief.project_skills_refusal(target, entry) -> str | None`.
- Шаг гоняется `runner.cmd_run` в LightTransitionSandbox с подменой `spawn_agent`; состояния tests_writing/review (без подтяжки и занятости зоны); `config.AGENT_ATTEMPTS`=1.
- Долгоживущему файлу нельзя импортировать gitcmd (guard «git-модуль») — потому различие main/диск в разовом файле, он наследует `ProjectSkillsBriefSandbox` долгоживущего.
- AC-8 «targets.yaml не читается» проверяется только задачей внешнего проекта (у артели — неоднозначность В-1 аудита).
- Стаб в runner (targets.target + имя + gitcmd.show + env/argv для не артели) — всё зелёное; мутации пойманы; стаб откатан `git checkout`.

## Не сработало
- yamlmini не разбирает кавычки в потоковом списке — имена в project_skills без кавычек.
- `cd && cmd`, xargs, sed, rm, циклы в bash — просят подтверждения.

## Где остановился
- preflight пройдена; планка готова, ждёт ответа на эскалацию AC-7.

## Чего не хватило
- Имени публичной проверки project_skills в SPEC (AC-7).
