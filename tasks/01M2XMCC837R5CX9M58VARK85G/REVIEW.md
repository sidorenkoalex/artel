---
task: 01M2XMCC837R5CX9M58VARK85G
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Защита main главной копии: git-хуки от ручных коммитов и push в main, маркер команд пульта, включение через doctor --fix

Пакет ревью не показал SPEC.md/PLAN.md («не существует в ветке» — они и
не должны быть в кодовой ветке); оба прочитаны с диска рабочего каталога
(`tasks/01M2XMCC837R5CX9M58VARK85G/SPEC.md`, `PLAN.md`, материализация
из артефактной ветки), TZ.md — для сверки границ «Только чтение».

## Фаза A: гейт плана

1. **Покрытие SPEC полно.** Таблица «Покрытие требований» PLAN закрывает
   требования 1–10 шагами 1–5; AC-1..AC-13 — планкой из 9 файлов.
   Сверено с диффом: каждое требование адресовано реальным файлом (см.
   таблицу ниже).
2. **Шаги — единицы размера MR**, не микрооперации: хуки / маркер /
   doctor / документ / тесты. Обоснование монолита (SPEC «Оценка объёма»)
   верно: хуки без маркера ломают `_push_merged_main` на первом
   `approve`, маркер без хуков — переменная без потребителя.
3. **Подход не конфликтует с архитектурой**: новый подмодуль doctor по
   конвенции пакета (коллаборанты через фасад `doctor.gitcmd`/
   `doctor.config`), маркер — в единственной точке `subprocess.run`
   каждой из четырёх точек входа; `in_repo` и `repo_context.git`
   получают его делегированием (`orchestrator/gitcmd.py:206`,
   `orchestrator/repo_context.py:64-66` — прочитаны, чтобы подтвердить
   заявление PLAN «без правки»; подтверждено).
4. **Отход от буквы AC-10** (`skip` вместо `fail`, когда `config.ROOT`
   — не репозиторий) PLAN называет явно и обосновывает требованием
   9/AC-13 (`tests/test_doctor.py`, песочница без `git init`, ждёт
   `DOCTOR: ок`). Принимаю: для главной копии третьего исхода нет,
   `skip` честнее `ok`, статус в выводе виден.
5. **«Влияние на систему» = дифф**: затронуто ровно заявленное
   (`docs/codebase-map.md`, `docs/operator-session.md`,
   `orchestrator/doctor/{__init__,cli,git_hooks}.py`,
   `orchestrator/gitcmd.py`, `scripts/git-hooks/*`,
   `tests/test_git_hooks.py`); `repo_context.py`, `runner.py`,
   `stack.py`, пути «Только чтение» ТЗ и защищённые пути не тронуты.
   Откат описан (revert + `git config --unset core.hooksPath`).

Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (хуки POSIX sh, только git) | OK | `scripts/git-hooks/pre-commit:15-28`, `pre-push:15-32`: `#!/bin/sh`, `[`, `read -r`, `printf`, `git symbolic-ref`. `sh -n` обоих — 0 (планка AC-1). Режим в индексе 100755 (`git ls-files -s`). |
| 2 (именованный текст отказа) | OK | Текст дословно по SPEC с ведущим «коммит»/«push»; сверен тестами `REFUSAL_CORE` и планкой AC-2/AC-5 на настоящем git. |
| 3 (`task/*`, `artifact/*`, `refs/artifacts/*` не трогаются) | OK | `pre-commit` — точное `= "main"`, `pre-push` — точное `refs/heads/main` целевого ref; тесты на все три класса refs и на «main второй парой в одном push». |
| 4 (`doctor --fix`: `core.hooksPath` + бит исполнения) | OK | `orchestrator/doctor/git_hooks.py:84-119` — репозиторный `git config` (не `--global`), `chmod \| 0o111`; подключено в `cli.py:133` ДО `all_checks` (`cli.py:139`) — проверка того же прогона видит результат (AC-11). |
| 5 (проверка «git-hooks») | OK | `git_hooks.py:47-81`: `ok` при точном `HOOKS_PATH` и исполняемых файлах, `fail` с «doctor --fix» при чужом/незаданном пути, отсутствии файла, отсутствии бита. `skip` вне репозитория — отход от буквы, обоснован PLAN (см. Фазу A, п.4). В `all_checks` — `cli.py:53`. |
| 6 (маркер у четырёх точек входа) | OK | `gitcmd.py:43` (`git`), `:191` (`carpentry`), `in_repo` → `git` (`:206`), `repo_context.git` → `gitcmd.git`/`in_repo` (`repo_context.py:64-66`). Настоящий дочерний git через `!`-алиас видит `MARK=1` (тест `test_repo_context_git_reaches_a_real_child_with_the_marker`). |
| 7 (прочие переменные не меняются; поверх env `carpentry`) | OK | `pult_env` — копия `os.environ`/`base` + одна переменная (`gitcmd.py:22-29`); тест сверяет словарь целиком в обе стороны; `os.environ` пульта не трогается (тест на утечку). |
| 8 (`role_env` без маркера) | OK | Код не менялся; `stack.ROLE_ENV_ALLOWLIST` отсекает переменную — тест на обе стороны (маркер выставлен у пульта → в env роли его нет). |
| 9 (песочницы не наследуют конфиг) | OK | Репозиторный конфиг; `tests/sandbox.py` HOME не подменяет, но `core.hooksPath` в глобальном слое машины Оператора пуст (`git config --global --get core.hooksPath` → пусто, код 1). 407 тестов затронутых модулей зелёные, CI ветки зелёный. |
| 10 (абзац документации) | OK | `docs/operator-session.md:122-144`: перечень четырёх команд, маркер обхода, границы (`task/*`, `artifact/*`, `refs/artifacts/*`), роль без маркера. |
| AC-1..AC-13 | OK | Планка 13 тестов зелёная (см. «Проверено исполнением»); пометок `manual`/`skip` нет. |

