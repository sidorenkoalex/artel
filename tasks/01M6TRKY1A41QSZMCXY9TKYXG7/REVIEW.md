---
task: 01M6TRKY1A41QSZMCXY9TKYXG7
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Приёмка принимает итог CI для дерева кода — без условия свежести при мерже пультом, с приложениями PLAN (ADR-0031, этап 1)

## Фаза A: план

- Таблица покрытия полна: требования 1–6 сопоставлены шагам; 5 — явно «не трогается» (в diff `fsm_merge_gate` нет), 6 — ветка `fresh` прежняя (`orchestrator/acceptance.py:4142`, в `_ci_job_run` путь `fresh` не тронут).
- Шаги — единицы размера MR (сценарий / `ci.py` / `acceptance.py` / юнит-тесты / перевод тестов по мандату).
- Подход не конфликтует с архитектурой: значение `merge_gate` сравнивает только `targets` (`targets.push_whitelisted`, `orchestrator/targets.py:615-620`, ложь ровно при `operator`, поля нет → истина → свежесть проверяется), литерала в `acceptance.py` нет; канал публикации — по ANSWER-4.
- «Влияние на систему» = diff: тронуты ровно `orchestrator/acceptance.py`, `orchestrator/ci.py`, `scripts/plan_appendix_ci.py`, два теста по мандату ANSWER-1, новый `tests/test_ci_publication_parse.py`, карта. `.github/`, `gates.yaml`, `skills/`, `templates/` не тронуты. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_freshness_held(entry)` в обоих потребителях (`acceptance.py:4150`, `:4402`). `local` — сверка с `config.MAIN_BRANCH` прежняя (`:4148`), `ci`/`both` — с `base` записи. Запись не прочитана (`_project_entry` → None) или поля нет — свежесть проверяется прежним текстом. AC-1/2/3 зелёные. |
| 2 | OK | Сценарий: сверка `FETCH_HEAD` с sha `ls-remote` в `plan_text` (`CiError` одной строкой → код 1); ровно одна строка `::notice title=plan-appendix-docs::…` на четырёх исходах; при `applied` — `appendix_digests` всех приложений, включая «уже в базе» (печать после цикла). Наложение не менялось. Чтение — `ci.full_suite_publication`: ровно одна проверка `FULL_SUITE_JOB`, ровно одна аннотация заголовка, `fullmatch`. Имя `FULL_SUITE_JOB` («Синтаксис и тесты оркестратора») совпадает с job, в котором идёт шаг сценария (`.github/workflows/ci.yml:208`, `:235`); публикации `python-min` (`:282`) и guard (`--check-workflow`, `:49`) не читаются. |
| 3 | OK | `_appendix_ci_refusal` передаётся только в `_acceptance_suite_run` (режим `local`), отказ не у артели и без приложений — прежний `TREE_DIFFERS`. Условия 3а (`_worktree_dirt`: `git diff --name-only HEAD` + `ls-files --others --exclude-standard`, кроме `tasks/`), 3е (`artifact_source.resolve` против `artifact_branch.branch_name`), 3ж (blob сценария головы против `origin/<base>`), 3б (исход `applied` и непустой ref), 3г (только чтение: `artifact_branch.ref_head` — `_head` в репо задачи, `gitcmd.remote_ref_state`; `origin_sync_refusal` не зовётся — AC-7 проверяет, что `origin` не сдвинут), 3в (`is_ancestor(x, remote)`), 3д (blob PLAN.md в X и в голове `origin`), 3з (`list(published.diffs) == appendix_digests(appendices)` — упорядоченно, appendices — разбор `guard` пульта через `appendix_tree.read_plan`). Каждый отказ — одна строка. |
| 4 | OK | Основание дописывается суффиксом `; основание: …` после прежнего начала: `local` — после «полный набор: принят итог CI {sha}, прогон {id}», `ci` — `record += _basis_suffix(bases)` после записи, начинающейся `CI_JOB_RECORD`; `is_ci_result` узнаёт (AC-1 ci, AC-4 проверяют `is_ci_result`). Основание свежести пишется только когда голова реально не содержит `origin/<base>`. |
| 5 | OK | `fsm_merge_gate` не тронут. |
| 6 | OK | AC-12 оба режима зелёные. |

## Замечания

Замечаний уровня blocker/major/minor нет.

Наблюдения (не замечания, к сведению Оператора):

- Существующие тесты (мандат ANSWER-1): `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py:161-169` — подслучай `stale` переведён на запись `target-human`; `tests/test_01m5xzskk8gzteca2kwafhe029_ci_full_suite.py:401-411` — ветка `else` в `break_condition` достигается только `stale_base` (`CONDITIONS`, `:388-389`), перевод на `target-human` с `assert gate` (неуспешная замена красит тест, а не тихо проходит). Утверждения, имена и случаи не изменены; свежесть по `origin/<base>` (не `main`) по-прежнему проверяется случаем на `target-human` — условие матрицы ANSWER-1 выполнено. Иных правок `tests/` вне нового файла нет.
- `tests/test_ci_publication_parse.py`: круг «сценарий печатает — `ci` разбирает» частично пересекается со сквозным `test_ac15_…[script_publication]` долгоживущего файла, но покрывает то, чего тот не видит (разбор `ci` на исходах `no-plan`/`no-appendices`/`no-ref` с пустым ref, строгость `fullmatch`, две проверки `FULL_SUITE_JOB`) — повтором не считаю. Заявки мутаций наблюдаемы; заявка `test_two_full_suite_checks_refuse_publication` подтверждена временной мутацией (см. ниже).
- Модель угрозы канала (уровень SPEC/ANSWER-4, не дефект реализации): аннотация `::notice` не привязана к шагу job. Сценарий-публикатор защищён 3ж, разбор — 3з, но сам процесс сценария импортирует `scripts/guard.py` → модули `orchestrator/` проверяемой ветки; ветка теоретически может при импорте подавить печать настоящей строки и пропуск `git apply`, а строку с верными sha256 (вычислимыми из PLAN) напечатать позже из теста в том же job. Тогда 3а–3з выполнены при дереве CI без приложений. Закрывается только вне зоны задачи (печать публикации до импорта кода ветки / отдельный защищённый шаг в `.github/`), поэтому — наблюдение, не замечание.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

(Записей нет: замечаний итерации 1 не заведено, прошлых итераций нет.)

## Вердикт

approved — требования 1–6 реализованы, отказ fail-closed по каждому условию 3а–3з, правка существующих тестов в границах мандата ANSWER-1, защищённые пути не тронуты.

## Проверено исполнением

- `python3 -m pytest -p no:cacheprovider -q tests/test_01m6trky1a41qszmcxy9tkyxg7_ci_result.py tests/test_01m6trky1a41qszmcxy9tkyxg7_ci_publication.py tests/test_ci_publication_parse.py tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py tests/test_01m5xzskk8gzteca2kwafhe029_ci_full_suite.py tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py` — 115 passed, 4 subtests passed (145 с).
- `artel.py plank-run 01M6TRKY1A41QSZMCXY9TKYXG7` — отказ «планки нет: в источнике нет файлов test_*.py»: планка задачи — только долгоживущие файлы `tests/` (прогнаны выше).
- Временная мутация `orchestrator/ci.py::full_suite_publication`: `if len(suite) != 1` → `if not suite` (берётся первая проверка) — `tests/test_ci_publication_parse.py::test_two_full_suite_checks_refuse_publication` красный (1 failed, 10 passed); код возвращён `git checkout -- orchestrator/ci.py`, дерево чистое.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — расхождение только в строке `built_at_sha`, содержимое свежее; файл возвращён.
- Сверено чтением: `targets.push_whitelisted` (`orchestrator/targets.py:615-620`), `artifact_branch.ref_head`/`branch_name` (`orchestrator/artifact_branch.py:96-101`, `:178-181` — только чтение), `artifact_source.resolve` (`:24-26`), `ci.FULL_SUITE_JOB` (`orchestrator/ci.py:36`) против имён job в `.github/workflows/ci.yml:208`, `:261`.

## Предложения системе

- Канал «аннотация `::notice` в job, где исполняется код ветки» доказывает публикацию только при отсутствии в том же job иного кода ветки; для этапа 2 ADR-0031 стоит печатать публикацию отдельным шагом до импорта модулей ветки или из защищённого кода (адрес: `scripts/plan_appendix_ci.py`, `.github/workflows/ci.yml:227-235`).
- Bash-разрешения шага ревью отклоняют `grep` с `$W/…` и `cd …;` — приходится звать каждую команду отдельно относительными путями; стоит указать это в миссии шага.
