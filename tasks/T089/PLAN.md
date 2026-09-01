---
task: T089
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: Тестовые хелперы третьего поколения — в sandbox

## Подход
Свести пять поименованных SPEC хелперов (`_ts_ago`, `FakeStream`, `SpyRun`,
`RealGitSandbox`, `_dead_pid`) в `tests/sandbox.py`, переключить копии в
`tests/*.py` на импорт. Разведка (grep по сигнатурам + `git branch` для
списка живых задач) дала точный список копий и их точное содержимое:

- `_ts_ago` (byte-identical, 4 копии в `tests/`): `test_release.py`,
  `test_merge_lock.py`, `test_lease.py`, `test_parallel_limit.py`.
- `_dead_pid` (byte-identical, 2 копии в `tests/`): `test_merge_lock.py`,
  `test_parallel_limit.py`.
- `FakeStream` (byte-identical в 3 из 4 копий, включая уже существующий
  приватный `tests/sandbox.py::_FakeStream`; 4-я копия в `test_doctor.py`
  не хранит `self.closed`, но нигде это отсутствие не используется —
  безопасно заменить канонической версией): `test_doctor.py`,
  `test_agent_log.py`, `test_step_cost.py`, `test_agent_failure.py`.
  Приватный `_FakeStream` в sandbox.py становится публичным `FakeStream`
  (единственное текущее использование — `FakeProc.__init__`).
- `SpyRun` (2 копии, НЕ byte-identical): `test_invariants.py` содержит
  надмножество поведения `test_auto_cycle.py` — специальный случай
  `rev-parse --verify refs/heads/*` (тот же приём, что `sandbox.fake_git`,
  нужен `cmd_new`/T048). В `test_auto_cycle.py` `gitcmd.git` подменён
  отдельно на `fake_git`, поэтому `SpyRun` там видит только вызовы
  `subprocess.run`, идущие МИМО `gitcmd.git` — специальный случай для них
  либо не встречается, либо безвреден (тот же ответ rc=0, что и раньше,
  для всего, что не совпадает с шаблоном). Каноническая версия — версия
  `test_invariants.py` (надмножество).
- `RealGitSandbox` (2 копии, структурно похожи, но НЕ идентичны):
  `test_gitcmd_branch_reads.py` и `test_answer_branch_reads.py` совпадают
  в базовой части (`setUp`: git init + одна фиксация + патч
  `ALL_CONFIG_ATTRS`; методы `git`/`checkout`), но расходятся в надстройке
  (`head`/`write_and_commit` у первого, `TASK`/`self.branch`/
  `commit_on_branch` у второго — `on_foreign_branch` нужен с самого начала
  теста только второму файлу). В sandbox выносится общая база
  (`RealGitSandbox`), в каждом файле остаётся локальный тонкий подкласс
  с его специфичной надстройкой — «чини класс, не экземпляр» применительно
  к общей части, без стирания реальных различий в поведении.

Других дублей того же класса тем же способом (grep по определению класса/
функции верхнего уровня без отступа) в `tests/*.py` не нашлось —
`_repo_scan.HELPER_PATTERNS` (пять регулярок из приёмочных тестов задачи)
и ручной просмотр совпадают.

Копии в `tasks/*/acceptance_tests/`: по правилу 3 SPEC трогаются только
файлы ЕЩЁ НЕ закрытых задач. `git branch --format='%(refname:short)'`
на момент правки живые: T085–T090 (включая саму T089). Ни у одной из них
`acceptance_tests/` не содержит копий пяти хелперов (grep подтверждает) —
дедуплицировать в открытых задачах нечего, AC-3 «зелён с рождения».
Все найденные копии в `acceptance_tests/` лежат в ЗАКРЫТЫХ задачах и
остаются нетронутыми (правило 3/4 SPEC) — полный список ниже,
«Известный остаток».

## Шаги

1. `tests/sandbox.py`: добавить канонические `_ts_ago`, `_dead_pid`,
   `SpyRun` (версия-надмножество из `test_invariants.py`), `RealGitSandbox`
   (общая база); переименовать приватный `_FakeStream` в публичный
   `FakeStream`, поправить единственную ссылку в `FakeProc.__init__`.
   Импорт модулей, которых сегодня в sandbox.py нет (`datetime`/`timedelta`/
   `timezone` для `_ts_ago`; `subprocess` уже импортирован).
2. `tests/test_release.py`, `tests/test_merge_lock.py`, `tests/test_lease.py`,
   `tests/test_parallel_limit.py`: удалить локальные `_ts_ago`
   (и `_dead_pid` в двух последних), добавить в импорт из
   `tests.sandbox`.
3. `tests/test_doctor.py`, `tests/test_agent_log.py`, `tests/test_step_cost.py`,
   `tests/test_agent_failure.py`: удалить локальные `class FakeStream`,
   добавить `FakeStream` в импорт из `tests.sandbox`; в
   `test_agent_log.py` `BlockingStream`/`BrokenPipeStream` наследуются от
   импортированного `FakeStream`.
4. `tests/test_invariants.py`, `tests/test_auto_cycle.py`: удалить локальные
   `class SpyRun`, добавить `SpyRun` в импорт из `tests.sandbox`.
