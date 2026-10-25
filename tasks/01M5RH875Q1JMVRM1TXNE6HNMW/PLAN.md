---
task: 01M5RH875Q1JMVRM1TXNE6HNMW
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Сведение тестов, волна 2а-2б — песочницы гейта исходов по компонентам, тесты `outcome_components` в стиле pytest, пути стенда в докстринге `outcome_prior`

## Подход

Свод механический и сверяется по AST планочными помощниками
(`acceptance_tests/_plan.py`): песочницы переносятся вырезкой строк
исходного файла дословно, тесты — функциями с заменами требования 17,
доказательство неослабления — один набор из 29 патчей мутаций против
старого файла («до», `--ref base`) и нового модуля («после», `--ref
worktree`) при неизменном дереве `orchestrator/`.

- `tests/components_outcome_sandbox.py` — докстринг одной строкой и
  строки 30–56 (импорты, константы до `COUNTS`), 59–235
  (`ContextRunnerProc`, `ComponentsOutcomeSandbox`), 554–576
  (`FAIL_TO_PASS_ACTION`, `FOREIGN`, `ForeignPlankSandbox`) исходного
  файла без единой правки.
- `tests/test_outcome_components_module.py` — фикстуры `box`
  (`ComponentsOutcomeSandbox`) и `foreign_box` (`ForeignPlankSandbox`),
  помощники `review_section`, `mandate_answer`, `broken_consumer` —
  функции модуля, 17 тестовых функций с теми же именами в том же порядке.
- Докстринг `outcome_prior` — замена двух путей на месте (строки 7–8),
  разбивка строк прежняя.
- Исходный файл удалён `git rm`; карта регенерирована
  `python3 scripts/codebase_map.py`.

Бюджет SPEC ($40) не пересматривается: файлов и шагов столько, сколько
оценивал SPEC.

## Шаги

1. Перенос песочниц, свод 17 тестов, правка докстринга `outcome_prior`,
   удаление исходного файла, карта. Проверка: сверка AST (раздел «Сверка
   по AST»), `python3 -m pytest tests/test_outcome_components_module.py`
   — 17 passed за 40,22 с, `pytest --collect-only` `outcome_prior` — 44
   теста.
2. Патчи `mutation-001.diff` … `mutation-029.diff` по заявкам (раздел
   «Мутации и заявки»).
3. Таблица «до» (раздел «Мутации до»).
4. Таблица «после» теми же диапазонами (раздел «Мутации после»),
   соответствие строк падения (раздел «Строки падения до → после»).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 3 |
| 3 | 3, 4 |
| 4 | 3, 4 (раздел «Находки») |
| 5 | 3, 4 |
| 6 | 3 (перепрогон части 16-29 после правки патчей 025/026) |
| 7 | 3, 4 (контроль зелёный во всех прогонах) |
| 8 | 3, 4 (`--wait-lock 4`, замок взят сразу) |
| 9 | 1–4 (раздел «Влияние на систему») |
| 10 | 1 |
| 11 | 1 |
| 12 | 1 |
| 13 | 1 |
| 14 | 1 |
| 15 | 1 |
| 16 | 1 |
| 17 | 1 |
| 18 | 1, 3 (раздел «Удалённые дубли») |
| 19 | 1 |
| 20 | 4 |
| 21 | 4 |
| 22 | 1, 3, 4 |
| 23 | 1 |
| 24 | 1 |
| 25 | вне роли (сессия при Операторе) |

## Соответствие имён «до → после»

Каждый тест перенесён функцией с тем же именем; стенд — `box` у бывших
`Ac16`, `Ac17`, `Ac18`, `Ac22`, `Ac13Ac14`, `foreign_box` у бывших `Ac19`,
`Ac25`, `Ac27`.

| Исходный тест | Функция |
|---|---|
| `Ac16DiffComponentsTest::test_ac23_seed_change_runs_both_components` | `tests/test_outcome_components_module.py::test_ac23_seed_change_runs_both_components` |
| `Ac16DiffComponentsTest::test_ac16_component_change_runs_only_its_component` | `tests/test_outcome_components_module.py::test_ac16_component_change_runs_only_its_component` |
| `Ac16DiffComponentsTest::test_ac16_diff_read_failure_refuses_preparation` | `tests/test_outcome_components_module.py::test_ac16_diff_read_failure_refuses_preparation` |
| `Ac17PerComponentTest::test_ac17_first_refusal_names_component` | `tests/test_outcome_components_module.py::test_ac17_first_refusal_names_component` |
| `Ac17PerComponentTest::test_ac17_out_of_bounds_component_line` | `tests/test_outcome_components_module.py::test_ac17_out_of_bounds_component_line` |
| `Ac17PerComponentTest::test_ac17_all_out_of_bounds_skip_record_and_review_lines` | `tests/test_outcome_components_module.py::test_ac17_all_out_of_bounds_skip_record_and_review_lines` |
| `Ac18ReviewLinesTest::test_ac18_package_shows_consumer_records` | `tests/test_outcome_components_module.py::test_ac18_package_shows_consumer_records` |
| `Ac18ReviewLinesTest::test_ac18_out_of_bounds_task_shows_consumer_lines` | `tests/test_outcome_components_module.py::test_ac18_out_of_bounds_task_shows_consumer_lines` |
| `Ac22FrontendTaskTest::test_ac22_tests_writing_exit_by_frontend_rule` | `tests/test_outcome_components_module.py::test_ac22_tests_writing_exit_by_frontend_rule` |
| `Ac22FrontendTaskTest::test_ac22_in_dev_outcome_gate_by_frontend` | `tests/test_outcome_components_module.py::test_ac22_in_dev_outcome_gate_by_frontend` |
| `Ac22FrontendTaskTest::test_ac22_merge_gate_outcome_by_frontend` | `tests/test_outcome_components_module.py::test_ac22_merge_gate_outcome_by_frontend` |
| `Ac13Ac14GateMandateTest::test_ac13_path_mandate_on_consumer_lifts_finding` | `tests/test_outcome_components_module.py::test_ac13_path_mandate_on_consumer_lifts_finding` |
| `Ac13Ac14GateMandateTest::test_ac14_id_mandate_on_consumer_lifts_finding` | `tests/test_outcome_components_module.py::test_ac14_id_mandate_on_consumer_lifts_finding` |
| `Ac19ForeignPlankTest::test_ac19_foreign_file_in_bounds_refused` | `tests/test_outcome_components_module.py::test_ac19_foreign_file_in_bounds_refused` |
| `Ac19ForeignPlankTest::test_ac19_task_out_of_bounds_still_refused` | `tests/test_outcome_components_module.py::test_ac19_task_out_of_bounds_still_refused` |
| `Ac25TrainingProjectTest::test_ac25_backend_file_on_frontend_task` | `tests/test_outcome_components_module.py::test_ac25_backend_file_on_frontend_task` |
| `Ac27OutOfBoundsForeignTest::test_ac27_foreign_out_of_bounds_not_checked` | `tests/test_outcome_components_module.py::test_ac27_foreign_out_of_bounds_not_checked` |

Помощники: `Ac18ReviewLinesTest.review_section` → `review_section(box, t)`,
`Ac13Ac14GateMandateTest.mandate_answer` → `mandate_answer(box, t, …)`,
`Ac13Ac14GateMandateTest.broken_consumer` → `broken_consumer(box)`.

Переименованных локальных имён нет: ни одно локальное имя исходных тестов
не совпало с функцией или фикстурой модуля и с фикстурами
`tests/fixtures.py` (`tmp_dir`, `tmp_root`, `initialized_tmp_root`,
`real_git`, `origin_real_git`, `light_transition`).

