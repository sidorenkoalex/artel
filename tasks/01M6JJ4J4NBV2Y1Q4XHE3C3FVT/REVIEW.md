---
task: 01M6JJ4J4NBV2Y1Q4XHE3C3FVT
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Граница git для ролей — отказ git clean и git в репозитории пульта, команда удаления файла задачи

## Фаза A — план
- Таблица покрытия полна: требования 1–10 привязаны к шагам 1–8, замер требования 6 есть в «Подходе» (2.8/2.4 с → 7.6/7.4 с).
- Шаги — проверяемые единицы (механизм, окружение, диспетчер, миссия, doctor, settings, документация, тесты), не микрооперации.
- Подход (обёртка на PATH + потолок в `role_env`, снятие диспетчером через PATH) соответствует требованиям 5, 6, 10 и решениям Оператора. «Влияние на систему» сходится с diff: 14 файлов, все в зонах SPEC; правка существующего теста — только мандатная `commit_probe`.
- Пробел плана: шаг 8 заявляет в `tests/test_role_git.py` только чистые функции. Тест на сквозное поведение `role_git.main`, диспетчера, `task-rm` и doctor план в `tests/` не закладывает (см. R1-F2).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `runner.py:1214-1217`: `GIT_CEILING_DIRECTORIES` = `Path(config.ROOT).resolve()`; AC-1 зелёный в планке |
| 2 | OK | `role_git.repo_paths`/`classify`/`main:313-326`: проверяются цепочка `-C`, `--git-dir`/`--work-tree`/`GIT_*`, `core.worktree`, вложенность после `realpath`; отказ «рабочая копия другой задачи» главнее «репозиторий пульта»; `--version`/`help` проходят |
| 3 | реализовано не так | Псевдоним, тело которого начинается с `-c <ключ>=<значение>`, раскрывается в `clean` мимо отказа, а pager/`!`-псевдоним, заданные `-c` в теле псевдонима, механизм не видит (R1-F1). Прочие формы AC-4–AC-7 работают |
| 4 | OK | `task_files.py`: набор проверяется целиком до первого `unlink`, родитель разрешается, сам путь — нет; `.git` любого уровня, каталог, ссылка наружу, файл ссылки документов отклоняются; `ARTEL_TASK` под признаком роли; `_ROLE_ALLOWED_COMMANDS` с комментарием; `docs_dir_note` называет `task-rm` |
| 5 | OK | `artel._run_without_role_git`: из PATH убирается только каталог обёртки этой копии, восстановление в `finally`; переменной-выключателя нет; все команды идут через таблицу (`artel.py:2646`), ранних обходов нет |
| 6 | OK | Каталог обёртки — второй элемент PATH (долгоживущий AC-16 зелёный); замер есть в PLAN |
| 7 | OK | `doctor/isolation.py::check_role_git_boundary`: (а) без обёртки из `mkdtemp(dir=<ROOT>/.artel)`, (б) только `clean -n`; `OSError` → `fail`; `rmtree` в `finally` |
| 8 | OK | `docs/stack.md` (белый список с `task-rm`, абзац о границе, строка паритета с принятыми ограничениями), `docs/reference/role-home.md`, `task_files.py` есть в карте |
| 9 | OK | `Bash(git clean:*)` в `deny`; ручной перенос описан |
| 10 | OK | `ARTEL_GIT_GUARD_ROOT` и потолок из одного разрешённого `config.ROOT`; корни — объединение корня обёртки и переменной; `ROLE_GIT_BIN` берётся от `__file__` модуля runner |

## Замечания

