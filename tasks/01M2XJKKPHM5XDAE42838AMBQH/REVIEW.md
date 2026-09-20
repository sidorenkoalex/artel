---
task: 01M2XJKKPHM5XDAE42838AMBQH
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Guard планки: артефакты задачи читаются только из артефактной ветки, отказ на выходе tests_writing

Итерация 2 — после ANSWER-1 Оператора (вариант B: ошибка только по
пути, якоренному на рабочую копию). Инкрементальный diff пакета пуст:
sha «предыдущего вердикта» 224c463e — это HEAD ветки (подтяжка main),
а не коммит вердикта; фактический diff итерации 2 — коммит 6d302114
(`scripts/guard.py` +132/−26, два файла `tests/`, карта), сверен
`git show 6d302114`; полный объём задачи — коммиты dd0ac309 + 6d302114
(`git show --stat`), других файлов задача не трогает. SPEC/PLAN в пакете
не показаны (артефакты живут в артефактной ветке) — прочитаны с диска
рабочего каталога (материализация головы артефактной ветки, коммит
c4d0f452).

## Фаза A: гейт плана

1. Таблица покрытия полна: требования 1–7 и три пункта ANSWER-1
   разложены по шагам 1–6; каждый AC-1..AC-10 адресован планкой либо
   `tests/`.
2. Шаги — единицы размера MR (функция guard, предикат гейта, два файла
   тестов, карта, приложение-диф, правка планки по ANSWER-1), без
   микроопераций и без «сделать всё».
3. Подход не конфликтует с конвенциями: AST-разбор обоснован AC-4;
   вложение предиката в `_tests_writing_dry_collect_gate` обосновано
   зонами SPEC (`orchestrator/fsm_advance.py` вне зон) и соответствует
   «рядом с сухим сбором». Правка залоченной планки идёт по ANSWER-1 п. 2
   (ADR-0012), легализована Оператором — журнал задачи, событие
   «правка планки» 20.09 06:30: старый sha 6e58b0b6, новый c4d0f452,
   основание ANSWER; `tests_locked_sha` задачи = c4d0f452 (прочитано из
   `.artel/state.db` пульта в режиме только чтения).
4. Дефект плана итерации 1 (R1-F3) закрыт: «Влияние на систему»
   (PLAN.md:204–239) переписано по прогону над всеми `tasks/*` с числом
   и классификацией; секция соответствует фактическому diff — затронуты
   ровно `scripts/guard.py`, `orchestrator/advance_gates/tests_writing.py`,
   два новых файла `tests/`, `docs/codebase-map.md`; `orchestrator/
   fsm_advance.py`, `pull.py`, `acceptance.py`, `amend.py` не тронуты
   (`git show --stat dd0ac309 6d302114`).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (функция guard над `*.py` планки; набор выражений доступа; в редакции ANSWER-1 — только якорные пути) | OK | `scripts/guard.py:1070` `artifact_disk_read_errors_from_files`, `:1124` `scan_artifact_disk_reads`; якорение — `_is_anchored:982`, `_anchored_names:1024`. Все 15 якорных форм `DiskReadFormsTest` ловятся, 8 форм от временного каталога `AnchoringTest` — нет; сверх тестов проверены руками: `os.path.dirname(__file__)`, `with open(Path(__file__)…/"SPEC.md")`, walrus, `/=`, `Path(config.TASKS, TASK, "PLAN.md")`, `.read_bytes()` на `joinpath` — все ловятся; `self.task_dir` (атрибут) — не ловится, как заявлено в PLAN «Пропуски правила». Эталон инцидента 01M2B6K3EM ловится (ANSWER-1 п. 3): юнит `test_incident_sample_01m2b6k3em_stays_reported` и прогон по `tasks/` (`…test_ac8_…:26` в списке) |