Заявка `test_ac19_task_out_of_bounds_still_refused` переписана по
требованию 19 SPEC в формулировке решения Оператора ANSWER-1 п. 3
(отказ даёт `_tests_writing_foreign_plank_gate`, не гейт FAIL_TO_PASS у
`in_outcome_bounds(profile)`): «гейт планки чужого компонента добавляется
только по профилю задачи в границе — под `if in_outcome_bounds(profile)`
вместо прежнего (`fsm_advance.tests_writing`, добавление
`_tests_writing_foreign_plank_gate` без условия)». Прочие заявки и
докстринги — дословно.

## Сверка по AST

Сверка — помощниками планки `_plan.py` на базе ad3608c6 против рабочей
копии (тот же код, что у планки):

- `sandbox_statements(старый файл)` против операторов
  `tests/components_outcome_sandbox.py` без докстринга: 24 оператора, все
  24 `ast.dump` равны, порядок тот же; классы `ContextRunnerProc`,
  `ComponentsOutcomeSandbox`, `ForeignPlankSandbox` — дамп равен.
- Тела 17 тестовых функций: `actual_test_body(функция) ==
  expected_test_body(метод, стенд)` — равны у всех 17; присваивания
  атрибутам стенда (`box.no_marker = True`, `box.no_marker = False`,
  `box.git_fail = …`, `box.git_fail = None`, `box.cases[…] = …`) — та же
  последовательность, что у `self.…` метода.
- Помощники `mandate_answer`, `review_section`, `broken_consumer`:
  `actual_helper_body == expected_helper_body(метод, "box")` и сигнатура
  равна дословной из требования 15 — у всех трёх.
- `outcome_prior`: `ast.dump` модуля без докстринга равен базе; изменены
  только строки 7–8 докстринга.

## Мутации и заявки

Номера — в порядке тестов исходного файла; патч меняет одну функцию
`orchestrator/…`. «Строка падения» — файл:строка упавшего утверждения из
лога прогона патча (`<id>-mutation-run-<n>-p<nnn>.log`): «до» — прогон
№1 или №3, «после» — №4 или №5.

### mutation-001 — гейт берёт только компонент задачи

- Заявка: `Ac16DiffComponentsTest::test_ac23_seed_change_runs_both_components`, альтернатива «гейт берёт только компонент задачи (`for_task`)».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_components_gate` — профили гейта — `(for_task_target(target, task_id, conn).profile,)` вместо `component_profiles(select_components(диффа))`.
- Случайность: исход зависит только от компонента задачи (`backend`, литерал сценария) и состава прогонов Vitest; случайные имена файлов и тестов и числа тестов на множество сторон раннера не влияют — Vitest не гоняется при любом зерне.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:262 → после tests/test_outcome_components_module.py:89.

### mutation-002 — выбор компонентов без потребителей `depends_on`

- Заявка: `Ac16DiffComponentsTest::test_ac23_seed_change_runs_both_components`, альтернатива «`select_components` без потребителей `depends_on`».
- Правка: `orchestrator/project_profile.py::_touches` — без регулярных выражений `paths` поставщиков `depends_on` вида `paths`/`files`.
- Случайность: дифф сценария — `backend/seed/data.py` и метка стороны `app.py` (литералы), выбор не зависит от случайных имён и чисел тестов; выживание одинаково при любом зерне (раздел «Находки»).
- Строка падения: нет — не убита ни «до», ни «после».

### mutation-003 — все компоненты без выбора по диффу

- Заявка: `Ac16DiffComponentsTest::test_ac16_component_change_runs_only_its_component`, альтернатива «гейт гоняет все компоненты записи без выбора по диффу».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_components_gate` — `profiles = component_profiles(target)`.
- Случайность: прогон pytest у задачи на `frontend` с правкой `frontend/src/App.jsx` появляется при любых случайных именах и числах тестов — проверяется пустота списка прогонов, не их содержимое.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:290 → после tests/test_outcome_components_module.py:118.

### mutation-004 — профиль гейта — первый компонент записи

- Заявка: `Ac16DiffComponentsTest::test_ac16_component_change_runs_only_its_component`, альтернатива «профиль гейта — `backend` (первый компонент записи)».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_components_gate` — `profiles = component_profiles(target)[:1]`.
- Случайность: порядок компонентов записи — литерал песочницы (`backend`, затем `frontend`), случайные имена и числа тестов в выбор не входят; прогоны pytest есть при любом зерне.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:290 → после tests/test_outcome_components_module.py:118.

### mutation-005 — сбой чтения диффа — пустой набор путей

- Заявка: `Ac16DiffComponentsTest::test_ac16_diff_read_failure_refuses_preparation`, альтернатива «сбой чтения диффа даёт пустой набор путей — гейт гоняет „все компоненты“».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_components_gate` — при `diff_names(...) is None` — `paths = []` вместо отказа подготовки.
- Случайность: отказ git вызовам `diff` из кадров гейта не зависит от имён и чисел тестов; ядро `_gate` каждого компонента само читает дифф и даёт тот же отказ «— подготовка» при любом зерне (раздел «Находки»).
- Строка падения: нет — не убита ни «до», ни «после».

### mutation-006 — сбой чтения диффа — гейт молча проходит

- Заявка: `Ac16DiffComponentsTest::test_ac16_diff_read_failure_refuses_preparation`, альтернатива «либо молча проходит».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_components_gate` — при `diff_names(...) is None` — `return None`.
- Случайность: записи «— подготовка» нет при любых случайных именах и числах тестов — гейт выходит до выбора компонентов.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:310 → после tests/test_outcome_components_module.py:139.

### mutation-007 — отказ без префикса компонента

- Заявка: `Ac17PerComponentTest::test_ac17_first_refusal_names_component`, альтернатива «без префикса компонента в детали».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_components_gate` — `return refusal` вместо `refusal._replace(detail=f"компонент {…}: …")`.
- Случайность: деталь отказа начинается со строки находки, а не с литерала «компонент frontend: », при любом выборе `broken` и любых именах.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:336 → после tests/test_outcome_components_module.py:164.

### mutation-008 — порядок компонентов не по записи

- Заявка: `Ac17PerComponentTest::test_ac17_first_refusal_names_component`, альтернатива «порядок не по записи — `frontend` первым, у `backend` записи нет».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_components_gate` — `for profile in reversed(inside)`.
- Случайность: `frontend` со сломанным `broken` отказывает первым при любом выборе `broken` (сломан всегда один тест `frontend`), запись `backend` не пишется — число записей 0 от зерна не зависит.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:340 → после tests/test_outcome_components_module.py:167.

### mutation-009 — компонент вне границы молча опущен

- Заявка: `Ac17PerComponentTest::test_ac17_out_of_bounds_component_line`, альтернатива «компонент вне границы молча опущен — строки нет».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_components_gate` — `_gate(..., extra=())` вместо `extra=outside`.
- Случайность: строка «компонент backend: вне границы гейта исходов» — литерал с именем компонента, от случайных имён и чисел тестов не зависит.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:357 → после tests/test_outcome_components_module.py:185.

### mutation-010 — компонент вне границы прогоняется ядром

- Заявка: `Ac17PerComponentTest::test_ac17_out_of_bounds_component_line`, альтернатива «компонент вне границы прогоняется ядром — прогоны pytest».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_components_gate` — `inside = list(profiles)`.
- Случайность: при обоих компонентах вне границы гейт пишет запись пройденного гейта вместо пропуска при любых случайных именах и числах тестов; заявивший тест её не ловит (раздел «Находки»).
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:371 → после tests/test_outcome_components_module.py:200 (утверждение бывшего соседнего теста `test_ac17_all_out_of_bounds_skip_record_and_review_lines`).

### mutation-011 — пропуск без записи

- Заявка: `Ac17PerComponentTest::test_ac17_all_out_of_bounds_skip_record_and_review_lines`, альтернатива «пропуск без записи (молча)».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_components_gate` — без `project_profile.journal_skip(...)`.
- Случайность: число записей пропуска 0 при любом зерне — оба компонента вне границы заданы литералом сценария.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:373 → после tests/test_outcome_components_module.py:202.

