---
task: T037
type: plan
author_role: developer
status: draft        # draft | ready | approved
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: Общая тестовая песочница и ревизия мокинга subprocess

## Подход

Три независимых, но последовательно зависимых изменения.

**1) `tests/sandbox.py`.** `TmpRootTest` не бывает одинаковым: файлы
патчат от 5 до 9 путей `config`, часть дополнительно копирует
`skills/`/`templates/`/`docs/`, патчит keychain/`preflight_checks`,
заводит задачу через `cmd_init`/`cmd_new`. Общий знаменатель — цикл
патчинга путей `config` и хелпер `capture`; всё остальное — специфика
конкретного файла, дедуп которой SPEC прямо исключает («Не входит»).
Поэтому `sandbox.TmpRootTest` параметризуется ОДНИМ атрибутом
`PATCHED_ATTRS` (по умолчанию — полный кортеж из 9 путей, AC-2), а
файлы с усечённым набором или дополнительной подготовкой — локальным
наследником с переопределённым `PATCHED_ATTRS`/`setUp`.

Приёмочный тест AC-1 (`tasks/T037/acceptance_tests/test_sandbox.py`,
залочен) проверяет отсутствие копий статическим AST-разбором: любой
`class`/`def`, буквально названный `TmpRootTest`/`capture`/`fake_git`
где-либо в файле (включая вложенные), — «своя копия», без разбора
базовых классов. Наследник обязан называться иначе, а имя
`TmpRootTest` внутри файла — быть переприсвоено ему одной строкой
(`TmpRootTest = _FileSpecificTmpRootTest`) сразу после определения:
все дальнейшие `class XyzTest(TmpRootTest):` в файле резолвятся в
наследника без единой правки в их сигнатурах. Это единственное
отклонение от «только импорты и пути патчей» (правки тестов, требование
4) — вынужденное конструкцией уже принятого приёмочного теста, не
дедупликацией: переименование `class`, без изменения тела, поведения
или ассертов.

Аналогично для метода `capture(self, fn, *args)`, который в части
файлов не входит в `TmpRootTest` (собственные лёгкие песочницы —
`AdvanceGuardTest`, `PromptChannelTest`, `TmpRepoTest`,
`CmdRunReviewPackageTest`, `PreviousVerdictShaTest`,
`SpecBudgetOnTheGateTest`, `FsmTest`, `KillKeepsMainIntactTest`,
`AutoCycleTest`, `ReviewFreshnessScenarioTest`,
`PultArtifactIsolationTest`, `RealPultGitTest`, `LockTest`): тело
метода везде байт-в-байт одинаковое (`io.StringIO` + `redirect_stdout`).
Замена — не переопределение метода, а присваивание атрибута класса
`capture = staticmethod(capture)` сразу после `from tests.sandbox
import capture` (имя `capture` внутри тела класса на момент этого
присваивания ещё не определено в пространстве имён класса, поэтому
справа читается импортированная функция модуля — обычная семантика
Python, `class Foo: x = len`). `self.capture(fn, *args)` во всех
вызывающих местах продолжает работать без изменений: `staticmethod` не
передаёт `self`, а сигнатура `capture(fn, *args)` этого и не ждёт. Это
`ast.Assign`, не `def`/`class` — под критерий AC-1 не подпадает и
переименования не требует.

Модуль-уровневый `capture`/`fake_git` (не метод) в части файлов
(`test_doctor.py`, `test_multitarget.py`, `test_multitarget_invariants.py`,
`test_git_fixation.py`, `test_review_freshness.py`, `test_auto_cycle.py`)
— обычный `from tests.sandbox import capture, fake_git`, вызывающий код
не меняется вовсе (имя резолвится так же, как и раньше).

