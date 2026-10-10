---
task: 01M4KG7VHHXTVTW5TTX2PGY5RY
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/providers/codex.py, orchestrator/suite_run.py, orchestrator/suite_lock.py, docs/codebase-map.md, tests/
budget_usd: 25
---

# SPEC: suite-run доступен роли на Codex (песочница workspace-write)

## Контекст
Роль на Codex идёт под `codex exec --sandbox workspace-write`
(`orchestrator/providers/codex.py`: `SANDBOX_MODE` ~133, сборка argv ~417):
запись открыта только в рабочий каталог шага и в каталог документов задачи
(`--add-dir`, `ADD_DIR_FLAG` ~220). `suite-run` (`orchestrator/suite_run.py`)
пишет замок полных прогонов машины `config.LOGS / "suite-run" / "lock.json"`
(`orchestrator/suite_lock.py::path`), своё хозяйство в
`config.LOGS / "suite-run"` (`_state_dir` ~88) и логи
`config.LOGS / "<id>-suite-run-<n>.log"` (`_log_path` ~116) — всё в
`.artel/logs/` главной копии, вне корней песочницы, отсюда PermissionError
(случаи 06.10 — 01M49B90T1, 01M48WTP12; 07.10 — A3; обход Оператора —
ручные прогоны во временных клонах). Кроме того, `suite-run` открывает БД
пульта (`store.db()`, ~429, ~608), а полный прогон у предела после
01M4K2767FXKZ8EW7AME81SZ9N пишет журнал задачи и алерт
(`acceptance.run_full_suite`). Роль на Claude песочницы ОС не имеет и
`suite-run` запускает. Песочница Codex — второй рубеж защиты главной копии
после сторожа пульта (01M4G8KPP8DVNBCPGCAPSVMAKZ); её не ослаблять сверх
нужного.

## Требования
1. Роль на Codex запускает `suite-run <id>`, `suite-run <id> --failed` и
   `suite-run <id> --wait <минуты>` из своего шага так же, как роль на
   Claude: прогон идёт под тем же замком машины (тот же файл
   `suite_lock.path()`), отчёт и лог прогона доступны роли, итог прогона
   тот же.
2. Песочница роли на Codex расширяется минимально: на запись
   дополнительно открываются только каталоги, без которых `suite-run` не
   работает (каталог замка и хозяйства `suite-run`, каталог его логов) —
   по одному `--add-dir` на каталог в argv шага Codex. Рабочее дерево
   главной копии, каталог `.artel/` целиком и БД пульта на запись роли не
   открываются.
3. Если `suite-run` без записи в БД не обходится, сбой записи в БД из
   процесса роли не валит прогон: роль получает итог и отчёт прогона, а
   журнал задачи досылает процесс пульта. Если и так нельзя — эскалация
   с вариантами, а не расширение песочницы на `.artel/` целиком.
4. Поведение для ролей на Claude и для Оператора не меняется: argv и
   окружение шага роли на Claude прежние, `suite-run`, запущенный
   Оператором, работает как прежде.
5. Ослабления нет: замок не обходится, пределы прогона
   (`project_profile.full_suite_limit`) те же, сторож главной копии и
   прочие ограничения песочницы Codex (`--sandbox workspace-write`)
   остаются.
6. Смена ожидания существующих тестовых методов `tests/` — только
   перечнем раздела «Меняемое поведение» этого SPEC (инвариант 38).

## Критерии приёмки

AC-1. argv шага роли на Codex несёт дополнительные корни записи `suite-run`
по одному `--add-dir` на каталог: каталог замка `suite-run` (родитель
`suite_lock.path()`) и каталог логов `suite-run` присутствуют; мутация
«каталог замка не выдан» ловится.

AC-2. Среди значений `--add-dir` argv шага роли на Codex нет рабочего
дерева главной копии (корня пульта), нет каталога `.artel/` целиком и нет
пути БД пульта (`config.DB`) или его каталога.

AC-3. argv шага роли на Codex по-прежнему несёт `--sandbox workspace-write`
и `--add-dir <каталог документов задачи>`.

AC-4. `suite-run <id>` в процессе без права записи в БД (открытие БД на
запись подменено отказом) доводит прогон до итога и отчёта; сбой записи
журнала не меняет итог прогона (зелёный остаётся зелёным, красный —
красным).

