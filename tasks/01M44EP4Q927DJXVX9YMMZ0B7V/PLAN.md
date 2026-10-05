---
task: 01M44EP4Q927DJXVX9YMMZ0B7V
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Помощник планки от пульта

## Подход
Исходный текст помощника — обычный модуль `orchestrator/plank_helper.py`
(только stdlib: `os`, `subprocess`, `tempfile`, `pathlib`) с блоком
«значения выкладки» (`TASK_ID`, `CODE_ROOT`, `DOCS_REPO`, `DOCS_REVISION`,
`DIFF_BASE`, `DIFF_BASE_SOURCE`). Выкладка (`acceptance.py`) читает этот
текст, заменяет каждую строку блока литералом `repr(значение)` и кладёт
результат как `_pult.py` в общий узел `_write_plank` — поверх одноимённого
файла планки и вне прунинга (ключ словаря `wanted`). Так помощник получают
все потребители выкладки без их правки.

- Ревизия выкладки: `materialize_from_branch` разрешает `branch` в sha один
  раз (`rev-parse <rev>^{commit}` в репозитории задачи) и читает список и
  тексты планки по этому sha — помощник называет ровно ту ревизию, с
  которой выложены файлы; `materialize_files` (черновик) берёт голову ссылки.
- База и источник: `gitcmd.diff_base`/`diff_base_source` ветки рабочей
  копии (`gitcmd.current_branch(code_dir)`, `repo=code_dir` — рабочая копия
  делит ссылки с клоном, значение совпадает с гейтом зон).
- `artifact_text`: `git ls-tree -z <sha> -- tasks/<id>/<name>` → нет записи
  `blob` — `None`; иначе `cat-file blob`. Любой ненулевой код git —
  `ArtifactReadError` (подкласс `GitError`). `GIT_CEILING_DIRECTORIES` и
  снятые `GIT_DIR`/`GIT_INDEX_FILE`/… не дают git уйти в объемлющий
  репозиторий.
- `changed_paths`: `git diff --name-only -z BASE HEAD` + `git ls-files
  --others --exclude-standard -z` минус `tasks/<id>/`; `branch_diff`:
  `git diff BASE HEAD`. Правило записано в докстрингах модуля и функции.
- `apply_check`: дифф файлом (как `plan_appendix.git_apply`) во временный
  каталог; `read-tree HEAD` во временный индекс (`GIT_INDEX_FILE`) и
  `git apply --check --cached [--reverse]` — рабочая копия и её индекс не
  трогаются, грязное дерево ответ не меняет.
- Пустая планка: помощник кладётся и к ней (так требует планка: песочницы
  AC-1/3/4/5/6 выкладывают ссылку без `acceptance_tests/`). Чтобы каталог
  «только с `_pult.py`» оставался «тесты не заведены», введён
  `acceptance.plank_present(tests_dir)`; им пользуются `_run_targets`
  (`run`/`collect`) и `summary`.
- Резервирование имени (требование 5): `guard.RESERVED_PLANK_HELPER_NAME`
  посторонний для `guard.is_extraneous_acceptance_test_file` — автокоммит
  (`checkpoint._journal_stray_step_artifacts`, без правки checkpoint.py)
  отбрасывает и копию помощника, оставленную в рабочей копии кода (AC-7),
  и `_pult.py` черновика с записью журнала. Отказ выхода из `tests_writing`
  — в уже вызываемом `_tests_writing_stray_plank_files_gate`: (а) `_pult.py`
  в голове ссылки документов — отказ сразу; (б) запись «посторонние файлы
  в каталоге планки» с `acceptance_tests/_pult.py` — подсказка «имя занято
  помощником пульта». Действие — прежнее «переход отклонён: посторонние
  файлы планки» (класс «чинит роль» в `refusal_classes.py`, вне зоны —
  новое действие стало бы «чинит Оператор» и остановило бы `auto`).
- Рецепт (требование 6): `ARTIFACT_DISK_READ_RECIPE_TMPL` и подсказка гейта
  называют `from _pult import artifact_text; artifact_text("<имя>")`;
  правило отказа не тронуто.

## Шаги
1. `orchestrator/plank_helper.py` — помощник (готово).
2. `orchestrator/acceptance.py` — `PLANK_HELPER_NAME`, `_docs_revision`,
   `_plank_helper_text`, `_with_plank_helper`, `plank_present`; выкладка
   из ссылки по sha ревизии (готово).
