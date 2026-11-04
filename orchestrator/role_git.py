"""Граница git роли: отказ git в репозитории пульта и в чужой задаче, отказ
`git clean` (SPEC 01M6JJ4J4NBV2Y1Q4XHE3C3FVT, требования 2, 3, 10).

Исполняется обёрткой `orchestrator/role_bin/git`, которую `runner.role_env`
ставит в PATH роли сразу после `.artel/venv/bin`: каждый прямой вызов git
шага роли проходит здесь до настоящего git. Вызов, который не отклонён,
исполняется настоящим git (первый `git` по PATH после каталога обёртки) с
теми же аргументами и окружением.

Защищаемые корни — объединение корня от расположения обёртки
(`orchestrator/role_bin/../..`) и корня из `ARTEL_GIT_GUARD_ROOT`, если он
задан (требование 10): переменная только добавляет корень, снять защиту с
корня обёртки нельзя. Переменной-выключателя нет (требование 5): механизм
снимает только диспетчер `artel.py`, убирая каталог обёртки из PATH своих
дочерних процессов.

Свою и чужие рабочие копии механизм выводит из корня без БД:
`<корень>/.artel/projects/<проект>/worktrees/<ARTEL_TASK>` — своя, прочие
каталоги там же — чужие; клон проекта своей копии
(`<корень>/.artel/projects/<проект>/repo`) — свой.

Только стандартная библиотека и без импорта пакета `orchestrator`: модуль
исполняется отдельным интерпретатором на каждый вызов git роли, и пакет
обёртки (`role_bin/` и этот файл) обязан работать сам по себе — так его
проверяет приёмка, скопировав в дублёр пульта. Поэтому перечни опций и
встроенных подкоманд git — копии из `orchestrator/gitcmd.py`, не импорт.

Модель угрозы — ошибочная команда роли, не намеренный обход: абсолютный путь
к git и произвольный интерпретатор идут мимо (`docs/stack.md`, «Паритет
безопасности роли»).
"""
import os
import re
import shlex
import subprocess
import sys

GUARD_ROOT_ENV = "ARTEL_GIT_GUARD_ROOT"
TASK_ENV = "ARTEL_TASK"
REFUSAL_EXIT = 1
CONFIG_TIMEOUT_SEC = 30

# Глобальные опции git со значением отдельным словом (`gitcmd.
# GIT_GLOBALS_WITH_VALUE` плюс `--attr-source` git 2.4x).
WITH_VALUE = ("-C", "-c", "--git-dir", "--work-tree", "--namespace",
              "--config-env", "--super-prefix", "--attr-source")
# Опции и подкоманды, не обращающиеся к репозиторию: проходят при любом
# текущем каталоге (решение Оператора, возврат 10).
INFO_OPTIONS = ("--version", "-v", "--help", "-h", "--html-path",
                "--man-path", "--info-path", "--exec-path")
