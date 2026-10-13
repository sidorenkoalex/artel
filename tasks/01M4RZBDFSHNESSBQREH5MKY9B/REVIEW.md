---
task: 01M4RZBDFSHNESSBQREH5MKY9B
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Бриф: шаблон артефакта роли целиком

## Фаза A — план
- Таблица покрытия PLAN полна (требования 1–9 → шаги 1–4); шаги — проверяемые единицы (код брифа, миссии, тесты, карта/прогоны).
- Подход не конфликтует с архитектурой: чтение внутри подменяемых функций брифа (AC-11), штатные `_manifest_component`/`_journal_component`, общий `run_id`, вызов до `context_package.discipline`.
- «Влияние на систему» совпадает с диффом: `orchestrator/brief.py`, `orchestrator/role_prompt.py`, `tests/test_brief.py`, `tests/test_review_package.py` (+1 строка), `docs/codebase-map.md`. Откат — revert merge-коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `brief.ROLE_TEMPLATES` (brief.py ~128): analyst — SPEC.md, QUESTIONS.md; developer — PLAN.md; spec_auditor — SPEC-AUDIT.md; reviewer/test_author нет. Одна таблица. |
| 2 | OK | `_template_components` зовётся последним в `analyst_map_component`, `developer_brief`, `spec_auditor_brief`; `role_prompt.mission_brief_package` структурно не тронут. Первый компонент/запись — прежние (AC-8 долгоживущего файла зелёный). |
| 3 | OK | `gitcmd.show(config.MAIN_BRANCH, rel, repo=config.ROOT)` напрямую; render — `_manifest_component` у developer/spec_auditor, `_journal_component` у analyst; до `discipline` — опись и деление на части общие. |
| 4 | OK | `text is None` → `store.journal(conn, task_id, role, "бриф: шаблон не прочитан", f"{rel}: {reason}")` + пометка вне границы на каждый шаблон; причина схлопнута в одну строку. |
| 5 | OK | Миссии трёх ролей: шаблон «в БРИФЕ РОЛИ ниже», `_template_unread_note()` — диск только при пометке «не прочитан»; имена шаблонов остались. |
| 6 | OK | Долгоживущий `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py` покрывает все мутации списка; свой `TemplateUnreadReasonTest` — только схлопывание причины (не повтор). |
| 7 | OK | Дифф `test_developer_step_has_no_package` — ровно одна строка `+ ["-C", root, "show", "main:templates/PLAN.md"],` между `ls-tree … tasks/<id>` и `["config", "--get", "user.name"]`; `assertEqual` списка сохранён; метод зелёный. Мандат ANSWER-1. |
| 8 | OK | Красных методов вне перечня нет (прогон 26 затронутых модулей ниже — 504 passed); подгонки `tests/sandbox.py` и прочих нет в диффе. |
| 9 | OK | `python3 scripts/codebase_map.py` на дереве ветки даёт расхождение только в строке `built_at_sha` — по скилу не дефект. |

Сверка изменённых утверждений с base: `tests/test_brief.py` — `3 → 4` и `1 → 3` ровно по разделу «Меняемое поведение» (требование 1; в песочнице `BriefUnitTest` шаблон даёт по одной записи — компонент или «не прочитан», `journal_details` считает все записи актора); `tests/test_review_package.py` — одна вставка по мандату ANSWER-1. Удалённых/ослабленных утверждений, сужения фикстур и переноса под условие нет. Докстринги с «Ловит мутацию» у обоих изменённых методов `test_brief.py` и у нового теста есть, заявки наблюдаемы (проверено временной мутацией).

## Замечания
Нет blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Замечаний нет — реестр пуст.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_brief.py tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py "tests/test_review_package.py::CmdRunReviewPackageTest"` — 51 passed, 32 subtests passed.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4RZBDFSHNESSBQREH5MKY9B` — 3 passed, код выхода 0.
- Все 26 модулей `tests/`, ссылающихся на `mission_brief_package`/`developer_brief`/`analyst_map_component`/`spec_auditor_brief` (в т.ч. test_review_package.py, test_agent_prompt.py, test_analyst_role.py, test_invariants.py, долгоживущие role_missions/developer_step/map_projection/note_brief/note_mission/spec_gate_decisions и др.) — 504 passed, 405 subtests passed (4 мин 49 с).
- Временная мутация `orchestrator/brief.py`: убрана строка developer из `ROLE_TEMPLATES` и схлопывание причины — `DeveloperBriefTest::test_assembles_three_components_and_journals_their_hashes` и `TemplateUnreadReasonTest::test_multiline_git_reason_collapses_into_one_note_line` оба красные; код возвращён `git checkout`, дерево чистое.
- `python3 scripts/codebase_map.py` + `git diff docs/codebase-map.md` — отличие только в `built_at_sha`; файл возвращён.
- `git diff 8b104aa3...HEAD -- tests/test_review_package.py` — единственная строка `+ ["-C", root, "show", "main:templates/PLAN.md"],`.

## Предложения системе
- Ревью-пакет: шаблон пакета советует смотреть затронутые модули, но поиск «кто зовёт функцию брифа» по `tests/` даёт 26 файлов и ~5 минут прогона — стоило бы, чтобы пакет сам называл набор модулей затронутых функций (адрес: `orchestrator/review.py`, сборка пакета).