3. `scripts/guard.py` — резерв имени, новый рецепт;
   `orchestrator/advance_gates/tests_writing.py` — отказ по имени в ссылке
   и подсказка по записи журнала, новая подсказка гейта источника
   артефактов (готово).
4. `tests/test_plank_helper.py` — 12 тестов с заявками мутаций; правка
   тестов прежнего рецепта и фикстуры `test_branch_freshness_gate.py`
   (готово, см. «Эскалация», вопрос 2).
5. `docs/codebase-map.md` — регенерирован `scripts/codebase_map.py`
   (готово).
6. Приложение к `skills/test-authoring.md` — раздел ниже (готово,
   `git apply --check` на чистом дереве прошёл).
7. По ANSWER-1: `orchestrator/pull.py:540` и
   `orchestrator/advance_gates/acceptance.py:228` — `is_dir()` каталога
   планки заменён на `acceptance.plank_present(...)`; в
   `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py` (`setUp`,
   `observed_run`) снимок каталога выкладки исключает
   `acceptance.PLANK_HELPER_NAME`, утверждения методов не тронуты; карта
   регенерирована (готово).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 2 (+7: потребители, проверяющие «планка есть») |
| 4 | 3 (автокоммит отбрасывает `_pult.py`), 2 (`drop_from_code_copy`) |
| 5 | 3 |
| 6 | 3 |
| 7 | 6 |
| 8 | 5 |
| 9 | 4 |

## Влияние на систему
- Каталог планки после выкладки теперь существует и при пустой планке
  (в нём только `_pult.py`). Внутри `acceptance.py` это закрыто
  `plank_present`. Но два потребителя вне зоны проверяют «планка есть»
  сами через `is_dir()`: `orchestrator/pull.py:540`
  (`_materialize_and_run_plank`) и
  `orchestrator/advance_gates/acceptance.py:228` (`_missing_plank_refuses`).
  Без их правки отказ «планка не найдена в источнике» на этих двух путях
  молча пропадает — это ослабление гейта. Его ловят существующие тесты
  (`tests/test_pull.py::PullEvaluateTest::test_refused_when_plank_missing_and_ac_required`,
  `::test_refused_none_when_branch_text_read_already_refused`,
  `tests/test_branch_freshness_gate.py::BranchFreshnessGateTest::test_approve_refuses_when_spec_read_fails_after_missing_plank`
  — до правки красные). По ANSWER-1 (вариант A) оба `is_dir()` заменены
  на `acceptance.plank_present(...)` — см. «Расширение зон»; отказ
  сохранён, три теста зелёные.
- Автокоммит: `_pult.py` в `acceptance_tests/` теперь посторонний —
  копия, оставшаяся в рабочей копии после прерванного `plank-run`,
  отбрасывается с записью журнала, а не уезжает в ссылку (AC-7). Если такая
  запись окажется последней в визите `tests_writing`, выход получит отказ
  с подсказкой про занятое имя, хотя файл положил пульт. На практике после
  такой записи у шага test_author всегда есть более поздние записи, и гейт
  её не читает. Риск записан ниже.
- Выкладка делает 4–5 лишних чтений git (`rev-parse`, `merge-base`).
  Тесты с подменой `gitcmd.in_repo`, считающие каждый вызов, это
  замечают: `test_branch_freshness_gate.py` — фикстура
  `_fixation_response` теперь отвечает на эти чтения сама, утверждения
  не тронуты.
- Гейты, лимиты и инварианты не ослаблены. Правило отказа «чтение с
  диска» не тронуто; заменён только текст рецепта.
- Откат: revert merge-коммита задачи; приложение к скилу Оператор
  откатывает отдельно.

## Приложение: правка skills/test-authoring.md
Проверено: `git apply --check` на чистом дереве (HEAD ветки задачи) —
применяется.

