# Записка analyst — 01M56KCVCTW5BV9TWTH54TW9Q9

## Выяснено
- Требование 4 (Claude: второй `--add-dir` с логами suite-run) противоречит двум существующим тестам:
  `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py:288-310` (test_ac7, `assertEqual(opened, [docs])`) и
  `tests/test_docs_dir_layout.py:538` (`opened[:at]+opened[at+2:] == bare` для claude). Это сравнения списков, через
  «Меняемое поведение» (только скаляры) их не провести, поэтому написан QUESTIONS.md (вопрос 1, дефолт B — исключить треб. 4).
- PATH: `_own_env` (acceptance.py:152-172) копирует PATH/LANG/LC_ALL, затем `env.update(profile.env)`. Все места запуска
  идут через `_place_env` (acceptance.py:607,720,838,1116,1543,1564,1591) и two_sided.py:242 — одна правка `_own_env` покрывает и two_sided.
- Предложенный порядок PATH (вопрос 3, деф. A): PATH вызывающего, затем dir(command[0]), затем /usr/bin,/bin,/usr/sbin,/sbin; без дублей; PATH из profile.env перекрывает.
- `_RUN_CATEGORY` (acceptance.py:292) уже знает xfailed/xpassed, не знает только `deselected`.
- FileNotFoundError перехвачен только в two_sided.py:255/260 (OSError); в acceptance — нет.
- `providers/claude.py::command(model, docs_dir, project)` не получает id задачи; лог suite-run: `config.LOGS/suite-run/<id>/<id>-suiterun-<n>.log` (suite_run.py:54).
- Тест test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py сверяет профильные env, равенство PATH пульту не проверяет — конфликта с треб. 1 нет.
- Рамка ТЗ $35; класс по таблице (6 AC, 4 зоны) ~40 → в SPEC ставить 35 (≥30 — сигнал объёма, нужна секция оценки).

## Не сработало
- —

## Где остановился
- QUESTIONS.md сдан (guard ок), SPEC.md не писался. После ANSWER: писать SPEC и удалить QUESTIONS.md.

## Чего не хватило
- Ничего существенного; дольше всего искал тесты, закрепляющие argv Claude (grep `add-dir` по tests/).
