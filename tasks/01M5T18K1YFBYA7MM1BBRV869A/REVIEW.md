---
task: 01M5T18K1YFBYA7MM1BBRV869A
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Конвенции внешнего проекта в брифе — из файла пульта, сверка дрейфа

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–11 разнесены по шагам 1–5.
- Шаги размером с MR (модуль `conventions.py`, бриф и миссии, `doctor`,
  документ, тесты). Это не микрооперации и не «сделать всё».
- Подход не расходится с архитектурой. Бриф, `doctor` и команда разбирают
  заголовок одной функцией `conventions.parse`, поэтому AC-3/AC-9/AC-11
  согласованы самим устройством кода. Подмодуль `doctor` следует правилу
  фасада: импортирует только `orchestrator.doctor`, коллаборант `conventions`
  подключён в `doctor/__init__.py`. `review.py` не тронут, как и требует
  SPEC «Не входит».
- «Влияние на систему» совпадает с diff: 12 файлов, все в `zones:`; карта
  перегенерирована в том же коммите 8fe480406. Вне зоны правок нет;
  `.github/`, `gates.yaml`, `skills/`, `templates/` не тронуты. Путь отката
  описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `brief._pult_conventions_part` (brief.py ~:783): `render(..., "conventions.md (.artel/projects/<имя>/conventions.md)", ...)`. Путь берётся из `conventions.path` → `repo_context.projects_root()`. Блок `PROJECT_CONVENTIONS` и `_read_project_conventions` удалены. |
| 2 | OK | `conventions.parse` отдаёт `lines[end+1:]`. Тело и опись (sha256 тела) проверяет AC-1 долгоживущего файла. |
| 3 | OK | Компонент `conventions.md` собирается до `resolve`. Если `ctx is None`, `_unread_mark` с `unresolved_reason` выдаётся всегда (AC-14). База читается только при наличии `knowledge`, `shown=set()`. |
| 4 | OK | `read_file`: `lstat` → «файла нет» / «не обычный файл», затем `O_NOFOLLOW`+`fstat`, затем UTF-8, затем текст `OSError`. Пометка и журнал — в `_pult_conventions_part`. |
| 5 | OK | Предел работает через `render` потребителя по тексту без заголовка. AC-4 проверяет оба края. |
| 6 | OK | `parse`/`_valid_stamp`: нет закрывающей `---`, `YamlError`, ветка не строка или пуста, sha не hex40, `sources` не непустой dict hex40 — всё это `BROKEN`. Блок без `conventions_stamp` — `PLAIN`. |
| 7 | OK | `stamp_refusal`: артель, неизвестный проект, клон (`--show-toplevel`), `refs/heads/<base>`, файлы не названы, режимы дерева, `read_file`, сломанный заголовок. Сверх SPEC — обратный разбор нового заголовка. Запись атомарная, права файла сохраняются. Сетевых вызовов нет (AC-13). |
| 8 | OK | `doctor/project_conventions.py` + `cli.all_checks`, сверка через `ls-tree` коммита базы. У артели строки нет. Дополнительный `warn` при несовпадении `base_branch` отметки с базой записи покрыт `tests/test_conventions.py::DriftBranchTest`. |
| 9 | OK | `docs/target-onboarding.md` содержит все пункты; AC-12 планки зелёный. |
| 10 | OK | Миссии analyst/developer: «файл пульта conventions.md, разобранный при Операторе». Фраза «конвенции проекта» в миссии developer сохранена (AC-7). |
| 11 | OK | Список обвязки берётся из `repo_context.wrapper_paths(ctx)`, формула — `config.is_protected_path`. Пометка элемента — «путь обвязки, пропущен». В каталоге обвязка отсекается до предела, N считается только по `*.md` (ANSWER-2 п.2). |

