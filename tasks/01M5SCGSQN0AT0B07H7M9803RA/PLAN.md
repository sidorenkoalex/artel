---
task: 01M5SCGSQN0AT0B07H7M9803RA
type: plan
author_role: developer
status: escalate
schema_version: 5
---

# PLAN: Записи внешних проектов — в локальный слой вне репозитория артели

## Подход
Локальный слой `.artel/targets.yaml` читается тем же разбором `yamlmini`,
что и слой репозитория (`targets._read_section` — один набор текстов отказа
на оба файла), каждая запись в трёх разделах сводится в запись прежнего
плоского вида (`targets.merge_local`) и проверяется прежним `check()` с
источником — путём слоя. Читатели записи (`load`/`target`/`core_reference`
и их вызывающие) не меняются: структура выдачи прежняя. Проверки, которые
должны назвать раздел (место поля, `PATH` в `description.env`, `<cache>`,
абсолютные пути, `machine.path` без своего раннера), идут ДО сведения —
иначе отказ дала бы прежняя проверка с текстом про `env`/`workdir`.

Команда `targets-migrate` (`projects.cmd_targets_migrate`) раскладывает
плоскую запись обратно, пишет текст своей записью подмножества
`yamlmini` (кавычки только у скаляров; значение, которое не записать, —
отказ с именем поля, ANSWER-1 п. 2), затем разбирает собранный текст,
сводит загрузчиком и сверяет поле в поле (тип значения и порядок
компонентов — тоже) — только после этого атомарно пишет файл.

Бюджет не переоценивается.

## Шаги
1. `config.TARGETS_LOCAL_REL`; `targets.local_path()`, `layers()`,
   `merge_local()`, `cache_dir()`; `load()`/`target()`/`core_reference()`
   со слиянием слоёв; `check(name, entry, source=None)`.
2. `projects.cmd_targets_migrate` + строка диспетчера и текста использования
   `artel.py` (вне `_ROLE_ALLOWED_COMMANDS`).
3. `doctor/cli.targets_local_layer_check` — строка `targets-local-layer`
   только в ветке годного `load()`.
4. `checkpoint.MainCopyWatch.local_layer_digest` (последнее поле, `None` по
   умолчанию), снятие суммы в `main_copy_watch_start`, сверка в
   `watch_main_copy` (и при `git status`, не ответившем, ANSWER-1 п. 4).
5. `test_lint.LIVE_FILES`/`LIVE_FILE_CONFIG_ATTRS`.
6. Правка `tests/test_acceptance_suite_profile.py::AcceptanceSuiteProfileTest.call`
   по требованию 14 (импорт `sandbox`, первый контекст
   `sandbox.declared_without_profile("sled")`).
7. Регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1 |
| 7 | 1 |
| 8 | 3 |
| 9 | 4 |
| 10 | 2 |
| 11 | 5 |
| 12 | 1 (код канарейки не тронут; слой следует за `config.TARGETS`) |
| 13 | 7 |
| 14 | 6 |

Прогоны: все четыре долгоживущих файла задачи и
`tests/test_acceptance_suite_profile.py` — 67 passed. Тесты затронутых
модулей (targets/doctor/main_copy/test_lint/projects/role_refusal/
core_reference/project_profile/repo_context/invariants и т. п.) — 440
passed, 1 failed; файлы, перенаправляющие `config.TARGETS`, — 187 passed,
29 failed: все 29 — одна причина, см. «Эскалация».

## Влияние на систему
- Без файла `.artel/targets.yaml` выдача `load()`/`target()`/
  `core_reference()` и тексты отказов слоя репозитория прежние байт в байт
  (AC-2, AC-5); меняется только хвост текста неизвестного имени
  (требование 6).
- `MainCopyWatch` прежней формы строится как раньше; при неизменной сумме
  надзор прежний байт в байт, лишних процессов нет (AC-14).
- Канарейка и `tests/sandbox.py` не тронуты: путь слоя вычисляется от
  `config.TARGETS`.
- Гейты, инварианты, лимиты не ослабляются; линт живых файлов только
  расширен. Откат — revert merge-коммита; файл слоя вне git, без него
  поведение прежнее.

