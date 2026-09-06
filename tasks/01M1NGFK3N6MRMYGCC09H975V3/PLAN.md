---
task: 01M1NGFK3N6MRMYGCC09H975V3
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: Канарейка v2 (часть 2): привязка пина к зелёной канарейке, триггер doctor, откат пина

## Подход

Часть 1 (01M1NEEWH5K1XPFRDGRMPYSBXJ) завела журнал прогонов канарейки
(`canary_runs`) без понятия «зелёный»/«старый» — эта задача привязывает
к нему три существующие точки (`pin-update`, `doctor`, новую `pin --to`)
ровно так, как это зафиксировал ANSWER-1 (Оператор, ответ на эскалацию
test_author этой задачи).

**Журнал становится зелёным/красным.** `store.insert_canary_run`
получает два новых keyword-параметра, `main_sha`/`verdict`
(по умолчанию `None` — сигнатура для вызывающих кода до этой задачи не
меняется). Колонки добавлены `add_column`'ом ВНУТРИ `_ensure_canary_tables`
(не в общем `migrate()`, ANSWER-1 п.2) — та же идемпотентная миграция,
что и у прочих колонок `store.py`, но привязанная к тому же ленивому
месту создания таблицы, каким уже заведена сама `canary_runs`
(докстринг `_ensure_canary_tables`: таблица не входит в универсальную
SCHEMA сознательно). `orchestrator/canary.py::_run_one_task` заполняет
оба поля при записи строки: `main_sha` — HEAD `config.ROOT` СНАРУЖИ
эфемерного клона (тот же момент, где уже пишется сама строка журнала —
клон к этому времени закрыт, `config.ROOT` уже настоящий пульт, не
подмена); `verdict` — `'green'`, если `_drive_task` дошла до
`merge_gate`/`verifying` и была убита штатно ИМЕННО там (не потолком
эскалаций/буксования), и маркер «ожидается эскалация» совпал с фактом
— иначе `'red'`. Для этого `_drive_task` теперь ВОЗВРАЩАЕТ маркер
исхода (`"merge_gate"`/`"verifying"`/`"inconclusive"`/`"other"`) вместо
`None` — единственный способ различить «прошла приёмку» от
«`_kill_inconclusive`», раз оба пути заканчиваются одним и тем же
`t["state"] == "killed"` в `_task_metrics`.

**Общая арифметика возраста — одна функция, не две копии.** AC-1
(`pin-update`) и AC-3/AC-4 (`doctor`) сравнивают ОДНО и то же число
(«сколько мержей main с последнего зелёного прогона») с ОДНИМ и тем же
порогом `config.CANARY_MAX_MERGES_SINCE_GREEN` (новая именованная
константа, дефолт 10 — ANSWER-1 п.3). Арифметика — новая функция
`orchestrator/canary.py::merges_since_last_green_run(conn, target_sha)`:
перебирает зелёные прогоны (`store.green_canary_runs`, самые свежие
первыми), отбрасывает те, чей `main_sha` не предок `target_sha`
(`gitcmd.is_ancestor`, новая обёртка над `merge-base --is-ancestor`),
берёт МИНИМАЛЬНЫЙ возраст (`gitcmd.merges_between`, новая обёртка над
`rev-list --count --merges S..T`) среди оставшихся; `None` — прогонов,
подходящих под фильтр, нет вовсе (пустой журнал — тот же вырожденный
случай, ANSWER-1 п.3: «сравнивать не с чем» ⇔ «порог всегда
достигнут»). И `pin.cmd_pin_update` (гейт ПОСЛЕ `fetch`, но ДО `merge`
— REVIEW.md итерации 1, R1-F1: `merge-base`/`rev-list` нуждаются в
локальном объекте целевого `sha`, который обычно принесёт как раз
`fetch`; `fetch` сам HEAD не двигает, так что «отказ не трогает HEAD»,
ANSWER-1 п.4, соблюдено и в этом порядке), и `doctor.check_canary_trigger`
(новый check, `all_checks`) зовут ЭТУ функцию — при будущей правке
порога/алгоритма место одно, не два.
Импорт `canary` в `pin.py`/`doctor.py` не создаёт цикл: ни `canary.py`,
ни модули, которые оно импортирует на уровне модуля (`fsm`, `auto`,
`runner`, `catalog`, ...), не импортируют `pin`/`doctor` на уровне
модуля (`runner.py` импортирует `doctor` только ЛОКАЛЬНО внутри
функции — проверено `python3 -c "import orchestrator.doctor"` и
аналогично для `pin`/`canary`/`artel` без ошибок).

