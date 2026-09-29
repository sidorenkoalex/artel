---
task: 01M3PKSWPETC49WFTFZ69GH3F2
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Канарейка исполняет код проверяемого коммита, а не код пина (ADR-0021, этап 0)

## Подход

Вход — новый модуль `orchestrator/canary_drive.py`, запускаемый пультом как
`sys.executable -m orchestrator.canary_drive --template <шаблон> --result
<файл> --venv-dir <venv пульта> [--codex-home <каталог>]` с рабочим каталогом
— эфемерным клоном. Запуск модулем (`-m`), а не путём к файлу: первым в
`sys.path` процесса стоит клон, и весь пакет `orchestrator` (а с ним
`scripts/guard.py`) приходит из проверяемого коммита. `config.ROOT` в этом
процессе вычисляется от расположения модуля, то есть это клон — переадресация
путей `_CLONE_CONFIG_ATTRS` там не нужна. Обёртку-подкоманду в `artel.py` не
заводил: `artel.py` не тронут.

Процесс клона делает то, что раньше делал пульт внутри
`_run_task_in_ephemeral_clone`: `catalog.cmd_new(..., canary=True)`,
`workspace.ensure`, `canary._drive_task` (помощники гейтов, подъём потолка,
потолок повторов developer, синтетический ANSWER — все его СОБСТВЕННОЙ копией
`canary.py`), затем `canary._task_metrics`. Результат — один JSON-объект,
записанный через временный файл и `os.replace` в файл, путь которого передал
пульт: `task_id`, `head` (HEAD клона, снятый до заведения задачи), `outcome`,
`escalated` (булево — фактическая эскалация), `metrics` (словарь
`_task_metrics`), `steps` (строки журнала `ts/actor/action/detail`). Вывод
процесса — только диагностика: он пишется в файл `.artel/canary-drive.log`
клона (не в канал — канал, не читаемый часами, повесил бы процесс).

Помощники ведения (`_drive_task`, `_pass_*`, `_kill_*`, `_raise_task_ceiling`,
`_task_metrics` и т.д.) остаются в `orchestrator/canary.py` без правки: пульт
их больше не вызывает, их исполняет процесс клона своей копией модуля. Так
ведение идёт «тем же порядком, что `_drive_task`» буквально тем же кодом, а
тесты этих помощников продолжают проверять ровно ту логику, которую исполняет
клон (см. «Переписанные тесты» ниже).

Пульт (`_run_task_in_ephemeral_clone`, фаза 1):
- проверяемый sha снимает ДО клона (явный `--sha` либо `gitcmd.head_sha()`);
- в блоке `_ephemeral_clone` (не изменён: клон, origin-заглушка, `cmd_init`,
  слой моделей, вход Codex) проверяет наличие `orchestrator/canary_drive.py`
  в клоне; нет — `sys.exit` с текстом «коммит <sha> не несёт входа … не умеет
  вести учебную задачу своим кодом (ADR-0021, этап 0)» до заведения задачи,
  возврата к ведению кодом пина нет;
- `_drive_in_clone` запускает процесс в своей группе (`start_new_session`) с
  `PYTHONUNBUFFERED=1` (вывод в файл не теряется в буфере при снятии
  сигналом) и ждёт `proc.wait(timeout=CANARY_DRIVE_TIMEOUT_SEC)`; по таймауту
  — и при любом другом прерывании ожидания (Ctrl-C, `SystemExit`, ветка
  `except BaseException` с повторным `raise`) — снимает всю группу
  `liveness.terminate_process_group` (шаги ролей — потомки процесса, а своя
  сессия SIGINT терминала не получает);
- `_read_drive_result` разбирает файл и проверяет все поля, которые читают
  следующие фазы; нет файла / не JSON / не объект / нет поля — причина, не
  исключение;
- код выхода ≠ 0, снятие по времени или неразборчивый результат —
  `_save_drive_failure` (вывод процесса + причина в
  `_diagnostics_dir(outer_root, run_stamp, <id задачи или имя шаблона>)`) и
  исключение `CanaryDriveFailed` изнутри блока клона — клон и origin-заглушку
  убирает тот же `finally`;
