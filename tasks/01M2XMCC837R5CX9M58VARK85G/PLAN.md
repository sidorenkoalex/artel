---
task: 01M2XMCC837R5CX9M58VARK85G
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Защита main главной копии: git-хуки от ручных коммитов и push в main, маркер команд пульта, включение через doctor --fix

## Подход

Правило «HEAD главной копии двигают только команды пульта» становится
программным в два слоя, включаемых одним коммитом (SPEC, «Решение:
монолит»):

1. **Хуки** `scripts/git-hooks/pre-commit` и `pre-push` — POSIX sh, только
   `git` и встроенные команды оболочки (`[`, `read`, `printf`, `case`
   не нужен). `pre-commit`: ветка под HEAD через `git symbolic-ref
   --quiet --short HEAD`; отказ, если она `main` и в окружении нет
   `ARTEL_PULT_GIT=1` (проверяется значение, не факт наличия —
   `ARTEL_PULT_GIT=0` из чужого окружения защиту не снимает).
   Отсоединённый HEAD хук пропускает: main им не двигается. `pre-push`:
   цикл `while read` по парам refs со stdin, сверяется ЦЕЛЕВОЙ
   (удалённый) ref `refs/heads/main` — при push `<sha>:refs/heads/main`
   локальная сторона имени main не несёт вовсе. Текст отказа обоих —
   общая дословная часть требования 2 с ведущим «коммит»/«push».
2. **Маркер** — `gitcmd.pult_env(base=None)`: копия `os.environ` (или
   переданного `base`) плюс `ARTEL_PULT_GIT=1` поверх. `gitcmd.git`
   отдаёт дочернему git `env=pult_env()`, `carpentry` — `pult_env(env)`
   поверх переданного плотницкого окружения; `in_repo` и
   `repo_context.git` делегируют в `git()`/`in_repo()` и получают маркер
   без правки. `os.environ` самого пульта не трогается — иначе маркер
   унаследовала бы оболочка сессии и защита стала бы бумажной.
   `runner.role_env` не меняется: белый список `stack.ROLE_ENV_ALLOWLIST`
   уже отсекает переменную (сверено тестом на обе стороны — переменная
   есть/нет у пульта).
3. **doctor** — новый подмодуль `orchestrator/doctor/git_hooks.py` по
   конвенции пакета (коллаборанты через фасад `doctor.gitcmd`/
   `doctor.config`, без прямых импортов): `check_git_hooks()` — `ok` при
   `core.hooksPath = scripts/git-hooks` и исполняемых файлах обоих хуков,
   `fail` с подсказкой `doctor --fix` при незаданном/чужом пути,
   отсутствующем файле или файле без бита исполнения; `_fix_git_hooks()`
   — `git config core.hooksPath scripts/git-hooks` (репозиторный конфиг,
   не `--global`/`init.templateDir` — требование 9) и `chmod | 0o111`
   файлам хуков. Проверка подключена в `all_checks` после
   `check_pin_unpushed` (постфактумный сторож рядом с превентивным),
   починка — в ветке `if fix:` `cmd_doctor` ДО `all_checks`, чтобы
   проверка в том же прогоне видела результат (AC-11).

   Деградация: `config.ROOT` — не git-репозиторий (`git rev-parse
   --is-inside-work-tree` не ответил `true`) — `skip`, не `fail`. Это
   единственный случай, где SPEC («fail иначе») сталкивается с
   требованием 9/AC-13: песочница `tests/test_doctor.py::
   DoctorCommandTest` («здоровый репо», без `git init`) прогоняет полный
   `all_checks` и ждёт `DOCTOR: ок`; `fail` красил бы её без единого
   хука. Главная копия всегда git-репозиторий — для неё третьего исхода
   нет; `skip` — честный пропуск (статус фасада, «сверка не проведена»),
   не `ok`, как у `check_root_pin` при недоступном origin.