AC-5. При сбое записи журнала из процесса без права записи в БД запись
журнала задачи о прогоне досылает процесс пульта (запись появляется в
журнале задачи).

AC-6. Прогон `suite-run` из процесса роли и полный прогон гейта пульта
пользуются одним и тем же файлом замка: пока замок держит один, второй не
стартует одновременно с ним.

AC-7. Шаг роли на Claude: argv и окружение процесса роли совпадают с
прежними (без новых `--add-dir` и без новых переменных окружения).

AC-8. Пределы прогона `suite-run` не меняются: при процессе без права
записи в БД прогон идёт с тем же пределом `project_profile.full_suite_limit`
и при его превышении даёт тот же исход «предел», что и прежде.

## Меняемое поведение
Сторож argv без каталога документов (`provider.command(model)`) этим SPEC
не меняется; меняется только ожидание «argv с каталогом документов минус
одна пара `--add-dir` равен argv без каталога» — у Codex в argv шага теперь
несколько пар `--add-dir` (требование 2).

- `tests/test_docs_dir_layout.py::CommandWithoutDocsDirTest::test_add_dir_only_when_docs_dir_given_and_model_stays_last`: `codex: opened[:at] + opened[at + 2:] == bare` → `codex: opened без всех пар --add-dir == bare, среди значений пар — каталог документов и корни suite-run` (требование 2)

## Оценка объёма и деление
Сигналы: число элементов зоны — 5 (`orchestrator/providers/codex.py`,
`orchestrator/suite_run.py`, `orchestrator/suite_lock.py`,
`docs/codebase-map.md`, `tests/`), из них `docs/codebase-map.md` и `tests/`
— общие зоны (`config.COMMON_ZONES`); собственных модулей — 3.

**Обоснование монолита** (материал для решения Оператора): выдача корней
записи в argv Codex (`codex.py`) без устойчивости `suite-run`/замка к
отсутствию записи в БД (`suite_run.py`, `suite_lock.py`) оставляет роль
на Codex с прежним провалом прогона; обратный порядок без выдачи корней
ничего не меняет для роли. Обе половины проверяются одной планкой
(AC-1..AC-8) и по объёму (3 модуля, 8 критериев) укладываются в класс
задачи ~$25.

## Не входит
- Зависание настоящего git в песочнице Codex (строка копилки 07.10,
  RealGitSandbox).
- Изоляция ролей Claude песочницей ОС (строка копилки 07.10 об асимметрии).
- Выборочный прогон тестов.
- Замер полного набора с заданным числом рабочих.
- Перевод ролей на Codex.
- Правка путей только для чтения из ТЗ: `orchestrator/acceptance.py`,
  `orchestrator/runner.py`, `orchestrator/providers/claude.py`,
  `orchestrator/store.py`, `orchestrator/config.py`,
  `orchestrator/checkpoint.py`, `orchestrator/liveness.py`,
  `orchestrator/notes.py`, `orchestrator/fsm_advance.py`,
  `orchestrator/advance_gates/`, `scripts/`, `.github/workflows/ci.yml`,
  `tests/test_invariants.py`, `docs/invariants.md`, `docs/triggers.md`,
  `docs/adr/`, `docs/roadmap.md`, `docs/backlog.md`,
  `docs/operator-session.md`, `templates/`, `skills/`, `CLAUDE.md`,
  `models.yaml`, `model_sets.yaml`, `roles.yaml`, `targets.yaml`, `.artel/`.

## Материалы
- ТЗ: `tasks/01M4KG7VHHXTVTW5TTX2PGY5RY/TZ.md` (бэклог «suite-run доступен
  роли с любым провайдером», копилка 07.10, очередь критичных 10.10 п.6).
- Предшественник: 01M4K2767FXKZ8EW7AME81SZ9N (журнал и алерт полного
  прогона у предела, слита 10.10).
- Сторож главной копии: 01M4G8KPP8DVNBCPGCAPSVMAKZ.
- Риск для PLAN: `store.db()` включает WAL (`store.py` ~341–352); чтение
  БД в WAL из процесса без записи в каталог БД может само упасть до
  записи журнала — это случай требования 3 (эскалация, если обойти нельзя).
