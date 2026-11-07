---
task: 01M6TRKY1A41QSZMCXY9TKYXG7
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Приёмка принимает итог CI для дерева кода — без условия свежести при мерже пультом, с приложениями PLAN (ADR-0031, этап 1)

## Подход

Механика одна — условия принятия итога CI `_ci_result_conditions`
(`orchestrator/acceptance.py`) и два её потребителя (`_acceptance_suite_run`
режима `local`, `_ci_job_run` режимов `ci`/`both`). Канал доказательства —
по ANSWER-4: сценарий CI печатает одну строку
`::notice title=plan-appendix-docs::ref=<X>; outcome=<…>; diffs=<h1,…>`,
приёмка читает аннотации ровно проверки `ci.FULL_SUITE_JOB`.

- `_ci_result_conditions` получает два именованных параметра:
  `freshness_held` (запись проекта — `merge_gate: operator`) и
  `appendix_refusal` (проверка доказательства CI для дерева, отличного от
  головы). Возвращает третье значение — основания принятия; они
  дописываются в запись журнала после прежнего начала (`полный набор:
  принят итог CI …`, `CI_JOB_RECORD…`), поэтому `is_ci_result` узнаёт
  запись по-прежнему. Основание «без проверки свежести» пишется только
  тогда, когда голова действительно не содержит `origin/<base>`.
- Свежесть: `merge_gate` читается из записи проекта задачи; только
  значение `operator` снимает условие. Не прочитано (поля нет, файл не
  разобран) — свежесть проверяется прежним текстом. В `local` сверка с
  `config.MAIN_BRANCH`, в `ci`/`both` — с `base` записи, как раньше.
  Значение сравнивает только `targets` (сторож
  `test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac9_no_support_literals_outside_targets`):
  `_freshness_held` зовёт существующий предикат
  `targets.push_whitelisted` (ложь ровно при `merge_gate: operator`; поля
  нет — истина, свежесть проверяется), без литерала в `acceptance.py`.
- Приложения (только `local`, только артель, только при непустом списке
  приложений из `appendix_tree.read_plan`): по порядку проверяются чистота
  рабочей копии (3а), источник PLAN (3е), сценарий-публикатор в голове
  против `origin/<base>` (3ж), публикация `FULL_SUITE_JOB` с исходом
  `applied` и sha X (3б), равенство локальной ссылки документов `origin`
  только чтением `gitcmd.remote_ref_state` (3г), X — предок головы ссылки
  (3в), blob PLAN.md в X и в голове (3д), упорядоченный список sha256
  диффов (3з). Любой отказ — прежний путь, причина одной строкой. Без
  приложений — прежний текст «дерево гейта отличается…».
- Чистота (3а): `git diff --name-only HEAD` пуст и нет неотслеживаемых
  неигнорируемых файлов; неотслеживаемые под `tasks/` не считаются — то же
  правило, что у снимка дерева гейта `suite_tree_hash` (выкладка планки и
  документы в копии кода в дерево головы не входят).
- `ci.full_suite_publication(sha)`: проверки коммита (`check_runs`) →
  ровно одна проверка `FULL_SUITE_JOB` с `id` → `gh api
  …/check-runs/<id>/annotations` → ровно одна аннотация заголовка
  `plan-appendix-docs` → разбор строки строгим выражением. Ноль или больше
  одной — отказ.
- Сценарий `scripts/plan_appendix_ci.py`: после `fetch` ссылки сверяет
  `FETCH_HEAD` с sha `ls-remote` (расхождение — `CiError` одной строкой,
  код 1) и печатает ровно одну строку публикации на исходах `no-ref`,
  `no-plan`, `no-appendices`, `applied` (после успешного наложения; список
  — всех приложений, наложенных или «уже в базе»). Наложение не меняется.
  Хеш — `appendix_digests` (sha256 hex байтов UTF-8 `PlanAppendix.diff`),
  у приёмки — своя функция `acceptance.appendix_digests` той же формы:
  сценарий не импортирует пульт.

Бюджет SPEC ($60) не пересматривается.

## Шаги

1. `scripts/plan_appendix_ci.py`: сверка `FETCH_HEAD`, `publication_line`,
   `appendix_digests`, печать публикации в `run`.
2. `orchestrator/ci.py`: `PUBLICATION_TITLE`, `CiPublication`,
   `parse_publication`, `full_suite_publication`.
3. `orchestrator/acceptance.py`: основания, чтение `merge_gate`, проверка
   доказательства приложений, новая форма `_ci_result_conditions`, запись
   журнала в обоих режимах.
4. Свои юнит-тесты на свойства вне долгоживущих файлов задачи:
   `tests/test_ci_publication_parse.py` (разбор строки публикации, круг
   «сценарий печатает — ci разбирает»).
