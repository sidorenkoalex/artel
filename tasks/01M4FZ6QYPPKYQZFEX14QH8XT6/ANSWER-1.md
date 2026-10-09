---
task: 01M4FZ6QYPPKYQZFEX14QH8XT6
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

---
task: 01M4FZ6QYPPKYQZFEX14QH8XT6
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: мандат Оператора на объявленную смену утверждений

## Ответы

Гейт неослабления тестов 09.10 10:32Z отказал переходу `in_dev → verifying`
по 12 методам. Каждый из них назван в разделе «Меняемое поведение» SPEC,
утверждённого Оператором на гейте SPEC 09.10: пара клиент/чат больше не
участвует в выборе наблюдения и не печатается в подсказке, вместо неё
проверяется ID наблюдения. Сессия при Операторе сверила диффы: свойство
каждого метода сторожится и после правки (например, в
`test_ac2_observed_cycle_gets_client_and_chat_unobserved_does_not`
проверка «наблюдение прежнего запуска не приписано живому циклу» идёт
теперь по ID наблюдения вместо клиента и чата).

Ослабление тестов разрешено: tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::LaunchHintTest::test_ac1_shape_launch_line_then_first_steps, tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::LaunchHintTest::test_ac3_active_observation_with_task_gives_its_client_chat_and_watch, tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::LaunchHintTest::test_ac4_disabled_task_suggests_observe_add_before_watch, tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::LaunchHintTest::test_ac5_foreign_stopped_observations_ignored_freshest_chosen, tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::CommandHintEndToEndTest::test_ac9_new_tz_hint_registers_observation, tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::CommandHintEndToEndTest::test_ac9_auto_stopped_by_stop_hints_observe_add, tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py::PinUpdateNamesStaleCyclesTest::test_ac2_observed_cycle_gets_client_and_chat_unobserved_does_not, tests/test_cycle_hint.py::CycleHintTest::test_enabled_observation_wins_over_fresher_one_without_task, tests/test_cycle_hint.py::CycleHintTest::test_task_removed_from_observation_suggests_observe_add, tests/test_cycle_hint.py::CycleHintTest::test_launch_text_continues_caller_prefix_on_one_line, tests/test_observation_edges.py::ObservationEdgesTest::test_two_chats_cannot_be_chosen_implicitly_for_one_task, tests/test_pin_update_stale_cycles.py::CycleCommandTest::test_restart_line_is_built_by_cycle_hint
Основание: решение Оператора 09.10.2026 — раздел «Меняемое поведение» SPEC 01M4FZ6QYPPKYQZFEX14QH8XT6, утверждённого на гейте SPEC 09.10 (инвариант 38); запуск без привязки к чату, выбор наблюдения по ID вместо пары клиент/чат.
