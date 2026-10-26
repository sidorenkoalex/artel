"""Вызовы git в корне репозитория, вопросы к ветке задачи и к произвольному
репозиторию (артефактные git-репо внешних target, ADR-0003 3д, tasks/T021)."""
import os
import sqlite3
import subprocess
import threading
import time
import uuid
from pathlib import Path

from . import config, keychain

# Маркер пульта (SPEC 01M2XMCC837R5CX9M58VARK85G, требования 6-7): git-хуки
# главной копии (`scripts/git-hooks/pre-commit`, `pre-push`) отказывают
# коммиту/push в main всем, у кого этой переменной нет в окружении, —
# команды пульта (push мержа, pin-update, note, doc-commit) помечают свои
# дочерние git-процессы здесь, ручной `git commit`/`git push` из оболочки
# сессии или Оператора маркера не несёт. Процесс роли (`runner.role_env`)
# его тоже не получает: белый список `stack.ROLE_ENV_ALLOWLIST` отсекает
# переменную — хук остаётся второй линией защиты main от роли.
PULT_MARKER_ENV = "ARTEL_PULT_GIT"
PULT_MARKER_VALUE = "1"


def pult_env(base: dict | None = None) -> dict:
    """Окружение дочернего git-процесса пульта: копия `base` (по умолчанию
    — текущего `os.environ`) плюс маркер `ARTEL_PULT_GIT=1` поверх.
    Только копия: сам `os.environ` не трогается, иначе маркер утёк бы в
    любой посторонний процесс пульта."""
    env = dict(os.environ if base is None else base)
    env[PULT_MARKER_ENV] = PULT_MARKER_VALUE
    return env


# Токен хостинга внешнего проекта (SPEC 01M545EDTHS47HSB59AKC1EZ9C,
# требования 1-3, 7): подкоманды git, говорящие с remote, — только они
# получают помощник учётных данных пульта; локальные связку ключей не читают.
HOSTING_SUBCOMMANDS = ("fetch", "push", "pull", "ls-remote")
HOSTING_TOKEN_ENV = "ARTEL_HOSTING_TOKEN"
# Помощник читает пароль из окружения, а не из своего текста: значение
# токена не попадает ни в argv git, ни в argv помощника (`GIT_TRACE`).
HOSTING_CREDENTIAL_HELPER = (
    '!f() { test "$1" = get || exit 0; echo username=x-access-token; '
    f'echo "password=${{{HOSTING_TOKEN_ENV}}}"; }}; f')


def url_key(url: str) -> str:
    """Адрес remote для сравнения: без завершающей черты и `.git`."""
    return url.strip().rstrip("/").removesuffix(".git")


def _under(path: Path, root: Path) -> tuple | None:
    """Части `path` относительно `root` (абсолютный вид, затем с
    раскрытыми ссылками — временный каталог macOS живёт под `/private`);
    `None` — `path` не под `root`."""
    for a, b in ((Path(os.path.abspath(path)), Path(os.path.abspath(root))),
                 (path.resolve(), root.resolve())):
        try:
            return a.relative_to(b).parts
        except ValueError:
            continue
    return None


def _project_of_path(path: Path) -> str | None:
    """Внешний проект, в области которого (`.artel/projects/<имя>/<…>`)
    лежит `path`; сам каталог проекта и область артели — не проект."""
    parts = _under(path, config.PROJECTS)
    if not parts or len(parts) < 2 or parts[0] == config.DEFAULT_TARGET:
        return None
    return parts[0]


def project_by_url(url: str, entries: dict | None = None) -> tuple | None:
    """(имя, запись) внешнего проекта, чей `url` — `url`; `None` — такого
    нет или `targets.yaml` не читается (прежнее поведение)."""
    if entries is None:
        entries = _declared_targets()
    key = url_key(url)
    for name, entry in entries.items():
        if (name != config.DEFAULT_TARGET and isinstance(entry, dict)
                and entry.get("url") and url_key(str(entry["url"])) == key):
            return name, entry
    return None


def _declared_targets() -> dict:
    from . import targets
    try:
        return targets.load()
    except targets.TargetsError:
        return {}


def _hosting_project(args: tuple) -> tuple | None:
    """(имя, запись) внешнего проекта, с хостингом которого говорит
    git-вызов `args`; `None` — вызов локальный, артели или вне проектов."""
    cwd = Path(config.ROOT)
    i = 0
    while i + 1 < len(args) and args[i] in ("-C", "-c"):
        if args[i] == "-C":
            cwd = cwd / args[i + 1]
        i += 2
    rest = args[i:]
    if not rest or rest[0] not in HOSTING_SUBCOMMANDS:
        return None
    name = _project_of_path(cwd)
    if name is not None:
        entry = _declared_targets().get(name)
        if isinstance(entry, dict):
            return name, entry
    if rest[0] == "push":
        entries = _declared_targets()
        for arg in rest[1:]:
            if not arg.startswith("-"):
                found = project_by_url(arg, entries)
                if found is not None:
                    return found
    return None


def hosting_token(name: str, entry: dict) -> tuple[str | None, str | None]:
    """(токен, отказ) операции хостинга проекта `name` по записи `entry`.

    (None, None) — прежняя авторизация: артель либо запись без поля
    `token_slot` вне процесса роли (требования 2, 4). Процесс роли —
    именованный отказ без чтения связки ключей, для записи с полем и без
    (требование 7). Слот пуст — отказ с именем слота (требование 2)."""
    from . import runner
    if name == config.DEFAULT_TARGET:
        return None, None
    if runner.in_role_environment():
        return None, (f"операция хостинга проекта {name} отказана: процесс "
                      f"роли — токен хостинга проекта читается только в "
                      f"сессии Оператора")
    slot = entry.get("token_slot")
    if not slot:
        return None, None
    token = keychain.token(slot)
    if not token:
        return None, (f"слот {slot} связки ключей пуст — операция хостинга "
                      f"проекта {name} отказана (token_slot записи проекта)")
    return token, None


def hosting_env(env: dict, token: str) -> dict:
    """Окружение хостингового git-вызова: чужие помощники сброшены пустым
    `credential.helper`, следом — помощник пульта (как `-c
    credential.helper= -c credential.helper=<пульт>`); конфигурация клона и
    `GIT_CONFIG_GLOBAL` не трогаются."""
    env = dict(env)
    try:
        count = int(env.get("GIT_CONFIG_COUNT") or 0)
    except ValueError:
        count = 0
    for value in ("", HOSTING_CREDENTIAL_HELPER):
        env[f"GIT_CONFIG_KEY_{count}"] = "credential.helper"
        env[f"GIT_CONFIG_VALUE_{count}"] = value
        count += 1
    env["GIT_CONFIG_COUNT"] = str(count)
    env[HOSTING_TOKEN_ENV] = token
    return env


# Единая точка отправки (SPEC 01M5WDB7F14SQ30QVWJY2XYBG2, требование 3;
# ADR-0029 п. 13): через `_push_plan` проходят все пять точек запуска git
# модуля. Любая отправка ветки задачи — запись «ветка отправлена» и опции
# `policy.push_options`; проект под белым списком (`targets.push_whitelisted`)
# — проверка argv, окружения и конфигурации клона до запуска процесса.
PUSH_SENT_ACTION = "ветка отправлена"
PUSH_REFUSED_ACTION = "отправка отказана"
PUSH_WHITELIST_SOURCE = "branch_push_whitelist"
PUSH_SUBCOMMANDS = ("push", "send-pack")
PUSH_RESET_CONFIG = ("-c", "push.followTags=false", "-c", "push.pushOption=")
PUSH_ALLOWED_FLAGS = ("-u", "--set-upstream", "-q", "--delete")
PUSH_LEASE_FLAG = "--force-with-lease"
ARTIFACT_REF_PREFIX = "refs/artifacts/"
GIT_CONFIG_ENV_NAMES = ("GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS")
GIT_CONFIG_ENV_PREFIXES = ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")
# Глобальные опции git со значением отдельным словом.
GIT_GLOBALS_WITH_VALUE = ("-C", "-c", "--git-dir", "--work-tree", "--namespace",
                          "--config-env", "--super-prefix")
