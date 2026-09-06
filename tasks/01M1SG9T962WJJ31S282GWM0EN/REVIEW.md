---
task: 01M1SG9T962WJJ31S282GWM0EN
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 4
---

# REVIEW: гейты зон и ёмкости: база сравнения — точка расхождения с origin/main

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (одна точка правды `gitcmd.diff_base`/`diff_base_source`, без сети) | OK | `orchestrator/gitcmd.py:229-279`; `_origin_main_ref_exists` — только `rev-parse --verify --quiet` локального ref, `diff_base` — `merge-base`, ни одной сетевой подкоманды. `None` на сбое обоих шагов. AC-1 закрыт `test_ac1_diff_base.py` (4 теста, все зелёные). |
| 2 (гейт зон/ёмкости/полный diff пакета — новая база; инкремент не тронут) | OK | `_zones_gate_refuses` (fsm_advance.py:656), `_capacity_gate_refuses` (fsm_advance.py:476, 505) и `review_package` при `iteration==1` (review.py:246-258) берут `gitcmd.diff_base`; инкрементальная ветка (`base = prev_sha`) и вырожденный откат `iteration>1` без `prev_sha` (`base = config.MAIN_BRANCH`) не изменены — подтверждено `test_ac4_incremental_review_unchanged.py` (мок `diff_base` роняет `AssertionError` при вызове, тест зелёный). |
| 3 (fail-closed на `None`) | OK | Оба гейта проверяют `if base is None: ... return True` до какого-либо `git diff`/`diff_names` (fsm_advance.py:477, 657). AC-5 закрыт двумя тестами (`test_ac5_fail_closed_on_none_base.py`). |
| 4 (журнал называет sha и источник базы) | OK | Финальные сообщения отказа обоих гейтов зовут `gitcmd.diff_base_source` и вставляют его вместе с sha (fsm_advance.py:511-521, 706-711). AC-6 закрыт 4 тестами. |
| 5 (внешний target вне объёма) | OK | В обоих гейтах проверка `store.task_target(...) != config.DEFAULT_TARGET` стоит раньше вызова `gitcmd.diff_base` (fsm_advance.py:469, 649) — внешний target не доходит до новой базы вовсе. Подтверждено `CapacityGateExternalTargetTest`/`ZonesGateExternalTargetSkipsTest` (обе зелёные) без правки. |

## Замечания

- major — `tests/test_zones_gate.py:142-153` (`ZonesGateGitFailureTest.test_git_not_answering_diff_names_refuses`) — тест мокает `gitcmd.diff_names` на `None`, чтобы поймать мутацию «проверка `if files is None: ... return True` убрана» (докстринг теста). Но `_zones_gate_refuses` теперь ЗОВЁТ `gitcmd.diff_base(branch)` раньше `diff_names` (fsm_advance.py:656), а `TmpRootTest`-песочница этого файла не несёт настоящего git-репозитория — реальные `rev-parse`/`merge-base` внутри `diff_base` отвечают «not a git repository» и `diff_base` возвращает `None` ДО того, как выполнение вообще доходит до мокнутого `diff_names`. Проверено запуском теста изолированно: журнальное сообщение — «гейт зон: git не ответил на определение базы сравнения» (новая ветка `base is None`, fsm_advance.py:657-666), а не «...список файлов диффа» (старая ветка, которую тест должен ловить). Тест зелёный (обе фразы содержат подстроку «гейт зон», по которой бьёт `assertTrue(any(...))`), но фактически НЕ ловит заявленную мутацию — сними её проверку сегодня, и тест этого не заметит, потому что до неё уже не доходит. Тот же класс риска относится к любому будущему тесту `TmpRootTest`, бьющему по «git не ответил» именно на `diff_names`/`git diff` этих двух гейтов через мок отдельной `gitcmd`-функции, а не через `gitcmd.git` целиком (в `tests/test_capacity_gate.py` мокается `gitcmd.git` целиком, поэтому там `diff_base` съезжает на пустую базу, но реальный вызов `git diff` — намеренная точка сбоя теста — всё равно достигается и остаётся тем, что тест проверяет; в `test_zones_gate.py` иначе — мок стоит на уровне `gitcmd.diff_names`, до которого код теперь не доходит). Предложение: замокать также `gitcmd.diff_base` (например, `return_value="deadbeef"`) рядом с `gitcmd.diff_names=None` в этом тесте, чтобы выполнение реально достигало проверяемой строки.
- minor — `orchestrator/review.py:319` — подсказка ревьюверу в инкрементальном пакете («если для оценки замечания недостаточно — посмотри полный diff ветки отдельно») называет буквально `git diff {config.MAIN_BRANCH}...{branch}` — тот же устаревший локальный `main`, из-за которого эта задача заведена (бэклог 05.09: чужие уже влитые коммиты раздувают diff). Ревьювер, последовавший этой подсказке дословно, получит ровно тот диф с шумом, который вся задача устраняет для самого пакета. Предложение: заменить литерал на команду через актуальную базу (`gitcmd.diff_base`-эквивалент) либо явно пометить, что это заведомо более широкий diff, чем даёт актуальная база.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_zones_gate.py:142-153 | тест `test_git_not_answering_diff_names_refuses` не доходит до мокнутого `diff_names` — `diff_base` отказывает раньше в этой песочнице | тест даёт ложную уверенность: сломай `if files is None: return True`, тест не заметит | замокать `gitcmd.diff_base` рядом с `diff_names=None`, чтобы выполнение реально достигало проверяемой ветки |
| R1-F2 | open | orchestrator/review.py:319 | подсказка ревьюверу для инкрементального пакета называет `git diff {config.MAIN_BRANCH}...{branch}` — устаревшую локальную базу | ревьювер, использовавший подсказку, получит diff с шумом чужих коммитов — тот самый класс проблем, который чинит эта задача | заменить литерал на актуальную (origin-aware) базу либо явно пометить diff как заведомо более широкий |