| 2 (`gitcmd.show`/`artifact_branch`/`subprocess git show|cat-file`, докстринг/комментарий — не ошибка) | OK | Ни один из этих вызовов не в `_FS_ACCESS_CALLS`/`_FS_ACCESS_METHODS`; докстринги/комментарии вне AST-выражений. `AllowedSourcesTest` + планка AC-2/AC-3/AC-4 зелёные |
| 3 (текст ошибки: файл, строка, рецепт) | OK | `<label>:<строка>: чтение артефакта задачи <имя> с диска — читай из артефактной ветки: gitcmd.show(artifact_branch.branch_name(TASK_ID), "tasks/<id>/<имя>")`; R1-F2 закрыт — `_artifact_name_in_literal:954` подставляет basename только при `startswith(name)` (проверено: `f"{TASK}-PLAN.md"` → `PLAN.md`, `ANSWER-1.md` → как есть) |
| 4 (не в `check()`/`main()`) | OK | Diff `check()`/`main()` не трогает; `NotWiredIntoCheckOrMainTest` со спаем и планка AC-8 зелёные; `python3 scripts/guard.py --all` из планки AC-8 — rc 0 при 21 исторической планке с чтением с диска |
| 5 (гейт выхода `tests_writing`, именованный отказ того же класса) | OK | `orchestrator/advance_gates/tests_writing.py:158–184`, вызов первым в `_tests_writing_dry_collect_gate:203` (файл в итерации 2 не менялся, сверен повторно после подтяжки main): стоп-кран и история брифа идут по префиксу `auto.py:33 REFUSAL_ACTION_PREFIX = "переход отклонён"`, `brief.py:66–69 _ROLE_NOT_FINISHED_REFUSAL_ACTIONS` нового действия не содержит, действие нигде вне модуля гейта не упоминается (grep по `orchestrator/`) |
| 6 (диф к `skills/test-authoring.md` приложением; фраза ANSWER-1 о фикстурах) | OK | Приложение в PLAN.md дополнено якорной формулировкой и фразой «пути фикстур вложенной песочницы от временного каталога под правило не подпадают»; `git apply --check` дифа, извлечённого из PLAN.md, — rc 0 на чистом дереве ветки; защищённые пути в ветке не тронуты |
| 7 (тесты в `tests/`; соседние наборы зелёные) | OK | Diff `tests/` в обоих коммитах — только два новых файла задачи; удалённые строки коммита 6d302114 (`git show 6d302114 -- tests/ | grep '^-'`) — ключи словаря форм и докстринг внутри этих же новых файлов, ни одного `assert` существующих тестов не тронуто. 204 теста затронутых модулей зелёные |
| ANSWER-1 п. 1 (вариант B, R1-F2, R1-F3) | OK | См. R1-F1..R1-F3 в реестре |
| ANSWER-1 п. 2 (правка залоченной планки, перечень в PLAN) | OK | `git diff 6e58b0b6 c4d0f452 -- …/acceptance_tests` — один файл `test_ac1_disk_read_named_forms.py`, +64/−0 (класс `TempDirFixturePathsPassTest`, словарь `TEMP_DIR_BODIES`, абзац докстринга); PLAN «Правка планки» описывает ровно это, «изменённых подтестов — ноль» — верно, все прежние образцы якорны. Чувствительность не ослаблена: контроль `control_refuses()` перед положительными сценариями сохранён |
| ANSWER-1 п. 3 (эталон 01M2B6K3EM) | OK | `AnchoringTest.test_incident_sample_01m2b6k3em_stays_reported` — ровно одна ошибка на строке `PLAN_DISK` рядом с законным `gitcmd.show` |

Оговорка по букве ANSWER-1, не дефект: литерал с началом `tasks/` —
якорь в любой позиции, поэтому `Path(tmp) / "tasks/X/PLAN.md"` (один
литерал на весь хвост) ловится, а `Path(tmp) / "tasks" / X / "PLAN.md"`
— нет; в 192 планках дерева первой формы нет.

## Замечания

- minor — `scripts/guard.py:1006` (`_is_anchored`, ветка `Attribute`) —
  `dotted.endswith(_ANCHOR_ATTR_SUFFIXES)` сравнивает строковый суффикс,
  не сегменты точечного имени: `sandbox_config.ROOT / "PLAN.md"` даёт
  ошибку (проверено прогоном: 1 ошибка), хотя `sandbox_config` — не
  `config` пульта. Последствие: планка, чей модуль-помощник назван
  `*config` и несёт `.ROOT`/`.TASKS` на временный каталог, получит отказ с
  рецептом «читай из артефактной ветки», который для её фикстуры не по
  делу. В 192 планках дерева такого имени нет — живого эффекта нет.
  Предложение: сравнивать по сегментам (`dotted.split(".")[-2:] ==
  ["config", "ROOT"]`), при случае.
