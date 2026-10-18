# Записка analyst

## Выяснено
- `plank-run` не гонит долгоживущие файлы по путям: `[файл]` только внутри планки (`orchestrator/plank_run.py:58-69`, отказ :151-155). `suite-run` — только полный набор (`--wait`/`--failed`). Раннер профиля по нескольким путям есть: `acceptance.run_plank(targets, cwd, profile)` (`acceptance.py:1096`); гейт выхода из tests_writing гонит долгоживущие вместе с планкой (`advance_gates/acceptance.py:405`).
- `plank_run.py`/`suite_run.py` по ТЗ только чтение, «правка вне зон — эскалация до SPEC» → батч QUESTIONS.md из одного вопроса (A расширить зону на plank_run.py — дефолт; B новая команда в artel.py; C suite-run).
- Остальное ТЗ достаточно: команда `guard <id> [файл]` в artel.py + `_ROLE_ALLOWED_COMMANDS` (`artel.py:1907-1910`); миссии в `role_prompt.py` (analyst :64, developer :120, test_author п.5 :88-95, reviewer :142-145, spec_auditor :272); признак артели — `artel = conn is None or brief.is_artel_task(...)` (`role_prompt.py:38`).

## Не сработало
- Bash с `$?` отклоняется песочницей (simple_expansion) — гонять guard без `echo rc=$?`.

## Где остановился
- QUESTIONS.md написан, guard ок. SPEC.md не писался.

## Чего не хватило
- Был ли в ТЗ смысл «назвать в SPEC» = назвать нужную правку plank_run.py (вне зон) или назвать отсутствие команды — отсюда вопрос.