`doctor.check_canary_trigger` возвращает статус `warn`, не `fail`: `fail`
— единственный статус, из-за которого `cmd_doctor` завершается `sys.exit(1)`
(см. хвост `cmd_doctor`), а триггер (docs/triggers.md: «ack обязан
нести решение», не блокирует прогон как инцидент) иначе держал бы
КАЖДЫЙ прогон doctor красным до самого первого прогона канарейки —
тот же приём деградации до `warn`, что уже несёт соседний
`check_root_pin`. Замечено регрессией `tests.test_doctor.
DoctorCommandTest.test_healthy_repo_prints_ok_and_does_not_exit` при
первой попытке со статусом `fail` — тест сам не менялся, изменена
только реализация check'а.

**`pin --to`** — новая функция `pin.cmd_pin_to(sha: str | None)`
(ANSWER-1 п.5) и новая CLI-команда `pin` (не подформа `pin-update`,
`orchestrator/artel.py::_cmd_pin`, тот же приём разбора флага, что уже
несёт `_cmd_pause` для `pause --now`). Явный `sha` — обязан быть
предком текущего HEAD (`gitcmd.is_ancestor`, та же обёртка, что и у
гейта выше) — `git reset --hard <sha>` на `config.ROOT`, БЕЗ
`fetch`/`push` (ADR-0013 ч.3: main пульта на origin не трогается ни в
одном случае). Без `sha` — цель `store.latest_green_canary_run`
(новая функция `store.py`, первая строка `green_canary_runs`, самый
свежий по `created_at`) без фильтра по предковости/возрасту (AC-6 не
требует такого фильтра для default-пути — только «последний ЗЕЛЁНЫЙ»,
не «последний зелёный и достаточно свежий», это разные требования: AC-1
про ПОРОГ обновления, AC-6 про ВЫБОР цели отката). Каждый вызов —
ровно одна запись журнала (`_refuse_rollback`/успешная ветка), успешная
или отказ — общий небольшой helper `_refuse_rollback` в `pin.py`
journал'ит и `sys.exit`'ит одним вызовом, чтобы не дублировать пару
строк на каждый из трёх отказов.

## Шаги

1. `orchestrator/config.py` — именованная константа
   `CANARY_MAX_MERGES_SINCE_GREEN` (дефолт 10, ANSWER-1 п.3).
2. `orchestrator/gitcmd.py` — `is_ancestor`/`merges_between`, тем же
   стилем деградации на `None`/`False`, что и соседний `commits_behind`.
3. `orchestrator/store.py` — `main_sha`/`verdict` в `_ensure_canary_tables`
   (идемпотентный `add_column`) и `insert_canary_run`; новые
   `green_canary_runs`/`latest_green_canary_run`.
4. `orchestrator/canary.py` — `_drive_task` возвращает маркер исхода;
   `merges_since_last_green_run` (общий guard); `_run_one_task`
   вычисляет и передаёт `main_sha`/`verdict`.
5. `orchestrator/pin.py` — гейт AC-1/AC-2 в `cmd_pin_update` (до
   fetch/merge); новая `cmd_pin_to` (AC-5/AC-6/AC-7).
6. `orchestrator/doctor.py` — новый `check_canary_trigger` (AC-3/AC-4),
   включён в `all_checks`.
7. `orchestrator/artel.py` — новая CLI-команда `pin --to [<sha>]`
   (`_cmd_pin`), обновлён докстринг команд.
8. Юнит-тесты (`tests/test_pin.py`, новый файл; `tests/test_gitcmd_branch_reads.py`,
   `tests/test_canary.py`, `tests/test_doctor.py` — точечные добавления)
   на всё из шагов 2-6, не покрытое приёмочными тестами дословно
   (граничные случаи `is_ancestor`/`merges_between`, `_drive_task`
   возвращает `"other"`/`"inconclusive"` отдельно от verdict-логики,
   `check_canary_trigger` статус `warn`/дедуп алерта).