## Вердикт

changes_requested — исправить R1-F1 (тест не ловит заявленную мутацию из-за нового порядка вызовов в `_zones_gate_refuses`) и R1-F2 (устаревшая подсказка в тексте пакета). Оба замечания локальны, без переделки подхода: сама реализация `diff_base`/`diff_base_source` и переключение трёх потребителей соответствуют SPEC и покрыты приёмочными тестами (AC-1..AC-8 зелёные, AC-9 обоснованно skip).

## Проверено исполнением

- `python3 -m unittest tests.test_zones_gate tests.test_capacity_gate tests.test_review_package -v` — 117 тестов, все зелёные (регрессия затронутых модулей не нарушена).
- `python3 -m unittest discover -s tasks/01M1SG9T962WJJ31S282GWM0EN/acceptance_tests -v` — 21 тест, все зелёные (AC-1..AC-8 исполняемые, AC-9 legit skip — ci-covered класс).
- `python3 -m unittest tests.test_zones_gate.ZonesGateGitFailureTest.test_git_not_answering_diff_names_refuses -v` — тест зелёный, но журнал отказа называет «git не ответил на определение базы сравнения» вместо ожидаемого «...список файлов диффа» — подтверждает R1-F1 (тест не бьёт по заявленной мутации).
- `python3 scripts/codebase_map.py` — регенерация чистая: diff после regen отличается только строкой `built_at_sha` (не признак дефекта), содержимое совпадает с закоммиченным; откатил регенерированный файл (`git checkout -- docs/codebase-map.md`), рабочее дерево не изменено.
- Сверка diff `tests/` (git diff --stat/полный diff из пакета) — новых ослаблений существующих ассертов не найдено, единственная правка (`tests/test_review_package.py::FakeGit`) только добавляет две новые ветки диспетчера под `rev-parse .../refs/remotes/origin/...` и `merge-base`, не трогая старые.

## Предложения системе

- `tests/test_zones_gate.py` и `tests/test_capacity_gate.py` не были достроены под новый вызов `gitcmd.diff_base` внутри проверяемых функций (в отличие от `tests/test_review_package.py::FakeGit`, который разработчик обновил осознанно, см. PLAN.md шаг 4) — класс «добавил вызов git-примитива в середину проверяемой функции, забыл один из нескольких моков-потребителей» стоит держать в чек-листе разработчика при следующей правке `gitcmd.py`, раз уже сам разработчик независимо отметил родственную проблему («третий по счёту частный диспетчер git-заглушки») в PLAN.md, «Предложения системе».
