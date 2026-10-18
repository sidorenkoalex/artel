---
task: 01M57JYJQC8VAHEWMXFNM7D1GS
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Планка внешнего проекта внутри workdir: конфиг, импорты и фикстуры проекта

## Подход
Выкладка живёт в самих функциях прогона `orchestrator/acceptance.py` — `run`,
`collect`, `run_plank`: их зовут все места требования 1 (гейты, подтяжка,
`plank-run`, обе ветви `amend-tests` — `amend.py:550-554`, `:724-728` уже
передают `cwd` рабочей копии и профиль), поэтому `amend.py` не меняется.

- `_plank_layout(task_id, tests_dir, code_root, own)` — контекст-менеджер:
  при `pytest-own` с `workdir` и `long_lived_dir` внутри `workdir` сначала
  дописывает идемпотентно `**/.artel-plank/` в файл
  `git rev-parse --git-path info/exclude` рабочей копии (общий для worktree
  клона), затем копирует каталог планки как он лежит на диске (штатная
  выкладка с `_pult.py` либо правка Оператора с помощником
  `plank_helper_laid_out`) в `<wt>/<long_lived_dir>/.artel-plank/<id>/acceptance_tests`,
  уборка (`_drop_layout`, вместе с пустым `.artel-plank/`) — в `finally`.
  git не назвал файл исключений / файл не записан — отказ выкладки без
  запуска pytest (выкладку, видимую git, класть нельзя).
- ANSWER-2: сбой записи `info/exclude` (нет прав, ввод-вывод, неразобранный
  путь `--git-path`) — отказ «отказ выкладки планки: … не записан (<причина>)»
  до создания выкладки, pytest не запускается (п.1). Проверка «шаблон уже
  есть» и дописывание идут под `fcntl.flock(LOCK_EX)` на самом файле
  (`open("a+")` → блокировка → чтение с начала → запись при отсутствии),
  поэтому две задачи одновременно оставляют одну строку (п.2).
- `run`/`collect`: цель-каталог планки заменяется путём выкладки
  (абсолютным); заголовок «планка: <tasks/<id>/acceptance_tests>, cwd: …»
  прежний. `long_lived_dir` вне `workdir` — прежний путь и строка
  `LAYOUT_OUTSIDE_NOTE` (у `collect` дописывается и к зелёному/пустому
  выводу). Тело вызова pytest вынесено в `_run_now`/`_collect_now` без
  изменений.
- `run_plank(..., task_id=None)`: `plank_run.py` передаёт `task_id` только
  для цели из планки; цель под `tasks/<id>/acceptance_tests` переводится
  `_layout_target` в тот же путь выкладки (с `::узлом`). Долгоживущий путь
  зовётся без `task_id` — выкладки нет (требование 4).
- `run_full_suite` (`pytest-own`): аргумент `--ignore=<lld от workdir>/.artel-plank`
  (без подстроки `acceptance_tests`); ключ итога `_own_suite_result_key` не
  трогается.
- `drop_from_code_copy` дополнительно убирает остаток
  `<wt>/<long_lived_dir>/.artel-plank/<id>/` по профилю задачи.

## Шаги
1. `orchestrator/acceptance.py`: `_plank_layout`, `_exclude_layout`,
   `_drop_layout`, `_layout_mode`, `_layout_target`; встраивание в `run`,
   `collect`, `run_plank`, `run_full_suite`, `drop_from_code_copy`.
2. `orchestrator/plank_run.py`: `task_id=task_id` в вызов `run_plank` для
   планки.
3. Две правки `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`
   по мандату ANSWER-1 (требование 12): в `assert_runs_file` к запретным
   целям добавлен путь выкладки `<wt>/<long_lived_dir>/.artel-plank/<id>`
   (та же проверка по префиксу, прежний путь остался); в
   `test_ac6_foreign_paths_and_plain_calls_keep_previous_outcome` для
   `self.ext` ожидаемый `plank` собирается в тесте из `self.wt(id)`,
   `long_lived_dir` профиля и `.artel-plank/<id>/acceptance_tests` с
   `realpath` — одна переменная обслуживает и :471, и :480; для `ARTEL`
   прежнее; `assertEqual` над списком сохранён. Мутация (снят `task_id` в
   `plank_run.py`) краснит `Ac6PreviousOutcomeTest` на цели внешнего проекта.
4. Новый тест `tests/test_acceptance_plank_layout_refusal.py` — свойство,
   не покрытое долгоживущими файлами: без файла исключений выкладки нет и
   pytest не запускается. Мутация (пропуск отказа `_exclude_layout`)
   краснит все три подтеста.
