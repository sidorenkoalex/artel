---
task: 01M4AXPY1PY4PS1YAFAMD47VBY
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Оборванная канарейка не оставляет прогонов и клонов; канарейка отвязывается сама

## Гейт плана (фаза A)

Таблица покрытия плана полна: требования 1–4, 5–6, 7–9 и 10 покрыты отдельными шагами. Шаги соразмерны MR, проверяемы и согласованы с существующей архитектурой: единый marker владельца читают жизненный цикл канарейки и `doctor`, а отвязанный запуск остаётся в публичном CLI. Влияние на систему и обратимый откат описаны и соответствуют фактическому diff.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Обработчик SIGTERM/SIGHUP прерывает ведение; `finally` снимает группы и удаляет клон с origin. |
| 2 | OK | Сигнальный исход записывается красной строкой с именем сигнала и без нового значения `verdict`. |
| 3 | OK | `run.json` клона читается при уборке, а группа сохранённого pid снимается при штатном, ошибочном, таймаутном и сигнальном выходе. |
| 4 | OK | Marker владельца записывается в клон; marker origin защищает окно до связи remote, а копия базы несёт marker процесса `suite-run`. |
| 5 | OK | Watchdog распознаёт временные каталоги и не трогает процессы живого владельца. |
| 6 | OK | Сироты канарейки, origin и базы находятся и удаляются; живые владельцы и конкретно связанный живой legacy-прогон защищены. |
| 7 | OK | `--detach` создаёт отдельную сессию, лог и файл результата, сразу печатая pid и пути. |
| 8 | OK | Справка называет `--detach` штатным запуском для сессии Оператора. |
| 9 | OK | `docs/operator-session.md` содержит отвязанный запуск и правило предварительной проверки нагрузки. |
| 10 | OK | Долгоживущие тесты покрывают критерии; новые тесты ownership содержат проверяемые заявки «Ловит мутацию». |

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/doctor/orphans.py:58-102 | Глобальный признак живого `suite-run` защищал все `artel-suite-base-*`, а не каталог конкретного прогона. | `doctor --fix` оставлял сироты при несвязанном живом `suite-run`. | Принято: `_live_suite_run_in(path)` сопоставляет cwd живого pid с конкретной базой; собственный marker новой базы остаётся приоритетным. Тест `test_unrelated_live_suite_run_does_not_protect_orphan_base` подтверждает, что чужой `run.json` не защищает сироту. |
| R1-F2 | accepted | orchestrator/doctor/orphans.py:82-97; orchestrator/canary.py:1205-1208 | Проверка origin обходила его живой marker до появления remote-связи. | `doctor --fix` мог удалить origin активной канарейки. | Принято: до remote-связи учитывается marker origin; после связи владельцем служит связанный клон. Origin проверяется и удаляется раньше клона. Тест `test_live_origin_marker_protects_before_remote_link` подтверждает защищённое окно. |

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py tests/test_canary_doctor_owner.py` — 16 passed.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4AXPY1PY4PS1YAFAMD47VBY` — зафиксированная планка: 1 passed, код pytest 0.
- `git diff --check c73f243f6aa5d258f68f155d94c760d4618b52f0...HEAD` — замечаний формата diff нет.

## Предложения системе