9. `python3 scripts/codebase_map.py` (правка `.py` в `orchestrator/`) +
   `scripts/guard.py` по артефактам задачи + прогон затронутых модулей
   `tests/` (не полный набор — гоняет CI).
10. ANSWER-2 (Оператор, возврат из `verifying`): `tests/sandbox.py::
    RealGitSandbox.setUp` — `.gitignore` (`.artel/`) в самом первом
    коммите песочницы, ДО `store.create_schema(store.db())`.

## Покрытие требований

| Требование (SPEC) | Шаг |
|---|---|
| 1 (`pin-update` отказывает без свежего зелёного прогона) | 1, 2, 3, 4, 5 |
| 2 (`doctor` — триггер `kind=trigger` по тому же порогу) | 1, 2, 3, 4, 6 |
| 3 (`pin --to <sha>`/`pin --to` — откат, main не трогается) | 3, 5, 7 |
| 4 (каждый откат — отдельная запись журнала) | 5 |

## Влияние на систему

Затронуты: `orchestrator/store.py` (сигнатура `insert_canary_run`
расширена двумя keyword-параметрами со значением по умолчанию `None` —
существующий вызыватель `canary.py:441` передаёт их явно новой веткой
кода этой же задачи, других вызывателей в кодовой базе нет, проверено
`grep -rn "insert_canary_run" orchestrator/ tests/`); `orchestrator/
canary.py` (`_drive_task` меняет тип возврата `None` → `str` —
единственные вызыватели, `tests/test_canary.py`, не читают возврат,
проверено); `orchestrator/pin.py` (`cmd_pin_update` получает
ДОПОЛНИТЕЛЬНУЮ проверку ПЕРЕД существующим телом — тело не меняется,
регресс AC-2 приёмочным тестом подтверждён зелёным); `orchestrator/
doctor.py` (новый check аддитивен в `all_checks`, статус `warn` —
не блокирует существующий контракт `cmd_doctor` exit-кода, регресс
`tests.test_doctor.DoctorCommandTest` подтверждён зелёным);
`orchestrator/artel.py` (новая команда `pin` — не пересекается с
существующей `pin-update`, разные строки диспетчера).

ANSWER-2 (Оператор, шаг 10): `tests/sandbox.py::RealGitSandbox.setUp` —
CI-репорт (коммит `231a7e0a`, джоб «Синтаксис и тесты оркестратора»)
показал `tests/test_gitcmd_check_ignore.py::DiffNamesTest::
test_lists_changed_paths` красным ТОЛЬКО в полном прогоне `tests/` — в
списке изменённых путей появлялись `.artel/state.db(-shm/-wal)`.
Причина структурная, не в конкретном новом тесте этой задачи (все
новые классы `tests/test_pin.py`/`tests/test_doctor.py`/`tests/
test_gitcmd_branch_reads.py`/`tests/test_canary.py` уже подменяют
`config.ROOT`/`config.DB` — перечитано построчно): `RealGitSandbox.
setUp` кладёт настоящую sqlite-БД (`store.create_schema`, WAL-режим —
`store.enable_wal`) ВНУТРЬ `self.root`, того же git-дерева, которое
подклассы коммитят `git add -A` — без `.gitignore` в песочнице (в
отличие от настоящего пульта, где `.artel/` исключён корневым
`.gitignore`) любой подкласс с БОЛЕЕ чем одним коммитом и сверкой их
разницы (`gitcmd.diff_names`) рискует поймать в диф WAL/SHM-файл БД,
если его содержимое на диске успело измениться между коммитами
(гонка контрольной точки WAL — не воспроизвелась стабильно локально
ни разу за несколько прогонов полного набора, но структурная причина
одна и та же, что бы её ни триггерило на раннере CI). Один пример
такой защиты УЖЕ был в кодовой базе точечно (`tests/
test_gitcmd_check_ignore.py::CheckIgnoreTest.setUp` сама пишет
`.gitignore` с `.artel/` до своих коммитов) — шаг 10 переносит ту же
защиту в БАЗОВЫЙ класс, единожды, для всех подклассов `RealGitSandbox`
(их больше 15 в `tests/`), а не полагается на то, что каждый новый
подкласс вспомнит сделать это сам. Не является ослаблением/новым
инвариантом — тестовая инфраструктура, не код продукта; поведение
`gitcmd.diff_names`/`check_ignore` и самого продукта не меняется,
только добавляется файл в git-дерево ВРЕМЕННОЙ песочницы теста.
Регресс: полный `tests/discover` дважды подряд зелёный (кроме заранее
известного нестабильного `tests.test_liveness.
TerminateProcessGroupTest.test_kills_the_leader_and_returns_a_positive_count`
— таймингового теста сигналов процесса, вне зоны этой задачи и не
упомянутого в ANSWER-2).

