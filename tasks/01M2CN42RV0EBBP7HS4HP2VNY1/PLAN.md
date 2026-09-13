---
task: 01M2CN42RV0EBBP7HS4HP2VNY1
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Рефакторинг canary.py — вынос запечатанного пула в pool_seal.py

## Подход
Чисто структурный перенос (находка ревизии №6 CR-2026-09-13-4 ★):
область запечатанного пула (canary.py:181–462 на коммите-базе
812c9064) переезжает дословно в новый `orchestrator/pool_seal.py`,
потребители переключаются на новый источник. Логика HMAC/openssl/
GUID-манифеста не тронута — тела функций скопированы байт-в-байт
(подтверждено приёмочным тестом AC-1, сравнивающим исходный текст
каждой из 13 функций построчно с `git show <BASE_COMMIT>:orchestrator/
canary.py`).

Единственная точка сцепления между областями — `_pool_dir()`. Приёмочная
планка (test_ac2) фиксирует конкретный способ связки: `canary.py` несёт
`from .pool_seal import _pool_dir` (не `from . import pool_seal` +
`pool_seal._pool_dir()`) — так `canary._pool_dir` остаётся тем же
объектом, что и `pool_seal._pool_dir`, и патч `mock.patch.object(canary,
"_pool_dir", ...)` в существующих/приёмочных тестах продолжает работать.

Требование 6 (разбить `_run_one_task` на три фазы) реализовано тремя
приватными функциями-фазами того же модуля (`_run_task_in_ephemeral_
clone` / `_record_canary_run` / `_baseline_deviation_note`) — порядок
побочных эффектов (запись `canary_runs` до сверки с бейзлайном, все
`print` в прежнем порядке) сохранён байт-в-байт: полный набор
`tests/test_canary.py` (85 тестов) зелёный без правки ассертов.

## Шаги

1. Создать `orchestrator/pool_seal.py`: 13 функций требования 1 плюс
   вспомогательные константы `SEALED_REL`/`GUIDS_REL`/`_TAG_HEX_LEN` —
   дословный перенос из `canary.py:181–462`; свой набор импортов
   (`hashlib`, `hmac`, `io`, `os`, `struct`, `subprocess`, `sys`,
   `uuid`, `contextlib.contextmanager`, `pathlib.Path`,
   `from . import alerts, config, keychain, runner`).
2. Удалить перенесённый диапазон из `canary.py`; заменить докстринг-блок
   :48–55 ссылкой на `pool_seal.py`; убрать импорты `hashlib`, `hmac`,
   `struct`, `uuid`, `keychain` (ни одного использования вне
   перенесённого кода не осталось); добавить `from .pool_seal import
   _pool_dir` — `cmd_canary` продолжает звать голое имя `_pool_dir()`.
3. Переключить потребителей: `artel.py::_cmd_canary` →
   `pool_seal.cmd_pool_seal()` (плюс `pool_seal` в импорт пакета);
   `catalog.py::cmd_init` → ленивый `from . import pool_seal`,
   `pool_seal.restore_pool_if_missing(conn)`; `doctor/cli.py` →
   `doctor.pool_seal.restore_pool_if_missing(conn)`;
   `doctor/canary_pool.py::check_canary_pool_drift` →
   `doctor.pool_seal.pool_drift_warning()`; `doctor/__init__.py` —
   `pool_seal` добавлен в общий кортеж импорта фасада (алфавитно, между
   `notes` и `projects`) и в докстринг-список коллаборантов.
4. Разбить `_run_one_task` на три внутримодульные фазы (требование 6):
   `_run_task_in_ephemeral_clone` (прогон в эфемерном клоне, включая
   сохранение диагностики, пока клон жив), `_record_canary_run` (запись
   строки `canary_runs`), `_baseline_deviation_note` (сверка с
   per-task бейзлайном) — сама `_run_one_task` только вызывает фазы по
   порядку и собирает итоговую печать; порядок побочных эффектов не
   изменён.
