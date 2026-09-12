---
task: 01M2B6K3EM7F2J72RC2F520Y2K
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Признак роли в окружении и conftest вместо хука роли

## Подход

Решение Оператора 12.09 — заменить клиентский PreToolUse-хук
(`docs/reference/role-home/claude/hooks/bash_guard.py`) и часть
`permissions.deny` (`init`/`doctor --restore`) LLM-независимым
признаком процесса роли в окружении: `runner.role_env` кладёт
`ARTEL_ROLE`/`ARTEL_TASK` (константы `orchestrator/config.py`), а сам
CLI их читает в двух местах.

1. `orchestrator/config.py` — константы `ARTEL_ROLE_ENV`/`ARTEL_TASK_ENV`
   (значения `"ARTEL_ROLE"`/`"ARTEL_TASK"` — буквальные строки требования 1).
2. `orchestrator/runner.py::role_env(role=None, task_id=None)` — второй
   параметр опционален (обратная совместимость вызовов без задачи,
   `orchestrator/doctor/*` вне зоны задачи), кладёт обе переменные в
   результат, только если значение передано.
3. Корневой `conftest.py` (новый файл) — хук `pytest_configure`: под
   `ARTEL_ROLE` в окружении отказывает (`pytest.exit`, код 2) сбору,
   если среди `sys.argv` нет позиционного аргумента-пути ниже `tests/`
   или несущего сегмент `acceptance_tests` под `tasks/`. Логика
   позиционных аргументов (пропуск флагов со значением, разбор `::`
   test-селектора) — та же идея, что была у `bash_guard._pytest_
   verdict`, но применена только к аргументам ЭТОГО процесса pytest
   (`sys.argv`), не к произвольной команде Bash — сфера уже сознательно
   у́же прежнего хука (тот же выбор, что и вся эта задача: механизм
   переезжает с протокола клиента на возможности самого CLI).
4. `orchestrator/artel.py` — `_role_restricted_command(cmd, rest)` +
   `_refuse_if_role_restricted`, вызывается в `main()` до диспетчерской
   таблицы: под `ARTEL_ROLE` отказывает `init`/`doctor --restore`/
   `canary pool-seal` текстом «команда недоступна процессу роли
   `<роль>`», реализации команд не вызываются.
5. Курируемый слой: `hooks.PreToolUse` убран из `settings.json`,
   `hooks/bash_guard.py` удалён физически (вместе с каталогом `hooks/`,
   который без него пуст); `permissions.deny` не тронут — сверено
   построчно с версией до правки. `docs/reference/role-home.md`
   переписан под новый механизм (файл в зоне задачи, не защищённый
   путь — правка прямая, не unified-diff-приложение).
6. Тесты хука `bash_guard` (`tests/test_role_bash_guard.py`) удалены —
   модуль, который они грузили по пути, снят пунктом 5; равноценная
   проверка гарантии («полный прогон набора тестов роли отказывает»)
   переехала в новый `tests/test_conftest_role_guard.py` (обязателен
   по имени требованием 5(а)/AC-4). `tests/test_doctor.py::
   RoleHomeReferenceHooksDirTest` (сверка `check_role_home_reference` на
   примере `hooks/bash_guard.py`) переименован в
   `RoleHomeReferenceSettingsFileTest` и переставлен на `settings.json`
   — тот же принцип сверки (`_role_home_diff` не в зоне задачи и не
   правится), другой файл-пример, поскольку прежнего в референсе больше
   нет.

Постоянные регрессионные юниты (кроме обязательного `tests/
test_conftest_role_guard.py`) добавлены по аналогии с уже существующими
местами: `tests/test_multitarget.py::RoleEnvTest` — два метода на
AC-1 (`ARTEL_ROLE`/`ARTEL_TASK` в `role_env`, поведение без `task_id`);
новый `tests/test_artel_role_restricted_commands.py` — гейт диспетчера
на AC-5 (три команды, оба состояния ARTEL_ROLE, плюс регресс «голый
`doctor` не ограничен»). Планка задачи (`tasks/01M2B6K3EM7F2J72RC2F520Y2K/
acceptance_tests/`) покрывает то же самое поведение сквозным
subprocess-прогоном — постоянные юниты добавлены как быстрая регрессия
в `tests/`, которую гоняет CI на каждый пуш (планка гоняется только на
гейте приёмки этой конкретной задачи).

## Шаги

1. `orchestrator/config.py` — константы `ARTEL_ROLE_ENV`/`ARTEL_TASK_ENV`.
2. `orchestrator/runner.py` — `role_env` несёт второй параметр
   `task_id`, кладёт обе переменные; вызов в `run_agent_once` передаёт
   `task_id`. Регрессия — `tests/test_multitarget.py::RoleEnvTest`.
3. Корневой `conftest.py` — гейт сбора pytest по `ARTEL_ROLE`.
   Регрессия — новый `tests/test_conftest_role_guard.py`.
