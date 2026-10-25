---
task: 01M5S6M2MZV68QH9QHWY0XP0YA
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Vitest 4 под пультом — флаг кэша, хуки и класс ошибки в отчётчике, итоговая строка, номер повтора

## Подход
Четыре независимых правки в границах «Ограничения зон по смыслу»
(ANSWER-1, решение 1); проверяет их долгоживущий файл
`tests/test_01m5s6m2mzv68qh9qhwy0xp0ya_vitest4.py` (64 теста, не правится).

- Флаг кэша: `VITEST_VERSION_FLAGS[4] = VitestFlags("--no-cache", True,
  "<проба 2.2 …>")`; `_vitest_head` добавляет `flags.cache_flag` одним
  аргументом и больше не заводит `_pult_dir(profile, "cache") / "vitest"`.
- Отчётчик: функции `hookFailed` (`"fail"`/`"run"`), `errorName`
  (`constructor` `Function<Имя>` кроме `Error`/`anonymous`, иначе `name`),
  `ownErrors`, поиск предка с ошибкой `.only` и предка с упавшим
  `beforeAll`/`afterAll` и непустым `errors()`; модуль с упавшим хуком
  верхнего уровня и тестами — без записи уровня файла. Приоритет: `.only`
  (д) → собственные ошибки → хук набора (б) → прежняя запись; `hook` только
  у `fail` (е2).
- `_VITEST_COUNTS`: `expected fail` в списке счётчиков.
- Номер повтора: общий помощник `_numbered_tail(name)` в
  `project_profile.py` (условие `parse_test_id`); `test_id` при `n is None`
  дописывает `#1`. В `advance_gates/acceptance.py` помощник
  `is_repeat(where)` (`n is not None and n >= 2`) рядом с
  `record_location`; его зовут `not_passed_kind` и сбор `repeats`.
- Мандатная правка `tests/test_report_outcome_module.py:1487`:
  `startswith("--cacheDir=")` → `== "--no-cache"` (ANSWER-1).

Три строки таблицы требования 2 выведены из правил, а не наблюдены на
Vitest 4.1.5 (ANSWER-1, решение 2): «честный провал `expect` в наборе с
упавшим `afterAll`», «`beforeAll` внешнего набора, тест во вложенном»,
«тест в `describe.only`» — отчётчик проверяют поддельные объекты по ним.

## Шаги
1. `project_profile.py`: запись таблицы, документация `VitestFlags` и
   комментарий таблицы; `_numbered_tail`, `test_id` с `#1`, `parse_test_id`
   через помощник.
2. `acceptance.py::_vitest_head`: флаг без каталога.
3. `agent_log.py::_VITEST_COUNTS`.
4. `advance_gates/acceptance.py::is_repeat` + `not_passed_kind`;
   `advance_gates/tests_writing.py` — сбор `repeats` через `is_repeat`.
5. `reporters/pult_vitest_reporter.js` — правила а)–е2), заголовок (з).
6. Мандатная правка теста; прогон долгоживущего файла и затронутых модулей;
   карта `scripts/codebase_map.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 5 |
| 3 | 3 |
| 4 | 1, 4 |
| 5 | 6 (файл test_author) |
| 6 | 6 |

## Влияние на систему
- Отказы `_vitest_head` (версия вне таблицы, без `requireAssertions`,
  `command` против базы) не трогаются; AC-3 держит тексты.
- `test_id` меняет вид идентификатора только у имён на `#<цифры>` без `n`
  — теперь `parse_test_id` возвращает их имя целиком (раньше отрезал хвост
  номером). Потребители `parse_test_id` (`two_sided`, `mutation_run`,
  `record_location`) получают верное имя; `_Ids` не меняется.
- Гейты: повтор теперь от `#2`; `#1` раньше в идентификаторах не
  встречался (`_Ids` первое вхождение не нумеровал), так что для прежних
  имён находки не меняются.
- Тест `test_report_outcome_module.py::test_vitest_component_with_workdir_gets_exact_pult_argv`
  — правка строже (равенство), по мандату ANSWER-1.
- Откат — revert merge-коммита.

Проверено в шаге: `tests/test_01m5s6m2mzv68qh9qhwy0xp0ya_vitest4.py` —
64 passed; 22 файла `tests/` по затронутым символам (vitest, `test_id`,
`not_passed_kind`, `vitest_summaries`, гейты планки, мандатный файл
`test_report_outcome_module.py`) — 427 passed, 582 subtests passed.
Карта перестроена `scripts/codebase_map.py`.

## Риски
- Реальный Vitest 4 может отличаться от поддельных объектов в трёх
  выведенных строках таблицы; расхождение — эскалация (ANSWER-1, п. 2).

## Предложения системе
- `plank-run` отказывает «планки нет» у задачи только с долгоживущими
  файлами (записка test_author) — команде пульта стоит уметь гонять их.
