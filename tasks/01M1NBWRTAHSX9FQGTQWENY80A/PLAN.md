---
task: 01M1NBWRTAHSX9FQGTQWENY80A
type: plan
author_role: developer
status: draft        # draft | ready | approved
schema_version: 3    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: Ответы Оператора в брифе ревьювера

## Подход

`orchestrator/review.py::review_package` сегодня не знает про
`ANSWER-n.md` вовсе — состав частей пакета фиксирован (задача, SPEC,
PLAN, прошлый REVIEW, форма вердикта, стат-список, diff). Добавляю
чтение ВСЕХ `ANSWER-n.md` задачи как отдельных компонентов пакета, той
же механикой sha256-журналирования, что уже несёт `brief.py` для
developer/analyst/test_author (`_journal_component`-style запись
`store.journal(..., "бриф: компонент", "<путь>: sha256=<hex>")`), но
БЕЗ вызова приватных функций `brief.py` напрямую — журналирование
пишется прямым вызовом `store.journal` + `context_package.sha256_of`
внутри `review.py` (тот же приём, что уже описан стабом в
`test_ac2_answer_component_journaled.py`), не через cross-module вызов
`brief._journal_component` (в кодовой базе нет прецедента вызова
приватных, с подчёркиванием, функций одного модуля orchestrator из
другого — только публичные `brief.new_run_id`/`wrap_boundary`/
`mark_unclosed_parts`/`component_hash` уже используются `review.py`).

Источник `ANSWER-n.md` — АРТЕФАКТНАЯ ветка задачи
(`artifact_source.resolve`, `artifact_branch.branch_name`), не
кодовая ветка `branch`, которой сегодня `review_package` уже читает
SPEC/PLAN/REVIEW: проверено эмпирически на этой самой задаче —
`tasks/01M1NBWRTAHSX9FQGTQWENY80A/ANSWER-1.md` коммитится `cmd_answer`
(`orchestrator/answer.py`) ИСКЛЮЧИТЕЛЬНО в артефактную ветку
(`artifact_branch.commit_files`, докстринг `answer.py`: «кодовую ветку
и рабочее дерево answer не трогает вовсе») — той же веткой уже
пользуется `brief._artifact_source_branch` для developer/analyst/
test_author. Чтение SPEC/PLAN/REVIEW через кодовую ветку `branch` —
существующее поведение вне зоны этой задачи (AC-3/AC-5 запрещают его
трогать), не меняю.

`review_package` получает новый первый параметр `conn` (та же позиция,
что у `brief.developer_brief(conn, task_id)`) — нужен для
`store.journal`. `artifact_source.resolve(conn, task_id)` сам `conn` не
разыменовывает (чистая функция имени ветки) — задачам без
`ANSWER-n.md` передача `conn` ничего не стоит: цикл журналирования не
выполняется ни разу, если список файлов пуст (AC-5).

Порядок компонента в пакете: после формы вердикта (`templates/
REVIEW.md`), перед стат-списком/diff — решения Оператора видны
ревьюверу до того, как он погружается в сам diff, но после того, как
у него на руках SPEC/PLAN/прошлый REVIEW/форма.

## Шаги

1. `orchestrator/review.py`: добавить `_answer_rels(task_id, branch)`
   (все `ANSWER-n.md` по возрастанию `n`, через `gitcmd.ls_tree_files` —
   аналог `brief._latest_answer_rel`, но без среза до последнего);
   `review_package` получает параметр `conn`, резолвит артефактную
   ветку через `artifact_source.resolve`, читает каждый ANSWER
   `artifact_text`, журналирует sha256 каждого найденного (непустого)
   компонента через прямой `store.journal(conn, task_id, "reviewer",
   "бриф: компонент", ...)`, вставляет как компоненты `parts` (той же
   `artifact_part`, что и остальные части) перед стат-списком —
   компоненты идут В СПИСКЕ `parts`, до вызова `context_package.
   discipline`, поэтому автоматически участвуют в общем размере тела и
   делении на части (AC-4).
2. `orchestrator/role_prompt.py`: прокинуть `conn` в вызов
   `review.review_package`.
3. `tests/test_review_package.py`: обновить существующие прямые вызовы
   `review.review_package(...)` новым параметром `conn` (патчинг
   `config.DB` в `ReviewPackageTest.setUp`, как уже делает
   `CmdRunReviewPackageTest`); добавить юнит-тесты `_answer_rels` и
   сборки пакета с несколькими ANSWER-файлами (сортировка по `n`,
   журнал, участие в делении на части, регресс без ANSWER-файлов).
4. Прогнать `tasks/01M1NBWRTAHSX9FQGTQWENY80A/acceptance_tests/`
   (залочены) — код чинится под них без правки тестов.
5. `scripts/guard.py` на PLAN.md, полный `tests/` — зелёный.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (все ANSWER-n.md — компоненты пакета) | 1 |
| 2 (sha256-журналирование новых ANSWER-компонентов) | 1 |
| 3 (ANSWER — в общем размере тела, деление на части наравне) | 1 |
| 4 (тесты: AC-1..AC-6) | 3, 4 |

## Влияние на систему

Сигнатура `review.review_package` меняется (новый первый параметр
`conn`) — единственный внешний вызывающий код, кроме тестов,
`orchestrator/role_prompt.py::mission_brief_package`, уже располагающий
`conn` (получен от `runner.cmd_run`); правка учтена шагом 2. Старые
`tasks/<other-id>/acceptance_tests/*.py` прежних задач (01M1GV6H5.../
01M1GCN1FPSC1A6WK9WD1Q1V8X), тоже зовущие `review_package(...)`
старой сигнатурой, — не часть `tests/` (полный набор — только
`tests/`, `acceptance.run_full_suite` гоняет `tests/`, не `tasks/*/
acceptance_tests`), `unittest discover -s tests` их не подхватывает —
не ломаются в контуре, который проверяет автогейт; отдельно их не
трогаю (замороженные артефакты смерженных задач, не моя зона).

Существующие компоненты пакета (SPEC/PLAN/прошлый REVIEW/форма/стат/
diff) не меняют ни источник чтения, ни журналирование (AC-3) — новый
код только добавляет компоненты, не переставляет и не изменяет
существующие; `test_all_parts_are_present_in_a_stable_order` и
аналогичные тесты `tests/test_review_package.py` остаются зелёными без
изменения ожиданий (кроме добавления `conn` в вызов).

Гейты/лимиты не ослабляются: `context_package.discipline`,
`CONTEXT_FILE_MAX_BYTES`, `CONTEXT_PART_MAX_BYTES` — без изменений,
ANSWER-компоненты проходят ту же дисциплину, что и остальные (AC-4).

Откат: правка локализована в `review.py`/`role_prompt.py`/
`tests/test_review_package.py`, ревертируется одним коммитом без
следов в остальной системе (новый git-вызов `ls-tree` на шаге ревью —
дополнительное чтение, не мутация).

## Риски

- `gitcmd.ls_tree_files` на шаге ревью — новый git-вызов, отсутствовавший
  раньше; для задач без ANSWER-файлов возвращает пустой список, для
  задач с ними — небольшая добавка ко времени сборки пакета (то же
  порядок стоимости, что уже платит `brief.py` для developer/analyst/
  test_author).

## Предложения системе
