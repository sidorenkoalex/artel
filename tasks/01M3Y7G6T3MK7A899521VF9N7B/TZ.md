---
task: 01M3Y7G6T3MK7A899521VF9N7B
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Прогоны pytest пульта не исполняют устаревший байткод из worktree

Источник: строка копилки 02.10 (П1) «Ложный красный автогейт приёмки
01M3XTF1CEBXT4J7P0EKG5J342»; разбор копилки после ревизии 02.10.

Факты (origin/main):
- 02.10 08:32Z автогейт приёмки 01M3XTF1CEBXT4J7P0EKG5J342 дал «2 failed»
  на исправном коде: полный набор `tests/` в worktree исполнил устаревший
  `orchestrator/__pycache__/fsm_advance.cpython-313.pyc`. Время изменения
  исходника и `.pyc` совпало до секунды (11:28:45), размер исходника не
  изменился (перестановка двух строк) — проверка свежести байткода по
  времени и размеру сочла кеш свежим. CI ветки зелёный; тот же тест с
  `PYTHONPYCACHEPREFIX` в чистый каталог — 4 passed. Следствие — ложная
  остановка задачи и ручной разбор.
- Все pytest-прогоны пульта идут через `_pytest_command`
  (`orchestrator/acceptance.py:21`) и три вызова `subprocess.run` без
  `env=`: `run()` (`:186`), `collect()` (`:240`), `run_full_suite()`
  (`:463`). Окружение наследуется от процесса пульта целиком; ни
  `PYTHONDONTWRITEBYTECODE`, ни `PYTHONPYCACHEPREFIX` в коде пульта,
  `conftest.py` и `tests/` нет.
- Через эти три функции идут: автогейт приёмки (`fsm_autogate.py:279`),
  полный набор при ручном подтверждении приёмки (`fsm.py:947`), полный
  набор на гейте мержа (`fsm_merge_gate.py:679`), прогон планки после
  подтяжки main (`pull.py:582`, `:584`), гейт приёмки
  (`advance_gates/acceptance.py:258`, `:260`), сухой сбор на
  tests_writing (`advance_gates/tests_writing.py:369`, `:371`),
  amend-tests (`amend.py:481`, `:485`, `:616`), doc-commit
  (`notes.py:881`).
- `PYTHONDONTWRITEBYTECODE=1` сам по себе НЕ лечит: он запрещает запись
  `.pyc`, но уже лежащий в `__pycache__` устаревший файл по-прежнему
  читается. Лечит отведение кеша в отдельный каталог
  (`PYTHONPYCACHEPREFIX`): существующие `__pycache__` worktree не
  читаются вовсе.

Требуется:
1. В `orchestrator/acceptance.py` — функция окружения прогона (рядом с
   `_pytest_command`): копия `os.environ` плюс `PYTHONPYCACHEPREFIX` на
   свежий временный каталог, созданный под этот прогон и удаляемый после
   него (в том числе при таймауте и исключении). Передаётся `env=` во все
   три вызова `subprocess.run` (`run`, `collect`, `run_full_suite`).
   Прочие переменные окружения не меняются (прогон по-прежнему не
   идёт через `runner.role_env` — см. докстроку `_pytest_command`).
2. Каталог кеша не лежит внутри `cwd` прогона и внутри `config.ROOT`
   (иначе он попадёт в рабочее дерево и под проверки guard/зон).
3. Полный набор с `-n`/`-p xdist` получает то же окружение: рабочие
   процессы xdist наследуют переменную (проверить тестом аргументов
   вызова, не живым xdist).
4. Тесты в `tests/` (по образцу `tests/test_acceptance.py:84–118` и
   `tests/test_acceptance_collect.py:80–89` — подмена
   `acceptance.subprocess.run`), каждый с «Ловит мутацию: …»:
   а) каждый из трёх вызовов получает `env` с `PYTHONPYCACHEPREFIX`
      («Ловит мутацию: env передан не во все вызовы»);
   б) каталог из переменной существует во время вызова, вне `cwd` и вне
      `config.ROOT`, и удалён после возврата — и после
      `subprocess.TimeoutExpired` («Ловит мутацию: каталог не удаляется
      / создан в worktree»);
   в) живой сценарий без подмены: во временном каталоге модуль и тест;
      в `__pycache__` подложен `.pyc` от другой версии модуля с тем же
      временем изменения и размером исходника (воспроизведение случая
      02.10); `acceptance.run` даёт зелёный результат по актуальному
      исходнику («Ловит мутацию: переменная убрана — исполняется
      подложенный байткод»).
5. Существующие тесты не ослабляются и не удаляются; полный набор
   `tests/` зелёный.

Зоны: orchestrator/acceptance.py, tests/test_acceptance_pycache.py,
docs/codebase-map.md.

Только чтение (не менять): orchestrator/fsm_autogate.py, orchestrator/fsm.py,
orchestrator/fsm_merge_gate.py, orchestrator/pull.py, orchestrator/amend.py,
orchestrator/notes.py, orchestrator/advance_gates/, orchestrator/stack.py,
orchestrator/runner.py, conftest.py, остальные файлы tests/, skills/,
docs/adr/, docs/invariants.md, tests/test_invariants.py, tasks/.

Не входит: запуски `scripts/codebase_map.py` (`pull.py:322`,
`fsm_postmerge.py:89`, `brief.py:286`) — не pytest, ложных красных не
давали; канарейка (`canary.py:2202`); прогоны планки самой ролью
(строка копилки 12.09 о команде `plank`); очистка уже лежащих
`__pycache__` в worktree.

Рамка: $15.