INFO_COMMANDS = ("version", "help")
# Встроенные подкоманды: псевдоним их не перекрывает (`gitcmd.GIT_BUILTINS`).
BUILTINS = frozenset((
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
# Значение, вызывающее git как команду: `git …`, `/usr/bin/git …`, `git-clean`.
# Вложенный git из pager, fsmonitor или `!`-псевдонима идёт мимо обёртки:
# git ставит свой exec-path первым в PATH дочерних процессов.
GIT_CALL = re.compile(r"(?:^|[\s;&|`(/=\"'])git(?:[\s\-;&|)\"']|$)")
# Ключи, значение которых git исполняет как команду оболочки.
COMMAND_KEYS = ("core.pager", "core.fsmonitor")
COMMAND_ENV = ("GIT_PAGER", "PAGER")


def _inside(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def real_git(wrapper_dir: str) -> str | None:
    """Первый `git` по PATH, не лежащий в каталоге обёртки."""
    for item in os.environ.get("PATH", "").split(os.pathsep):
        if not item or os.path.realpath(item) == wrapper_dir:
            continue
        candidate = os.path.join(item, "git")
        if (os.path.isfile(candidate) and os.access(candidate, os.X_OK)
                and os.path.realpath(candidate)
                != os.path.join(wrapper_dir, "git")):
            return candidate
    return None


def protected_roots(wrapper_dir: str) -> list[str]:
    """Корень от расположения обёртки и модуля плюс корень из переменной."""
    roots = [os.path.realpath(os.path.join(wrapper_dir, os.pardir, os.pardir)),
             os.path.realpath(os.path.join(os.path.dirname(
                 os.path.abspath(__file__)), os.pardir))]
    extra = os.environ.get(GUARD_ROOT_ENV)
    if extra:
        roots.append(os.path.realpath(extra))
    unique = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return unique


def parse(args: list) -> tuple[list, int]:
    """([(опция, значение | None)…], индекс подкоманды) — разбор глобальных
    опций git до первого слова, не начинающегося с `-`."""
    opts = []
    i = 0
    while i < len(args):
        arg = args[i]
        if not arg.startswith("-"):
            break
        if arg in WITH_VALUE:
            opts.append((arg, args[i + 1] if i + 1 < len(args) else None))
            i += 2
            continue
        name, eq, value = arg.partition("=")
        opts.append((name, value) if eq else (arg, None))
        i += 1
    return opts, i


def informational(opts: list, args: list, idx: int) -> bool:
    """Вызов, не обращающийся к репозиторию: `--version`, `help`, справка
    без подкоманды, `--exec-path` без значения, `--list-cmds`."""
    for name, value in opts:
        if name in INFO_OPTIONS and value is None:
            return True
        if name == "--list-cmds":
            return True
    return idx >= len(args) or args[idx] in INFO_COMMANDS


def option_config(opts: list) -> list:
    """[(ключ, значение)…] из опций `-c` и `--config-env` разбора `parse`."""
    entries = []
    for name, value in opts:
        if value is None:
            continue
        if name == "-c":
            key, _eq, val = value.partition("=")
            entries.append((key.lower(), val))
        elif name == "--config-env":
            key, _eq, var = value.partition("=")
            entries.append((key.lower(), os.environ.get(var, "")))
    return entries


def command_line_config(opts: list) -> list:
    """[(ключ, значение)…] конфигурации из командной строки и окружения:
    `-c`, `--config-env`, `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_COUNT`."""
    entries = option_config(opts)
    try:
        for token in shlex.split(os.environ.get("GIT_CONFIG_PARAMETERS", "")):
            key, _eq, val = token.partition("=")
            entries.append((key.lower(), val))
    except ValueError:
        pass
    try:
        count = int(os.environ.get("GIT_CONFIG_COUNT", "0") or "0")
    except ValueError:
        count = 0
    for n in range(max(count, 0)):
        key = os.environ.get(f"GIT_CONFIG_KEY_{n}")
        if key is not None:
            entries.append((key.lower(), os.environ.get(f"GIT_CONFIG_VALUE_{n}", "")))
    return entries


def repo_paths(opts: list, cmdline: list) -> list:
    """Пути, задающие репозиторий или рабочее дерево вызова: текущий
    каталог после всех `-C` (каждый относительный — от предыдущего, как
    `chdir` у git), `--git-dir`/`GIT_DIR`, `--work-tree`/`GIT_WORK_TREE`,
    `core.worktree` из командной строки — все после `realpath`."""
    cur = os.path.realpath(os.getcwd())
    for name, value in opts:
        if name == "-C" and value:
            cur = os.path.realpath(os.path.join(cur, value))
    paths = [cur]
    named = {"--git-dir": os.environ.get("GIT_DIR"),
             "--work-tree": os.environ.get("GIT_WORK_TREE")}
    for name, value in opts:
        if name in named and value is not None:
            named[name] = value
    extra = [v for v in named.values() if v]
    extra += [v for k, v in cmdline if k == "core.worktree" and v]
    for value in extra:
        paths.append(os.path.realpath(os.path.join(cur, value)))
    return paths


def classify(path: str, roots: list, task: str | None) -> tuple[str, str]:
    """(вид, место): "foreign" — внутри рабочей копии другой задачи, "pult" —
    прочее внутри защищаемого корня, "own" — своя рабочая копия или клон её
    проекта, "outside" — вне корней. Из нескольких корней — худший вид."""
    rank = {"outside": 0, "own": 1, "pult": 2, "foreign": 3}
    verdict = ("outside", "")
    for root in roots:
        found = _classify_in(path, root, task)
        if rank[found[0]] > rank[verdict[0]]:
            verdict = found
    return verdict


def _classify_in(path: str, root: str, task: str | None) -> tuple[str, str]:
    if not _inside(path, root):
        return ("outside", "")
    projects = os.path.join(root, ".artel", "projects")
    if _inside(path, projects) and path != projects:
        parts = os.path.relpath(path, projects).split(os.sep)
        if len(parts) >= 3 and parts[1] == "worktrees":
            copy = os.path.join(projects, *parts[:3])
            return ("own", copy) if task and parts[2] == task else ("foreign", copy)
        if (len(parts) >= 2 and parts[1] == "repo" and task and os.path.isdir(
                os.path.join(projects, parts[0], "worktrees", task))):
            return ("own", os.path.join(projects, parts[0], "repo"))
    return ("pult", root)


def read_config(git: str, globals_: list) -> list | None:
    """[(ключ, значение)…] действующей конфигурации вызова — все источники,
    которые читает git (файлы, в том числе `config.worktree` рабочей копии,
    `-c`, `--config-env`, `GIT_CONFIG_*`); `None` — git не ответил."""
    try:
        res = subprocess.run([git, *globals_, "--no-pager", "config", "--list", "-z"],
                             stdin=subprocess.DEVNULL, capture_output=True,
                             timeout=CONFIG_TIMEOUT_SEC)
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    entries = []
    for record in res.stdout.decode("utf-8", "replace").split("\0"):
        if not record:
            continue
        key, _nl, value = record.partition("\n")
        entries.append((key.lower(), value))
    return entries


def _alias_refusal(sub: str, config: list) -> str | None:
    """Причина отказа по псевдониму: `!`-псевдоним, раскрытие в `clean`
    или тело, задающее `-c`/`--config-env` pager, fsmonitor или
    `core.worktree`.

    Тело псевдонима git разбирает как глобальные опции перед подкомандой и
    допускает в нём `-c`/`--config-env`: значение опции — не подкоманда
    (`cl = -c a.b=c clean`), а заданная там конфигурация в `git config
    --list` вызова не видна — её проверяет разбор тела."""
    aliases = {}
    for key, value in config:
        if key.startswith("alias."):
            aliases[key[len("alias."):]] = value
    word, seen = sub, set()
    while True:
        if word == "clean":
            return (f"псевдоним `{sub}` раскрывается в `git clean`" if word != sub
                    else "`git clean`")
        if word in BUILTINS or word in seen:
            return None
        value = aliases.get(word.lower())
        if value is None:
            return None
        if value.startswith("!"):
            return (f"псевдоним `{word}` исполняет команду оболочки (`!…`): "
                    f"вложенный git из неё идёт мимо границы git роли")
        seen.add(word)
        try:
            words = shlex.split(value)
        except ValueError:
            return None
        opts, idx = parse(words)
        body = option_config(opts)
        reason = _command_refusal(body)
        if reason is not None:
            return f"псевдоним `{word}`: {reason}"
        for key, value in body:
            if key == "core.worktree":
                return (f"псевдоним `{word}` задаёт `core.worktree` — рабочее "
                        f"дерево вне проверки границы git роли")
            if key.startswith("alias."):
                aliases[key[len("alias."):]] = value
        if idx >= len(words):
            return None
        word = words[idx]


def _command_refusal(config: list) -> str | None:
    """Причина отказа по pager/fsmonitor, значение которых вызывает git."""
    for key, value in config:
        if (key in COMMAND_KEYS or key.startswith("pager.")) and GIT_CALL.search(value):
            return (f"`{key}` = «{value}» вызывает git: вложенный git идёт "
                    f"мимо границы git роли")
    for name in COMMAND_ENV:
        value = os.environ.get(name, "")
        if GIT_CALL.search(value):
            return (f"`{name}` = «{value}» вызывает git: вложенный git идёт "
                    f"мимо границы git роли")
    return None


def _task_rm_hint(wrapper_dir: str, task: str | None) -> str:
    artel = os.path.join(os.path.dirname(wrapper_dir), "artel.py")
    return (f"убрать свой файл — командой пульта `python3 {artel} task-rm "
            f"{task or '<id>'} <путь>…`")


def _refuse(text: str) -> int:
    sys.stderr.write(f"git роли: отказ — {text}\n")
    return REFUSAL_EXIT


def main(argv: list) -> int:
    if len(argv) < 2:
        return _refuse("обёртка запущена без своего каталога")
    wrapper_dir = os.path.realpath(argv[1])
    args = argv[2:]
    git = real_git(wrapper_dir)
    if git is None:
        sys.stderr.write("git роли: настоящий git не найден в PATH после обёртки\n")
        return 127
    opts, idx = parse(args)
    if informational(opts, args, idx):
        os.execv(git, [git, *args])
    task = os.environ.get(TASK_ENV) or None
    roots = protected_roots(wrapper_dir)
    hint = _task_rm_hint(wrapper_dir, task)
    cmdline = command_line_config(opts)
    verdicts = [(path, *classify(path, roots, task))
                for path in repo_paths(opts, cmdline)]
    for path, kind, place in verdicts:
        if kind == "foreign":
            return _refuse(f"рабочая копия другой задачи: {path} лежит в "
                           f"{place}; git роли работает только в своей "
                           f"рабочей копии")
    for path, kind, place in verdicts:
        if kind == "pult":
            return _refuse(f"{path} лежит внутри корня пульта {place}: "
                           f"репозиторий пульта и его каталоги git роли "
                           f"недоступны ({hint})")
    if not any(kind == "own" for _path, kind, _place in verdicts):
        os.execv(git, [git, *args])
    # Репозиторий вызова — своя рабочая копия или клон её проекта внутри
    # корня пульта: дальше отказ `git clean` и его обходных форм.
    sub = args[idx]
    if sub == "clean":
        return _refuse(f"`git clean` в репозитории внутри пульта недоступен "
                       f"роли: он удаляет файлы мимо границ задачи ({hint})")
    config = read_config(git, args[:idx])
    if config is None:
        return _refuse(f"конфигурация git вызова не прочитана — механизм не "
                       f"может проверить псевдонимы, pager и fsmonitor ({hint})")
    for key, value in config:
        if key == "core.worktree" and os.path.isabs(value):
            kind, place = classify(os.path.realpath(value), roots, task)
            if kind in ("pult", "foreign"):
                return _refuse(f"core.worktree {value} лежит вне своей рабочей "
                               f"копии ({place}) ({hint})")
    reason = _command_refusal(config) or _alias_refusal(sub, config)
    if reason is not None:
        return _refuse(f"{reason} ({hint})")
    # Исправление опечатки (`help.autocorrect`) исполнило бы `clean` вместо
    # `claen` мимо проверки подкоманды выше.
    os.execv(git, [git, *args[:idx], "-c", "help.autocorrect=0", *args[idx:]])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
