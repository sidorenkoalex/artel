## Выяснено
- Итерация 4 (возврат аудита 2 из 2). Блокирующее п.1 аудита подтверждено по коду: ключ итога `pytest-own` считают три входа — `full_suite` с профилем из `acceptance._task_own_profile` (acceptance.py:2376-2410, `Profile.from_values`), гейт мержа (fsm_merge_gate.py:832-837/982, через `decide`), поиск базы `suite_run` (suite_run.py:523, профиль из `_profile_command`, suite_run.py:294, `from_values`). `profile_of` values несут только PROFILE_FIELDS (repo_context.py:171-172) — `tools` туда не попадают.
- pull.py/plank_run.py/amend.py строят `Profile.from_values`, но `suite_result_key` не зовут (grep) — на ключ не влияют.
- Варианты закрытия п.1: (A) расширить зоны — `_task_own_profile` + `suite_run._profile_command` берут `tools` из `components(target)`; (B) `tools` в values `profile_of` (repo_context.py — Оператор в ANSWER-1 ответ 1 запретил) → `from_values` читает их, все входы сразу; (C) `tools` не в ключе базы (пересмотр ответа 3).
- Пп. 2-4 аудита — уточнения SPEC: AC-3 добавить `3.1`↔`3.12.0` fail; определение «неразбираемой строки» и разбор `paths`; имена строк doctor, поток `--version`, шов подмены — вынесены вопросами с дефолтами в тот же батч.

## Где остановился
- QUESTIONS.md записан (4 вопроса: зоны `tools`, разбор строк, имена строк doctor, поток `--version`/шов), guard ок; SPEC.md не тронут. После ответа — переписать тр. 7-8, AC-3, AC-8, AC-11/12, «Не входит», удалить QUESTIONS.md.

## Чего не хватило
- Карта не показывает, кто строит `Profile` в обход `decide` — grep `from_values`.
