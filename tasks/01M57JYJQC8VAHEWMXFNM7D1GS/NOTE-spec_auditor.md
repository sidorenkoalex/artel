# Записка spec_auditor — 01M57JYJQC8VAHEWMXFNM7D1GS

## Выяснено
- Визит 3 (spec_sha a0a85302…): все 6 решений гейта SPEC визита 2 отражены (треб. 6, 7, AC-3, AC-6, AC-9, AC-10, «Не входит»/риски). Места кода сверены заново: acceptance.py :188/:213/:231/:600/:662/:737/:780/:801/:1134/:1146/:1166/:1454/:1798/:1951, plank_run.py :66-77/:227/:241, amend.py :535-565/:684/:723-728, zones.py:150-158, plank_helper.py:118-125, checkpoint.py:1796, runner.py:1218, тест :345-348/:471/:480, profile_callers :269/:716.
- Все прогоны планки идут через acceptance.run/collect/run_plank (вызывающие: advance_gates/acceptance.py:405/408, tests_writing.py:573/576, pull.py:668/671, amend.py, plank_run.py) — выкладку можно делать внутри них от `tdir/acceptance_tests` (amend передаёт tdir с правкой на диске).
- Сверка перечня долгоживущих — по git-дереву головы (advance_gates/acceptance.py:117-133), остаток выкладки её не трогает.
- drop_from_code_copy(task_id, code_dir) профиля не знает — разработчику придётся найти long_lived_dir сам (деталь реализации).
- Новые отклонения (мелкие): сбой записи исключения не задан (fail-closed?); гонка двух задач проекта при дописывании общего info/exclude; `import _pult` при `--import-mode=importlib` в addopts проекта.

## Не сработало
- Эмпирика pytest в mktemp — песочница Bash не пускает подстановку.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready.

## Чего не хватило
- Доступа на чтение к pyproject sled (`.artel/projects/sled/…`) — import-mode проекта не проверен.