4. `orchestrator/artel.py` — гейт диспетчера на три команды. Регрессия —
   новый `tests/test_artel_role_restricted_commands.py`.
5. Курируемый слой: `settings.json` (снятие `hooks.PreToolUse`),
   удаление `hooks/bash_guard.py`, правка `docs/reference/role-home.md`.
6. Уборка тестов хука: удаление `tests/test_role_bash_guard.py`,
   адаптация `tests/test_doctor.py::RoleHomeReferenceHooksDirTest` ->
   `RoleHomeReferenceSettingsFileTest`.
7. Регенерация `docs/codebase-map.md` (правка `*.py` в `orchestrator/`
   и `tests/`).

Один MR — изменения тесно связаны (один механизм, три читателя),
раздельные MR только фрагментировали бы обзор одного и того же решения.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 3 |
| 3 | 4 |
| 4 | 5 |
| 5 | 3, 4, 6 |

## Влияние на систему

Зона задачи узкая и не пересекается с логикой `orchestrator/doctor/`:
`check_role_home_reference`/`_role_home_diff` (`orchestrator/doctor/
preflight.py`) остаются НЕТРОНУТЫМИ — сверка родовая (по каждому файлу
референса), правка данных референса (снятие `hooks/bash_guard.py`,
изменение `settings.json`) не требует правки её кода. Единственное
следствие для существующих тестов doctor — пара `tests/test_doctor.py`,
завязанная на КОНКРЕТНЫЙ пример файла (`hooks/bash_guard.py`), больше
не находит его в референсе; заменена на равноценную проверку того же
свойства на `settings.json` (шаг 6), без ослабления: то же поведение
`_role_home_diff` (отсутствие/расхождение файла референса — warn)
проверяется на другом, оставшемся в референсе файле.

Уже развёрнутый на этом пульте `.artel/home/.claude` этим изменением
пультом НЕ переписывается: `catalog._deploy_role_home_reference`
разворачивает референс `docs/reference/role-home/claude/` в
`.artel/home/.claude` только при отсутствии каталога (холодный старт),
на уже работающем пульте изменения референса сами по себе никуда не
попадают. Расхождение (у Оператора в `.artel/home/.claude/settings.json`
всё ещё будет висеть старый `hooks.PreToolUse`, а `hooks/bash_guard.py`
никуда не денется) увидит `doctor role-home-reference` (WARN с
перечнем отличающихся файлов) — переразворачивает каталог сам
Оператор, синхронизацию эта задача не автоматизирует (не входит в
зону, тот же принцип, что и остальная синхронизация референса).

Класс защиты сузился осознанно, решением Оператора 12.09: прежний хук
ловил ЛЮБУЮ Bash-команду роли (включая исторические формы `python3 -m
unittest`), новый `conftest.py` — только собственный процесс pytest
(единственный раннер тестов по `pyproject.toml`/skills сегодня).
Диспетчерский гейт `artel.py` заменяет ТОЛЬКО `init`/`doctor --restore`/
`canary pool-seal` из `permissions.deny` — остальные записи
(`git clone`, `gh repo clone`, `git remote add`, чтение пула канарейки,
`openssl enc -d`, `security find-generic-password`) остаются на
клиентском `permissions.deny` без изменений (SPEC, требование 4/AC-6) —
эта задача их не трогает и не заменяет.

Инварианты/лимиты/гейты FSM не затронуты: `MAX_PARALLEL_TASKS`,
бюджетные потолки, гейты зон/ёмкости и т.п. — вне зоны, ни один не
ослаблен. Откат — `git revert` этого MR: возвращает хук и три строки
`permissions.deny`, `role_env`/`artel.py`/`conftest.py` — к прежнему
поведению (параметр `task_id` необязателен, откат не ломает вызовы,
появившиеся после).

## Риски

- Роль, чей шаг реально нуждается в прогоне ПОЛНОГО набора `tests/`
  внутри шага (случая по конвенции быть не должно — skill
  `coding-standards.md` прямо это запрещает), теперь получит отказ от
  `conftest.py`, а не от клиентского хука — та же по духу гарантия,
  другой канал. Риск отсутствия у роли способа обойти гейт нежелательным
  образом не рассматривается — гейт для этого и ставится.
- `docs/reference/role-home.md` правится напрямую (файл в зоне, не в
  списке защищённых путей `config.PROTECTED_PATHS`) — если Оператор
  сочтёт этот путь фактически защищённым, откат — тривиальный `git
  revert` части диффа.

## Предложения системе

- `orchestrator/doctor/preflight.py::_role_home_diff` завязка тестов на
  КОНКРЕТНОЕ имя файла референса (а не на факт «хоть один файл
  референса меняет/удаляет разработчик») — второй раз за две задачи
  (T058 снятие/восстановление хука, эта задача снятие) правка референса
  требует синхронной правки теста doctor по имени файла. Возможный
  адрес: тест-параметризация по списку файлов референса на момент
  прогона, а не по литералу `hooks/bash_guard.py`.
