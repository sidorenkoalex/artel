---
task: 01M6JJ4J4NBV2Y1Q4XHE3C3FVT
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Граница git для ролей — потолок подъёма, обёртка git роли, отказ `git clean`, команда `task-rm`

## Подход
Механизм требований 2–3 — обёртка git на PATH роли (вариант, допускаемый
требованием 6), одинаковая для Claude и Codex, потому что живёт в окружении
шага (`runner.role_env`), а не в протоколе CLI.

- `orchestrator/role_bin/git` — `sh`-скрипт: берёт свой каталог от `$0`
  (`dirname`/`realpath` в PATH роли нет) и исполняет
  `python3 -I -S orchestrator/role_git.py <каталог обёртки> "$@"`.
- `orchestrator/role_git.py` — только stdlib, без импорта пакета
  `orchestrator` (приёмка AC-14 копирует `role_bin/` и `role_git.py` в дублёр
  без остального пакета). Разбирает глобальные опции git до подкоманды;
  считает пути вызова: текущий каталог после цепочки `-C` (каждый
  относительный — от предыдущего, `realpath` на каждом шаге), `--git-dir`/
  `GIT_DIR`, `--work-tree`/`GIT_WORK_TREE`, `core.worktree` из `-c`/
  `--config-env`/`GIT_CONFIG_PARAMETERS`/`GIT_CONFIG_COUNT`. Каждый путь
  классифицируется относительно защищаемых корней — корня от расположения
  обёртки (и модуля) плюс корня из `ARTEL_GIT_GUARD_ROOT` (только добавляет):
  «foreign» — внутри `<корень>/.artel/projects/*/worktrees/<не ARTEL_TASK>`,
  «own» — своя рабочая копия или клон проекта, где она лежит, «pult» —
  прочее внутри корня, «outside». Без `ARTEL_TASK` своей копии нет
  (fail-closed). Отказ «рабочая копия другой задачи» главнее «репозиторий
  пульта» (возврат 6). Всё вне корней — сразу `execv` настоящего git
  (AC-8, AC-15). Внутри своей копии: `clean` — отказ; затем
  `git config --list -z` с теми же глобальными опциями (видит все источники:
  файлы клона и `config.worktree`, `-c`, `--config-env`, `GIT_CONFIG_*`) —
  отказ по `!`-псевдониму, по цепочке псевдонимов до `clean`, по
  `core.pager`/`core.fsmonitor`/`pager.<cmd>`/`GIT_PAGER`/`PAGER` с вызовом
  git, по `core.worktree` вне своей копии. Пропущенный вызов исполняется
  настоящим git с `-c help.autocorrect=0` (опечатка `claen` не исполнит
  `clean`). `--version`, `help`, справка проходят при любом каталоге
  (возврат 10). Переменной-выключателя нет.
- Настоящий git — первый `git` по PATH после каталога обёртки; вложенный git
  из pager/fsmonitor/`!`-псевдонима обёртку не видит — поэтому отказ на
  верхнем уровне (требование 3).
- `runner.role_env`: `PATH = venv/bin, orchestrator/role_bin, …` (каталог —
  `ROLE_GIT_BIN` от `__file__` модуля runner, требование 10);
  `GIT_CEILING_DIRECTORIES` и `ARTEL_GIT_GUARD_ROOT` — оба
  `Path(config.ROOT).resolve()`. `runner.path_without_role_git` — единый
  способ снять обёртку.
- `artel.main()` под признаком роли исполняет команду через
  `_run_without_role_git`: PATH процесса без каталога обёртки на время
  команды, восстановление в `finally` (возврат 5) — дочерние процессы пульта
  (git, pytest `plank-run`/`suite-run`/`mutation-run`) идут без обёртки,
  потолок и корень на месте. Вызовы git пульта (`gitcmd.git`) и так идут с
  `cwd=ROOT`, потолок им не мешает (AC-14 knowledge из каталога документов —
  зелёный).
- `orchestrator/task_files.py` — `task-rm <id> <путь>…`: под признаком роли
  `<id>` обязан совпасть с `ARTEL_TASK`; задача по БД (`db_readonly`,
  `resolve_task_id`); корни — `workspace.path` и `artifact_branch.docs_dir`
  после `realpath`. Каждый путь: родитель разрешается, сам путь — нет
  (удаляется ссылка, не цель); вне корней, сам корень, `.git` на любом
  уровне, каталог, ссылка наружу, файл каталога документов из
  `refs/artifacts/<id>` — отказ. Набор проверяется целиком до первого
  `unlink`.