### mutation-012 — деталь пропуска без головы

- Заявка: `Ac17PerComponentTest::test_ac17_all_out_of_bounds_skip_record_and_review_lines`, альтернатива «деталь записи без головы».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_components_gate` — `skip="\n".join([*outside])`.
- Случайность: строки «голова <sha>» нет при любом sha и любых случайных именах — проверяется её наличие, не значение.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:376 → после tests/test_outcome_components_module.py:205.

### mutation-013 — деталь пропуска без строк компонентов

- Заявка: `Ac17PerComponentTest::test_ac17_all_out_of_bounds_skip_record_and_review_lines`, альтернатива «деталь записи без строк компонентов».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_components_gate` — `skip` только со строкой головы.
- Случайность: строки «компонент backend/frontend: вне границы…» — литералы имён компонентов, от зерна не зависят.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:378 → после tests/test_outcome_components_module.py:207.

### mutation-014 — `review_lines` не читает запись пропуска

- Заявка: `Ac17PerComponentTest::test_ac17_all_out_of_bounds_skip_record_and_review_lines`, альтернатива «`review_lines` не читает запись пропуска — только „не исполнялся“».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_components_review_lines` — без цикла по записям пропуска.
- Случайность: строки «гейт исходов: компонент …: вне границы…» нет при любом зерне — их источник только запись пропуска.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:382 → после tests/test_outcome_components_module.py:211.

### mutation-015 — `review_lines` — только последняя запись головы

- Заявка: `Ac18ReviewLinesTest::test_ac18_package_shows_consumer_records`, альтернатива «`review_lines` берёт только последнюю запись головы — строки `backend` пропадают».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_components_review_lines` — `list(latest.values())[-1:]`.
- Случайность: число тестов базы `frontend` по построению `training` всегда больше числа `backend` (n_front = n_back + 1…3, оба меньше 10), поэтому «тестов базы n_back;» не встречается в строках `frontend` ни при каком зерне.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:411 → после tests/test_outcome_components_module.py:240.

### mutation-016 — пакет фильтрует строки по профилю задачи

- Заявка: `Ac18ReviewLinesTest::test_ac18_package_shows_consumer_records`, альтернатива «пакет фильтрует строки по профилю задачи — строк `frontend` нет».
- Правка: `orchestrator/review.py::_outcome_gate_lines` — у записи из нескольких компонентов строки только записей головы с ключом профиля задачи (`acceptance.report_suite_result_key` по дереву головы).
- Случайность: ключ записи `frontend` с ключом профиля `backend` не совпадает ни при каком зерне (разные команды раннера), строка «тестов базы n_front;» в пакете не появляется.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:414 → после tests/test_outcome_components_module.py:243.

### mutation-017 — строки пакета по границе профиля задачи

- Заявка: `Ac18ReviewLinesTest::test_ac18_out_of_bounds_task_shows_consumer_lines`, альтернатива «строки отфильтрованы по границе профиля задачи».
- Правка: `orchestrator/review.py::_outcome_gate_lines` — `None` при профиле задачи вне границы без исключения записи из нескольких компонентов.
- Случайность: `backend` без `report` вне границы задан литералом сценария; строк гейта в пакете нет при любых случайных именах и числах тестов.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:428 → после tests/test_outcome_components_module.py:258.

### mutation-018 — выход из `tests_writing` на `decide(target)`

- Заявка: `Ac22FrontendTaskTest::test_ac22_tests_writing_exit_by_frontend_rule`, альтернатива «выход на `decide(target)`».
- Правка: `orchestrator/fsm_advance.py::tests_writing` — `decision = project_profile.decide(target)`.
- Случайность: `decide` записи из двух компонентов отказывает всегда, от случайных имён проекта и тестов не зависит.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:444 → после tests/test_outcome_components_module.py:273.

### mutation-019 — гейт исходов `in_dev` на `decide(target)`

- Заявка: `Ac22FrontendTaskTest::test_ac22_in_dev_outcome_gate_by_frontend`, альтернатива «`_bounds` на `decide(target)`».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_outcome_integrity_gate` — без ветки записи из нескольких компонентов: граница — `_bounds(decide(target))`.
- Случайность: `decide` записи из двух компонентов — отказ при любом зерне, гейта и записей нет.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:459 → после tests/test_outcome_components_module.py:289.

### mutation-020 — профиль мержа на `decide(target)`

- Заявка: `Ac22FrontendTaskTest::test_ac22_merge_gate_outcome_by_frontend`, альтернатива «`_profile_refusal_exit` на `decide(target)`».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_merge_profile_refusal_exit` — `decision = project_profile.decide(target)`.
- Случайность: отказ «merge отклонён: профиль тестов проекта» даёт `decide` записи из двух компонентов при любом зерне.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:476 → после tests/test_outcome_components_module.py:307.

### mutation-021 — гейт исходов мержа молчит

- Заявка: `Ac22FrontendTaskTest::test_ac22_merge_gate_outcome_by_frontend`, альтернатива «гейт исходов мержа молчит».
- Правка: `orchestrator/advance_gates/outcome_integrity.py::merge_gate_escalates` — у записи из нескольких компонентов `return False` после проверки профиля.
- Случайность: записей «гейт исходов…» в окне мержа нет при любых случайных именах и числах тестов.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:479 → после tests/test_outcome_components_module.py:310.

### mutation-022 — мандат по области компонента задачи

- Заявка: `Ac13Ac14GateMandateTest::test_ac13_path_mandate_on_consumer_lifts_finding`, альтернатива «мандат проверяется по области компонента задачи — `answer` отказывает».
- Правка: `orchestrator/advance_gates/mandate.py::_weakening_scope_refusal` — без областей других компонентов записи в границе (`_record_outcome_profiles`).
- Случайность: путь `frontend/src/<случайное>.test.jsx` вне `^backend/` и `backend/tests/**` при любом случайном имени файла — `answer` отказывает всегда; выбор `broken` в отказ не входит.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:505 → после tests/test_outcome_components_module.py:334 (утверждение исхода `mandate_answer`).

### mutation-023 — мандат не покрывает находку другого компонента

- Заявки: `Ac13Ac14GateMandateTest::test_ac13_path_mandate_on_consumer_lifts_finding` (альтернатива «находка другого компонента не покрывается мандатом — отказ „сломан правкой“ на рубеже») и `Ac13Ac14GateMandateTest::test_ac14_id_mandate_on_consumer_lifts_finding` (альтернатива «находка остаётся непокрытой») — одинаковы по смыслу, одна мутация.
- Правка: `orchestrator/advance_gates/outcome_integrity.py::_judge` — мандаты ANSWER читаются, только если компонент гейта — компонент задачи (`for_task`).
- Случайность: находка «сломан правкой» — у одного случайного `broken` компонента `frontend` при любом зерне; без мандата она остаётся непокрытой независимо от `broken` и `other`.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:530 → после tests/test_outcome_components_module.py:361; у второго теста — до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:548 → после tests/test_outcome_components_module.py:380.

### mutation-024 — компонент идентификатора сверяется с профилем задачи