```diff
diff --git a/skills/test-authoring.md b/skills/test-authoring.md
index 1216820d..d4337fc7 100644
--- a/skills/test-authoring.md
+++ b/skills/test-authoring.md
@@ -125,10 +125,41 @@ guard разбирает её текстом, без импорта файлов
 тем же локом, что планку, и гоняет в одном прогоне с ней; метод
 `test_ac<n>_…` долгоживущего файла своей задачи покрывает критерий.
 
+## Помощник пульта `_pult.py` — единственный рекомендуемый способ
+При каждой выкладке планки (прогон гейта, сухой сбор, подтяжка main,
+`plank-run`) пульт кладёт рядом с тестами `acceptance_tests/_pult.py` —
+помощник планки (исходный текст — `orchestrator/plank_helper.py`). Он
+импортирует только стандартную библиотеку и работает в рабочей копии без
+`.artel/` и со сломанным пакетом `orchestrator`. Импорт — как соседнего
+модуля: `sys.path.insert(0, str(Path(__file__).resolve().parent))`, затем
+`from _pult import artifact_text, changed_paths`.
+- `artifact_text(name)` — текст `tasks/<id>/<name>` из ссылки документов
+  той ревизии, с которой выложена планка; файла нет — `None`, сбой git —
+  исключение `ArtifactReadError`;
+- `branch_diff()` — закоммиченный дифф задачи от базы до HEAD рабочей
+  копии;
+- `changed_paths()` — пути задачи правилом гейта зон: закоммиченный дифф
+  от базы плюс неотслеживаемые файлы вне `tasks/<id>/`; незакоммиченные
+  правки отслеживаемых файлов не входят;
+- `apply_check(diff, reverse=False)` — применимость unified-диффа к дереву
+  HEAD: `""` — git согласен, иначе его ответ; `reverse=True` — правка уже
+  в дереве; рабочая копия и её индекс не меняются;
+- константы `TASK_ID`, `CODE_ROOT` (корень рабочей копии), `DIFF_BASE` и
+  `DIFF_BASE_SOURCE` (база диффа и её источник — пульт считает их при
+  выкладке тем же `gitcmd.diff_base`, что гейт зон).
+
+Помощник — единственный рекомендуемый способ читать артефакты задачи,
+считать её дифф и проверять приложения PLAN: свой `gitcmd.show`,
+`git merge-base` или самописный `_plank.py` для этого не пиши. Имя
+`_pult.py` занято: свой файл с этим именем в `acceptance_tests/` выход из
+`tests_writing` отклоняет подсказкой «имя занято помощником пульта».
+Долгоживущим файлам `tests/` помощник не нужен: факты задачи (артефакты,
+дифф) — предмет разовой группы.
+
 ## Источник артефактов задачи — только артефактная ветка
-Источник артефактов задачи в планке: только артефактная ветка через
-`gitcmd.show(artifact_branch.branch_name(TASK_ID), "tasks/<id>/PLAN.md")`;
-диск рабочей копии — не источник, пульт материализует только
+Источник артефактов задачи в планке: только ссылка документов задачи через
+помощник пульта — `artifact_text("PLAN.md")` из `_pult.py` (раздел
+выше); диск рабочей копии — не источник, пульт материализует только
 `acceptance_tests/`. В каталоге документов задачи
 (`.artel/projects/<проект>/tasks/<id>/`, ADR-0021 этап 1) `tasks/<id>/`
 лежит целиком, в рабочей копии кода его нет, а в среде прогона гейта
@@ -142,9 +173,10 @@ materialize_from_branch`) — один `acceptance_tests/`: тест, читаю
 AC-8, 13.09 01M2CN465W test_ac4 — оба чинились руками через
 `amend-tests`). Выход из `tests_writing` отказывает такой планке текстом
 «переход отклонён: планка читает артефакты с диска» с файлом, строкой и
-рецептом; чтение через `gitcmd.show`/`artifact_branch` или `subprocess`
-с `git show`/`git cat-file` — законно, имя артефакта в докстринге или
-комментарии — тоже. Пути фикстур вложенной песочницы от временного
+рецептом — `artifact_text(…)` помощника; чтение через `gitcmd.show`/
+`artifact_branch` или `subprocess` с `git show`/`git cat-file` гейт не
+отклоняет, но рекомендуемый путь — помощник, имя артефакта в докстринге
+или комментарии — тоже законно. Пути фикстур вложенной песочницы от временного
 каталога под правило не подпадают (`self.tdir` `LightTransitionSandbox`,
 `tempfile`); путь, записанный через `config.TASKS`/`config.ROOT`, —
 якорный, даже если песочница подменяет их временным каталогом: бери
@@ -275,8 +307,10 @@ ls_tree_files` на дисковые реализации, помощники `w
 на все смерженные с тех пор задачи, поэтому дифф от неё несёт чужие
 файлы. Локальная ветка — база только когда ref `origin` недоступен
 (`origin` не заведён, fetch не прошёл). Пульт уже считает так одной
