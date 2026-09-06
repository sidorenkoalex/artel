---
task: 01M1TKP6AAY4W8GDGZNA9R0JZT
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: P1a — раннер pytest в пульте: acceptance, dry_run, amend и их тесты

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (acceptance.py::run()/run_full_suite() на pytest) | OK | `_pytest_command()` собирает команду через `stack.pytest_python_executable()`, `cwd`/`location_note`/вырожденные случаи сохранены; AC-1..AC-3 зелёные. |
| 2 (amend.py::_run_summary/_RUN_SUMMARY на сводку pytest) | OK | Регулярка покрывает все категории (passed/failed/error/skipped/xfailed/xpassed/warning) с корректной плюрализацией error(s)/warning(s); AC-4, AC-5, AC-11 зелёные. |
| 3 (разбор AC-n/redness-маркеров не меняется) | OK | `scripts/guard.py` — 0 строк диффа (проверено `git diff --stat` между базой и HEAD); AC-6 регресс-тест зелёный. |
| 4 (таймаут отдельного теста, `stack.PER_TEST_TIMEOUT_SEC=120`) | OK | AC-7 зелёный (зависший тест убит pytest-timeout, не общим таймаутом run()). |
| 5 (`.pytest_cache/` не артефакт) | OK | `-p no:cacheprovider` в обеих командах; AC-8 зелёный. |
| 6 (`pyproject.toml` с testpaths/python_files/timeout) | Реализовано не так | Файл заведён верно (AC-9 зелёный), но комментарии `orchestrator/stack.py:53-58` и `pyproject.toml:1-9` утверждают несуществующую защиту от рассинхронизации — см. замечание R1-F1. |
| 7 (существующие `tests/*.py` не переписаны под идиомы pytest) | OK | `tests/test_amend.py` — только фикстуры `RunSummaryTest` под новый формат вывода, сценарии/структура класса не тронуты; остальные файлы `tests/` не в диффе. |
| 8 (doctor.py явно называет pytest в venv-packages) | OK | `_venv_packages_check()` — отдельная фраза для пропавшего/несовпавшего pytest; `doctor/cli.py:121` печатает `detail` целиком, без усечения; AC-12 зелёный. |

Деление на монолит (SPEC «Оценка объёма») обосновано и не оспаривается:
пять требований действительно образуют одну неделимую механику смены
раннера, шаги PLAN — проверяемые единицы, покрытие требований в PLAN
полное.

## Замечания

