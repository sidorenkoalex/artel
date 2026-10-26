---
task: 01M5TBFH5VZ7GSRXX7VNKHFCCQ
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ослабление тестов разрешено: tests/test_report.py

Основание: ночной мандат Оператора 25.10.2026 (дословно: «Даю на ночь: (1) мандат на правку существующих тестов в задачах эпиков и B без ослабления, с матрицей и независимой проверкой»). Объём — ровно шесть методов `tests/test_report.py` из матрицы SPEC: `TileHtmlTest::test_non_escalated_task_has_no_escalation_marker` (:208), `TileHtmlTest::test_escalated_task_names_the_source_step` (:215), `TileHtmlTest::test_title_is_html_escaped` (:225), `BoardHtmlTest::test_known_states_follow_canonical_fsm_order` (:238), `BoardHtmlTest::test_unknown_state_is_appended_sorted_not_dropped` (:250), `BoardHtmlTest::test_no_tasks_reports_empty_board` (:260). Меняется только вход вызова (карточка или модель `board.py` вместо строки БД); все утверждения, их вид и ожидаемые значения прежние. Прочие тесты `report` (в т.ч. `tests/test_report.py:1018`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py:524,550`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py:357`, тесты метки проекта) не меняются. Удаление утверждений, `skip`, ослабление вида — не разрешены.

Независимая проверка: подтверждено после исправления (отдельный агент без контекста сессии, 26.10.2026: шесть методов и их свойства названы полностью, других тестов report вне мандата нет; найденная им непокрытость свойства «запросы к steps не растут с числом задач» внесена строкой «ок при условии» с новым AC; ссылки приведены к определениям методов).

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| tests/test_report.py — `TileHtmlTest::test_non_escalated_task_has_no_escalation_marker` | у неэскалированной задачи нет маркера эскалации — tests/test_report.py:208 | остаётся: плитка из карточки с `escalated_from` | tests/test_report.py:208 | ок при условии: меняется только вход, `assertNotIn` прежний |
| tests/test_report.py — `TileHtmlTest::test_escalated_task_names_the_source_step` | маркер эскалации и её источник — tests/test_report.py:215 | остаётся | tests/test_report.py:215 | ок при условии: оба `assertIn` прежние |
| tests/test_report.py — `TileHtmlTest::test_title_is_html_escaped` | экранирование названия — tests/test_report.py:225 | остаётся | tests/test_report.py:225 | ок при условии: утверждения прежние |
| tests/test_report.py — `BoardHtmlTest::test_known_states_follow_canonical_fsm_order` | канонический порядок состояний — tests/test_report.py:238 | остаётся | tests/test_report.py:238 | ок при условии: `assertLess` прежний |
| tests/test_report.py — `BoardHtmlTest::test_unknown_state_is_appended_sorted_not_dropped` | неизвестное состояние не теряется — tests/test_report.py:250 | остаётся: карточка с неизвестным состоянием остаётся на доске | tests/test_report.py:250 | ок при условии: оба `assertIn` прежние |
| tests/test_report.py — `BoardHtmlTest::test_no_tasks_reports_empty_board` | пустая доска «Задач нет» — tests/test_report.py:260 | остаётся | tests/test_report.py:260 | ок при условии: `assertIn` прежний |
| orchestrator/board.py, report из модели — число запросов к steps | «запросы report к steps не растут с числом задач» — tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py:550 (сейчас держит при прежнем report; tests/test_report.py:1018 зовёт внутренности напрямую) | остаётся только при пакетном чтении журнала в модели; нынешний board.waiting_on → zone_lock.queue_wait читает steps на каждую карточку | не покрыто | ок при условии: SPEC требует (а) build_model для report делает постоянное число запросов к steps (пакетное чтение для waiting_on); (б) новый AC: cmd_report на 2 и на 7 задачах — одинаковое число запросов к steps; (в) cmd_report передаёт build_model своё соединение — один store.db() за прогон (как :524, :550) |
