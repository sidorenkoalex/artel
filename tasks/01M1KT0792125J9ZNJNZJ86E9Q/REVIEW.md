---
task: 01M1KT0792125J9ZNJNZJ86E9Q
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 3
---

# REVIEW: Hotfix A7 — маршрут analyst и канал ANSWER через источник артефактов

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`runner.step_role` читает TZ.md через `artifact_source.resolve`, поверх старой проверки, старый путь для прежнего флоу не тронут) | OK | `orchestrator/runner.py:94-106`. Приёмочные `test_ac1_analyst_role_reads_artifact_branch.py` (2 теста, оба через внутреннюю `step_role` и через публичный `runner.cmd_run`) — зелёные; `test_ac2_legacy_flow_tz_on_code_branch.py` (задача прежнего флоу, TZ на кодовой ветке) — зелёный, регресс на AC-2 подтверждён. |
| 2 (`answer` пишет `ANSWER-n.md` плотницки в артефактную ветку, кодовую ветку/worktree не трогает) | OK | `orchestrator/answer.py` переписан целиком, `_cmd_answer` больше не вызывает `workspace.ensure`. `test_ac3_answer_writes_to_artifact_branch.py` — зелёный (3 теста: happy path, нумерация ANSWER-n по содержимому ветки, кодовая ветка не заводится). AC-5 (задача прежнего флоу для `answer`) корректно закрыт пометкой `skip` в `test_ac5_legacy_flow_answer_escalation.py` с обоснованием — сценарий структурно недостижим после варианта A из `ANSWER-1.md` (после A7 у любой задачи есть артефактная ветка, отдельного пути `answer` для «задачи без неё» не существует); это решение Оператора, а не догадка разработчика — легальный пропуск по правилу skila «manual/skip — дорогие пометки». |
| 3 (`approve` в `escalated` видит ANSWER, записанный командой из требования 2) | OK | Не требовало отдельного кода — `fsm._answer_file_count` уже была ветко-корректна до этой задачи (SPEC «Материалы»). `test_ac4_approve_returns_from_escalation_after_answer.py` — зелёный, оба пути (есть свежий ANSWER / нет) проверены. |
| 4 (автокоммит артефактов шага переносит удаления) | Реализовано не так — см. R1-F1 | `test_ac6_checkpoint_propagates_deletions.py` (сценарий analyst: QUESTIONS.md → SPEC.md) — зелёный, и юнит-тесты `tests/test_checkpoint_external_step_artifacts.py::test_same_role_second_step_drops_a_file_it_no_longer_writes` / `test_same_role_deletion_does_not_remove_another_roles_file` подтверждают именно этот сценарий и его симметрию с «чужая роль не страдает». Но эвристика удаления («последний коммит пути на артефактной ветке — автокоммит ЭТОЙ ЖЕ роли ⇒ путь, отсутствующий сегодня на диске, удаляется») бьёт не только по намеренному случаю (analyst убирает QUESTIONS.md), а по любому повторному шагу той же роли в том же состоянии, где файл, который роль хочет СОХРАНИТЬ, просто не переписан на этом заходе — см. разбор ниже. Класс не покрыт ни одним тестом ни в PLAN, ни в diff. |
| 5 (существующие тесты зелёные, поведение прежнего флоу не меняется) | OK | Полный `tests/` (`python3 -m unittest discover -s tests -q`) зелёный; `test_ac7_full_suite_and_a7_tests_green.py` (гоняет и `tests/`, и приёмочные тесты A7, 44 шт.) зелёный. `test_ac2` регрессионно подтверждает, что старая проверка TZ.md на кодовой ветке не заменена, а дополнена. |

## Замечания

