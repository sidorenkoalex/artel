---
task: 01M1KVG3KSCY47HWXWF5HM0E76
type: review
author_role: reviewer
status: changes_requested        # draft | approved | changes_requested | escalate
iteration: 1
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

- major — `tests/test_gitcmd_check_ignore.py` (все 11 методов: `CheckIgnoreTest` строки 28-72, `DiffNamesTest` строки ~78-104), `tests/test_doctor_fix_ignored_artifacts.py` (все 5 методов, строки 43-102), `tests/test_checkpoint_external_step_artifacts.py:277-345` (новый класс `CommitExternalStepArtifactsGitignoreFilterTest`, 5 методов), `tests/test_acceptance_tests_flow.py:1166` (`test_pyc_only_diff_after_lock_does_not_block_the_transition`) — ни один из 22 новых/изменённых тестовых методов не несёт докстринг с заявкой `Ловит мутацию: …` (review-checklist, Фаза B п.3; skills/test-authoring.md). У `test_pyc_only_diff_after_lock_does_not_block_the_transition` докстринг вообще есть (описывает сценарий), но без строки-заявки; у остальных 21 — докстринга нет вовсе, только (местами) докстринг класса. Это ровно тот код, что покрывает НОВУЮ фильтрующую логику задачи (`check_ignore`, `diff_names`, симметрия исключения в `checkpoint.py`, лок в `fsm_advance.py`, `doctor --fix`) — без заявленной мутации ревьювер не может сверить тест с ней (как требует чеклист), а будущий читатель не может быстро понять, какую регрессию каждый тест ловит. Предложение: добавить в докстринг каждого метода из перечисленных 22 строку `Ловит мутацию: …` (конкретная правдоподобная поломка, как это уже сделано в `tasks/01M1KVG3KSCY47HWXWF5HM0E76/acceptance_tests/*` — образец в этом же MR).
- minor — `tasks/01M1KVG3KSCY47HWXWF5HM0E76/acceptance_tests/test_ac6_existing_plankas_stay_green.py:106-110` (`test_ac6_hotfix_planka_stays_green`) — извлечение планки hotfix кладётся по ФИКСИРОВАННОМУ пути внутри настоящего рабочего дерева (`_REPO_ROOT / "tasks" / HOTFIX_TASK`), защищённому только `assertFalse(dest.exists())` + `addCleanup`, без блокировки/уникального имени. При конкурентном запуске этого же теста (воспроизведено во время этого ревью: два одновременных вызова того же файла — один увидел каталог, оставленный другим ещё не завершившимся вызовом, и упал на `assertFalse`) либо при прерывании (таймаут/kill CI ровно во время `git archive`/`tar`, до `addCleanup`) каталог остаётся на диске и ЛОМАЕТ КАЖДЫЙ последующий прогон этого теста тем же `assertFalse`, пока кто-то вручную не уберёт `tasks/01M1KT0792125J9ZNJNZJ86E9Q`. Два изолированных (не конкурентных) прогона в рамках этого ревью прошли зелёными — дефекта в штатном последовательном сценарии нет, только хрупкость при параллели/прерывании. Предложение: извлекать в путь с уникальным суффиксом (например `f"tasks/{HOTFIX_TASK}-{os.getpid()}"` с симлинком/копией под ожидаемым именем для `parents[3]`) либо явно документировать «тест не безопасен для параллельного запуска» рядом с `_resolve_hotfix_ref`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_gitcmd_check_ignore.py:28-104, tests/test_doctor_fix_ignored_artifacts.py:43-102, tests/test_checkpoint_external_step_artifacts.py:277-345, tests/test_acceptance_tests_flow.py:1166 | 22 новых/изменённых юнит-теста без заявки `Ловит мутацию:` в докстринге | ревью и будущие читатели не могут сверить тест с заявленной мутацией; риск тавтологичных/неловящих тестов остаётся непроверяемым | добавить в докстринг каждого метода строку `Ловит мутацию: …` по образцу acceptance_tests этой же задачи |
| R1-F2 | open | tasks/01M1KVG3KSCY47HWXWF5HM0E76/acceptance_tests/test_ac6_existing_plankas_stay_green.py:106-110 | извлечение hotfix-планки в фиксированный реальный путь репозитория, без изоляции от конкурентных/прерванных прогонов | конкурентный или прерванный прогон оставляет мусор, ломающий все последующие прогоны того же теста до ручной уборки | извлекать во временный/уникальный путь (например с `os.getpid()`) вместо голого `_REPO_ROOT / "tasks" / HOTFIX_TASK` |