- штатный результат — прежний 9-элементный кортеж фазы 1. Форма кортежа
  сохранена (её держат подмена фазы 1 в
  `tests/test_canary_codex_clone_auth.py::PhaseOneCodexAuthArgumentTest` и
  залоченная планка 01M3GKJFN90ATK2KECNDZXPPP6), поэтому HEAD клона едет к фазе
  3 в `metrics["code_sha"]` (рядом проверяемый — `metrics["target_sha"]`).
  Расхождение HEAD клона с проверяемым делает исход не штатным
  (`normal_outcome=False`): вердикт не `green` прежней формулой
  `_run_verdict`, диагностика сохраняется, базовая линия не трогается. При
  сохранении диагностики туда же кладётся вывод процесса клона.

Фаза 3 `_record_canary_run`: `main_sha` = `metrics["code_sha"]` (коммит, чьим
кодом задача велась), без него — прежний проверяемый sha; тот же sha
возвращается в сводку (`sha=<...>`), при расхождении с меткой
`_sha_label(<код>, None)`. `_run_one_task` дописывает к строке сводки
`[РАСХОЖДЕНИЕ КОММИТА: задачу вёл код <код>, а проверялся <проверяемый> —
прогон не зелёный]` и ловит `CanaryDriveFailed` (`_report_drive_failure`):
красная строка `canary_runs` (метрики нулевые, `outcome=drive_failed`,
`main_sha=NULL` — какой код вёл задачу, процесс не сообщил), строка сводки с
причиной и путь диагностики; остальные задачи прогона идут дальше, пульт не
падает. Схема `canary_runs` не менялась.

Предельное время — `canary.CANARY_DRIVE_TIMEOUT_SEC = 8 ч` (`config.py` —
только чтение): четыре роли × `AGENT_TIMEOUT_SEC` (2700 с) на попытку плюс
повторы и возвраты из эскалации; конечно и с запасом.

Состояние процесса пульта, которого нет на диске клона, передаётся
аргументами: переопределение `CODEX_HOME` (ставит `_ephemeral_clone` при
входе Codex) — `--codex-home`; venv пульта (`VENV_DIR` сознательно не
переадресуется, `_CLONE_EXEMPT_CONFIG_ATTRS`) — `--venv-dir`.

Бюджет — в пределах оценки SPEC ($40), переоценка не нужна.

## Шаги

1. `orchestrator/canary_drive.py` — вход процесса клона (`drive`,
   `build_result`, `write_result`, `main`).
2. `orchestrator/canary.py` — фаза 1 через процесс клона (`_drive_in_clone`,
   `_read_drive_result`, `_save_drive_failure`, `CanaryDriveFailed`, отказ без
   входа), `main_sha` из HEAD клона в `_record_canary_run`, расхождение
   коммитов и сбой процесса в `_run_one_task` (`_report_drive_failure`),
   константы `CANARY_DRIVE_ENTRY`/`CANARY_DRIVE_MODULE`/
   `CANARY_DRIVE_TIMEOUT_SEC`; модульный докстринг.
