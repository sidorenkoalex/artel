## Выяснено
- Третий аудит (spec_sha 8b124974…): решения №2 п. 1–6 в SPEC перенесены (треб. 3, 5, 7, 8, AC-4…AC-7, AC-11); адреса сходятся с кодом c2dc427f.
- `pult-pytest` — значение `runner` (targets.py:69), report компонента — только junit-xml | pult-vitest (targets.py:106). Условие треб. 5 «report, отличным от pult-pytest» всегда истинно.
- Каналы `_task_own_profile`/`place_channel` (acceptance.py:3282-3294, :374-380) отдают профиль только pytest-own или reported — компонент без report с runner pult-pytest и plank_layout до мест прогона не доходит; AC этого не ловят.
- Порядок отказа правила (треб. 1) и прежних путей без выкладки (AC-11) не задан.

## Не сработало
- `ls` не найден; `;` + `echo rc=$?` в Bash отвергается — команды без `$`.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready, guard ок.

## Чего не хватило
- Словарь: `pult-pytest` — runner, `junit-xml`/`pult-vitest` — report; какой профиль идёт в места прогона — `place_channel` (acceptance.py:374).