## Вердикт
changes_requested — добавить заявки `Ловит мутацию:` в докстринги 22 новых/изменённых юнит-тестов (R1-F1, major). R1-F2 (minor) — на усмотрение разработчика, не блокирует.

## Проверено исполнением
- `python3 -m unittest discover -s tests -q` (полный набор) — 1374 теста, OK.
- `python3 -m unittest discover -s tasks/01M1KVG3KSCY47HWXWF5HM0E76/acceptance_tests -q` — 8 тестов (AC-1..AC-6), OK.
- `python3 -m unittest discover -s tasks/01M1H224X5A8W159MKF1Q24R5Y/acceptance_tests -q` (планка A7) — 44 теста, OK (прогнано дважды независимо, оба раза зелёное).
- `python3 -m unittest tasks.01M1KVG3KSCY47HWXWF5HM0E76.acceptance_tests.test_ac6_existing_plankas_stay_green -v` (изолированный прогон AC-6, включая вытяжку планки hotfix 01M1KT0792125J9ZNJNZJ86E9Q из `artifact/01m1kt0792125j9znjnzj86e9q`) — 2 теста, OK.
- `python3 -m unittest tests.test_gitcmd_check_ignore tests.test_doctor_fix_ignored_artifacts -v` — 16 тестов, OK.
- `python3 -m unittest tests.test_checkpoint_external_step_artifacts -v` — 15 тестов (включая 5 новых), OK.
- `python3 -m unittest tests.test_acceptance_tests_flow.LockTest.test_pyc_only_diff_after_lock_does_not_block_the_transition -v` — 1 тест, OK.
- Прочитан код `orchestrator/gitcmd.py` (check_ignore/diff_names), `orchestrator/checkpoint.py:260-338`, `orchestrator/fsm_advance.py:467-560`, `orchestrator/doctor.py:1015-1090`, `orchestrator/artifact_branch.py:1-137` — подтверждено: `check_ignore`/`diff_names` оба зовутся с `cwd=config.ROOT` (единый критерий «.gitignore пульта» для лока даже на foreign-target); `doctor --fix` пишет только плотницки в `refs/heads/artifact/<id>` (временный `GIT_INDEX_FILE`), `main`/рабочее дерево не затрагивает; `done`/`killed` фильтруются тем же приёмом, что `check_orphans`.
- `git show --stat b137903` — подтяжка main (HEAD) не затронула `*.py`, регенерация `docs/codebase-map.md` для неё не требовалась; сама карта (diff) корректно отражает новые функции `check_ignore`/`diff_names` и новые импорты (`doctor.py -> artifact_branch`, тестовые файлы).
- Diff проверен на отсутствие правок защищённых путей (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) — не затронуты.

## Предложения системе
- review-checklist требует заявку `Ловит мутацию:` для «каждого нового/изменённого теста» без явной оговорки области, а сам приём формально описан в skills/test-authoring.md — скиле, адресованном роли test_author и `acceptance_tests/`. На практике конвенция в `tests/` соблюдается менее чем в 10% файлов (6 из 79) — стоит явно решить и зафиксировать в skills: требование либо распространяется на юнит-тесты разработчика тоже (тогда стоит подсветить это в conventions-core/developer-скиле), либо остаётся зоной test_author, и review-checklist нужно сузить формулировку.
