---
task: 01M3Y7G6T3MK7A899521VF9N7B
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/acceptance.py, tests/test_acceptance_pycache.py, docs/codebase-map.md
budget_usd: 25
---

# SPEC: Прогоны pytest пульта не исполняют устаревший байткод из worktree

## Контекст
02.10 08:32Z автогейт приёмки задачи 01M3XTF1CEBXT4J7P0EKG5J342 дал
«2 failed» на исправном коде: полный набор `tests/` в worktree исполнил
устаревший `orchestrator/__pycache__/fsm_advance.cpython-313.pyc`. Время
изменения исходника и `.pyc` совпало до секунды, размер исходника не
изменился, и проверка свежести байткода по времени и размеру сочла кеш
свежим. CI ветки был зелёным, тот же тест с `PYTHONPYCACHEPREFIX` в чистый
каталог — 4 passed. Итог — ложная остановка задачи и ручной разбор.

Все pytest-прогоны пульта идут через `_pytest_command`
(`orchestrator/acceptance.py:21`) и три вызова `subprocess.run` без `env=`:
`run()` (`:186`), `collect()` (`:240`), `run_full_suite()` (`:463`).
Окружение целиком наследуется от процесса пульта. Через эти функции идут
автогейт приёмки, полный набор при подтверждении приёмки и на гейте мержа,
прогон планки после подтяжки main, гейт приёмки, сухой сбор на
tests_writing, amend-tests и doc-commit. `PYTHONDONTWRITEBYTECODE=1` проблему
не решает: уже лежащий устаревший `.pyc` всё равно читается. Решает
отведение кеша в отдельный каталог (`PYTHONPYCACHEPREFIX`).

## Требования
1. В `orchestrator/acceptance.py`, рядом с `_pytest_command`, есть функция
   окружения прогона. Она возвращает копию `os.environ`, в которую добавлен
   `PYTHONPYCACHEPREFIX`, указывающий на свежий временный каталог. Каталог
   создаётся под этот прогон и удаляется после него, в том числе после
   таймаута и после исключения.
2. Окружение из требования 1 передаётся через `env=` во все три вызова
   `subprocess.run`: в `run`, `collect` и `run_full_suite`.
3. Прочие переменные окружения прогона не меняются. Прогон по-прежнему
   не идёт через `runner.role_env` (см. докстроку `_pytest_command`).
4. Каталог кеша лежит вне `cwd` прогона и вне `config.ROOT`.
5. Полный набор с `-n`/`-p xdist` получает то же окружение, поэтому
   рабочие процессы xdist наследуют переменную. Это проверяется тестом
   аргументов вызова, без живого xdist.
6. В `tests/test_acceptance_pycache.py` лежат тесты по образцу
   `tests/test_acceptance.py:84–118` и `tests/test_acceptance_collect.py:80–89`
   (подмена `acceptance.subprocess.run`). У каждого теста есть строка
   «Ловит мутацию: …». Тесты покрывают три сценария:
   а) каждый из трёх вызовов получает `env` с `PYTHONPYCACHEPREFIX`;
   б) каталог из переменной существует во время вызова, лежит вне `cwd`
      и вне `config.ROOT` и удалён после возврата, в том числе после
      `subprocess.TimeoutExpired`;
   в) живой сценарий без подмены `subprocess.run`, описанный в AC-6.

## Критерии приёмки
AC-1. Каждый из вызовов `acceptance.run`, `acceptance.collect` и
`acceptance.run_full_suite` передаёт в `subprocess.run` аргумент `env`, в
котором задан `PYTHONPYCACHEPREFIX`. Ловит мутацию: `env` передан не во все
вызовы.

AC-2. Все прочие переменные `env`, переданного в `subprocess.run`, совпадают
с `os.environ` процесса пульта: значения те же, лишних и пропавших
ключей нет. Отличается только `PYTHONPYCACHEPREFIX`.

AC-3. Во время вызова `subprocess.run` каталог из `PYTHONPYCACHEPREFIX`
существует и лежит вне `cwd` прогона и вне `config.ROOT`. Ловит мутацию:
каталог создан в worktree.

