---
task: 01M1KVG3KSCY47HWXWF5HM0E76
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 2
schema_version: 3    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: Автокоммит артефактов шага учитывает .gitignore

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (автокоммит фильтрует по `.gitignore`, критерий = `git check-ignore`, не список расширений) | OK | `gitcmd.check_ignore` (orchestrator/gitcmd.py:143-176) — настоящий `git check-ignore -v -z --stdin`; `checkpoint._commit_external_step_artifacts` (orchestrator/checkpoint.py:300-309) фильтрует им `raw_files`/`existing` до diff'а. `dropme/`-тест (директорное правило, не суффикс) зелёный — AC-1 подтверждено. |
| 2 (игнорируемый файл в ветке стабилен в обе стороны) | OK | orchestrator/checkpoint.py:307-309 — `files`/`existing` фильтруются СИММЕТРИЧНО ДО вычисления `removed`/добавлений; юнит- и приёмочные тесты на удаление/перезапись зелёные (AC-3). |
| 3 (лок не спорит из-за игнорируемых файлов) | OK | `fsm_advance.in_dev` (orchestrator/fsm_advance.py:505-541) — `gitcmd.diff_names` + вычитание `gitcmd.check_ignore(names)`; критерий явно «`.gitignore` пульта» (проверяется в `config.ROOT`) — соответствует формулировке требования. AC-4 зелёный. |
| 4 (`doctor --fix` убирает игнорируемые файлы, журналит, `main` не трогает) | OK | `doctor._fix_ignored_artifact_files` (orchestrator/doctor.py:1026-1067) + `artel.py`/`doctor.cmd_doctor` флаг `--fix`; пишет плотницки (`artifact_branch.commit_files`/`write_commit`, temp `GIT_INDEX_FILE`) — `main`/рабочее дерево не трогает по построению (проверено кодом `artifact_branch.py:39-137`); журналит только затронутые задачи, `done`/`killed` пропускает тем же фильтром, что `check_orphans`. AC-5 зелёный. |
| 5/6 (тесты, регрессия) | OK | Полный `tests/` (1374), планка A7 (44) и планка hotfix 01M1KT0792125J9ZNJNZJ86E9Q зелёные — см. «Проверено исполнением». AC-6 зелёный. |

## Замечания
Пусто — обе записи прошлой итерации закрыты (см. «Реестр замечаний»),
новых замечаний в инкрементальном diff (017e977..HEAD: только тестовые
файлы, `.gitignore`, `docs/codebase-map.md`) не найдено.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_gitcmd_check_ignore.py:28-104, tests/test_doctor_fix_ignored_artifacts.py:43-102, tests/test_checkpoint_external_step_artifacts.py:277-345, tests/test_acceptance_tests_flow.py:1166 | 22 новых/изменённых юнит-теста без заявки `Ловит мутацию:` в докстринге | ревью и будущие читатели не могут сверить тест с заявленной мутацией; риск тавтологичных/неловящих тестов остаётся непроверяемым | подтверждено: коммит `b94ba66` добавил `Ловит мутацию: …` во все 22 метода (пересчитано по diff `017e977..b94ba66` — 11+5+5+1); выборочно сверено с реальным кодом (`gitcmd.check_ignore` — `i+3`/`i+=4`-парсинг `-z`-полей, `try/except OSError`, `if not paths: return set()`; `checkpoint._commit_external_step_artifacts` — симметричная фильтрация `raw_files`/`existing` до diff'а строки 294-309; `doctor._fix_ignored_artifact_files` — фильтр `done`/`killed`, условный journal); заявки конкретны и правдоподобны, не пересказ имени метода — закрываю |
| R1-F2 | accepted | tasks/01M1KVG3KSCY47HWXWF5HM0E76/acceptance_tests/test_ac6_existing_plankas_stay_green.py:106-110 | извлечение hotfix-планки в фиксированный реальный путь репозитория, без изоляции от конкурентных/прерванных прогонов | конкурентный или прерванный прогон оставляет мусор, ломающий все последующие прогоны того же теста до ручной уборки | отказ разработчика обоснован: файл — часть зафиксированной приёмочной планки этой же задачи (test_author, tasks/T023), правка кода теста ролью developer вне полномочий роли — необходима эскалация, а не фикс в этой итерации; severity minor, явно помечено вердиктом итерации 1 как «на усмотрение, не блокирует» — принимаю отказ |

## Вердикт
approved — оба замечания прошлой итерации закрыты (R1-F1 исправлено и
проверено против кода, R1-F2 обоснованно отклонено в рамках полномочий
роли), новых дефектов в инкрементальном diff нет, полный набор тестов и
обе планки (A7, hotfix) зелёные.

## Проверено исполнением
- `python3 -m unittest discover -s tests -q` (полный набор) — 1374 теста, OK.
- `python3 -m unittest discover -s tasks/01M1KVG3KSCY47HWXWF5HM0E76/acceptance_tests -q` — 8 тестов (AC-1..AC-6), OK.
- `python3 -m unittest discover -s tasks/01M1H224X5A8W159MKF1Q24R5Y/acceptance_tests -q` (планка A7) — 44 теста, OK.
- `python3 -m unittest tasks.01M1KVG3KSCY47HWXWF5HM0E76.acceptance_tests.test_ac6_existing_plankas_stay_green -v` (изолированный прогон AC-6, включая вытяжку планки hotfix 01M1KT0792125J9ZNJNZJ86E9Q) — 2 теста, OK.
- `python3 -m unittest tests.test_gitcmd_check_ignore tests.test_doctor_fix_ignored_artifacts tests.test_checkpoint_external_step_artifacts tests.test_acceptance_tests_flow.LockTest.test_pyc_only_diff_after_lock_does_not_block_the_transition -v` — 32 теста (включая все 22 метода из R1-F1), OK; докстринги в выводе `-v` подтверждают наличие строки `Ловит мутацию: …` у каждого.
- `git diff 017e977..HEAD -- . ':!tasks/01M1KVG3KSCY47HWXWF5HM0E76/REVIEW.md'` — инкремент с прошлого вердикта: только 22 докстринга (R1-F1), `.gitignore` (`.pytest_cache/`, коммит оператора `74ba725`, подтянут через main — не правка этой задачи) и `docs/codebase-map.md` (только `built_at_sha`, содержимое не менялось — не дефект). Функциональный код (`orchestrator/*.py`) с прошлой итерации не менялся.
- `git diff main...HEAD --stat` (весь MR) — защищённые пути (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) не затронуты.
- `git status --short` после прогона всех тестов — рабочее дерево чистое, `addCleanup` теста AC-6 не оставил мусора.

## Предложения системе
- review-checklist требует заявку `Ловит мутацию:` для «каждого нового/изменённого теста» без явной оговорки области, а сам приём формально описан в skills/test-authoring.md — скиле, адресованном роли test_author и `acceptance_tests/`. На практике конвенция в `tests/` соблюдается менее чем в 10% файлов — стоит явно решить и зафиксировать в skills: требование либо распространяется на юнит-тесты разработчика тоже (тогда стоит подсветить это в conventions-core/developer-скиле), либо остаётся зоной test_author, и review-checklist нужно сузить формулировку. (Повтор наблюдения из итерации 1 — не снято.)