- Заявка: `Ac13Ac14GateMandateTest::test_ac14_id_mandate_on_consumer_lifts_finding`, альтернатива «компонент идентификатора сверяется с профилем задачи — отказ „компонента «frontend» нет в записи components:“».
- Правка: `orchestrator/advance_gates/mandate.py::_test_id_refusal` — без ветки записи из нескольких компонентов (`_record_test_id_refusal`).
- Случайность: компонент идентификатора — литерал `frontend`, профиль задачи — `backend`; отказ при любых случайных `broken`, `other` и именах.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:505 → после tests/test_outcome_components_module.py:334 (утверждение исхода `mandate_answer`).

### mutation-025 — файл чужого компонента молча пропущен

- Заявка: `Ac19ForeignPlankTest::test_ac19_foreign_file_in_bounds_refused`, альтернатива «файл, чьего компонента нет среди профилей гейта (профиль задачи один), молча пропущен — переход проходит в `in_dev`». Адрес заявки (`criterion_files`) устарел: файл без компонента `criterion_files` пропускает и на базе, отказ даёт `_tests_writing_foreign_plank_gate` (ANSWER-1 п. 3) — патч воплощает наблюдаемую мутацию там.
- Правка: `orchestrator/advance_gates/tests_writing.py::_tests_writing_foreign_plank_gate` — отказ только файлу компонента задачи (`comp == profile.component and …`), т. е. файл чужого компонента пропускается.
- Случайность: имя файла планки и номер критерия случайны, но компонент файла по правилу планки — литерал (`backend`), отказа нет при любом зерне.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:591 → после tests/test_outcome_components_module.py:399.

### mutation-026 — гейт планки чужого компонента только в границе задачи

- Заявка: `Ac19ForeignPlankTest::test_ac19_task_out_of_bounds_still_refused`, альтернатива ANSWER-1 п. 3 — `_tests_writing_foreign_plank_gate` под `if in_outcome_bounds(profile)`.
- Правка: `orchestrator/fsm_advance.py::tests_writing` — гейт добавляется в список только при `in_outcome_bounds(profile)` вместо добавления без условия.
- Случайность: задача на `backend` без `report` вне границы задана литералом сценария; гейта нет и отказа нет при любых случайных именах файла и критерия.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:606 → после tests/test_outcome_components_module.py:417.

### mutation-027 — компоненты в тексте отказа перепутаны

- Заявка: `Ac25TrainingProjectTest::test_ac25_backend_file_on_frontend_task`, альтернатива «компоненты в тексте отказа перепутаны местами».
- Правка: `orchestrator/advance_gates/tests_writing.py::_tests_writing_foreign_plank_gate` — «компонента {profile.component}, задача — компонента {comp}».
- Случайность: компоненты — литералы `backend`/`frontend`, имя файла случайно, но подставляется в ожидание тем же значением — исход от зерна не зависит.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:625 → после tests/test_outcome_components_module.py:437.

### mutation-028 — отказ без имени файла

- Заявка: `Ac25TrainingProjectTest::test_ac25_backend_file_on_frontend_task`, альтернатива «отказ без имени файла».
- Правка: `orchestrator/advance_gates/tests_writing.py::_tests_writing_foreign_plank_gate` — «файл планки — компонента …» без `{path.name}`.
- Случайность: ожидание несёт случайное имя файла, деталь — нет ни при каком зерне.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:625 → после tests/test_outcome_components_module.py:437.

### mutation-029 — отказ без условия границы чужого компонента

- Заявка: `Ac27OutOfBoundsForeignTest::test_ac27_foreign_out_of_bounds_not_checked`, альтернатива «отказ дан любому файлу чужого компонента без условия границы».
- Правка: `orchestrator/advance_gates/tests_writing.py::_tests_writing_foreign_plank_gate` — `if True:` вместо `if in_outcome_bounds(owners.get(comp)):`.
- Случайность: `backend` без `report` вне границы — литерал сценария; отказ при любых случайных именах.
- Строка падения: до tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:642 → после tests/test_outcome_components_module.py:455.

## Строки падения до → после

Каждая убитая мутация «после» убита функцией, в которую перенесён её
убийца «до», и тем же утверждением (соответствие требования 17); строки —
из логов прогонов патчей (раздел «Мутации и заявки», строка «Строка
падения»). Строки «до» прочих убийц «до» (кроме заявившего теста) и их
пары «после» совпадают по тому же соответствию: 257→84, 258→85, 262→89,
266→93, 290→118, 291→119, 310→139, 332→160, 336→164, 340→167, 355→183,
357→185, 371→200, 373→202, 376→205, 378→207, 382→211, 411→240, 414→243,
428→258, 444→273, 459→289, 476→307, 479→310, 505→334, 530→361, 548→380,
591→399, 593→401, 606→417, 608→419, 624→436, 625→437, 642→455, 647→460,
648→461 (старый файл → `tests/test_outcome_components_module.py`).

## Находки

- mutation-002 (`select_components` без потребителей `depends_on`) не убита никем ни «до», ни «после»: правка сценария коммитится с меткой стороны `app.py`, путь вне компонентов даёт по `select_components` все компоненты, и потребитель `frontend` выбирается и без `depends_on`. Тест `Ac16DiffComponentsTest::test_ac23_seed_change_runs_both_components` не удалён — его альтернативу «только компонент задачи» убивает mutation-001.
- mutation-005 (сбой диффа → пустой набор путей → все компоненты) не убита никем: ядро `_gate` каждого компонента само читает дифф (`_name_status`) под тем же отказом git и даёт ту же запись «— подготовка». Тест `Ac16DiffComponentsTest::test_ac16_diff_read_failure_refuses_preparation` не удалён — альтернативу «молча проходит» убивает mutation-006.
- mutation-010 (компонент вне границы прогоняется ядром) заявивший тест не ловит: при `backend` без `report` его прогон не идёт полным прогоном стороны base/head, запись проходит; мутацию убивает бывший соседний тест «оба компонента вне границы» (запись пройденного гейта вместо пропуска). Тест не удалён — его альтернативу «строки нет» убивает mutation-009.
- Тестов без мутации, убиваемой при любом зерне, нет; мутаций с исходом «ошибка сбора, импорта или setup», «итог неизвестен», «патч не применяется», «патч трогает тесты», «не прогнана» или «оборвана по пределу» в последних строках нет.

## Удалённые дубли

Нет: все 17 тестов перенесены.

## Мутации до

Рабочих процессов — `auto` (умолчание узла прогона, `--workers` не
задавался); части: `--patches 1-15` (№1) и `--patches 16-29` (№2, №3).
Прогон №2 устарел: патчи 025 и 026 в нём не воплощали заявку (025
отказывал и файлу компонента задачи, 026 снимал гейт целиком вместо
условия `in_outcome_bounds`), оба переписаны и часть 16-29 прогнана
заново целиком (№3); исходы мутаций 16–24 и 27–29 в №2 и №3 совпали,
строки №2 для 25 и 26 относятся к прежним патчам (другие sha256).
Контрольные прогоны «до» (без патча): №1 — 17 passed in 11.17 с, №3 — 17
passed in 12.18 с. Замок брался сразу, `--wait-lock` не ждал.

