---
task: 01M3Y75GCRESC2KDS9VPRJK4PS
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: pin-update называет живые циклы auto/run, запущенные на старом коде

## Подход
Один отбор на обе точки вывода — `orchestrator/doctor/stale_cycles.py`:
- `process_start_time(pid)` — `ps -o lstart= -p <pid>` под `LC_ALL=C`
  (местное время → UTC); `ps` ищется по PATH, иначе `/bin/ps` (окружение
  шага роли может не нести `/bin`). Любой сбой (OSError/SubprocessError,
  ненулевой код, пустой/неразборчивый ответ) → `None`, цикл попадает в
  перечень с пометкой «не удалось определить» (требование 4).
- `stale_cycles(conn, pin_moment)` — `store.all_leases`, фильтр
  `hostname == socket.gethostname()` + `liveness._pid_alive` (образец
  `check_leases`), старт `< pin_moment` либо неопределим; состояние задачи
  из `tasks`; аргументы наблюдения — `observed_runs` по task_id И pid,
  `client`/`chat` из связанной `observations`.
- `stale_cycle_lines` — строка на цикл: id, pid, время старта, состояние,
  `artel.py stop <id>`, затем `artel.py auto <id> [--client c --chat ch]`.
- `check_stale_cycles(conn)` — момент пина = `ts` последней записи
  «pin обновлён»; `warn` «циклы на коде старше пина» с перечнем, иначе
  `ok`; без записи пина — `ok`.

`pin.cmd_pin_update`: момент сдвига фиксируется сразу после успешного
`merge --ff-only`; после записи «pin обновлён» перечень печатается и
пишется отдельной записью журнала «pin: циклы на коде старше пина» (только
если перечень непуст). Сигналов процессам ничего не шлёт.

Почему отбор не в `pin.py`: `tests/test_invariants.py::
CarpentryGitCallsGoThroughGitcmdTest` (инвариант 33) запрещает прямой
`subprocess.run(` в `pin.py`; в пакете doctor вызов идёт через фасад
`doctor.subprocess` по его правилу. `pin.py` импортирует `doctor`.

## Шаги
1. `orchestrator/doctor/stale_cycles.py` + экспорт в фасаде
   `orchestrator/doctor/__init__.py` + регистрация `check_stale_cycles` в
   `orchestrator/doctor/cli.py::all_checks` рядом с проверками пина.
2. `orchestrator/pin.py::cmd_pin_update` — `_report_stale_cycles` после
   записи «pin обновлён».
3. Юнит-тесты `tests/test_pin_update_stale_cycles.py` на свойства, не
   покрытые долгоживущим файлом: lease чужой машины не назван; `doctor` без
   записи пина не предупреждает и отбор не зовёт; `lstart` трактуется как
   местное время (TZ=Europe/Moscow) и вызывается с `LC_ALL=C`. Мутации
   проверены: снятие фильтра hostname и `replace(tzinfo=utc)` вместо
   `astimezone` — тесты красные; снятие ветки «нет записи пина» — красный.
4. `python3 scripts/codebase_map.py` — карта регенерирована.
5. Подтяжка main (возврат «конфликт подтяжки»): коммит `8e44ec70`.
   Конфликты аддитивные, разрешены объединением обеих сторон:
   - `orchestrator/pin.py`: импорт `ci, doctor` вместе;
     `_report_stale_cycles` и `_refuse_unless_main_ci_green` (из main,
     SPEC 01M3SF7DPFGEZ7VYEGGXGTX49E) лежат рядом. В `cmd_pin_update`
     порядок такой: fetch → канарейка → CI main → `merge --ff-only` →
     момент пина → «pin обновлён» → перечень циклов.
   - `orchestrator/doctor/__init__.py`: подключены и `main_ci`, и
     `stale_cycles`;
     `orchestrator/doctor/cli.py::all_checks`: `check_main_ci()`, затем
     `check_stale_cycles(conn)`.
   - `docs/codebase-map.md`: взят из main и перегенерирован
     `scripts/codebase_map.py`.
6. Ответ Оператора ANSWER-1 на эскалацию о красной долгоживущей планке
   после подтяжки: Оператор поправил долгоживущий файл через `amend-tests`
   (коммит `f7128cae`, в `_PinUpdateSandbox.setUp` подменён
   `ci.main_line_status`). Сумма файла `8cedcc42…` сверена с
   `acceptance_tests/long_lived.sha256.txt` — совпадает. Проверку CI в
   `pin-update` (`_refuse_unless_main_ci_green`) не ослаблял. Код задачи в
   этом шаге не менялся. Карта перегенерирована
   `scripts/codebase_map.py`: тест задачи теперь импортирует
   `orchestrator/ci.py`.

Прогоны после ANSWER-1 (передний план, `-p no:cacheprovider -p timeout -o
timeout=120`): `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`,
`tests/test_pin_update_stale_cycles.py`, `tests/test_pin.py`,
`tests/test_doctor.py`, `tests/test_invariants.py`,
`tests/test_codebase_map.py` — вместе 254 passed, 0 failed.