5. ANSWER-2, п.1: в том же файле `test_refusal_when_exclude_not_writable`
   (настоящий `git init`, на месте `info/exclude` каталог) и
   `test_refusal_on_lock_io_error` (`flock` бросает `EIO`) — отказ с
   причиной, pytest не запущен, `.artel-plank` нет, во всех трёх прогонах.
   Мутация (ошибка записи глотается) краснит оба — проверено.
6. ANSWER-2, п.2: `tests/test_acceptance_plank_exclude_lock.py` —
   держатель `flock` в тесте + поток `_exclude_layout`: поток ждёт и после
   строки держателя второй не пишет; два потока с барьером ×20 — одна
   строка. Мутация (снят `flock`) краснит оба — проверено.
7. Регенерация `docs/codebase-map.md`.
8. ANSWER-3: уточнение мандата ANSWER-1 — правка помощника
   `PlankLongLivedSandbox.assert_runs_file` (:345-348), которую гейт
   неослабления назвал находкой
   `Ac5OwnProfileLongLivedRunTest::test_ac5_long_lived_path_runs_by_own_profile`,
   покрыта мандатом без изменения объёма. Код и тест не меняются: правка уже
   ровно та (запретные цели — прежний путь планки и путь выкладки по
   префиксу, `assertFalse` над всеми целями). Перепроверено: тесты задачи,
   `test_01m56g23…`, `test_acceptance_plank_*` — 24 passed.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1 |
| 3 | 1, 2 |
| 4 | 2 (без `task_id` для долгоживущего пути), 3 |
| 5 | 1 (`finally` в `_plank_layout`) |
| 6 | 1 (`_exclude_layout` до `copytree` под `flock`; `drop_from_code_copy`), 4, 5, 6 |
| 7 | 1 (`--ignore` в `run_full_suite`) |
| 8 | 1 (исключение `info/exclude`) |
| 9 | 1 (заголовок прежний, узел несёт `.artel-plank/<id>/acceptance_tests/<файл>`) |
| 10 | 1 (`LAYOUT_OUTSIDE_NOTE`) |
| 11 | 1 (у `pult-pytest` `_plank_layout` ничего не делает) |
| 12 | 3, 8 |
| 13 | тесты test_author: `tests/test_01m57jyjqc8vahewmxfnm7d1gs_*.py` |

Проверки: `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`,
`..._artel_plank_unchanged.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`
— 19 passed; тесты затронутых модулей (acceptance*, amend*, plank_run*,
pytest-own места, profile_callers, pull_long_lived_plank) — 87 + 119
passed. Каталог `acceptance_tests/` задачи пуст (все AC — долгоживущие).
Полный набор `suite-run` №1 — зелёный: прошло 5842, упало 0, пропущено 2.
После ANSWER-2: тесты задачи + `test_acceptance_plank_*` +
`test_01m56g23…` — 24 passed; `suite-run` №2 — зелёный: прошло 5846,
упало 0, пропущено 2.

## Влияние на систему
- Артель (`pult-pytest`) — путь не меняется: `_layout_mode` возвращает «»,
  argv/cwd/тексты прежние (закреплено `..._artel_plank_unchanged.py`).
- Чекпоинт/гейт зон/`_pult.changed_paths()` — выкладка скрыта общим
  `info/exclude` клона, файлы `tracked` не меняются; `.gitignore` в дерево
  не кладётся. Запись в `info/exclude` — локальная настройка клона, в
  историю не попадает.
- Полный набор `pytest-own` — добавлен только `--ignore` каталога
  выкладки; ключ кеша итога прежний.
- Гейты, лимиты, guard не ослабляются; правка существующего теста — ровно
  две по мандату ANSWER-1 (запретных целей больше, `assertEqual` строгий).
- Откат — revert коммита задачи.

## Риски
- Глубина файла планки внешнего проекта меняется: планка, якорящая корень
  через `Path(__file__).parents[n]`, промахнётся (SPEC, «Материалы»).
- Базовое имя файла планки, совпадающее с долгоживущим файлом
  `long_lived_dir`, без `__init__.py` даст «import file mismatch» в общем
  вызове с `extra`.

## Предложения системе
- Шаг разработчика: `pytest -n … -p xdist` по файлам затронутых модулей
  роняет все узлы («node down: Not properly terminated») без пояснения —
  стоит назвать в скиле, что параллель в шаге недоступна.
- Риск (ANSWER-2, п.3): под конфигом проекта с `--import-mode=importlib`
  импорт `_pult` из планки (`from _pult import …`) может не работать —
  каталог выкладки не попадает в `sys.path`. Отдельной правки задача не
  вносит; адрес — `orchestrator/plank_helper.py`/выкладка помощника.