```
# mutation-run №1 задачи 01M5RH875Q1JMVRM1TXNE6HNMW
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py
# рабочих процессов: auto
# патч 1 mutation-001.diff sha256 f21a3a36c8854face62eba332bbdfcfce4dd3011f252b4547a29121638a1d956
# патч 2 mutation-002.diff sha256 dfd7788ee55f5fff8ab64c84b4f6088602233fae6c8dc90da565de7e6126d8aa
# патч 3 mutation-003.diff sha256 eaec24e4b9625e140c150c4623bfb169173fc5f640c0966674be9f6782fc353e
# патч 4 mutation-004.diff sha256 a1537c4836ad806277ceb70cc3435f77c41b853bdaeb94c33aaba543993ee545
# патч 5 mutation-005.diff sha256 7dab14fe24615085fa76ba0a21dec4cf2808b865df54ca90ecc25abecf70a53f
# патч 6 mutation-006.diff sha256 b4d24d98def714bd41f72798846d32664f99ea6a464501e0c0e471c3bee07523
# патч 7 mutation-007.diff sha256 cc53ea97cec57ed771380b3e59f603f559306b654f0381b6848741b14aababfc
# патч 8 mutation-008.diff sha256 0eea811e321c34e68e5b87dfb7c1bbd37e521aa54bb800db9902eb5f387dd5cb
# патч 9 mutation-009.diff sha256 123e343aac2d8a069caa0baca1a7113d6f9e474dd0cbc105aebe78c8f7c0892d
# патч 10 mutation-010.diff sha256 68ca5e64717bca75668b3540dd128e580c7299f45026e93b45064b3970d6cfd1
# патч 11 mutation-011.diff sha256 4fd203d709f6a6f259499853fb96d7ceffd8fc2ba5bb2aa1257192de3ee678b8
# патч 12 mutation-012.diff sha256 41e9967bd35c62a966cbd9ae0abc4bd849ab6e8bd2ec9af55e82bd28e2384615
# патч 13 mutation-013.diff sha256 e447589c8221d68927199c0b4aa442f33f375ecee9fb699d80c8637ce1cc91b9
# патч 14 mutation-014.diff sha256 8502c6a509fee627463e5cd4fe648f92df3789cfe215ccf22a8866397bdd4ad0
# патч 15 mutation-015.diff sha256 bc9fe26fb11cfa2a9ac56e362a77685ffe68b59482b11a7fe521253c9af529ec
номер	исход	узлы
1	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac23_seed_change_runs_both_components,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_first_refusal_names_component,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_out_of_bounds_component_line,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_all_out_of_bounds_skip_record_and_review_lines,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_out_of_bounds_task_shows_consumer_lines,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_package_shows_consumer_records
2	не убита	
3	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac16_component_change_runs_only_its_component
4	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac23_seed_change_runs_both_components,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_out_of_bounds_component_line,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_package_shows_consumer_records,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_out_of_bounds_task_shows_consumer_lines,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_first_refusal_names_component,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_all_out_of_bounds_skip_record_and_review_lines,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac16_component_change_runs_only_its_component
5	не убита	
6	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac16_diff_read_failure_refuses_preparation
7	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_first_refusal_names_component
8	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_first_refusal_names_component,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac23_seed_change_runs_both_components
9	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_out_of_bounds_component_line
10	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_all_out_of_bounds_skip_record_and_review_lines
11	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_all_out_of_bounds_skip_record_and_review_lines
12	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_all_out_of_bounds_skip_record_and_review_lines
13	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_all_out_of_bounds_skip_record_and_review_lines
14	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_all_out_of_bounds_skip_record_and_review_lines
15	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_package_shows_consumer_records
```

```
# mutation-run №2 задачи 01M5RH875Q1JMVRM1TXNE6HNMW
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py
# рабочих процессов: auto
# патч 16 mutation-016.diff sha256 d4462902789d50acac7049bb240751f0cf153299f78f495690756ef9d97deef4
# патч 17 mutation-017.diff sha256 d364987d5093b624d6757c9f25ba498353a250ddb067d5f26ff15e5c080ddffa
# патч 18 mutation-018.diff sha256 91202daafdc4c257b877cf33f11edc3a6a9423e5fa41d64cd9b6cdd8dd98ada3
# патч 19 mutation-019.diff sha256 86ffdae74390a2a36f71b418b378e3890b42e3e9868eb7f6ebc2b0f7411ef652
# патч 20 mutation-020.diff sha256 49ab4835093e99345429abecfe9a2309b44b5a906f5815a0896eb80e32ebc96a
# патч 21 mutation-021.diff sha256 729421f23d6625dc94d584cbbfdc2ec18d2c0c77a1a3eb5a6d7ff2ed86100b5f
# патч 22 mutation-022.diff sha256 284a68839b4e86b709bd3090334454003489f6685cb92b1536147775e5ca5579
# патч 23 mutation-023.diff sha256 90078ba88f9e68f9a5ccbe6a3647223ee3c42fab1cd81f2ab1448b6fc5039778
# патч 24 mutation-024.diff sha256 7c3b643cac49df7b12f7bc941c274b1c55304961a4a086582b73a0cb6dbfb081
# патч 25 mutation-025.diff sha256 e1855f05b2142589d55a3d52312dbf53314c0d761101ffcc3917a46209604ffb
# патч 26 mutation-026.diff sha256 c76cae3158848136ffca82ed154cb4e2c59e1cb1761df71dd7df50e66383485c
# патч 27 mutation-027.diff sha256 2929cea62c3088fbeefd9dad8c4dad99617d6e52d29195547970ad3ddee6f6c3
# патч 28 mutation-028.diff sha256 27d11c230b821c8fe62b8b814383614dff262194eacaec88c9d253046279f1db
# патч 29 mutation-029.diff sha256 3bb2392faac355e3e8813e40bd444a4275d136ee3e37ec1ee9850d8db5b1ce30
номер	исход	узлы
16	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_out_of_bounds_task_shows_consumer_lines,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_package_shows_consumer_records
17	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_out_of_bounds_task_shows_consumer_lines
18	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac13Ac14GateMandateTest::test_ac14_id_mandate_on_consumer_lifts_finding,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac22FrontendTaskTest::test_ac22_merge_gate_outcome_by_frontend,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_first_refusal_names_component,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_out_of_bounds_component_line,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac16_component_change_runs_only_its_component,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_package_shows_consumer_records,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac22FrontendTaskTest::test_ac22_in_dev_outcome_gate_by_frontend,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac16_diff_read_failure_refuses_preparation,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac23_seed_change_runs_both_components,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_all_out_of_bounds_skip_record_and_review_lines,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_foreign_file_in_bounds_refused,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_out_of_bounds_task_shows_consumer_lines,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac13Ac14GateMandateTest::test_ac13_path_mandate_on_consumer_lifts_finding,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac22FrontendTaskTest::test_ac22_tests_writing_exit_by_frontend_rule,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac25TrainingProjectTest::test_ac25_backend_file_on_frontend_task,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac27OutOfBoundsForeignTest::test_ac27_foreign_out_of_bounds_not_checked,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_task_out_of_bounds_still_refused
19	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_out_of_bounds_component_line,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_first_refusal_names_component,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_out_of_bounds_task_shows_consumer_lines,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac23_seed_change_runs_both_components,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_package_shows_consumer_records,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_all_out_of_bounds_skip_record_and_review_lines,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac16_diff_read_failure_refuses_preparation,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac16_component_change_runs_only_its_component,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac22FrontendTaskTest::test_ac22_in_dev_outcome_gate_by_frontend
20	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac22FrontendTaskTest::test_ac22_merge_gate_outcome_by_frontend
21	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac22FrontendTaskTest::test_ac22_merge_gate_outcome_by_frontend
22	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac13Ac14GateMandateTest::test_ac13_path_mandate_on_consumer_lifts_finding
23	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac13Ac14GateMandateTest::test_ac14_id_mandate_on_consumer_lifts_finding,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac13Ac14GateMandateTest::test_ac13_path_mandate_on_consumer_lifts_finding
24	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac13Ac14GateMandateTest::test_ac14_id_mandate_on_consumer_lifts_finding
25	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac22FrontendTaskTest::test_ac22_tests_writing_exit_by_frontend_rule,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac13Ac14GateMandateTest::test_ac13_path_mandate_on_consumer_lifts_finding,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac16_component_change_runs_only_its_component,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_package_shows_consumer_records,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac22FrontendTaskTest::test_ac22_merge_gate_outcome_by_frontend,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac13Ac14GateMandateTest::test_ac14_id_mandate_on_consumer_lifts_finding,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac22FrontendTaskTest::test_ac22_in_dev_outcome_gate_by_frontend,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac23_seed_change_runs_both_components,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_foreign_file_in_bounds_refused,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_first_refusal_names_component,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac16_diff_read_failure_refuses_preparation,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac27OutOfBoundsForeignTest::test_ac27_foreign_out_of_bounds_not_checked,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac25TrainingProjectTest::test_ac25_backend_file_on_frontend_task,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_task_out_of_bounds_still_refused
26	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_foreign_file_in_bounds_refused,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac25TrainingProjectTest::test_ac25_backend_file_on_frontend_task,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_task_out_of_bounds_still_refused,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac27OutOfBoundsForeignTest::test_ac27_foreign_out_of_bounds_not_checked
27	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_foreign_file_in_bounds_refused,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac25TrainingProjectTest::test_ac25_backend_file_on_frontend_task,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_task_out_of_bounds_still_refused,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac27OutOfBoundsForeignTest::test_ac27_foreign_out_of_bounds_not_checked
28	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_foreign_file_in_bounds_refused,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac25TrainingProjectTest::test_ac25_backend_file_on_frontend_task,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_task_out_of_bounds_still_refused,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac27OutOfBoundsForeignTest::test_ac27_foreign_out_of_bounds_not_checked
29	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac27OutOfBoundsForeignTest::test_ac27_foreign_out_of_bounds_not_checked
```