Отдельный случай — `test_brief.py:177`: локальная (вложенная в тест)
функция `fake_git`, которая оборачивает `fake_git_stale(...)` и ведёт
список вызовов (`calls.append(args)`) для собственного ассерта этого
теста. Она НЕ дублирует сущность из требования 1 (другое поведение,
захватывает состояние теста) — но `def fake_git` внутри метода — тоже
`ast.FunctionDef` с именем `fake_git`, приёмочный тест ловит его так
же, как настоящую копию. Переименование в `fake_git_with_calls` (тело
и вызывающий код внутри теста не меняются, второй вынужденный
отход от «только импорты/пути патчей» по той же причине, что и выше).

`fake_git` в `tests/sandbox.py` — версия «с идентичностью» (учитывает
`git config --get user.name/user.email`, как в `test_agent_log.py`/
`test_step_cost.py`): для остальных пяти файлов, где сегодня стоит
версия «пустой ответ на всё», она строгий надмножественный
заменитель — они не проверяют идентичность в выводе/ассертах (сверено
grep'ом по `user.name|user.email|ВНИМАНИЕ.*идентичн` перед правкой),
поэтому подмена не меняет исход ни одного существующего теста.

**2) Обёртка `runner.spawn_agent`.** Сегодня `run_agent_once` зовёт
`subprocess.Popen(["claude", ...], cwd=cwd, env=env, text=True,
bufsize=1, stdin=prompt_file, stdout=subprocess.PIPE,
stderr=subprocess.STDOUT)` напрямую (`orchestrator/runner.py:420-435`).
14 тестовых файлов мокают этот вызов через `mock.patch.object(runner.
subprocess, "Popen", ...)` — а `runner.subprocess` и `doctor.subprocess`
это один и тот же модульный объект `subprocess`, так что подмена
глобальна: любой сторонний код (например, будущий `subprocess.run`
внутри `doctor.cli_version()`) неявно попадает под тот же мок. Обёртка

```python
def spawn_agent(cmd: list[str], **kwargs) -> subprocess.Popen:
    return subprocess.Popen(cmd, **kwargs)
```

— тонкий проброс: вызывающий код передаёт ровно те же позиционные и
именованные аргументы, что раньше уходили в `subprocess.Popen`
напрямую (`spawn_agent(["claude", ...], cwd=cwd, env=env, ...)`), и
`popen.call_args.kwargs["stdout"]`/`.args[0][0] == "claude"` в тестах
продолжают работать без изменений — меняется только КОГО патчат
(`mock.patch.object(runner, "spawn_agent", ...)` вместо
`mock.patch.object(runner.subprocess, "Popen", ...)`), не форма
вызова. Вспомогательные `claude_only_popen`/`side_effect`-обёртки
(`test_doctor.py`, `test_git_fixation.py`), которые сегодня
фильтруют `cmd[0] == "claude"` и иначе уходят в настоящий `Popen`
(потому что подмена была глобальной), остаются как есть: ветка
«не claude» становится мёртвой (после введения `spawn_agent` в него
в принципе не попадает ничего, кроме вызова агента), но убирать её —
за пределами задачи (не входит: правки тестов вне импортов/путей
патчей). По всем 14 файлам — механическая замена цели патча, тело
теста и ассерты не трогаются.

Комментарии в тестовых файлах, которые объясняют СЕГОДНЯШНЮЮ причину
глобальности патча (`test_multitarget.py:597-598`,
`test_git_fixation.py:645-650` и т.п.), после правки будут неточны —
не трогаю их: правки тестов ограничены импортами и путями патчей
(требование 4), правка комментария в их число не входит. Это
осознанный остаточный долг, зафиксирован в «Риски».