7. Возврат из verifying (CI красный на `36732227`:
   `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::LaunchHintTest::
   test_ac7_no_bare_cycle_hint_literals_outside_cycle_hint` — f-строка
   `artel.py auto {task_id}` в `orchestrator/doctor/stale_cycles.py`).
   Зона `orchestrator/cycle_hint.py` разрешена ANSWER-2.
   - `orchestrator/cycle_hint.py::cycle_command(cmd, task_id, client=None,
     chat=None)` — строка запуска по уже известным аргументам наблюдения,
     без чтения БД и без заглушек; `--client`/`--chat` только при обоих
     значениях.
   - `orchestrator/doctor/stale_cycles.py`: `_observation_args` возвращает
     `(client, chat)` наблюдения этого запуска (task_id И pid) либо
     `(None, None)`; `stale_cycle_lines` строит команду `auto` через
     `doctor.cycle_hint.cycle_command` (модуль подключён в фасаде
     `orchestrator/doctor/__init__.py`). Семантика AC-2 прежняя.
   - Тест `tests/test_pin_update_stale_cycles.py::CycleCommandTest::
     test_restart_line_is_built_by_cycle_hint`; мутация (возврат
     собственной сборки строки в `stale_cycle_lines`) — красный, код
     возвращён. Тест launch_hint и долгоживущие тесты не правились.
   - Карта перегенерирована `scripts/codebase_map.py`.
   Прогоны (передний план, `-p no:cacheprovider -p timeout -o
   timeout=120`): launch_hint + `tests/test_01m3y75gcresc2kds9vprjk4ps_
   stale_cycles.py` + `tests/test_pin_update_stale_cycles.py` +
   `tests/test_cycle_hint.py` + `tests/test_pin.py` — 32 passed;
   `tests/test_doctor.py` + `tests/test_invariants.py` +
   `tests/test_codebase_map.py` — 236 passed.

8. Ответ Оператора ANSWER-3: раздел «Расширение зон» с путём
   `orchestrator/cycle_hint.py` добавлен в PLAN.md; код не менялся.
   Карта перегенерирована `scripts/codebase_map.py` (в ней появилась
   публичная `cycle_hint.cycle_command`). Повторные прогоны (передний
   план, `-p no:cacheprovider -p timeout -o timeout=120`): launch_hint +
   `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py` +
   `tests/test_pin_update_stale_cycles.py` + `tests/test_cycle_hint.py` +
   `tests/test_pin.py` — 32 passed; `tests/test_doctor.py` +
   `tests/test_invariants.py` + `tests/test_codebase_map.py` — 236 passed.

## Покрытие требований
| Требование | Шаг |
|---|---|
| 1 (перечень в выводе и журнале, команды stop/auto, аргументы наблюдения) | 1, 2 |
| 2 (без сигналов процессам) | 2 |
| 3 (проверка doctor по последней записи «pin обновлён») | 1 |
| 4 (время старта из таблицы процессов, «не удалось определить») | 1 |
| 5 (тесты с «Ловит мутацию») | 3 |

## Влияние на систему
- `pin-update`: поведение до и включая запись «pin обновлён» не меняется;
  добавлен вывод и одна запись журнала после неё. Отказы fetch/канарейки/
  CI main/merge — прежние.
- `doctor`: одна новая строка `stale-cycles`, статус только `ok`/`warn`,
  на итог `DOCTOR` (провалы) не влияет. Новый внешний вызов — `ps` на
  каждый живой lease этой машины, с таймаутом 10 с.
- Инвариант 33 соблюдён (в `pin.py` нет прямых `subprocess`), правило
  фасада doctor (подмодуль не импортирует `subprocess`/`shutil`) соблюдено.
  Тесты, гейты, лимиты не ослаблялись.
- Откат — revert коммита задачи.

## Расширение зон

Пути: orchestrator/cycle_hint.py

Обоснование: инвариант SPEC 01M3XTFJCC5TG63FHW907GQM4D — строка запуска run/auto собирается только в cycle_hint.py; команда перезапуска stale_cycles строится функцией cycle_command оттуда (возврат Оператора из verifying, 02.10).

## Риски
- Точность `ps lstart` — секунда: цикл, стартовавший в ту же секунду, что
  и сдвиг пина, может быть назван «старше пина» в `pin-update` и не назван
  в `doctor` (момент там — `ts` журнала с точностью до секунды).
- Формат `lstart` под `LC_ALL=C` одинаков у macOS/BSD и procps; иной
  формат даёт «не удалось определить», не отказ.

## Предложения системе
- SPEC называет `tests/test_pin_update_stale_cycles.py` файлом тестов, а
  test_author положил долгоживущий файл под именем
  `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py` (вне `zones:`
  SPEC); analyst мог бы сразу называть в SPEC имя по конвенции ADR-0020.
- Анализ SPEC («Материалы») не учёл инвариант 33 для `pin.py` — новый
  внешний вызов там запрещён; карта кодовой базы не несёт инвариантов
  модулей, такие запреты всплывают только прогоном `test_invariants.py`.
- Подтяжка main, в которой появилось новое условие команды (`pin-update`
  стал требовать зелёный CI), ломает залоченный долгоживущий файл задачи,
  и разработчик не может это закрыть без `amend-tests`. Гейт подтяжки
  (`orchestrator/pull.py::evaluate`) мог бы называть такой класс сразу —
  красная долгоживущая планка после подтяжки, — а не через шаг разработчика.