3. `tests/test_canary_drive.py` — новые тесты (ниже); карта
   `docs/codebase-map.md` регенерирована `scripts/codebase_map.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (ведение процессом из клона, вход `canary_drive.py`, JSON-файл) | 1, 2 |
| 2 (состав результата) | 1 |
| 3 (пульт не исполняет ведение) | 2 |
| 4 (ответственность пульта неизменна) | 2 (`_ephemeral_clone`, `_set_plan`, `_codex_clone_auth`, `_baseline_deviation_note`, `_run_verdict` не тронуты) |
| 5 (коммит клона в `main_sha` и сводке, расхождение красит) | 2 |
| 6 (коммит без входа — именованный отказ) | 2 |
| 7 (сбой/зависание — красный прогон с диагностикой) | 2 |
| 8 (тесты) | 3 |

Критерии: AC-1..AC-10 — зелёные приёмочные тесты задачи (прогнаны по файлам:
ac1_ac2 — 2, ac3+ac4 — 6, ac5_ac6+ac7+ac8_ac9 — 8, оба ac10 — 2, все
прошли); AC-11 — этот PLAN (ни один метод `tests/` не удалён, ни один
существующий файл `tests/` не изменён).

## Переписанные тесты и сохранённые свойства (требование 8, AC-11)

Существующие файлы `tests/` НЕ изменены и ни один метод не удалён. Причина:
помощники ведения остались в `orchestrator/canary.py` и исполняются процессом
клона его копией модуля, а тесты «ведения в процессе пульта» проверяли именно
эти помощники напрямую, а не то, какой процесс их зовёт. Их свойства
сохраняются как есть и относятся теперь к коду, который исполняет клон:

- `tests/test_canary.py` — `DriveTaskEscalationCapTest`,
  `DriveTaskStallCapTest`, `DriveTaskDevRetryOnAcceptanceRefusalTest`,
  `DriveTaskDevRetryCapExceededTest`,
  `DriveTaskOtherClassRefusalDoesNotRetryDeveloperTest`,
  `DriveTaskPassesVerifyingSyntheticallyTest`, `PassVerifyingTest`,
  `KillAtVerifyingCompatTest`, `SpecGateArtifactSourceTest` — потолки
  эскалаций/стагнации/повторов developer, синтетический `verifying`, проход
  гейта SPEC: без изменений; `EphemeralCloneConfigRemapTest`,
  `CloneConfigAttrsInvariantTest` — клон пульта (не изменён);
  `RunOneTaskVerdictUsesNormalOutcomeTest`, `NeedsDiagnosticsTest`,
  `JournalExcerptLinesTest`, `MetricsFromJournalTest` — вердикт, выдержка,
  метрики: без изменений.
- `tests/test_canary_budget_ceiling.py` (`DriveTaskBudgetCeilingTest`,
  `RaiseTaskCeilingTest`, `KillCeilingExhaustedTest`, `RunVerdictTest`) —
  однократный подъём потолка и исход «исчерпан потолок задачи»: без изменений.
- `tests/test_canary_synthetic_answer.py` (`EscalationCapUnchangedTest`,
  `SyntheticAnswerReturnTest`, `SyntheticAnswerTextTest`) — синтетический
  ANSWER: без изменений.
- `tests/test_canary_codex_clone_auth.py` (`EphemeralCloneCodexHomeTest`,
  `PhaseOneCodexAuthArgumentTest`) — вход Codex клона и прокладка
  `codex_auth` до фазы 1: без изменений (форма кортежа фазы 1 сохранена ради
  них).
- `tests/test_canary_template_flag.py`, `tests/test_canary_sets.py` — выбор
  шаблонов и наборов: без изменений.

Новый файл `tests/test_canary_drive.py` (каждый тест — со строкой «Ловит
мутацию»; сторожа проверены временной мутацией, см. ниже):
- `CloneCodeDrivesTheTaskTest` — настоящий `git clone` крошечного репозитория,
  чей `canary_drive.py` в каждом коммите несёт свою метку: результат несёт
  метку проверяемого коммита («ведение учебной задачи в процессе пульта»);
  процесс — `sys.executable -m orchestrator.canary_drive` с `cwd` = клон и
  `--result`.
- `CommitWithoutEntryTest` — отказ «ADR-0021, этап 0», процесс не запускался,
  клон убран.
- `CloneProcessFailureTest` — код выхода 3 и зависание (предел сжат до 2 с):
  `CanaryDriveFailed`, вывод процесса сохранён снаружи клона, клон убран;
  зависший процесс, печатающий без `flush`, — вывод всё равно в диагностике
  (R1-F3).
- `InterruptedPultTest` — `KeyboardInterrupt` из ожидания процесса клона:
  прерывание уходит наружу, группа процесса снята, клон убран (R1-F1).
- `CommitMismatchSummaryTest` — строка сводки `_run_one_task` при
  `code_sha != target_sha` несёт `[РАСХОЖДЕНИЕ КОММИТА …]` и оба sha, при
  равенстве — без пометки (AC-6, R1-F2).
- `CanaryDriveMainTest.test_drive_opens_the_task_then_worktree_then_drives_it`
  / `test_drive_refuses_without_a_worktree_and_does_not_drive` — порядок
  `drive()` (HEAD → `cmd_new` → `workspace.ensure` → `_drive_task` →
  `build_result`) и отказ без worktree (R1-F2).
- `ReportedCommitMismatchTest` — чужой HEAD в результате: исход не штатный,
  диагностика сохранена.
- `ReadDriveResultTest`, `RecordCanaryRunCodeShaTest`,
  `DriveFailureReportTest`, `CanaryDriveMainTest` — разбор результата,
  `main_sha` из HEAD клона, красная строка сбоя, запись одного JSON-объекта и
  применение `--codex-home`/`--venv-dir`.

Проверка сторожей мутацией (прогон `tests/test_canary_drive.py`):
`cwd=config.ROOT` вместо клона — красные оба `CloneCodeDrivesTheTaskTest`;
без проверки кода выхода, без сверки HEAD и с `main_sha = target_sha` —
красные соответственно `test_nonzero_exit_…`, `test_other_reported_head_…`,
`test_main_sha_is_the_commit_…`. Код возвращён, файл зелёный (14 тестов).

Итерация 2 (замечания ревью R1-F1..R1-F3, коммит b1df1b86), мутации по
одной, прогон `tests/test_canary_drive.py`, код возвращён `git checkout`:
`except BaseException` → `except ZeroDivisionError` — красный
`InterruptedPultTest`; без `PYTHONUNBUFFERED` — красный
`test_output_of_a_killed_process_is_not_lost_in_its_buffer`; удалён
`canary._drive_task(conn, task_id)` в `drive` — красный
`test_drive_opens_the_task_then_worktree_then_drives_it`; условие
`[РАСХОЖДЕНИЕ КОММИТА]` → `if False:` — красный `CommitMismatchSummaryTest`.
Файл зелёный — 19 тестов.

Прогоны итерации 2 (`-p timeout -o timeout=120`): `test_canary_drive`,
`test_canary`, `test_canary_budget_ceiling`, `test_canary_codex_clone_auth`,
`test_canary_synthetic_answer`, `test_canary_template_flag`,
`test_canary_sets`, `test_pin`, `test_codebase_map`,
`test_guard_mutation_claim` — 291 passed; приёмочные тесты задачи — 20 passed.

Прогоны после финальной правки (по модулям, `-p timeout -o timeout=120`):
`test_canary_drive`, `test_canary`, `test_canary_budget_ceiling`,
`test_canary_codex_clone_auth`, `test_canary_synthetic_answer`,
`test_canary_template_flag`, `test_canary_sets`, `test_new_argv_parsing`,
`test_pin`, `test_codebase_map`, `test_doctor_canary_pool`,
`test_doctor_canary_sets` — 311 passed; `test_invariants`,
`test_multitarget_invariants`, `test_guard_mutation_claim` — 91 passed.

## Влияние на систему

- `pin-update` (`orchestrator/pin.py`, не тронут) по-прежнему принимает только
  `verdict='green'` набора по умолчанию; теперь такая строка означает, что
  задачу вёл код её `main_sha`. Строки сбоя процесса клона — `red` с пустым
  `main_sha`, в допуск не попадают (`store.green_canary_runs`).
- Канарейка на коммитах старше мержа этой задачи отказывает до заведения
  задачи (требование 6) — осознанно: пин сдвигается только на коммит с
  входом. Первая проверка на деле — после мержа, вне задачи (SPEC «Не
  входит»).
- Процесс клона исполняется интерпретатором пульта; venv и `CODEX_HOME`
  передаются явно, прочее окружение наследуется как было у ведения в пульте.
- Гейты, лимиты, инварианты, тесты не ослаблены; `_run_verdict`,
  `_needs_diagnostics`, `_baseline_deviation_note`, `_ephemeral_clone` не
  менялись. Откат — revert одного merge-коммита (схема БД не менялась).

## Риски

- Залоченная планка уже смерженной задачи 01M1SC3Y20YBTTJVQDJBF2NDQW
  (`test_canary_report_kill_reason.py`, зовёт `_run_one_task` с подменённым
  нульарным `_ephemeral_clone` и подменами `runner`/`auto` в процессе пульта)
  опирается на ведение в процессе пульта и против нового устройства не
  пройдёт; CI её не гоняет (`pytest tests`), её правка — чужая планка и
  мандат Оператора (`amend-tests`), вне этой задачи. Планка
  01M3GKJFN90ATK2KECNDZXPPP6 (`test_ac8_ac9_…`) подменяет саму фазу 1
  фикстурой пяти параметров — совместима: 9-элементный кортеж фазы 1 и
  откат `main_sha` на проверяемый sha при метриках без `code_sha`
  сохранены. Форма вызова `_ephemeral_clone()` без аргументов сохранена.
- Предел 8 ч выбран оценкой, не замером живых прогонов; если честный прогон
  его превысит — прогон красный с диагностикой, константа правится отдельно.
- Мутационная проверка с `cwd=config.ROOT` на миг запустила настоящий вход в
  рабочем каталоге шага: в его игнорируемом `.artel/` осталась пустая
  `state.db` без таблиц (задача не заводилась, веток нет).

## Предложения системе

- `skills/coding-standards.md`, раздел про сторожей: мутация «не тот рабочий
  каталог у дочернего процесса» исполняет настоящий код в рабочем каталоге
  шага — стоит оговорить, что такие мутации ставятся с подменой пути на
  временный каталог, а не на `config.ROOT`.
