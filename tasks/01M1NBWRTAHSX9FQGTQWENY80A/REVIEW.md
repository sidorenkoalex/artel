---
task: 01M1NBWRTAHSX9FQGTQWENY80A
type: review
author_role: reviewer
status: changes_requested        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 3    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: Ответы Оператора в брифе ревьювера

## Гейт плана (Фаза A)
Покрытие требований в PLAN.md полное (таблица «Покрытие требований»
закрывает требования 1–5, требование 4 отдельной строкой в шаге 3).
Шаги — проверяемые единицы: шаг 1 (код `review.py`), шаг 2 (правка
вызывающего), шаг 3 (скил), шаг 4 (тесты) — размер MR адекватен,
микроопераций/«сделать всё одним шагом» нет. Подход (свой резолвер
`_answer_rels` вместо переиспользования приватной `brief.
_journal_component`, вставка ANSWER-компонентов как обычных элементов
`parts`) не конфликтует с существующей архитектурой пакета
(`context_package.discipline`, `artifact_part`) — переиспользует её
без особого случая, как и требует AC-4. План проходит.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_answer_rels` перечисляет ВСЕ `ANSWER-n.md` артефактной ветки, не только последний (`orchestrator/review.py:104-120`). |
| 2 | OK | Журналирование — прямой `store.journal(..., "бриф: компонент", f"{rel}: sha256=...")` (`review.py:195-203`), та же форма записи, что `brief._journal_component`; корректно опирается на уточнение ANSWER-1 (T101 не применяется). |
| 3 | OK | ANSWER-компоненты — элементы списка `parts`, переданного в `context_package.discipline` целиком (`review.py:234-240`), не добавлены отдельным довеском после деления. |
| 4 | OK | `skills/review-checklist.md` несёт одну строку в пункте 6 про ANSWER-границы (совпадает текстом с AC-7). |
| 5 | Частично | Тесты покрывают все AC (см. ниже прогон), но 8 новых юнит-тестов в `tests/test_review_package.py` не несут докстринг с заявкой «Ловит мутацию» — см. замечание R1-F1. |

Критерии приёмки:
- AC-1..AC-5 — покрыты приёмочными тестами `tasks/.../acceptance_tests/test_ac1..5*.py`, все зелёные (прогнал каждый файл отдельно).
- AC-6 — обеспечен существующим автогейтом (`test_ac6_full_suite_green.py` — легитимный skip, класс «ci-covered»); полный набор `tests/` прогнан вручную — 1360 тестов, зелёные.
- AC-7 — строка в `skills/review-checklist.md` присутствует и текстуально соответствует формулировке AC-7.

## Замечания

- major — `tests/test_review_package.py:1011-1046` (`AnswerRelsTest`, 4 метода: `test_sorted_by_number_not_by_ls_tree_order`, `test_non_answer_files_under_the_same_dir_are_ignored`, `test_git_failure_yields_no_answers`, `test_no_answer_files_at_all_yields_an_empty_list`) и `tests/test_review_package.py:1087-1130` (`AnswerComponentsInReviewPackageTest`, 4 метода: `test_all_answer_files_are_included_in_ascending_order`, `test_each_answer_gets_its_own_journal_entry_with_its_own_sha256`, `test_existing_package_components_get_no_new_journal_entries`, `test_no_answer_files_leaves_no_journal_entries_and_no_trace`) — ни один из этих 8 новых тестовых методов не несёт докстринг с заявкой `Ловит мутацию: …` (skills/test-authoring.md, «Чувствительность: у теста — заявленная мутация», «каждого тестового метода»); у обоих классов есть только докстринг класса, без единого докстринга метода. Последствие: ревьювер лишён заявленного сценария и наблюдаемого свойства для каждого теста — приходится восстанавливать мутацию по коду задним числом (что я и сделал вручную для проверки: `test_sorted_by_number_not_by_ls_tree_order` ловит перепутанную сортировку по возрастанию/убыванию или текстовую вместо числовой; `test_git_failure_yields_no_answers` ловит пропущенную проверку `returncode`/отсутствие `or []` после `ls_tree_files`; `test_each_answer_gets_its_own_journal_entry_with_its_own_sha256` ловит журналирование одним сводным хэшем на все ANSWER вместо отдельной записи на каждый), но это работа автора теста, а не ревьювера. Контраст: приёмочные тесты этой же задачи (`test_ac1..5*.py`) все 10 методов несут корректную заявку «Ловит мутацию» — конвенция соблюдена там и нарушена только в юнит-тестах `tests/test_review_package.py`. Предложение: добавить каждому из 8 методов докстринг вида «<сценарий>. Ловит мутацию: <конкретная правдоподобная поломка>.» по образцу уже присутствующих докстрингов в `test_ac*.py` этой же задачи.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_review_package.py:1011-1046,1087-1130 | 8 новых тестовых методов (`AnswerRelsTest`, `AnswerComponentsInReviewPackageTest`) без докстринга «Ловит мутацию» | ревью не может сверить тест с заявленной мутацией — конвенция test-authoring.md нарушена системно (все 8 методов) | добавить докстринг с заявкой «Ловит мутацию: …» каждому из 8 методов |

## Вердикт
changes_requested — добавить докстринги «Ловит мутацию: …» ко всем 8 новым методам `AnswerRelsTest`/`AnswerComponentsInReviewPackageTest` в `tests/test_review_package.py` (R1-F1). Остальное — код `review.py`/`role_prompt.py`, `skills/review-checklist.md`, приёмочные тесты, влияние на систему, целостность — без замечаний.

## Проверено исполнением
- `python3 -m unittest discover -s tests` (фоновый прогон) — 1360 тестов, все зелёные (AC-6).
- Каждый `tasks/01M1NBWRTAHSX9FQGTQWENY80A/acceptance_tests/test_ac{1,2,3,4,5}_*.py` запущен отдельно (`python3 <файл> -v`) — все 10 тестов OK, покрывают AC-1..AC-5.
- `python3 scripts/codebase_map.py` (регенерация) сверена с закоммиченной картой: `git diff -- docs/codebase-map.md | grep -v built_at_sha` — расхождений нет кроме строки `built_at_sha` (не дефект, скил review-checklist это явно оговаривает); локальная регенерация отменена (`git checkout -- docs/codebase-map.md`) перед завершением ревью.
- `git diff --stat main...HEAD` сверен построчно со списком «Изменённые файлы» ревью-пакета — полное совпадение, side effects вне заявленных 15 файлов нет.
- Прочитаны вручную: `orchestrator/review.py` (полностью), `orchestrator/artifact_source.py`, `orchestrator/gitcmd.py::ls_tree_files`, `orchestrator/brief.py` (механика `_journal_component`/`component_hash`) — для сверки, что новая журнальная запись в `review.py` использует ту же форму (`"бриф: компонент"`, `sha256_of` по исходному тексту) и что `conn` не используется `artifact_source.resolve` иначе, чем заявлено в PLAN.
- Прочитаны `ANSWER-1.md`/`ANSWER-2.md` из `artifact/01m1nbwrtahsx9fqgtqweny80a` — подтверждают, что мандат на правку `skills/review-checklist.md` (AC-7/требование 4) и трактовка требования 2 (T101 не применяется) в SPEC/PLAN действительно исходят от Оператора, не домыслены разработчиком.

## Предложения системе
(нет)
