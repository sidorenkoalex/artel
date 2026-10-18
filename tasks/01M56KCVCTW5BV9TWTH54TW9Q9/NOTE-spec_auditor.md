## Выяснено
- Повторный аудит SPEC sha 2a54ced8…: все пять решений гейта №1 учтены; вердикт concerns, 3 отклонения, guard ок.
- tests/test_acceptance_pycache.py:73-98 требует, чтобы у pult-pytest FileNotFoundError доходил до вызывающего (run, collect, run_full_suite) — требование 3 SPEC не ограничено pytest-own.
- _place_env/_own_env получают только профиль, не каталог прогона (acceptance.py:144-152); two_sided.py:242 зовёт _place_env(profile) сам — относительный command[0] «от workdir» требует правки вне зон.
- Окружение мест несёт служебные переменные: PYTHONUNBUFFERED (acceptance.py:1592, оба профиля), PYTHONPATH/REPORT_ENV у two_sided (two_sided.py:243-245) — литеральное ожидание AC-7 неполно.
- FULL_SUITE_NOT_STARTED не кешируется (acceptance.py:2028-2031); база suite-run сохраняется только завершённой (suite_run.py:540-546).

## Не сработало
- Bash с `cd` перед git, с `;`/`$?` требует подтверждения — только одиночные команды с литеральными путями.

## Где остановился
- SPEC-AUDIT.md готов (status ready, verdict concerns).

## Чего не хватило
- Список тестов, фиксирующих поведение pult-pytest при исключении запуска (нашёл grep по assertRaises(FileNotFoundError)).