# Встроенные подкоманды git: псевдоним их не перекрывает, конфигурацию
# клона ради них не читаем. Прочие — кандидаты в псевдоним (`alias.*`).
GIT_BUILTINS = frozenset((
    "add", "am", "apply", "archive", "bisect", "blame", "branch", "bundle",
    "cat-file", "check-attr", "check-ignore", "check-ref-format", "checkout",
    "cherry", "cherry-pick", "clean", "clone", "commit", "commit-tree",
    "config", "count-objects", "describe", "diff", "diff-files", "diff-index",
    "diff-tree", "fetch", "for-each-ref", "format-patch", "fsck", "gc", "grep",
    "hash-object", "help", "init", "log", "ls-files", "ls-remote", "ls-tree",
    "merge", "merge-base", "merge-file", "merge-tree", "mktree", "mv",
    "name-rev", "notes", "prune", "pull", "read-tree", "rebase", "reflog",
    "remote", "repack", "replace", "reset", "restore", "rev-list", "rev-parse",
    "revert", "rm", "shortlog", "show", "show-ref", "sparse-checkout", "stash",
    "status", "switch", "symbolic-ref", "tag", "update-index", "update-ref",
    "var", "verify-commit", "version", "worktree", "write-tree",
))


def _project_tasks(project: str) -> list:
    """(id, ветка, состояние) задач проекта из БД пульта; БД нет — пусто."""
    if not config.DB.exists():
        return []
    from . import store
    return store.project_tasks(store.db(), project)


def _last_sent_sha(task_id: str) -> str | None:
    """sha последней записи «ветка отправлена» журнала задачи."""
    if not config.DB.exists():
        return None
    from . import store
    row = store.last_task_step_of(store.db(), task_id, (PUSH_SENT_ACTION,))
    return (row["detail"] or "").split(" ")[0] if row is not None else None


def _raw_config(cwd: Path, *args: str) -> str:
    """Вывод `git config <args>` клона `cwd`; пусто — ключа нет."""
    try:
        res = subprocess.run(["git", "-C", str(cwd), "config", *args],
                             capture_output=True, text=True, env=pult_env())
    except OSError:
        return ""
    return res.stdout.strip() if res.returncode == 0 else ""


def _split_globals(args: list, cwd: Path) -> tuple[list, int | None, Path]:
    """(глобальные опции, индекс подкоманды или None, рабочий каталог git
    с учётом `-C`) argv git без ведущего `git`."""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        word = args[i]
        if word in GIT_GLOBALS_WITH_VALUE:
            if word == "-C" and i + 1 < len(args):
                cwd = cwd / args[i + 1]
            i += 2
        else:
            i += 1
    return args[:i], (i if i < len(args) else None), cwd


def _push_words(rest: list) -> tuple[list, list, list]:
    """(флаги, значения `-o`, позиционные) аргументов после `push`."""
    flags, options, positional = [], [], []
    i = 0
    while i < len(rest):
        word = rest[i]
        if word in ("-o", "--push-option"):
            options.append(rest[i + 1] if i + 1 < len(rest) else "")
            i += 2
            continue
        if word.startswith("--push-option="):
            options.append(word.split("=", 1)[1])
        elif word.startswith("-o") and len(word) > 2:
            options.append(word[2:])
        elif word.startswith("-"):
            flags.append(word)
        else:
            positional.append(word)
        i += 1
    return flags, options, positional


def _is_url(dest: str) -> bool:
    return "://" in dest or (":" in dest and "@" in dest.split(":", 1)[0])


class _PushPlan:
    """Решение точки отправки по одному вызову git: argv к запуску или
    отказ; после успешного кода — записи «ветка отправлена»."""

    def __init__(self, args: list, cwd: Path):
        self.args = args
        self.cwd = cwd
        self.refusal: str | None = None
        self.sent: list = []

    def after(self, code: int) -> None:
        """Записи «ветка отправлена: <sha>» после отправки с кодом 0."""
        if code != 0 or not self.sent:
            return
        from . import store
        try:
            conn = store.db()
            for task_id, src, branch in self.sent:
                res = subprocess.run(
                    ["git", "-C", str(self.cwd), "rev-parse", "--verify",
                     f"{src}^{{commit}}"], capture_output=True, text=True,
                    env=pult_env())
                sha = res.stdout.strip() if res.returncode == 0 else ""
                if sha:
                    store.journal(conn, task_id, "orchestrator",
                                  PUSH_SENT_ACTION, f"{sha} {branch}")
        except (OSError, sqlite3.Error):
            # Запись — след отправки, не её условие: отправка уже прошла.
            pass


def _dead_states() -> tuple:
    """Окончательные состояния: ветка такой задачи — не «своя» ветка
    отправки. Список — `fsm.TERMINAL_STATES`; импорт отложен, потому что
    `fsm` сам импортирует этот модуль."""
    from . import fsm
    return fsm.TERMINAL_STATES


def _refspecs(refspecs: list, tasks: list) -> list:
    """Разбор refspec отправки: словарь на каждый — назначение, вид
    (`branch`/`artifacts`/`ref`), форма (`+`, `:<ref>`) и задача проекта, к
    ветке или ссылке документов которой он относится (`None` — нет такой)."""
    by_branch: dict = {}
    for row in tasks:
        live = row["state"] not in _dead_states()
        if row["branch"] not in by_branch or live:
            by_branch[row["branch"]] = row
    ids = {row["id"]: row for row in tasks}
    parsed = []
    for spec in refspecs:
        body = spec[1:] if spec.startswith("+") else spec
        src, colon, dst = body.partition(":")
        dst = dst if colon else src
        if dst.startswith(ARTIFACT_REF_PREFIX):
            kind, name = "artifacts", dst
            row = ids.get(dst[len(ARTIFACT_REF_PREFIX):])
        elif dst.startswith("refs/") and not dst.startswith("refs/heads/"):
            kind, name, row = "ref", dst, None
        else:
            kind, name = "branch", dst.removeprefix("refs/heads/")
            row = by_branch.get(name)
        parsed.append({"spec": spec, "src": src or name, "name": name,
                       "kind": kind, "plus": spec.startswith("+"),
                       "colon": colon and not src, "task": row})
    return parsed


