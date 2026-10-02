---
task: 01M3Y7G6T3MK7A899521VF9N7B
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Прогоны pytest пульта не исполняют устаревший байткод из worktree

## Фаза A — план
- Таблица покрытия PLAN закрывает требования 1–6. Требование 6 (AC-1…AC-6)
  законно отнесено к долгоживущему файлу test_author
  `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`. В
  `tests/test_acceptance_pycache.py` лежат только свойства, которых в нём
  нет, так что повтора нет (ADR-0020 п. 4).
- План состоит из одного шага. Для правки в одну функцию и три `env=` это
  размер MR, а не микрооперация.
- Подход (`PYTHONPYCACHEPREFIX` на `tempfile.mkdtemp`, уборка в `finally`,
  без `runner.role_env`) совпадает с SPEC и докстрокой `_pytest_command`.
  Дополнение — повтор `rmtree` — обосновано воспроизведённым сбоем
  `test_timeout_is_not_green`.
- «Влияние на систему» совпадает с диффом: `orchestrator/acceptance.py`,
  новый `tests/test_acceptance_pycache.py`, карта. Существующие тесты не
  тронуты (в `git diff 99b954f5...HEAD -- tests/` изменённых или удалённых
  строк нет, только новый файл). Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/acceptance.py::_pytest_env` — копия `os.environ` и `PYTHONPYCACHEPREFIX` на свежий `mkdtemp`; уборка в `finally` срабатывает и на `TimeoutExpired`, и на любом другом исключении (исключение выходит через `with` внутри `try`) |
| 2 | OK | `env=env` передан в `run`, `collect` и `run_full_suite` |
| 3 | OK | Меняется одна переменная; `role_env` не используется; `os.environ` не мутируется (`test_existing_prefix_in_pult_environment_is_overridden`) |
| 4 | OK | Каталог лежит в системном временном каталоге. Риск `TMPDIR` внутри `config.ROOT` честно записан в PLAN; AC-3 проверяет это в среде тестов |
| 5 | OK | Вызов с `-n … -p xdist` идёт в том же `with`; AC-5 проверяет по аргументам |
| 6 | OK | AC-1…AC-6 — в долгоживущем файле, дополнительные свойства — в `tests/test_acceptance_pycache.py`; у каждого метода есть «Ловит мутацию: …» |
| AC-7 | OK | Разовый тест планки `test_ac7_pycache_tests_file.py` («Группа: разовый» — факт задачи, граница групп соблюдена) |

## Замечания
Блокирующих и major-замечаний нет.

Наблюдение без severity: если `tempfile.mkdtemp` упадёт (нет места,
недоступен `TMPDIR`), `OSError` теперь выйдет из `run`/`collect`/`run_full_suite`
исключением, а не исходом прогона. Тот же класс, что и `FileNotFoundError`
от отсутствующего интерпретатора, который и раньше не перехватывался, — это
не регрессия контракта.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest tests/test_acceptance_pycache.py tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py tasks/01M3Y7G6T3MK7A899521VF9N7B/acceptance_tests tests/test_acceptance.py tests/test_acceptance_collect.py -p no:cacheprovider -q` — 37 passed, 41 subtests passed.
- Временная мутация: строка `env["PYTHONPYCACHEPREFIX"] = cache_dir` заменена на `pass`. Те же два файла `tests/` — 32 failed, в том числе живой `test_ac6_stale_pyc_with_same_mtime_and_size_is_not_executed`: подложенный `.pyc` с тем же mtime и размером действительно исполняется без переменной, и сторож AC-6 ловит это. Код возвращён (`git checkout`).
- Временная мутация в `_remove_cache_dir`: `except OSError: break` вместо паузы. `tests/test_acceptance_pycache.py` — 3 passed. Это ожидаемо: запасной `rmtree(..., ignore_errors=True)` сам служит повтором. Заявленные в тесте мутации («один rmtree без повтора / без перехвата OSError») подмена `flaky_rmtree` различает: `OSError` подменяет исход таймаута, либо остаётся `failures["left"] == 1`. Код возвращён.
- `python3 scripts/codebase_map.py` и `git diff -- docs/codebase-map.md` — расхождение только в `built_at_sha`, карта свежая. Регенерация откачена.
- CI коммита 5dc7e33a зелёный (по пакету).

## Предложения системе
- Многострочные Bash-команды ревьювера (heredoc, `;`-цепочки с `cp`) в шаге упираются в подтверждение, а временные мутации приходится делать через `python3 -c` и `git checkout --`. Это стоит прописать в review-checklist как штатный приём «временной мутации» (перекликается с наблюдением разработчика в PLAN).