```
# mutation-run №3 задачи 01M5RH875Q1JMVRM1TXNE6HNMW
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py
# рабочих процессов: auto
# патч 16 mutation-016.diff sha256 d4462902789d50acac7049bb240751f0cf153299f78f495690756ef9d97deef4
# патч 17 mutation-017.diff sha256 d364987d5093b624d6757c9f25ba498353a250ddb067d5f26ff15e5c080ddffa
# патч 18 mutation-018.diff sha256 91202daafdc4c257b877cf33f11edc3a6a9423e5fa41d64cd9b6cdd8dd98ada3
# патч 19 mutation-019.diff sha256 86ffdae74390a2a36f71b418b378e3890b42e3e9868eb7f6ebc2b0f7411ef652
# патч 20 mutation-020.diff sha256 49ab4835093e99345429abecfe9a2309b44b5a906f5815a0896eb80e32ebc96a
# патч 21 mutation-021.diff sha256 729421f23d6625dc94d584cbbfdc2ec18d2c0c77a1a3eb5a6d7ff2ed86100b5f
# патч 22 mutation-022.diff sha256 284a68839b4e86b709bd3090334454003489f6685cb92b1536147775e5ca5579
# патч 23 mutation-023.diff sha256 90078ba88f9e68f9a5ccbe6a3647223ee3c42fab1cd81f2ab1448b6fc5039778
# патч 24 mutation-024.diff sha256 7c3b643cac49df7b12f7bc941c274b1c55304961a4a086582b73a0cb6dbfb081
# патч 25 mutation-025.diff sha256 14b2fcea8e0a36b06ba6e888d22370700a8574a878ddceeddf0aa60d9a88919f
# патч 26 mutation-026.diff sha256 e1df9c28eb3a1f27241f6bf7b9dcd34571ff68a3739f7fcc50107ce873090d2e
# патч 27 mutation-027.diff sha256 2929cea62c3088fbeefd9dad8c4dad99617d6e52d29195547970ad3ddee6f6c3
# патч 28 mutation-028.diff sha256 27d11c230b821c8fe62b8b814383614dff262194eacaec88c9d253046279f1db
# патч 29 mutation-029.diff sha256 3bb2392faac355e3e8813e40bd444a4275d136ee3e37ec1ee9850d8db5b1ce30
номер	исход	узлы
16	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_out_of_bounds_task_shows_consumer_lines,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_package_shows_consumer_records
17	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_out_of_bounds_task_shows_consumer_lines
18	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_foreign_file_in_bounds_refused,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_all_out_of_bounds_skip_record_and_review_lines,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_first_refusal_names_component,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_out_of_bounds_component_line,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac22FrontendTaskTest::test_ac22_in_dev_outcome_gate_by_frontend,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_out_of_bounds_task_shows_consumer_lines,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac16_diff_read_failure_refuses_preparation,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_package_shows_consumer_records,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac16_component_change_runs_only_its_component,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac23_seed_change_runs_both_components,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac22FrontendTaskTest::test_ac22_merge_gate_outcome_by_frontend,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac13Ac14GateMandateTest::test_ac14_id_mandate_on_consumer_lifts_finding,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac22FrontendTaskTest::test_ac22_tests_writing_exit_by_frontend_rule,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac13Ac14GateMandateTest::test_ac13_path_mandate_on_consumer_lifts_finding,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac27OutOfBoundsForeignTest::test_ac27_foreign_out_of_bounds_not_checked,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac25TrainingProjectTest::test_ac25_backend_file_on_frontend_task,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_task_out_of_bounds_still_refused
19	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_out_of_bounds_task_shows_consumer_lines,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_all_out_of_bounds_skip_record_and_review_lines,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_out_of_bounds_component_line,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac18ReviewLinesTest::test_ac18_package_shows_consumer_records,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac23_seed_change_runs_both_components,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac22FrontendTaskTest::test_ac22_in_dev_outcome_gate_by_frontend,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac16_diff_read_failure_refuses_preparation,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac17PerComponentTest::test_ac17_first_refusal_names_component,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac16DiffComponentsTest::test_ac16_component_change_runs_only_its_component
20	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac22FrontendTaskTest::test_ac22_merge_gate_outcome_by_frontend
21	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac22FrontendTaskTest::test_ac22_merge_gate_outcome_by_frontend
22	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac13Ac14GateMandateTest::test_ac13_path_mandate_on_consumer_lifts_finding
23	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac13Ac14GateMandateTest::test_ac14_id_mandate_on_consumer_lifts_finding,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac13Ac14GateMandateTest::test_ac13_path_mandate_on_consumer_lifts_finding
24	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac13Ac14GateMandateTest::test_ac14_id_mandate_on_consumer_lifts_finding
25	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_foreign_file_in_bounds_refused,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac25TrainingProjectTest::test_ac25_backend_file_on_frontend_task,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_task_out_of_bounds_still_refused,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac27OutOfBoundsForeignTest::test_ac27_foreign_out_of_bounds_not_checked
26	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_task_out_of_bounds_still_refused
27	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_foreign_file_in_bounds_refused,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac25TrainingProjectTest::test_ac25_backend_file_on_frontend_task,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_task_out_of_bounds_still_refused,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac27OutOfBoundsForeignTest::test_ac27_foreign_out_of_bounds_not_checked
28	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_foreign_file_in_bounds_refused,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac25TrainingProjectTest::test_ac25_backend_file_on_frontend_task,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac19ForeignPlankTest::test_ac19_task_out_of_bounds_still_refused,tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac27OutOfBoundsForeignTest::test_ac27_foreign_out_of_bounds_not_checked
29	убита	tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py::Ac27OutOfBoundsForeignTest::test_ac27_foreign_out_of_bounds_not_checked
```

## Мутации после