- **major** — `orchestrator/role_git.py:262-264` (`_alias_refusal`) — разбор тела псевдонима выкидывает слова, начинающиеся с `-`, но не пропускает значение опции. Git разрешает в теле псевдонима `-c <ключ>=<значение>`: проверено, `git -c "alias.zz=-c a.b=c version" zz` исполняется, а `-C`/`--git-dir` git отвергает («changes environment variables»). Сценарий: в своей рабочей копии `git -c 'alias.cl=-c a.b=c clean -fX' cl` или `cl = -c a.b=c clean -fX` в `.git/config`. `_alias_refusal("cl", [("alias.cl", "-c a.b=c clean -n")])` возвращает `None`: первым словом считается `a.b=c`, оно не встроенная команда и не псевдоним. Настоящий git на временном репозитории `-c "alias.cl=-c a.b=c clean -n" cl` выдал `Would remove junk.txt` — `git clean` проходит мимо отказа требования 3, то есть повторяется инцидент. Тот же класс: `-c core.pager=<git …>`, `-c core.fsmonitor=<git …>` или `-c alias.y=!…` в теле псевдонима не попадают в `git config --list` и минуют `_command_refusal` (`role_git.py:341`). Предложение: разбирать слова тела тем же `parse()` (с пропуском значений `WITH_VALUE`); записи `-c`/`--config-env` из тела добавлять к проверяемой конфигурации (pager/fsmonitor/псевдонимы) либо отклонять псевдоним, тело которого задаёт `-c`/`--config-env`. Тест — в `tests/test_role_git.py` с заявкой «Ловит мутацию».
- **major** — `tests/test_role_git.py` (весь файл) и все файлы планки с пометкой «Группа: разовый» — ядро механизма после мержа никто не сторожит (ADR-0018, п. 3). Планка помечена «разовый», потому что guard запрещает git через `subprocess` в долгоживущих файлах test_author. На `tests/` разработчика этот запрет не распространяется (`scripts/guard.py:4328`, `long_lived_sign_hits` — правило для долгоживущих файлов задачи), а свойства — это свойства кода. Проверено временной мутацией: прогон `tests/test_role_git.py`, `tests/test_01m6jj4j4nbv2y1q4xhe3c3fvt_role_git_boundary.py` и `tests/test_multitarget.py` остаётся зелёным (66 passed) на каждой из мутаций:
  - `role_git.py:328` — отказ `sub == "clean"` выключен;
  - `role_git.py:314` — отказ «рабочая копия другой задачи» выключен;
  - `role_git.py:341` — отказ по pager/псевдониму выключен (`reason = None`);
  - `artel.py:2787` — диспетчер не снимает обёртку из PATH;
  - `task_files.py:34` — `<id>` ≠ `ARTEL_TASK` не отклоняется;
  - `role_prompt.py:531` — `task-rm` убран из миссии;
  - `doctor/isolation.py:482` — `check_role_git_boundary` не отдаёт `fail`.

  Ни один `tests/` не обращается к `role_git.main`, `_run_without_role_git`, `cmd_task_rm`, `docs_dir_note`, `check_role_git_boundary` (grep по `tests/` находит только `test_role_git.py`, а в нём — лишь чистые функции). После мержа регрессия любого из этих мест пройдёт CI зелёной. Предложение: добавить в `tests/` (например, в `tests/test_role_git.py`) сквозные тесты над временным дублёром ROOT вне настоящего репозитория:
  - `role_git.main` — `clean` в своей копии, чужая копия, pager с git (можно подменить `os.execv`/`real_git`);
  - `artel._run_without_role_git` — PATH дочернего процесса без каталога обёртки, восстановление `os.environ`;
  - `task_files.cmd_task_rm` — проверка `ARTEL_TASK`;
  - `role_prompt.docs_dir_note` — упоминание `task-rm`;
  - `doctor.check_role_git_boundary` — `fail` без потолка и без обёртки.

  Каждый тест — с заявкой «Ловит мутацию».
