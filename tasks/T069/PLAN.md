---
task: T069
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: B1a — изоляция обвязки целевого: MCP-вектор и флаги CLI

## Подход

Флаг — `--strict-mcp-config`, подтверждён `claude --help` установленного
пина CLI (`config.CLI_VERSION_PIN = "2.1.227"`, сверено вручную перед
планом):

    --strict-mcp-config   Only use MCP servers from --mcp-config,
                           ignoring all other MCP configurations

Курируемого `--mcp-config` у пульта нет (SPEC, требование 1) — один
`--strict-mcp-config` без него резолвит шагу ноль MCP-серверов
независимо от `.mcp.json` рабочего каталога. Добавляется без условия и
без новой константы `config.py`: в отличие от `--setting-sources`
(строковый список источников, реально варьируемый), это булев флаг без
второго состояния в объёме задачи — заводить под него отдельную
константу означало бы абстракцию без необходимости (coding-standards).

Argv команды `claude` сегодня строится один раз, инлайново, внутри
`runner.run_agent_once` (`orchestrator/runner.py:653-667`) — единственное
реальное место сборки (docstring `spawn_agent`). SPEC, требование 2,
явно просит для `isolation_smoke` «офлайн-сборку cmd/env шага» —
не константу-прокси (как было сделано для `--setting-sources` в T058),
а именно cmd. Выношу сборку списка в чистую функцию `runner.role_cmd()`
(без побочных эффектов, без аргументов — сегодняшний argv ни от чего не
зависит, кроме `config.AGENT_SETTING_SOURCES`) и зову её из обеих точек:
`run_agent_once` — для реального запуска, `doctor.isolation_smoke` — для
офлайн-проверки. Один источник истины вместо двух синхронизируемых
руками списков флагов; заодно закрывает риск, отмеченный в PLAN.md T058
(«структурная проверка ловит дрейф константы, но не дрейф самого argv»)
— здесь и структурная, и реальная сборка — один и тот же код.

`isolation_smoke` получает четвёртый маркер, по образцу трёх уже
существующих (user-слой HOME, project-CLAUDE.md-в-промпте,
`--setting-sources`): сверяет `"--strict-mcp-config" in runner.role_cmd()`.
Итоговый `detail` при `ok` называет проверку словом «MCP» — под это
заточен приёмочный тест AC-2, ищущий подстроку "mcp" в тексте.

Инвентаризация обвязки target'а (требование 3) — новая функция
`doctor.check_target_wrapper(target)`, по образцу `check_target_layout`:
докфуд — `skip` (не внешний target, ADR-0003 3д), иначе смотрит
`config.PROJECTS/<target>/workspace/` (`runner.role_cwd` — то же дерево,
что видит шаг роли, не артефактный репозиторий `config.PROJECTS/<target>`
целиком, куда git-первичка A2b коммитит SPEC/PLAN/REVIEW) на присутствие
`.claude`, `.mcp.json`, `CLAUDE.md`, `AGENTS.md`. Любой найден — `warn`
с перечислением найденных путей (детерминированный порядок — по
кортежу маркеров, не `os.listdir`); ничего не найдено — `ok`. Никогда
`fail` (требование 3: «ничего не блокирует»). Вызывается из `all_checks`
в существующем цикле по `targets.load()`, рядом с `check_target_layout`
(SPEC «Материалы» называет это место образцом).

## Шаги

1. `orchestrator/runner.py`: вынести сборку argv в `role_cmd() -> list[str]`
   (без аргументов и без побочных эффектов), добавить `--strict-mcp-config`
   в конец списка; `run_agent_once` зовёт `spawn_agent(role_cmd(), ...)`
   вместо инлайнового литерала.
2. `orchestrator/doctor.py`: `isolation_smoke` — четвёртый маркер
   (`"--strict-mcp-config" not in runner.role_cmd()` → `leaks.append(...)`
   с текстом, содержащим «MCP»); финальный `ok`-detail дополнен
   упоминанием MCP-изоляции.
3. `orchestrator/doctor.py`: `check_target_wrapper(target)` — новая
   функция; `all_checks` зовёт её в цикле `for name, entry in
   declared.items()` рядом с `check_target_layout(name)`.
