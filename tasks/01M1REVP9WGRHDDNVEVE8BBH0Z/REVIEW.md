---
task: 01M1REVP9WGRHDDNVEVE8BBH0Z
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 4
---

# REVIEW: критерий сироты для `doctor --fix` и предпросмотр кандидатов

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (сирота = нет в БД И нет на origin, один `ls-remote --heads origin 'artifact/*'` на прогон) | OK | `orchestrator/doctor.py::_remote_artifact_branch_names`/`_orphan_artifact_branches` (строки 1390-1448); подтверждено юнит- и приёмочными тестами (AC-1/AC-2/AC-3 зелёные). |
| 2 (ветка на origin — не сирота, даже без строки БД) | OK | Фильтр `b not in remote` в `_orphan_artifact_branches` (doctor.py:1446-1448); `test_ac2_*` зелёные. |
| 3 (`doctor` без `--fix` печатает число+первые N имён+пометку) | OK | `cmd_doctor` else-ветка (doctor.py:1660-1664) + `_print_orphan_branch_candidates` (doctor.py:1502-1512); `test_ac4_*` зелёные. |
| 4 (`doctor --fix` печатает тот же предпросмотр до удаления, число удалённых после) | OK | `cmd_doctor` fix-ветка (doctor.py:1634-1655); `test_ac5_*` зелёные. |
| 5 (origin недоступен → `--fix` не удаляет ничего, FAIL с именованной причиной) | OK | `orphans is None` → `Check("orphan-branches-origin", "fail", ...)`, `sweep_orphan_artifact_branches` не вызывается (doctor.py:1635-1640); `test_ac6_*` и `CmdDoctorOriginUnavailableTest` зелёные. |
| 6 (origin недоступен → предпросмотр печатает «критерий не вычислим без origin») | OK | `cmd_doctor` else-ветка (doctor.py:1661-1662); `test_ac7_*` зелёный. |

## Замечания

- major — `tests/test_doctor.py:955,965,986,1013,1021,1034,1045,1064,1074,1091,1102,1121,1131` — из 15 новых тестовых методов этой задачи (классы `RemoteArtifactBranchNamesTest`, `OrphanArtifactBranchOriginFilterTest`, `SweepOrphanArtifactBranchesOriginGateTest`, `PrintOrphanBranchCandidatesTest`, `CmdDoctorOriginUnavailableTest`) только 2 несут заявку `Ловит мутацию: …` (skills/test-authoring.md, «Чувствительность: у теста — заявленная мутация»; review-checklist Фаза B п.3). Конкретно:
  - без докстринга вовсе (нарушает и «Докстринг — сценарий, не пересказ имени»): `test_parses_branch_names_from_ls_remote_output:955`, `test_absent_from_both_is_an_orphan:1013`, `test_orphans_none_deletes_nothing_and_raises_no_incident:1064`, `test_truncates_names_to_the_configured_limit:1091`, `test_empty_list_does_not_crash:1102`, `test_fix_mode_fails_named_and_does_not_call_sweep:1121`, `test_preview_mode_reports_uncomputable_and_does_not_exit:1131`;
  - докстринг есть, но без явной заявки `Ловит мутацию: …` (описывает сценарий/требование, не называет правдоподобную поломку): `test_empty_response_is_an_empty_set_not_none:965`, `test_git_not_answering_at_all_is_none:986`, `test_known_to_db_but_absent_from_origin_is_not_an_orphan:1021`, `test_remote_none_makes_the_whole_result_none:1034`, `test_default_argument_computes_remote_itself:1045`, `test_default_argument_computes_orphans_itself:1074`.

  Последствие: ревьювер (и будущий читатель) не может сверить, какую конкретно поломку каждый тест обязан ловить — часть этих тестов (например, `test_absent_from_both_is_an_orphan`) сама по себе не отличает мутацию `and`→`or` в критерии (это разделяют только соседние тесты класса), и без явной заявки это не очевидно из кода теста. Ровно тот класс пробела, что уже отмечался в предыдущих задачах (приёмочные тесты соблюдают конвенцию `test-authoring.md`, а новые юнит-тесты в `tests/*.py` — часто нет).

  Предложение: для каждого перечисленного метода добавить докстринг вида «<сценарий одной строкой>.\n\nЛовит мутацию: <конкретная правдоподобная поломка реализации, на которой тест покраснеет>» — по образцу уже соответствующих конвенции методов этой же задачи (`test_nonzero_return_code_is_none:975`, `test_present_on_origin_is_not_an_orphan_even_without_a_db_row:1002` — сверено по номерам строк текущего файла).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | tests/test_doctor.py:955,965,986,1013,1021,1034,1045,1064,1074,1091,1102,1121,1131 | 15 новых тестовых методов, у 13 нет заявки `Ловит мутацию: …` (7 из них — вовсе без докстринга) | нарушение test-authoring.md, тесты нельзя сверить с заявленной чувствительностью | всем 13 перечисленным методам добавлена (или дополнена, где докстринг уже был) заявка `Ловит мутацию: <конкретная поломка>` — по образцу уже соответствующих конвенции методов той же задачи; логика тестов не менялась, `python3 -m unittest tests.test_doctor` — 110/110 зелёных |

## Вердикт

changes_requested — устранить R1-F1 (докстринги с заявкой `Ловит мутацию: …` для перечисленных методов `tests/test_doctor.py`). Логика и покрытие требований/AC сами по себе корректны, отдельного изменения кода `orchestrator/doctor.py`/`config.py` не требуется.

## Проверено исполнением

- `cd tasks/01M1REVP9WGRHDDNVEVE8BBH0Z/acceptance_tests && python3 -m unittest test_ac1_ac2_orphan_criterion test_ac3_single_origin_query test_ac4_preview_without_fix test_ac5_fix_preview_then_deleted_count test_ac6_origin_unavailable_blocks_fix test_ac7_origin_unavailable_preview_message -v` — 11 тестов, все зелёные (AC-8 — легальный skip, ci-covered).
- `python3 -m unittest tests.test_doctor -v` (полный модуль, включая изменённый и новые тесты) — 110 тестов, все зелёные.
- `python3 -m unittest tests.test_invariants tests.test_coldstart` — 56 тестов, все зелёные (модули, соседние с зоной задачи, риск PLAN).
- `python3 scripts/codebase_map.py` (регенерация в отдельную копию, дифф без строки `built_at_sha`) — содержимое совпадает с закоммиченным `docs/codebase-map.md`; расхождение только в `built_at_sha`, что не является дефектом (conventions). Рабочее дерево возвращено `git checkout -- docs/codebase-map.md` после проверки.
- Прочитан код `orchestrator/doctor.py` (строки 1373-1667) и `orchestrator/config.py` (176-190) целиком в контексте изменения; сверено с SPEC/PLAN артефактной ветки `artifact/01m1revp9wgrhddnveve8bbh0z` (SPEC.md/PLAN.md не материализованы в самой кодовой ветке — прочитаны через `git show`).

## Предложения системе

- Повторно подтверждается наблюдение [[feedback_test_authoring_mutation_claim_gap]]: разрыв между дисциплиной приёмочных тестов (test_author, под локом) и юнит-тестами разработчика в `tests/*.py` по заявке `Ловит мутацию: …` — стоит рассмотреть, не добавить ли эту проверку в guard.py хотя бы для новых/изменённых тестов в диффе MR (сейчас это целиком на ревьювере, вручную).