def _whitelist_refusal(project: str, entry: dict, globals_: list, sub: str,
                       cwd: Path, env: dict, flags: list, options: list,
                       positional: list, specs: list) -> str | None:
    """Причина отказа отправки проекта под белым списком (требование 3
    (в)); None — отправка разрешена."""
    from . import targets
    if sub != "push":
        return f"подкоманда {sub} — отправка только через push"
    i = 0
    while i < len(globals_):
        if globals_[i] != "-C":
            return f"глобальная опция git {globals_[i]} перед push"
        i += 2
    if _project_of_path(cwd) != project:
        return f"отправка не из клона проекта {project} ({cwd})"
    names = sorted(n for n in env if n in GIT_CONFIG_ENV_NAMES
                   or n.startswith(GIT_CONFIG_ENV_PREFIXES))
    if names:
        return f"переменные окружения {', '.join(names)}"
    leases = []
    for flag in flags:
        if flag.startswith(PUSH_LEASE_FLAG + "="):
            leases.append(flag.split("=", 1)[1])
        elif flag not in PUSH_ALLOWED_FLAGS:
            return f"флаг {flag} вне белого списка"
    forbidden = entry.get("push_options_forbidden") or []
    for option in options:
        reason = targets.push_option_error(option, forbidden)
        if reason is not None:
            return f"опция -o {reason}"
    if not positional or not specs:
        return "отправка без явного refspec"
    dest = positional[0]
    if dest != "origin" and url_key(dest) != url_key(str(entry.get("url") or "")):
        return f"назначение {dest} — не origin и не url записи проекта"
    deleting = "--delete" in flags
    for spec in specs:
        if spec["plus"]:
            return f"refspec {spec['spec']} с «+»"
        if spec["colon"]:
            return f"удаление формой {spec['spec']}"
        if deleting:
            if spec["kind"] != "artifacts" or spec["task"] is None:
                return (f"--delete {spec['spec']} — удаление только "
                        f"refs/artifacts/<id> задачи проекта")
            continue
        if spec["kind"] == "artifacts":
            continue
        if spec["kind"] == "ref":
            return f"отправка ссылки {spec['name']} (теги и иные ссылки)"
        if spec["name"] == entry.get("base"):
            return f"отправка в base {spec['name']}"
        task = spec["task"]
        if task is None or task["state"] in _dead_states():
            return f"ветка {spec['name']} — не ветка живой задачи проекта"
    for lease in leases:
        ref, colon, sha = lease.partition(":")
        name = ref.removeprefix("refs/heads/")
        own = [s for s in specs if s["kind"] == "branch" and s["name"] == name]
        if not colon or not sha or not own:
            return f"{PUSH_LEASE_FLAG}={lease} — нужна форма <своя ветка>:<sha>"
        last = _last_sent_sha(own[0]["task"]["id"])
        if last != sha:
            return (f"{PUSH_LEASE_FLAG}={lease}: sha не последней записи "
                    f"«{PUSH_SENT_ACTION}» ({last or 'записи нет'})")
    for key in ("pushurl", "push", "mirror"):
        if _raw_config(cwd, "--get-all", f"remote.origin.{key}"):
            return f"в конфигурации клона задан remote.origin.{key}"
    if _raw_config(cwd, "--local", "--get-all", "push.pushOption"):
        return "в конфигурации клона задан push.pushOption"
    return None


def _refuse(plan: _PushPlan, project: str | None, related: str | None,
            env: dict, task_id: str | None, reason: str) -> _PushPlan:
    """Отказ отправки с записью: журнал задачи отправки, иначе задачи
    контекста (`task_id`, `ARTEL_TASK`), иначе алерт `incident`."""
    from . import alerts, store
    plan.refusal = f"{PUSH_REFUSED_ACTION} (проект {project}): {reason}"
    context = task_id or env.get(config.ARTEL_TASK_ENV) or os.environ.get(
        config.ARTEL_TASK_ENV)
    try:
        conn = store.db()
        target = related or (context if context and store.task_exists(
            conn, context) else None)
        if target is not None:
            store.journal(conn, target, "orchestrator", PUSH_REFUSED_ACTION,
                          plan.refusal)
        else:
            alerts.raise_alert(conn, project, "incident", PUSH_WHITELIST_SOURCE,
                               plan.refusal)
    except sqlite3.Error:
        pass
    return plan


def _push_plan(args: list, cwd: Path, env: dict | None,
               task_id: str | None) -> _PushPlan | None:
    """Решение единой точки отправки по argv git `args` (без `git`),
    запущенному в `cwd` с окружением `env` (None — окружение пульта).
    None — вызов не отправка и не псевдоним в клоне проекта."""
    globals_, index, cwd = _split_globals(args, cwd)
    if index is None:
        return None
    sub = args[index]
    if sub not in PUSH_SUBCOMMANDS and sub in GIT_BUILTINS:
        return None
    from . import targets
    env = dict(os.environ if env is None else env)
    plan = _PushPlan(list(args), cwd)
    cwd_project = _project_of_path(cwd)
    try:
        entries = targets.load()
    except targets.TargetsError:
        entries = None
    if sub not in PUSH_SUBCOMMANDS:
        # Подкоманда вне встроенных — возможно, псевдоним клона.
        if cwd_project is None:
            return None
        entry = (entries or {}).get(cwd_project)
        if entry is not None and not targets.push_whitelisted(entry):
            return None
        alias = _raw_config(cwd, "--get", f"alias.{sub}")
        if not alias:
            return None
        return _refuse(plan, cwd_project, None, env, task_id,
                       f"подкоманда {sub} — псевдоним git ({alias})")
    flags, options, positional = _push_words(args[index + 1:])
    dest = positional[0] if positional else ""
    project = cwd_project
    if project is None and dest and not _is_url(dest):
        project = _project_of_path(cwd / dest.removeprefix("file://"))
    if project is None and dest and entries is not None:
        found = project_by_url(dest, entries)
        project = found[0] if found is not None else None
    project = project or config.DEFAULT_TARGET
    tasks = _project_tasks(project)
    specs = _refspecs(positional[1:], tasks)
    related = next((s["task"]["id"] for s in specs if s["task"] is not None),
                   None)
    entry = (entries or {}).get(project)
    if project != config.DEFAULT_TARGET and entry is None:
        why = ("targets.yaml не читается" if entries is None
               else "записи проекта нет")
        return _refuse(plan, project, related, env, task_id,
                       f"гейт мержа неизвестен — {why}")
    whitelisted = (project != config.DEFAULT_TARGET
                   and targets.push_whitelisted(entry))
    if whitelisted:
        reason = _whitelist_refusal(project, entry, globals_, sub, cwd, env,
                                    flags, options, positional, specs)
        if reason is not None:
            return _refuse(plan, project, related, env, task_id, reason)
    deleting = "--delete" in flags or "-d" in flags or any(
        s["colon"] for s in specs)
    branches = [s for s in specs if s["kind"] == "branch"
                and s["task"] is not None and not s["colon"]]
    added = []
    if branches and not deleting:
        for option in (entry or {}).get("push_options") or []:
            added += ["-o", option]
    if sub == "push" and not deleting and "--dry-run" not in flags \
            and "-n" not in flags:
        plan.sent = [(s["task"]["id"], s["src"], s["name"]) for s in branches]
    reset = list(PUSH_RESET_CONFIG) if whitelisted else []
    plan.args = (globals_ + reset + [sub] + added + list(args[index + 1:]))
    return plan


def _refused(args, refusal: str, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        list(args), 1, "" if text else b"",
        refusal if text else refusal.encode())