4. Юнит-тесты:
   - `tests/test_agent_prompt.py::PromptChannelTest` — новый метод:
     `--strict-mcp-config` в argv обеих ролей (`in_dev`, `review`),
     `--mcp-config` отсутствует (тем же `argv_of`, что и соседние
     проверки).
   - `tests/test_doctor.py::IsolationSmokeTest` — мутационный тест
     четвёртого класса: `mock.patch.object(doctor.runner, "role_cmd",
     return_value=[...без --strict-mcp-config...])` ловится проверкой
     (`status == "fail"`, detail называет MCP).
   - `tests/test_doctor.py` — новый класс `TargetWrapperCheckTest`:
     докфуд-skip, чистый target — `ok`, target с `.mcp.json`/`.claude`/
     `CLAUDE.md`/`AGENTS.md` в `workspace/` — `warn` с именами найденных
     путей в `detail`, никогда `fail`.
5. `docs/codebase-map.md`: регенерация (`python3 scripts/codebase_map.py`)
   — правка `.py` в `orchestrator/`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 4 (argv несёт `--strict-mcp-config`, без `--mcp-config`) |
| 2 | 2, 4 (`isolation_smoke` — маркер MCP-вектора, мутационный тест) |
| 3 | 3, 4 (`check_target_wrapper`, вызов из `all_checks`, юнит-тесты) |

## Влияние на систему

- `--strict-mcp-config` сужает то, что реально видит `claude` шага роли
  (ноль MCP-серверов вместо неограниченного `.mcp.json` рабочего
  каталога) — не расширяет ничего из ранее закрытого. `--setting-sources`
  и остальные существующие флаги (`--allowedTools`, `--output-format`,
  `--permission-mode`) не трогаются; порядок аргументов внутри `role_cmd()`
  сохранён 1-в-1 с прежним инлайновым литералом плюс один новый флаг в
  конце — CLI порядок не важен (прецедент T058, PLAN «Подход»).
- Рефакторинг сборки argv в `role_cmd()` — механический вынос без
  изменения поведения для существующих флагов; все текущие тесты,
  читающие argv через `argv_of`/`popen.call_args.args[0]`
  (`tests/test_agent_prompt.py`, `tests/test_doctor.py`,
  `tests/test_multitarget.py` и др.), продолжают видеть тот же список
  плюс один добавленный элемент — точечная правка, не смена контракта
  `spawn_agent`.
- `isolation_smoke` расширяется, три существующих маркера (user-слой,
  project-слой, `--setting-sources`) не меняются — их тексты и мутационные
  тесты (`tests/test_doctor.py::IsolationSmokeTest`) остаются как есть.
- `check_target_wrapper` — чисто информационная (`ok`/`warn`, никогда
  `fail`) добавка в `all_checks`: не меняет код выхода `doctor` для
  здоровых конфигураций без обвязки (`DoctorCommandTest` — существующий
  тест на код выхода 0 для здорового репо не задет, warn не влияет на
  `sys.exit`, только `fail` в `cmd_doctor`).
- Ни один существующий тест не ослаблен и не удалён; полный набор
  `tests/` прогнан после правки (AC-4) — единственная точка касания
  существующих файлов вне `runner.py`/`doctor.py` — новые тестовые
  методы/класс.
- Откат: три точечных изменения (вынос `role_cmd()` + один флаг, один
  блок в `isolation_smoke`, одна новая функция + одна строка вызова в
  `all_checks`) — обратимы одним `git revert` без побочных правок
  остального кода.

## Риски

- `--strict-mcp-config` — тот же класс риска, что уже принят у
  `--setting-sources` (PLAN T058, «Риски»): недокументирован вне
  `claude --help` установленной версии, апгрейд CLI мимо ревизии пина
  теоретически может сменить семантику флага молча. Живая канарейка
  MCP-вектора в headless `-p`-режиме не наблюдаема структурно (см.
  докстринг `tasks/T069/acceptance_tests/test_ac1_strict_mcp_command.py`
  — экспериментально подтверждено: свежий, ранее не подтверждённый
  project-scope MCP-сервер не подключается в headless-режиме ни с
  флагом, ни без него, дифференцирующего сигнала нет ни в каком
  варианте) — офлайн-сборка cmd (юнит-тест + `isolation_smoke`) остаётся
  единственной постоянной гарантией этого требования; расхождение
  фактического поведения флага с `--help`, если обнаружится на другой
  версии CLI, — повод для отдельного разбора при следующей осознанной
  ревизии `config.CLI_VERSION_PIN`, не для этой задачи.
- `check_target_wrapper` смотрит только `workspace/` внешнего target'а —
  не сам GitHub-репозиторий до его клонирования (`role_cwd` создаёт
  `workspace/` лениво). До первого реального шага роли на target'е
  (клон ещё не случился) проверка честно вернёт `ok` на пустом
  каталоге — не ложноотрицательный результат, а точное отражение
  текущего состояния локальной копии; не входит в объём этой задачи
  (GitHub-адаптер — B1b).

## Предложения системе