## Замечания

Все четыре — minor; ни одно не требует правки в рамках этой задачи,
закрыты на месте как наблюдения (реестр — `accepted`, чтобы гейт
`review -> verifying` принял `approved`).

- minor — `scripts/git-hooks/pre-commit:19` — хук `pre-commit` git зовёт
  только из `git commit`; коммит на main, созданный `git merge --no-ff`,
  `git pull` (не-ff), `git cherry-pick`, `git rebase`, `git revert`,
  проходит без отказа (проверено зондом: `merge --no-ff` и `cherry-pick`
  на main без маркера — код 0, коммит создан; `commit --amend` — отказ).
  Последствие: сценарий инцидента 19.09 в варианте «запрещённый pull»
  всё ещё оставляет локальный merge-коммит на main — отказывает только
  `pre-push` при попытке его опубликовать, а HEAD главной копии уже
  разъехался с origin (ловит постфактумный `check_pin_unpushed`). SPEC
  требует ровно `pre-commit`/`pre-push` — соответствие не нарушено;
  предложение на будущее: третий файл `pre-merge-commit` (тот же текст
  хука; git зовёт его из `merge`/`pull`) — отдельной строкой копилки.
- minor — `orchestrator/doctor/git_hooks.py:18` (`HOOKS_PATH`
  относительный) — в linked worktree относительный `core.hooksPath`
  разрешается от корня ЭТОГО worktree (проверено зондом: подменённый в
  worktree `pre-commit` исполнился при коммите из worktree с
  `marker=1`). То есть git-команды пульта в рабочей копии роли —
  `checkpoint.py:1039` (`in_repo(wt, "commit")`), `github_adapter.py:88,
  158` (`in_repo(repo, "push")`) — исполняют хук из ВЕТКИ РОЛИ с полным
  окружением пульта (включая маркер). Не новый класс: пульт уже
  исполняет код роли в своём окружении без фильтра —
  `orchestrator/acceptance.py:101` гоняет приёмочные тесты роли без
  `env=`, а сам маркер — обычная переменная, которую любой процесс
  выставит себе (SPEC честно называет хук «второй линией» к
  `permissions.deny`). Предложение вне этой задачи (требование 4 SPEC
  задаёт относительное значение дословно): абсолютный `core.hooksPath`
  = `config.ROOT/scripts/git-hooks` (зонд: при нём коммит из worktree
  исполняет хуки главной копии, а отказ на main сохраняется) и/или
  `scripts/git-hooks/` в защищённые пути — решение Оператора, см.
  «Предложения системе».
- minor — `tests/test_git_hooks.py:490`
  (`test_fix_is_repository_local_not_global`) — тест читает НАСТОЯЩИЙ
  глобальный git-конфиг машины (`git config --global --get
  core.hooksPath`; `RealGitSandbox` в `tests/sandbox.py` HOME /
  `GIT_CONFIG_GLOBAL` не подменяет — прочитал файл, чтобы это
  подтвердить: подмен HOME там нет). На машине с глобальным
  `core.hooksPath` (husky-подобные инструменты) тест красный без дефекта
  кода. Сегодня у Оператора значение пусто, на GitHub-раннере тоже —
  зелёно. Предложение: в тесте выставить `GIT_CONFIG_GLOBAL` на
  временный файл через `mock.patch.dict(os.environ, …)` — тогда
  «глобальный слой пуст, если `--fix` туда не писал» сверяется
  герметично.
