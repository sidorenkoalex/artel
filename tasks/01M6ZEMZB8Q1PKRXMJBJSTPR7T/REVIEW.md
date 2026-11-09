---
task: 01M6ZEMZB8Q1PKRXMJBJSTPR7T
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Тёплый байткод интерпретатора в прогонах pytest пульта

## Фаза A — план
- Таблица покрытия требований 1–12 полна. Новый раздел PLAN «Возврат из
  ревью, итерация 1» сопоставляет каждый пункт указания Оператора на гейте
  SPEC с кодом или тестом.
- «Влияние на систему» сходится с инкрементальным diff 76048aa0…8ced9ac4.
  Изменены три файла: `orchestrator/acceptance.py`, докстринг в
  `timeout_integrations.py` (только заявка, утверждения не тронуты) и новый
  `tests/test_acceptance_pycache_guards.py`. Залоченные файлы задачи и
  существующие тесты не правились. Защищённых путей в diff нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | без изменений с итерации 1. Строка при `None` — см. наблюдение 1 |
| 2 | OK | `tests/sandbox.py` не менялся |
| 3 | OK | |
| 4 | OK | |
| 5 | OK | `_helper_run` запускает `[interp, "-", *args]` с `input=script`, без `-I` (указание 1(б)). Удаление идёт через `_remove_tree` (os.walk/os.remove/os.rmdir, указание 1(а)). Если `_pytest` интерпретатора лежит под исключёнными каталогами, `_interpreter_admitted` возвращает молча, сборки и `.failed` нет (указание 6) |
| 6 | OK | |
| 7 | OK | |
| 8 | OK | `_failed_age`: при нечисловом значении, NaN, `inf` или времени в будущем отметка удаляется и возвращается `None` (указание 8(а)). Место, которое не является каталогом (`S_ISDIR` по `lstat`), не доверено (указание 8(в)) |
| 9 | OK | |
| 10 | OK | в argv процессов шаблона нет подстроки `pytest`: тест guards это утверждает, `PytestRunStub` больше не путает запрос с прогоном |
| 11 | OK | залоченный `test_01m3y7g6…_pycache.py` зелёный |
| 12 | свидетельство | решение на приёмке (ANSWER-2, ответ 2) |

## Замечания
Blocker и major нет. Одно minor-наблюдение по тесту вынесено в
«Наблюдения» (пункт 3). Оно касается только формулировки заявки, свойство
кода исполнено.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/acceptance.py:385-404 | запрос и сборка шли через `-c <скрипт>` | — | исправлено: форма `[interp, "-"]` + `input=`. Тест `test_helpers_read_code_from_stdin_without_pytest_in_argv` зелёный и проверяет и `argv[1] == "-"`, и отсутствие подстроки |
| R1-F2 | accepted | orchestrator/acceptance.py:301, :404, :498-499, :547, :604 | `shutil.rmtree` в шагах шаблона | — | исправлено: `_remove_tree` во всех шагах шаблона. `grep rmtree` по шагам шаблона пуст. Оставшиеся `shutil.rmtree` (`_remove_cache_dir` — уборка префикса и HOME прогона, :856-868) — законная уборка прогона |
| R1-F3 | accepted | orchestrator/acceptance.py:607-624, :655-656 | интерпретатор с `_pytest` под исключёнными каталогами давал строку и `.failed` | — | исправлено: `_interpreter_admitted`. Проверено временной мутацией: при `if False and …` тест `test_interpreter_with_pytest_under_excluded_dir_is_silent` красный, код возвращён |
| R1-F4 | accepted | orchestrator/acceptance.py:502-520 | повреждённая `.failed` не удалялась | — | исправлено: удаление и `None`. Оба случая покрывает параметризованный тест |
| R1-F5 | accepted | tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py:142-144 | заявка мутации не была наблюдаема | — | исправлено: заявка переписана на наблюдаемую мутацию (байткод `self.root` в префиксе), утверждения не тронуты |

## Наблюдения для Оператора
1. (с итерации 1, не снято) Указание 8(б) («место `None` — строки нет»)
   расходится с требованием 1 SPEC («…пустым префиксом и строкой о сбое»).
   Код (`acceptance.py:630-631`) следует SPEC и печатает строку. Решение за
   Оператором.
2. (с итерации 1) На приёмке мутацию ANSWER-2 стоит формулировать как
   «байткод `self.root` попадает в префикс». Мутация «весь шаблон без
   фильтра» на этом тесте нейтральна.
3. minor, не заведено в реестр: при 0 blocker/major незакрытая запись
   заблокировала бы `approved` гейтом только из-за текста докстринга.
   `tests/test_acceptance_pycache_guards.py::test_template_steps_never_call_shutil_rmtree`:
   в заявке перечислена мутация «очистка префикса» (`_empty_prefix`), но
   тест её не ловит. Проверено временной мутацией: при `shutil.rmtree` в
   `_empty_prefix` все 5 тестов зелёные. На отбрасывании шаблона префикс
   ещё пуст, и `_empty_prefix` ничего не удаляет. Сам код `_empty_prefix`
   правильный (`_remove_tree`). Чтобы заявка стала честной, достаточно
   убрать из неё «очистку префикса» или добавить сценарий сбоя посреди
   копирования. Это можно сделать попутно в любой следующей правке файла.

## Вердикт
approved. Все пять записей итерации 1 закрыты (`accepted`), blocker и
major нет.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_acceptance_pycache_guards.py tests/test_acceptance_pycache_script.py tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py tests/test_acceptance_pycache.py tests/test_acceptance.py tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py tests/test_01m6zemzb8q1pkrxmjbjstpr7t_template_rules.py`:
  105 passed, 44 subtests passed (34 с).
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6zemzb8q1pkrxmjbjstpr7t_template_runs.py tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`:
  48 passed, 6 subtests passed (238 с).
- Временная мутация `_interpreter_admitted` (проверка снята): красный
  `test_interpreter_with_pytest_under_excluded_dir_is_silent`, код возвращён.
- Временная мутация `_empty_prefix` → `shutil.rmtree`: guards 5 passed
  (наблюдение 3), код возвращён. После обеих мутаций `git status` чист.
- `grep -n rmtree orchestrator/acceptance.py`: в шагах шаблона (строки 290-690)
  вызовов `shutil.rmtree` нет.

## Предложения системе
- Гейт реестра (`approved` только при всех `accepted`) не различает minor:
  ревьюверу приходится выбирать между лишней итерацией ради формулировки
  докстринга и выносом замечания из реестра
  (`orchestrator/fsm_advance.py::review`, skills/review-checklist.md
  «Вердикт» и «Реестр»). Полезен статус для minor, не блокирующий вердикт.
