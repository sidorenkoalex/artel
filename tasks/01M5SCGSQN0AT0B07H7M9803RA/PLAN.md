---
task: 01M5SCGSQN0AT0B07H7M9803RA
type: plan
author_role: developer
status: ready
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
8. По ANSWER-2 (вариант (а)): `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py::ProjectAreaSandbox.setUp`
   — одна строка `(self.root / ".artel" / "targets.yaml").unlink(missing_ok=True)` сразу после
   `self.addCleanup(targets_patcher.stop)`: убирает запись артели, посеянную `RealGitSandbox` по
   адресу локального слоя. Утверждения, методы и их число не менялись.

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
| 14 | 6, 8 (правка песочницы по мандату ANSWER-2) |

Прогоны: все четыре долгоживущих файла задачи и
`tests/test_acceptance_suite_profile.py` — 67 passed. Тесты затронутых
модулей (targets/doctor/main_copy/test_lint/projects/role_refusal/
core_reference/project_profile/repo_context/invariants и т. п.) — 440
passed, 1 failed; файлы, перенаправляющие `config.TARGETS`, — 187 passed,
29 failed (одна причина — посеянный `RealGitSandbox` файл по адресу
локального слоя). После шага 8: `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`,
`tests/test_invariants.py::MainCopyGitUnchangedDuringTaskTest`,
`tests/test_acceptance_suite_profile.py` и четыре долгоживущих файла задачи —
98 passed; `tests/test_invariants.py` целиком — 84 passed (прежний 1 failed
затронутых модулей — `MainCopyGitUnchangedDuringTaskTest`, та же причина).

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
  (закрыто шагом 8 по ANSWER-2).

## Предложения системе
- `tests/sandbox.py::RealGitSandbox` кладёт `config.TARGETS` песочницы в
  `root/.artel/targets.yaml` — адрес, совпадающий с локальным слоем любой
  песочницы, чей `TARGETS` лежит в `root/`; ни ТЗ, ни SPEC, ни записка
  test_author этого пересечения не увидели (записка проверила только
  `RealGitSandbox` без перенаправления). Класс: «новый файл по пути,
  производному от подменяемого атрибута, — сверить с раскладками
  существующих песочниц до SPEC».