def git(*args: str, task_id: str | None = None) -> subprocess.CompletedProcess:
    """git в корне репозитория; исход разбирает вызывающий.

    Ошибка запуска (git не установлен) — такой же ненулевой код возврата,
    как и ошибка самой команды: уборке достаточно знать, что ответа нет.

    Дочерний процесс получает окружение пульта плюс маркер
    `ARTEL_PULT_GIT=1` (`pult_env`, требования 6-7): прочие переменные не
    меняются — git-идентичность, PATH, `GIT_*` Оператора доходят как есть.

    Хостинговая операция внешнего проекта (`_hosting_project`) идёт с
    токеном слота `token_slot` его записи (`hosting_env`) либо отказывает
    без запуска git (`hosting_token`; SPEC 01M545EDTHS47HSB59AKC1EZ9C).

    Отправка проходит единую точку `_push_plan` (SPEC
    01M5WDB7F14SQ30QVWJY2XYBG2, требование 3); `task_id` — задача, от имени
    которой команда пульта отправляет (журнал отказа без своей задачи).
    """
    env = pult_env()
    plan = _push_plan(list(args), Path(config.ROOT), env, task_id)
    if plan is not None:
        if plan.refusal is not None:
            return _refused(args, plan.refusal)
        args = tuple(plan.args)
    project = _hosting_project(args)
    if project is not None:
        token, refusal = hosting_token(*project)
        if refusal is not None:
            return subprocess.CompletedProcess(args, 1, "", refusal)
        if token is not None:
            env = hosting_env(env, token)
    try:
        res = subprocess.run(["git", *args], cwd=config.ROOT, env=env,
                             capture_output=True, text=True)
    except OSError as exc:
        return subprocess.CompletedProcess(args, 1, "", str(exc))
    if plan is not None:
        plan.after(res.returncode)
    return res


def current_branch(repo: Path | None = None) -> str:
    """Ветка под HEAD; пустая строка — git не ответил.

    `res is None` — заглушки `gitcmd.git` в тестах, не связанных с git,
    отвечают `None` тем же приёмом, что и у `head_sha` (T031: эта функция
    впервые попадает на горячий путь `set_state` через `on_foreign_branch`,
    где такие заглушки уже встречаются).
    """
    args = ("rev-parse", "--abbrev-ref", "HEAD")
    res = in_repo(repo, *args) if repo else git(*args)
    return res.stdout.strip() if res is not None and res.returncode == 0 else ""


def qualified_ref(branch: str) -> str:
    """Полное имя ссылки: имя ветки — под `refs/heads/`, полное имя
    (`refs/artifacts/<id>` — ссылка документов задачи, ADR-0021 п.3) —
    как есть. Вопросы «есть ли/какой sha» к ветке и к ссылке документов
    задаёт один и тот же примитив."""
    return branch if branch.startswith("refs/") else f"refs/heads/{branch}"


def branch_exists(branch: str, repo: Path | None = None) -> bool:
    """`res is None` — тот же вырожденный случай, что у `head_sha`: заглушки
    `gitcmd.git` в тестах, не связанных с git, отвечают `None`. `repo` —
    клон проекта, в котором живёт ветка (ADR-0021 п.1)."""
    args = ("rev-parse", "--verify", "--quiet", qualified_ref(branch))
    res = in_repo(repo, *args) if repo else git(*args)
    return res is not None and res.returncode == 0


def branch_merged(branch: str, repo: Path | None = None,
                  base: str | None = None) -> bool:
    """Смержена ли ветка в main — тем же критерием, каким git защищает `-d`.
    `repo` — клон проекта; `base` — ревизия main (в клоне — `origin/main`:
    локальный `main` клона push мержа не двигает)."""
    args = ("branch", "--merged", base or config.MAIN_BRANCH, "--list", branch)
    res = in_repo(repo, *args) if repo else git(*args)
    return res.returncode == 0 and bool(res.stdout.strip())


def commits_behind(branch: str, base: str | None = None,
                   repo: Path | None = None) -> int | None:
    """Число коммитов `base` (по умолчанию `config.MAIN_BRANCH`), которых
    нет в `branch`; `None` — git не ответил, `branch`/`base` не существует,
    или ответ не разобрать как число (SPEC T051, требование 2).

    `base` — параметр, не читается через `config.MAIN_BRANCH` как значение
    по умолчанию аргумента (оно вычислилось бы один раз при определении
    функции и не увидело бы подмену `config.MAIN_BRANCH` в тестах, тот же
    приём, что у остальных примитивов модуля). `res is None`/непустой,
    но нечисловой вывод — тот же вырожденный случай «git не ответил
    осмысленно», что у `head_sha`: заглушки `gitcmd.git` в
    тестах, не связанных с git (SPEC T051, требование 9), отвечают пустым
    выводом с кодом 0 на любую нераспознанную команду и не должны
    трактоваться как «ноль коммитов».

    `repo` (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, AC-4) — клон, в котором
    сравниваются `branch`/`base` (`gitcmd.in_repo`), не всегда `config.ROOT`:
    ветка внешнего target существует только в её собственном клоне.
    `None` (по умолчанию) — прежнее поведение байт-в-байт.
    """
    args = ("rev-list", "--count", f"{branch}..{base or config.MAIN_BRANCH}")
    res = in_repo(repo, *args) if repo else git(*args)
    if res is None or res.returncode != 0:
        return None
    text = res.stdout.strip()
    return int(text) if text.isdigit() else None


def is_ancestor(ancestor: str, descendant: str,
                repo: Path | None = None) -> bool:
    """`ancestor` — предок `descendant` (или тот же коммит) тем же
    критерием, каким это понимает сам git (`merge-base --is-ancestor`).

    Несуществующий/несвязанный sha даёт ненулевой код возврата — тот же
    `False`, что и «не предок» (ANSWER-1
    01M1NGFK3N6MRMYGCC09H975V3 п.3: прогон с чужой историей не считается
    вовсе, не «бесконечно старый»)."""
    args = ("merge-base", "--is-ancestor", ancestor, descendant)
    res = in_repo(repo, *args) if repo else git(*args)
    return res is not None and res.returncode == 0


def commit_exists(sha: str, repo: Path | None = None) -> bool:
    """`sha` — коммит в объектной базе репозитория пульта (или клона
    `repo`, если задан). `False` — объекта нет (или он не коммит), либо
    git не ответил."""
    args = ("cat-file", "-e", f"{sha}^{{commit}}")
    res = in_repo(repo, *args) if repo else git(*args)
    return res is not None and res.returncode == 0


def merges_between(sha_from: str, sha_to: str,
                   repo: Path | None = None) -> int | None:
    """Число merge-коммитов на отрезке `sha_from..sha_to` (ANSWER-1
    01M1NGFK3N6MRMYGCC09H975V3 п.3: «возраст» зелёного прогона канарейки
    относительно целевого sha) — тот же вырожденный случай `None`, что и
    `commits_behind`: git не ответил, либо ответ не разобрать числом."""
    # Hotfix №20 (11.09): только мержи В main — по первой родительской
    # линии. Без `--first-parent` считались и merge-коммиты внутри ветки
    # задачи (подтяжка main, слияние разработчика, снимок артефактов):
    # один мерж задачи давал 4 «мержа», гейт pin-update (порог 10)
    # срабатывал через 2–3 задачи.
    args = ("rev-list", "--count", "--first-parent", "--merges",
            f"{sha_from}..{sha_to}")
    res = in_repo(repo, *args) if repo else git(*args)
    if res is None or res.returncode != 0:
        return None
    text = res.stdout.strip()
    return int(text) if text.isdigit() else None


def commit_committer_dates(since: str, until: str,
                           repo: Path | None = None) -> list[str] | None:
    """ISO8601 committer-даты (`%cI`, со смещением) коммитов диапазона
    `since..until` (SPEC T076, требование 1) — порядок вывода `git log`
    вызывающему коду не важен, каждая дата сверяется независимо
    (`fixation.refixate_after_rejected_transition`).

    `None` — git не ответил, либо диапазон недостижим (`since` не предок
    `until`, несуществующий sha — `res.returncode != 0`): вызывающий код
    обязан трактовать это как «неизвестно» и не перефиксировать
    (fail-closed, тот же принцип, что `fixation.check_integrity` при
    неответившем git).
    """
    args = ("log", "--format=%cI", f"{since}..{until}")
    res = in_repo(repo, *args) if repo else git(*args)
    if res is None or res.returncode != 0:
        return None
    return [ln for ln in res.stdout.splitlines() if ln.strip()]


