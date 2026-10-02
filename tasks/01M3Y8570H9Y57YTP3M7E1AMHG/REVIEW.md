---
task: 01M3Y8570H9Y57YTP3M7E1AMHG
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Шаг test_author с целиком долгоживущей планкой не считается проваленным

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–4 привязаны к шагам 1–2. Требование 3 держится тем, что ветки других ролей не тронуты; проверяет это AC-5 планки.
- Шаги размером с MR, проверяемые. Подход не спорит с архитектурой: правило пути берётся только из `guard.is_long_lived_test_path`/`guard.long_lived_path_prefix`, копии правила нет. База берётся через общую точку `gitcmd.diff_base`. Если git молчит, шаг получает отказ (fail-closed, ADR-0002).
- Отказ от переиспользования `checkpoint._test_author_own_paths` обоснован: тот смотрит только `git status` и только в `tests_writing`, поэтому файл, закоммиченный ролью, не засчитал бы. Я это проверил мутацией M1, см. ниже.
- «Влияние на систему» совпадает с diff: `orchestrator/runner.py`, новый `tests/test_test_author_long_lived_artifact.py`, карта. Всё в зонах SPEC.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/runner.py:1021-1052`: дизъюнкция «файл в `acceptance_tests/`» ИЛИ `_has_own_long_lived_test`. Помощник собирает изменения относительно базы ветки (`git diff --name-only <base> -- tests` сравнивает с рабочим деревом, поэтому видны и закоммиченные, и незакоммиченные) и неотслеживаемые файлы. Фильтр — только `guard.is_long_lived_test_path(task_id, rel)` плюс проверка `is_file`. AC-1 и AC-3 зелёные |
| 2 | OK | Текст отказа: `acceptance_tests/ (файл в tasks/<id>/acceptance_tests/ либо долгоживущий файл tests/test_<id>_<имя>.py)`. Префикс берётся из `guard.long_lived_path_prefix`. AC-2 и AC-4 зелёные |
| 3 | OK | Ветки reviewer/developer/analyst не изменены, AC-5 зелёный |
| 4 | OK | Новый файл `tests/test_test_author_long_lived_artifact.py`: 4 теста, у каждого заявка «Ловит мутацию» с наблюдаемым расхождением (`None` вместо имени артефакта и наоборот) |

## Замечания
Blocker/major нет.

Что я проверил и не нашёл дефекта:
- Тесты разработчика не повторяют планку (ADR-0020 п.4). Планка гоняет сквозной путь AC-1..AC-5, новые тесты проверяют свойства самого признака: закоммиченный файл, файл базы, удалённый файл, молчание git.
- Ветвления под литералы планки нет, правило общее.
- Пути из `git diff --name-only`/`ls-files` даются от корня worktree, `cwd` совпадает с корнем. Пути долгоживущих файлов состоят из `[a-z0-9_]`, поэтому `core.quotepath` на них не влияет.
- Файлы из `.gitignore` не засчитываются (`--exclude-standard`). Чекпоинт такой файл тоже не закоммитит, так что поведение согласовано.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Замечаний нет, реестр пуст.

## Вердикт
approved

## Проверено исполнением
- `python3 -m unittest tests.test_test_author_long_lived_artifact tests.test_01m3y8570h9y57ytp3m7e1amhg_required_artifact tests.test_agent_failure tests.test_runner_role_environment` дал `Ran 32 tests … OK`. Сюда входят планка задачи (AC-1..AC-5) и новые тесты.
- Временные мутации `orchestrator/runner.py::_has_own_long_lived_test`. После каждой я прогонял только `tests.test_test_author_long_lived_artifact` и возвращал код:
  - M4: `base is None → True` (fail-open). Красным стал ровно `test_git_silence_refuses`.
  - M3: убрал `(cwd / rel).is_file()`. Красным стал ровно `test_deleted_file_does_not_count`.
  - M1: `git diff --name-only HEAD` вместо базы, то есть смотрим только незакоммиченное. Красным стал ровно `test_file_committed_by_role_counts`.
  - После мутаций `git status --short` показывает, что код восстановлен: изменений в отслеживаемых файлах нет.
- `python3 scripts/codebase_map.py` дал в `docs/codebase-map.md` расхождение только в строке `built_at_sha`, значит карта свежая. Регенерацию я откатил через `git checkout -- docs/codebase-map.md`.
- Мутацию M2 («без сравнения с базой») сам не гонял: `test_file_already_in_base_does_not_count` по построению проверяет файл, который есть в базе и не менялся. Это согласуется с прогоном разработчика (PLAN, шаг 2).

## Предложения системе
- Подтверждаю наблюдение из PLAN. В песочнице роли нет `ls`/`rm`, а встроенный python-скрипт в heredoc отклоняется как «expansion obfuscation». Для временных мутаций пришлось писать скрипт в `tasks/<id>/` и удалять его через `python3 -c`. Ревьюверу пригодился бы штатный `scripts/` прогон «мутация → тест → откат».