Те же части и рабочие процессы `auto`, `--ref worktree` (рабочая копия с
незакоммиченным сводом поверх ad3608c6, дерево `orchestrator/` то же, что
у базы); sha256 каждого патча — как в шапках «до» (№1, №3).

Перед частью 1-15:

```
$ git status --porcelain -- orchestrator/
(вывод пуст)
```

```
# mutation-run №4 задачи 01M5RH875Q1JMVRM1TXNE6HNMW
# источник патчей: каталог на диске
# ревизия прогона: worktree ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_outcome_components_module.py
# рабочих процессов: auto
# патч 1 mutation-001.diff sha256 f21a3a36c8854face62eba332bbdfcfce4dd3011f252b4547a29121638a1d956
# патч 2 mutation-002.diff sha256 dfd7788ee55f5fff8ab64c84b4f6088602233fae6c8dc90da565de7e6126d8aa
# патч 3 mutation-003.diff sha256 eaec24e4b9625e140c150c4623bfb169173fc5f640c0966674be9f6782fc353e
# патч 4 mutation-004.diff sha256 a1537c4836ad806277ceb70cc3435f77c41b853bdaeb94c33aaba543993ee545
# патч 5 mutation-005.diff sha256 7dab14fe24615085fa76ba0a21dec4cf2808b865df54ca90ecc25abecf70a53f
# патч 6 mutation-006.diff sha256 b4d24d98def714bd41f72798846d32664f99ea6a464501e0c0e471c3bee07523
# патч 7 mutation-007.diff sha256 cc53ea97cec57ed771380b3e59f603f559306b654f0381b6848741b14aababfc
# патч 8 mutation-008.diff sha256 0eea811e321c34e68e5b87dfb7c1bbd37e521aa54bb800db9902eb5f387dd5cb
# патч 9 mutation-009.diff sha256 123e343aac2d8a069caa0baca1a7113d6f9e474dd0cbc105aebe78c8f7c0892d
# патч 10 mutation-010.diff sha256 68ca5e64717bca75668b3540dd128e580c7299f45026e93b45064b3970d6cfd1
# патч 11 mutation-011.diff sha256 4fd203d709f6a6f259499853fb96d7ceffd8fc2ba5bb2aa1257192de3ee678b8
# патч 12 mutation-012.diff sha256 41e9967bd35c62a966cbd9ae0abc4bd849ab6e8bd2ec9af55e82bd28e2384615
# патч 13 mutation-013.diff sha256 e447589c8221d68927199c0b4aa442f33f375ecee9fb699d80c8637ce1cc91b9
# патч 14 mutation-014.diff sha256 8502c6a509fee627463e5cd4fe648f92df3789cfe215ccf22a8866397bdd4ad0
# патч 15 mutation-015.diff sha256 bc9fe26fb11cfa2a9ac56e362a77685ffe68b59482b11a7fe521253c9af529ec
номер	исход	узлы
1	убита	tests/test_outcome_components_module.py::test_ac18_package_shows_consumer_records,tests/test_outcome_components_module.py::test_ac17_out_of_bounds_component_line,tests/test_outcome_components_module.py::test_ac17_first_refusal_names_component,tests/test_outcome_components_module.py::test_ac18_out_of_bounds_task_shows_consumer_lines,tests/test_outcome_components_module.py::test_ac23_seed_change_runs_both_components,tests/test_outcome_components_module.py::test_ac17_all_out_of_bounds_skip_record_and_review_lines
2	не убита	
3	убита	tests/test_outcome_components_module.py::test_ac16_component_change_runs_only_its_component
4	убита	tests/test_outcome_components_module.py::test_ac17_first_refusal_names_component,tests/test_outcome_components_module.py::test_ac23_seed_change_runs_both_components,tests/test_outcome_components_module.py::test_ac16_component_change_runs_only_its_component,tests/test_outcome_components_module.py::test_ac17_all_out_of_bounds_skip_record_and_review_lines,tests/test_outcome_components_module.py::test_ac18_out_of_bounds_task_shows_consumer_lines,tests/test_outcome_components_module.py::test_ac18_package_shows_consumer_records,tests/test_outcome_components_module.py::test_ac17_out_of_bounds_component_line
5	не убита	
6	убита	tests/test_outcome_components_module.py::test_ac16_diff_read_failure_refuses_preparation
7	убита	tests/test_outcome_components_module.py::test_ac17_first_refusal_names_component
8	убита	tests/test_outcome_components_module.py::test_ac23_seed_change_runs_both_components,tests/test_outcome_components_module.py::test_ac17_first_refusal_names_component
9	убита	tests/test_outcome_components_module.py::test_ac17_out_of_bounds_component_line
10	убита	tests/test_outcome_components_module.py::test_ac17_all_out_of_bounds_skip_record_and_review_lines
11	убита	tests/test_outcome_components_module.py::test_ac17_all_out_of_bounds_skip_record_and_review_lines
12	убита	tests/test_outcome_components_module.py::test_ac17_all_out_of_bounds_skip_record_and_review_lines
13	убита	tests/test_outcome_components_module.py::test_ac17_all_out_of_bounds_skip_record_and_review_lines
14	убита	tests/test_outcome_components_module.py::test_ac17_all_out_of_bounds_skip_record_and_review_lines
15	убита	tests/test_outcome_components_module.py::test_ac18_package_shows_consumer_records
```

Перед частью 16-29:

```
$ git status --porcelain -- orchestrator/
(вывод пуст)
```