Инварианты/гейты рядом: инвариант 35 (без сети в тестах/офлайн-путях) —
`check_canary_trigger`/`merges_since_last_green_run` читают только
ЛОКАЛЬНЫЙ `config.ROOT` (`git merge-base`/`rev-list`, без `fetch`),
ANSWER-1 п.3 буквально требует этого для `doctor`. Принцип целостности:
ни один существующий тест/гейт/лимит не ослаблен — гейт `pin-update`
СТРОЖЕ прежнего поведения (новый отказ добавлен, старый путь без
изменений при пройденном гейте, AC-2 это явно требует и приёмочный
тест это проверяет), `check_canary_trigger` — новый аддитивный check,
`pin --to` — новая команда, не изменяющая поведение существующих.

Откат: `git revert` коммита(ов) этой ветки — колонки `main_sha`/
`verdict` в `canary_runs` остаются в схеме неиспользуемыми (тот же
прецедент, что и у прочих аддитивных миграций `store.py` — колонки не
удаляются откатом кода, только добавляются). `pin-update` без отката
кода вернулся бы к поведению без гейта; `pin --to` как команда исчезнет
из диспетчера `artel.py`.

## Риски

`_run_one_task` теперь вызывает `gitcmd.head_sha()` СНАРУЖИ
`_ephemeral_clone()` (после его выхода) — тот же порядок, в котором уже
читается `outer_conn = store.db()` парой строк выше; `_ephemeral_clone`
восстанавливает атрибуты `config` в `finally` даже при исключении
внутри блока, так что `config.ROOT` к этому моменту гарантированно
настоящий пульт, не клон (проверено чтением `_ephemeral_clone`,
дополнительно — зелёными `tests/test_canary.py`, которые уже
покрывают этот контекстный менеджер).

## Возврат — подтяжка после 01M1TKP269 и разреза doctor

Возврат из `merge_gate` (решение Оператора 06.09): ветка отстала от
main на 445+ коммитов, три зоны задачи (`canary.py`, `doctor.py`,
`pin.py`) за это время переписаны независимыми задачами. `git merge
origin/main` — конфликты только в четырёх местах (`docs/codebase-map.md`
— взят origin, перегенерирован отдельно шагом 9 методики; `orchestrator/
artel.py` — докстринг списка команд, объединены обе половины;
`orchestrator/canary.py` — три хунка; `orchestrator/doctor.py` —
modify/delete). `config.py`, `store.py`, `gitcmd.py`, `pin.py`,
`tests/sandbox.py`, `tests/test_canary.py`, `tests/test_doctor.py`
смержились автоматически без конфликта — наши добавления (`CANARY_MAX_
MERGES_SINCE_GREEN`, `is_ancestor`/`merges_between`, `green_canary_runs`/
`latest_green_canary_run`/`insert_canary_run(main_sha=, verdict=)`,
`cmd_pin_to`, ANSWER-2 `.gitignore` в `RealGitSandbox`) физически не
пересекались построчно с параллельной работой на main.

Три правки причины возврата:

