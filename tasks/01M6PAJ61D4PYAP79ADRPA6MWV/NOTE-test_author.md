# Записка test_author 01M6PAJ61D4PYAP79ADRPA6MWV

## Выяснено
- Профиль compose из записи песочницы: test_profile — `Profile.from_values` + `with_tools` (как `decide`), components — `component_profiles` (он ставит from_components=True даже test_profile).
- Локальный слой — `targets.local_path()`, три раздела; weakening/mutation scopes — в policy.
- guard долгоживущих: запрещён литерал-строка с `tasks/` (голое "tasks" как часть Path — можно), id задачи в строках/именах, `obj._x` из orchestrator.
- subprocess держит свою ссылку на monotonic — подмена `time.monotonic` не ломает таймауты subprocess (приём для AC-8 «остаток ≤ 0»).
- Пределы вызовов docker наблюдаются подменой `subprocess.Popen` подклассом (communicate/wait timeout).
- Стаб вскрыл: git роли — обёртка role_bin/git, ей нужен python3 в PATH; LC_CTYPE ставит сам Python (PEP 538); абсолютная command в description отказана; plank-run запускает pytest с PYTHONPYCACHEPREFIX в окружении.

## Сделано
- tests/test_01m6paj61d4pyap79adrpa6mwv_compose_record.py — AC-1, AC-2 (под стабом 57/57).
- tests/test_01m6paj61d4pyap79adrpa6mwv_compose_run.py — AC-3..AC-15 кроме 16/17 (под стабом 72/72; 4 мутации стаба пойманы).
- tests/test_01m6paj61d4pyap79adrpa6mwv_compose_docker.py — AC-17 (настоящий Docker пропущен: нет docker).
- планка test_prior_runners_unchanged.py (разовый, AC-16), test_task_id_call_sites.py (разовый, AST, AC-9 места гейтов) — под стабом зелёные.
- Стаб убран: `git checkout -- orchestrator/`, временные файлы — task-rm.

## Где остановился
- Готово: на базе долгоживущие 121 красных (TargetsError — compose неизвестен), 1 зелёный (pytest-own без task_id), AC-17 проба 5 зелёных; планка AST 5 красных, AC-16 3 зелёных с рождения. preflight пройден весь.
- Тест AC-5/AC-6 разделён на две функции (имя `test_ac5_ac6_` засчитывало только AC-5).
- docs/codebase-map.md не регенерирован: правка вне tests/ откатывается пультом — это требование 12 разработчику.

## Чего не хватило
- Имя константы правила перекрытия (AC-15) SPEC не даёт — перебор публичных `acceptance.*COMPOSE*`.
- Имя параметра id у `two_sided.run` SPEC не даёт — взят `task_id`.
