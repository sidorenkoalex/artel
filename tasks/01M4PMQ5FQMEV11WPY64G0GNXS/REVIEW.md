---
task: 01M4PMQ5FQMEV11WPY64G0GNXS
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Итог прогона и провал внутри subTest — в отчёте suite-run и в перечнях упавших гейтов

## Фаза A — план
- Таблица покрытия полна: требования 1–9 привязаны к шагам; требование 8
  закрыто долгоживущим файлом `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`
  и шагом 3.
- Шаги размера MR (по модулю на шаг, тест, карта), не микрооперации.
- Подход не конфликтует с архитектурой: формат записей не меняется,
  новые функции (`subtest_unit`, `subtest_parents`, `_subtest_progress`,
  `Parsed.rerun` со значением по умолчанию) — аддитивные; вердикт по коду
  выхода (`_full_suite_outcome`) не тронут. «Влияние на систему» совпадает
  с diff (`acceptance.py`, `suite_run.py`, один тест в `tests/test_suite_run.py`,
  карта).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `acceptance.py:165-167` — последнее совпадение `finditer`; без привязки к рамке. AC-1 держит долгоживущий тест. |
| 2 | OK | `_FAILED_LINE` (`acceptance.py:153`), `_SUBFAILED_ENTRY` + слияние в `failed_entries` (`acceptance.py:1413`, `1453-1465`), `_SUBFAILED_PROGRESS` (`suite_run.py:88-91`). Ключ один — `subtest_unit` для обоих источников; на настоящем прогоне без/с xdist подтест считается один раз (проверил исполнением). |
| 3 | OK | `_FAILED_ENTRY`, `_PROGRESS` не тронуты; новая ветка FAILED/ERROR в `_FAILED_LINE` эквивалентна прежней `\S+.*`. AC-10 зелёный. |
| 4 | OK | Единица `<nodeid> <метка>`; сверка «итог pytest: N упавших, разобрано M» в `render` (`suite_run.py:430`). Оговорка про nodeid с пробелом у теста с подтестами — см. «Наблюдения». |
| 5 | OK | Единицы подтестов живут в отдельном словаре `_subtest_progress`, `PASSED <id>` родителя их не перезаписывает. |
| 6 | OK | `_progress` подтестов не видит; AC-4 (счёт по nodeid через `cmd_suite_run --wait 0`) зелёный. |
| 7 | OK | `_full_suite_outcome` не тронут; AC-9 (гейт и `suite-run`) зелёные. |
| 8 | OK | Долгоживущий файл: захваченный вывод обоих видов + настоящий прогон под `-n 2 -p xdist` без skip; мутации из требования покрыты заявками тестов (AC-1, AC-2/3/4 по трём разборам, AC-7 пара vs родитель, AC-4 PASSED родителя). |
| 9 | OK | Раздел SPEC «Меняемое поведение» есть; потребители (`amend.py:551` — `any(rel in line …)`, подстрочная проверка, работает и со строкой `SUBFAILED…`; `plank_run.py:189`; `amend.py:355`; `_suite_metrics`) не правились. |

## Замечания

Блокирующих, major и minor замечаний нет — реестр пуст.

Наблюдение вне реестра (в границах, заданных самим SPEC; не дефект
реализации относительно SPEC): правило SPEC «строка хода с xdist — nodeid
последнее слово строки» и «короткий итог — слово с `::` перед « - »» не
выдерживает nodeid с пробелом в id параметризации у теста с подтестами.
Проверено настоящим pytest (pytest 9.1.1, xdist 3.8.0) на тесте
`@pytest.mark.parametrize("v", ["a b"])` + `subtests.test(msg="q")`:
- с xdist `suite_run.parse` даёт единицу `b] [q] tests/test_e.py::test_sp[a`
  и цель повтора `b]` (`suite_run.py:88-91` → `rerun`, `suite_run.py:363`);
  `failed.json` получит `b]`, и `suite-run --failed` передаст pytest
  несуществующий путь;
- строку короткого итога `SUBFAILED[q] tests/test_e.py::test_sp[a b] - …`
  `_SUBFAILED_ENTRY` (`acceptance.py:1413`) не разбирает вовсе; без xdist
  строку хода `… test_sp[a b] SUBFAILED[q] [100%]` — тоже (там сработает
  честная строка «итог pytest: 5 упавших, разобрано 4»).
Риск назван в PLAN («Риски»), для `tests/` этого репозитория (unittest,
без parametrize) недостижим, поэтому замечанием не оформлен; предложение —
в «Предложения системе».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4PMQ5FQMEV11WPY64G0GNXS`
  — отказ «планки нет: в источнике … нет файлов test_*.py»: все тесты
  задачи — долгоживущие в `tests/`, их прогон ниже.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py tests/test_suite_run.py tests/test_acceptance.py tests/test_full_suite_reuse.py`
  — 57 passed, 26 subtests passed (включая настоящий прогон под `-n 2 -p xdist`).
- Пачка `tests/test_amend*.py tests/test_*plank_run*.py tests/test_*suite_run*.py tests/test_suite_lock*.py`
  одним вызовом не уложилась в 10 минут инструмента — итог не получен,
  в довод не беру; CI коммита f5cfaa58 зелёный (16 проверок).
- Зонд настоящим pytest 9.1.1 во временном каталоге (без xdist и с
  `-n 2 -p xdist`): подтесты `self.subTest()` (метка `(<subtest>)`),
  `subtests.test(msg="m::n")` (метка с `::`), параметризация с пробелом.
  Метки `(<subtest>)` и `[m::n]` разбираются верно в обоих видах вывода и
  в оборванном выводе; подтест с меткой в строке хода и коротком итоге
  считается один раз; `rerun` — nodeid родителей. Случай с пробелом в id —
  см. «Наблюдение» выше.
- `python3 scripts/codebase_map.py` + `git diff docs/codebase-map.md` без
  строки `built_at_sha` — расхождений нет (карта свежая); файл возвращён
  `git checkout`.
- `git diff 4582f129 -- tests/` — только добавление
  `RenderTest::test_summary_mismatch_line_only_when_parsed_fewer`;
  существующие утверждения не менялись. Заявка «`<` → `<=`» наблюдаема:
  на `FINISHED` (2 из 2) строка сверки появится и `assertNotIn` упадёт;
  свойство «строки нет при полном разборе» долгоживущий файл не держит —
  не повтор.

## Предложения системе
- `orchestrator/suite_run.py` (`Parsed.rerun` → `failed.json`): цели
  повтора `--failed` стоит ограничивать строками с `::` (или сверять
  nodeid подтеста из строки хода xdist с nodeid родителя из строки
  `PASSED/FAILED` того же прогона) — тогда обрезанный nodeid с пробелом
  в id параметризации не превратит весь повтор в «file not found». Кандидат
  в бэклог, приоритет низкий.
- Песочница ревьювера не даёт `grep` по site-packages venv пульта — формат
  вывода pytest пришлось проверять зондом с настоящим прогоном; для задач
  про разбор вывода pytest полезно открыть чтение `.artel/venv/…/_pytest/`.