Относительный `core.hooksPath`: git считает его от корня рабочего дерева,
где хук запускается, — worktree задачи после подтяжки этой ветки берёт
хуки из своего дерева (роль коммитит на `task/*` — проходит), worktree
без каталога `scripts/git-hooks` хуков просто не имеет. Файлы хуков
закоммичены с режимом 100755 — выписанные деревья получают бит
исполнения из индекса, `doctor --fix` нужен главной копии ради
`core.hooksPath`.

`gitcmd.check_ignore` (третий прямой `subprocess.run` модуля) маркер не
получает намеренно: `git check-ignore` хуков не запускает, SPEC называет
ровно четыре точки входа (требование 6).

Оценка бюджета SPEC ($35) не пересматривается: 2 sh-файла, 3 правки
`orchestrator/`, 1 новый подмодуль, 1 абзац документа, 1 тестовый файл —
в рамках прогноза SPEC.

## Шаги

1. Хуки `scripts/git-hooks/pre-commit`, `scripts/git-hooks/pre-push`
   (100755) — требования 1–3.
2. Маркер пульта в `orchestrator/gitcmd.py` (`PULT_MARKER_ENV`,
   `PULT_MARKER_VALUE`, `pult_env`, `git`, `carpentry`) — требования 6–8;
   `repo_context.git` и `in_repo` — через делегирование.
3. `orchestrator/doctor/git_hooks.py` (`check_git_hooks`,
   `_fix_git_hooks`), реэкспорт в `orchestrator/doctor/__init__.py`,
   подключение в `orchestrator/doctor/cli.py` (`all_checks`, ветка `fix`)
   — требования 4–5, 9.
4. Абзац «Правки main только командами» в `docs/operator-session.md`
   (после «Операторские действия — только по явной команде») —
   требование 10.
5. `tests/test_git_hooks.py`: хуки настоящим git во временном
   репозитории (отказ/проход/маркер/значение маркера/`task/*`/
   `artifact/*`/`refs/artifacts/*`/несколько refs в одном push), маркер в
   env четырёх точек входа и его отсутствие в `os.environ` пульта,
   `role_env` без маркера, `check_git_hooks` (пять исходов + `skip` +
   подключение в `all_checks`), `_fix_git_hooks` (установка, локальность,
   идемпотентность, не-репозиторий, вызов из `cmd_doctor(fix=True)` и
   отсутствие вызова без `--fix`); регенерация карты кодовой базы.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (хуки POSIX sh, только git) | 1 |
| 2 (именованный текст отказа) | 1 |
| 3 (`task/*`, `artifact/*`, `refs/artifacts/*` не трогаются) | 1, 5 |
| 4 (`doctor --fix` ставит `core.hooksPath` и бит исполнения) | 3 |
| 5 (проверка «git-hooks» без `--fix`) | 3 |
| 6 (маркер у `git`/`in_repo`/`carpentry`/`repo_context.git`) | 2 |
| 7 (прочие переменные не меняются; поверх env `carpentry`) | 2 |
| 8 (`role_env` без маркера) | 2 (без правки), 5 |
| 9 (песочницы не наследуют конфиг главной копии) | 3 (репозиторный конфиг, `skip` вне репозитория), 5 |
| 10 (абзац документации) | 4 |
| AC-1..AC-13 | планка `tasks/01M2XMCC837R5CX9M58VARK85G/acceptance_tests/` — 9 файлов, все зелёные |

## Влияние на систему

- **Каждый дочерний git пульта** теперь стартует с `env=` (копия
  `os.environ` + маркер) вместо наследования по умолчанию. Содержимое
  окружения байт-в-байт то же плюс одна переменная — поведение git не
  меняется; проверено тестами `test_gitcmd_*.py`, `test_repo_context.py`,
  `test_multitarget.py`, `test_doctor.py`, `test_git_fixation.py`,
  `test_artifact_branch_*.py`, `test_runner_role_model.py` (см. итоги
  прогонов ниже). Подмены `gitcmd.subprocess.run` в песочницах
  (`SpyRun`, `claude_only_run`, `network_guarded_real_run`) принимают
  `**kwargs` — новый `env=` через них проходит.
