---
task: 01M5K11K3VV23VK177YWMWKJ14
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/cleanup.py, orchestrator/artel.py, tests/
budget_usd: 45
---

# SPEC: kill --reason — причина ликвидации задачи в записи перехода и в RETRO

## Контекст
Находка ревизии кода 22.10 CR-2026-10-22-3. Команда `kill` не принимает
причину: переход `state -> killed` всегда пишется с постоянной деталью
`kill switch` (`orchestrator/cleanup.py:587`), и RETRO ликвидированной
задачи (`orchestrator/retro.py:619` `build_killed`, причина — деталь
последней записи `state -> killed`, `orchestrator/retro.py:666`/`:671`)
показывает «Итог: killed — причина: kill switch». По журналу 30.09–22.10
16 из 24 ликвидаций прошли без причины ($197.67); у 11 из них причина
живёт только в ручных строках `docs/backlog.md`, вне БД. Нужен
необязательный флаг `--reason`: причина попадает в деталь перехода и,
через неё, в RETRO без правки `retro.py` и `snapshot.py`.

## Требования

1. `kill <id> [--yes] [--reason "<текст>"]`: диспетчер
   `orchestrator/artel.py` разбирает значение флага существующим
   `_reason_arg` (`orchestrator/artel.py:1801`) и передаёт его в
   `cleanup.cmd_kill(task_id, …, confirmed=…, reason=…)` новым
   необязательным именованным параметром `reason: str | None = None`;
   `cmd_kill` передаёт его в `_cmd_kill`. Порядок флагов после `<id>`
   произвольный. Именованный аргумент `reason=` диспетчер передаёт только
   при наличии флага `--reason` (образец — `_approve_during_canary_kwargs`,
   `orchestrator/artel.py:1882`); без флага вызов прежний —
   `cleanup.cmd_kill(<id>, confirmed=…)` без аргумента `reason`, поэтому
   существующие тесты
   `tests/test_kill_live_cycle_refusal.py::KillDispatchYesFlagTest::test_yes_flag_reaches_cmd_kill_as_confirmed_true`
   (`:156`) и
   `tests/test_kill_live_cycle_refusal.py::KillDispatchYesFlagTest::test_missing_flag_reaches_cmd_kill_as_confirmed_false`
   (`:167`), проверяющие вызов `assert_called_once_with(self.TASK,
   confirmed=…)`, остаются зелёными без правок.
2. С причиной деталь перехода `state -> killed` — `kill switch: <текст>`,
   где в тексте каждый перевод строки (`\r\n`, `\n`, `\r`) заменён одним
   пробелом (`\r\n` — один пробел, не два), затем пробелы по краям
   обрезаны (strip) — строка «Итог:» в RETRO остаётся одной строкой. Без
   флага — прежняя деталь `kill switch` побайтно.
3. Без флага `--reason` диспетчер `orchestrator/artel.py` печатает одну
   строку `причина не записана — в следующий раз: artel.py kill <id>
   --reason "<текст>"` — только при вызове `kill` из командной строки и
   только если этот вызов записал переход в `killed`. `<id>` в подсказке —
   аргумент команды в том виде, как его ввёл Оператор (например, префикс
   id); `"<текст>"` — буквальная заглушка, печатается как есть, без
   подстановки. Для этого `cleanup.cmd_kill` возвращает `True`, если
   переход записан, иначе `False` (значение берётся из `_cmd_kill`). При
   отказе живому циклу (`_refuse_live_cycle`) и для уже терминальной задачи
   подсказки нет. Сам `cleanup.cmd_kill` подсказку не печатает, поэтому
   вызовы из `orchestrator/canary.py` (без флагов) её не выводят.
4. Отказы по причине проверяются в диспетчере или в начале `cmd_kill` —
   до проверки живого цикла (`_refuse_live_cycle`), до взятия lease и до
   любой записи в журнал; задача и её lease не меняются:
   - `--reason` с пустым или пробельным текстом — отказ «kill: --reason
     требует непустую причину»;
   - значение `--reason`, начинающееся с `--` (например,
     `kill <id> --reason --yes`), — отказ «kill: --reason требует причину
     следующим аргументом, а не флаг».
5. Задача уже терминальна (`done`/`killed`) — перехода нет, причина нигде
   не пишется, вывод прежний («уже … — kill не требуется»), уборка — как
   прежде.
6. Подтверждение `--yes`, отказ живому циклу (`_refuse_live_cycle`),
   уборка ветки, worktree и lease, коммит закрытия — без изменений. Текст
   отказа `_refuse_live_cycle` не меняется.
7. При любом отказе (пустая причина, значение `--reason`, начинающееся с
   `--`, отказ живому циклу) и для терминальной задачи текст причины не
   пишется нигде: ни одной записи журнала задачи с этим текстом в детали,
   ни в RETRO задачи (следствие требований 4–6: причина существует только
   в детали записанного перехода `state -> killed`).
