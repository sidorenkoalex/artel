---
task: T072
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: Evidence-контракт ревью: Проверено исполнением

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Секция «Проверено исполнением» с непустым содержимым описана как обязательная при `status: approved` — реализована структурной проверкой в `scripts/guard.py:335-353` (`review_evidence_errors`), приложена к шаблону диффом для Оператора. |
| 2 | OK | `review_evidence_errors` вызывается из `check_content` (`scripts/guard.py:403-404`) для `atype == "review"`, условие на `status == "approved"` внутри функции (`guard.py:342-343`) — для прочих статусов возвращает `[]`, покрыто `AC-5`/`test_ac5_...` и `test_non_approved_statuses_do_not_require_the_section`. `check_content` — единственный путь проверки REVIEW.md и с диска (`orchestrator/acceptance.py`), и с ветки (`orchestrator/fsm.py::guard_refuses`, `fsm.py:433`) — правка действует в обоих без отдельной правки FSM, подтверждено чтением `fsm.py:420-433,684`. |
| 3 | OK (диффы, не применены) | `templates/REVIEW.md` и `skills/review-checklist.md` — защищённые пути (conventions-core), правка приложена как дифф в блоке «Дифф для Оператора» PLAN.md, не закоммичена в ветку задачи — правильно по конвенции. Оба диффа проверены `git apply --check` против текущего состояния этих файлов на main — применяются чисто. |
| 4 | OK | Два разных текста ошибки: «без секции … — добавь секцию» (`guard.py:346-348`) и «секция … пустая — впиши» (`guard.py:351-352`), оба называют, что класть внутрь (команды/тесты, что показали) — проверено `RejectionMessageNamesWhatIsMissingTest` (AC-4), тест зелёный. |
| 5 | OK | AC-1 — `test_ac1_approved_with_filled_evidence_section_passes` зелёный. |
| 6 | OK | AC-2 — `test_ac2_approved_without_evidence_section_is_rejected` зелёный. |
| 7 | OK | AC-3 — `test_ac3_approved_with_empty_evidence_section_is_rejected` зелёный. |
| 8 | OK | AC-4 — см. требование 4 выше. |
| 9 | OK | AC-5 — `test_ac5_non_approved_statuses_pass_without_evidence_section` перебирает `guard.RULES["review"]["statuses"] - {"approved"}` (draft, changes_requested, escalate), все зелёные. |
| 10 | OK (manual, обоснованно) | AC-6/AC-7 — помечены `manual` в `tasks/T072/acceptance_tests/test_manual_criteria.py` с той же мотивировкой, что и прецедент T046 (коммит 435cf39): `templates/`/`skills/` — защищённые пути, годны к проверке только после применения MR Оператором. Проверил сам: диффы существуют, синтаксически корректны, применяются чисто к текущему `main` (см. «Проверено исполнением»). |
| 11 | OK | AC-8 — полный набор `python3 -m unittest discover -s tests` зелёный (912/912), включая шесть фикстур, дополненных секцией «Проверено исполнением» (`tests/test_advance_guard.py`, `tests/test_auto_cycle.py`, `tests/test_invariants.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_review_freshness.py`, `tests/test_fsm_branch_correct_status_reads.py`) — проверил, что оставшиеся REVIEW-фикстуры с `type: review` (`tests/test_review_package.py`) не задеты, т.к. несут `status: changes_requested`/`draft`, не `approved`. |

## Замечания

- ...

## Вердикт
approved

Дефектов уровня blocker/major не найдено. Реализация точно следует
плану: единая условная проверка в `check_content`, действующая
одинаково на обоих путях чтения REVIEW.md (диск и ветка), два разных
и содержательных текста ошибки для «нет секции» / «секция пустая»,
защищённые файлы не тронуты напрямую — только приложены диффом для
Оператора с тем же прецедентом (T046/435cf39), что и заявлено. Класс
регрессии (approved-фикстуры без секции) закрыт целиком, а не по
одному файлу — подтверждено. AC-6/AC-7 корректно помечены manual по
объективной причине (правка защищённых путей вне прав исполнителя),
не как уклонение от теста.

## Проверено исполнением
- `python3 -m unittest discover -s tests -v` — 912 тестов, все
  зелёные (включая новые/изменённые `tests/test_guard_schema.py`,
  `tests/test_advance_guard.py`, `tests/test_auto_cycle.py`,
  `tests/test_invariants.py`, `tests/test_acceptance_tests_flow.py`,
  `tests/test_review_freshness.py`,
  `tests/test_fsm_branch_correct_status_reads.py`).
- `python3 -m unittest discover -s tasks/T072/acceptance_tests -v` —
  5 тестов, все зелёные (AC-1, AC-2, AC-3, AC-4, AC-5).
- Прочитан полный `scripts/guard.py`, включая `review_evidence_errors`
  (guard.py:335-353) и точку вызова в `check_content`
  (guard.py:403-404) — подтверждено чтением кода, что проверка
  условна на `atype == "review" and status == "approved"`, не задевает
  `RULES["review"]["sections"]` (безусловный список).
- Прочитан `orchestrator/fsm.py:420-433,684` — подтверждено, что
  `guard_refuses` вызывает `guard.check_content`, т.е. новая проверка
  действует и на пути «чужой чекаут ветки», не только с диска.
- `grep -n "check_content|guard.check" orchestrator/*.py` — других
  мест вызова guard на REVIEW.md, кроме `fsm.py`, не найдено.
- `grep -rl "type: review" --include="*.py" .` — сверил все файлы со
  `status: approved` в REVIEW-фикстурах; вне списка из PLAN
  (`tests/test_review_package.py`) approved-фикстур типа review не
  оказалось (там только `changes_requested`/`draft`).
- Оба диффа из блока «Дифф для Оператора» (`templates/REVIEW.md`,
  `skills/review-checklist.md`) сохранены во временные файлы и
  прогнаны через `git apply --check` против текущего рабочего дерева
  — применяются чисто, без конфликтов контекста.
- Сверено, что `git diff --stat main...task/t072-evidence-kontrakt-revyu-prover`
  не касается `templates/`, `skills/`, `.github/`, `gates.yaml`,
  `roles.yaml` — защищённые пути не нарушены.

## Предложения системе
