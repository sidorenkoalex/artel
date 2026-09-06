---
task: 01M1SG9WPVN8P3S4X7975N9T69
type: spec
author_role: analyst
status: ready
schema_version: 4
zones: docs/reference/role-home/, docs/reference/role-home.md, orchestrator/doctor.py, tests/
budget_usd: 10
---

# SPEC: сторож Bash роли — возврат запрета полного прогона tests/ до таймаута на тест

## Контекст
Раскатка изменений референса `.artel/home/.claude/` — операторское
действие после мержа (`orchestrator/catalog._deploy_role_home_reference`
копирует референс в `.artel/home/` только при отсутствии каталога, то
есть на холодном старте, поэтому правка референса на уже работающем
пульте сама туда не попадает). Хук `docs/reference/role-home/claude/
hooks/bash_guard.py` (коммиты f0c537b2, 80c38245; PreToolUse, matcher
`Bash`) отклонял до запуска полный прогон набора тестов внутри шага
роли; задача стека ч.3 (01M1RDCEF0JZ4AVQRE43JFH8TN, коммит dea8016b)
сняла его как временный вместе с тестом `tests/test_role_bash_guard.py`.
После снятия developer задачи 01M1REVEZ1HESMJ7AFD5A9MEJ8 (P0) пять раз
запустил полный набор за один шаг и ушёл в таймаут 45 минут ($25.7,
PLAN.md не написан) — правило текстом в скилах не удержало класс в
третий раз. Штатное закрытие класса — таймаут на каждый тест (P1 фазы
S, `pytest-timeout`), которого ещё нет; до его появления хук
восстанавливается в прежней редакции.

## Требования

1. Восстановить `docs/reference/role-home/claude/hooks/bash_guard.py` и
   его подключение в `docs/reference/role-home/claude/settings.json`
   (`hooks.PreToolUse`, matcher `Bash`, команда `python3
   "$CLAUDE_CONFIG_DIR/hooks/bash_guard.py"`, timeout 10) в редакции
   коммита 80c38245 (discover по каталогу планки задачи разрешён, по
   всему дереву — нет), сохранив текущий список `permissions.deny`.
   Логика отказа не расширяется сверх этой редакции.
2. Восстановить `tests/test_role_bash_guard.py` той же редакции (коммит
   80c38245); случай «пять полных прогонов подряд» не добавлять — хук
   отклоняет каждый прогон по отдельности, повторный отказ не даёт
   нового покрытия.
3. Показать (тестом или докстрингом), что `python3` в команде хука
   резолвится через PATH роли из манифеста стека (`orchestrator/
   runner.py::role_env`/`_venv_interpreter_bin` — каталог `.artel/venv/
   bin` первым в PATH процесса, унаследованном хуком от CLI роли), а не
   через профиль оболочки Оператора.
4. Проверка `orchestrator/doctor.py::check_role_home_reference` обязана
   видеть каталог `hooks/` референса как часть сверки: расхождение
   развёрнутого `hooks/bash_guard.py` с референсом — WARN, как по
   `CLAUDE.md`/`settings.json`.
5. Докстринг хука и `docs/reference/role-home.md` несут условие снятия:
   после мержа задачи P1 (таймаут на тест) хук снимается ею, не руками
   Оператора.
6. Раскатка восстановленного референса в `.artel/home/.claude/` —
   операторское действие после мержа (деплой — только на холодном
   старте); в RETRO задачи это должно быть названо явно.

## Критерии приёмки

AC-1. `docs/reference/role-home/claude/hooks/bash_guard.py` существует,
и его функция `verdict()` даёт тот же результат, что редакция коммита
80c38245: голый `python3 -m unittest` (без имён модулей/файлов) —
отклонён; `discover` без `-s`/с `-s tests`/`-s .` — отклонён; `discover`
с `-s <каталог планки задачи>` (например
`tasks/<id>/acceptance_tests`) — разрешён; `pytest`/`python3 -m pytest`
без аргументов-путей или с путём `tests`/`tests/`/`.` — отклонён; по
конкретному модулю/файлу — разрешён. Список отклоняемых форм не шире и
не уже, чем в редакции 80c38245.

