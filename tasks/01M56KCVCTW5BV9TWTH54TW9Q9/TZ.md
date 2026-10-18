---
task: 01M56KCVCTW5BV9TWTH54TW9Q9
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Окружение шага роли внешнего проекта: PATH, сводка и логи suite-run

# Окружение шага роли внешнего проекта: PATH, сводка и логи suite-run

## Факты

Строка бэклога 18.10 (П1) «Окружение шага роли внешнего проекта: PATH, uv, логи и сводка suite-run», разбор «что прибито под артель».
- PATH роли — только каталоги объявленных инструментов (`orchestrator/runner.py:945-958`, `_role_path_dirs`: venv пульта, git, gh, claude). Прогон `pytest-own` наследует PATH вызывающего (`orchestrator/acceptance.py:152-172`, `_own_env`), поэтому `suite-run` из шага роли на sled 01M55SKHZ293CCAK0N7T4H7ZMR дал 201 ложное падение: `FileNotFoundError: 'bash'` (196) и `'date'` (5) (`.artel/logs/suite-run/01M55SKHZ293CCAK0N7T4H7ZMR/…-suiterun-1.log`). Гейты пульта гоняют набор из своего процесса с полным PATH — их это не задевает.
- Сводка прогона не знает слова `deselected` (`acceptance.py:292-295`, `_RUN_CATEGORY`) — у sled («201 failed, 4309 passed, 1156 skipped, 4 deselected, 13 warnings in 52s») разбор взял последнее совпадение «13 warnings in 52s» и показал разработчику «прошло: 0, упало: 0».
- `uv` (команда профиля sled) не объявлен инструментом роли и находится только потому, что лежит в одном каталоге с `gh` (`/opt/homebrew/bin`); `FileNotFoundError` отсутствующей команды профиля в `acceptance.run`/`collect`/`run_plank` не перехвачен (трейсбек вместо отказа; `two_sided` его ловит).
- Роли на Claude недоступен каталог логов `suite-run` (у Codex открыт вторым `--add-dir`, `orchestrator/providers/codex.py:416-443`; у Claude — только каталог документов, `orchestrator/providers/claude.py:193-194`): developer sled «лог открыть не дали».

## Требуется

1. Прогон `pytest-own` (все места запуска профиля) получает PATH, в котором есть системные каталоги (`/usr/bin`, `/bin`, `/usr/sbin`, `/sbin`) и каталог исполняемого файла первой команды профиля (`command[0]`, найденный по PATH пульта), независимо от того, запущен он процессом пульта или из шага роли; порядок и точный состав аналитик обосновывает в SPEC. У `pult-pytest` и у артели PATH прогона не меняется.
2. Разбор сводки прогона знает `deselected` (и `xfailed`/`xpassed`, если их нет) — счёт «прошло/упало/пропущено» верный на строке sled выше.
3. Отсутствие исполняемого файла команды профиля (`FileNotFoundError`) во всех местах запуска профиля — именованный отказ прогона («команда профиля <имя> не найдена»), не трейсбек.
4. Роль на Claude видит каталог логов `suite-run` своей задачи (вторым `--add-dir`, как у Codex), только чтение по смыслу; у артели — тоже (паритет с Codex) либо аналитик обосновывает иное.
5. У артели argv, окружение и `cwd` прогонов `pult-pytest` не меняются; зафиксировать тестами до правки.
6. Тесты детерминированы, без сети: учебный проект `pytest-own` с командой-обёрткой, вызывающей `bash`/`date`, запущенный с урезанным PATH «как у роли», — зелёный; разбор строки сводки sled; отсутствующая команда профиля — отказ; argv Claude-роли содержит каталог логов suite-run задачи.

Критерии приёмки:
- suite-run/plank-run из шага роли внешнего проекта не падают из-за PATH роли;
- сводка с deselected считается верно;
- отсутствующая команда профиля — именованный отказ;
- у артели прогоны `pult-pytest` прежние.

Зоны: `orchestrator/acceptance.py`, `orchestrator/runner.py`, `orchestrator/providers/claude.py`, `tests/`.

Только чтение: `orchestrator/stack.py`, `orchestrator/providers/codex.py`, `orchestrator/project_profile.py`, `orchestrator/suite_run.py`, `targets.yaml`, `docs/backlog.md`. Правка вне зон — эскалация до SPEC.

Не входит: повторная загрузка CPython uv на каждый прогон (решается подполем `env` профиля — `UV_PYTHON_INSTALL_DIR`, правка `targets.yaml` Оператором); выкладка планки внутрь workdir (отдельная строка); Codex на внешних проектах.

Рамка: $35. Набор моделей — по умолчанию.