AC-4. После возврата каждой из трёх функций каталог из
`PYTHONPYCACHEPREFIX` удалён. Он удалён и тогда, когда `subprocess.run`
бросил `subprocess.TimeoutExpired`. Ловит мутацию: каталог не удаляется.

AC-5. В `run_full_suite` вызов `subprocess.run` с аргументами xdist
(`-n`/`-p xdist`) получает `env` с `PYTHONPYCACHEPREFIX`. Проверяется по
аргументам вызова, без живого xdist.

AC-6. Живой сценарий без подмены `subprocess.run`. Во временном каталоге
лежат модуль и тест к нему. В `__pycache__` подложен `.pyc` от другой
версии модуля с тем же временем изменения и тем же размером исходника
(воспроизведение случая 02.10). `acceptance.run` по такому каталогу даёт
зелёный результат по актуальному исходнику. Ловит мутацию: переменная
убрана, и исполняется подложенный байткод.

AC-7. Тесты AC-1…AC-6 лежат в `tests/test_acceptance_pycache.py`. У каждого
тестового метода есть строка «Ловит мутацию: …».

## Оценка объёма и деление
Сработали два сигнала:
- «число затрагиваемых модулей/файлов». Счётчик guard учитывает все
  упомянутые в тексте пути `orchestrator/*.py`. Почти все они названы
  только как места вызова или файлы «только для чтения» (из ТЗ). Меняется
  один модуль кода (`orchestrator/acceptance.py`), к нему добавляется один
  новый файл тестов (`tests/test_acceptance_pycache.py`) и карта.
- «прогноз диффа не дан». Прогноз диффа: 12 КиБ (функция окружения и три
  `env=` в `acceptance.py` — около 2 КиБ, новый файл тестов вместе с живым
  сценарием AC-6 — около 10 КиБ).

Обоснование монолита (материал для решения Оператора): правка
`orchestrator/acceptance.py` состоит из одной функции окружения и передачи
её в три вызова, которые делят эту функцию. Если разделить вызовы, часть
прогонов пульта останется под тем же дефектом. Если отделить тесты от кода,
получится либо красная планка, либо код без проверки. Ни одно из этих
промежуточных состояний не стоит мержить отдельно.

## Не входит
- Запуски `scripts/codebase_map.py` (`pull.py:322`, `fsm_postmerge.py:89`,
  `brief.py:286`): это не pytest, и ложных красных они не давали.
- Канарейка (`canary.py:2202`).
- Прогоны планки самой ролью (строка копилки 12.09 о команде `plank`).
- Очистка уже лежащих `__pycache__` в worktree.
- Правка файлов только для чтения: `orchestrator/fsm_autogate.py`,
  `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`,
  `orchestrator/pull.py`, `orchestrator/amend.py`, `orchestrator/notes.py`,
  `orchestrator/advance_gates/`, `orchestrator/stack.py`,
  `orchestrator/runner.py`, `conftest.py`, остальные файлы `tests/`,
  `skills/`, `docs/adr/`, `docs/invariants.md`, `tests/test_invariants.py`,
  `tasks/`.
- Зелёный полный набор `tests/` и неослабление существующих тестов
  (требование 5 ТЗ): эти проверки держит пульт.

## Материалы
- ТЗ: `tasks/01M3Y7G6T3MK7A899521VF9N7B/TZ.md`. Источник — строка копилки
  02.10 (П1) «Ложный красный автогейт приёмки 01M3XTF1CEBXT4J7P0EKG5J342».
- Места вызова (только чтение): `fsm_autogate.py:279`, `fsm.py:947`,
  `fsm_merge_gate.py:679`, `pull.py:582`/`:584`,
  `advance_gates/acceptance.py:258`/`:260`,
  `advance_gates/tests_writing.py:369`/`:371`, `amend.py:481`/`:485`/`:616`,
  `notes.py:881`.
- Рамка ТЗ — $15. `budget_usd` поставлен на $25, потому что это нижняя
  планка калибровки (`config.BUDGET_CALIBRATION_TABLE`, skills/spec-authoring.md).
