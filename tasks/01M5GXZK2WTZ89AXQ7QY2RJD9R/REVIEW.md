---
task: 01M5GXZK2WTZ89AXQ7QY2RJD9R
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: G3б-1 — заменяемые тесты в SPEC, строгий режим и amend-tests для файлов с меткой

## Фаза A — план

- Таблица покрытия PLAN полна: требования 1–8 → шаги 1–6. Шаги — единицы
  размера MR (guard; mandate+fsm; tests_writing; amend; тесты AC-21+карта;
  приложения).
- Подход совпадает с архитектурой: раздел — по образцу «Меняемое поведение»
  (`guard.replaced_test_items` в `_content_errors` → одна функция на CLI и
  `spec_writing -> spec_gate`), утверждение — запись журнала, чтение — по
  журналу. Ограничение зон соблюдено: в `fsm.py` правлены только
  `_approve_spec_gate` и новая `_replaced_tests_declaration` рядом с
  `_behavior_change_declaration`; в `tests_writing.py` — только
  `_tests_writing_fail_to_pass_gate` (импорты внутри функции).
- «Влияние на систему» = diff: 7 файлов кода зоны + 2 файла тестов мандата
  ANSWER-1; вне зоны ничего (`git diff --stat` пакета). Откат — revert,
  схема БД не меняется.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `REPLACED_TESTS_SECTION`, `parse_replaced_test_line`, `replaced_test_items` (scripts/guard.py, блок «Заменяемые тесты»); все 7 нарушений называют строку; заглушка/пусто — без ошибок; `is_test_id_form` — тот же `partition`, что `parse_test_id` (AC-2 зелёный). |
| 2 | OK | `fsm._replaced_tests_declaration`: канарейка → ни сверки, ни записи; форма → отказ решения профиля → граница/`skip` → компонент → маски → голова main/файл → `matrix_refusals(..., test_ids=…)`. В `_approve_spec_gate` вызов только при пройденной сверке «Меняемое поведение», обе записи — после обеих сверок, порядок DECLARED → REPLACED; источник текста — тот же `declaration_text`. Отзыв — пустая деталь при прежней записи. `mandate.approved_replacements` читает последнюю запись тем же разбором строки. |
| 3 | OK | `spec_audit.signals` — сигнал сразу после «Меняемое поведение» по `section_body(...).strip()` (заглушка засчитывается). |
| 4 | OK | Сверка сразу после `_spec_anchor_check`, до правила планки; `REPLACEMENT_REFUSAL_ACTION` в `REFUSAL_CLASSES` как `ROLE_FIXES`; деталь — строка на нарушение. |
| 5 | OK | `_BAN_TABLE` + `_table_arguments` (первая пара скобок после литерала), `suite` с меткой — тем же условием, что `describe`, текст `describe`-находки побайтно прежний; `_test_calls` читает имя после `.each\`…\``. Наблюдение (не замечание): `_test_calls` не пропускает пробел между `.each` и `` ` `` и перед `(`, а `_BAN_TABLE` пропускает — расхождение только в консервативную сторону (критерий не засчитан → отказ трассируемости), обхода запретов нет. |
| 6 | OK | `LABELLED_REFUSAL`/`_refuse_labelled` сняты; при правиле не по умолчанию: группа 2 — `_rule_plank_errors` (состав `tests_writing.py:373–389`, без `plank_has_group_lines`), группа 3 — `_labelled_long_lived_errors` (строка группы, признаки, запреты, удаление по `plank_test_names`); `--from-branch` — `_snapshot_plank_files` через общий предикат `guard.is_labelled_plank_test` (его же зовёт `acceptance_test_files`; поведение диска не изменилось — `_rule_plank_files` и так отдаёт только первый уровень owns/is_test). Статика долгоживущих с меткой в `--from-branch` — при каждом вызове с непустым перечнем, прогон — только при расхождении (`static=False`). Правило по умолчанию — прежние вызовы (`_by_rule`). |
| 7 | OK | Оба приложения в PLAN, только добавленные строки; применимость подтверждена планкой AC-22 (зелёная). |
| 8 | OK | Три метода мандата переписаны на проход с сохранением всех случаев (4/2/1); `AMEND_REFUSAL` значения не меняли и употребляются только в `assertNotIn` (labelled_gates.py:1436, fail_to_pass.py:2648); `assert_refused_without_writes` заменён помощником класса `assert_passed`; `LabelledSandbox`/`CarryOverSandbox`/`FailToPassSandbox` и прочие методы не тронуты. |

Сверка изменённых утверждений с base (Фаза B п. 6): все три метода из раздела
«Изменённые утверждения тестов» названы в мандате ANSWER-1 (маркер
«Ослабление тестов разрешено:»), исход рубежа — «покрыто мандатом». Новые
ожидания совпадают с AC-21 поштучно: отказа нет, `tests_locked_sha` сдвинут
и равен голове ветки документов, +1 запись «правка планки»; (б) «удалены:»
с путём и файла нет в дереве лока; (г)/Ac25 — голова кодовой ветки сдвинута,
перечень несёт sha256 правки; `--from-branch` — голова кодовой ветки
прежняя. Условия 1–5 ANSWER-1 соблюдены; свойство «файлы с меткой не обходят
проверки» держат долгоживущие тесты AC-16..AC-19, AC-23 задачи. Сужения
данных под неизменными утверждениями нет (правка — только внутри трёх
методов и помощников класса Ac11).

Долгоживущие свойства — в `tests/` (три файла `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_*.py`,
`Группа: долгоживущий`); заявки «Ловит мутацию» называют наблюдаемое
расхождение (вывод/префикс/четыре величины/запись журнала). Повтора
долгоживущих тестов разработчиком нет — разработчик тестов не добавлял.

## Замечания

Замечаний уровня blocker/major/minor нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт

approved.

## Проверено исполнением

- `python3 orchestrator/artel.py plank-run 01M5GXZK2WTZ89AXQ7QY2RJD9R` — 8 passed, код 0 (AC-15, AC-21, AC-22).
- `python3 -m pytest -q -p no:xdist tests/test_01m5gxzk2wtz89axq7qy2rjd9r_guard_section_bans.py tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py` — 14 passed, 68 subtests passed.
- `python3 -m pytest -q -p no:xdist tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py` — 12 passed, 22 subtests passed.
- `python3 -m pytest -q -p no:xdist tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py::Ac11AmendLabelledRefusalTest tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py::Ac25AmendAndTemplateTest` — 4 passed, 16 subtests passed.
- `grep -n "AMEND_REFUSAL\|assert_refused_without_writes"` по двум файлам мандата — константы на прежних строках 1371/2362, употребление только в `assertNotIn`, старый помощник удалён.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без `built_at_sha` — пусто (карта свежая), рабочая копия возвращена `git checkout`.
- Прочитаны `guard._rule_plank_files` (эквивалентность нового предиката составу диска), `amend._task_profile`/`_profile_or_exit` (профиль `None` при правиле не по умолчанию недостижим: отказ решения — выход раньше), хвост `fsm._approve_spec_gate` (записи после обеих сверок, до `audit_fail`).
- CI коммита d192d330 зелёный (16 проверок, по пакету).

## Предложения системе

- `pytest -n 8` в worktree роли падает «node down: Not properly terminated» для песочниц с настоящим git — долгоживущие тесты пришлось гнать `-p no:xdist`; стоит указать в скиле ревьювера, каким способом гонять долгоживущие файлы задачи (класс: среда шага).