AC-2. `docs/reference/role-home/claude/settings.json` несёт
`hooks.PreToolUse` с записью `{"matcher": "Bash", "hooks": [{"type":
"command", "command": "python3 \"$CLAUDE_CONFIG_DIR/hooks/bash_guard.py\"",
"timeout": 10}]}`; текущий список `permissions.deny` (8 записей на
момент SPEC) сохранён без изменений и без потерь ни одной записи.

AC-3. `tests/test_role_bash_guard.py` восстановлен в редакции коммита
80c38245 (классы `VerdictTest` — включая
`test_blocks_full_suite_forms`, `test_allows_targeted_runs_and_other_commands`,
`test_reason_names_the_rule_and_the_alternative` — и `HookProtocolTest`
с проверкой кода возврата 2/стандартного вывода ошибки и сверкой
`settings.json`); случай «пять полных прогонов подряд» в файл не
добавлен. Прогон `python3 -m unittest tests.test_role_bash_guard` —
зелёный.

AC-4. Докстринг `bash_guard.py` содержит явное утверждение (со ссылкой
на `orchestrator/runner.py::role_env`/`_venv_interpreter_bin`), что
`python3` команды хука резолвится через PATH роли манифеста стека
(`.artel/venv/bin` — первым в PATH процесса, из которого хук
запускается как дочерний процесс CLI роли), а не через профиль
оболочки Оператора. Отдельный тест на этот пункт не обязателен —
утверждение может быть только текстовым (докстринг).

AC-5. `tests/test_doctor.py` несёт тест: если развёрнутый
`.artel/home/.claude/hooks/bash_guard.py` отсутствует или отличается
побайтово от референса, `orchestrator.doctor.check_role_home_reference()`
возвращает статус `warn` с упоминанием `hooks/bash_guard.py` в перечне
расхождений. Существующий обход `_role_home_diff` (`reference.rglob("*")`)
уже проходит по вложенным каталогам референса — код
`orchestrator/doctor.py` для этого критерия менять не требуется, тест
фиксирует поведение как регресс-гвардию.

AC-6. Докстринг `bash_guard.py` и раздел `docs/reference/role-home.md`
несут одинаковое по смыслу условие: хук — временная мера до появления
таймаута на тест (P1, `pytest-timeout`); после мержа задачи P1 хук
снимается ЕЮ, не ручной правкой Оператора.

AC-7. Раздел «Контекст» настоящего SPEC называет раскатку в
`.artel/home/.claude/` операторским действием после мержа первым же
предложением — это предложение детерминированно попадает в «Суть»
`docs/retro/<id>.md` при закрытии задачи (`orchestrator/retro.py::
_first_context_sentence`), других действий по этому пункту не требуется.

## Не входит

- Таймаут на каждый тест (P1, `pytest-timeout`) — предмет отдельной
  задачи, здесь хук — временная мера до её появления (см. AC-6).
- Ограничение шага роли по времени выполнения CLI-команды.
- Правка `skills/*.md`.
- Случай «пять полных прогонов подряд» в `tests/test_role_bash_guard.py`
  (см. требование 2/AC-3) — не добавляется намеренно.
- Изменение кода `orchestrator/doctor.py` — зона в границах задачи
  только потому, что существующая проверка должна ПРОДОЛЖИТЬ покрывать
  восстановленный файл (см. AC-5); если тест покажет, что покрытие уже
  корректно без правок, код `doctor.py` не трогается.

## Материалы

- Коммиты: f0c537b2 (первая редакция хука+теста), 80c38245 (уточнение
  discover по каталогу планки), dea8016b (снятие хука, добавление
  `check_role_home_reference`, стек ч.3 — `orchestrator/runner.py::role_env`).
- `docs/backlog.md`, приоритет 1 (копилка 05.09).