**3) Сверка пина CLI в `preflight_checks`.** `check_cli_version()` уже
существует и используется в `all_checks()` — добавляется вызовом в
конец `preflight_checks()`, ПОСЛЕ раннего `return` по блокирующим
проверкам (тот же принцип, что уже применён к `check_git_identity()`:
«исход уже решён — платить subprocess-вызовом не о чем»). Так как
`check_cli_version()` только `"ok"`/`"warn"` (никогда `"fail"`,
`orchestrator/doctor.py:104-114`), pre-flight не блокируется — критерий
приёмки требует ровно этого (`tasks/T037/acceptance_tests/
test_preflight_cli_pin.py::test_ac4_preflight_reports_a_cli_version_pin_mismatch`
ожидает пустой список блокирующих проверок при версии-заглушке
`"0.0.1"`). Модульный докстринг `doctor.py` (строки 29-50) — переписать:
абзац объясняет СТАРОЕ решение сузить требование 5 из-за конфликта с
мокингом `Popen`; после шага 2 конфликта нет, абзац переписывается на
то, что сверка возвращена (со ссылкой на T037 и решение Оператора
25.08, которое эта задача выполняет).

Модуль `tests/test_doctor.py` уже имеет тесты на `preflight_checks`,
не мокающие `doctor.cli_version`/`shutil.which` для части сценариев
(`PreflightBlocksMissingTokenTest`): после правки при реальном проходе
через `check_cli_version()` они делают настоящий `subprocess.run(["claude",
"--version"])` (не через `spawn_agent`, значит не под тестовым моком).
Это не ломает ни одной проверки: `claude` либо есть в PATH (реальная
версия, не совпавшая с пином, — тоже `"warn"`), либо нет
(`OSError` → `None` → `"warn"` c текстом «версия... не определилась»)
— ни один сценарий этого файла не проверяет отсутствие warn-строк или
точное число subprocess-вызовов на этом пути (сверено перед правкой);
единственный тест с таким инвариантом
(`test_blocking_failure_makes_no_subprocess_calls_at_all`) блокируется
раньше (`token` fail → ранний `return` до `check_cli_version()`).

## Шаги

1. Завести `tests/sandbox.py` (`TmpRootTest`, `capture`, `fake_git`,
   AC-1/AC-2). Перевести 9 файлов с `TmpRootTest` и 8 файлов с
   одноимённым `fake_git` (см. таблицу переносов) на импорт;
   отдельно — метод `capture` ещё в 13 местах (12 файлов), где он не
   часть `TmpRootTest` (staticmethod-присваивание). Прогнать
   `tasks/T037/acceptance_tests/test_sandbox.py` и весь `unittest
   discover -s tests`. Один MR.
2. Завести `runner.spawn_agent` (обёртка `subprocess.Popen` на пути
   запуска шага), перевести `run_agent_once` на неё. Перевести 14
   тестовых файлов, мокающих `runner.subprocess.Popen`, на мокинг
   `runner.spawn_agent` (замена цели патча, без прочих изменений).
   Прогнать `tasks/T037/acceptance_tests/test_runner_wrapper.py` и
   весь `unittest discover -s tests`.
3. Добавить `check_cli_version()` в `preflight_checks()` (после
   раннего возврата по блокирующим проверкам), переписать связанный
   абзац докстринга `doctor.py`. Прогнать
   `tasks/T037/acceptance_tests/test_preflight_cli_pin.py` и весь
   `unittest discover -s tests`.

Шаги зависимы по порядку (2 требует 1 — обёртка вводится в модуль,
которым уже пользуется `tests/sandbox.py`; 3 требует 2 — сверка пина
без разъединения мокинга Popen регрессирует ровно тот конфликт T022,
который и обязана снять задача), но один MR: откат — `git revert`
merge-коммита целиком (требование 6), без промежуточных состояний.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 3 |
| 4 | 1, 2, 3 |
| 5 | 1, 2, 3 |
| 6 | 1, 2, 3 (один MR) |

## Таблица переносов

`TmpRootTest` — файл → набор `PATCHED_ATTRS` в наследнике (расхождение
с полным набором по умолчанию) → дополнительная логика `setUp`,
оставшаяся в файле:

