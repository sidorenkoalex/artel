---
task: 01M5R45M0FQB2WVRHYBRF81JM6
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Скорость пульта, git 5: пакетное чтение документов в read_tree и один rev-parse в suite_tree_hash

## Фаза A — план
Таблица покрытия PLAN полна: требования 1–6 привязаны к шагам. Шаги размером с MR. Подход не расходится с архитектурой: `ls-tree` идёт через `_git` → `gitcmd.in_repo`, `cat-file` — через `gitcmd.carpentry`, `show` — через `gitcmd.show`, то есть запись 33 `docs/invariants.md` соблюдена. Счёт вызовов «до/после» (требование 4, AC-9) приведён: всего, `show`, `ls-tree`, `cat-file` и `rev-parse`. Расхождение с оценкой исследования (−36 вместо ~−60) объяснено.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1а | OK | `orchestrator/artifact_branch.py:665-668`: `_head` вызывается один раз. Пустая голова ведёт в `_read_tree_by_files` — это прежний код `ls_tree_files`/`show` по имени ссылки, перенесённый без изменений. |
| 1б | OK | `_tree_entries` делает `ls-tree -r <sha> -- tasks/<id>` без `-z`/`-l`/`--name-only`, разбор — через `_LS_TREE_LINE.fullmatch`. `_cat_blobs` делает `gitcmd.carpentry(repo, ["cat-file","--batch"], dict(os.environ), input=bytes, text=False)`. При пустом списке oid `cat-file` не запускается. Прямого `subprocess` нет. |
| 1в | OK | Отказ, `None` или неразобранная строка `ls-tree` → `None` → прежний путь целиком. Строку с путём, который `splitlines` режет по U+2028/`\x85` при `quotePath=false`, regex не разберёт — тогда тоже прежний путь, это безопасно. |
| 1г | OK | Подмодуль (тип `commit`), путь в кавычках, `missing`, обрыв или неразобранный заголовок (`break` — всё, что дальше, не попадает в словарь), ненулевой код, `OSError` — во всех этих случаях `gitcmd.show(head, rel)`. Путь в кавычках при этом даёт прежний отказ `show`. |
| 1д | OK | `_blob_text`: строгое декодирование кодировкой `io.TextIOWrapper(io.BytesIO()).encoding`, затем замена `\r\n` и `\r` на `\n`, BOM не снимается. При ошибке — `None`, и файл выпадает так же, как при `UnicodeDecodeError`, который ловит `gitcmd.show` (`gitcmd.py:629`). |
| 1е | OK | Порядок ключей — порядок `ls-tree`. Имя, сигнатура и докстринг `read_tree` не изменились. `amend.py` и `retro.py` не тронуты (`git diff --stat`). |
| 1ж | OK | Основной путь — 3 вызова (`rev-parse --verify`, `ls-tree`, `cat-file`). Запасные пути — прежнее чтение плюс `rev-parse`. |
| 2 | OK | `orchestrator/acceptance.py:2912-2946`: сначала объединённый вызов. `None` → `None`. Ответ принимается только при коде 0 и ровно двух строках `splitlines()`, иначе выполняются прежние два вызова с прежними исходами. На git 2.30 `rev-parse` эхом выводит неизвестный флаг `--path-format=absolute` — получается три строки, поэтому срабатывает запасной путь, а не ложное принятие ответа. Остальное тело и `_with_tree_db_files` не тронуты. |
| 3 | OK | Есть `tests/test_01m5r45m0fqb2wvrhybrf81jm6_batched_reads.py`: pytest, настоящий git, эталоны, «Ловит мутацию:» в каждом тесте. Отличия эталона от дословной копии оговорены в докстринге модуля: адреса имён, `carpentry` вместо `Popen`, `_with_tree_db_files` опущен, а пустоту `tree_db_files` тест проверяет сам. |
| 4 | OK | Таблица в PLAN. |
| 5 | OK | Существующие файлы `tests/` не тронуты: в диффе `tests/` только новый файл. |
| 6 | OK | `python3 scripts/codebase_map.py` на ветке не даёт расхождений в карте, кроме `built_at_sha` (в моём прогоне — пустой содержательный дифф). |

## Замечания
Нет замечаний уровня blocker или major. Наблюдения уровня «вкус», без замечания:
- `_cat_blobs` передаёт повторяющийся oid дважды (вариант `same_oid`). Это корректно, разбор идёт по входному списку, но можно было бы убрать повтор. На поведение не влияет.
- `except OSError` в `_cat_blobs` при настоящем `carpentry` лишний: тот сам превращает `OSError` в код 1. Зато он нужен для заглушек (AC-4 `oserror`), так что ловушка оправдана.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний blocker/major/minor не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M5R45M0FQB2WVRHYBRF81JM6` — 5 passed, код выхода pytest 0.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5r45m0fqb2wvrhybrf81jm6_batched_reads.py tests/test_retro_artifact_branch_reads.py` — 48 passed за 15.10 с. Git локально 2.50.1, поэтому AC-5 не пропущен по `skipif`.
- `python3 scripts/codebase_map.py` и `git diff docs/codebase-map.md`: содержательных строк в диффе нет, карта свежая. Регенерацию я откатил через `git checkout docs/codebase-map.md`.
- `git diff bb6e426e...HEAD --stat -- tests/ orchestrator/amend.py orchestrator/retro.py orchestrator/gitcmd.py` — только новый `tests/test_01m5r45m0fqb2wvrhybrf81jm6_batched_reads.py`, требование 5 и AC-8 соблюдены.
- Прочитаны `gitcmd.show`, `ls_tree_files`, `carpentry`, `in_repo`, `branch_head_sha` и `artifact_branch._head`/`_git`. Цель — сверить, что 1д совпадает с декодированием `text=True` и что исключение `UnicodeDecodeError` текстового `ls-tree` проходит и по новому пути.
- Временную мутацию `_blob_text` (снять перевод `\r`) запустить не удалось: составную команду с `sed -i` не одобрили. Поэтому чувствительность AC-2 к этой мутации проверена только чтением теста: вариант `newlines`, сравнение с эталоном.

## Предложения системе
- Временная мутация из скила review-checklist требует правки файла и его возврата, но в шаге ревью составная команда `cp`/`sed -i` упирается в подтверждение. Нужна штатная команда пульта «mutate-run <файл> <патч> <тесты>» с автоматическим откатом (адрес: `skills/review-checklist.md`, раздел «Сторож — проверен временной мутацией»).