- minor — `tasks/01M2XJKKPHM5XDAE42838AMBQH/PLAN.md:240` («Пропуски
  правила») — названа одна ложноотрицательная форма (атрибут
  `self.task_dir`), но их больше, все того же класса «литерал вне самого
  выражения доступа»: `for name in ("PLAN.md", "SPEC.md"): (TASK_DIR /
  name).read_text()`, распаковка `a, b = Path(__file__)…, 1`, именованный
  аргумент `open(file=str(TASK_DIR) + "/PLAN.md")`, значение параметра по
  умолчанию `def f(d=TASK_DIR)` — все четыре проверены прогоном, 0 ошибок.
  По букве требования 1 («литерал, участвующий в выражении доступа») это
  вне правила, код SPEC соответствует; последствие — инцидентный класс
  через цикл по именам гейт не остановит, поймает красная планка на
  первом прогоне пультом, как до задачи. Предложение: при следующей
  правке PLAN/скила назвать цикл по именам рядом с атрибутом; правки
  кода в рамках задачи не требует.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | scripts/guard.py:1070; SPEC требование 1, AC-1, AC-5 | правило по любому выражению доступа ловило записи/чтения фикстур вложенной песочницы: 68/186 планок, включая планку самой задачи | гейт отказывал бы штатному стилю планок FSM-задач | Проверено ревьювером: правило переписано по варианту B (`_is_anchored`/`_anchored_names`); прогон `scan_artifact_disk_reads` над всеми `tasks/*` — 192 планки, 21 с ошибками, 35 строк, планка задачи чиста, все 21 — либо инцидентный класс (`__file__`/`REPO_ROOT / "tasks"`: 01M2B6K3EM, 01M2DC6SQV, T046, T047, T093, T094, 01M1SG9W), либо `config.TASKS` в тексте песочницы (14 планок) — как классифицировано в PLAN; 8 форм от временного каталога не ловятся (`AnchoringTest`, тест гейта `test_temp_dir_fixture_plank_passes_to_in_dev`, планка `TempDirFixturePathsPassTest`); правка планки легализована Оператором (журнал «правка планки», `tests_locked_sha` = c4d0f452). Суть исправлена — accepted |
| R1-F2 | accepted | scripts/guard.py:954 `_artifact_name_in_literal` | для части f-строки `-PLAN.md` в рецепт уходил `tasks/<id>/-PLAN.md` | рецепт называл несуществующий файл | Проверено: basename подставляется только при `basename.startswith(name)`, иначе само имя; `TASK_DIR / f"{TASK}-PLAN.md"` → `tasks/<id>/PLAN.md`, `ANSWER-1.md`/`ANSWER-3.md` — как есть (юнит `test_recipe_names_the_artifact_not_the_literal_fragment` + ручной прогон). accepted |
| R1-F3 | accepted | tasks/01M2XJKKPHM5XDAE42838AMBQH/PLAN.md:204–239 | «Влияние на систему» не называло реальный класс ложных срабатываний и не было измерено по `tasks/` | Оператор видел заниженную оценку риска | Проверено: пункт переписан по прогону — 190 планок / 21 / 35 строк с классификацией по трём классам и явной оговоркой про `config.TASKS`; мой прогон на HEAD после подтяжки main — 192 / 21 / 35 (две новые планки чисты), классификация совпадает построчно. accepted |
| R2-F1 | accepted | scripts/guard.py:1006 | `endswith(("config.ROOT", "config.TASKS"))` — строковый суффикс, `sandbox_config.ROOT` якорен | ложный отказ планке с модулем `*config`, имеющим `.ROOT`/`.TASKS`; в дереве таких нет | minor, наблюдение на будущее (сравнение по сегментам); правки в рамках задачи не требует — SPEC/ANSWER-1 исполнены. Закрыто ревьювером на месте; `accepted`, чтобы гейт `review -> verifying` не отклонил `approved` |
| R2-F2 | accepted | tasks/01M2XJKKPHM5XDAE42838AMBQH/PLAN.md:240 | список ложноотрицательных форм неполон: цикл по именам, распаковка, именованный аргумент `open(file=…)`, параметр по умолчанию | чтение артефакта через переменную-имя гейт не остановит; ловит красная планка на прогоне пультом, как до задачи | minor, только артефакт: по букве требования 1 код верен. Закрыто ревьювером на месте как наблюдение для следующей правки PLAN/скила; `accepted` по той же причине |

## Вердикт

approved — вариант B ANSWER-1 реализован: ошибка только по якорному
пути, инцидентный эталон ловится, песочницы от временного каталога не
ловятся, планка задачи чиста и её правка легализована Оператором;
R1-F1..R1-F3 закрыты по существу, два новых minor — наблюдения без
последствий для живых планок, правок не требуют.

## Проверено исполнением

Рабочий каталог `.artel/worktrees/01M2XJKKPHM5XDAE42838AMBQH`, HEAD
`224c463e`; CI коммита зелёный (14 проверок, по пакету). Python 3.13.

- `python3 -m pytest -q tests/test_guard_artifact_disk_read.py
  tests/test_fsm_advance_tests_writing_artifact_source.py
  tests/test_fsm_advance_tests_writing_dry_collect.py
  tests/test_acceptance_collect.py tests/test_guard_*.py` — 204 passed,
  76 subtests passed, 1.9 с.
- `python3 -m pytest -q tasks/01M2XJKKPHM5XDAE42838AMBQH/acceptance_tests/`
  — 15 passed, 23 subtests passed (внутри — планка AC-8 с реальным
  `scripts/guard.py --all`, rc 0; AC-9 с `git apply --check` во
  временном worktree от merge-base). Пометок `# AC-n: manual|skip` нет
  (grep); AC-10 отмечен комментарием как ci-covered — честно, полный
  `tests/` гоняет CI.