## Риски
- Песочницы тестов, кладущие что-либо по адресу
  `config.TARGETS.parent/.artel/targets.yaml`, теперь читают это как
  локальный слой — ровно это и случилось с `ProjectAreaSandbox`
  (см. «Эскалация»).

## Предложения системе
- `tests/sandbox.py::RealGitSandbox` кладёт `config.TARGETS` песочницы в
  `root/.artel/targets.yaml` — адрес, совпадающий с локальным слоем любой
  песочницы, чей `TARGETS` лежит в `root/`; ни ТЗ, ни SPEC, ни записка
  test_author этого пересечения не увидели (записка проверила только
  `RealGitSandbox` без перенаправления). Класс: «новый файл по пути,
  производному от подменяемого атрибута, — сверить с раскладками
  существующих песочниц до SPEC».

## Эскалация

Код причины: покраснел существующий тест вне мандата (SPEC, требование 14:
«Покраснел любой другой существующий тест — эскалация с его именем и
причиной, а не правка»).

**Вопросы**

1. (блокирует) Разрешить правку песочницы
   `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py::ProjectAreaSandbox.setUp`
   одной строкой — убрать посеянный `RealGitSandbox` файл сразу после
   перенаправления `config.TARGETS` на `root/targets.yaml`:

   ```diff
   @@ -172,6 +172,7 @@ class ProjectAreaSandbox(RealGitSandbox):
                                                self.root / "targets.yaml")
            targets_patcher.start()
            self.addCleanup(targets_patcher.stop)
   +        (self.root / ".artel" / "targets.yaml").unlink(missing_ok=True)
   ```

   Утверждения, методы и их число не меняются — только изоляция помощника,
   как у правки требования 14. Проверено временным применением и откатом:
   `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py` и
   `tests/test_invariants.py::MainCopyGitUnchangedDuringTaskTest` — 31
   passed.
   Варианты: (а) эта строка в `ProjectAreaSandbox.setUp` — дефолт;
   (б) правка `tests/sandbox.py::RealGitSandbox` (другое имя файла
   `TARGETS` песочницы под `.artel/`) — шире, задевает все песочницы
   на настоящем git, SPEC её исключает («Не входит»);
   (в) иное решение Оператора.
   Если гейт неослабления потребует машинной строки — «Ослабление тестов
   разрешено: tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py» в
   ANSWER-2.

**Контекст**

Красные тесты (29, одна причина):
- `tests/test_invariants.py::MainCopyGitUnchangedDuringTaskTest::test_main_copy_git_is_unchanged_from_new_to_done`
- `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py` — 28 методов
  классов `ArtelTaskInProjectAreaTest`, `ExternalTaskInProjectAreaTest`,
  `CloneCreationTest`, `RepoContextOfArtelTest`, `CodeCopyOfTaskTest`,
  `CloneHooksFromPinTest`, `OperatorCommandsThroughCloneTest`,
  `HeldRecordBaseFromCloneTest`, `EndToEndMainCopyUntouchedTest`,
  `MergeGateStepsOnCloneTest`, `HistoricalDocsRefsTest` (все на
  `ProjectAreaSandbox`/`TaskFlowSandbox`).

Причина: `RealGitSandbox.setUp` (`tests/sandbox.py:1925-1931`) подменяет
`config.TARGETS` на `root/.artel/targets.yaml` и сеет туда запись артели
плоского вида; `ProjectAreaSandbox.setUp`
(`tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py:171-174`)
перенаправляет `config.TARGETS` на `root/targets.yaml` — и посеянный файл
остаётся ровно по адресу локального слоя (`targets.local_path()` =
`root/.artel/targets.yaml`). Загрузчик по требованию 2 отказывает:
«запись артели — только в targets.yaml репозитория». Подстроить код под
этот файл нельзя без нарушения требования 2 (запись `artel` и плоская
запись в локальном слое — обязательные отказы, AC-5).

Код всех требований 1–14 реализован и лежит в worktree; долгоживущие
тесты задачи зелёные; карта регенерирована.

**Блокирует**

Зелёный полный набор `tests/` (рубеж `in_dev -> verifying`, CI ветки):
без правки песочницы 29 существующих тестов красные.