1. **Разрез `doctor.py` → пакет `orchestrator/doctor/`**
   (01M1TT9BPBRYMDXXEWVZSRG51V, уже смерженная в main задача): взял
   пакет `orchestrator/doctor/` origin/main целиком (`git checkout
   origin/main -- orchestrator/doctor/`), удалил монолитный `orchestrator/
   doctor.py`. `check_canary_trigger` (AC-3/AC-4) перенесён дословно (та
   же арифметика, тот же фиксированный текст алерта для дедупа — REVIEW.md
   итерации 1, R1-F2) в `orchestrator/doctor/canary_pool.py` (тематически
   соседствует с `check_canary_pool_drift`/`check_role_log_pool_leak` —
   тоже канареечные проверки), обращения к коллаборантам переписаны на
   фасадный приём пакета (`doctor.gitcmd`, `doctor.canary`, `doctor.
   config`, `doctor.alerts`, `doctor.Check` — не отдельный импорт в
   подмодуле, докстринг `orchestrator/doctor/__init__.py`). Зарегистрирован
   в `orchestrator/doctor/__init__.py` (импорт из `.canary_pool`) и в
   `orchestrator/doctor/cli.py::all_checks` (рядом с `check_canary_pool_
   drift`). Тесты `tests/test_doctor.py::CanaryTriggerCheckTest`
   обращаются к `doctor.check_canary_trigger` — атрибут пакета, путь
   вызова не изменился с точки зрения теста.

2. **Verdict через смерженное понятие штатного исхода, не через
   `reached in (merge_gate, verifying)`**: `_drive_task` (ANSWER-1 п.2,
   исходная реализация) возвращал маркер `"merge_gate"`/`"verifying"`/
   `"inconclusive"`/`"other"` — на main за это время `_drive_task` вообще
   перестал возвращать что-либо осмысленное (ADR-0015: `verifying`
   переставлен ПЕРЕД ревьювером и с тех пор проходится синтетически,
   `_pass_verifying`, не убивает задачу), а различение штатного исхода
   от «не сошлась» переехало в отдельную пару `_kill_outcome_note`/
   `_needs_diagnostics` (уже покрыты `NeedsDiagnosticsTest`, 4/4 сочетаний
   истинности). Правка: `_drive_task` вернулась к сигнатуре `-> None` без
   маркеров (все `return "..."` — на голый `return`), `state ==
   "verifying"` ведёт через `_pass_verifying`/`continue` (не через
   старую `_kill_at_verifying`/`return`). `_run_one_task` считает
   `verdict = "green" if not _needs_diagnostics(normal_outcome, mismatch)
   else "red"` — `normal_outcome`/`mismatch` уже вычислены той же
   функцией для собственной логики диагностики/бейзлайна двумя строками
   выше, переиспользованы, не задублированы.

3. **`verifying` не конечная точка — не считать зелёным**: прямое
   следствие пункта 2 — раз `_pass_verifying` не убивает задачу, а ведёт
   её дальше в `review`, реальное вождение канарейки сегодня может
   закончиться штатным killed ТОЛЬКО на `merge_gate`
   (`_kill_outcome_note` признаёт «штатно» ещё и недостижимый из
   `_drive_task` `_kill_at_verifying` — оставлен нетронутым ради чужой
   залоченной планки, REVIEW.md 01M1TKP269W9JN3NBJCR5Q6C3B итерации 2,
   R2-F1, править её эта задача не вправе). Отдельного кода для этого
   пункта не потребовалось — устраняется тем же изменением, что и пункт 2.

Обновлённые тесты `tests/test_canary.py`: `DriveTaskReachedGateMarkerTest`
(тестировал сам убранный маркер) заменён на `RunOneTaskVerdictUsesNormal
OutcomeTest` (таблица истинности verdict = `not _needs_diagnostics(...)`
— та же матрица, что и `NeedsDiagnosticsTest`, явно как формула verdict'а);
две ссылки на `result = canary._drive_task(...)` /
`assertEqual(result, "inconclusive")` в `DriveTaskEscalationCapTest`/
`DriveTaskStallCapTest` убраны — функция больше ничего не возвращает.

Требования SPEC 1-4/AC-1..AC-8 — без изменений, реализация не
пересматривалась по существу, только адаптирована под изменившиеся
зоны main.

## Предложения системе