- **Мерж/push пульта** (`fsm_merge_gate::_push_merged_main` через
  `repo_context.git`, `pin-update`, `note`, `artifact_branch.push`) идут
  с маркером — хуки для них прозрачны. Роль в worktree коммитит на
  `task/*` — хук пропускает без маркера; маркер в `role_env` не
  протекает (тест на обе стороны).
- **doctor**: одна новая проверка в `all_checks`; в песочницах без
  `git init` — `skip` (не меняет код выхода), в песочницах
  `RealGitSandbox`, гоняющих полный `all_checks` без хуков, дала бы
  `fail` — таких тестов в `tests/` нет (сверено: `cmd_doctor`/`all_checks`
  без патча `all_checks` зовут только `_DoctorTmpRootTest`-песочницы).
  `--fix` вне репозитория ничего не пишет (`git config` не зовётся).
- **Ослаблений нет**: существующие тесты, гейты и guard не трогались;
  `check_pin_unpushed` остаётся (постфактумный сторож дополняется
  превентивным, не заменяется).
- **Откат**: revert одного merge-коммита + в главной копии
  `git config --unset core.hooksPath` (конфиг репозитория revert не
  трогает; без него после отката хуки просто не найдутся — каталога нет
  — и защита тихо исчезнет, `doctor` без проверки об этом не скажет).
- **Зоны SPEC** соблюдены: `scripts/git-hooks/`, `orchestrator/gitcmd.py`,
  `orchestrator/doctor/`, `docs/operator-session.md`, `tests/`;
  `orchestrator/repo_context.py` правки не потребовал (делегирование),
  `orchestrator/config.py`/`runner.py`/`stack.py` не тронуты.
  `docs/codebase-map.md` регенерирован тем же коммитом (правило
  conventions-core).

## Риски

- `skip` вместо `fail` при `config.ROOT` вне git-репозитория — отход от
  буквы AC-10 («fail в остальных случаях») ради требования 9/AC-13;
  обоснование в «Подходе». Если ревью сочтёт, что нужен `fail`, придётся
  доучивать песочницу `tests/test_doctor.py::_DoctorTmpRootTest` (не
  ослабление, но правка существующего теста).
- Главная копия защищена только после `doctor --fix` в ней — сам мерж
  этой задачи `core.hooksPath` не ставит (включение через `init` — вне
  задачи, SPEC «Не входит»). До этого `check_git_hooks` в главной копии
  будет `fail` и красить `doctor` — это ожидаемый сигнал Оператору.
- Ассистентская сессия при Операторе, которой действительно нужно
  закоммитить в main вне команды пульта, получит отказ — это и есть цель;
  обход именован в тексте отказа и в документе.
- Стороннее ПО с `git config --global core.hooksPath` на машине
  Оператора: репозиторный `core.hooksPath` сильнее глобального, но
  глобальные хуки пропадут для этого репозитория. В текущей главной копии
  глобального значения нет (AC-13 сверяет).

## Предложения системе

- `skills/coding-standards.md` / `tests/sandbox.py`: класс «проверка
  doctor, требующая настоящего `config.ROOT`-репозитория, против
  песочницы `_DoctorTmpRootTest` без `git init`» — уже третья проверка
  (`check_root_pin`, `check_pin_unpushed`, теперь `check_git_hooks`)
  решает это своей деградацией (`ok`/`warn`/`skip`) по-разному; общего
  правила «статус проверки, когда ROOT — не репозиторий» нет.
- PATH шага роли не несёт `ls`/`sed` (манифест стека) — обычные
  однострочники осмотра репозитория в шаге приходится переписывать через
  `git ls-files`/`python3`; если это намеренно, стоит сказать в
  `skills/coding-standards.md` одной строкой, чтобы роль не тратила
  попытки.
