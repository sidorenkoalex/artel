---
task: 01M2XJKKPHM5XDAE42838AMBQH
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Guard планки: артефакты задачи читаются только из артефактной ветки, отказ на выходе tests_writing

## Подход

Три зоны SPEC — три правки, одна механика.

1. **`scripts/guard.py` — статическая проверка по AST, не по тексту
   строки.** Новая функция `artifact_disk_read_errors_from_files(files)`
   над уже прочитанными `(label, текст)` парами (тот же приём, что
   `redness_marker_errors_from_files`/`indented_ac_marker_errors_from_files`)
   и обёртка `scan_artifact_disk_reads(tdir)` над ВСЕМИ
   `acceptance_tests/**/*.py` (не только `test_*.py` — AC-5). Нарушение —
   строковый литерал с именем из `ARTIFACT_FILE_NAMES` (`PLAN.md`,
   `SPEC.md`, `REVIEW.md`, `TZ.md`, `QUESTIONS.md`, `TEST_REPORT.md`,
   `ANSWER-`) внутри выражения доступа к файловой системе: операнд `/`
   (`str / str` в Python не существует, поэтому литерал-операнд `/` — всегда
   pathlib, и `TASK_DIR / "PLAN.md"` через переменную ловится так же) или
   поддерево вызова `open`/`Path`/`pathlib.Path`/`os.path.join`/
   `os.path.exists`/`.read_text(`/`.joinpath(` (включая цепочку получателя —
   `TASK_DIR.joinpath("PLAN.md").read_text()`). AST выбран, потому что AC-4
   планки нарочно ставит имя артефакта в концевой комментарий строки с
   настоящим `open("fixture.txt")` — текстовая эвристика тут даёт ложную
   ошибку. `gitcmd.show`/`artifact_branch`/`subprocess.run` в набор
   выражений доступа не входят, поэтому требование 2 выполняется без
   отдельного белого списка. Текст ошибки — `<label>:<строка литерала>:
   чтение артефакта задачи <имя> с диска — читай из артефактной ветки:
   gitcmd.show(artifact_branch.branch_name(TASK_ID), "tasks/<id>/<имя>")`
   (требование 3); для префикса `ANSWER-` рецепт называет настоящее имя из
   литерала (`ANSWER-1.md`). Файл с `SyntaxError` ошибок здесь не даёт —
   синтаксис ловит сухой сбор того же гейта точнее. Метка — путь
   относительно `tdir` (`acceptance_tests/test_x.py`): каталог на гейте —
   временная материализация, абсолютный путь в истории отказов брифа
   бесполезен.

2. **`orchestrator/advance_gates/tests_writing.py` — гейт.** Новый
   предикат `_tests_writing_artifact_source_gate(acc_tdir, task_id)`
   возвращает `GateRefusal("переход отклонён: планка читает артефакты с
   диска", "; ".join(errors), hint)` — тот же каркас `_run_gates`, что у
   сухого сбора, поэтому запись уходит `store.journal(..., "fsm", ...)` с
   префиксом «переход отклонён: », и история отказов брифа test_author
   (`brief.advance_refusal_history`) и стоп-кран T038 видят её тем же
   классом (AC-7); в `brief._ROLE_NOT_FINISHED_REFUSAL_ACTIONS` действие не
   вносится. **Ключевое решение:** предикат зовётся из
   `_tests_writing_dry_collect_gate` ДО `acceptance.collect`, а не
   отдельным элементом списка `_run_gates` в `fsm_advance.tests_writing`
   (`orchestrator/fsm_advance.py:337`) — этот файл не входит в зоны SPEC
   (`scripts/guard.py, orchestrator/advance_gates/tests_writing.py,
   tests/`), и гейт зон на `in_dev -> review` отказал бы правке. SPEC
   формулирует место как «рядом с сухим сбором» — вложение в тот же гейт
   этому соответствует; статическая проверка дешевле субпроцесса pytest и
   даёт точнее диагноз, поэтому идёт первой. Каталог — тот же `acc_tdir`,
   что у сухого сбора (`_tests_writing_acceptance_dir`): материализованная
   из ветки планка для внешнего target/worktree, `tdir` — для остального.

3. **`tests/` — два новых файла**, `check()`/`main()` guard не трогаются
   (требование 4/AC-8).

Бюджет: SPEC оценил $40, PLAN укладывается (три файла кода + два файла
тестов, ~330 строк диффа) — `budget_usd` не поднимается.