def list_branches(prefix: str = "", repo: Path | None = None) -> list[str] | None:
    """Локальные ветки под `refs/heads/<prefix>`; `None` — git не ответил.

    Наблюдаемый мир для холодного старта (SPEC T049, требование 1):
    ветки `task/*` без строки БД — один из трёх источников максимума
    номеров задач (`orchestrator/coldstart.py`). Пустой список — легитимный
    ответ (веток с таким префиксом нет), тот же приём, что у
    `ls_tree_files` не путать с `None`.
    """
    args = ("for-each-ref", "--format=%(refname:short)", f"refs/heads/{prefix}")
    res = in_repo(repo, *args) if repo else git(*args)
    if res is None or res.returncode != 0:
        return None
    return [b for b in res.stdout.splitlines() if b]


def carpentry(repo: Path, args: list, env: dict, *,
             input: bytes | None = None, text: bool = True,
             task_id: str | None = None) -> subprocess.CompletedProcess:
    """Плотницкая git-команда (read-tree/hash-object/update-index/write-tree/
    commit-tree — `artifact_branch.write_commit`) в `repo` со своим
    окружением (`GIT_INDEX_FILE`, для `commit-tree` — ещё и `GIT_AUTHOR_*`/
    `GIT_COMMITTER_*`): единая точка `subprocess.run` для всей плотницкой
    записи артефактной ветки (SPEC 01M1KVGD18P9H5WR7VM8TGPV1T, требования
    2-3) — раньше `artifact_branch.py` звал `subprocess.run` напрямую, в
    обход `gitcmd` и любой его подмены, и утекал в НАСТОЯЩИЙ репозиторий
    пульта из тестов, подменявших только `gitcmd.git` (SPEC «Контекст»).

    `tests/sandbox.py::TmpRootTest` патчит не эту функцию отдельно, а сам
    `gitcmd.subprocess.run` (тот же объект, что глобальный `subprocess.
    run`, — общий модуль-синглтон): патч перехватывает и эти вызовы тоже,
    без изменения точки подмены (`tests/01M1KVGD18P9H5WR7VM8TGPV1T/
    acceptance_tests/test_ac3_sandbox_default_covers_carpentry.py`).

    Маркер пульта `ARTEL_PULT_GIT=1` ложится ПОВЕРХ переданного `env`
    (`pult_env(env)`, SPEC 01M2XMCC837R5CX9M58VARK85G, требование 7):
    `GIT_INDEX_FILE`/`GIT_AUTHOR_*`/`GIT_COMMITTER_*` плотницкой записи
    доходят до git нетронутыми.

    Ошибка запуска (git не установлен) — ненулевой код возврата, как у
    `git()`: запись в ссылку документов на переходе FSM (паспорт задачи) не
    имеет права ронять сам переход — kill switch срабатывает и без git.
    """
    plan = _push_plan(list(args), Path(repo), env, task_id)
    if plan is not None:
        if plan.refusal is not None:
            return _refused(["git", *args], plan.refusal, text)
        args = plan.args
    try:
        res = subprocess.run(["git", *args], cwd=repo, env=pult_env(env),
                             capture_output=True, text=text, input=input)
    except OSError as exc:
        return subprocess.CompletedProcess(["git", *args], 1,
                                           "" if text else b"", str(exc))
    if plan is not None:
        plan.after(res.returncode)
    return res


def _point_plan(repo: Path, args: tuple, env: dict | None,
                task_id: str | None) -> tuple[list, _PushPlan | None]:
    """(argv после `git`, решение точки отправки) точек `read*` (`-C`)."""
    argv = ["-C", str(repo), *args]
    plan = _push_plan(argv, Path(config.ROOT), env, task_id)
    return (plan.args if plan is not None else argv), plan


def in_repo(repo: Path, *args: str,
            task_id: str | None = None) -> subprocess.CompletedProcess:
    """git-команда в произвольном репозитории (не ROOT пульта) через `-C`.

    Не `subprocess.run(..., cwd=repo)` внутри `git()`: существующие тесты
    подменяют саму функцию `gitcmd.git` заглушками сигнатуры `(*args: str)`
    (мультитаргет, FSM, бюджет, автоцикл) — добавь `git()` параметр `cwd`,
    эти заглушки упали бы `TypeError` на неожиданном keyword-аргументе.
    `-C <repo>` остаётся обычным позиционным аргументом `git(*args)`, тем
    же вызовом, который заглушки уже умеют разобрать (tasks/T021 PLAN,
    «Подход»).

    `task_id` уходит в `git` только заданным — те же заглушки его не знают.
    """
    if task_id is None:
        return git("-C", str(repo), *args)
    return git("-C", str(repo), *args, task_id=task_id)


# Чтения git со сроком, байтами, своим окружением и потоком (SPEC
# 01M5T79C5GFJGQ9XCTH8W0PDFQ): у мест, которые раньше звали `subprocess`
# сами, одна точка запуска git — сюда повесит память чтений git 4.
# `subprocess.TimeoutExpired` из этих функций наружу не выходит: истечение
# срока — `Timeout`, вызывающий отличает его от прочих отказов.

class Timeout(Exception):
    """Срок git-команды истёк; процесс git остановлен."""


class OverLimit(Exception):
    """Поток вывода git превысил предел байт; процесс git остановлен."""


class LaunchFailed(Exception):
    """Процесс потока не запустился; `error` — исключение запуска как есть
    (`OSError` либо `TimeoutExpired` конструктора процесса)."""

    def __init__(self, error: BaseException):
        super().__init__(str(error))
        self.error = error


def read(repo: Path, *args: str, timeout: float | None = None,
         input: bytes | None = None, text: bool = False,
         task_id: str | None = None) -> subprocess.CompletedProcess:
    """git-команда в `repo` (`-C`) через `subprocess.run`, вывод байтами
    (`text` — строкой), `input` — байтовый вход, `timeout` — срок.

    Не `in_repo`: подмены `gitcmd.git` тестов (`fake_git`) отвечают
    фейком, а этим чтениям нужен настоящий git. Путь — глобальный
    `subprocess.run`, как раньше у мест: его по-прежнему видят `SpyRun` и
    шпионы `subprocess.run` существующих тестов. Ключевые аргументы, не
    заданные вызывающим, в `subprocess.run` не передаются — вызов тот же,
    что был у места. `OSError` запуска выходит наружу: каждое место
    разбирает его по-своему; истечение срока — `Timeout`."""
    kwargs = {}
    if input is not None:
        kwargs["input"] = input
    if text:
        kwargs["text"] = True
    if timeout is not None:
        kwargs["timeout"] = timeout
    argv, plan = _point_plan(repo, args, None, task_id)
    if plan is not None and plan.refusal is not None:
        return _refused(["git", *argv], plan.refusal, text)
    try:
        res = subprocess.run(["git", *argv],
                             capture_output=True, env=pult_env(), **kwargs)
    except subprocess.TimeoutExpired:
        raise Timeout(f"git {args[0] if args else ''}: срок {timeout} с "
                      f"истёк") from None
    if plan is not None:
        plan.after(res.returncode)
    return res