8. Справка `orchestrator/artel.py` (строка `kill <id>` в перечне команд,
   `orchestrator/artel.py:172`) называет `[--yes] [--reason "<текст>"]`.
9. Тесты детерминированные, без сети; допустимо подменять
   `cleanup._commit_closing`, `cleanup.cleanup_killed_task`,
   `cleanup.cleanup_project_remote`, `cleanup._refuse_unsynced_docs` и
   `fixation.ref_drift` — по образцу `tests/test_kill_cleanup.py`.
   Существующие тесты не правятся и остаются зелёными.

## Критерии приёмки

AC-1. `artel.py kill <id> --reason "дубль X" --yes` через `artel.main` —
деталь последней записи `state -> killed` равна `kill switch: дубль X`, а
`retro.build_killed(conn, <id>)` содержит строку
`Итог: killed — причина: kill switch: дубль X` (на текущем коде — красный:
деталь «kill switch»).

AC-2. `artel.py kill <id> --yes --reason "дубль X"` (обратный порядок
флагов) через `artel.main` — тот же результат, что в AC-1: деталь
`kill switch: дубль X` и та же строка «Итог:» в `retro.build_killed`.

AC-3. `artel.py kill <аргумент>` без `--reason` через `artel.main`
(переход записан), где `<аргумент>` — префикс id задачи, отличный от
полного id, — деталь последней записи `state -> killed` равна
`kill switch` побайтно, в выводе есть строка
`причина не записана — в следующий раз: artel.py kill <аргумент> --reason "<текст>"`,
где `<аргумент>` — ровно введённый префикс (не полный id), а
`"<текст>"` — буквально эти семь символов в кавычках, без подстановки.

AC-4. `artel.py kill <id>` без `--reason` при живом цикле и без `--yes` —
отказ `_refuse_live_cycle` с прежним текстом, подсказки требования 3 в
выводе нет.

AC-5. `artel.py kill <id>` без `--reason` для терминальной задачи через
`artel.main` — вывод «kill не требуется», подсказки требования 3 нет.

AC-6. Прямой вызов `cleanup.cmd_kill(task_id)` без флагов (как из
`canary.py`) — переход в `killed` записан, подсказки требования 3 в выводе
нет, возвращено `True`.

AC-7. `artel.py kill <id> --reason ""` и `artel.py kill <id> --reason "   "`
— отказ «kill: --reason требует непустую причину»; состояние задачи не
изменилось, новых записей журнала задачи нет.

AC-8. `artel.py kill <id> --reason ""` при живом цикле без `--yes` — отказ
о пустой причине; записи журнала «kill отклонён: цикл жив» нет.

AC-9. `artel.py kill <id> --reason --yes` — отказ «kill: --reason требует
причину следующим аргументом, а не флаг»; состояние задачи не изменилось,
новых записей журнала задачи нет, ни одна запись журнала задачи не
содержит в детали текста `--yes` как причины (записи `state -> killed`
нет).

AC-10. Причина с переводом строки `\n` (`"строка 1\nстрока 2"`) — деталь
последней записи `state -> killed` равна `kill switch: строка 1 строка 2`,
строка «Итог:» в `retro.build_killed` одна.

AC-11. Причина с переводом строки `\r\n` (`"строка 1\r\nстрока 2"`) —
деталь последней записи `state -> killed` равна
`kill switch: строка 1 строка 2` (между словами ровно один пробел),
строка «Итог:» в `retro.build_killed` одна.

AC-12. Причина с одиночным `\r` (`"строка 1\rстрока 2"`) — деталь
последней записи `state -> killed` равна `kill switch: строка 1 строка 2`,
строка «Итог:» в `retro.build_killed` одна.

AC-13. Причина с пробелами и переводом строки по краям
(`"  дубль X \n"`) — деталь последней записи `state -> killed` равна
`kill switch: дубль X` (края обрезаны).

AC-14. `artel.py kill <id> --reason "дубль X"` для терминальной задачи —
записи перехода `state -> killed` этим вызовом нет, вывод
«kill не требуется», ни одна запись журнала задачи не содержит текста
`дубль X`, RETRO задачи не содержит текста `дубль X`.

AC-15. `artel.py kill <id> --reason "дубль X"` при живом цикле без `--yes`
— отказ `_refuse_live_cycle` с прежним текстом, записи `state -> killed`
нет, ни одна запись журнала задачи (в том числе запись «kill отклонён:
цикл жив») не содержит текста `дубль X`, RETRO задачи не содержит текста
`дубль X`.

