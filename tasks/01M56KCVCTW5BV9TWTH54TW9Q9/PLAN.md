---
task: 01M56KCVCTW5BV9TWTH54TW9Q9
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Окружение шага роли внешнего проекта: PATH, сводка и логи suite-run

## Подход
Все правки — в `orchestrator/acceptance.py`. Тесты задачи уже написаны
test_author (`tests/test_01m56kcvctw5bv9twth54tw9q9_*.py`, залочены);
код пишется под них, свои тесты — только на непокрытые свойства.

1. **PATH прогона `pytest-own`.** `_own_env(profile, run_dir=None)` и
   `_place_env(command, run_dir=None)` получают необязательный каталог
   прогона. PATH собирает новая `_own_path(profile, run_dir)`: PATH
   вызывающего как есть, затем каталог `command[0]` (абсолютный — его
   каталог; относительный с `/` — от `run_dir`, без `run_dir` шаг
   пропускается; голое имя — `shutil.which` по PATH вызывающего, не
   найдено — пропуск), затем недостающие `/usr/bin`, `/bin`, `/usr/sbin`,
   `/sbin`, без повторов. `test_profile.env` применяется после — его `PATH`
   по-прежнему перекрывает собранное. Семь мест `acceptance.py` передают
   свой `run_cwd`; `two_sided._run_side` (вне зон) зовёт `_place_env(profile)`
   без каталога — получает (а)+(в).
2. **`deselected`** добавляется в `_RUN_CATEGORY` — `run_summary_line`
   берёт всю итоговую строку, `suite_run.parse` считает по ней.
3. **Отказ «команда профиля <имя> не найдена».** Новое исключение
   `CommandNotFound(OSError)` и помощник `_launch(argv, cwd, own, **kw)`:
   `subprocess.Popen` с переводом `FileNotFoundError` в `CommandNotFound`
   только у `pytest-own` и только когда `exc.filename` — сам `argv[0]`
   (а не `cwd`: несуществующий `cwd` Popen тоже называет
   `FileNotFoundError`). Через `_launch` идут `_run_in_session` и два
   прямых `Popen` полного прогона (с наблюдением и в лог). Наследник
   `OSError`, не `FileNotFoundError`: `two_sided._run_side` ловит `OSError`
   и сохраняет свой текст «pytest не запустился: …», а наружу
   `FileNotFoundError` не выходит. Места ловят именно `CommandNotFound` —
   перехват узкий по типу: `FileNotFoundError` открытия лога/временных
   файлов не превращается в отказ. Каналы: `run`/`collect` — `(False,
   текст)`, `run_repeat` — `RedTest` каждого файла, `run_plank` —
   `REFUSED_EXIT_CODE`, `run_full_suite` — `FULL_SUITE_NOT_STARTED: текст`
   (итог `full_suite` не кешируется — существующая ветка возврата).
   У `pult-pytest` путь запуска не меняется (`subprocess.run`/`Popen` как
   были) — `FileNotFoundError` доходит до вызывающего.
4. **`pult-pytest` без изменений** — `_pytest_env`/`_pytest_command` не
   трогаются; закреплено долгоживущим `…_pult_pytest_unchanged.py`.

## Шаги
1. `acceptance.py`: `_own_path`, параметр `run_dir` у `_own_env`/`_place_env`,
   передача `run_cwd` в семи местах; `deselected` в `_RUN_CATEGORY`;
   `CommandNotFound`, `_launch`, перехват в семи местах.
2. Прогон тестов затронутых модулей: четыре файла задачи,
   `test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`,
   `test_acceptance*.py`, `test_suite_run*.py`, `test_two_sided*.py`;
   регенерация карты `scripts/codebase_map.py`; полный набор — `suite-run`.
   Свой сторож `tests/test_acceptance_own_launch.py`: несуществующий `cwd`
   запуска не называется «команда профиля … не найдена», перевод — только
   у `pytest-own` (проверен мутацией: без сверки `exc.filename` — красный).

Итог шага: 4 файла задачи + `pytest_own_places` — 23 passed, 217 subtests;
соседние модули (`test_acceptance*`, `test_full_suite_*`,
`test_plank_run_edges`, `test_suite_run`, two_sided, `pytest_own_result_ids`)
— 100 passed. `suite-run` в шаге не запустился: замок полных прогонов
машины ≥15 мин держал `suite-run` задачи 01M56G23ZQDHV2BKEVWWC22R96 (pid
54448), каждая попытка — отказ «на машине уже идёт прогон»; полный набор
остаётся гейту и CI.

## Покрытие требований
| Требование | Шаг |
|---|---|
| 1 (PATH: вызывающий + каталог `command[0]` + системные; env профиля перекрывает) | 1 |
| 2 (`deselected` в итоговой строке) | 1 |
| 3 (отказ «команда профиля <имя> не найдена» каналом места, узкий перехват) | 1 |
| 4 (`pult-pytest` без изменений) | 1, 2 |

## Влияние на систему
Затронут только путь `pytest-own` (внешние проекты): у артели
(`pult-pytest`) argv, окружение и `cwd` не меняются — `_pytest_env` не
тронут, `_launch` переводит исключение только при `own`. `PATH` процесса
роли (`runner.role_env`) не меняется. Гейты не ослабляются: отказ запуска
идёт в «прогон не начат», который потребители уже читают как «не
проверен», и в кеш итогов не попадает. Разбор итоговой строки только
расширен (лишняя категория), прежние строки разбираются так же. Откат —
revert одного merge-коммита.

## Риски
- Хвост PATH у процесса пульта может получить `/usr/sbin`/`/sbin` или
  каталог команды — в конце, ничего не затеняет (обоснование SPEC).
- `exc.filename == argv[0]` также при отсутствии интерпретатора из
  shebang обёртки — это тоже «команду не запустить», текст отказа
  допустим.

## Предложения системе
- `suite-run` при занятом замке машины только отказывает: ни очереди, ни
  `--wait` до старта. В PATH роли нет `sleep`, поэтому цикл ожидания из
  шелла роли превращается в холостую долбёжку пульта (пришлось ждать
  через `python3 -c` с `time.sleep`). Не хватает команды «поставить
  suite-run в очередь за замком».
- `pytest -n` (xdist) в шаге роли падает с «node down: Not properly
  terminated» — параллельный прогон тестов затронутых модулей из шага
  недоступен.