- Прогон `guard.scan_artifact_disk_reads(tdir)` по каждому
  `tasks/*/acceptance_tests/` (python-скрипт из воркtree): 192 планки,
  21 с ошибками, 35 строк; список планок и строк совпадает с
  классификацией PLAN «Влияние на систему» (9 инцидентных строк в 7
  планках, 26 строк `config.TASKS` в 14 песочницах); планки этой задачи
  в списке нет.
- Ручные пробы `guard.artifact_disk_read_errors_from_files` (18 форм):
  ловятся — `os.path.dirname(__file__)` в `os.path.join`, `Path(__file__)
  .parent / ".." / "PLAN.md"`, `(TASK_DIR / "PLAN.md").exists()`, `with
  open(Path(__file__)…/"SPEC.md")`, `/=`-цепочка, `Path(config.TASKS,
  TASK, "PLAN.md")`, `.read_bytes()`, walrus, `Path("tasks/X/PLAN.md")
  .read_text()`; не ловятся — атрибут `self.task_dir` (заявлено в PLAN),
  цикл по именам, распаковка, `open(file=…)`, параметр по умолчанию
  (R2-F2), `.with_name`, `.glob`; ложно ловится `sandbox_config.ROOT`
  (R2-F1); `Path(tmp) / "tasks/X/PLAN.md"` ловится по букве ANSWER-1.
- `git apply --check` на дифе, извлечённом из блока ```diff PLAN.md, —
  rc 0; `git diff --name-only 56b8e043 HEAD -- skills/ templates/
  gates.yaml roles.yaml .github/` — пусто.
- `python3 scripts/codebase_map.py` и сравнение с картой ветки без
  строки `built_at_sha` — совпадает (карта свежая после подтяжки main);
  карта возвращена `git checkout`.
- `python3 scripts/guard.py tasks/01M2XJKKPHM5XDAE42838AMBQH/PLAN.md` —
  «GUARD: ок».
- `git show --stat dd0ac309 6d302114` — файлы задачи: `scripts/guard.py`,
  `orchestrator/advance_gates/tests_writing.py`, два новых `tests/*.py`,
  `docs/codebase-map.md`; `git show 6d302114 -- tests/ | grep '^-'` —
  удалённые строки только внутри новых файлов задачи.
- `git diff 6e58b0b6 c4d0f452 -- tasks/…/acceptance_tests` — один файл,
  +64/−0; `.artel/state.db` пульта (sqlite, `mode=ro`): `tests_locked_sha`
  = c4d0f452, событие «правка планки» (operator, 2026-09-20 06:30:59Z,
  старый sha 6e58b0b6 → новый c4d0f452, основание ANSWER…).
- `grep -n "_ROLE_NOT_FINISHED_REFUSAL_ACTIONS = " -A4 orchestrator/brief.py`,
  `grep -n "REFUSAL_ACTION_PREFIX = " orchestrator/auto.py`, `grep -rln
  "планка читает артефакты с диска" orchestrator/` — только модуль гейта
  (AC-7 по коду, после подтяжки main).
- Сверка заявок «Ловит мутацию»: 15 тестов планки — 15 заявок; 17 тестов
  `test_guard_artifact_disk_read.py` — 17; 6 тестов
  `test_fsm_advance_tests_writing_artifact_source.py` — 6; каждая описывает
  сценарий и наблюдаемое свойство.

## Предложения системе

- Пакет ревью строит инкрементальный diff от «sha предыдущего вердикта»,
  но берёт за него HEAD ветки (224c463e — подтяжка main), и diff
  итерации 2 пришёл пустым, а SPEC/PLAN — «не показаны» (они в
  артефактной ветке, не в кодовой). Класс уже отмечен скилом (T082,
  T087), повторился здесь третий раз; адрес — сборщик пакета
  (`orchestrator/brief.py`, поиск sha вердикта по `git log -- REVIEW.md`
  артефактной ветки, чтение SPEC/PLAN из артефактной ветки, не из
  кодовой).
- Гейт вердикта требует `accepted` по всем записям реестра, а
  review-checklist говорит «0 blocker/major → approved»: minor при
  approved приходится закрывать самому ревьюверу «на месте» (прецеденты
  01M2XJKV84, 01M2XMCC83, здесь R2-F1/R2-F2) — статус `accepted` теряет
  смысл «разработчик исправил». Стоит либо завести терминальный статус
  для наблюдений (`noted`), либо не считать minor блокирующими гейт
  (skills/review-checklist.md «Реестр замечаний» п. 4,
  `orchestrator/advance_gates/tests_writing.py:54–72`).