AC-16. Диспетчер `artel.main` с подменённым `cleanup.cmd_kill`:
`kill <id> --reason "дубль X"` вызывает его с `reason="дубль X"`;
`kill <id>` и `kill <id> --yes` — без аргумента `reason`
(`cmd_kill(<id>, confirmed=False)` / `cmd_kill(<id>, confirmed=True)`).
Существующие
`tests/test_kill_live_cycle_refusal.py::KillDispatchYesFlagTest::test_yes_flag_reaches_cmd_kill_as_confirmed_true`
и
`tests/test_kill_live_cycle_refusal.py::KillDispatchYesFlagTest::test_missing_flag_reaches_cmd_kill_as_confirmed_false`
зелёные без правок.

AC-17. Строка справки `orchestrator/artel.py` с командой `kill <id>`
называет `[--yes] [--reason "<текст>"]`.

## Оценка объёма и деление
Сработавшие сигналы: число критериев приёмки ≥ 10 (17 критериев);
`budget_usd` ≥ $30 ($45 — решение Оператора на гейте SPEC 23.10.2026,
круг 1). Прочие сигналы не срабатывают: зон кода две
(`orchestrator/cleanup.py`, `orchestrator/artel.py`) плюс общая `tests/`.

Материал для решения Оператора — обоснование монолита: критерии — это
шестнадцать сценариев одного поведения (разбор флага → параметр
`cmd_kill` → деталь перехода → возврат `True`/`False` → подсказка
диспетчера) и одна строка справки. Разбор флага в `artel.py` без
параметра `reason` у `cmd_kill` не имеет потребителя, а параметр без
разбора флага недостижим из командной строки; подсказка требования 3
опирается на возвращаемое значение `cmd_kill`. Разрезанная по зонам
(`artel.py` / `cleanup.py`) задача давала бы часть без наблюдаемого
поведения либо с неполным контрактом флага.

## Не входит
- Причина у ликвидаций канарейки (`orchestrator/canary.py`, находка
  CR-2026-09-30-17 — отдельная задача); вызовы `cleanup.cmd_kill(task_id)`
  в `canary.py` не меняются.
- Обязательность `--reason` (решение Оператора после накопления
  статистики).
- Правка контракта сессии (`docs/operator-session.md`) о новом флаге —
  строкой `note`/`doc-commit` Оператора после мержа.
- Разбор прежних 16 ликвидаций в БД.
- Правка `orchestrator/retro.py`, `orchestrator/snapshot.py`,
  `orchestrator/store.py`, `orchestrator/lease.py`,
  `orchestrator/fixation.py`, `orchestrator/fsm.py`,
  `orchestrator/fsm_merge_gate.py`, `orchestrator/canary_drive.py`,
  `orchestrator/liveness.py`, `orchestrator/workspace.py`,
  `orchestrator/watch.py` (свой разбор `--reason`),
  `orchestrator/checkpoint.py`, `orchestrator/advance_gates/tests_writing.py`,
  `orchestrator/doctor/ignored_artifacts.py`, `docs/backlog.md` — только
  чтение.
- В `orchestrator/artel.py` — ничего, кроме разбора флагов `kill` и строки
  справки; в `orchestrator/cleanup.py` — ничего, кроме `cmd_kill` и
  `_cmd_kill`.
- Правка существующих тестов (`tests/test_kill_cleanup.py`,
  `tests/test_kill_live_cycle_refusal.py`, `tests/test_retro.py`,
  `tests/test_retro_artifact_branch_reads.py`,
  `tests/test_snapshot_closing_outcome.py`, `tests/test_canary.py` и
  прочих) — мандат на правку не нужен и не выдан (решение Оператора
  23.10.2026); их зелёность и полный зелёный набор `tests/` держит пульт.

## Материалы
- ТЗ: `tasks/01M5K11K3VV23VK177YWMWKJ14/TZ.md`; отчёт ревизии
  `docs/audits/code-revision-2026-10-22.md` (CR-2026-10-22-3).
- Решения Оператора на гейте SPEC 23.10.2026, круг 1 (по SPEC-AUDIT.md,
  вердикт concerns): условная передача `reason=` (требование 1, AC-16);
  `\r\n`/`\r`/strip (требование 2, AC-11–AC-13); причина не пишется при
  отказах (требование 7, AC-9, AC-14, AC-15); `<id>` как введён и
  литерал `"<текст>"` (требование 3, AC-3); бюджет $45.
- Код: `orchestrator/artel.py:172`, `:1801` (`_reason_arg`), `:1882`
  (`_approve_during_canary_kwargs`), `:2181`;
  `orchestrator/cleanup.py:434` (`_refuse_live_cycle`), `:447`
  (`cmd_kill`), `:558` (`_cmd_kill`), `:583`–`591` (флаг `won`);
  `orchestrator/retro.py:619`, `:666`, `:671`; `orchestrator/snapshot.py:62`;
  `tests/test_kill_live_cycle_refusal.py:125` (`KillDispatchYesFlagTest`),
  `:156`, `:167`.
- `_reason_arg` при `--reason` последним аргументом выходит со своим
  текстом «--reason требует основание следующим аргументом.» — ТЗ этот
  случай не меняет.