- minor — `orchestrator/doctor/git_hooks.py:23-28` (`_inside_work_tree`)
  — `git rev-parse --is-inside-work-tree` отвечает `true` и для
  `config.ROOT`, ВЛОЖЕННОГО в чужой репозиторий (не сам репозиторий);
  тогда `_fix_git_hooks` пишет `core.hooksPath` в конфиг ОБЪЕМЛЮЩЕГО
  репозитория, а `check_git_hooks` сверяет его же. Экспозиция сегодня
  нулевая: `TmpRootTest` кладёт ROOT в системный temp
  (`tests/sandbox.py:683`), главная копия — сама репозиторий.
  Предложение: сверять `git rev-parse --show-toplevel` с `config.ROOT`
  (тот же один вызов git).

Проверено и замечаний не дало:
- Прямых `subprocess.run(["git", …])` мимо `gitcmd` в `orchestrator/`
  нет; единственный вне — `scripts/ci_push_class.py:60,64` (`cat-file`,
  `diff` — хуков не зовут).
- `gitcmd.check_ignore` без маркера — намеренно (PLAN), `git
  check-ignore` хуков не запускает.
- `note` работает в отдельном `git init` репозитории
  (`orchestrator/notes.py:279`, `.artel/notes-work`) — конфиг главной
  копии туда не доходит, коммит/push там идут через `in_repo` с
  маркером; `pin-update` — `merge --ff-only`, коммита не создаёт;
  `_push_merged_main` — `repo_context.git` в `config.ROOT` с маркером
  (тест `test_push_to_main_with_marker_passes` — тот же refspec
  `<sha>:refs/heads/main`).
- `pre-push` с `<sha>:refs/heads/main` сверяет удалённую сторону пары
  (`pre-push:23`) — тест на голый sha слева и на main второй парой.
- Тесты: каждый из 28 новых несёт заявку «Ловит мутацию: …» с
  правдоподобной мутацией, сверенной с телом теста (например,
  `test_marker_with_another_value_does_not_bypass` действительно ловит
  `-n` вместо `= "1"`; `test_push_to_refs_heads_main_is_refused_without_marker`
  — чтение локального ref вместо целевого). Существующие тесты не
  изменены (дифф `tests/` — только новый файл).
- Целостность (ADR-0002): гейты/лимиты/guard не ослаблены;
  `check_pin_unpushed` остаётся; защищённые пути не тронуты;
  `docs/codebase-map.md` регенерирован — после `python3
  scripts/codebase_map.py` расхождение только в `built_at_sha`.
- Безопасность: секретов нет; в вывод отказа хука ничего из окружения
  не подставляется; `_fix_git_hooks` не пишет вне репозитория (тест
  `test_fix_outside_a_repository_writes_nothing`).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | scripts/git-hooks/pre-commit:19 | `pre-commit` не зовётся из `merge`/`pull`/`cherry-pick`/`rebase`/`revert` — коммит на main этими командами создаётся без отказа | Локальный merge-коммит на main (вариант инцидента «запрещённый pull») остаётся; блокируется только его push, разъезд с origin ловит постфактумный `check_pin_unpushed` | minor, в рамках SPEC (требует ровно `pre-commit`/`pre-push`) — правки не требует; предложение `pre-merge-commit` — строкой копилки. Закрыто на месте как наблюдение |
| R1-F2 | accepted | orchestrator/doctor/git_hooks.py:18 | Относительный `core.hooksPath` в worktree роли разрешается в `scripts/git-hooks/` ветки роли — git пульта в worktree (`checkpoint.py:1039`, `github_adapter.py:88,158`) исполняет хук из ветки роли с окружением пульта | Роль может подменить хук в своей ветке; класс не новый — `acceptance.py:101` уже исполняет тесты роли в окружении пульта, маркер — обычная переменная (SPEC: «вторая линия») | minor, вне этой задачи: SPEC требование 4 задаёт относительное значение дословно; абсолютный путь / защищённый путь — решение Оператора (см. «Предложения системе»). Закрыто на месте как наблюдение |
| R1-F3 | accepted | tests/test_git_hooks.py:490 | Тест читает настоящий глобальный git-конфиг машины (`RealGitSandbox` HOME/`GIT_CONFIG_GLOBAL` не подменяет) | Красный тест без дефекта кода на машине с глобальным `core.hooksPath`; сегодня у Оператора и на раннере значение пусто — зелёно | minor, вкус: `GIT_CONFIG_GLOBAL` на временный файл в тесте. Закрыто на месте как наблюдение |
| R1-F4 | accepted | orchestrator/doctor/git_hooks.py:23-28 | `--is-inside-work-tree` истинно для ROOT, вложенного в чужой репозиторий, — `--fix` писал бы `core.hooksPath` объемлющему репозиторию | Экспозиция нулевая: песочницы в системном temp, главная копия — сама репозиторий | minor, вкус: `--show-toplevel` == `config.ROOT`. Закрыто на месте как наблюдение |

