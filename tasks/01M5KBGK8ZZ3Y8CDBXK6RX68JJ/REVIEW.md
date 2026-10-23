---
task: 01M5KBGK8ZZ3Y8CDBXK6RX68JJ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Тест argv гейта полного набора не зависит от имени интерпретатора

## Фаза A: план
- Таблица покрытия полна: требования 1–4 → шаг 1. Один шаг на задачу из
  одного файла — размер MR, не микрооперация.
- Подход (одна подмена `pytest_python_executable` на весь метод, литерал
  ожидания, настоящий локальный git для условия ревизии) не конфликтует с
  архитектурой; код пульта не трогается.
- «Влияние на систему» = diff: `tests/test_suite_run.py` + регенерация
  `docs/codebase-map.md`; мандат ANSWER-1 назван, откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `tests/test_suite_run.py:334-359`: внешняя подмена `acceptance.stack.pytest_python_executable` охватывает `run_full_suite` и сборку `expected`; литерал совпадает с SPEC символ в символ; `assertEqual` всего argv; докстринг называет обе мутации (AC-2); `stack` импортирован. |
| 2 | OK | `GateArgvInterpreterIndependenceTest` (`:367-397`): временный главный репозиторий с `.artel/venv/bin/python3`, `git worktree add --detach` без venv, подмены `_MODULE_ROOT`/`VENV_DIR`/`stack.sys.executable`, вложенный прогон через `unittest.TestResult`, `wasSuccessful()`. Без сети. Красный на прежнем теле, зелёный на новом — проверено исполнением (ниже). |
| 3 | OK | `GateArgvInterpreterSourceTest` (`:400-418`): первый элемент argv равен значению подмены; ловит `sys.executable` и голый `python3` — проверено мутациями. |
| 4 | OK | Diff ветки — только `tests/test_suite_run.py` и `docs/codebase-map.md` (AC-8). Прочие методы файла не тронуты (AC-7): diff меняет только тело `test_gate_call_argv_unchanged`, остальное — добавления (хунк «переиспользует» старые строки под новый класс — артефакт диффа, не правка). |

Изменённое утверждение `GateArgvTest::test_gate_call_argv_unchanged`
сверено с base: прежнее `assertEqual(argv, _pytest_command("tests") + [-n, N, -p, xdist])`
заменено литералом той же длины и состава при подменённом интерпретаторе —
утверждение строже (ловит правку общей части `_pytest_command`), не слабее;
покрыто мандатом ANSWER-1 и его матрицей. Сужения данных/переноса под условие нет.

## Замечания

Нет замечаний blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest tests/test_suite_run.py -q -p no:cacheprovider` — 19 passed, 6 subtests passed.
- `python3 …/orchestrator/artel.py plank-run 01M5KBGK8ZZ3Y8CDBXK6RX68JJ` — 8 passed, код выхода 0.
- Временные мутации в процессе (`mock.patch` поверх `acceptance._pytest_command`, файлы не правились):
  - удалён `-p timeout` → `GateArgvTest::test_gate_call_argv_unchanged` красный (AC-3);
  - переставлены `no:cacheprovider`/`timeout` → тот же метод красный (AC-3);
  - первый элемент `sys.executable` → `GateArgvInterpreterSourceTest` красный (AC-6);
  - первый элемент голый `python3` → `GateArgvInterpreterSourceTest` красный (AC-6);
  - тело `test_gate_call_argv_unchanged` подменено прежним (ожидание через `_pytest_command` вне подмены) → `GateArgvInterpreterIndependenceTest` красный с ожидаемой причиной: `'/fake/bin/python' != '…/tmp…/main/.artel/venv/bin/python3'`; на новом теле — зелёный (AC-5).
- `python3 scripts/codebase_map.py` — расхождение только в строке `built_at_sha` (карта свежа по содержимому); регенерированный файл возвращён `git checkout`.

## Предложения системе
- `scripts/codebase_map.py` не знает режима проверки: `--check` молча перегенерирует файл в рабочей копии — ревьюверу, которому нельзя править код, легко оставить грязное дерево. Стоит либо режим `--check`, либо отказ на неизвестный флаг.