| Файл | `PATCHED_ATTRS` | Доп. логика в файле |
|---|---|---|
| `test_doctor.py` | по умолчанию (9/9) | copytree skills/templates, docs/codebase-map.md, CLAUDE.md, keychain-заглушка, ambient-токены очищены, `TARGETS` записан, `cmd_init` |
| `test_git_fixation.py` | ROOT,DB,TASKS,LOGS,PROJECTS,ROLE_HOME,ROLE_CONFIG_DIR,TARGETS (8/9, без BACKUP_MARKER) | — |
| `test_multitarget_invariants.py` | ROOT,DB,TASKS,LOGS,PROJECTS,ROLE_HOME,ROLE_CONFIG_DIR,TARGETS (8/9, без BACKUP_MARKER) | copytree templates/skills, docs/codebase-map.md, CLAUDE.md, keychain-заглушка, `preflight_checks` → `[]` |
| `test_multitarget.py` | DB,TASKS,LOGS,PROJECTS,ROLE_HOME,ROLE_CONFIG_DIR,TARGETS (7/9, без ROOT, BACKUP_MARKER) | keychain-заглушка, `preflight_checks` → `[]` |
| `test_acceptance_tests_flow.py` | DB,TASKS,LOGS,ROLE_HOME,ROLE_CONFIG_DIR (5/9) | `gitcmd.git` → `fake_git`, `cmd_init`+`cmd_new`, `self.tdir` |
| `test_analyst_role.py` | DB,TASKS,LOGS,ROLE_HOME,ROLE_CONFIG_DIR (5/9) | `gitcmd.git` → `fake_git`, `cmd_init`+`cmd_new`, `self.tdir` |
| `test_agent_log.py` | DB,TASKS,LOGS,ROLE_HOME,ROLE_CONFIG_DIR (5/9) | — |
| `test_agent_failure.py` | DB,TASKS,LOGS,ROLE_HOME,ROLE_CONFIG_DIR (5/9) | — |
| `test_step_cost.py` | DB,TASKS,LOGS,ROLE_HOME,ROLE_CONFIG_DIR (5/9) | — |

`fake_git` (буквальное имя, требование 1) — 8 файлов, все на общую
версию «с идентичностью» из `tests/sandbox.py`:
`test_agent_log.py`, `test_step_cost.py` (уже эта версия — переносится
без изменения поведения), `test_acceptance_tests_flow.py`,
`test_analyst_role.py`, `test_agent_failure.py`, `test_auto_cycle.py`,
`test_review_freshness.py` (версия «пустой ответ» — заменяется
надмножественной, см. «Подход»); `test_brief.py:177` — вложенная
функция с другим поведением, переименована в `fake_git_with_calls`,
НЕ переносится в sandbox (не входит в требование 1; правки — импортов
и путей патчей нет, только имя).

`capture` (буквальное имя) — метод `TmpRootTest` наследуется
автоматически (9 файлов выше); отдельно, как `staticmethod`-присваивание
после `from tests.sandbox import capture` — ещё 12 файлов/13
определений: `test_advance_guard.py` (`AdvanceGuardTest`),
`test_agent_prompt.py` (`PromptChannelTest`), `test_kill_cleanup.py`
(`TmpRepoTest`), `test_review_package.py` (`CmdRunReviewPackageTest`,
`PreviousVerdictShaTest` — 2 определения), `test_spec_budget.py`
(`SpecBudgetOnTheGateTest`), `test_invariants.py` (`FsmTest`,
`KillKeepsMainIntactTest` — 2 определения), `test_auto_cycle.py`
(`AutoCycleTest`), `test_review_freshness.py`
(`ReviewFreshnessScenarioTest`), `test_multitarget_invariants.py`
(`PultArtifactIsolationTest`), `test_git_fixation.py`
(`RealPultGitTest`), `test_acceptance_tests_flow.py` (`LockTest`).
Модуль-уровневый `capture` (не метод) — прямой импорт без обёртки:
`test_doctor.py`, `test_multitarget.py`, `test_multitarget_invariants.py`
(отдельно от метода `PultArtifactIsolationTest` выше), `test_git_fixation.py`
(отдельно от метода `RealPultGitTest` выше).