## Вердикт

approved. 0 blocker, 0 major; четыре minor закрыты на месте как
наблюдения (реестр — `accepted`), правки кода не требуют. Реализация
соответствует всем десяти требованиям SPEC и AC-1..AC-13; отход `skip`
вместо `fail` вне репозитория обоснован PLAN и принят.

## Проверено исполнением

Рабочий каталог `.artel/worktrees/01M2XMCC837R5CX9M58VARK85G`, HEAD
`1a4f6d4d` (единственный коммит задачи поверх `9c59fc82`).

- `python3 -m unittest tests.test_git_hooks -v` — 28 тестов, OK (6.97 с).
- `python3 -m unittest discover -s
  tasks/01M2XMCC837R5CX9M58VARK85G/acceptance_tests -p 'test_*.py' -v`
  (из корня рабочего каталога) — 13 тестов, OK (3.66 с); пометок
  `# AC-n: manual|skip` в планке нет (grep).
- Тесты затронутых модулей: `python3 -m unittest
  tests.test_gitcmd_branch_reads tests.test_gitcmd_carpentry
  tests.test_gitcmd_check_ignore tests.test_gitcmd_fetch_ref_sha
  tests.test_doctor tests.test_runner_role_model tests.test_repo_context
  tests.test_multitarget tests.test_git_fixation
  tests.test_artifact_branch_push tests.test_artifact_branch_new_parent
  tests.test_step_autocommit tests.test_checkpoint_zone_filter
  tests.test_checkpoint_external_step_artifacts
  tests.test_doctor_fix_ignored_artifacts
  tests.test_doctor_artifact_branch_sync tests.test_doctor_artifact_branch_ci
  tests.test_timeout_checkpoint
  tests.test_fsm_merge_gate_scratch_worktree_cleanup
  tests.test_protected_paths_gate` — 407 тестов, OK (228.8 с). Полный
  набор не гонял (решение Оператора 05.09) — CI коммита 1a4f6d4d зелёный
  (7 проверок, из пакета).
- `python3 scripts/codebase_map.py` и `git diff -- docs/codebase-map.md`
  — расхождение только строка `built_at_sha`; вернул файл `git checkout`.
- `git ls-files -s scripts/git-hooks` — оба файла `100755`.
- `git config --global --get core.hooksPath` — пусто, код 1 (машина
  Оператора без глобального `hooksPath`; контекст R1-F3).
- `grep -rn 'subprocess.run(["git"' orchestrator scripts` — вне
  `gitcmd.py` только `scripts/ci_push_class.py:60,64`.
- Одноразовый зонд (python + настоящий git во временном репозитории с
  копией хуков задачи, `GIT_CONFIG_GLOBAL=/dev/null`, файл зонда удалён):
  (1) linked worktree с подменённым `pre-commit` — при коммите из
  worktree исполнился хук worktree, вывод `ROLE-HOOK RAN … marker=1`
  (R1-F2); (2) `git merge --no-ff` на main без маркера — код 0, коммит
  создан; (3) `git cherry-pick` на main без маркера — код 0, коммит
  создан (R1-F1); (4) `git commit --amend` на main без маркера — код 1,
  именованный отказ; (5) `git pull --ff-only` без маркера — код 0
  (коммита нет, отказ и не нужен); (6) worktree без каталога
  `scripts/git-hooks` — коммит проходит молча (ожидаемо, PLAN);
  (7) абсолютный `core.hooksPath` — коммит из worktree берёт хуки
  главной копии (подменённый хук не исполнился), отказ на main
  сохраняется (контекст R1-F2).

## Предложения системе

- `scripts/git-hooks/` — код, который git пульта исполняет с полным
  окружением пульта в любой рабочей копии, включая worktree роли
  (R1-F2). Кандидат в защищённые пути (`gates.yaml`, решение Оператора)
  либо переход на абсолютный `core.hooksPath` = `config.ROOT/scripts/
  git-hooks` следующей задачей — тогда worktree роли исполняет только
  хуки главной копии, а роль без каталога хуков в старом worktree всё
  равно защищена.
- Класс «тест читает настоящий глобальный конфиг/HOME машины»
  (`tests/sandbox.py`: `RealGitSandbox` не подменяет HOME /
  `GIT_CONFIG_GLOBAL`) — R1-F3 здесь; стоит одной строкой в
  `skills/test-authoring.md` или подменой в самой песочнице, иначе
  каждый новый тест с `git config --global` будет зависеть от машины.
- Согласен с PLAN: три проверки doctor (`check_root_pin`,
  `check_pin_unpushed`, `check_git_hooks`) деградируют по-разному, когда
  ROOT — не репозиторий (`ok`/`warn`/`skip`); общего правила нет.
