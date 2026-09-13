---
task: 01M2CN42RV0EBBP7HS4HP2VNY1
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/pool_seal.py, orchestrator/canary.py, orchestrator/catalog.py, orchestrator/artel.py, orchestrator/doctor/__init__.py, orchestrator/doctor/cli.py, orchestrator/doctor/canary_pool.py, docs/codebase-map.md, tests/
budget_usd: 35
---

# SPEC: Рефакторинг canary.py — вынос запечатанного пула в pool_seal.py

## Контекст
`orchestrator/canary.py` (1358 строк) держит две несвязанные области:
запечатанный пул шаблонов ТЗ (:181–462) и прогон синтетического
конвейера (`_ephemeral_clone` :501, `_drive_task` :850, `_run_one_task`
:1187). Единственная общая точка — `_pool_dir()` (:181, зовётся также
из `cmd_canary` :1341). Находка ревизии №6 CR-2026-09-13-4 ★, ТЗ-черновик
Р-4: вынести область пула в отдельный модуль `orchestrator/pool_seal.py`.
Поведение не меняется — это структурный перенос, не переработка логики.

## Требования

1. Создать `orchestrator/pool_seal.py`: функции текущего диапазона
   canary.py:181–462 (`_pool_dir`, `sealed_path`, `guids_path`,
   `_mac_key`, `_secret_fd`, `_hmac_tag_hex`, `_openssl_encrypt`,
   `_openssl_decrypt`, `_serialize_pool`, `_deserialize_pool`,
   `_authorized_pool_payload`, `restore_pool_if_missing`,
   `pool_drift_warning`, `cmd_pool_seal`) переносятся в него дословно
   (без изменения тел). `_pool_dir` живёт в `pool_seal.py`; `canary.py`
   импортирует то, что ему из этого набора всё ещё нужно (в первую
   очередь `_pool_dir`, используемую в `cmd_canary`).
2. Из `canary.py` убрать импорты `hashlib`, `hmac`, `struct`, `uuid`,
   `keychain`, если после переноса ни один из них в `canary.py` больше
   не используется.
3. Докстринг-блок `canary.py` (:48–55), описывающий механику
   запечатанного пула, заменить ссылкой на новое место (`pool_seal.py`)
   вместо описания реализации на месте.
4. Переключить потребителей пула на `orchestrator/pool_seal.py`:
   - `orchestrator/artel.py:705` (`canary.cmd_pool_seal()` →
     `pool_seal.cmd_pool_seal()`, включая соответствующую правку
     импорта модуля);
   - `orchestrator/catalog.py:46–50` (ленивый импорт внутри `cmd_init`:
     `from . import canary` → `from . import pool_seal`,
     `canary.restore_pool_if_missing(conn)` →
     `pool_seal.restore_pool_if_missing(conn)`);
   - `orchestrator/doctor/cli.py:98` (`doctor.canary.restore_pool_if_missing(conn)`
     → `doctor.pool_seal.restore_pool_if_missing(conn)`);
   - `orchestrator/doctor/canary_pool.py:61`
     (`doctor.canary.pool_drift_warning()` →
     `doctor.pool_seal.pool_drift_warning()`);
   - `orchestrator/doctor/__init__.py:96` (добавить `pool_seal` в
     список импортируемых модулей пакета `orchestrator`, чтобы
     `doctor.pool_seal` было доступно тем же приёмом, что и
     `doctor.canary` сегодня).
5. После переключения проверить отсутствие циклов импортов между
   `canary.py`, `pool_seal.py`, `catalog.py` и `doctor/__init__.py`
   (`python -X importtime` либо прямой импорт каждого модуля).
6. `_run_one_task` (canary.py:1187) остаётся в `canary.py`, разбит на
   три приватные внутримодульные фазы: прогон в эфемерном клоне,
   сверка результата с бейзлайном, диагностика и запись в
   `canary_runs`. Внешние сигнатуры `cmd_canary`, `cmd_pool_seal`
   (после переноса — в `pool_seal.py`), `restore_pool_if_missing`,
   `pool_drift_warning` не меняются.
7. Внешнее поведение не меняется: вывод команд `canary --k N [--sha]`
   и `canary pool-seal`, поведение `init` и `doctor` (в частях,
   касающихся пула), тексты и порядок записей журнала, схема БД
   (`canary_runs`), имена и пути файлов пула и диагностики, формат
   запечатанного пула байт-в-байт (HMAC, openssl, GUID-манифест) —
   идентичны состоянию до переноса.
8. Обновить только импорты и пути патчей в `tests/test_canary.py`
   (~20 обращений к именам пула, диапазон :1492–1636, и два патча
   `canary.keychain` на :1567 и :1588 → `pool_seal.keychain`) и в
   `tests/test_doctor_canary_pool.py` (патч `doctor.canary.keychain`
   на :149 → `doctor.pool_seal.keychain`). Существующие ассерты этих
   тестов не меняются.
9. Регенерировать `docs/codebase-map.md` штатным
   `python3 scripts/codebase_map.py` после переноса (появится новый
   модуль `orchestrator/pool_seal.py`).
10. Не трогать: логику HMAC/шифрования и авторизации пула по существу
    (перенос дословный), `_ephemeral_clone`, `_drive_task`, поведение
    `--sha`, `orchestrator/runner.py::in_role_environment`,
    `orchestrator/answer.py:113` и `orchestrator/prune.py:80` (только
    упоминают `canary` в комментариях — не правятся).

## Критерии приёмки

