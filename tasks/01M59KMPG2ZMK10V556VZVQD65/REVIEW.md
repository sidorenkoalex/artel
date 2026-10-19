---
task: 01M59KMPG2ZMK10V556VZVQD65
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: G2а-1 — правило планки компонента

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–12 привязаны к шагам 1–4.
- Шаги размера MR: guard → project_profile → потребители → юнит-тесты и карта.
- Подход не конфликтует с архитектурой. Правило — необязательный параметр `rule` уже вызываемых функций guard. Ветка перехода фильтрует пути методами `rule.owns`/`rule.is_test`; у умолчания остаётся прежний `endswith(".py")`. Поэтому сторож предпроверки не правится (требование 11).
- «Влияние на систему» совпадает с diff: 11 файлов, все в зонах SPEC; защищённые пути не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `guard.PlankComponent`/`PlankRule`/`DEFAULT_PLANK_RULE` (`scripts/guard.py`, блок «Правило планки по компоненту»). `component_of`/`is_test`/`masks` на месте. `ALWAYS_STRAY_PLANK_NAMES` — это `_pult.py`, `PASSPORT.md`, `conftest.py`; вложенный путь — тоже `None`. `.md`/`.txt` — `SHARED_PLANK_FILE`. Помощник — `_<имя>.<расширение маски>`. Сверил по `ACCEPTANCE_TESTS_ALLOWED_TOP_LEVEL` (`scripts/guard.py:2484`): `conftest.py` и `PASSPORT.md` были посторонними и в main. Значит, `DEFAULT_PLANK_RULE.component_of` не меняет поведение чекпоинта и предпроверки артели. |
| 2 | OK | `project_profile.plank_rule`: проверка `is_artel` идёт до чтения записи; `test_profile` получает умолчание; `TargetsError` перехватывается. Отказ `report: pult-vitest` без `tests` проверяется первым, по полю `report`. pytest-команда и компонент без `tests` получают умолчание. `decide` не зовётся, `is_pytest_command` импортируется лениво. `Profile.tests`/`plank_layout` объявлены с `compare=False`. |
| 3 | OK | Сигнатуры прежние, `rule` добавлен только как необязательный параметр. Без правила и при умолчании (`_by_rule` ложно) работает прежняя ветка кода. Области чтения артели закреплены `test_ac15_disk_read_areas_unchanged` и планкой. |
| 4 | OK | `TEST_CALL_HEAD` заякорен на `^[ \t]*`; `.each(…)` с многострочной таблицей; литерал в трёх видах кавычек; `${` отсекается. Пометки — `AC_SLASH_MARKER`. Для пометки с отступом — `INDENTED_SLASH_AC_MARKER_REASON_TMPL`: тот же шаблон, у которого заменён только префикс. Подсказка «нет теста» называет `it('AC-<n>: …')`. |
| 5 | OK | `first_comment`: строки `//` подряд либо один `/* */`. Слово «место» в тексте отказа подставляется параметром. Текст артели прежний (проверено `test_ac15_texts_and_compositions_unchanged`). |
| 6 | OK | `checkpoint._plank_rule` пишет причину отказа в журнал до записи о посторонних файлах. |
| 7 | OK | `fsm._tests_writing_ac_state` (оба пути), `preflight`, `amend` (`_plank_rule_or_exit` в обоих режимах, `_rule_test_files` для маркера красноты). `_test_files`/`_groups`/`acceptance_test_files` не тронуты. |
| 8 | OK | `dry_run` работает по правилу. `_plank_sources(rule=)` тоже. Fail-closed `_plank_rule_refusal` идёт до чтения планки, существующим путём отказа; тексты совпадают со SPEC. В `summary` правило берётся через `_summary_plank_rule`; вызывающий не изменён. |
| 9 | OK | `_task_docs_violations`: `plank_rules = guard_rules or by_rule or refusal`. Структура `.md` проверяется только при `guard_rules`. Путь артели прежний: при умолчании передаётся `rule=None`. |
| 10 | OK | Тексты и составы закреплены долгоживущим `ArtelUnchangedTest`. |
| 11 | OK | `git diff 9da139ee -- tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py` пуст, тесты сторожа зелёные. |
| 12 | OK | Долгоживущий файл задачи (17 методов) и планка (25 тестов) работают без сети и Node. На каждую форму требования 4 есть отдельный subTest. |

Тесты. Заявки «Ловит мутацию» в `tests/test_guard_plank_rule_parsing.py` наблюдаемы. Две из них я проверил временной мутацией (см. ниже), обе поймались. Новый файл не повторяет свойства долгоживущего: счёт сводки, подсказку смешанного правила и скобки в строках `.each` долгоживущий файл не проверяет. Существующие тесты `tests/` в diff не менялись: изменённых или удалённых ассертов нет. Ветвлений под литералы фикстур планки в коде нет.

Наблюдение — не замечание, в реестр не внесено. `_closing_paren` (`scripts/guard.py`, разбор `.each`) пропускает строки, но не комментарии. Если в многострочной таблице `.each` есть `// don't`, апостроф «открывает» строку, вызов не распознаётся, и критерий получает «нет теста». Проверено: `plank_test_names("test.each([\n  [1], // don't\n  [2],\n])('AC-5: x %i', …)")` → `[]`. Ошибка в сторону fail-closed: ложный отказ с понятной подсказкой, ложного покрытия нет. Обход для автора — убрать комментарий из таблицы. Логичнее закрыть в G2б вместе с «одной меткой на тест».

## Замечания

Нет (blocker/major не найдено).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 orchestrator/artel.py plank-run 01M59KMPG2ZMK10V556VZVQD65` — 25 passed за 61.74 с, код выхода pytest 0.
- `python3 -m pytest -q tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py tests/test_guard_plank_rule_parsing.py tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py` — 40 passed, 126 subtests passed.
- `git diff --stat 9da139ee -- tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py` — пусто (AC-14).
- Временная мутация 1: снял якорь `^[ \t]*` у `TEST_CALL_HEAD`. `test_ac3_each_test_form_covers_its_own_criterion` покраснел на формах `foo.it` и `x = test`. Код возвращён (`git checkout scripts/guard.py`).
- Временная мутация 2: убрал пропуск строк в `_closing_paren`. `EachTableStringsTest` покраснел. Код возвращён, `git status` чист.
- Зонд разбора: `plank_test_names` на `it(...)` и `test.concurrent("…")` с отступом даёт оба литерала; `first_comment('/* Красен до реализации: x */ const a = 1;')` маркер находит; случай с апострофом в комментарии таблицы `.each` описан выше.
- `python3 scripts/codebase_map.py` → `git diff --stat docs/codebase-map.md`: одна строка (`built_at_sha`), содержимое карты свежее. Регенерированный файл откачен.

## Предложения системе
- `skills/review-checklist.md`: реестр замечаний при `approved` требует, чтобы каждая запись была `accepted`. Поэтому minor-наблюдение нельзя завести записью, не заблокировав вердикт, и его приходится выносить свободным текстом мимо реестра. Стоит разрешить статус вроде `deferred` для minor без последствий для мержа.
