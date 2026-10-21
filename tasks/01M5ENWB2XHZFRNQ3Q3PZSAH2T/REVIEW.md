---
task: 01M5ENWB2XHZFRNQ3Q3PZSAH2T
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: G5а — документы `knowledge` компонента в брифе ролей внешнего проекта

## Фаза A: план
- Таблица покрытия полна: требования 1–10 — шаг 1 (`orchestrator/brief.py`),
  11 — долгоживущий файл test_author. Один шаг размера MR — уместно для
  правки одной функции и её помощников.
- Подход не конфликтует с архитектурой: правка внутри
  `_project_conventions_parts` (требование 10), импорт `project_profile`
  внутри `_knowledge_of` с объяснённой причиной (круговой импорт),
  вызывающие и `review.py` не тронуты. «Влияние на систему» совпадает с
  диффом: изменён только `orchestrator/brief.py` (+ карта).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_knowledge_of`: `decide(target).profile` с `from_components`, затем `components(target)` ровно из одного с непустым `knowledge`; поле записи `KNOWLEDGE_FIELD` не читается. |
| 2 | OK | Куски `PROJECT_CONVENTIONS` прежние; `shown` пополняется до `render` (`shown.add(rel)` перед `render` и в корне, и у элементов); пометки в `shown` не попадают; `posixpath.normpath` сводит `./CLAUDE.md` к `CLAUDE.md`. |
| 3 | OK | `_tree_entries` — `ls-tree -z`; корень `PROJECT_CONVENTIONS` переведён на тот же помощник (ASCII-вывод прежний — эталоны AC-9/10 зелёные). Временная мутация «без `-z`» красит AC-7. |
| 4 | OK | `ls-tree -- <путь>` с `--literal-pathspecs` (`_clone_git(literal=True)`), текст — `show sha:rel`; подкаталог виден (AC-1). |
| 5 | OK | `ls-tree -r`, обычные (100644/100755) `*.md`, сортировка, убирание `shown` до среза `[:20]`; строки предела/не обычных/«файлов *.md нет» после кусков каталога; запись журнала `KNOWLEDGE_TRUNCATED_ACTION` с элементом и N. |
| 6 | OK | Все пять видов пометок; у файла каталога — «каталог <элемент>, документ <k>: <класс>» без пути и stderr, запись журнала той же строкой. |
| 7 | OK | Подписи по SPEC; путь файла каталога — первой строкой тела внутри границы. |
| 8 | OK | Перечень пометки базы — `PROJECT_CONVENTIONS` + элементы `knowledge`. |
| 9 | OK | Отказ/пропуск `decide`, `TargetsError` из `decide`/`components` → `None`, прежний вывод; развилка артели не тронута. |
| 10 | OK | Правка внутри `_project_conventions_parts`; AC-11 зелёный для 4 брифов и пакета ревьювера. |
| 11 | OK | Долгоживущий файл `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`: учебный git-проект, эталон литералами при подменённом `new_run_id`; существующие тесты не тронуты (дифф `tests/` пуст). |

## Замечания
Blocker/major нет. Наблюдения без требования правки (не заводятся в реестр):
- `orchestrator/brief.py` (`_knowledge_dir_parts`, `label … из {len(docs)}`) —
  файл каталога, чтение которого не удалось, остаётся в M (соседи подписаны
  «из 3», показаны 2). SPEC определяет M скобкой «после убирания повторов и
  предела», PLAN оговаривает единый отсчёт k/M явно — читается как
  допустимая трактовка.
- `irregular` считает все символьные ссылки/подмодули под каталогом, не только
  с именем `*.md` — SPEC этого не уточняет, PLAN заявляет именно так.
- Долгоживущий файл задачи шёл 96 с в CI (порог 60 с) — локально 48 с;
  стоимость тестов, не дефект кода.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `artel.py plank-run 01M5ENWB2XHZFRNQ3Q3PZSAH2T` — отказ «планки нет: в
  refs/artifacts нет test_*.py» (у задачи только долгоживущий файл в `tests/`).
- `python3 -m pytest -q tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`
  — 24 passed, 53 subtests passed (48 с).
- `python3 -m pytest -q tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py
  tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py tests/test_brief.py`
  — 46 passed, 38 subtests passed (прежнее поведение конвенций не сломано).
- Временная мутация: в `_tree_entries` убран `-z` (разбор по `\n`) —
  `test_ac7_cyrillic_file_and_dir_names_read_from_base` красный в обоих
  subTest; код возвращён `git checkout -- orchestrator/brief.py`, дерево чистое.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без
  строки `built_at_sha` — расхождений нет (карта свежа); файл возвращён.

## Предложения системе
- `plank-run` у задачи без планки в `acceptance_tests/` (только долгоживущий
  файл в `tests/`) отвечает отказом — скил review-checklist мог бы прямо
  называть замену: прогон долгоживущего файла `tests/test_<id>_*.py`.