AC-1. `orchestrator/pool_seal.py` существует и содержит функции
`_pool_dir`, `sealed_path`, `guids_path`, `_mac_key`, `_secret_fd`,
`_hmac_tag_hex`, `_openssl_encrypt`, `_openssl_decrypt`,
`_serialize_pool`, `_deserialize_pool`, `_authorized_pool_payload`,
`restore_pool_if_missing`, `pool_drift_warning`, `cmd_pool_seal`; их
тела идентичны телам в `orchestrator/canary.py` до переноса (перенос
дословный, без изменения логики).

AC-2. В `orchestrator/canary.py` этих тринадцати функций/имён больше
нет; модуль импортирует из `pool_seal` только то, что использует
(минимум `_pool_dir`). Импорты `hashlib`, `hmac`, `struct`, `uuid`,
`keychain` остаются в `canary.py` только если хотя бы одно
использование каждого из них сохранилось вне перенесённого кода.

AC-3. `orchestrator/artel.py:_cmd_canary` вызывает
`pool_seal.cmd_pool_seal()` (не `canary.cmd_pool_seal()`) для
подкоманды `pool-seal`.

AC-4. `orchestrator/catalog.py::cmd_init` делает ленивый импорт
`pool_seal` и зовёт `pool_seal.restore_pool_if_missing(conn)` (не
`canary.restore_pool_if_missing`).

AC-5. `orchestrator/doctor/cli.py` зовёт
`doctor.pool_seal.restore_pool_if_missing(conn)` вместо
`doctor.canary.restore_pool_if_missing(conn)`.

AC-6. `orchestrator/doctor/canary_pool.py::check_canary_pool_drift`
зовёт `doctor.pool_seal.pool_drift_warning()` вместо
`doctor.canary.pool_drift_warning()`.

AC-7. `orchestrator/doctor/__init__.py` импортирует `pool_seal` наряду
с `canary` в общем списке импортов пакета `orchestrator`, так что
`doctor.pool_seal.<имя>` разрешается тем же путём, что и
`doctor.canary.<имя>` сегодня.

AC-8. Прямой импорт каждого из модулей `orchestrator.canary`,
`orchestrator.pool_seal`, `orchestrator.catalog`, `orchestrator.doctor`
(например, `python -c "import orchestrator.doctor"` из корня
репозитория) завершается без `ImportError`/`ImportError: cannot import
name` о циклическом импорте.

AC-9. Сигнатуры `cmd_canary`, `cmd_pool_seal`, `restore_pool_if_missing`,
`pool_drift_warning` (модуль после переноса — `pool_seal` для трёх
последних) не изменились относительно состояния до переноса.

AC-10. Полный набор `tests/` зелёный после переноса (`pytest`), включая
`tests/test_canary.py` и `tests/test_doctor_canary_pool.py` с
обновлёнными путями импортов/патчей (в частности, патчи
`canary.keychain` → `pool_seal.keychain` и `doctor.canary.keychain` →
`doctor.pool_seal.keychain`) и без изменения существующих ассертов.

AC-11. `docs/codebase-map.md` регенерирован (`python3
scripts/codebase_map.py`) и несёт секцию для нового модуля
`orchestrator/pool_seal.py`.

AC-12. PLAN.md разработчика несёт таблицу переносов (функция → откуда
→ куда), подтверждение, что откат выполним ревертом одного merge-
коммита, и сравнение вывода `artel.py doctor` и `artel.py status` до и
после переноса (без изменяющих флагов); саму канарейку (`artel.py
canary`) в рамках этой задачи не гонять.

## Оценка объёма и деление
Сигналы: число затрагиваемых файлов зоны = 7 (`orchestrator/pool_seal.py`,
`orchestrator/canary.py`, `orchestrator/catalog.py`,
`orchestrator/artel.py`, `orchestrator/doctor/__init__.py`,
`orchestrator/doctor/cli.py`, `orchestrator/doctor/canary_pool.py`) —
на грани, `tests/` как зона считается отдельно; число критериев
приёмки = 12 (≥ 10) — сигнал сработал.

Обоснование монолита: перенос дословный (без изменения логики) и все
затронутые точки взаимозависимы одним общим действием — переименованием
источника импорта `_pool_dir`/`restore_pool_if_missing`/
`pool_drift_warning`/`cmd_pool_seal`. Разрезать по границам зон
невозможно без промежуточного нерабочего состояния: пока `canary.py`
несёт старые функции, а хотя бы один потребитель (`catalog.py`,
`artel.py`, `doctor/*`) уже переключён на несуществующий `pool_seal`,
`cmd_init`/`doctor`/`canary pool-seal` падают с `ImportError`. Атомарная
смена источника импорта для всех потребителей — необходимое условие
зелёной планки; часть без остальных не мержима.

## Не входит
- Логика HMAC/шифрования и авторизации пула по существу (только
  дословный перенос кода, не переработка).
- `orchestrator/runner.py::in_role_environment` — рубеж роли, не
  трогается.
- `_ephemeral_clone`, `_drive_task` — остаются в `canary.py` как есть.
- Поведение флага `--sha`.
- Правки `orchestrator/answer.py:113`, `orchestrator/prune.py:80`
  (только комментарии, упоминающие `canary`).
- Любые попутные улучшения вне переноса (переименование,
  реструктуризация тестов сверх правки импортов/патчей, изменение
  формата запечатанного пула).
- Прогон самой канарейки (`artel.py canary`) — только смоук `doctor`/
  `status`.

## Материалы
- docs/audits/code-revision-2026-09-13.md, находка CR-2026-09-13-4 ★.
- tasks/01M2CN42RV0EBBP7HS4HP2VNY1/TZ.md.