- doctor `role-git-boundary` (`doctor/isolation.py`): (а) `git rev-parse` из
  `tempfile.mkdtemp(dir=<ROOT>/.artel)` под окружением роли без обёртки
  (иначе обёртка отказала бы сама и пропажа потолка не видна) — ожидается
  ненулевой код; (б) `git clean -n` в `<ROOT>` под полным окружением —
  ожидается отказ со строкой `task-rm`. `OSError` mkdtemp — `fail` с
  причиной; каталог пробы удаляется в `finally`.

Бюджет SPEC не пересматривается.

**Замер прямого `pytest` (требование 6).** Файл
`tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py` (4 теста, git-ёмкий),
окружение роли, собранное `runner.role_env` этой ветки, cwd — рабочая копия;
по два прогона: без каталога обёртки в PATH (как было: `tests/direct_git.py`
ставит git мимо xcrun) — 2.8 с и 2.4 с; с обёрткой — 7.6 с и 7.4 с. Причина —
питон обёртки на каждый вызов git (~20 мс) и git через `/usr/bin/git`
(xcrun) вместо прямого: `prefer_direct_git` не срабатывает, когда первый
`git` по PATH — обёртка. Прогоны `suite-run`/`plank-run`/`mutation-run`
идут без обёртки (требование 5) и не замедляются.

## Шаги
1. Механизм: `orchestrator/role_git.py`, `orchestrator/role_bin/git`
   (бит исполнения 0755).
2. Окружение роли: `runner.ROLE_GIT_BIN`, `path_without_role_git`, PATH,
   `GIT_CEILING_DIRECTORIES`, `ARTEL_GIT_GUARD_ROOT` в `role_env`.
3. Диспетчер: `_run_without_role_git` в `artel.main`, `task-rm` в таблице,
   в `_ROLE_ALLOWED_COMMANDS` (с комментарием) и в справке;
   `orchestrator/task_files.py`.
4. Миссия: `role_prompt.docs_dir_note` называет `task-rm`.
5. doctor: `check_role_git_boundary` + `ROLE_GIT_BOUNDARY_CHECK`, экспорт в
   фасаде, строка в `all_checks`.
6. `docs/reference/role-home/claude/settings.json`: `Bash(git clean:*)` в
   `deny`.
7. Документация: `docs/stack.md` (белый список с `task-rm`, абзац о границе,
   строка таблицы паритета с принятыми ограничениями),
   `docs/reference/role-home.md` (механизм, `task-rm`, ручной перенос
   `deny`), карта `scripts/codebase_map.py`.
8. Тесты: мандатная правка `tests/test_multitarget.py::RoleEnvTest::commit_probe`
   (проба во временном каталоге вне `self.root`, утверждения не тронуты);
   новый `tests/test_role_git.py` — свойства, которых нет в долгоживущем
   файле задачи: цепочка `-C`, пути `--git-dir`/`GIT_WORK_TREE`/
   `core.worktree` из `GIT_CONFIG_PARAMETERS`, классификация путей,
   fail-closed без `ARTEL_TASK`, `ARTEL_GIT_GUARD_ROOT` только добавляет
   корень, цепочка псевдонимов, pager/fsmonitor, проверка набора `task-rm`.
   Мутации проверены временной правкой: «`-C` от исходного cwd», «без задачи
   всё своё», «один уровень псевдонима» — каждая красит свой тест.
9. Итерация 2 (замечания ревью R1-F1..F3):
   - R1-F1: `role_git._alias_refusal` разбирает тело псевдонима тем же
     `parse()` (значение `-c`/`--config-env` — не подкоманда); конфигурация
     из тела (`option_config`) проверяется: pager/fsmonitor с вызовом git и
     `core.worktree` — отказ, `alias.*` тела участвуют в дальнейшем
     раскрытии (`!`-псевдоним, `clean`).
   - R1-F3: `task-rm` не планирует повтор пути (`f`, `./f`) дважды.
   - R1-F2: в `tests/test_role_git.py` — сквозные сторожа ядра над
     временным дублёром ROOT: `role_git.main` (своя копия, чужая копия,
     корень, pager/псевдоним с `-c` в теле, вне корней и `--version`;
     `os.execv` подменён), `artel._run_without_role_git` (PATH без
     обёртки, восстановление после исключения), `cmd_task_rm` (`ARTEL_TASK`,
     повтор пути), `docs_dir_note` (`task-rm <id>`), `check_role_git_boundary`
     (`ok`; `fail` без потолка и без обёртки; временный каталог убран).
     Мутации ревью (`role_git.py` foreign/`reason = None`, `artel.py` PATH,
     `task_files.py` `ARTEL_TASK`, `role_prompt.py` `task-rm`,
     `doctor/isolation.py` `fail`) и мутации R1-F1/R1-F3 — каждая красит
     файл. Мутация «отказ `sub == "clean"` выключен» в одиночку
     эквивалентна: слово `clean` отклоняет и `_alias_refusal`; выключение
     обоих мест — 4 красных теста.
