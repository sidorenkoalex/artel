# Записка test_author — 01M590GJAF0EDV4NBC4C99MFVH

## Выяснено
- Визит 3 (после ANSWER-2: В1–В5 — варианты A). Пишу планку целиком.
- Раскладка: долгоживущий tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py (AC-1…4, 5 п.1–4, 6, 7…10, 11 на уровне функций acceptance/two_sided, 15, 16, 18 п.1/2/5, 19, 20); разовый acceptance_tests/test_gates_wiring.py (AC-5 approve/подсказка мержа, AC-11 сквозь вызывающих, AC-12, AC-13, AC-14, AC-17, AC-18 п.3/4, AC-21).
- Канал профиля компонента: запись `components:` с одним компонентом → `project_profile.decide(<проект>).profile` → места прогона (`command=`/`profile=`). Одиночный компонент с `workdir`/`env` по targets.py обязан нести `runner: pytest-own` (правило `_check_component_rules`); компонент без runner — без workdir.
- Подменённый раннер: исполняемый драйвер вне дерева (пишет argv/cwd/env/pgid в зонд, отчёт по сценарию JSON). Vitest ставит поддельный install (python) в `node_modules/.bin/vitest` своего cwd — как `npm ci`.
- Таблица `project_profile.VITEST_VERSION_FLAGS`: форму записи не навязываю — флаг кэша = строковое значение на `--`, «принимает» = булево значение; отрицательная версия — подмена таблицы целиком `patch.object`.
- Узел гейта мержа — `fsm_merge_gate._full_suite_or_refuse(conn, task, paths, scratch, ctx)` (прецедент tests/test_worktree_db_files.py).
- Сквозные места — подкласс `ProfileCallersSandbox` из tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py (разовый файл).

## Не сработало
- `ls` в Bash недоступен; `$VAR` в Bash требует подтверждения.

## Где остановился
- Долгоживущий файл написан и прогнан: красные падают по правильным причинам (нет поля tests, таблицы версий, report_args, имени в ключе, сторожа); зелёные с рождения — AC-4/6 п.1–2, AC-12 п.2, AC-20.
- Разовый acceptance_tests/test_gates_wiring.py написан, test_escalation.py удалён; preflight — все проверки «пройдена».
- Валидация стабом: докстринги обоих файлов заявляют её проведённой (стаб удалён, рабочая копия чистая — git status пуст).
- Визит 4 (после таймаута): preflight — все «пройдена»; пометок escalate/manual/skip нет; все AC-1…21 покрыты методами. Долгоживущий файл: 33 красных по заявленным причинам, 8 зелёных. Перечитка на согласованность сделана: единственная правка — AC-19 брал версию Vitest литералом «4.x», теперь версия из таблицы (как во всех сценариях). plank-run: 11 failed, 4 passed (зелёные — AC-12 п.2, AC-13 без приложений, AC-14 ×2, как в маркере). preflight — все «пройдена». Шаг сдан.
- yamlmini: кавычки в потоковом списке не разбираются — `[--junitxml, {path}]` без кавычек.
- pytest собирает вспомогательный метод `tests_of` как тест (префикс test) — не называть помощники на `test`.

## Чего не хватило
- Нигде не сказано, как одиночный компонент с `workdir` проходит правило `runner` targets.py — выяснил чтением `_check_component_rules`.
