---
task: 01M5R45M0FQB2WVRHYBRF81JM6
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Скорость пульта, git 5: пакетное чтение документов в read_tree и один rev-parse в suite_tree_hash

## Подход
`read_tree` (`orchestrator/artifact_branch.py`): голова ссылки разрешается
один раз (`_head`); пустая — прежний путь целиком (`_read_tree_by_files`:
`gitcmd.ls_tree_files`/`gitcmd.show` по имени ссылки, как раньше — его
подменяют лёгкие песочницы). Голова есть — один `git ls-tree -r <sha> --
tasks/<id>` через `_git` → `gitcmd.in_repo` (`_tree_entries`, разбор строки
`<режим> SP <тип> SP <oid> TAB <путь>`; отказ, `None` или неразобранная
строка — прежний путь целиком). Затем один `git cat-file --batch` через
`gitcmd.carpentry(..., dict(os.environ), input=b"<oid>\n"…, text=False)`
(`_cat_blobs`; записей-blob нет — не запускается). Байты → текст
`_blob_text`: кодировка `io.TextIOWrapper(io.BytesIO()).encoding` строго,
затем `\r\n`/`\r` → `\n`, BOM не снимается — то же, что `text=True` у
`subprocess.run` в `gitcmd.show`. Подмодуль, путь в кавычках, `missing`,
оборванный/неразобранный ответ (всё после места обрыва), ненулевой код или
`OSError` у `cat-file` — `gitcmd.show(<sha>, rel)` по одному. Порядок ключей —
порядок `ls-tree`. Прямого `subprocess` в модуле нет.

`suite_tree_hash` (`orchestrator/acceptance.py`): первый вызов —
`rev-parse --show-toplevel --path-format=absolute --git-path index`. Код 0 и
ровно две строки — корень и путь индекса (`.strip()`), второго `rev-parse` нет.
`None` — `None`. Иначе (git 2.30 без `--path-format`, одна строка) — прежние
два вызова на прежних местах с прежними исходами. Остальное тело и
`_with_tree_db_files` не тронуты.

Счёт вызовов git (требование 4, AC-9) снят шимом `git` в `PATH` (сценарий
во временном каталоге пишет argv каждого процесса git, включая дочерние
процессы пульта), прогон
`python3 -m pytest tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac5ProofMismatchTest`,
файл тестов не менялся; подкоманда — первое слово после ведущих `-C <путь>`.

| Показатель | До (b5ed9438) | После (2c34c10e) |
|---|---|---|
| всего | 1332 | 1296 |
| show | 121 | 103 |
| ls-tree | 91 | 91 |
| cat-file | 0 | 3 |
| rev-parse | 372 | 351 |

Снято 36 вызовов, а не ~60 из оценки исследования: в этом тесте `read_tree`
читает каталоги из 1–2 файлов, и сбереженные `show` частично съедает
добавленный `rev-parse --verify` головы; `ls-tree` заменён один к одному.

## Шаги
1. `read_tree` + закрытые помощники `_read_tree_by_files`, `_tree_entries`,
   `_cat_blobs`, `_blob_text`, `_LS_TREE_LINE` в `orchestrator/artifact_branch.py`.
2. Объединённый `rev-parse` с запасным путём в начале `suite_tree_hash`.
3. `python3 scripts/codebase_map.py` — карта только выводом генератора.
4. Проверка: `tests/test_01m5r45m0fqb2wvrhybrf81jm6_batched_reads.py` — 41
   passed; тесты, вызывающие `read_tree`/`suite_tree_hash`, плюс
   `test_snapshot_closing_outcome.py`, `test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`,
   `test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py` — 351 passed, 244 subtests.
5. Счёт вызовов git до/после (таблица выше).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (а–ж) | 1, 4 |
| 2 | 2, 4 |
| 3 | долгоживущий файл test_author; прогон — 4 |
| 4 | 5 |
| 5 | 4 (существующие тесты не правлены, зелёные) |
| 6 | 3 |

## Влияние на систему
Инвариант 33 (`docs/invariants.md`: работа со ссылкой документов — через
точку подмены `gitcmd`) не ослаблен: `read_tree` только читает, `ls-tree`
идёт через `gitcmd.in_repo`, `cat-file` — через `gitcmd.carpentry`, `show` —
через `gitcmd.show`; `subprocess` в `artifact_branch.py` не добавлен.
Вызывающие (`amend.py`, `retro.py`), `gitcmd.py`, существующие тесты не
тронуты. `suite_tree_hash` на git 2.30 идёт прежним путём (AC-7). Откат —
revert коммита ветки.

## Риски
- Мелкие каталоги: при отсутствующей ссылке вызовов два вместо одного
  (принято SPEC 1ж).
- Гонка в запасных путях прежняя (SPEC «Не входит»).

## Предложения системе
- Сторож роли в `conftest.py` отказывает `pytest -n` (воркеры xdist
  читаются как полный прогон): прогон 18 файлов затронутых модулей шёл
  6:40 последовательно.
- Скрипта счёта вызовов git по подкомандам у пульта нет — пришлось писать
  шим `PATH` руками; требование 4 повторится в следующих задачах «Скорость
  пульта, git N».
