---
task: 01M5S6M2MZV68QH9QHWY0XP0YA
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Vitest 4 под пультом — флаг кэша, хуки и класс ошибки в отчётчике, итоговая строка, номер повтора

## Фаза A: план
- Таблица покрытия полна: требования 1–6 → шаги 1–6; шаги размера MR.
- Подход в границах «Ограничения зон по смыслу» (ANSWER-1, решение 1): diff трогает ровно названные места
  (`VITEST_VERSION_FLAGS`/`VitestFlags`/`_numbered_tail`/`test_id`/`parse_test_id`, `_vitest_head`,
  `_VITEST_COUNTS`, `is_repeat` рядом с `record_location`, сбор `repeats`, отчётчик, мандатный тест).
- Три выведенные строки таблицы помечены в PLAN (ANSWER-1, решение 2). «Влияние на систему» совпадает с diff; откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `project_profile.py`: `VitestFlags("--no-cache", True, "<проба…>")`, форма класса прежняя, документация и комментарий таблицы обновлены; `acceptance.py:_vitest_head` → `[*base, flag, flags.cache_flag]`, `mkdir` каталога кэша удалён; отказы и их тексты не тронуты (AC-3 зелёный). |
| 2а | OK | `failedHook(node, names)`: `"fail"`/`"run"`, порядок `TEST_HOOKS` = `beforeEach`, `afterEach`. |
| 2б/в | OK | `clean` = `passed`/`skipped` без своих ошибок, `declared` не `skip`/`todo`, нет `ownHook` → `suiteHookFailure` по `ancestors` до модуля включительно, хук + непустой `errors()`. Честный провал идёт по своим ошибкам. |
| 2г | OK | `errorName`: собственное поле `constructor` (`hasOwnProperty` — не ловит унаследованный `Object` у JSON), `Function<Имя>` кроме `Error`/`anonymous`, иначе `name`, иначе `null`; одно правило для теста, хука, уровня файла. |
| 2д | OK | `onlyErrors` — свои ошибки, затем предки; приоритет над хуком набора (ANSWER-1, решение 8); `hook` остаётся `null`. |
| 2е/е2 | OK | `moduleErrorRecord(mod, root, hasTests)` не пишет запись уровня файла при упавшем хуке модуля и наличии тестов; `hook` выставляется только при `entry.state === "fail"`. |
| 2ж/з | OK | Форма записи и путь вывода прежние (AC-9 зелёный); заголовок файла перечисляет а)–е2). |
| 3 | OK | `expected fail` в обеих частях ряда `_VITEST_COUNTS`; прочие регулярные выражения не тронуты. |
| 4 | OK | `_numbered_tail` — общее условие; `test_id` при `n is None` дописывает `#1`; `parse_test_id` прежний по поведению; `_Ids` не тронут; `is_repeat` (`n >= 2`) зовут `not_passed_kind` и сбор `repeats`. Других мест вида `where[3] is not None` в `orchestrator/` нет (grep). |
| 5 | OK | Долгоживущий файл test_author, 64 теста; в `tests/` разработчик повторов не добавил. |
| 6 | OK | Правится только `test_vitest_component_with_workdir_gets_exact_pult_argv:1487` (`startswith("--cacheDir=")` → `== "--no-cache"`) — ровно мандат ANSWER-1, утверждение строже; других изменений `tests/` в diff нет. |

## Замечания
Нет замечаний уровня blocker/major/minor.

Проверено и замечанием не стало:
- Тест-модуль с упавшим `beforeAll` верхнего уровня, где все тесты — явный `it.skip`: записи уровня файла нет, и тесты остаются `skip`, то есть ошибка хука не попадёт в отчёт. На настоящем Vitest `beforeAll` при полностью пропущенном файле не исполняется, поэтому сценарий не воспроизводится — не дефект.
- Смена вида идентификатора у имён на `#<цифры>` (`x #12` → `x #12#1`) уже сохранённых идентификаторов: заявлено в PLAN «Влияние на систему». Идентификаторы базы и ветки строит один и тот же код, расхождения нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -p no:cacheprovider -q tests/test_01m5s6m2mzv68qh9qhwy0xp0ya_vitest4.py tests/test_report_outcome_module.py` → 105 passed (долгоживущий файл задачи под настоящим `node` + мандатный файл).
- 14 файлов `tests/` по затронутым символам (`test_id`, `not_passed_kind`, `vitest_summaries`, `pult_vitest`, `VITEST_VERSION_FLAGS`): `test_01m58fnwbv25ff26e7az9q9912_components`, `test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout`, `test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass`, `test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates`, `test_01m5edw6kd1escevrsv2wpnxap_file_level`, `test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer`, `test_01m5jgsaanr1nzyqd4fcsve48y_mandate_components`, `test_mandate_test_id`, `test_outcome_gate_module`, `test_outcome_components_module`, `test_project_components`, `test_pytest_own_result_ids`, `test_vitest_summary_pump`, `test_id_format_guard` → 259 passed, 407 subtests passed.
- Временная мутация отчётчика (`ancestors` обрывается после непосредственного родителя + признак падения хука только `"fail"`): `-k "ac5 or ac6 or ac8"` → 8 failed, в том числе `test_ac8_only_error_marks_mode_only_up_the_chain`. Код возвращён `git checkout --`, `git status` чистый.
- `grep -rn "where\[3\]" orchestrator` → единственное место — `is_repeat`.
- `plank-run` не запускался: у задачи нет планки `acceptance_tests/`, только долгоживущий файл (см. PLAN).

## Предложения системе
- `plank-run` для задачи только с долгоживущими файлами нечего гонять — это уже отметил PLAN; ревьюверу полезна команда пульта «прогнать долгоживущие файлы задачи» (повторяю наблюдение независимо).