5. Перевод случаев несвежей ветки при `operator` в существующих тестах
   (мандат ANSWER-1) — только если покраснеют; карта
   `python3 scripts/codebase_map.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 3, 5 |
| 2 | 1, 2 |
| 3 | 2, 3 |
| 4 | 3 |
| 5 | — (не трогается: `fsm_merge_gate` не правится) |
| 6 | 3 (ветка `fresh` прежняя) |

## Влияние на систему

- Ослабление гейта приёмки ограничено двумя случаями, принятыми ADR-0031
  (этап 1): свежесть у `merge_gate: operator` держит `merge_gate`
  (`_sync_main_or_wait` + полный прогон приложений), дерево с приложениями
  принимается только при доказательстве CI по восьми условиям 3а–3з.
  Любая неоднозначность — прежний локальный прогон (fail-closed).
- `target-human` — прежнее поведение побайтно (тексты причин те же).
- `merge_gate`, `fsm_merge_gate._full_suite_or_refuse`, `.github/`,
  наложение приложений в сценарии — не меняются.
- Отказ сценария при расхождении `FETCH_HEAD` строже прежнего «PLAN.md нет»
  (прежде молча зелёный CI без приложений).
- Откат — revert merge-коммита задачи.

## Риски

- Аннотации GitHub читаются через `gh api` с правом `checks:read` токена
  пульта; нет права — отказ с причиной, локальный прогон (как прежде).
- Сценарий исполняется и в job `python-min`, и в job `guard`
  (`--check-workflow`): их публикации лежат у других проверок и не
  читаются (требование 2).

## Проверка

- Долгоживущие файлы задачи: `tests/test_01m6trky1a41qszmcxy9tkyxg7_ci_result.py`
  41/41, `…_ci_publication.py` 5/5 — зелёные.
- Существующие тесты: красны были ровно три случая несвежей ветки при
  `operator` (`test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py::CiAcceptanceTest::test_ac4_bad_ci_or_stale_branch_runs_local_suite`
  подслучай `stale`; `test_01m5xzskk8gzteca2kwafhe029_ci_full_suite.py::test_ac9_unmet_condition_unknown_without_local_run[stale_base]`,
  `::test_ac10_fresh_suite_rereads_ci_without_local_run[stale_base]`) —
  по мандату ANSWER-1 переведены на запись `target-human`, утверждения и
  имена не менялись; после перевода зелёные. `test_acceptance.py`,
  `test_acceptance_suite_profile.py`, `test_report_outcome_module.py`,
  `test_task_component_places.py`, тесты сценария CI (`test_plan_appendix_ci.py`,
  `test_01m443…`, `test_01m466…`, `test_01m4jd3…`, `test_01m5tbfc…`) — зелёные.
- Новый `tests/test_ci_publication_parse.py` (11): мутации `fullmatch` →
  `search` и «первая из двух проверок `FULL_SUITE_JOB`» красят его (проверено
  временной правкой, откачено).
- Не прогнан в шаге: `test_01m443…::NoCommitNoPushTest::test_ac4_script_creates_no_commits_and_moves_no_refs`
  — в окружении роли `shutil.which("git")` даёт обёртку `role_bin/git`,
  та через PATH находит прокладку теста, рекурсия до тайм-аута; от правки
  не зависит (CI без обёртки роли).

- Возврат из verifying (литерал `merge_gate == 'operator'` в
  `acceptance._freshness_held`) закрыт вызовом `targets.push_whitelisted`;
  после правки зелёные: сторож `test_01m5w27…_unsupported_project.py`,
  `…ci_result.py`, `…ci_publication.py`, `test_01m4begq…_ci_acceptance.py`,
  `test_01m5xzskk…_ci_full_suite.py`, `test_ci_publication_parse.py` —
  115 passed.

## Предложения системе

- В `targets.py` нет предиката «мержит пульт» (`merge_gate: operator`)
  под своим именем — приёмке пришлось звать `push_whitelisted`, чьё имя
  про белый список отправок; стоит завести `merged_by_pult(entry)`.

- `python3 -c "from orchestrator import checkpoint"` падает циклом импорта
  (`fixation` → `workspace` → `lease` → `artifact_branch` →
  `fixation.FIXATION_AUTHOR_NAME`): файл
  `tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py` сам по себе не
  собирается, только после файла, импортирующего `catalog`.
- Тесты с прокладкой `git` (`GIT_SHIM`, `shutil.which("git")`) виснут в шаге
  роли: обёртка `orchestrator/role_bin/git` ищет git по PATH и находит
  прокладку. Стоит звать в прокладке `role_git.real_git()`-аналог или
  пропускать обёртку роли при поиске.