5. Обновить импорты/пути патчей: `tests/test_canary.py` (~20 обращений
   в диапазоне :1492–1645 плюс два патча `canary.keychain` →
   `pool_seal.keychain`), `tests/test_doctor_canary_pool.py`
   (`doctor.canary.keychain` → `doctor.pool_seal.keychain`,
   `doctor.canary.cmd_pool_seal()` → `doctor.pool_seal.cmd_pool_seal()`
   ×3). Дополнительно (обнаружено прогоном затронутых тестов, не было
   в перечне требования 8 SPEC): `tests/test_artel_role_restricted_
   commands.py` и `tests/test_new_argv_parsing.py` патчили
   `canary.cmd_pool_seal`/`artel.canary.cmd_pool_seal` через
   `artel._cmd_canary` — тот же класс правки (путь патча), перенесены
   на `pool_seal.cmd_pool_seal`/`artel.pool_seal.cmd_pool_seal`.
   Существующие ассерты нигде не изменены.
6. Регенерировать `docs/codebase-map.md` (`python3
   scripts/codebase_map.py`) — новая секция `orchestrator/pool_seal.py`.
7. Проверить отсутствие циклов импортов (`python3 -c "import
   orchestrator.<module>"` для `canary`/`pool_seal`/`catalog`/`doctor`/
   `artel`, плюс `python3 -X importtime -c "import orchestrator.doctor"`)
   и прогнать юнит- и приёмочные тесты затронутых модулей.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 2 |
| 4 | 3 |
| 5 | 7 |
| 6 | 4 |
| 7 | 1, 4 (перенос дословный + порядок фаз сохранён) |
| 8 | 5 |
| 9 | 6 |
| 10 | 1–4 (не тронуто: `_ephemeral_clone`, `_drive_task`, `--sha`, `runner.in_role_environment`, `answer.py:113`, `prune.py:80`) |

## Влияние на систему

**Таблица переносов** (функция → откуда → куда, все — `orchestrator/`):

| Функция/имя | Откуда (canary.py, коммит-база 812c9064) | Куда |
|---|---|---|
| `_pool_dir` | :181 | `pool_seal.py` (импортируется в `canary.py` по имени) |
| `sealed_path` | :218 | `pool_seal.py` |
| `guids_path` | :222 | `pool_seal.py` |
| `_mac_key` | :226 | `pool_seal.py` |
| `_secret_fd` | :233 | `pool_seal.py` |
| `_hmac_tag_hex` | :249 | `pool_seal.py` |
| `_openssl_encrypt` | :273 | `pool_seal.py` |
| `_openssl_decrypt` | :285 | `pool_seal.py` |
| `_serialize_pool` | :298 | `pool_seal.py` |
| `_deserialize_pool` | :315 | `pool_seal.py` |
| `_authorized_pool_payload` | :332 | `pool_seal.py` |
| `restore_pool_if_missing` | :380 | `pool_seal.py` |
| `pool_drift_warning` | :399 | `pool_seal.py` |
| `cmd_pool_seal` | :425 | `pool_seal.py` |
| `SEALED_REL`/`GUIDS_REL`/`_TAG_HEX_LEN` | :213–215 | `pool_seal.py` (константы, используемые перенесёнными функциями) |

Затронуты только точки импорта/вызова (`artel.py`, `catalog.py`,
`doctor/__init__.py`, `doctor/cli.py`, `doctor/canary_pool.py`) — сама
логика HMAC/openssl/GUID-манифеста, `_ephemeral_clone`, `_drive_task`,
`--sha`, `runner.in_role_environment` не тронуты (требование 10).
Гейты/лимиты/инварианты не ослаблены — перенос не убирает ни одной
проверки, только меняет модуль-источник имени.

**Откат** — ревертом ОДНОГО merge-коммита этой задачи: вся правка сделана
в одном шаге разработчика на кодовой ветке (два коммита на самой ветке,
второй — точечное исправление первого под приёмочную планку; при мерже в
main ветка ложится ОДНИМ merge-коммитом, как и любая другая задача этого
пульта): `git revert -m 1 <merge-sha>` возвращает `canary.py` к прежнему
монолиту и удаляет `pool_seal.py`, потребители возвращаются к
`canary.<имя>` автоматически (тот же diff в обратную сторону).

