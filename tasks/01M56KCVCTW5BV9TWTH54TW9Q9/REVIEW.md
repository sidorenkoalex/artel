---
task: 01M56KCVCTW5BV9TWTH54TW9Q9
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Окружение шага роли внешнего проекта: PATH, сводка и логи suite-run

## Фаза A: план
- Таблица покрытия полна: требования 1–4 → шаги 1–2. Шаги — размер одного MR.
- Подход (одна зона `orchestrator/acceptance.py`, `two_sided` не правится и
  получает PATH через общий `_place_env` без `run_dir`) совпадает со SPEC
  («Не входит», требование 1 (б)) и с ANSWER-1 (ответ 1 — B, ответ 3 — A).
- «Влияние на систему» соответствует diff: изменены только
  `orchestrator/acceptance.py` и новый `tests/test_acceptance_own_launch.py`
  (плюс карта). `runner.py`, `providers/claude.py`, `suite_run.py`,
  `two_sided.py` не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_own_path` (acceptance.py:158–185): PATH вызывающего как есть, затем каталог `command[0]` (абсолютный — `dirname`; относительный с `/` — от `run_dir`, без него пропуск; голое имя — `shutil.which(head, path=caller)`, не найдено — пропуск), затем недостающие `/usr/bin`, `/bin`, `/usr/sbin`, `/sbin` без повторов. `env.update(profile.env)` идёт после — `PATH` профиля перекрывает. Все семь мест `acceptance.py` передают `run_cwd`/`root`; `two_sided._run_side` зовёт без каталога. |
| 2 | OK | `deselected` добавлен в `_RUN_CATEGORY` (acceptance.py:356). |
| 3 | OK | `CommandNotFound(OSError)` + `_launch`: перевод только при `own` и `exc.filename == argv[0]` (у CPython `orig_executable`/`args[0]`; при несуществующем `cwd` filename — каталог). Перехват узкий по типу: `open(log)` в `_run_full_suite_to_log` бросает обычный `FileNotFoundError`, мимо. Каналы: `run`/`collect` — `(False, …)`, `run_repeat` — `RedTest` на каждый файл, `run_plank` — `REFUSED_EXIT_CODE`, `run_full_suite` — `FULL_SUITE_NOT_STARTED: …` (возврат до кеширования; все три пути полного прогона проходят через этот `try`, путь без наблюдения — через `_run_pytest` → `_run_in_session` → `_launch`). `two_sided` ловит `OSError` — свой текст сохранён. |
| 4 | OK | `_pytest_env`/`_pytest_command` не тронуты; у `pult-pytest` `_launch(own=False)` пробрасывает исключение как есть; закреплено `…_pult_pytest_unchanged.py` (зелёный). |

## Замечания
Блокеров, major и minor нет.

Проверено и не стало замечанием:
- `tests/test_acceptance_own_launch.py::test_missing_command_named_only_for_own`
  не дублирует долгоживущий `…_missing_command.py`. Долгоживущий проверяет
  `pult-pytest` через `run`/`collect`/`run_full_suite` без наблюдения, а эти
  вызовы идут через `subprocess.run`, не через `_launch`. Ветку
  `_launch(own=False)` (пути с наблюдением и в лог у артели) сторожит только
  этот тест.
- Заявки «Ловит мутацию» в новом тесте исполнимые: удаление сверки
  `exc.filename` временной мутацией делает тест красным (см. «Проверено
  исполнением»).
- Утверждения существующих тестов не менялись: в diff `tests/` только новый
  файл.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m56kcvctw5bv9twth54tw9q9_{missing_command,own_run_path,pult_pytest_unchanged,summary_deselected}.py tests/test_acceptance_own_launch.py tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py tests/test_acceptance_pycache.py` — 28 passed, 226 subtests passed (99 с).
- `artel.py plank-run 01M56KCVCTW5BV9TWTH54TW9Q9` — отказ «планки нет: в refs/artifacts/… нет файлов test_*.py». Планки `acceptance_tests/` у задачи нет: критерии закрыты долгоживущими тестами в `tests/`, они прогнаны выше.
- Временная мутация `acceptance._launch`: `if not own or exc.filename != argv[0]` → `if not own`. `tests/test_acceptance_own_launch.py` — 1 failed (`test_missing_cwd_is_not_a_missing_command`), 1 passed. Код возвращён (`git checkout`), `git status` чистый.
- `python3 scripts/codebase_map.py` + `git diff docs/codebase-map.md` — расходится только строка `built_at_sha`, карта свежая. Регенерация откачена.
- CI коммита 53da2fc1 — зелёный (по пакету). Полный набор в шаге не запускался (решение Оператора 05.09).

## Предложения системе
- `plank-run` у задачи, чьи критерии целиком закрыты долгоживущими тестами
  в `tests/`, даёт «отказ — планки нет». Для ревьювера это шум, похожий на
  сбой. Стоит отличать исход «планки нет по замыслу» от отказа
  (`orchestrator/artel.py plank-run`).
