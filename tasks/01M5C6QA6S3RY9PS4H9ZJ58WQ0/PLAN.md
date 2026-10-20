---
task: 01M5C6QA6S3RY9PS4H9ZJ58WQ0
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Механика канарейки, часть А — реестр живого прогона, окно тишины, мерж и обходы окна

## Подход
Реестр живого прогона живёт в `orchestrator/canary.py` (зона задачи; нового
модуля вне зон не заводим): каталог `config.ROOT/.artel/<config.CANARY_LIVE_DIRNAME>`
считается от `config.ROOT` в момент вызова — песочница подменяет его через
`ROOT` из `ALL_CONFIG_ATTRS`, правка `tests/sandbox.py` не нужна.

- Запись: файл `<run_stamp>-<pid>.json` (pid, время старта процесса из
  `doctor.stale_cycles.process_start_time`, `run_stamp`, sha, набор, время
  начала, число задач), пишется атомарно (tmp + `os.replace`). Рядом —
  метка `<run_stamp>.lock`, создаётся `O_CREAT|O_EXCL` ДО записи; метка
  уже есть — отказ «canary: прогон <run_stamp> уже идёт», чужие файлы не
  трогаются. Снятие — `finally` контекстного менеджера; путь запомнен при
  записи (во время ведения `_ephemeral_clone` уводит `config` на клон).
- `cmd_canary`: после выбора sha и `run_stamp` — `_interrupt_on_signal`
  снаружи, менеджер реестра внутри (сигнал на любом участке снимает
  запись); новый необязательный параметр-приёмник `on_run_stamp` (вызов
  `on_run_stamp(run_stamp)` до первой строки и до первого клона);
  возврат — `run_stamp`.
- Чтение: `canary.live_runs()` — сверка pid (`liveness._pid_alive`, без
  правки `owner_alive`), времени старта с допуском `_LSTART_SPAN`
  (`None` при сверке — живая), возраста против
  `CANARY_DRIVE_TIMEOUT_SEC × задач + час`. Не живые и нечитаемые записи
  убираются вместе с меткой (если метка их pid) и пишут строку журнала
  пульта без задачи.
- Потребители зовут `canary` лениво (импорт внутри функции): `canary`
  импортирует `pool_seal`→`notes` и `fsm` — циклы импорта.
  Общие помощники в `canary`: `live_run_note(default_set_only)` — «идёт
  канарейка <run_stamp> на <sha7>», `window_bypass_refusal`,
  `DURING_CANARY_FLAG`, текст отказа пустого основания.
- `notes._silence_window_reason` — первой проверкой живой прогон любого
  набора. `note`/`doc-commit` принимают `--during-canary` (argparse
  `nargs="?", const=""`, идиома `--accept-red`); пустое основание — отказ
  сразу после разбора. `note --now`/`--flush`, `doc-commit --flush` при
  живом прогоне без флага — отказ текстом требования 8, с флагом — строка
  журнала пульта с основанием и прежний путь.
- `canary pool-seal` — `cmd_pool_seal(during_canary=None)`, разбор флага в
  `artel._cmd_canary`; та же проверка в начале команды.
- `approve`: `artel._during_canary_arg` по образцу `_fixes_main_arg`,
  флаг и основание — в `_approve_reason_indices`; `fsm.cmd_approve(...,
  during_canary=None)`; не на `merge_gate` — отказ по образцу
  `--no-answer`; на `merge_gate` основание доезжает до тела окна мержа
  только когда передано (kwargs, чтобы заглушки тела в существующих тестах
  с прежней сигнатурой не падали). В `_cmd_approve_merge_gate`
  непосредственно перед `_push_merged_main` — `_refuse_during_canary`:
  задача артели и живой прогон набора по умолчанию — журнал задачи и
  `sys.exit` текстом требования 5 (мьютекс снимает `finally` цикла); с
  флагом — строка журнала задачи с основанием.
- `artel._cmd_canary --result-file`: строки `canary_runs` отбираются по
  `run_stamp`, полученному приёмником, а не по номеру строки.

## Шаги
1. `config.CANARY_LIVE_DIRNAME`; реестр, чтение, помощники и правка
   `cmd_canary` в `orchestrator/canary.py`.
2. Окно тишины и обходы в `orchestrator/notes.py`; `pool_seal.cmd_pool_seal`.
3. Флаг в `orchestrator/artel.py` (approve, pool-seal, файл результата),
   `orchestrator/fsm.py`, проверка в `orchestrator/fsm_merge_gate.py`.
4. Свои юнит-тесты на свойства вне долгоживущих файлов —
   `tests/test_canary_live_registry_units.py`: основание `--during-canary`
   не читается как sha; нечитаемая запись реестра убирается с журналом;
   метка чужого pid того же `run_stamp` при уборке не снимается (обе
   заявки мутации проверены временной мутацией — тест краснел). Карта
   `scripts/codebase_map.py`, прогон долгоживущих файлов задачи (21 тест,
   зелёные) и тестов затронутых модулей (canary*, notes*, doc_commit*,
   merge_gate*, approve*, merge_queue, invariants — 726 тестов, зелёные).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 2 |
| 5 | 3 |
| 6 | 2, 3 |
| 7 | 3 |
| 8 | 2 |
| 9 | 3 |
| 10 | 1, 2, 3 |
| 11 | 4 |

## Влияние на систему
- Новая поверхность — каталог `.artel/canary-live/` вне git; без живого
  прогона все потребители видят пустой список, поведение прежнее
  (требование 10). Ни один гейт, тест или лимит не ослабляется:
  проверка мержа — дополнительный отказ перед push, окно тишины — ещё
  один триггер.
- `liveness.owner_alive`, `CANARY_OWNER_MARKER`, `stale_cycles` не
  меняются (только вызов).
- Сигнатуры `cmd_approve`, `cmd_pool_seal`, `cmd_canary`,
  `_cmd_approve_merge_gate(_cycle)` расширены только необязательными
  параметрами.
- Откат — revert одного merge-коммита; каталог реестра эфемерен.

## Риски
- Зависание записи после SIGKILL прогона держит окно до сверки pid —
  сверка pid/старта снимает её первым же чтением.
- Ложная «живость» при переиспользовании pid отсекается временем старта.

## Предложения системе
- `pytest -n` (xdist) в окружении шага роли падает «node down: Not
  properly terminated» на старте — скил coding-standards советует только
  последовательный прогон, но причина не записана нигде.
- `from orchestrator.doctor import stale_cycles` даёт функцию (фасад
  реэкспортирует одноимённое имя), а не модуль — ловушка для любого
  потребителя `_LSTART_SPAN`; кандидат в карточку знаний.

Полный набор: suite-run №1 — прошло 6181, упало 0, пропущено 2.