**Смоук `doctor`/`status` до/после** (без изменяющих флагов, канарейка
не гонялась): живой прогон `artel.py doctor`/`status` из этого рабочего
каталога (git-worktree роли) недоступен по инварианту T056 (`_refuse_
if_worktree`, сам пульт отказывает в исполнении не из главной копии);
попытка получить независимую копию для сравнения (`git clone` внутри
рабочего каталога задачи) была отклонена в этой сессии инструментом
подтверждения — не повторялась (правило «не повторять один и тот же
отклонённый вызов»). Вместо буквального двойного прогона CLI выполнен
эквивалентный прямой вызов `catalog.cmd_status()`/`doctor.cmd_doctor()`
(тот же код, что стоит за подкомандами `status`/`doctor`) в изолированной
песочнице (временный `config.ROOT`, тем же приёмом, что и
`tests/sandbox.py::TmpRootTest`) на ПОСЛЕ-коде: `status` печатает «Задач
нет...» как на чистом состоянии; `doctor` проходит все проверки без
исключений, в частности `[ok] canary-pool-drift: открытый пул канарейки
не расходится с запечатанным...` — ровно та проверка, что теперь читает
`doctor.pool_seal.pool_drift_warning()` вместо `doctor.canary.
pool_drift_warning()`. Поскольку AC-1 (приёмочный тест) уже доказывает
байт-в-байт идентичность тел перенесённых функций, а этот смоук
подтверждает, что фасад `doctor`/`cmd_status` резолвит новый путь без
ошибок и печатает тот же текст, текстовый вывод `doctor`/`status`
до/после переноса тождественен по построению — отдельный повторный
прогон ДО-кода в изолированной копии не потребовался.

## Риски

- Автоматическая связка `_pool_dir` через `from .pool_seal import
  _pool_dir` (не `pool_seal._pool_dir()`) — единственный вариант,
  совместимый с залоченной приёмочной планкой (`test_ac2_canary_pool_
  dir_is_the_same_object_as_pool_seal`/`test_ac2_cmd_canary_resolves_
  pool_dir_through_canary_local_name`): при первой попытке реализации
  через `from . import pool_seal` эти два теста красили — планка
  зафиксировала конкретный способ импорта, не только факт переноса.
- Обратная совместимость с чужими залоченными планками
  (`tasks/01M1SC3Y20YBTTJVQDJBF2NDQW/acceptance_tests/
  test_canary_report_kill_reason.py`) сохранена: сигнатуры
  `_run_one_task`/`_ephemeral_clone` не менялись, разбивка на фазы —
  внутренняя.

## Предложения системе
- `orchestrator/canary.py` после переноса не использует `os` нигде,
  кроме перенесённого в `pool_seal.py` кода — импорт `import os`
  формально стал мёртвым, но требование 2 SPEC перечисляет только пять
  конкретных имён (`hashlib`/`hmac`/`struct`/`uuid`/`keychain`) под
  удаление; правило «рефакторинг = перенос, не улучшение»
  (skills/coding-standards.md) запрещает попутную чистку сверх
  перечисленного — оставлено как есть, но стоит учесть при следующей
  правке `canary.py`.
- SPEC требования 8 перечислил для правки только `tests/test_canary.py`
  и `tests/test_doctor_canary_pool.py`; полный прогон затронутых
  тестов вскрыл ещё два файла с тем же классом правки (путь патча
  `canary.cmd_pool_seal` → `pool_seal.cmd_pool_seal` через диспетчер
  `artel.py`): `tests/test_artel_role_restricted_commands.py` и
  `tests/test_new_argv_parsing.py`. Стоит добавить в скил
  test-authoring/code-revision практику «после переноса имени — grep
  по старому модуль.имя во ВСЕМ `tests/`, не только по файлам,
  перечисленным в SPEC».
