---
task: 01M2XMCC837R5CX9M58VARK85G
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Защита main главной копии: git-хуки от ручных коммитов и push в main, маркер команд пульта, включение через doctor --fix

Источник: решение Оператора 19.09 («пора защитить main программно: если
изменение — команда, если команды нет — её нужно сделать»). Парная задача
— «Документная правка командой пульта» (doc-commit), заводится тем же
днём.

Факты:
- В главной копии пульта нет ни одного git-хука (`.git/hooks` пуст,
  `core.hooksPath` не задан); в настройках Claude Code хуков на команды
  Bash нет. Единственный сторож — `doctor` «pin-unpushed»
  (`orchestrator/doctor/root_pin.py::check_pin_unpushed`), который видит
  незапушенные коммиты уже постфактум.
- Ни одна команда пульта не создаёт коммитов на ветке main главной
  копии: `pin-update` (`orchestrator/pin.py`) делает `git merge
  --ff-only` до sha из origin; мерж задачи (`orchestrator/fsm_merge_gate.py::
  _push_merged_main`) пушит явный sha scratch-дерева в `refs/heads/main`
  origin командой `repo_context.git(ctx, "push", "origin",
  "<sha>:refs/heads/main")`, исполняемой в `config.ROOT`; `note`
  (`orchestrator/notes.py`) коммитит в отдельном рабочем репозитории
  `.artel/notes-work`. Push веток задач (`orchestrator/github_adapter.py`)
  и refs/artifacts (`orchestrator/snapshot.py`) main не касаются.
- Инцидент 19.09: ассистентская сессия трижды закоммитила docs/backlog.md
  прямо в main главной копии во время идущих циклов (обход команды
  `note`); после мержа задачи HEAD главной копии отстал от origin на
  четыре коммита, и прямой push стал невозможен без запрещённого pull.
  Правило «HEAD главной копии без локальных коммитов» держится только
  памятью сессии.
- Все вызовы git пультом идут через `orchestrator/gitcmd.py` (`git`,
  `in_repo`, `carpentry`) и `orchestrator/repo_context.py::git`;
  окружение процесса они наследуют от `os.environ` (кроме `carpentry`,
  которой env передаётся явно).
- Рабочие копии ролей (`.artel/worktrees/<id>`) делят конфигурацию
  репозитория с главной копией: `core.hooksPath` действует и на них;
  роли коммитят и пушат только ветки `task/*`.

Требуется:
1. Хуки в репозитории: `scripts/git-hooks/pre-commit` и
   `scripts/git-hooks/pre-push` (POSIX sh, только git и стандартные
   утилиты — PATH роли ограничен манифестом). `pre-commit` отказывает
   коммиту, если текущая ветка — main и в окружении нет маркера пульта
   (требование 3); `pre-push` читает пары refs со stdin и отказывает,
   если среди целевых refs есть `refs/heads/main` и маркера нет. Текст
   отказа именованный: «коммит/push в main главной копии — только
   командой пульта (note, doc-commit, pin-update, approve на merge_gate);
   обход по решению Оператора: ARTEL_PULT_GIT=1». Коммиты и push веток
   `task/*`, `artifact/*`, `refs/artifacts/*` хуки не трогают.
2. Включение: `doctor --fix` ставит `git config core.hooksPath
   scripts/git-hooks` в главной копии и делает хуки исполняемыми;
   `doctor` без `--fix` несёт проверку «git-hooks»: ok при
   `core.hooksPath = scripts/git-hooks` и исполняемых файлах, fail с
   подсказкой `doctor --fix` иначе. Тестовые песочницы (`tests/sandbox.py`,
   временные репозитории) конфигурацию главной копии не наследуют —
   проверить, что существующие тесты не начинают упираться в хуки.
3. Маркер пульта: `gitcmd.git`, `gitcmd.in_repo`, `gitcmd.carpentry` и
   `repo_context.git` добавляют в окружение своих процессов git
   переменную `ARTEL_PULT_GIT=1` — так команды пульта (push мержа,
   pin-update, note, doc-commit) проходят хуки, а ручной `git commit`/
   `git push` из оболочки сессии или Оператора — нет. Прочие переменные
   окружения не меняются (`carpentry` — поверх переданного env).
4. Роли: процесс роли (`runner.role_env`) маркер НЕ получает — роль не
   вправе писать в main (сегодня и не пишет: только ветка задачи; хук
   становится второй линией к `permissions.deny`).
5. Документация: `docs/operator-session.md` — абзац «Правки main только
   командами» с перечнем команд и маркером обхода (обычный документ, не
   защищённый путь).
6. Тесты (tests/): в временном репозитории с включёнными хуками — коммит
   на main без маркера отказывает с именованным текстом, с маркером
   проходит; коммит на ветке `task/x` без маркера проходит; push
   `sha:refs/heads/main` без маркера отказывает, с маркером проходит;
   push ветки `task/x` без маркера проходит; `gitcmd.git`/`in_repo`/
   `carpentry`/`repo_context.git` несут маркер в env дочернего процесса;
   `role_env` маркер не несёт; проверка doctor «git-hooks» ok/fail и
   `--fix` её включает. Существующие `tests/test_gitcmd_*.py`,
   `tests/test_doctor.py`, `tests/test_runner_role_model.py` остаются
   зелёными.

Зоны: scripts/git-hooks/, orchestrator/gitcmd.py,
orchestrator/repo_context.py, orchestrator/doctor/, docs/operator-session.md,
tests/.

Только чтение (не менять): orchestrator/pin.py, orchestrator/fsm_merge_gate.py,
orchestrator/notes.py, orchestrator/github_adapter.py,
orchestrator/snapshot.py (пути записи в origin — только сверить, что
проходят хуки с маркером), orchestrator/runner.py (`role_env` не
меняется — сверить, что маркер туда не протекает через `os.environ`
белым списком `stack.ROLE_ENV_ALLOWLIST`), orchestrator/catalog.py
(`init` — зона идущей задачи 01M2XJKQNF; включение хуков в `init` —
позже, см. «Не входит»).

Не входит: включение хуков командой `init` (зона занята — отдельной
строкой копилки после мержа); хуки на стороне GitHub (защита ветки в
настройках репозитория — действие Оператора); хуки Claude Code на
команды Bash; команда `doc-commit` (парное ТЗ).

Рамка: $35.
