---
task: 01M4NZ5W9ZTKGTW7DGZQGMP2GP
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Наблюдение неослабления — двусторонний прогон каждого изменённого метода и замер расхода test_author (шаг 0)

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–11 разнесены по шагам 1–5.
- Шаги — единицы размера MR (config/sandbox, плагин, наблюдение, отчёт, карта и прогоны).
- Подход совпадает с архитектурой: наблюдение вызывается в `_test_integrity_gate`, а не в `_journal_pass` (Е4); существующий вердикт и запись «пройден» не трогаются. «Влияние на систему» соответствует диффу: 5 файлов кода и карта, вне зон задачи ничего нет, откат — revert.
- PLAN честно называет отступление от буквы требования 1. В коде место утверждения — всегда последний кадр «вне библиотек», без промежуточного шага «последний кадр в файле узла». Требование 1 в скобках само приравнивает случай «помощник другого файла» к ветке «кадра в файле узла нет». На самом деле у такого утверждения кадр вызова помощника в файле узла есть. AC-1 и залоченный тест `test_ac1_outcome_carries_relative_assertion_location` требуют строку помощника, так что реализация следует AC и замыслу SPEC. Расхождение остаётся только для экзотического случая: утверждение, выброшенное кодом под корнем дерева, но не тестом (например, `assert` в `app.py`). Там будет «неприменимо», а не «да»/«нет». Это наблюдение, не вердикт, поэтому не замечание (см. «Предложения системе»).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `two_sided.py` `_PLUGIN_SOURCE::_location`: путь берётся относительно `rootpath` (`--rootdir={tree}` в `_run_side`), stdlib и site/dist-packages отсеиваются. Признак «неприменимо» для другого файла или места вне тела метода даёт `test_integrity._changed_flag`. `refusals`/`results` прежние (AC-1 зелёный); `Outcome.sides` по умолчанию `None`. Отступление от буквы см. в фазе A. |
| 2 | OK | `_observe` стоит после `_journal_pass` и до `if ev.rest is None`. Методы — `ev.cmp.changes` с `base_source != head_source`. Запись: голова, база, адрес, вердикт `ev.outcomes`, `kind`, признаки, длительность, исход, признак и место каждой стороны. |
| 3 | OK | `_changed_lines`: `difflib` по телам методов в номерах строк файла каждой версии. «Новая на базе» сверяется с head, «старая на ветке» — с base. Временной мутацией подтверждено, что AC-4 это ловит (ниже). |
| 4 | OK | Перехват внутри `_observe` и `_observe_methods` (по методу). `two_sided.run` гейта вне перехвата. Повтор на том же sha пропускается по `_observed` (префикс «голова <sha>;»). При сбое git в `_evaluate` поле `cmp` не `None` (`_Evaluation(None, …, cmp)`, `test_integrity.py:1087`), `changes` пуст — `_observe` выходит без исключения. |
| 5 | OK | `TWO_SIDED_PASSED_ACTION` наблюдение не пишет. `merge_gate_escalates`, `uncovered`, `review_lines` не тронуты (AC-8, AC-14 зелёные). |
| 6 | OK | `config.TWO_SIDED_OBSERVATION = True`, `TWO_SIDED_OBSERVATION_LIMIT_SEC = 600`. Таймаут стороны — `_side_timeout(deadline)`; гейт зовёт без `deadline`. Исчерпанный предел — `SIDE_LIMIT` у метода и всех следующих. Канарейка уходит выходом `is_canary` до `_observe`. |
| 7 | OK | `tests/sandbox.py` — одна строка с комментарием рядом с `config.MODELS_LOCAL`. |
| 8 | OK | `test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py` и `test_fsm_advance_gate_smoke.py` не изменены и зелёные. |
| 9 | OK | Покрыто долгоживущими тестами `VerdictUnchangedTest` (сценарии обоих `ac24`, объявленная смена, мандат, отказ и исключение объявленного прогона). |
| 10 | OK | `report._test_author_steps`, `_write_groups`: окно `OPERATOR_WINDOW_DAYS`, префиксы `acceptance` и сегмент `tests/`. Обрезанный путь или отсутствующий файл — «н/д»; провайдер не Claude — «н/д»; git не вызывается. |
| 11 | OK | `OBSERVATION_CLASSES`: «покрыто мандатом» первым (В3), нераспознанный текст — «прочее». |

## Замечания
Замечаний уровня blocker, major или minor нет.

Проверено и замечанием не стало:
- Дифф `tests/` вне долгоживущих файлов задачи — только добавленная строка в `tests/sandbox.py`. Существующих утверждений не меняли и не удаляли; сужения данных нет.
- Сообщение таймаута в `_run_side`: было `({config.TWO_SIDED_PYTEST_TIMEOUT_SEC} с)`, стало `({timeout:g} с)`. Для целого значения 300 текст совпадает.
- Карта кодовой базы свежая: после `scripts/codebase_map.py` содержимое без строки `built_at_sha` не отличается.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: в итерации 1 замечаний не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 …/orchestrator/artel.py plank-run 01M4NZ5W9ZTKGTW7DGZQGMP2GP` — 4 passed, код выхода pytest 0.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py` — 24 passed, 42 subtests passed, 122 с.
- `python3 -m pytest -q -p no:cacheprovider -x tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py tests/test_fsm_advance_gate_smoke.py tests/test_test_integrity_gate.py` — 96 passed, 3 subtests passed (требование 8, флаг выключен песочницей).
- `python3 -m pytest -q -p no:cacheprovider tests/test_report.py tests/test_01m4ag3qyv3e7mn7fava10vdjg_file_time_report.py tests/test_guard_assertion_changes.py tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py` — 104 passed, 20 subtests passed.
- Временная мутация в `_observation_detail`: сторона «старая версия на ветке» сверялась с изменёнными строками head. Прогон `-k ac4` долгоживущего файла дал SUBFAILED `test_hit / старая версия на ветке`, то есть сторож ловит заявленную мутацию. Код возвращён `git checkout`, `git status` чистый.
- `python3 scripts/codebase_map.py` и `git diff -- docs/codebase-map.md` без строки `built_at_sha` — расхождений нет. Файл возвращён `git checkout`.

## Предложения системе
- Замер test_author (`report._write_groups`) при реальной длине путей пульта почти всегда даст «н/д» по файлам и строкам. Префикс рабочей копии `/Users/…/.artel/projects/artel/worktrees/<id>/` занимает 94 знака, поэтому `tests/` заканчивается ровно на 100-м знаке и имя файла отрезается. Каталог документов `…/tasks/<id>/` + `acceptance` — тоже ровно 100. Число Write считается верно, но файлы и строки уйдут в «н/д». Оператору стоит знать об этом, прежде чем опираться на метрику (решение Б4 о необрезанном аргументе).
- Отступление требования 1 от AC-1 (класс «скобка в требовании противоречит критерию»). Требование 1 приравняло «помощник другого файла» к «кадра в файле узла нет», хотя кадр вызова в файле узла есть. Аудит SPEC стоит сверять с тем, как утверждение реально лежит в трассировке.
- Долгоживущий `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py` идёт 122–155 с, это выше порога 60 с: каждый сценарий гоняет настоящий pytest на деревьях. Это нагрузка на CI каждого пуша. Кандидат на разбор скила test-authoring о цене песочницы «настоящий переход».