- major — `orchestrator/checkpoint.py:230-247` (докстринг), `:267-280` (логика `_commit_external_step_artifacts`) — правило удаления «путь пропал с диска сегодня И последний коммит этого пути на артефактной ветке — автокоммит той же роли ⇒ удалить» рассчитано и протестировано только на ОДИН задокументированный сценарий (analyst: QUESTIONS.md → SPEC.md), но применяется безусловно к ЛЮБОЙ роли на любом её повторном шаге в одном и том же FSM-состоянии. Реальный, не гипотетический контрпример — роль `developer` в состоянии `in_dev`:
  - `orchestrator/fsm_advance.py::in_dev` (строки 477-491) отказывает в переходе `in_dev -> review`, пока `PLAN.md` не в статусе `ready`/`approved` — `run`/`auto` в этом случае зовут `runner.cmd_run` для той же роли `developer` заново, без смены состояния (`orchestrator/auto.py::_cmd_auto`, цикл до `config.AUTO_MAX_STEPS=30` раз, строки 165-259);
  - `orchestrator/fsm.py::_cmd_reject` (строки 707-747) — `reject` из `acceptance`, `merge_gate` ИЛИ `verifying` тоже возвращает задачу в `in_dev` (`store.set_state(..., "in_dev", ...)`) без смены роли, до `config.LIMIT_ACCEPT_REJECTS` раз для `acceptance`, без лимита для `merge_gate`/`verifying`.
  - На каждом таком повторном шаге `commit_step_artifacts` вызывается безусловно после любого успешного (`rc==0`, без обрыва потока) прогона агента (`orchestrator/runner.py:655-659`), с ОДНОЙ И ТОЙ ЖЕ строкой commit message для пары task_id/role — независимо от того, изменилось ли что-то в FSM-состоянии. `task_dir` роли на каждом таком заходе пуст (`shutil.rmtree` в конце предыдущего успешного коммита, `checkpoint.py:283`), а `orchestrator/brief.py::developer_brief` не кладёт содержимое прежнего `PLAN.md` в промпт — единственная защита от потери файла держится на том, что агент-роль буквально перепишет `PLAN.md` заново по тексту миссии (`orchestrator/role_prompt.py:67`, «2) Напиши `{task_ref}/PLAN.md`»), что кодом никак не гарантировано. Если агент на повторном заходе решит НЕ переписывать `PLAN.md` (например, посчитает план уже актуальным и правит только код) — новая логика молча (без ошибки, только строкой в журнале) удалит `PLAN.md` с артефактной ветки пульта, как будто роль сама от него отказалась.
  - `PLAN.md` этой задачи (раздел «Риски») не упоминает этот класс вовсе — там описан только риск смены текста commit message в будущем, не риск потери файла при штатном повторном шаге той же роли.
  - Предложение: либо явно принять этот риск решением Оператора (эскалация/ADR — класс касается целостности артефактов, ADR-0002), либо сузить эвристику удаления (требовать более сильный сигнал намерения, чем просто «роль не переписала файл в этот раз» — например, не удалять файлы, чьё имя не входит в список артефактов, которые эта роль обычно порождает/убирает по своему скилу), и в любом случае добавить тест на класс «та же роль, второй шаг в ТОМ ЖЕ состоянии, файл не переписан → файл не должен быть удалён» (симметрично уже существующему `test_same_role_second_step_drops_a_file_it_no_longer_writes`, но для НЕнамеренного случая).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | orchestrator/checkpoint.py:6-24,197-267,289-297 | эвристика удаления «путь пропал с диска и последний коммит на артефактной ветке — автокоммит той же роли» срабатывает и на реальном повторном шаге той же роли в том же состоянии (auto-цикл `in_dev` при PLAN.md не ready; `reject` из acceptance/merge_gate/verifying), где ничто не гарантирует, что роль перепишет файл, который хочет сохранить | молчаливая потеря PLAN.md (или другого артефакта роли) без явного намерения — только строка в журнале, которую легко не заметить | сужена эвристика удаления (второй вариант решения из замечания): к условию «последний коммит пути — автокоммит этой же роли» добавлено обязательное условие «frontmatter `type` пути — в `_DELETABLE_ARTIFACT_TYPES` (сейчас только `questions`)», читается через `gitcmd.show`+`yamlmini.frontmatter` до принятия решения об удалении. PLAN.md/REVIEW.md/SPEC.md (`type: plan/review/spec`) больше никогда не кандидаты на удаление этим путём, даже если совпал автор последнего коммита — QUESTIONS.md (`type: questions`, единственный документированный сценарий) продолжает удаляться штатно (AC-6 и `test_same_role_second_step_drops_a_file_it_no_longer_writes` зелёные). Новый регресс-тест `tests/test_checkpoint_external_step_artifacts.py::test_same_role_second_step_in_the_same_state_does_not_drop_an_untouched_file` — та же роль, второй шаг, PLAN.md не переписан, роль пишет другой файл (REVIEW.md) в тот же `task_dir` → PLAN.md не удалён |