5. `tests/test_gitcmd_branch_reads.py`, `tests/test_answer_branch_reads.py`:
   удалить локальный `class RealGitSandbox(TmpRootTest)` с полным телом,
   заменить на локальный тонкий подкласс импортированного
   `sandbox.RealGitSandbox` с файл-специфичной надстройкой; переименовать
   ссылки на старое имя класса у существующих тестовых классов
   (`ShowTest(RealGitSandbox)` → `ShowTest(_GitcmdRealGitSandbox)` и т. п.,
   аналогично во втором файле) на новое локальное имя.
6. Прогнать `python3 -m unittest discover -s tests` — зелёный (AC-6).
   Прогнать `python3 scripts/guard.py --all` (гейт AC на самих себе,
   `tasks/T089/*`), убедиться, что дифф не касается ничего вне `tests/` и
   `tasks/*/acceptance_tests/` (AC-5, приёмочный тест уже это проверяет).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2, 3, 4, 5 |
| 3 | (нет копий в открытых задачах — действие не требуется, AC-3 зелён с рождения) |
| 4 | «Известный остаток» ниже + сама секция «Покрытие требований» |
| 5 | 1–5 (правки только в tests/) |

## Влияние на систему
Правки — только тестовая обвязка (`tests/sandbox.py` и `tests/test_*.py`),
поведение боевого кода (`orchestrator/`, `scripts/`) не меняется — ни один
файл вне `tests/` не редактируется этим MR. Риск для системных инвариантов
и НЕОСЛАБЛЯЕМЫХ тестов (`test_agent_log.py`, `test_invariants.py`,
`test_step_cost.py` несут такие метки) — только в том, что перенос
хелперов случайно изменит их поведение и тем самым ослабит проверку:
- `SpyRun` в `test_invariants.py` — принимается КАК канонический вариант
  (надмножество), поведение файла не меняется вообще.
- `SpyRun` в `test_auto_cycle.py` — получает надмножество поведения
  (специальный случай `rev-parse --verify`), не теряет ничего из своего;
  `gitcmd.git` там всё равно подменён отдельно на `fake_git`, поэтому
  специальный случай либо не задействуется, либо безвреден.
- `FakeStream` в `test_doctor.py` — получает лишний атрибут `self.closed`,
  который нигде не читается; поведение теста не меняется.
- `RealGitSandbox` — общая база выносится без изменений построчно, файловые
  надстройки (`head`/`write_and_commit`, `TASK`/`branch`/`commit_on_branch`)
  остаются на месте, просто в подклассе, а не в самом `RealGitSandbox`.
- `_ts_ago`/`_dead_pid` — byte-identical копии, перенос без изменений.

Откат: `git revert` — правка не трогает БД/схему/CLI, откатывается одним
коммитом без побочных эффектов на систему.

Артефакты `tasks/*/acceptance_tests/` закрытых задач НЕ редактируются
(правило 3 SPEC, право есть только у Оператора/по правилам самой
задачи) — эти копии остаются как известный остаток.

### Известный остаток (правило 4 SPEC, AC-4)
Копии хелперов в `acceptance_tests/` уже ЗАКРЫТЫХ задач (нет локальной
ветки `task/t<id>-...` на момент правки) — не редактируются этой задачей:

- `FakeStream`: `tasks/T028/acceptance_tests/test_brief.py`,
  `tasks/T029/acceptance_tests/test_incremental_diff.py`,
  `tasks/T034/acceptance_tests/test_runner_git_identity_warning.py`,
  `tasks/T040/acceptance_tests/test_step_cost_on_missing_final_event.py`,
  `tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py`,
  `tasks/T045/acceptance_tests/_sandbox.py`,
  `tasks/T048/acceptance_tests/_sandbox.py`,
  `tasks/T074/acceptance_tests/test_ac9_checkpoint_on_abnormal_step_end.py`.
- `_ts_ago`: `tasks/T044/acceptance_tests/test_lease_enforcement.py`,
  `tasks/T053/acceptance_tests/test_ac6_dead_holder_lock_stepped_over.py`,
  `tasks/T062/acceptance_tests/test_ac1_ac2_ac3_ac5_release_command.py`.
- `_dead_pid`: `tasks/T053/acceptance_tests/test_ac6_dead_holder_lock_stepped_over.py`,
  `tasks/T060/acceptance_tests/test_max_parallel_tasks.py`.

`SpyRun`/`RealGitSandbox` в `acceptance_tests/` закрытых задач не найдены
(grep пуст).

## Риски
- Приёмочный тест AC-1/AC-2 гоняет grep по РЕГУЛЯРНЫМ ВЫРАЖЕНИЯМ верхнего
  уровня — переименование локальных подклассов `RealGitSandbox` в
  `_GitcmdRealGitSandbox`/`_AnswerRealGitSandbox` не должно случайно
  сохранить имя `RealGitSandbox` где-то ещё (например, в docstring —
  не страшно, паттерн ищет только `^class RealGitSandbox\b`).
- `test_auto_cycle.py` не импортирует `tests.sandbox` иначе, чем
  `capture, fake_git` сегодня — добавление `SpyRun` в этот же импорт
  тривиально, конфликтов имён нет.

## Предложения системе