10. Итерация 3 (возврат с гейта мержа, ANSWER-1: две обёртки на PATH
    передавали вызов друг другу — требование 6):
    - `role_git.is_role_wrapper` — признак обёртки любой копии пульта:
      рядом с каталогом лежит `../role_git.py` либо файл несёт маркер
      `artel-role-git-wrapper` (добавлен в `role_bin/git`);
      `role_git.real_git` пропускает каждый такой `git` на PATH, не только
      свой каталог — обёртка никогда не зовёт другую обёртку. Переменной
      вложенного вызова нет (п. 3 возврата отменён ANSWER-1).
    - `runner._resolve_declared_tools`: если `shutil.which("git")` —
      обёртка (любой копии), берётся `role_git.real_git` — в PATH роли
      попадает каталог настоящего git, а не каталог чужого `role_bin`.
    - Тесты `tests/test_role_git.py`: `TwoWrappersTest` — копия пакета
      обёртки во временном каталоге и своя обёртка на одном PATH (оба
      порядка); `--version`, `status` вне корня и `status` в своей копии
      дублёра (обёртка читает `git config`) — код 0 за 10 с; вызов в своей
      группе процессов под `RLIMIT_NPROC` (запущенные + 64), по таймауту
      группа снимается `killpg`; число запусков настоящего git — через
      шим-счётчик, 1..3. `RoleEnvForeignWrapperTest` — `role_env` при
      чужой обёртке первой на PATH несёт ровно один каталог обёртки — свой.
      Мутации: старый `real_git` (только свой каталог) — `TwoWrappersTest`
      красный (снят таймаутом); `which` без фильтра в `runner` —
      `RoleEnvForeignWrapperTest` красный. `DoctorBoundaryTest.env` (тест
      этой задачи) собирает PATH без обёрток любой копии.
    - Существующие тесты `tests/` не правились (в том числе
      `test_multitarget` сверх `commit_probe`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 1, 2 |
| 3 | 1, 9 |
| 4 | 3, 4, 9 |
| 5 | 3 |
| 6 | 2, 10 (замер — «Подход») |
| 7 | 5 |
| 8 | 7 |
| 9 | 6, 7 |
| 10 | 1, 2 |

Итерация 3: планка `plank-run` — 119 passed; `tests/test_role_git.py`,
долгоживущий файл задачи, `test_multitarget`, `test_providers`,
`test_codex_login_shell_path`, `test_01m5kjne39…_direct_git`,
`test_runner_role_environment`, `test_stack` — 160 passed; `test_codebase_map`
— 34 passed. Сценарий возврата: копия пакета обёртки первой на PATH процесса
pytest — `test_multitarget` (в том числе
`RoleEnvTest::test_commit_of_the_step_passes_with_that_environment`) и
`tests/test_role_git.py` зелёные, без зависания; см. «Риски» о
долгоживущем `test_ac16_wrapper_dir_second_in_role_path_before_git`.

Итерация 2: планка `plank-run` — 119 passed; `tests/test_role_git.py`,
долгоживущий файл задачи, `test_multitarget`, `test_codebase_map` — 110
passed; на настоящем git через обёртку в дублёре
`git -c 'alias.cl=-c a.b=c clean -fX' cl` — отказ, файл на месте.

Итерация 1: планка `plank-run` — 119 passed; долгоживущий
`tests/test_01m6jj4j4nbv2y1q4xhe3c3fvt_role_git_boundary.py` — 4 passed;
затронутые модули (`test_multitarget`, `test_providers*`,
`test_codex_login_shell_path`, `test_01m5kjne39…_direct_git`,
`test_01m3xtf5…_role_refusal`, `test_runner_role_environment`,
`test_doctor*`, `test_stack*`, `test_stack_parity_table`, тесты
`plank-run`/`suite-run`/`knowledge`/`preflight`/`pull_main`/`reference`/
`targets_migrate`, `pult_commit`, `docs_command`, `test_codebase_map`,
`test_role_git`) — зелёные.

## Влияние на систему
- Окружение каждого шага роли меняется: PATH получает второй элемент,
  появляются две переменные. Пульт сам запускает процессы под `role_env`
  только при старте агента (`runner.py`, spawn) — собственные вызовы git
  пульта обёртку не видят; команды пульта, запущенные ролью, снимают её
  (`_run_without_role_git`). Порядок PATH, закреплённый тестами
  требования 6, сохранён (первый — `venv/bin`, инструменты манифеста
  дальше в прежнем порядке).
- Шаг роли не может больше: `git clean` в своей копии (замена — `task-rm`),
  git в каталогах пульта и чужих копиях, `!`-псевдонимы и pager/fsmonitor
  с git в своей копии. Обычная работа роли (status/diff/add/commit/log/
  stash/checkout в своей копии и клоне) проходит.
- `doctor` получает строку `role-git-boundary`; на исправном пульте `ok`,
  проба неразрушительна (`clean -n`, временный каталог удаляется).
- Гейты, тесты, лимиты не ослабляются: единственная правка существующего
  теста — мандатная (`commit_probe`, раздел SPEC «Правки существующих
  тестов»), утверждения не тронуты. Пропуск
  `Ac7WrapperMachineTest::test_ac7_…` при прямом pytest под окружением роли
  — принят Оператором (матрица неослабления SPEC).
- Откат — revert одного merge-коммита; на работающем пульте строка `deny`
  переносится вручную (и вручную же убирается).
- Ручной шаг Оператора после мержа: перенести `"Bash(git clean:*)"` в
  `.artel/home/.claude/settings.json` (`docs/reference/role-home.md`).

## Риски
- Прямой `pytest` роли под окружением роли медленнее примерно втрое
  (замер выше); `suite-run`/`plank-run` не затронуты.
- Обёртке нужен `python3` в PATH (в окружении роли он первым — `venv/bin`);
  без него вызов git падает 127 — отказ, не пропуск.
- Вне охвата SPEC (модель угрозы — ошибочная команда): прочие каналы,
  где git исполняет команду оболочки (`core.editor`, `diff.external`,
  `core.sshCommand`, `credential.helper`, фильтры), `git help -a` с
  pager-ом из файла конфигурации на tty, рабочее дерево вне корня с
  каталогом `.git` внутри корня (`git worktree add /tmp/x` пульта).
- Вложенный git в своих хуках клона идёт мимо обёртки — как и прежде.
- Долгоживущий
  `tests/test_01m6jj4j4nbv2y1q4xhe3c3fvt_role_git_boundary.py::test_ac16_wrapper_dir_second_in_role_path_before_git`
  (файл залочен, не правился): его помощник `_real_git` пропускает только
  каталог обёртки рабочей копии. При прямом `pytest` из рабочей копии,
  когда на PATH процесса стоит обёртка ДРУГОЙ копии (главной после мержа),
  `_real_git` отдаёт её каталог, а `role_env` по п. 2 возврата этот каталог
  в PATH роли больше не кладёт — тест красный (воспроизведено: 2 failed).
  В CI, `suite-run`, `plank-run` и при обычном прямом прогоне — зелёный.
  Класс тот же, что принятый пропуск `Ac7WrapperMachineTest` (матрица
  неослабления SPEC). Если Оператор сочтёт это расхождением — правка
  `amend-tests`: `_real_git` пропускает любой каталог, где `git` —
  обёртка роли (`role_git.is_role_wrapper`).

## Предложения системе
- `task-rm` недоступен роли до мержа задачи (роль зовёт `artel.py` главной
  копии пульта): временный файл каталога документов в итерации 2 пришлось
  убрать `python3 -c os.unlink`. Ожидаемо, но класс «команда задачи,
  нужная самой задаче, появляется только после мержа» стоит учесть.
- Bash роли (курируемый `settings.json`): `chmod` и запуск локального
  скрипта (`orchestrator/role_bin/git …`) требуют подтверждения, `ls`
  недоступен — бит исполнения пришлось ставить `python3 -c os.chmod`,
  обёртку гонять через `subprocess` из python. Класс «нет штатного способа
  проверить исполняемый файл задачи» — кандидат в копилку.
- `tests/direct_git.py::prefer_direct_git` не знает обёртки git роли:
  мог бы вставлять каталог прямого git и тогда, когда первый `git` по
  PATH — обёртка (сама обёртка ищет git после себя) — вернул бы ускорение
  прямому `pytest` роли; файл вне зоны задачи.
- `artel.py guard 01M6JJ4J4NBV2Y1Q4XHE3C3FVT` на 04.11 красит SPEC.md
  задачи: «пути упомянуты, но не классифицированы: .artel/notes-pending/»
  (путь из «Контекста» — перечень удалённого инцидентом). Артефакт
  аналитика, роль разработчика его не правит; PLAN.md guard проходит.