## Вердикт

changes_requested — R1-F1 обязателен к решению (закрыть кодом/тестом или явным принятием риска Оператором) до аппрува. Остальная реализация (требования 1, 2, 3, 5) корректна, покрыта юнит- и приёмочными тестами, поведение задач прежнего флоу не меняется.

## Проверено исполнением

- `python3 -m unittest discover -s tests -q` — весь набор `tests/` пульта, код возврата 0, все тесты зелёные.
- `python3 tasks/01M1KT0792125J9ZNJNZJ86E9Q/acceptance_tests/test_ac1_analyst_role_reads_artifact_branch.py` — 2 теста, OK.
- `python3 tasks/01M1KT0792125J9ZNJNZJ86E9Q/acceptance_tests/test_ac2_legacy_flow_tz_on_code_branch.py` — 1 тест, OK.
- `python3 tasks/01M1KT0792125J9ZNJNZJ86E9Q/acceptance_tests/test_ac3_answer_writes_to_artifact_branch.py` — 3 теста, OK.
- `python3 tasks/01M1KT0792125J9ZNJNZJ86E9Q/acceptance_tests/test_ac4_approve_returns_from_escalation_after_answer.py` — 2 теста, OK.
- `python3 tasks/01M1KT0792125J9ZNJNZJ86E9Q/acceptance_tests/test_ac5_legacy_flow_answer_escalation.py` — 0 тестов (легальный `skip` всего файла, обоснование внутри), без ошибок.
- `python3 tasks/01M1KT0792125J9ZNJNZJ86E9Q/acceptance_tests/test_ac6_checkpoint_propagates_deletions.py` — 2 теста, OK.
- `python3 tasks/01M1KT0792125J9ZNJNZJ86E9Q/acceptance_tests/test_ac7_full_suite_and_a7_tests_green.py` — 2 теста (полный `tests/` + 44 приёмочных теста A7, `tasks/01M1H224X5A8W159MKF1Q24R5Y/acceptance_tests`), OK.
- `python3 scripts/codebase_map.py` локально, сравнение `git diff docs/codebase-map.md` без строки `built_at_sha` — расхождений нет (карта в diff задачи регенерирована корректно относительно содержимого); локальная перегенерация отменена `git checkout --`, в коммит не идёт.
- Прочитаны точечно, вне пакета (причина — проверка реальности сценария R1-F1): `orchestrator/artifact_source.py`, `orchestrator/answer.py`, `orchestrator/runner.py` (полностью), `orchestrator/checkpoint.py:180-292`, `orchestrator/gitcmd.py` (`git`/`show`/`ls_tree_files`), `orchestrator/fsm_advance.py:467-524` (`in_dev`), `orchestrator/auto.py` (цикл `_cmd_auto`), `orchestrator/fsm.py:694-747` (`_cmd_reject`), `orchestrator/role_prompt.py:60-93` (миссии developer/reviewer), tasks/01M1KT0792125J9ZNJNZJ86E9Q/SPEC.md и PLAN.md (восстановлены из `artifact/01m1kt0792125j9znjnzj86e9q` — живут в артефактной ветке пульта, не в кодовой; ревью-пакет их не нашёл именно поэтому).

## Предложения системе
- `orchestrator/role_prompt.py:68` (миссия developer) ссылается на чтение `{task_ref}/REVIEW.md` «в этом рабочем каталоге» — после перехода на архитектуру A7 (пустой `task_dir` на каждом шаге, `checkpoint.py:283`) этот файл там физически никогда не появляется; текст миссии не актуализирован под пост-A7 модель и может вводить роль-агента в заблуждение независимо от находки R1-F1.