- **minor** — `orchestrator/task_files.py:51-52` — один и тот же путь дважды в наборе (`task-rm <id> f f`, либо `f` и `./f`) проходит проверку оба раза. Первый `unlink` удаляет файл, второй падает необработанным `FileNotFoundError` с трассировкой. Вред мал (удалён только допустимый файл), но команда, обещающая «всё или ничего», завершается исключением. Предложение: убрать дубликаты в `planned` (или проверять повтор в `_check`).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | orchestrator/role_git.py:262-264 | Тело псевдонима с `-c k=v` перед `clean`: значение опции принимается за подкоманду; `-c core.pager=…`/`-c alias.y=!…` в теле не проверяются | `git -c 'alias.cl=-c a.b=c clean -fX' cl` в своей копии исполняет `git clean` (проверено на временном репозитории: `Would remove junk.txt`) — нарушено требование 3 | Разбирать тело `parse()` с пропуском значений `WITH_VALUE`; учитывать или отклонять `-c`/`--config-env` в теле; тест в `tests/test_role_git.py` ; исправлено (developer, итерация 2: `_alias_refusal` разбирает тело `parse()` с пропуском значений `WITH_VALUE`; `-c`/`--config-env` тела (`option_config`) проверяются — pager/fsmonitor с git и `core.worktree` → отказ, `alias.*` из тела участвуют в раскрытии; тесты `ConfigRefusalTest::test_config_options_in_alias_body_are_not_the_subcommand`, `WrapperMainTest::test_pager_and_alias_with_dash_c_in_body_refused`; на настоящем git через обёртку `-c 'alias.cl=-c a.b=c clean -fX' cl` — отказ, файл цел) |
| R1-F2 | fixed | tests/test_role_git.py (весь файл); планка «разовый» | В `tests/` нет сторожа для `role_git.main`, `artel._run_without_role_git`, проверки `ARTEL_TASK` в `task-rm`, `task-rm` в `docs_dir_note` и `fail` в doctor; все 7 временных мутаций остались зелёными | После мержа регрессия ядра границы git проходит CI незамеченной | Добавить сквозные тесты в `tests/` над временным дублёром ROOT, с заявками «Ловит мутацию» ; исправлено (developer, итерация 2: в `tests/test_role_git.py` сквозные тесты над временным дублёром ROOT — `WrapperMainTest` (`role_git.main`, `os.execv` подменён), `DispatcherPathTest` (`artel._run_without_role_git`), `TaskRmCommandTest` (`ARTEL_TASK`, повтор пути), `MissionTaskRmTest` (`docs_dir_note`), `DoctorBoundaryTest` (`ok`/`fail` без потолка/без обёртки); все 7 мутаций ревью и мутации R1-F1/R1-F3 красят файл. Мутация `role_git.py:328` в одиночку эквивалентна — `clean` отклоняет и `_alias_refusal`; выключение обоих мест — 4 красных теста) |
| R1-F3 | fixed | orchestrator/task_files.py:51-52 | Повтор пути в наборе не отсекается | Второй `unlink` падает трассировкой `FileNotFoundError` | Убрать дубликаты в `planned` ; исправлено (developer, итерация 2: `task_files.cmd_task_rm` не кладёт повтор пути в `planned`; тест `TaskRmCommandTest::test_repeated_path_removed_once`) |

## Вердикт
changes_requested: исправить R1-F1 (обход отказа `git clean` псевдонимом с `-c` в теле) и R1-F2 (долгоживущие тесты ядра в `tests/`); R1-F3 — по желанию, в той же итерации.

## Проверено исполнением
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M6JJ4J4NBV2Y1Q4XHE3C3FVT` — 119 passed, код выхода pytest 0.
- `python3 -m pytest -p no:cacheprovider -q tests/test_role_git.py tests/test_01m6jj4j4nbv2y1q4xhe3c3fvt_role_git_boundary.py tests/test_multitarget.py` — 66 passed, 14 subtests passed.
- Временные мутации (скрипт в каталоге документов; каждая правка возвращена, `git status --short` после прогона пуст) — 7 мутаций из R1-F2, на каждой те же три файла `tests/` зелёные (66 passed).
- `_alias_refusal("cl", [("alias.cl", "-c a.b=c clean -n")])` → `None`; настоящий git на временном репозитории вне ROOT: `git -C <tmp> -c "alias.cl=-c a.b=c clean -n" cl` → код 0, `Would remove junk.txt` (R1-F1).
- `git -c "alias.zz=-c a.b=c version" zz` → версия git (git допускает `-c` в теле псевдонима); `-C`/`--git-dir` в теле git отвергает «changes environment variables» — значит, класс R1-F1 ограничен `-c`/`--config-env`.
- `python3 -c "from orchestrator import doctor; …"` — фасад doctor несёт `providers.UnknownProviderError`, `runner`, `shutil`, `subprocess`, которыми пользуется новая строка.

## Предложения системе
- Обоснование группы «разовый» в планке («guard запрещает git через subprocess в долгоживущих файлах») переносит сторож свойств кода на разработчика, но в плане разработчика это нигде не обязательно — ядро задачи осталось без сторожа после мержа. Кандидат для `skills/test-authoring.md`: если свойство кода уходит в «разовый» из-за ограничения guard, test_author в заголовке файла называет, какой тест `tests/` разработчика обязан его держать.