## Шаги

1. `scripts/guard.py`: `ARTIFACT_FILE_NAMES`, `_FS_ACCESS_CALLS`,
   `_FS_ACCESS_METHODS`, `ARTIFACT_DISK_READ_RECIPE_TMPL`, помощники
   `_dotted_name`/`_artifact_name_in_literal`/`_artifact_literals`/
   `_is_fs_access_call`, функции `artifact_disk_read_errors_from_files`
   и `scan_artifact_disk_reads` — после `scan_indented_ac_markers`.
   Ни `check()`, ни `main()` не меняются.
2. `orchestrator/advance_gates/tests_writing.py`: константа
   `ARTIFACT_DISK_READ_ACTION`, предикат
   `_tests_writing_artifact_source_gate`, вызов первым действием
   `_tests_writing_dry_collect_gate`.
3. `tests/test_guard_artifact_disk_read.py` — функция guard: пять
   образцов + f-строки + `/` через переменную (AC-1), семь имён и
   `ANSWER-` (AC-5), рецепт (требование 3), дедупликация вложенных
   выражений, порядок по строкам, разрешённые источники (AC-2/AC-3),
   докстринги/комментарии/концевой комментарий (AC-4), `SyntaxError`,
   область `_helper.py` и относительная метка (AC-5), отсутствие
   каталога, `--all` + `check()` зелены и спай `scan_artifact_disk_reads`
   не вызван (AC-8).
   `tests/test_fsm_advance_tests_writing_artifact_source.py` — гейт через
   настоящий `fsm.cmd_advance` в `LightTransitionSandbox`: именованное
   действие, detail с файлом/строкой/рецептом, печать detail и подсказки,
   состояние остаётся `tests_writing` (AC-6); `collect` не зван на
   отклонённой планке; лок не переставляется; чистая планка с
   `gitcmd.show` проходит в `in_dev`; отказ виден в
   `brief.advance_refusal_history` для `test_author` (AC-7).
4. Регенерация `docs/codebase-map.md` (`python3 scripts/codebase_map.py`),
   прогон планки задачи по файлам и тестов затронутых модулей, guard на
   PLAN.md, коммит кода в ветку.
5. Приложение к PLAN.md — unified diff к `skills/test-authoring.md`
   (ниже, применяет Оператор), проверен `git apply --check`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (функция guard над `*.py` планки, набор выражений доступа) | 1, 3 |
| 2 (gitcmd.show/artifact_branch/subprocess, докстринг/комментарий — не ошибка) | 1, 3 |
| 3 (текст ошибки: файл, строка, рецепт) | 1, 3 |
| 4 (не в `check()`/`main()`) | 1, 3 |
| 5 (гейт выхода `tests_writing`, именованный отказ того же класса) | 2, 3 |
| 6 (диф к `skills/test-authoring.md` приложением) | 5 |
| 7 (тесты в `tests/`, соседние наборы зелены) | 3, 4 |

## Влияние на систему

- **Новый отказ на живом переходе `tests_writing -> in_dev`** — только для
  планок, читающих артефакт с диска; исторические планки не
  сканируются (`--all`/`check()` не зовут проверку — AC-8 юнит-тест со
  спаем и планка задачи). Живые задачи, у которых планка уже залочена
  и лежит в `in_dev` и дальше, гейт не пересекают.
- **Инвариант `docs/invariants.md:90`** («новые правила guard и гейтов
  действуют на живые задачи, история не переписывается») исполняется
  буквально: правило действует на выходе `tests_writing`, backfill по
  `tasks/` не делается.
- **Гейты рядом** — трассируемость AC, посторонние файлы планки (AC-8
  01M2ARQRDV), сухой сбор — не ослаблены: новый предикат добавлен ДО
  `acceptance.collect` внутри того же гейта, порядок и тексты остальных
  отказов не меняются; `tests/test_fsm_advance_tests_writing_dry_collect.py`
  зелен без правок.
- **Стоп-кран T038 / история отказов брифа** — общий механизм не
  правится; отказ идёт стандартным `_run_gates`, действие не внесено в
  `brief._ROLE_NOT_FINISHED_REFUSAL_ACTIONS`.
