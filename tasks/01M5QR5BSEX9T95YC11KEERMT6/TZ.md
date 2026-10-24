---
task: 01M5QR5BSEX9T95YC11KEERMT6
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Скорость набора: уборка full_suite_lock без ожидания предела и запись замера вместо настоящих прогонов в doctor_duration ac8

# Скорость набора тестов: уборка `full_suite_lock` без ожидания предела и замена настоящих прогонов в `doctor_duration` ac8 записью замера

## Факты

Решение Оператора 24.10.2026 (дословно): «Заводи рекомендованный набор: быстрая задача по full_suite_lock и doctor_duration сейчас, задачи по git 1, 5, 2, 3, 4 — по очереди между волнами; шаблон песочниц и подделку pytest — отложить.» Мандат Оператора 24.10.2026 (дословно): «Даю мандат на tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py и tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py: в ac8 заменить 16 из 17 measured_run записью замера, один настоящий прогон оставить; в full_suite_lock исправить имя файла в stop_everything.» Повод — исследование скорости набора 24.10 (полный прогон 1500 с из предела 1500 с, триггер suite.near_limit №886); замеры шпионом процессов на 9c0e8b8c. Сверено с origin/main 9c0e8b8c.

- `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py` — долгоживущий файл задачи 01M46D5T8SZ9D6S34TZFX8S46V (1052 строки). Уборка `stop_everything` (:355, ставится `addCleanup` в :199): для каждого `tree-<метка>` пробника зовёт `self.release(path.name)` (:357), а `release(label)` (:252) пишет `release-<label>` (`release_path`, :249–250) — получается `release-tree-<метка>`, тогда как тест-пробник ждёт `release-<метка>`. Поэтому цикл ожидания (:360–363) каждый раз доходит до предела 10 с, затем группы процессов снимаются `SIGKILL`. Замер: 94 паузы, 10,0 из 16,4 с теста `test_ac11_not_started_is_refused_with_holder` (:1016); то же у `test_ac6_wait_over_limit_is_not_started_without_pytest` (:657) и `test_ac9_timeout_is_refused_as_timeout_not_as_broken_appendix` (:962) — тесты, где держатель не отпущен самим тестом.
- `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py` — долгоживущий файл задачи 01M4ARAXF7VSS5XZ8C99BX8DE2 (272 строки). `measured_run(delay, count=4, workers=1)` (:77) пишет учебный тест со сном `delay`, запускает настоящий `acceptance.full_suite(...)` и утверждает, что записан шаг «прогон: время» (:89); `journal_measurement(duration, tests=4, workers=1)` (:91) пишет замер через `acceptance.journal_suite_metrics` без прогона. `test_ac8_ack_restarts_calibration_after_signal` (:253) делает 17 настоящих прогонов: `k = config.SUITE_DURATION_CALIBRATION_RUNS` (= 8, `orchestrator/config.py:232`) раз `measured_run(0.01)`, затем `measured_run(4.0)` (сигнал), затем ещё `k` раз `measured_run(0.01)`. Замер: 17 × 1,56 с = 26,5 из 33,8 с теста плюс сон 4 с во вложенном тесте. Соседние тесты файла (:168–246) калибруются записями `journal_measurement(1.12)` и сигналят `journal_measurement(1.92)`.
- Вызовы `doctor_checks` в этом файле обращаются к настоящему `gh` и `claude --version` (строка копилки 24.10) — вне этой задачи.
- Гейт неослабления читает мандат из `ANSWER-n.md`; замена вызовов помощника с утверждением уменьшает число прослеженных утверждений теста — находка снимается мандатом на путь.

## Требования

1. `full_suite_lock`: в `stop_everything` отпуск пробников пишет файл, который ждёт пробник: `self.release(path.name.removeprefix("tree-"))` (или равное по смыслу); прочие строки уборки (сигнал `linger`, ожидание до 10 с, `SIGKILL` групп, сверка записей pid) не меняются. Тесты файла и их утверждения не меняются.
2. `doctor_duration` ac8: из 17 вызовов `measured_run` один остаётся настоящим — первый вызов калибровки `measured_run(0.01)` (держит свойство «настоящий полный прогон пишет замер»); остальные 15 калибровочных и сигнальный заменяются `journal_measurement` с длительностями, при которых калибровка и сигнал устроены как в соседних тестах файла (калибровка — по образцу `journal_measurement(1.12)`, сигнал — заметно выше порога, по образцу `journal_measurement(1.92)` или выше); значения и их обоснование — в PLAN. Утверждения теста (`len(found) == 1`, сброс после `ack_alert`, отсутствие повторного сигнала без нового окна) не меняются; текст «Ловит мутацию» не меняется. Если настоящий первый прогон своей длительностью мешает калибровке (разброс выше порога сигнала), он ставится в начало и его вклад в калибровку обосновывается в PLAN либо выбирается иная позиция — решение с замерами в PLAN.
3. Доказательство неослабления для ac8: патч мутации из его заявки («doctor перечитывает старую калибровку после ack и сразу повторно открывает тот же suite.duration без нового окна») в `tasks/<id>/mutation-001.diff` и ещё одна правдоподобная мутация калибровки в `mutation-002.diff`; `mutation-run <id> --ref base --tests tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py --wait-lock 4` и `--ref worktree` тем же набором — обе мутации убиты «до» и «после» утверждением ac8 (строка падения из лога — в PLAN); дерево `orchestrator/` и sha256 патчей в шапках совпадают; вывод — в PLAN дословно.
4. Время: в PLAN — время `test_ac6_wait_over_limit_is_not_started_without_pytest`, `test_ac9_…`, `test_ac11_…` и `test_ac8_ack_restarts_calibration_after_signal` до и после (одиночные адресные прогоны без xdist); после правки ни один тест `full_suite_lock` не ждёт предел уборки (в логе уборки нет снятия по `SIGKILL` живых процессов пробника — или объяснение в PLAN).
5. Временные файлы в рабочей копии не создаются (допустимо: файл первого уровня каталога документов задачи не `.md` и не `test_*`/`mutation-*` либо `$TMPDIR` командой `python3`). Ожидание замка — только `--wait-lock`.
6. Независимая проверка (повтор `mutation-run`, сверка диффа) — сессией при Операторе до approve на merge_gate.

Зоны: tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py, tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py, docs/codebase-map.md

Ограничение зон по смыслу: в `full_suite_lock` — только строка отпуска в `stop_everything`; в `doctor_duration` — только тело `test_ac8_ack_restarts_calibration_after_signal`; код `orchestrator/` не меняется; `docs/codebase-map.md` — только вывод генератора.

Только чтение: orchestrator/ (весь код пульта; мутации — только во временной копии `mutation-run`), orchestrator/acceptance.py, orchestrator/doctor/, orchestrator/config.py, orchestrator/advance_gates/test_integrity.py, orchestrator/advance_gates/mandate.py, orchestrator/mutation_run.py, tests/sandbox.py, tests/fixtures.py, scripts/guard.py, tests/test_invariants.py, orchestrator/test_lint.py.

Не входит: остальные тесты `doctor_duration` и обращения `doctor_checks` к `gh`/`claude --version` (строка копилки); замена пауз в других тестах `full_suite_lock` (`hold_then_contend` и др.); общая подделка pytest и шаблон песочниц (отложены решением Оператора); изменение кода пульта.

Бюджет: $30.