-точкой правды — `gitcmd.diff_base`/`gitcmd.diff_base_source`: бери её, а
-не собственный `git merge-base`. Планка 01M3H3JW9XE1THF0HK8RESZ0CV
+точкой правды — `gitcmd.diff_base`/`gitcmd.diff_base_source` — и
+подставляет её в помощник пульта: дифф задачи бери `branch_diff()`, список
+путей — `changed_paths()` из `_pult.py` (раздел о помощнике), а не
+собственный `git merge-base`. Планка 01M3H3JW9XE1THF0HK8RESZ0CV
 считала от локальной ветки и эскалировала исправную задачу на мерже;
 соседняя 01M3H3JRBD544GQ10SS3DBGEVP считала от `origin` и не пострадала.
 
```

## Риски
- Ложная подсказка «имя занято» при копии помощника, оставленной
  прерванным `plank-run` в рабочей копии test_author: срабатывает, только
  если запись «посторонние файлы» стала последней в визите. Исправить
  точно можно только в `checkpoint.py` (вне зоны): там копию из рабочей
  копии кода можно молча отбрасывать, а журналировать только черновик.
- `apply_check` на `--cached` проверяет индекс HEAD без рабочего дерева:
  дифф с бинарными файлами без полного индекса git отклонит. Так же
  отклоняет и `git_apply` пульта.

## Предложения системе
- `orchestrator/pull.py`, `orchestrator/advance_gates/acceptance.py`: у
  вопроса «планка есть?» после выкладки нет одной точки правды, каждый
  потребитель спрашивает `is_dir()`. Любое добавление файлов в выкладку
  (как здесь) молча ослабляет отказ «планка не найдена». Нужен один
  предикат (`acceptance.plank_present`) у всех потребителей.
- Тесты с подменой `gitcmd.in_repo`, считающие ВСЕ вызовы как предмет
  (`test_branch_freshness_gate.py::_recording_ok`), краснеют от любого
  нового чтения git в общем узле. Класс «фикстура считает чужие вызовы»
  стоит закрыть явным белым списком предмета, а не чёрным списком
  непредмета.

## Расширение зон
Пути: orchestrator/pull.py, orchestrator/advance_gates/acceptance.py

Обоснование: выкладка кладёт `_pult.py` и к пустой планке (требование 3,
песочницы планки AC-1/3/4/5/6), поэтому `is_dir()` каталога планки у этих
двух потребителей перестал отвечать на вопрос «планка есть». Ровно две
строки — `orchestrator/pull.py:540` и
`orchestrator/advance_gates/acceptance.py:228` — заменены на
`acceptance.plank_present(...)`; отказ «планка не найдена в источнике»
сохранён (`tests/test_pull.py`, `tests/test_branch_freshness_gate.py`
зелёные). Мандат — ANSWER-1, вопрос 1, вариант A.

## Изменённые утверждения тестов (мандат ANSWER-1, вопрос 2)
Методы не удалялись и не переименовывались.
- 2.1–2.3 `tests/test_guard_artifact_disk_read.py`
  (`DiskReadFormsTest::test_error_text_carries_the_artifact_branch_recipe`,
  `::test_every_artifact_name_is_covered`,
  `AnchoringTest::test_recipe_names_the_artifact_not_the_literal_fragment`)
  — ожидаемый текст рецепта `gitcmd.show(..., "tasks/<id>/X")` →
  `artifact_text("X")` (требование 6).
- 2.4–2.5 `tests/test_fsm_advance_tests_writing_artifact_source.py`
  (`ArtifactSourceGateTest::test_disk_reading_plank_is_refused_with_named_action`,
  `RefusalClassTest::test_refusal_surfaces_in_test_author_brief_history`)
  — рецепт и подсказка называют помощник пульта (требование 6).
- 2.6 `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`
  (`DraftInTestsWritingTest::test_ac1_tests_writing_runs_draft_with_pult_runner`,
  `FixedPlankAfterTestsWritingTest::test_ac2_later_states_run_fixed_plank_and_single_file`)
  — в `setUp` (`observed_run`) снимок каталога выкладки исключает
  `acceptance.PLANK_HELPER_NAME`; утверждения методов прежние.

## Проверка
- `plank-run 01M44EP4Q927DJXVX9YMMZ0B7V`: 35 passed, код выхода 0.
- `python3 -m pytest tests/test_pull.py tests/test_branch_freshness_gate.py
  tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py tests/test_plank_helper.py
  tests/test_approve_acceptance_full_suite.py tests/test_acceptance_tests_flow.py
  tests/test_pull_long_lived_plank.py tests/test_guard_artifact_disk_read.py
  tests/test_fsm_advance_tests_writing_artifact_source.py`: 166 passed.
- Карта регенерирована `scripts/codebase_map.py`.