- **Ложные срабатывания** — снижены разбором AST: имя в комментарии,
  докстринге, в аргументах `gitcmd.show`/`subprocess.run`, в `+`-конкатенации
  не ловятся. Остаточный класс: литерал имени артефакта внутри вызова
  `open`/`Path`/… к постороннему файлу с похожим именем (например
  `open("MY_PLAN.md")`) — подстрочное совпадение, роль получит отказ с
  файлом/строкой и переименует фикстуру; SPEC требует именно вхождение
  имени в литерал.
- **Откат** — revert одного merge-коммита: новые функции guard никем, кроме
  гейта, не вызываются; строки `_tests_writing_dry_collect_gate`
  возвращаются к прежним.
- `orchestrator/pull.py`, `orchestrator/acceptance.py`, `orchestrator/amend.py`,
  `orchestrator/fsm_advance.py` не меняются (SPEC «Не входит», зоны).

## Риски

- Планка, у которой `acceptance_tests/` в момент гейта материализован из
  ветки (внешний target, self на своей ветке): проверка читает тот же
  каталог `acc_tdir`, что и сухой сбор, — если материализация вернула
  каталог без файлов (git не ответил), проверка молчит так же, как молчит
  сухой сбор на пустой планке; отдельного поведения не вводится.
- `amend-tests` новую проверку не зовёт (SPEC «Не входит», отдельное ТЗ по
  `orchestrator/amend.py:311–320`).

## Предложения системе

- SPEC называет зоны `scripts/guard.py, orchestrator/advance_gates/tests_writing.py,
  tests/`, но список гейтов выхода `tests_writing` живёт в
  `orchestrator/fsm_advance.py:332–340` — новый гейт этого состояния
  нельзя добавить отдельным элементом `_run_gates`, не выйдя из зон;
  пришлось вложить предикат в гейт сухого сбора. Класс: «зоны SPEC
  указывают модуль гейтов, а точка подключения — в другом модуле»
  (skills/spec-authoring.md, раздел зон — отметить, что для
  `advance_gates/*` точка вызова в `fsm_advance.py` входит в зону).

## Приложение: unified diff к `skills/test-authoring.md` (требование 6, применяет Оператор)

Диф снят `git diff` с временной правки рабочей копии и возвращён
`git checkout -- skills/test-authoring.md`; в ветке задачи файл не
изменён. Проверка `git apply --check` этого дифа (извлечённого из PLAN.md)
на чистом дереве ветки прошла с кодом 0 — см. «Шаги», п. 5.

```diff
diff --git a/skills/test-authoring.md b/skills/test-authoring.md
index 157036c3..1dde9f92 100644
--- a/skills/test-authoring.md
+++ b/skills/test-authoring.md
@@ -56,6 +56,24 @@ guard разбирает её текстом, без импорта файлов
 пока ты не переименуешь файл под `_*.py` или не встроишь его содержимое
 в сами тесты.
 
+## Источник артефактов задачи — только артефактная ветка
+Источник артефактов задачи в планке: только артефактная ветка через
+`gitcmd.show(artifact_branch.branch_name(TASK_ID), "tasks/<id>/PLAN.md")`;
+диск рабочей копии — не источник, пульт материализует только
+`acceptance_tests/`. В worktree `tasks/<id>/` лежит целиком, а в среде
+прогона гейта (`orchestrator/pull.py`, `orchestrator/acceptance.py::
+materialize_from_branch`) — один `acceptance_tests/`: тест, читающий
+`PLAN.md`/`SPEC.md`/`REVIEW.md` через `Path(__file__)…/"PLAN.md"`,
+`open(`, `.read_text(`, `os.path.join`, `os.path.exists`, зелен у тебя
+и красен на гейте (12.09 01M2B6K3EM AC-8, 13.09 01M2CN465W test_ac4 —
+оба чинились руками через `amend-tests`). Выход из `tests_writing`
+отказывает такой планке текстом «переход отклонён: планка читает
+артефакты с диска» с файлом, строкой и рецептом; чтение через
+`gitcmd.show`/`artifact_branch` или `subprocess` с `git show`/`git
+cat-file` — законно, имя артефакта в докстринге или комментарии — тоже.
+Образец: `tasks/01M2CN465WEDCF6D77V37FJ82E/acceptance_tests/
+test_ac4_invariants_diff_attachment.py`.
+
 ## Чувствительность: у теста — заявленная мутация
 Тест обязан ловить поломку, а не исполнять ритуал покрытия. Для
 каждого тестового метода назови в его докстринге конкретную
```