`mock.patch.object(runner.subprocess, "Popen", ...)` →
`mock.patch.object(runner, "spawn_agent", ...)` (требование 2) — 14
файлов: `test_agent_log.py`, `test_acceptance_tests_flow.py`,
`test_agent_failure.py`, `test_analyst_role.py`, `test_agent_prompt.py`,
`test_auto_cycle.py`, `test_git_fixation.py`, `test_doctor.py`,
`test_multitarget_invariants.py`, `test_multitarget.py`,
`test_invariants.py`, `test_review_package.py`, `test_review_freshness.py`
(один случай — `mock.patch("orchestrator.runner.subprocess.Popen")`,
строковая форма → `mock.patch("orchestrator.runner.spawn_agent")`),
`test_step_cost.py`.

Откат всей задачи — `git revert` merge-коммита ветки
`task/t037-obschaya-testovaya-pesochnitsa` целиком: правка не вводит
миграций схемы БД и не меняет продуктовое поведение вне тестовой
инфраструктуры и добавленной pre-flight-проверки (сама проверка —
чистое добавление функции в список, откатывается тем же ревертом без
остаточного состояния).

## Влияние на систему

Задача — рефакторинг (правила tasks/T015): наблюдаемое поведение
системы не меняется, кроме ЯВНО заявленного требования 3 (сверка пина
CLI возвращается в pre-flight — предупреждение, не блок, поэтому не
может провалить ни один существующий сценарий запуска шага). Тесты,
гейты, лимиты и guard-проверки не ослабляются: количество тестов после
задачи не меньше 599 (замер на момент SPEC/эту ветку), ни один ассерт
и сценарий существующего теста не редактируется — только импорты,
пути патчей и, в двух вынужденных случаях (`TmpRootTest`-наследник,
`test_brief.py` локальный `fake_git`), переименования без изменения
тела/поведения, продиктованные буквальной AST-проверкой залоченного
приёмочного теста (не могу его прав ить — tasks/T023). `runner.
spawn_agent` — тонкий проброс к `subprocess.Popen` без собственной
логики, поведение `run_agent_once` байт-в-байт то же (те же аргументы
вызова). Откат — один `git revert`, без миграций и без промежуточных
состояний (требование 6).

## Риски

- Комментарии в тестовых файлах, объясняющие сегодняшнюю причину
  мокинга Popen «глобально» (`test_multitarget.py:597-598`,
  `test_git_fixation.py:645-650` и аналогичные), станут неточны после
  введения `spawn_agent` — не правлю их (вне «импорты и пути патчей»,
  требование 4). Отдельная уборка — вне объёма этой задачи.
- `PreflightBlocksMissingTokenTest` (`test_doctor.py`) после шага 3 на
  двух сценариях (`test_token_present_lets_the_step_start`,
  `test_broken_identity_warns_but_does_not_block_the_step`) делает
  настоящий `subprocess.run(["claude","--version"])` вместо замоканного
  — не ломает ассерты (см. «Подход»), но на машине без `claude` в PATH
  добавляет реальную (быструю, `OSError`) попытку exec на каждый такой
  прогон. Не устраняю (правка теста добавила бы мок вне «импорты и
  пути патчей»).
- `PATCHED_ATTRS`-наследники и staticmethod-присваивание `capture` —
  оба приёма продиктованы буквальной (не по духу) реализацией
  залоченного `tasks/T037/acceptance_tests/test_sandbox.py`
  (`_own_fixture_definitions` ловит любой `class`/`def` с этим именем,
  не глядя на базовые классы) — если Оператор сочтёт эти два отступления
  от «только импорты/пути патчей» неприемлемыми, альтернатива
  (переименовать САМ `TmpRootTest` во всех вызывающих местах файла)
  меняет на порядок больше строк ради того же результата; выбран
  вариант с меньшим диффом.
