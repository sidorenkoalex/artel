---
task: 01M3Y8570H9Y57YTP3M7E1AMHG
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Шаг test_author с целиком долгоживущей планкой не считается проваленным

## Подход
Расширяю только ветку `test_author` в
`orchestrator/runner.py::_missing_required_artifact`: прежняя проверка
`tasks/<id>/acceptance_tests/` остаётся первой, вторая — новый помощник
`_has_own_long_lived_test(cwd, task_id)`. Шаг засчитывается, если любая
из двух проверок нашла файл.

Помощник берёт пути, изменённые относительно базы ветки, в рабочем каталоге
роли: `gitcmd.diff_base("HEAD", repo=cwd)`, затем
`git diff --name-only <база> -- tests` (отслеживаемые изменения, в том числе
закоммиченные ролью) и `git ls-files --others --exclude-standard -- tests`
(новые файлы). Путь засчитывается, если
`guard.is_long_lived_test_path(task_id, rel)` истинно и файл есть на диске.
Признак тот же, что у `checkpoint._test_author_own_paths` («свой путь,
отличный от базы ветки»), а правило пути берётся только из `guard`. Сам
`_test_author_own_paths` переиспользовать нельзя: вне `tests_writing` он
возвращает пустое множество и видит только `git status`. Файл, который роль
закоммитила сама, он бы не засчитал. Если git не ответил, помощник
возвращает `False`, и шаг получает прежний отказ (fail-closed, ADR-0002).

В тексте отказа test_author теперь названы обе формы:
`acceptance_tests/ (файл в tasks/<id>/acceptance_tests/ либо долгоживущий
файл tests/test_<id>_<имя>.py)`. Префикс берётся из
`guard.long_lived_path_prefix`. Ветки остальных ролей не тронуты.

Бюджет — в пределах SPEC: одна функция, один новый тестовый файл и карта.

## Шаги
1. `orchestrator/runner.py`: импорт `scripts.guard`, ветка test_author в
   `_missing_required_artifact`, новый `_has_own_long_lived_test`.
   Проверка: долгоживущая планка
   `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py` —
   5 passed, 12 subtests passed.
2. `tests/test_test_author_long_lived_artifact.py`: четыре теста на
   настоящем git (`RealGitSandbox`) для свойств, которых планка не
   покрывает: файл, закоммиченный ролью, засчитывается; неизменённый файл
   базы не засчитывается; удалённый файл не засчитывается; при молчании git
   (`diff_base is None`) шаг получает отказ. Каждый тест проверен временной
   мутацией из его «Ловит мутацию»: M1 (только status), M2 (без
   сравнения с базой), M3 (без `is_file`), M4 (fail-open). Каждая мутация
   краснит ровно 1 тест из 4, код возвращён.
3. `python3 scripts/codebase_map.py` — карта перегенерирована.
4. Прогон затронутых модулей: `tests/test_agent_failure.py`,
   `tests/test_runner_role_environment.py`,
   `tests/test_long_lived_step_end_to_end.py` и планка — 32 passed,
   16 subtests passed.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (acceptance_tests/ ЛИБО свой долгоживущий файл, правило пути через `guard`) | 1, 2 |
| 2 (отказ называет обе формы) | 1 |
| 3 (analyst/developer/reviewer без изменений) | 1 (ветки не тронуты; AC-5 планки) |
| 4 (тесты в новом файле с «Ловит мутацию») | 2 |

## Влияние на систему
- Затронута только приёмка обязательного артефакта шага test_author в
  `run_agent_once`. Для остальных ролей код и текст отказа те же (AC-5
  зелёный). Изменилось одно: test_author с одной долгоживущей планкой
  больше не уходит в `_finish_missing_artifact` и не тратит попытку и
  бюджет впустую.
- Гейты не ослаблены. Доступ к `tests_writing -> …` по-прежнему решают
  гейты `advance_gates/tests_writing.py` (перечень сумм, группы планки),
  а не эта проверка. Она только определяет, засчитан ли шаг. Мандат
  коммита test_author (`checkpoint._test_author_own_paths`) не менялся.
- Чужой префикс и `tests/test_other.py` по-прежнему не засчитываются (AC-2).
  Удалённые файлы и файлы, не отличающиеся от базы, тоже не засчитываются
  (тесты шага 2).
- На каждый шаг test_author без `acceptance_tests/` добавляются три
  git-вызова в worktree.
- Откат — revert коммита задачи.

## Риски
- В журнале и в сообщении WIP-чекпоинта имя «артефакта» test_author стало
  длиннее: в нём пояснение обеих форм. По тексту
  «без артефакта acceptance_tests/» никто не разбирает журнал (grep по
  `orchestrator/` и `tests/` ничего не нашёл).

## Предложения системе
- `checkpoint._test_author_own_paths`: в докстринге сказано, что в
  `tests_writing` своими считаются и правки уже закоммиченных своих файлов,
  но код вычитает всё, что есть в базе ветки (`candidates - set(in_base)`).
  Правка файла, который уже есть в базе, своей не считается. Нужно
  сверить, что верно, докстринг или код.
- Песочница шага роли: в оболочке нет `ls`/`cat`/`rm` (`command not
  found`), а bash-функции с `${…}` отказывают как «expansion obfuscation».
  Временные мутации сторожей пришлось гонять отдельным python-скриптом в
  worktree. Стоит дать в `scripts/` штатный прогон «мутация → тест →
  откат».