def read_env(repo: Path, env: dict, *args: str, timeout: float,
             task_id: str | None = None) -> subprocess.CompletedProcess:
    """git-команда в `repo` (`-C`, `cwd` — `config.ROOT`) со своим
    окружением `env` (`GIT_INDEX_FILE` временного индекса) поверх маркера
    пульта; вывод строкой.

    Не `carpentry`: процесс — `subprocess.Popen` со сроком, мимо
    перехвата `subprocess.run` шпионом `SpyRun` (тот ответил бы фейковым
    sha на `write-tree`). По истечении срока процесс убивается и вывод
    дочитывается — `Timeout`; `OSError` запуска выходит наружу."""
    argv, plan = _point_plan(repo, args, env, task_id)
    if plan is not None and plan.refusal is not None:
        return _refused(["git", *argv], plan.refusal)
    process = subprocess.Popen(["git", *argv],
                               cwd=config.ROOT, env=pult_env(env),
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise Timeout(f"git {args[0] if args else ''}: срок {timeout} с "
                      f"истёк") from None
    if plan is not None:
        plan.after(process.returncode)
    return subprocess.CompletedProcess(process.args, process.returncode,
                                       stdout, stderr)


STREAM_CHUNK = 1 << 16


def read_stream(repo: Path, *args: str, limit: int, timeout: float,
                chunk: int = STREAM_CHUNK,
                task_id: str | None = None) -> subprocess.CompletedProcess:
    """Вывод git-команды в `repo` (`-C`), прочитанный потоком порциями
    `chunk` с пределом `limit` байт и сроком `timeout`; stderr отброшен.

    Три различимых отказа: перебор предела — `OverLimit`, истечение срока
    — `Timeout` (процесс в обоих случаях убит, вывод сверх предела не
    копится), процесс не запустился — `LaunchFailed`. Ненулевой код
    возврата — не исключение: результат с этим кодом разбирает вызывающий.
    Процесс — `subprocess.Popen`: поток через `subprocess.run` не читается."""
    argv, plan = _point_plan(repo, args, None, task_id)
    if plan is not None and plan.refusal is not None:
        return _refused(["git", *argv], plan.refusal, text=False)
    end = time.monotonic() + timeout
    try:
        proc = subprocess.Popen(["git", *argv],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, env=pult_env())
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LaunchFailed(exc) from exc
    expired = threading.Event()

    def kill_on_deadline():
        expired.set()
        proc.kill()

    timer = threading.Timer(timeout, kill_on_deadline)
    timer.start()
    chunks, total, over = [], 0, False
    try:
        while True:
            data = proc.stdout.read(chunk)
            if not data:
                break
            total += len(data)
            if total > limit:
                over = True
                proc.kill()
                break
            chunks.append(data)
        proc.stdout.close()
        code = proc.wait()
    finally:
        timer.cancel()
    if over:
        raise OverLimit(f"вывод git {args[0] if args else ''} > {limit} байт")
    if expired.is_set() or time.monotonic() > end:
        raise Timeout(f"git {args[0] if args else ''}: срок {timeout} с истёк")
    if plan is not None:
        plan.after(code)
    return subprocess.CompletedProcess(proc.args, code, b"".join(chunks), None)


def head_sha(repo: Path | None = None) -> str:
    """sha текущего HEAD; пустая строка — нет коммитов или git не ответил.

    `res is None` — не только реальный отказ `subprocess.run` (уже
    свёрнут в `git()` в `CompletedProcess` с ненулевым кодом), но и
    подмена `gitcmd.git` в тестах, не связанных с git вовсе
    (test_advance_guard.py: `lambda *a: None`, задачам которого сама
    фиксация артефактов не нужна) — тот же смысл «ответа нет».
    """
    res = in_repo(repo, "rev-parse", "HEAD") if repo else git("rev-parse", "HEAD")
    return res.stdout.strip() if res is not None and res.returncode == 0 else ""


def check_ignore(paths, repo: Path | None = None) -> set[str] | None:
    """Пути из `paths`, которые `.gitignore` ПУЛЬТА (`config.ROOT`) считает
    игнорируемыми; `None` — git не ответил. Настоящий разбор `.gitignore`
    (`git check-ignore`), не самодельный список расширений (SPEC
    01M1KVG3KSCY47HWXWF5HM0E76, требование 1) — только так ловится
    директорное правило (например, `__pycache__/`), которое списком
    суффиксов не выразить.

    Батч одним вызовом `--stdin -z` на весь список путей шага, не по
    одному на файл. Путям не обязательно существовать на диске
    `config.ROOT` — `check-ignore` матчит их как строки пути, не как
    файлы (нужно для путей внешнего target, которых в рабочей копии
    пульта нет вовсе).
    """
    paths = list(paths)
    if not paths:
        return set()
    data = "".join(p + "\0" for p in paths).encode()
    try:
        res = subprocess.run(["git", "check-ignore", "-v", "-z", "--stdin"],
                             cwd=repo or config.ROOT, input=data,
                             capture_output=True)
    except OSError:
        return None
    if res.returncode not in (0, 1):
        return None
    fields = res.stdout.split(b"\0")
    ignored = set()
    i = 0
    while i + 3 < len(fields):
        pathname = fields[i + 3]
        if pathname:
            ignored.add(pathname.decode())
        i += 4
    return ignored


def diff_names(a: str, b: str, *paths: str,
               repo: Path | None = None) -> list[str] | None:
    """Пути, различающиеся между `a` и `b` под `paths`; `None` — git не
    ответил. В отличие от `diff_paths` (голое да/нет), отдаёт сами пути —
    нужно, чтобы отличить настоящую правку от разницы только в
    игнорируемых `.gitignore` файлах (SPEC 01M1KVG3KSCY47HWXWF5HM0E76,
    требование 3). `repo` — как у `show`."""
    args = ("diff", "--name-only", a, b, "--", *paths)
    res = in_repo(repo, *args) if repo else git(*args)
    if res is None or res.returncode != 0:
        return None
    return [p for p in res.stdout.splitlines() if p]


def diff_name_status(a: str, b: str, *paths: str,
                     repo: Path | None = None) -> list[tuple] | None:
    """Записи `git diff -M --name-status` между `a` и `b` под `paths`:
    `(статус, путь, новый путь | None)`; `None` — git не ответил (тот же
    вырожденный случай, что у `diff_names` рядом).

    Отличие от `diff_names`: статус записи и ВТОРОЙ путь у пары
    переименования/копии (`R100`/`C85`) — определение переименования
    остаётся работой git (SPEC 01M3FQ2V77QNK95Z599DM124QN, требование 3),
    а не собственной эвристики пульта «пара удалён/добавлен с совпадающим
    набором имён».

    Разбор идёт по `-z` (поля разделены NUL, у `R`/`C` их три подряд:
    статус, старый путь, новый), не по табуляциям: путь с пробелом или
    кавычкой в обычном выводе экранируется кавычками, и табуляционный
    разбор отдал бы искажённое имя.
    """
    args = ("diff", "-M", "--name-status", "-z", a, b, "--", *paths)
    res = in_repo(repo, *args) if repo else git(*args)
    if res is None or res.returncode != 0:
        return None
    fields = [f for f in res.stdout.split("\0") if f]
    entries: list[tuple] = []
    i = 0
    while i < len(fields):
        status = fields[i]
        if status[:1] in ("R", "C"):
            if i + 2 >= len(fields):
                break
            entries.append((status, fields[i + 1], fields[i + 2]))
            i += 3
            continue
        if i + 1 >= len(fields):
            break
        entries.append((status, fields[i + 1], None))
        i += 2
    return entries


def diff_paths(a: str, b: str, *paths: str,
               repo: Path | None = None) -> bool | None:
    """True — ревизии `a` и `b` расходятся по путям; None — git не ответил.

    `git diff --quiet` кодирует ответ кодом возврата (0 — совпадают,
    1 — расходятся), не выводом: достаточно для проверки лока
    acceptance_tests/ (orchestrator/fsm.py, tasks/T023, требование 5)
    без парсинга самого диффа. Тот же вырожденный случай «git не ответил»,
    что у `head_sha`: заглушка `gitcmd.git = lambda *a: None`
    в тестах, не связанных с git, возвращает `None` тем же приёмом.
    """
    args = ("diff", "--quiet", a, b, "--", *paths)
    res = in_repo(repo, *args) if repo else git(*args)
    if res is None or res.returncode not in (0, 1):
        return None
    return res.returncode == 1


def _origin_main_ref_exists(repo: Path | None = None) -> bool | None:
    """`refs/remotes/origin/<MAIN_BRANCH>` заведён в репозитории; `None` —
    git не ответил на саму проверку. Только чтение уже существующего
    локального ref — без `fetch`/`ls-remote`, никаких сетевых обращений
    (тесты не выходят в сеть, 01M1QHQ277…): ref обновляется механикой
    подтяжки и входа в `verifying`, эта функция его не актуализирует."""
    args = ("rev-parse", "--verify", "--quiet",
           f"refs/remotes/origin/{config.MAIN_BRANCH}")
    res = in_repo(repo, *args) if repo else git(*args)
    return None if res is None else res.returncode == 0


def diff_base(branch: str, repo: Path | None = None) -> str | None:
    """Одна точка правды для базы сравнения ветки задачи (tasks/
    01M1SG9T962WJJ31S282GWM0EN): merge-base `branch` с `refs/remotes/
    origin/<MAIN_BRANCH>`, если такой ref есть в репозитории; иначе —
    merge-base с локальным `config.MAIN_BRANCH`. Замена двухточечного
    сравнения с локальным `config.MAIN_BRANCH` целиком (гейт зон) и
    трёхточечного, но с той же устаревшей базой (гейт ёмкости, полный
    diff ревью-пакета) — локальный пин по построению отстаёт от
    `origin/main`, которую ветка задачи как раз подтягивает: точка
    расхождения с локальным main старее и тащит в дифф чужие коммиты.

    `None` — git не ответил ни на проверку существования ref, ни на саму
    команду `merge-base`: вызывающий код обязан отказать fail-closed
    (ADR-0002), не подставлять `None` дальше как базу diff'а.

    `repo` (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, AC-10) — клон, в котором
    считается merge-base, не всегда `config.ROOT`. `None` (по умолчанию)
    — прежнее поведение байт-в-байт.
    """
    exists = _origin_main_ref_exists(repo)
    if exists is None:
        return None
    base_ref = (f"refs/remotes/origin/{config.MAIN_BRANCH}" if exists
               else config.MAIN_BRANCH)
    args = ("merge-base", base_ref, branch)
    res = in_repo(repo, *args) if repo else git(*args)
    if res is None or res.returncode != 0:
        return None
    return res.stdout.strip()


def diff_base_source(branch: str, repo: Path | None = None) -> str:
    """Название источника базы `diff_base(branch)` для журнала: `"origin/
    <MAIN_BRANCH>"` — ref заведён и был использован; иначе — локальный
    `config.MAIN_BRANCH` (tasks/01M1SG9T962WJJ31S282GWM0EN, требование 4:
    отказы гейтов зон/ёмкости обязаны называть, откуда взята база, не
    только её sha). Не зовёт `diff_base` повторно и не переиспользует её
    результат — только независимо повторяет тот же критерий наличия ref;
    git не ответивший на эту проверку — локальный `config.MAIN_BRANCH` тем
    же вырожденным откатом, что и у `diff_base` в этом случае (вызывающий
    код сюда доходит только когда `diff_base` уже вернула не-`None` базу,
    так что расхождение возможно только при флапе git между двумя
    вызовами). `repo` — тот же клон, что уже передан `diff_base` (AC-10)."""
    return (f"origin/{config.MAIN_BRANCH}" if _origin_main_ref_exists(repo)
           else config.MAIN_BRANCH)


def has_no_remote(repo: Path) -> bool:
    """True — `git remote` пуст: ни одной записи (ADR-0003 3д, требование 7).

    Потребитель — doctor (A3); здесь только сама проверка.
    """
    res = in_repo(repo, "remote")
    return res is not None and res.returncode == 0 and not res.stdout.strip()


# --------------------------------------------------------------------------
# Ветко-корректные чтения артефактов задачи (SPEC T031): источник истины —
# ВЕТКА задачи, не рабочая копия пульта, которую чужой checkout (журнал
# T030, ~17:35 25.08.2026) может подменить у оркестратора под ногами.

def branch_head_sha(branch: str, repo: Path | None = None) -> str:
    """sha головы `branch` независимо от текущего чекаута; пустая строка —
    ветки нет в git или он не ответил (`res is None` — тот же вырожденный
    случай заглушек `gitcmd.git`, что у `head_sha`).

    `repo` (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, AC-6) — клон, в котором
    читается голова, не всегда `config.ROOT`. `None` (по умолчанию) —
    прежнее поведение байт-в-байт."""
    args = ("rev-parse", "--verify", "--quiet", qualified_ref(branch))
    res = in_repo(repo, *args) if repo else git(*args)
    return res.stdout.strip() if res is not None and res.returncode == 0 else ""


def on_foreign_branch(branch: str, repo: Path | None = None) -> bool:
    """True — рабочее дерево ТОЧНО стоит не на `branch`, и `branch` реально
    существует в git: единственный случай, когда чтение с ВЕТКИ задачи
    безопасно и осмысленно предпочесть рабочей копии (SPEC T031).

    Иначе (своя ветка и так выписана; ветка ещё не создана ролью — легитимный
    ранний момент жизни задачи до первого `git checkout -b`, ADR-0003 3д;
    git не ответил на сам вопрос «какая ветка сейчас») — прежнее поведение,
    рабочая копия: вырожденный случай, на котором стоял весь стенд
    заглушек `gitcmd.git` до этой задачи, остаётся вырожденным и после неё.
    """
    current = current_branch(repo)
    return bool(branch and current and current != branch
               and branch_exists(branch, repo))


def show(branch: str, rel: str, *,
         repo: Path | None = None) -> tuple[str | None, str]:
    """(текст, "") — файл `rel` из `branch`; (None, причина) — файла там
    нет, или git не ответил.

    Не путать с `review.artifact_text`: та ещё откатывается на рабочее
    дерево, если файла в ветке нет (законно для ревью WIP-diff'а, T011);
    здесь ветка — источник истины БЕЗ отката на дерево (SPEC T031,
    AC-1/AC-2) — откат на прежнее поведение делает вызывающий код через
    `on_foreign_branch`, а не эта функция молча.

    `repo` — репозиторий, в котором живёт `branch` (ссылка документов
    задачи внешнего проекта — в клоне проекта, ADR-0021 п.3); `None` —
    `config.ROOT`, прежнее поведение байт-в-байт.
    """
    args = ("show", f"{branch}:{rel}")
    try:
        res = in_repo(repo, *args) if repo else git(*args)
    except UnicodeDecodeError as exc:
        # git отдаёт байты файла как есть; strict-декодирование внутри
        # subprocess роняло бы всю команду трейсбеком (тот же приём, что
        # у review.artifact_text, T011 ревью 2).
        return None, f"не прочитан: {exc}"
    if res is None:
        return None, "git не ответил"
    if res.returncode == 0:
        return res.stdout, ""
    return None, res.stderr.strip()[:200] or f"git show вернул {res.returncode}"


def remote_branch_sha(branch: str, repo: Path | None = None) -> str:
    """sha `branch` в `origin`; пустая строка — там такой ветки нет (ещё не
    публиковалась, либо разошлась по имени) или git не ответил.

    Адресуется полным `refs/heads/<branch>`, не голым именем ветки (SPEC
    01M1GS5HZ1JXFGKVR95HEW0AEZ, AC-2): `git ls-remote origin <branch>`
    неполным именем мог бы зацепить одноимённый тег — здесь сверяется
    именно голова ветки-задачи.

    `repo` (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, AC-6) — клон, чей `origin`
    опрашивается, не всегда `config.ROOT`. `None` (по умолчанию) —
    прежнее поведение байт-в-байт.
    """
    args = ("ls-remote", "origin", qualified_ref(branch))
    res = in_repo(repo, *args) if repo else git(*args)
    if res is None or res.returncode != 0 or not res.stdout.strip():
        return ""
    return res.stdout.split()[0]


def remote_ref_state(ref: str, repo: Path | None = None) -> tuple[str, str]:
    """(sha, "") — голова `ref` в `origin` пульта (или клона `repo`, если
    задан); ("", "") — в `origin` такой ссылки нет; ("", причина) —
    `origin` не ответил. В отличие от `remote_branch_sha`, «ссылки нет» и
    «спросить не удалось» здесь различимы: сверка ссылки документов с
    `origin` (ADR-0021 п.3) обязана отказывать и там, и там, но называть
    разное."""
    args = ("ls-remote", "origin", qualified_ref(ref))
    res = in_repo(repo, *args) if repo else git(*args)
    if res is None:
        return "", "git не ответил"
    if res.returncode != 0:
        return "", (res.stderr or "").strip()[:200] or "ls-remote не удался"
    out = res.stdout.split()
    return (out[0] if out else ""), ""


def fetch_ref_sha(remote: str, ref: str, *,
                  repo: Path | None = None,
                  tracking_refs: bool = True) -> tuple[str, str]:
    """(sha, "") — голова ветки `ref` в `remote` через ВРЕМЕННУЮ приватную
    ссылку `refs/artel/fetch/<pid>-<uuid>` (SPEC
    01M2ARQGY51B99YNP9PY806AN1, AC-1/AC-2/AC-3): `git fetch <remote>
    +refs/heads/<ref>:refs/artel/fetch/<pid>-<uuid>`, затем `git rev-parse
    --verify` этой ссылки — БЕЗ единого обращения к `FETCH_HEAD`.

    Общий `FETCH_HEAD` — один файл на репозиторий (приватный на worktree
    начиная с git 2.5, но всё равно общий для всех шагов, исполняемых В
    ТОМ ЖЕ рабочем дереве/`config.ROOT`): параллельный шаг ДРУГОЙ задачи
    в том же репозитории (push/fetch артефактной ветки) мог переписать
    его МЕЖДУ нашими собственными `fetch` и чтением результата (инцидент
    12.09 07:15Z, канарейка 01M2A22CG2: merge-коммит 9a7f06c4 принёс
    голову ЧУЖОЙ артефактной ветки вместо `origin/main`). Приватная
    ссылка своя у каждого вызова (`<pid>-<uuid>` в имени) — гонки на
    общем файле нет ни при каком совпадении по времени с другим шагом,
    а объекты фетча при этом реально попадают в объектную базу (то, ради
    чего вызывающему коду вообще нужен fetch, а не голый `ls-remote`).

    ("", причина) — `remote`/`ref` недоступны, или git не ответил на
    любой из шагов; причина — первые 200 символов stderr (тот же приём,
    что у `show`/`drop`). Приватная ссылка убирается (`git update-ref
    -d`) и на успех, и на отказ `rev-parse` (`finally`, AC-2) —
    единственный случай, когда убирать нечего, это отказ самого `fetch`
    (ссылка тогда ещё не создана).

    `repo` (по образцу `in_repo`) — клон, в котором идёт ВЕСЬ git-трафик
    примитива (`in_repo`, не голый `git`); `None` (по умолчанию) —
    `config.ROOT`.

    `tracking_refs=False` (SPEC 01M42NBCADGSGTCBZB8NKBVDVH, требование 2)
    — `--refmap=`: git не обновляет попутно ссылку отслеживания
    `refs/remotes/<remote>/<ref>` (по имени remote он делает это даже при
    явной refspec), и чужая блокировка этой ссылки — параллельный push
    `note` в ту же секунду, инцидент 03.10 22:54Z, «cannot lock ref» — не
    роняет fetch. По умолчанию — прежнее поведение для остальных вызовов.
    """
    private_ref = f"refs/artel/fetch/{os.getpid()}-{uuid.uuid4().hex}"
    refspec = f"+refs/heads/{ref}:{private_ref}"
    refmap = () if tracking_refs else ("--refmap=",)
    fetch_args = ("fetch", *refmap, remote, refspec)
    fetch = in_repo(repo, *fetch_args) if repo else git(*fetch_args)
    if fetch is None:
        return "", "git не ответил"
    if fetch.returncode != 0:
        return "", (fetch.stderr.strip()[:200] or "git fetch вернул ненулевой код")
    try:
        verify_args = ("rev-parse", "--verify", private_ref)
        res = in_repo(repo, *verify_args) if repo else git(*verify_args)
        if res is None:
            return "", "git не ответил"
        if res.returncode != 0 or not res.stdout.strip():
            return "", (res.stderr.strip()[:200] or "приватная ссылка не разрешилась")
        return res.stdout.strip(), ""
    finally:
        delete_args = ("update-ref", "-d", private_ref)
        in_repo(repo, *delete_args) if repo else git(*delete_args)


def fetch_head_sha(remote: str, ref: str,
                   repo: Path | None = None) -> tuple[str, str]:
    """(sha, "") — голова `ref` в `remote`, через `fetch_ref_sha` (SPEC
    01M2ARQGY51B99YNP9PY806AN1): приватная ссылка `refs/artel/fetch/
    <pid>-<uuid>`, БЕЗ обращения к `FETCH_HEAD` (до этой задачи здесь
    стоял отдельный `git rev-parse ... FETCH_HEAD` — общий на репозиторий
    файл, который параллельный шаг другой задачи мог переписать между
    нашими fetch и чтением результата, инцидент 12.09 07:15Z). `git
    fetch` не трогает HEAD и рабочее дерево ни при каком исходе — HEAD
    главной копии остаётся на месте. ("", причина) — `remote` недоступен
    (нет сети, `remote` не настроен, песочница) или git не ответил;
    причина — первые 200 символов stderr.

    Не `ls_remote`/`remote_branch_sha` (голый sha без объектов): вызывающему
    коду (`artifact_branch`, `workspace`) нужен РЕАЛЬНО присутствующий
    локально коммит — родитель плотницкой записи (`write_commit`, `read-tree
    parent`) обязан существовать в объектной базе, не только числиться sha
    на удалённой стороне.
    """
    return fetch_ref_sha(remote, ref, repo=repo)


def ls_tree_files(branch: str, rel_dir: str, *,
                  repo: Path | None = None) -> list[str] | None:
    """Пути файлов под `rel_dir` в дереве `branch`; None — git не ответил.

    Пустой список — легитимный ответ (ветка есть, каталога в ней нет —
    тот же вырожденный случай, что у `guard.scan_acceptance_tests` для
    отсутствующей `acceptance_tests/` на диске), не путать с `None`.
    `repo` — как у `show`.
    """
    args = ("ls-tree", "-r", "--name-only", branch, "--", rel_dir)
    res = in_repo(repo, *args) if repo else git(*args)
    if res is None or res.returncode != 0:
        return None
    return [p for p in res.stdout.splitlines() if p]
