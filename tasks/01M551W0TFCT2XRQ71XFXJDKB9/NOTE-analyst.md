# Записка analyst

## Выяснено
- ANSWER-1: вариант A — runner.py (только _missing_required_artifact/_has_own_long_lived_test, :1310-1346) в зонах, потолок прежний $25.
- Места без профиля: role_prompt.py:36, :78-80, :94, :114; checkpoint.py:376, :384, :412, :497; runner.py:1317-1319, :1338, :1340, :1345.
- Источник профиля — project_profile.for_task(conn, task_id).profile (Decision; profile=None при skip/refusal — гейт tests_writing тогда пропускает). Profile.long_lived_prefix/long_lived_example/is_long_lived — project_profile.py:106-118.
- Профиль артели: long_lived_dir tests, long_lived_name test_<id>_<name>.py (targets.yaml:47-48); sled — backend/tests (:85-86).

## Не сработало
- Первый прогон guard: сигналы объёма (tests/ как каталог, инвариантный механизм чекпоинта, нет прогноза диффа) и неклассифицированные пути amend/preflight/acceptance.py — закрыто секцией «Оценка объёма» (монолит, прогноз 30 КиБ) и строкой в «Не входит».

## Где остановился
- SPEC.md status: ready, 5 AC, guard ок; QUESTIONS.md удалён. Готовый текст правки skills/test-authoring.md (абзац 114-126) — в «Материалах» SPEC.

## Чего не хватило
- Поведение при отсутствии профиля (Decision.skip/refusal) в задании/чекпоинте ТЗ не оговаривает; SPEC это не фиксирует — решает разработчик (разумно: умолчания, как сегодня).