```
# mutation-run №5 задачи 01M5RH875Q1JMVRM1TXNE6HNMW
# источник патчей: каталог на диске
# ревизия прогона: worktree ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_outcome_components_module.py
# рабочих процессов: auto
# патч 16 mutation-016.diff sha256 d4462902789d50acac7049bb240751f0cf153299f78f495690756ef9d97deef4
# патч 17 mutation-017.diff sha256 d364987d5093b624d6757c9f25ba498353a250ddb067d5f26ff15e5c080ddffa
# патч 18 mutation-018.diff sha256 91202daafdc4c257b877cf33f11edc3a6a9423e5fa41d64cd9b6cdd8dd98ada3
# патч 19 mutation-019.diff sha256 86ffdae74390a2a36f71b418b378e3890b42e3e9868eb7f6ebc2b0f7411ef652
# патч 20 mutation-020.diff sha256 49ab4835093e99345429abecfe9a2309b44b5a906f5815a0896eb80e32ebc96a
# патч 21 mutation-021.diff sha256 729421f23d6625dc94d584cbbfdc2ec18d2c0c77a1a3eb5a6d7ff2ed86100b5f
# патч 22 mutation-022.diff sha256 284a68839b4e86b709bd3090334454003489f6685cb92b1536147775e5ca5579
# патч 23 mutation-023.diff sha256 90078ba88f9e68f9a5ccbe6a3647223ee3c42fab1cd81f2ab1448b6fc5039778
# патч 24 mutation-024.diff sha256 7c3b643cac49df7b12f7bc941c274b1c55304961a4a086582b73a0cb6dbfb081
# патч 25 mutation-025.diff sha256 14b2fcea8e0a36b06ba6e888d22370700a8574a878ddceeddf0aa60d9a88919f
# патч 26 mutation-026.diff sha256 e1df9c28eb3a1f27241f6bf7b9dcd34571ff68a3739f7fcc50107ce873090d2e
# патч 27 mutation-027.diff sha256 2929cea62c3088fbeefd9dad8c4dad99617d6e52d29195547970ad3ddee6f6c3
# патч 28 mutation-028.diff sha256 27d11c230b821c8fe62b8b814383614dff262194eacaec88c9d253046279f1db
# патч 29 mutation-029.diff sha256 3bb2392faac355e3e8813e40bd444a4275d136ee3e37ec1ee9850d8db5b1ce30
номер	исход	узлы
16	убита	tests/test_outcome_components_module.py::test_ac18_package_shows_consumer_records,tests/test_outcome_components_module.py::test_ac18_out_of_bounds_task_shows_consumer_lines
17	убита	tests/test_outcome_components_module.py::test_ac18_out_of_bounds_task_shows_consumer_lines
18	убита	tests/test_outcome_components_module.py::test_ac18_package_shows_consumer_records,tests/test_outcome_components_module.py::test_ac18_out_of_bounds_task_shows_consumer_lines,tests/test_outcome_components_module.py::test_ac22_in_dev_outcome_gate_by_frontend,tests/test_outcome_components_module.py::test_ac16_diff_read_failure_refuses_preparation,tests/test_outcome_components_module.py::test_ac17_out_of_bounds_component_line,tests/test_outcome_components_module.py::test_ac16_component_change_runs_only_its_component,tests/test_outcome_components_module.py::test_ac22_tests_writing_exit_by_frontend_rule,tests/test_outcome_components_module.py::test_ac13_path_mandate_on_consumer_lifts_finding,tests/test_outcome_components_module.py::test_ac23_seed_change_runs_both_components,tests/test_outcome_components_module.py::test_ac17_first_refusal_names_component,tests/test_outcome_components_module.py::test_ac14_id_mandate_on_consumer_lifts_finding,tests/test_outcome_components_module.py::test_ac17_all_out_of_bounds_skip_record_and_review_lines,tests/test_outcome_components_module.py::test_ac22_merge_gate_outcome_by_frontend,tests/test_outcome_components_module.py::test_ac19_foreign_file_in_bounds_refused,tests/test_outcome_components_module.py::test_ac25_backend_file_on_frontend_task,tests/test_outcome_components_module.py::test_ac27_foreign_out_of_bounds_not_checked,tests/test_outcome_components_module.py::test_ac19_task_out_of_bounds_still_refused
19	убита	tests/test_outcome_components_module.py::test_ac17_all_out_of_bounds_skip_record_and_review_lines,tests/test_outcome_components_module.py::test_ac22_in_dev_outcome_gate_by_frontend,tests/test_outcome_components_module.py::test_ac18_package_shows_consumer_records,tests/test_outcome_components_module.py::test_ac16_component_change_runs_only_its_component,tests/test_outcome_components_module.py::test_ac18_out_of_bounds_task_shows_consumer_lines,tests/test_outcome_components_module.py::test_ac23_seed_change_runs_both_components,tests/test_outcome_components_module.py::test_ac17_out_of_bounds_component_line,tests/test_outcome_components_module.py::test_ac17_first_refusal_names_component,tests/test_outcome_components_module.py::test_ac16_diff_read_failure_refuses_preparation
20	убита	tests/test_outcome_components_module.py::test_ac22_merge_gate_outcome_by_frontend
21	убита	tests/test_outcome_components_module.py::test_ac22_merge_gate_outcome_by_frontend
22	убита	tests/test_outcome_components_module.py::test_ac13_path_mandate_on_consumer_lifts_finding
23	убита	tests/test_outcome_components_module.py::test_ac14_id_mandate_on_consumer_lifts_finding,tests/test_outcome_components_module.py::test_ac13_path_mandate_on_consumer_lifts_finding
24	убита	tests/test_outcome_components_module.py::test_ac14_id_mandate_on_consumer_lifts_finding
25	убита	tests/test_outcome_components_module.py::test_ac19_foreign_file_in_bounds_refused,tests/test_outcome_components_module.py::test_ac27_foreign_out_of_bounds_not_checked,tests/test_outcome_components_module.py::test_ac25_backend_file_on_frontend_task,tests/test_outcome_components_module.py::test_ac19_task_out_of_bounds_still_refused
26	убита	tests/test_outcome_components_module.py::test_ac19_task_out_of_bounds_still_refused
27	убита	tests/test_outcome_components_module.py::test_ac19_foreign_file_in_bounds_refused,tests/test_outcome_components_module.py::test_ac27_foreign_out_of_bounds_not_checked,tests/test_outcome_components_module.py::test_ac25_backend_file_on_frontend_task,tests/test_outcome_components_module.py::test_ac19_task_out_of_bounds_still_refused
28	убита	tests/test_outcome_components_module.py::test_ac19_foreign_file_in_bounds_refused,tests/test_outcome_components_module.py::test_ac27_foreign_out_of_bounds_not_checked,tests/test_outcome_components_module.py::test_ac25_backend_file_on_frontend_task,tests/test_outcome_components_module.py::test_ac19_task_out_of_bounds_still_refused
29	убита	tests/test_outcome_components_module.py::test_ac27_foreign_out_of_bounds_not_checked
```

Контрольные прогоны «после» (без патча): №4 — 17 passed in 17.28 с, №5 —
17 passed in 14.98 с.

Число тестов и строк: «до» — 17 тестов, 650 строк
(`tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`); «после» —
17 тестовых функций, 463 строки (`tests/test_outcome_components_module.py`)
плюс 232 строки песочниц (`tests/components_outcome_sandbox.py`).

## Влияние на систему

- Код `orchestrator/` не меняется: мутации живут только во временной
  копии `mutation-run`; перед каждой частью «после» `git status
  --porcelain -- orchestrator/` пуст, дерево `orchestrator/` всех шапок —
  ad3608c6.
- Тесты не ослаблены: 17 тестов с теми же утверждениями (сверка AST),
  песочницы — дословно, ни `skip`/`xfail`, ни пределов. Убыль
  прослеживаемых guard утверждений (методы песочниц зовутся через стенд)
  приписывается удаляемому пути и покрыта мандатом ANSWER-1;
  `outcome_prior` меняется только в докстринге и мандатом не покрыт.
- Не тронуты `tests/merge_outcome_sandbox.py`,
  `tests/outcome_gate_sandbox.py`, `tests/test_merge_outcome_module.py`,
  `tests/test_outcome_gate_module.py`, `tests/fixtures.py`,
  `tests/sandbox.py`, `tests/test_invariants.py`;
  `docs/codebase-map.md` — только вывод генератора.
- Временные файлы: генератор патчей жил первым уровнем каталога
  документов (`gen_patches.py`, имя не `test_*`/`mutation-*`) и удалён до
  конца шага; в рабочей копии временных файлов нет — `git status
  --porcelain` называет только пути требования 9.
- Откат — revert одного merge-коммита: возвращает исходный файл и
  убирает два новых модуля.

## Риски

- `ContextRunnerProc` и песочницы теперь импортируются из не-тестового
  модуля: pytest не собирает `tests/components_outcome_sandbox.py`
  (имя не `test_*`), классы песочниц без методов `test_*` в новом модуле
  тестов не дают.
- Зерно не фиксировалось: исходы «до» и «после» совпали во всех 29
  мутациях на разных зёрнах прогонов.

## Предложения системе

- Заявки долгоживущих тестов ссылаются на устаревшие адреса (`criterion_files` в заявке `test_ac19_foreign_file_in_bounds_refused` при отказе из `_tests_writing_foreign_plank_gate`; номера строк `fsm_advance.py`) — при своде тестов такая заявка не воплощается дословно; полезна проверка в guard/ревью: заявка называет функцию, а не строки, и функция существует.
- Альтернативы заявок, которые тест не может различить из-за устройства песочницы (метка стороны `app.py` расширяет выбор компонентов до всех — `depends_on` не проверяется ни одним тестом записи из нескольких компонентов), видны только мутацией; стоит завести тест выбора по `depends_on` с коммитом без метки (`no_marker`).