Сверка тестов с мандатом ANSWER-1/ANSWER-2:
- Эталоны `ETALON_JOURNAL/MANIFEST/REVIEW` (У2) сверены построчно по диффу. Ушли только хвост `'\n' 'конвенции проекта: AGENTS.md — файла нет …'` и подпись `CLAUDE.md (корень ветки …)`. Подпись заменена на `conventions.md (.artel/projects/uchebnyetalon/conventions.md)`. Тело, границы, 122 байт и sha256 те же, все значения — литералы.
- У1: в `NoNetworkTest` и `test_ac4` есть элемент `knowledge`, добавлено `assertIn(guide)`, запрет сети не тронут.
- У3: в `ProjectConventionsInBriefTest` только добавлено `assertNotIn(base_claude)`.
- У4 и У6: в `BothConventionFilesTest` опись и подпись проверяются тем же видом. `assertNotEqual` заменён на `assertEqual(len(label_lines), 1)` и `header == label_lines[0]`. Тексты базы добавлены в `others`.
- У5: в `run_scenario` есть `knowledge: [guide.md]`, перебор четырёх сценариев не сокращён. «git не ответил» идёт через `fail_base_reads`, а не через `fail_claude_reads`, поэтому сценарий по-прежнему валит чтение базы.
- Решение 10: `test_ac10` использует подмену `os.open` и проверяет «не разобраны: <текст ошибки>».
- Два расхождения PLAN с буквой мандата в `RepeatsAndMarksTest` принимаю, это не ослабление. (1) `assertFalse(...)` заменено на `assertEqual(len(...), 1)` — строже. (2) `assertNotIn("knowledge компонента")` при новой фикстуре невыполнимо по построению. Свойство «второго куска нет» держит сохранённый `assertEqual(len(headers), 1)`; добавленный `assertIn("пропущен")` закрепляет, что единственный заголовок — пропуск по размеру. Сужения данных под неизменными утверждениями не нашёл: `KnowledgeSandbox.prepare` только добавляет `conventions.md`.

## Замечания
Блокеров и major нет. Ниже наблюдения уровня вкуса, в реестр они не
внесены и мерж не блокируют:
- `tests/test_conventions.py::ParseTest::test_uppercase_or_unquoted_numeric_sha_is_broken`. Имя метода обещает и случай с заглавными буквами, но в подтестах есть только sha из цифр без кавычек и короткий blob.
- `conventions.tree_objects`. Если вызвать `conventions-stamp` одновременно с `docs` и `docs/x.md`, `git ls-tree` не печатает запись каталога. Проверил на временном репозитории: вывод содержит только `docs/x.md` и `CLAUDE.md`. Отказ всё равно будет, но с причиной «нет в дереве» вместо «каталог». Случай редкий, и записи файла он не допускает.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: дефектов уровня blocker/major в итерации 1 не найдено.

## Вердикт
approved

## Проверено исполнением
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M5T18K1YFBYA7MM1BBRV869A` — 24 passed, код выхода pytest 0. В их числе AC-6 (побайтная сверка брифов артели) и AC-12.
- `python3 -m pytest -q -p no:cacheprovider -p no:xdist` по файлам задачи — 119 passed, 115 subtests passed, 41 с. Файлы: `tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_brief.py`, `tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_stamp.py`, `tests/test_conventions.py`, `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, `tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py`, `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`. Первая попытка с `-n 4` не собрала тесты: рабочие процессы xdist упали «node down», ни один тест не прошёл. Повторил последовательно.
- Временный git-репозиторий, `git --literal-pathspecs ls-tree -z HEAD -- docs/AGENTS.md CLAUDE.md docs`. Вложенный путь находится, значит `conventions-stamp … docs/AGENTS.md` из документа рабочий. Запись каталога при соседнем пути внутри него не печатается — см. наблюдение выше.
- `git log -- docs/codebase-map.md`: карта перегенерирована в коммите кода задачи 8fe480406, новые модули в ней есть.

## Предложения системе
- Пакет ревью несёт подсказку «Изменённые утверждения тестов» с исходом «покрыто мандатом» и в случаях, когда вид утверждения сменился (`assertNotIn` → `assertIn`). Полезно показывать вид «было/стало» прямо в строке гейта, чтобы ревьюверу не искать его в диффе.
