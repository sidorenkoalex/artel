---
task: 01M2B6JS2BZNBW9WSHT1RPFXTE
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: note — окно тишины (удержание строк копилки во время живых циклов)

## Подход

Добавлена именованная константа `config.NOTE_SILENCE_WINDOW_STATES`
(ровно пять состояний из SPEC, с комментарием — AC-1) и функция
`notes._silence_window_reason()`: живой держатель `merge_locks` (тот же
признак живости, что `merge_lock._holder_is_dead`) ЛИБО хоть одна задача
(`store.all_tasks`) в состоянии из константы — условие ИЛИ, любой из двух
триггеров независимо открывает окно.

Порядок операций «валидация до окна» (требование 2, AC-4) обеспечен
разделением прежнего `_attempt` на две чистые функции: `_fetch_and_build`
(fetch+checkout+`_build_for` — валидация и здесь же `sys.exit` при отказе)
и `_commit_and_push` (запись+commit+push уже построенной правки). `_run`
(путь одной новой заметки) вызывает `_fetch_and_build` первым, и только
ПОСЛЕ успешной валидации проверяет окно — открыто, кладёт исходный
`request` (не построенный текст) в `.artel/notes-pending/` через уже
существующий `_hold_pending` (тот же формат/каталог, AC-9) и печатает
сообщение; закрыто — коммитит и пушит как раньше, с тем же повтором
non-fast-forward. `_attempt` (используется только `_flush_pending`)
использует те же две функции без понятия окна — окно уже решено
вызывающим кодом.

`cmd_note` меняется минимально: оппортунистический флаш в начале
(`if args.flush or _silence_window_reason() is None: _flush_pending()`)
— короткое замыкание `or` не даёт explicit `--flush` зависеть от окна
(AC-6), а обычный вызов допушивает удержанное только вне окна (AC-8).
Добавлен флаг `--now <раздел>` (те же `choices`, что позиционный
`section`) — диспетчер зовёт `_run(..., bypass_window=True)` (AC-7),
`--flush` как раньше просто вызывает `_flush_pending()` безусловно (уже
вызванной в начале `cmd_note`) и возвращается.

Тесты `tests/test_notes.py` дополнены стендом `NoteSilenceSandbox`
(настоящий git, bare origin — по образцу `RealGitSandbox`, независимо от
залоченных `tasks/<id>/acceptance_tests/`, которые материализуются
только на время задачи) с покрытием AC-1..AC-9, включая явно требуемый
SPEC случай «живой держатель `merge_locks` без единой задачи в
состояниях набора» (AC-1) и «`escalated` не входит в набор» (AC-5).
Существующие тесты `tests/test_notes.py` не тронуты по существу — только
`CmdNoteArgumentValidationTest.setUp` получил `store.create_schema`:
`cmd_note` теперь читает `merge_locks`/`tasks` на КАЖДЫЙ вызов
(оппортунистический флаш выше), без схемы это падало бы
`sqlite3.OperationalError` раньше ожидаемого `SystemExit` разбора
аргументов — не ослабление проверок, только фикстура под новое поведение.

## Шаги

1. `orchestrator/config.py`: константа `NOTE_SILENCE_WINDOW_STATES`.
2. `orchestrator/notes.py`: `_silence_window_reason`; разбивка `_attempt`
   на `_fetch_and_build`/`_commit_and_push`; `_run(request,
   bypass_window=False)` с проверкой окна между валидацией и push;
   `--now` в `_parse_args`; `cmd_note` — оппортунистический флаш
   уважает окно, диспетчер `--now`.
3. `tests/test_notes.py`: фикстура схемы в `CmdNoteArgumentValidationTest`;
   `NoteSilenceSandbox` + тесты AC-1..AC-9.
4. `docs/codebase-map.md`: регенерация (`scripts/codebase_map.py`) —
   правка `.py` в `orchestrator/`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (окно тишины: держатель ИЛИ состояние, константа) | 1, 2 |
| 2 (валидация до окна) | 2 |
| 3 (удержание в `.artel/notes-pending/`, сообщение) | 2 |
| 4 (вне окна — как сегодня) | 2 |
| 5 (`--flush` обходит окно) | 2 |
| 6 (`--now` обходит окно) | 2 |
| 7 (оппортунистический допуш уважает окно) | 2 |
| 8 (порядок отправки по имени файла) | 2 (не менялось, `_pending_paths` уже сортирует) |

## Влияние на систему

Затронуты только `orchestrator/notes.py` (команда `note`) и
`orchestrator/config.py` (новая константа, существующие не менялись).
`store.py`/`pull.py`/`fsm_merge_gate.py` не тронуты (SPEC «Не входит»).
Новый путь `notes.py` читает `merge_locks`/`tasks` через уже
существующие `store.merge_lock_row`/`store.all_tasks` и `merge_lock.
_holder_is_dead` — используется как чтение, ни одна из этих таблиц/
функций не меняется и не ослабляется. Поведение без открытого окна
(наиболее частый случай) не меняется — та же цепочка fetch/build/
commit/push с тем же числом попыток `MAX_PUSH_ATTEMPTS`, только
разложенная на две функции. Формат/каталог удержания (`_hold_pending`,
`.artel/notes-pending/*.json`) переиспользован без изменений — `doctor.
check_pending_notes` и существующие потребители `pending_notes()`
не задеты. Откат — правка этой же пары файлов, `_silence_window_reason`
самодостаточна и ничего не пишет.

## Риски

Оппортунистический флаш и путь `_run` теперь безусловно читают БД
(`store.db()`) на каждый вызов `note`, включая случаи, где раньше
дело ограничивалось разбором аргументов (без сети/БД вовсе) — на
проде это не проблема (БД уже заведена `init` до первого `note`), но
потребовало починки фикстуры одного тестового класса (см. «Подход»).

## Предложения системе

(пусто)