- major — `orchestrator/stack.py:53-58` и `pyproject.toml:1-9` — оба
  места комментируют константу `PER_TEST_TIMEOUT_SEC = 120` /
  `timeout = 120` фразой «TOML не умеет читать значение отсюда;
  расхождение ловит `tests/test_stack.py`» — но такой проверки нет:
  `grep -n "PER_TEST_TIMEOUT_SEC" tests/` и `grep -n "120\|timeout"
  tests/test_stack.py` не находят ни одного теста, сравнивающего эти
  два числа. Единственный тест, трогающий значение `120`, —
  `tasks/01M1TKP6AAY4W8GDGZNA9R0JZT/acceptance_tests/
  test_ac9_pyproject_config.py::test_ac9_default_timeout_equals_
  requirement_4_value` — он сверяет `pyproject.toml` с ЛИТЕРАЛОМ `120`
  (что совпадает с AC-9 намеренно — докстринг AC-9 явно просит именно
  литерал, не производную от ещё не введённой константы), но это
  task-specific планка `tasks/<id>/acceptance_tests/`, не постоянный
  набор `tests/`, и она не читает `stack.PER_TEST_TIMEOUT_SEC` вовсе —
  сверки ДВУХ мест друг с другом там тоже нет. Сценарий: будущая
  задача меняет `stack.PER_TEST_TIMEOUT_SEC` (например, на 180) без
  правки `pyproject.toml` — ни один тест постоянного набора `tests/`
  этого не заметит, planka продолжит молча резать тесты по старому
  таймауту 120с из `pyproject.toml`, разработчик и ревьювер будущей
  задачи полагаются на защиту, которой нет (комментарий явно называет
  `tests/test_stack.py`), и класс зависаний 04–05.09, ради которого
  заведено требование 4, тихо возвращается на новом пороге. Предложение:
  либо добавить в `tests/test_stack.py` тест, читающий оба значения
  (`stack.PER_TEST_TIMEOUT_SEC` и `timeout` из `pyproject.toml` тем же
  парсером, что `_util.read_pytest_config`/`tomllib`) и сравнивающий их
  равенство, либо переписать оба комментария так, чтобы не называть
  конкретный несуществующий тест защитой (описать как ручную
  синхронизацию без автоматической проверки).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | orchestrator/stack.py:53-58, pyproject.toml:1-9 | Комментарии утверждают, что `tests/test_stack.py` ловит рассинхронизацию `PER_TEST_TIMEOUT_SEC`/`pyproject.toml[timeout]`, такого теста нет | Будущий дрейф значения тихо не ловится, комментарий вводит в заблуждение | Добавлен `tests/test_stack.py::ManifestConstantsTest::test_per_test_timeout_matches_pyproject_toml` — читает `pyproject.toml` через `tomllib`, сверяет `[tool.pytest.ini_options].timeout` с `stack.PER_TEST_TIMEOUT_SEC`; проверено принудительной рассинхронизацией (тест падает на 120 != 180). Комментарии `stack.py`/`pyproject.toml` оставлены как есть — их ссылка на `tests/test_stack.py` теперь верна |

## Вердикт

changes_requested — исправить R1-F1 (ложная ссылка на несуществующий
тест синхронизации таймаута в комментариях `orchestrator/stack.py` и
`pyproject.toml`). Остальной диф корректен, функционально полон,
подтверждён прогоном; после закрытия R1-F1 препятствий к approved нет.

## Проверено исполнением

- `python3 -m pytest tasks/01M1TKP6AAY4W8GDGZNA9R0JZT/acceptance_tests
  -p no:cacheprovider -p timeout -o timeout=120` (та же команда, что
  строит `acceptance._pytest_command()`) — 28 passed за 124.95с (все
  AC-1..AC-12 приёмочной планки этой задачи, включая AC-7 per-test
  timeout).
- `python3 -m pytest tests/test_amend.py tests/test_acceptance.py
  tests/test_stack.py -p no:cacheprovider -p timeout -o timeout=120` —
  41 passed за 6.38с (регресс затронутых модулей — `_run_summary`,
  `run()`/`run_full_suite()`, `check_stack()`/`pytest_python_executable`).
- `git diff --stat 05314792c48198a2ffce65b0b96e0591edb5183f...HEAD --
  scripts/guard.py orchestrator/doctor.py` — пусто, требование 3 и
  зона `orchestrator/doctor.py` действительно не тронуты (AC-6
  регресс-тест зелёный в прогоне выше).
- `python3 scripts/codebase_map.py --check` — без вывода/без ошибки:
  `docs/codebase-map.md` актуален содержимому дерева после подтяжки
  main (регенерация ANSWER-5 не устарела).
- Полный `tests/` не прогонялся в шаге ревью (решение Оператора
  05.09) — CI коммита a221645f зелёный (14 проверок), условие гейтов
  verifying/merge выполнено независимо.

## Предложения системе

- Класс «докстринг/комментарий утверждает существование проверки,
  которой нет в дереве» (`orchestrator/stack.py`, `pyproject.toml` —
  эта задача) стоит ловить до ревью: `guard.py` уже статически сканирует
  `acceptance_tests/*.py` — тот же принцип (грепнуть путь файла,
  упомянутый в комментарии рядом с «расхождение ловит»/«проверено»,
  и проверить, что там реально есть релевантный тест) применим и к
  обычному коду `orchestrator/`, не только к планкам приёмки.
