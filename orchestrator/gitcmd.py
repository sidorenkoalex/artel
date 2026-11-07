"""Вызовы git в корне репозитория, вопросы к ветке задачи и к произвольному
репозиторию (артефактные git-репо внешних target, ADR-0003 3д, tasks/T021)."""
import os
import posixpath
import re
import shlex
import sqlite3
import subprocess
import tempfile
import threading
import time
import urllib.parse
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
HOSTING_SUBCOMMANDS = ("fetch", "push", "pull", "ls-remote", "clone")
HOSTING_TOKEN_ENV = "ARTEL_HOSTING_TOKEN"
# Хост адреса записи проекта (SPEC 01M6EZXVFGCHB1S4W45AWJ0QH6, требование
# 11): помощник отдаёт пароль только на запрос `get` с этим `host` —
# подмодуль на другом хосте токена слота не получает. Пустое значение
# (адрес-путь, `file://`) совпадает только с запросом без `host`.
HOSTING_HOST_ENV = "ARTEL_HOSTING_HOST"
# Помощник читает пароль из окружения, а не из своего текста: значение
# токена не попадает ни в argv git, ни в argv помощника (`GIT_TRACE`).
HOSTING_CREDENTIAL_HELPER = (
    '!f() { test "$1" = get || exit 0; h=; while IFS= read -r l; do '
    'case "$l" in host=*) h="${l#host=}";; esac; done; '
    f'test "$h" = "${{{HOSTING_HOST_ENV}}}" || exit 0; '
    'echo username=x-access-token; '
    f'echo "password=${{{HOSTING_TOKEN_ENV}}}"; }}; f')
# Выбор токена по адресу (SPEC 01M6P1Z0ZHVNDYWN3FZSZWBCG3, требования 2-3):
# только для записи с `submodule_tokens`. Помощник видит путь запроса
# (`credential.useHttpPath=true`), снимает с него `/` и `.git` и ищет среди
# `ARTEL_HOSTING_SUB_PATH_n`: совпал — токен `ARTEL_HOSTING_SUB_TOKEN_n`
# (пустой — ничего, не токен проекта), не совпал — токен проекта. Хост
# сравнивается без учёта регистра: `ARTEL_HOSTING_HOST` здесь — в нижнем
# регистре. `eval` раскрывает только имя переменной с номером — значения
# путей и токенов через него не проходят.
HOSTING_SUB_COUNT_ENV = "ARTEL_HOSTING_SUB_COUNT"
HOSTING_SUB_PATH_ENV = "ARTEL_HOSTING_SUB_PATH_"
HOSTING_SUB_TOKEN_ENV = "ARTEL_HOSTING_SUB_TOKEN_"
HOSTING_PATH_CREDENTIAL_HELPER = (
    '!f() { test "$1" = get || exit 0; h=; p=; while IFS= read -r l; do '
    'case "$l" in host=*) h="${l#host=}";; path=*) p="${l#path=}";; esac; '
    "done; h=$(printf '%s' \"$h\" | tr '[:upper:]' '[:lower:]'); "
    f'test "$h" = "${{{HOSTING_HOST_ENV}}}" || exit 0; '
    'p="${p%/}"; p="${p%.git}"; i=0; '
    f'while test "$i" -lt "${{{HOSTING_SUB_COUNT_ENV}:-0}}"; do '
    f'eval "s=\\${{{HOSTING_SUB_PATH_ENV}$i}}"; '
    f'if test "$p" = "$s"; then eval "t=\\${{{HOSTING_SUB_TOKEN_ENV}$i}}"; '
    'test -n "$t" || exit 0; echo username=x-access-token; '
    'echo "password=$t"; exit 0; fi; i=$((i+1)); done; '
    'echo username=x-access-token; '
    f'echo "password=${{{HOSTING_TOKEN_ENV}}}"; }}; f')


def url_host(url: str) -> str:
    """`host` адреса `url` в том виде, в каком его называет запрос git к
    помощнику учётных данных: с портом, без учётной части; адрес-путь и
    `file://` — пустая строка (ANSWER-1 п. 2)."""
    url = url.strip()
    if "://" in url:
        if url.lower().startswith("file://"):
            return ""
        return urllib.parse.urlsplit(url).netloc.rpartition("@")[2]
    head, colon, _rest = url.partition(":")
    if colon and "/" not in head:
        return head.rpartition("@")[2]
    return ""


def url_key(url: str) -> str:
    """Адрес remote для сравнения: без завершающей черты и `.git`."""
    return url.strip().rstrip("/").removesuffix(".git")


def gitmodules_entries(text: str) -> list:
    """[(путь, адрес)] подмодулей текста `.gitmodules`."""
    sections: dict = {}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        m = re.match(r'^\[submodule\s+"(.+)"\]$', line)
        if m:
            current = sections.setdefault(m.group(1), {})
        elif line.startswith("["):
            current = None
        elif current is not None and "=" in line:
            key, value = line.split("=", 1)
            current[key.strip().lower()] = value.strip().strip('"')
    return [(fields.get("path", name), fields["url"])
            for name, fields in sections.items() if fields.get("url")]


SCP_URL_RE = re.compile(r"^((?:[^@/:\s]+@)?([^/:\s]+)):(.*)$")


def resolve_submodule_url(url: str, base: str) -> str:
    """Относительный адрес `./…`/`../…` — от адреса записи, как у git."""
    if not url.startswith(("./", "../")):
        return url
    base = base.rstrip("/")
    if "://" in base:
        parts = urllib.parse.urlsplit(base)
        path = posixpath.normpath(posixpath.join(parts.path or "/", url))
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, "", ""))
    m = SCP_URL_RE.match(base)
    if m:
        path = posixpath.normpath(posixpath.join("/" + m.group(3), url)).lstrip("/")
        return f"{m.group(1)}:{path}"
    return url


def submodule_scheme(url: str) -> str:
    """Схема адреса подмодуля в нижнем регистре; вид scp — `ssh`; адрес
    без схемы — пустая строка."""
    if "://" in url:
        return urllib.parse.urlsplit(url).scheme.lower()
    return "ssh" if SCP_URL_RE.match(url) else ""


def same_host(url: str, base: str) -> bool:
    """`url` — на хосте адреса `base`: `url_host` (с портом), имя без учёта
    регистра (SPEC 01M6P1Z0ZHVNDYWN3FZSZWBCG3, требование 2)."""
    host = url_host(base).lower()
    return bool(host) and url_host(url).lower() == host


def clone_gitmodules(name: str) -> list | None:
    """[(путь, адрес)] `.gitmodules` клона проекта `name`; `None` — файла
    нет или он не читается."""
    from . import repo_context  # лениво: `repo_context` импортирует этот модуль
    path = repo_context.clone_path(name) / ".gitmodules"
    try:
        return gitmodules_entries(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def submodule_credentials(name: str, entry: dict) -> list:
    """[(путь подмодуля, слот, путь адреса без `.git`, токен)] подмодулей
    поля `submodule_tokens` записи `entry`, которым помощник выдаёт токен
    их слота (SPEC 01M6P1Z0ZHVNDYWN3FZSZWBCG3, требования 2, 4): путь есть в
    `.gitmodules` клона проекта, адрес (относительный — от `url` записи) —
    `http(s)://` на хосте записи. Прочим слот не читается. Токен пустого
    слота — пустая строка."""
    field = entry.get("submodule_tokens") or {}
    if not field:
        return []
    base = str(entry.get("url") or "")
    found = []
    for sub_path, raw in clone_gitmodules(name) or []:
        slot = field.get(sub_path)
        if not slot:
            continue
        address = resolve_submodule_url(raw, base)
        if (submodule_scheme(address) not in ("http", "https")
                or not same_host(address, base)):
            continue
        key = url_key(urllib.parse.urlsplit(address).path).lstrip("/")
        found.append((sub_path, slot, key, keychain.token(slot) or ""))
    return found


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
    if rest and rest[0] == "clone":
        return _clone_project(rest[1:])
    submodules = (len(rest) > 1 and rest[0] == "submodule"
                  and rest[1] == "update")
    if not rest or (rest[0] not in HOSTING_SUBCOMMANDS and not submodules):
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


def _clone_project(words: list) -> tuple | None:
    """(имя, запись) внешнего проекта со `token_slot`, чей `url` клонирует
    `git clone <words>` (SPEC 01M6EZXVFGCHB1S4W45AWJ0QH6, требование 10).
    Каталог клона ещё не в области проекта — проект узнаётся по адресу.
    Запись без `token_slot` — `None`: авторизация клона прежняя."""
    entries = _declared_targets()
    for word in words:
        if word.startswith("-"):
            continue
        found = project_by_url(word, entries)
        if found is not None:
            return found if found[1].get("token_slot") else None
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


def hosting_env(env: dict, token: str, host: str = "") -> dict:
    """Окружение хостингового git-вызова: чужие помощники сброшены пустым
    `credential.helper`, следом — помощник пульта (как `-c
    credential.helper= -c credential.helper=<пульт>`); конфигурация клона и
    `GIT_CONFIG_GLOBAL` не трогаются. `host` — хост адреса записи
    (`url_host`): только на него помощник отдаёт пароль."""
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
    env[HOSTING_HOST_ENV] = host
    return env


def hosting_path_env(env: dict, token: str, host: str, subs: list) -> dict:
    """Окружение хостингового git-вызова записи с `submodule_tokens`: как
    у `hosting_env`, но помощник выбирает токен по пути запроса
    (`HOSTING_PATH_CREDENTIAL_HELPER`, `credential.useHttpPath=true`).
    `subs` — `submodule_credentials` записи."""
    env = dict(env)
    try:
        count = int(env.get("GIT_CONFIG_COUNT") or 0)
    except ValueError:
        count = 0
    for key, value in (("credential.helper", ""),
                       ("credential.helper", HOSTING_PATH_CREDENTIAL_HELPER),
                       ("credential.useHttpPath", "true")):
        env[f"GIT_CONFIG_KEY_{count}"] = key
        env[f"GIT_CONFIG_VALUE_{count}"] = value
        count += 1
    env["GIT_CONFIG_COUNT"] = str(count)
    env[HOSTING_TOKEN_ENV] = token
    env[HOSTING_HOST_ENV] = host.lower()
    env[HOSTING_SUB_COUNT_ENV] = str(len(subs))
    for i, (_path, _slot, key, sub_token) in enumerate(subs):
        env[f"{HOSTING_SUB_PATH_ENV}{i}"] = key
        env[f"{HOSTING_SUB_TOKEN_ENV}{i}"] = sub_token
    return env


# Единая точка отправки (SPEC 01M5WDB7F14SQ30QVWJY2XYBG2, требование 3;
# ADR-0029 п. 13): через `_push_plan` проходят все пять точек запуска git
# модуля. Любая отправка ветки задачи — запись «ветка отправлена» и опции
# `policy.push_options`; проект под белым списком (`targets.push_whitelisted`)
# — проверка argv, окружения и конфигурации клона до запуска процесса.
# Запись читается как «ветка отправлена: <sha> <ветка>» (действие и
# `detail` подряд, SPEC 01M5WDB7JY0VJGHVKCABA2QC5T, требование 15); записи
# прежнего вида без двоеточия `_last_sent_sha` тоже читает.
PUSH_SENT_ACTION = "ветка отправлена:"
PUSH_SENT_LEGACY_ACTION = "ветка отправлена"
PUSH_REFUSED_ACTION = "отправка отказана"
# Причина отказа первой отправки пределом `policy.max_in_flight` (SPEC
# 01M5XZ9Z68XE2EKPDHYCAK25KF, требование 7): по ней `status` и черновой MR
# GitHub отличают штатную очередь от сбоя отправки.
IN_FLIGHT_LIMIT_REASON = "предел max_in_flight"
# Код возврата отказа пределом `max_in_flight` (SPEC
# 01M6EZXVFGXC6WBDA9QJESAZRW, требование 7): прочие отказы точки отправки
# несут 1, git — свои коды; 75 — EX_TEMPFAIL, «повтори позже».
IN_FLIGHT_REFUSAL = 75
PUSH_REFUSAL = 1
# Сбой чтения при проверке предела — не отказ пределом: текст без
# `IN_FLIGHT_LIMIT_REASON`, иначе `status` покажет сбой очередью.
IN_FLIGHT_UNCHECKED = "policy.max_in_flight не проверен"
DB_UNREAD = "БД пульта не прочитана"
PUSH_WHITELIST_SOURCE = "branch_push_whitelist"
PUSH_SUBCOMMANDS = ("push", "send-pack")
PUSH_RESET_CONFIG = ("-c", "push.followTags=false", "-c", "push.pushOption=")
PUSH_ALLOWED_FLAGS = ("-u", "--set-upstream", "-q", "--delete")
PUSH_LEASE_FLAG = "--force-with-lease"
ARTIFACT_REF_PREFIX = "refs/artifacts/"
GIT_CONFIG_ENV_NAMES = ("GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS")
GIT_CONFIG_ENV_PREFIXES = ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")
# Переменные, переносящие репозиторий вызова: под белым списком отправка
# идёт только из клона проекта рабочим каталогом.
GIT_LOCATION_ENV_NAMES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")
# Переменные, подменяющие транспорт или слои конфигурации вызова (SPEC
# 01M6EZXVFGCHB1S4W45AWJ0QH6, требование 12): под белым списком — отказ.
GIT_TRANSPORT_ENV_NAMES = ("GIT_SSH_COMMAND", "GIT_SSH", "GIT_CONFIG_GLOBAL",
                           "GIT_CONFIG_SYSTEM")
# Ключи действующей конфигурации, уводящие отправку мимо адреса записи или
# её транспорта (там же); имена — в каноническом виде `git config`.
PUSH_REDIRECT_CONFIG = r"^url\..*\.(insteadof|pushinsteadof)$|^core\.sshcommand$"
# Каталог хуков пульта проекта `target-human` под `<config.ROOT>/scripts/
# git-hooks` (требования 1, 6): его `pre-push` держит правила белого списка.
TARGET_HUMAN_HOOKS = "target-human"
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


def project_hooks_path(entry: dict | None) -> Path:
    """Каталог хуков пульта проекта с записью `entry` — абсолютный путь в
    главной копии пульта: у проекта `target-human` — свой каталог, у прочих
    проектов и артели (`entry` None) — прежний `<config.ROOT>/scripts/
    git-hooks`."""
    from . import targets
    path = Path(config.ROOT) / "scripts" / "git-hooks"
    if entry is not None and targets.merged_by_project_people(entry):
        return path / TARGET_HUMAN_HOOKS
    return path


PUSH_POLICY_NAME = "artel-push-policy"


def push_policy_text(project: str, entry: dict) -> str:
    """Эталон файла политики `pre-push` проекта `target-human` по записи
    `entry` (SPEC 01M6EZXVFGCHB1S4W45AWJ0QH6, «Термины»)."""
    from . import targets
    template = entry.get("branch_template") or targets.DEFAULT_BRANCH_TEMPLATE
    return (f"project={project}\nbase={entry.get('base') or ''}\n"
            f"branch_template={template}\n"
            f"artifacts_prefix={ARTIFACT_REF_PREFIX}\n")


def push_policy_path(cwd: Path) -> tuple[Path | None, str | None]:
    """(путь файла политики в общем каталоге git репозитория `cwd`,
    причина отказа)."""
    try:
        res = subprocess.run(["git", "-C", str(cwd), "rev-parse",
                              "--git-common-dir"],
                             capture_output=True, text=True, env=pult_env())
    except OSError as exc:
        return None, f"общий каталог git {cwd} не получен: {exc}"
    if res.returncode != 0 or not res.stdout.strip():
        detail = (res.stderr or "").strip()[:200] or "git вернул ненулевой код"
        return None, f"общий каталог git {cwd} не получен: {detail}"
    return Path(cwd) / res.stdout.strip() / PUSH_POLICY_NAME, None


def write_push_policy_file(path: Path, data: bytes) -> None:
    """Пишет файл политики, не идя по символической ссылке на его месте
    (REVIEW R3-F1): общий каталог git клона контролирует роль, и ссылка
    `artel-push-policy` → чужой файл иначе дала бы ей перезапись любого
    файла, доступного пульту. Временный файл того же каталога (`mkstemp` —
    `O_EXCL`, по ссылке не открывает) переименовывается на место пути:
    `os.replace` заменяет саму ссылку, а не её цель. Каталог на месте файла
    — `OSError`, как и прочие сбои записи."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _push_policy_refusal(project: str, entry: dict, cwd: Path) -> str | None:
    """Файл политики клона проекта `target-human` перед отправкой пульта
    (решение Оператора при возврате с приёмки): пульт перезаписывает его
    эталоном по записи — источнику истины, — затем читает обратно. Файл не
    записан или не читается (нет прав, на его месте каталог, общий каталог
    git не получен) — отказ до git с путём файла, а не только отказ хука.
    None — на диске эталон."""
    path, error = push_policy_path(cwd)
    if error is not None:
        return f"файл политики не найден — {error}"
    expected = push_policy_text(project, entry).encode("utf-8")
    try:
        write_push_policy_file(path, expected)
    except OSError as exc:
        return f"файл политики {path} не записан по записи проекта: {exc}"
    try:
        actual = path.read_bytes()
    except OSError as exc:
        return f"файл политики {path} не читается: {exc}"
    if actual != expected:
        return f"файл политики {path} не равен эталону по записи проекта"
    return None


def same_dir(value: str, expected: Path) -> bool:
    """Значение `core.hooksPath` — абсолютный путь каталога `expected`
    (временный каталог macOS живёт под `/private`, оттого сверка и по
    раскрытым ссылкам)."""
    if not os.path.isabs(value):
        return False
    return (os.path.abspath(value) == os.path.abspath(expected)
            or Path(value).resolve() == Path(expected).resolve())


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
    row = store.last_task_step_of(store.db(), task_id,
                                  (PUSH_SENT_ACTION, PUSH_SENT_LEGACY_ACTION))
    return (row["detail"] or "").split(" ")[0] if row is not None else None


def last_sent_sha(task_id: str) -> str | None:
    """sha последней записи «ветка отправлена» задачи; None — записи нет."""
    return _last_sent_sha(task_id) or None


# Подпись коммита пульта (SPEC 01M5WDB7JY0VJGHVKCABA2QC5T, требования 2-5):
# автор и коммиттер — `machine.commit_author` записи проекта, строка
# `policy.co_author` и трейлер — в сообщении, запись журнала «коммит
# пульта» — только при `commit_author`. Трейлер — сведение, решений по нему
# пульт не принимает.
PULT_ACTOR_TRAILER = "Artel-Actor: orchestrator"
PULT_COMMIT_ACTION = "коммит пульта:"


def _project_entry(project: str | None) -> dict:
    if not project:
        return {}
    from . import targets
    try:
        entry = targets.target(project)
    except targets.TargetsError:
        return {}
    return entry if isinstance(entry, dict) else {}


def commit_author(project: str | None) -> tuple[str, str] | None:
    """(имя, почта) `commit_author` записи проекта; None — поля нет."""
    author = _project_entry(project).get("commit_author")
    if isinstance(author, dict) and author.get("name") and author.get("email"):
        return str(author["name"]), str(author["email"])
    return None


def pult_identity(project: str | None, name: str, email: str) -> tuple[str, str]:
    """Автор коммита пульта: `commit_author` проекта, иначе прежний."""
    return commit_author(project) or (name, email)


def pult_identity_args(project: str | None, name: str | None = None,
                       email: str | None = None) -> list:
    """`-c user.name=… -c user.email=…` коммита пульта в рабочей копии;
    пусто — у проекта нет `commit_author` и прежнего автора не задано
    (идентичность клона, как раньше)."""
    author = commit_author(project)
    if author is None:
        if name is None:
            return []
        author = (name, email)
    return ["-c", f"user.name={author[0]}", "-c", f"user.email={author[1]}"]


def pult_message(message: str, project: str | None) -> str:
    """Сообщение коммита пульта: строка `co_author` и трейлер пульта
    последним абзацем. Трейлер — `policy.commit_trailer` записи проекта
    (пустое значение — трейлера нет), без поля — `PULT_ACTOR_TRAILER`."""
    entry = _project_entry(project)
    lines = []
    co_author = entry.get("co_author")
    if isinstance(co_author, str) and co_author.strip():
        lines.append(co_author.strip())
    trailer = entry.get("commit_trailer", PULT_ACTOR_TRAILER)
    if trailer:
        lines.append(trailer)
    if not lines:
        return message.rstrip("\n") + "\n"
    return message.rstrip("\n") + "\n\n" + "\n".join(lines) + "\n"


def journal_pult_commit(conn, task_id: str, project: str | None, sha: str,
                        kind: str) -> None:
    """Запись «коммит пульта: <sha> (<вид>)» — только для проекта с
    `commit_author`: журнал прочих проектов не меняется."""
    if not sha or commit_author(project) is None:
        return
    from . import store
    store.journal(conn, task_id, "orchestrator", PULT_COMMIT_ACTION,
                  f"{sha} ({kind})")


# Сверка `commit_author` с владельцем токена (требование 6) — до первой
# отправки ветки задачи, в этой точке, по любому пути отправки.
AUTHOR_CHECK_REFUSAL = "сверка автора"
AUTHOR_CHECK_SKIPPED_ACTION = "сверка автора — после адаптера"


def _token_user_unimplemented(forge, project: str, reason: str) -> bool:
    """Ответ `reason` — именованный отказ реестра forge «у реализации
    хостинга проекта нет функции token_user». Признак берётся из реестра, не
    из сравнения значения `forge` с литералом: текст «не реализовано»,
    пришедший от хостинга, у которого функция есть, пропуском не считается."""
    hosting = forge.hosting(project)
    implementation = forge.IMPLEMENTATIONS.get(hosting)
    if implementation is None or hasattr(implementation, "token_user"):
        return False
    return reason == f"token_user: не реализовано для {hosting}"


def _author_check_refusal(project: str, entry: dict, task_id: str) -> str | None:
    """Причина отказа отправки ветки задачи `task_id` по сверке автора;
    None — отправка идёт (совпадение, проекта без `commit_author`, ветка уже
    отправлялась, хостинг github без функции)."""
    author = entry.get("commit_author")
    if not (isinstance(author, dict) and author.get("name")):
        return None
    if _last_sent_sha(task_id):
        return None
    name = str(author["name"])
    from . import forge
    user = forge.token_user(project)
    reason = getattr(user, "reason", "") or ""
    if reason:
        if _token_user_unimplemented(forge, project, reason):
            from . import store
            try:
                store.journal(store.db(), task_id, "orchestrator",
                              AUTHOR_CHECK_SKIPPED_ACTION,
                              f"commit_author {name}: {reason} — сверка с "
                              f"владельцем токена отложена до адаптера "
                              f"{forge.hosting(project)}")
            except sqlite3.Error:
                pass
            return None
        return (f"{AUTHOR_CHECK_REFUSAL} не выполнена: commit_author {name}, "
                f"владелец токена не получен — {reason}")
    username = getattr(user, "username", None)
    if not username:
        return (f"{AUTHOR_CHECK_REFUSAL} не выполнена: commit_author {name}, "
                f"token_user дал пустой ответ (имени владельца токена нет)")
    if username != name:
        return (f"{AUTHOR_CHECK_REFUSAL}: commit_author {name} не совпадает с "
                f"владельцем токена token_user {username}")
    return None


def _raw_config(cwd: Path, *args: str) -> str:
    """Вывод `git config <args>` клона `cwd`; пусто — ключа нет."""
    try:
        res = subprocess.run(["git", "-C", str(cwd), "config", *args],
                             capture_output=True, text=True, env=pult_env())
    except OSError:
        return ""
    return res.stdout.strip() if res.returncode == 0 else ""


class _ConfigUnread(Exception):
    """`git config` клона не ответил: сверка белого списка не выполнена."""


def _strict_config(cwd: Path, *args: str) -> str:
    """Вывод `git config <args>` клона `cwd`; пусто — ключа нет (код 1).
    Иной сбой git — `_ConfigUnread`: под белым списком непрочитанная
    конфигурация — отказ, а не «ключа нет» (иначе сбой молча пропускал бы
    сверки `insteadOf`/`sshCommand`/`core.hooksPath`)."""
    command = "git config " + " ".join(args)
    try:
        res = subprocess.run(["git", "-C", str(cwd), "config", *args],
                             capture_output=True, text=True, env=pult_env())
    except OSError as exc:
        raise _ConfigUnread(f"{command}: {exc}") from exc
    if res.returncode == 0:
        return res.stdout.strip()
    if res.returncode == 1:
        return ""
    raise _ConfigUnread(f"{command}: код {res.returncode}, "
                       f"{(res.stderr or '').strip()[:200]}")


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


def _global_values(globals_: list, name: str) -> list:
    """Значения глобальной опции `name` (`<name> <значение>` и
    `<name>=<значение>`) среди глобальных опций git."""
    values = []
    i = 0
    while i < len(globals_):
        word = globals_[i]
        if word == name and i + 1 < len(globals_):
            values.append(globals_[i + 1])
            i += 2
            continue
        if word.startswith(name + "="):
            values.append(word.split("=", 1)[1])
        i += 1 if word not in GIT_GLOBALS_WITH_VALUE else 2
    return values


def _option_words(globals_: list) -> list:
    """Имена глобальных опций git без их значений."""
    words = []
    i = 0
    while i < len(globals_):
        words.append(globals_[i])
        i += 2 if globals_[i] in GIT_GLOBALS_WITH_VALUE else 1
    return words


def _alias_in_argv(globals_: list) -> str | None:
    """Определение псевдонима в самой команде (`-c alias.*`,
    `--config-env=alias.*`); ключ конфигурации git регистронезависим."""
    for name in ("-c", "--config-env"):
        for value in _global_values(globals_, name):
            if value.lower().startswith("alias."):
                return f"{name} {value}"
    return None


def _alias_body_words(globals_: list, env: dict) -> tuple[list, list]:
    """(слова, проекты по тексту) тел псевдонимов, заданных самой командой.

    Тело `-c alias.<имя>=<тело>` — как есть, у `--config-env` — значение
    названной переменной окружения; у `!`-формы — слова shell-команды с
    подставленными `$VAR`/`${VAR}` окружения. Слово `--опция=<значение>`
    даёт и значение. Проекты по тексту — имена из упоминаний
    `.artel/projects/<имя>/` в теле: путь в клон может стоять внутри слова
    shell-команды (`cd …&&`), а не отдельным словом."""
    words, named = [], []
    for name in ("-c", "--config-env"):
        for value in _global_values(globals_, name):
            key, _, body = value.partition("=")
            if not key.lower().startswith("alias."):
                continue
            if name == "--config-env":
                body = env.get(body, "")
            body = re.sub(r"\$\{([A-Za-z_]\w*)[^}]*\}|\$([A-Za-z_]\w*)",
                          lambda m: env.get(m.group(1) or m.group(2), ""),
                          body.removeprefix("!"))
            named += re.findall(r"\.artel/projects/([^/\s\"';&|]+)/", body)
            try:
                split = shlex.split(body)
            except ValueError:
                split = body.split()
            for word in split:
                words.append(word)
                if word.startswith("-") and "=" in word:
                    words.append(word.split("=", 1)[1])
    return words, named


def _alias_guarded_project(cwd_project: str | None, words: list, cwd: Path,
                           entries: dict | None,
                           named: list = ()) -> str | None:
    """Внешний проект под белым списком или с неизвестным гейтом, к клону
    которого относится вызов с псевдонимом в argv: клон вызова, проект,
    названный в теле псевдонима, либо слово после подкоманды или тела
    псевдонима — путь, `file://`-адрес или `url` записи проекта.
    None — псевдоним вызова белый список не касается."""
    from . import targets
    candidates = ([cwd_project] if cwd_project else []) + list(named)
    for word in words:
        local = _local_dest_path(word)
        if local:
            candidates.append(_project_of_path(cwd / local))
        elif entries is not None and _is_url(word):
            found = project_by_url(word, entries)
            candidates.append(found[0] if found is not None else None)
    for project in candidates:
        if project is None or project == config.DEFAULT_TARGET:
            continue
        entry = (entries or {}).get(project)
        if entry is None or targets.push_whitelisted(entry):
            return project
    return None


def _location_projects(globals_: list, cwd: Path, env: dict) -> set:
    """Внешние проекты, в клон которых ведут репозиторий и рабочее дерево
    вызова: `--git-dir` (иначе `GIT_DIR`, иначе рабочий каталог),
    `--work-tree`/`GIT_WORK_TREE`, `GIT_COMMON_DIR`; путь вне области
    проектов и клон артели — не проект."""
    git_dirs = _global_values(globals_, "--git-dir") or [
        v for v in (env.get("GIT_DIR"),) if v]
    paths = [cwd / p for p in git_dirs] or [cwd]
    for value in (_global_values(globals_, "--work-tree")
                  or [v for v in (env.get("GIT_WORK_TREE"),) if v]):
        paths.append(cwd / value)
    if env.get("GIT_COMMON_DIR"):
        paths.append(cwd / env["GIT_COMMON_DIR"])
    return {p for p in map(_project_of_path, paths) if p is not None}


def _push_words(rest: list) -> tuple[list, list, list, list]:
    """(флаги, значения `-o`, позиционные, индексы позиционных в `rest`)
    аргументов после `push`."""
    flags, options, positional, indexes = [], [], [], []
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
            indexes.append(i)
        i += 1
    return flags, options, positional, indexes


def _is_url(dest: str) -> bool:
    return "://" in dest or (":" in dest and "@" in dest.split(":", 1)[0])


def _local_dest_path(dest: str) -> str | None:
    """Путь на диске, в который ведёт назначение отправки: сам путь или
    путь `file://`-адреса (git отправляет по нему в тот же каталог, что и
    по простому пути); None — сетевой адрес."""
    if dest.startswith("file://"):
        parts = urllib.parse.urlsplit(dest)
        return urllib.parse.unquote(parts.path) or None
    return None if _is_url(dest) else dest


class _PushPlan:
    """Решение точки отправки по одному вызову git: argv к запуску или
    отказ; после успешного кода — записи «ветка отправлена»."""

    def __init__(self, args: list, cwd: Path):
        self.args = args
        self.cwd = cwd
        self.refusal: str | None = None
        self.code = PUSH_REFUSAL
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


def _awaiting_state() -> str:
    """Состояние ожидания людей проекта — `fsm.AWAITING_HUMAN`; импорт
    отложен по той же причине, что в `_dead_states`."""
    from . import fsm
    return fsm.AWAITING_HUMAN


def _awaiting_human_spec(specs: list) -> dict | None:
    """Первый refspec отправки, ведущий в ветку задачи в `awaiting_human`
    (отправляемую или удаляемую); None — такого нет."""
    state = _awaiting_state()
    return next((s for s in specs if s["kind"] == "branch"
                 and s["task"] is not None and s["task"]["state"] == state),
                None)


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


def _resolves(cwd: Path, rev: str) -> bool:
    """`rev` клона `cwd` — коммит (`rev-parse --verify`)."""
    try:
        res = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--quiet",
                              "--verify", f"{rev}^{{commit}}"],
                             capture_output=True, text=True, env=pult_env())
    except OSError:
        return False
    return res.returncode == 0


def _explicit_source(cwd: Path, src: str) -> str | None:
    """Источник refspec ветки под белым списком в явном виде: `HEAD`,
    полный sha коммита или `refs/heads/<ветка>` клона; None — иное (тег,
    иная ссылка, выражение ревизии). Короткое имя git ищет и среди тегов
    раньше веток — оттого подставляется полное имя ветки."""
    if src == "HEAD":
        return src if _resolves(cwd, src) else None
    if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", src):
        return src if _resolves(cwd, src) else None
    if src.startswith("refs/") and not src.startswith("refs/heads/"):
        return None
    full = "refs/heads/" + src.removeprefix("refs/heads/")
    return full if _resolves(cwd, full) else None


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
    names = sorted(n for n in env if (n in GIT_CONFIG_ENV_NAMES
                   or n in GIT_LOCATION_ENV_NAMES
                   or n in GIT_TRANSPORT_ENV_NAMES
                   or n.startswith(GIT_CONFIG_ENV_PREFIXES)))
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
        src = _explicit_source(cwd, spec["src"])
        if src is None:
            return (f"источник {spec['src']} refspec {spec['spec']} — не "
                    f"ветка, не HEAD и не sha коммита")
        # Назначение — всегда явное `refs/heads/<имя>`: иначе git выводит
        # вид назначения из источника, и тег уходит в refs/tags/<имя>.
        spec["src"] = src
        spec["explicit"] = f"{src}:refs/heads/{spec['name']}"
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
    try:
        for key in ("pushurl", "push", "mirror"):
            if _strict_config(cwd, "--get-all", f"remote.origin.{key}"):
                return f"в конфигурации клона задан remote.origin.{key}"
        if _strict_config(cwd, "--local", "--get-all", "push.pushOption"):
            return "в конфигурации клона задан push.pushOption"
        return _config_redirect_refusal(entry, cwd)
    except _ConfigUnread as exc:
        return f"конфигурация клона не прочитана — сверка не выполнена: {exc}"


def _config_redirect_refusal(entry: dict, cwd: Path) -> str | None:
    """Причина отказа по действующей конфигурации вызова `cwd` (все слои,
    включая конфигурацию рабочей копии; SPEC 01M6EZXVFGCHB1S4W45AWJ0QH6,
    требование 12): `remote.origin.url` не ровно одно значение, равное
    адресу записи, ключи `PUSH_REDIRECT_CONFIG`, `core.hooksPath` задан и
    не каталог хуков пульта проекта. Незаданный `core.hooksPath` не отказ:
    отправка пульта несёт свой `-c`, а снятый ролью путь ловит строка
    `doctor`. Сбой чтения — `_ConfigUnread`."""
    # `git push origin` шлёт на КАЖДОЕ значение remote.origin.url всех
    # слоёв: второе значение (локальное или из ~/.gitconfig) увело бы
    # ветку на чужой адрес мимо сверки последнего значения.
    origins = _strict_config(cwd, "--get-all", "remote.origin.url").splitlines()
    if len(origins) != 1:
        return (f"в конфигурации remote.origin.url — значений "
                f"{len(origins)} ({', '.join(origins) or 'не задан'}), нужно "
                f"ровно одно — адрес записи проекта")
    if url_key(origins[0]) != url_key(str(entry.get("url") or "")):
        return (f"в конфигурации remote.origin.url = {origins[0]}"
                f" — не адрес записи проекта")
    found = _strict_config(cwd, "--get-regexp", PUSH_REDIRECT_CONFIG)
    if found:
        return f"в конфигурации задан {found.splitlines()[0].split(' ')[0]}"
    expected = project_hooks_path(entry)
    for value in _strict_config(cwd, "--get-all", "core.hooksPath").splitlines():
        if not same_dir(value, expected):
            return (f"в конфигурации core.hooksPath = {value} — не каталог "
                    f"хуков пульта проекта {expected}")
    return None


def _in_flight_refusal(project: str, entry: dict,
                       task_ids: list) -> tuple[str, str] | None:
    """(задача, причина) отказа ПЕРВОЙ отправки ветки задачи пределом
    `policy.max_in_flight` (SPEC 01M5XZ9Z68XE2EKPDHYCAK25KF, требование 7);
    None — предела нет, отправка не первая или предел не достигнут.

    Первая отправка — у задачи нет записи «ветка отправлена» ни новой, ни
    старой формы. В счёт идут незакрытые задачи этого проекта с такой
    записью в любом состоянии; закрытые (`done`, `killed`) и задачи других
    проектов — нет."""
    from . import store, targets
    limit = targets.delivery_policy(entry)["max_in_flight"]
    if limit is None or not task_ids or not config.DB.exists():
        return None
    conn = store.db()
    sent = (PUSH_SENT_ACTION, PUSH_SENT_LEGACY_ACTION)
    first = [t for t in task_ids
             if store.last_task_step_of(conn, t, sent) is None]
    if not first:
        return None
    flying = [row["id"] for row in store.project_tasks(conn, project)
              if row["state"] not in _dead_states() and row["id"] not in first
              and store.last_task_step_of(conn, row["id"], sent) is not None]
    if len(flying) < limit:
        return None
    return first[0], (f"{IN_FLIGHT_LIMIT_REASON}: незакрытых задач проекта "
                      f"с отправленной веткой {len(flying)} из {limit} — "
                      f"первая отправка ветки задачи {first[0]} ждёт, пока "
                      f"одна из них закроется")


def in_flight_refusal(task_id: str) -> str | None:
    """Причина, по которой единая точка отправки откажет первой отправке
    ветки задачи `task_id` пределом `policy.max_in_flight`; None — не
    откажет. Для команды, которая коммитит до отправки (`amend-tests`,
    ответ Оператора ANSWER-3 задачи 01M5XZ9Z68XE2EKPDHYCAK25KF): отказ до
    коммита, без неотправленного хвоста.

    Сбой чтения записи или БД — причина «не проверен» для задачи любого
    проекта, кроме артели (SPEC 01M6EZXVFGXC6WBDA9QJESAZRW, требование 4):
    пульт работает над собой и при сломанном `targets.yaml`. Проект задачи
    не прочитан — задача не известна как задача артели, отказ."""
    from . import store, targets
    if not config.DB.exists():
        return None
    try:
        project = store.task_target(store.db(), task_id)
    except sqlite3.Error as exc:
        return f"{IN_FLIGHT_UNCHECKED} — {DB_UNREAD}: {exc}"
    try:
        entry = targets.load().get(project)
        if entry is None:
            return None
        found = _in_flight_refusal(project, entry, [task_id])
    except targets.TargetsError as exc:
        if project == config.DEFAULT_TARGET:
            return None
        return f"{IN_FLIGHT_UNCHECKED} — запись проекта не прочитана: {exc}"
    except sqlite3.Error as exc:
        if project == config.DEFAULT_TARGET:
            return None
        return f"{IN_FLIGHT_UNCHECKED} — {DB_UNREAD}: {exc}"
    return found[1] if found is not None else None


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


def _push_destination(args: list, index: int, cwd: Path,
                      cwd_project: str | None, entries: dict | None) -> tuple:
    """(флаги, опции, позиционные слова, их позиции, проект, разбор
    refspec) отправки `args[index]` — проект по месту вызова, иначе по
    локальному пути или адресу назначения, иначе артель."""
    flags, options, positional, positions = _push_words(args[index + 1:])
    project = _destination_project(positional, cwd, cwd_project, entries)
    specs = _refspecs(positional[1:], _project_tasks(project))
    return flags, options, positional, positions, project, specs


def _destination_project(positional: list, cwd: Path,
                         cwd_project: str | None,
                         entries: dict | None) -> str:
    """Проект отправки по позиционным словам `positional` без чтения БД:
    по месту вызова, иначе по локальному пути или адресу назначения, иначе
    артель.

    Записи не прочитаны, назначение — сетевой адрес, не адрес `origin`
    корня пульта: проект не узнать, и это не артель (SPEC
    01M6EZXVFGXC6WBDA9QJESAZRW, требование 2) — проект называет сам адрес,
    записи у него нет, и точка отправки отказывает «гейт мержа
    неизвестен»."""
    dest = positional[0] if positional else ""
    project = cwd_project
    local = _local_dest_path(dest) if dest else None
    if project is None and local:
        project = _project_of_path(cwd / local)
    if project is None and dest and entries is not None:
        found = project_by_url(dest, entries)
        project = found[0] if found is not None else None
    if project is None and dest and entries is None and local is None:
        origin = _raw_config(Path(config.ROOT), "--get", "remote.origin.url")
        if not origin or url_key(dest) != url_key(origin):
            project = url_key(dest)
    return project or config.DEFAULT_TARGET


def _refuse_awaiting_human(plan: _PushPlan, project: str, specs: list,
                           env: dict, task_id: str | None) -> bool:
    """Ветку задачи в `awaiting_human` ведут люди проекта (SPEC
    01M5XZ9Z68V75VXF5Z66C708T4, требование 18): отказ при любой форме —
    отправка, явный refspec, `--delete`, `:<ветка>` — и при любом гейте.
    True — отказ записан в `plan`."""
    waiting = _awaiting_human_spec(specs)
    if waiting is None:
        return False
    _refuse(plan, project, waiting["task"]["id"], env, task_id,
            f"ветка {waiting['name']} задачи {waiting['task']['id']} в "
            f"{_awaiting_state()} — ждёт людей проекта, пульт её не "
            f"отправляет")
    return True


def _awaiting_human_refusal(argv: list, task_id: str | None) -> str | None:
    """Отказ отправки ветки задачи в `awaiting_human` для argv `in_repo`
    (`-C <клон> …`) — до `git()`, который тесты и вызыватели подменяют
    (ответ Оператора ANSWER-1 п. 5). Прочие отказы единой точки здесь не
    решаются: их выносит `_push_plan` внутри `git()`, один раз."""
    globals_, index, cwd = _split_globals(argv, Path(config.ROOT))
    if index is None or argv[index] not in PUSH_SUBCOMMANDS:
        return None
    from . import targets
    env = dict(os.environ)
    located = _location_projects(globals_, cwd, env)
    if len(located) > 1:
        return None
    try:
        entries = targets.load()
    except targets.TargetsError:
        entries = None
    _flags, _options, positional, _positions = _push_words(argv[index + 1:])
    project = _destination_project(positional, cwd, next(iter(located), None),
                                   entries)
    plan = _PushPlan(list(argv), cwd)
    try:
        specs = _refspecs(positional[1:], _project_tasks(project))
    except sqlite3.Error as exc:
        # Ветки задач не сверены — отправка вне артели не идёт (SPEC
        # 01M6EZXVFGXC6WBDA9QJESAZRW, требование 6); у артели — как прежде.
        if project == config.DEFAULT_TARGET:
            return None
        _refuse(plan, project, None, env, task_id,
                f"{DB_UNREAD} — ветки задач проекта не сверены: {exc}")
        return plan.refusal
    if _refuse_awaiting_human(plan, project, specs, env, task_id):
        return plan.refusal
    return None


def _push_plan(args: list, cwd: Path, env: dict | None,
               task_id: str | None) -> _PushPlan | None:
    """Решение единой точки отправки по argv git `args` (без `git`),
    запущенному в `cwd` с окружением `env` (None — окружение пульта).
    None — вызов не отправка и не псевдоним в клоне проекта."""
    globals_, index, cwd = _split_globals(args, cwd)
    if index is None:
        return None
    sub = args[index]
    alias_argv = _alias_in_argv(globals_) if globals_ else None
    if alias_argv is None and sub not in PUSH_SUBCOMMANDS and sub in GIT_BUILTINS:
        return None
    from . import targets
    env = dict(os.environ if env is None else env)
    plan = _PushPlan(list(args), cwd)
    located = _location_projects(globals_, cwd, env)
    cwd_project = next(iter(located)) if len(located) == 1 else None
    if len(located) > 1:
        return _refuse(plan, ", ".join(sorted(located)), None, env, task_id,
                       "проект вызова не определён — репозиторий и рабочее "
                       "дерево в клонах разных проектов")
    try:
        entries = targets.load()
    except targets.TargetsError:
        entries = None
    if alias_argv is not None:
        # Псевдоним, заданный самой командой, превращает любое имя в
        # отправку мимо разбора подкоманды — под белым списком (и при
        # неизвестном гейте) отказ при любой подкоманде; у артели и
        # проектов `operator` вызов прежний.
        # Назначение может стоять и в теле псевдонима (`alias.p=push <клон>
        # main`, `!git -C <клон> push …`), не только в словах после него.
        body_words, named = _alias_body_words(globals_, env)
        guarded = _alias_guarded_project(cwd_project,
                                         body_words + args[index + 1:], cwd,
                                         entries, named)
        if guarded is None:
            return None
        return _refuse(plan, guarded, None, env, task_id,
                       f"псевдоним git в команде ({alias_argv})")
    if sub not in PUSH_SUBCOMMANDS:
        # Подкоманда вне встроенных — возможно, псевдоним клона.
        if cwd_project is None:
            return None
        entry = (entries or {}).get(cwd_project)
        if entry is not None and not targets.push_whitelisted(entry):
            return None
        # Глобальная опция перед псевдонимом может подложить его определение
        # (`-c include.path=…`, `--git-dir` в чужой репозиторий).
        foreign = [w for w in _option_words(globals_) if w != "-C"]
        if foreign:
            return _refuse(plan, cwd_project, None, env, task_id,
                           f"глобальная опция git {foreign[0]} перед "
                           f"подкомандой {sub}")
        try:
            alias = _strict_config(cwd, "--get", f"alias.{sub}")
        except _ConfigUnread as exc:
            return _refuse(plan, cwd_project, None, env, task_id,
                           f"подкоманда {sub} — псевдоним не сверен, "
                           f"конфигурация клона не прочитана: {exc}")
        if not alias:
            return None
        return _refuse(plan, cwd_project, None, env, task_id,
                       f"подкоманда {sub} — псевдоним git ({alias})")
    flags, options, positional, positions, project, specs = _push_destination(
        args, index, cwd, cwd_project, entries)
    related = next((s["task"]["id"] for s in specs if s["task"] is not None),
                   None)
    if _refuse_awaiting_human(plan, project, specs, env, task_id):
        return plan
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
        if reason is None and targets.merged_by_project_people(entry):
            reason = _push_policy_refusal(project, entry, cwd)
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
        if entry is not None:
            for task_id_of in dict.fromkeys(s["task"]["id"] for s in branches):
                reason = _author_check_refusal(project, entry, task_id_of)
                if reason is not None:
                    return _refuse(plan, project, task_id_of, env, task_id,
                                   reason)
            try:
                waiting = _in_flight_refusal(
                    project, entry,
                    list(dict.fromkeys(s["task"]["id"] for s in branches)))
            except sqlite3.Error as exc:
                # Счёт не прочитан — предел не проверен, отправка вне артели
                # не идёт (SPEC 01M6EZXVFGXC6WBDA9QJESAZRW, требование 5).
                if project != config.DEFAULT_TARGET:
                    return _refuse(plan, project, related, env, task_id,
                                   f"{IN_FLIGHT_UNCHECKED} — {DB_UNREAD}: "
                                   f"{exc}")
                waiting = None
            if waiting is not None:
                _refuse(plan, project, waiting[0], env, task_id, waiting[1])
                plan.code = IN_FLIGHT_REFUSAL
                return plan
        plan.sent =[(s["task"]["id"], s["src"], s["name"]) for s in branches]
    reset = list(PUSH_RESET_CONFIG) if whitelisted else []
    if whitelisted and targets.merged_by_project_people(entry):
        # Хук белого списка срабатывает и тогда, когда роль сняла или
        # подменила постоянный `core.hooksPath` клона (SPEC
        # 01M6EZXVFGCHB1S4W45AWJ0QH6, требование 6).
        reset += ["-c", f"core.hooksPath={project_hooks_path(entry)}"]
    rest = list(args[index + 1:])
    for spec, pos in zip(specs, positions[1:]):
        if "explicit" in spec:
            rest[pos] = spec["explicit"]
    plan.args = (globals_ + reset + [sub] + added + rest)
    return plan


def _refused(args, refusal: str, text: bool = True,
             code: int = PUSH_REFUSAL) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        list(args), code, "" if text else b"",
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
            return _refused(args, plan.refusal, code=plan.code)
        args = tuple(plan.args)
    project = _hosting_project(args)
    if project is not None:
        token, refusal = hosting_token(*project)
        if refusal is not None:
            return subprocess.CompletedProcess(args, 1, "", refusal)
        if token is not None:
            host = url_host(str(project[1].get("url") or ""))
            if project[1].get("submodule_tokens"):
                env = hosting_path_env(env, token, host,
                                       submodule_credentials(*project))
            else:
                env = hosting_env(env, token, host)
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
            return _refused(["git", *args], plan.refusal, text, plan.code)
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

    Отправка ветки задачи в `awaiting_human` отказывается уже здесь, до
    `git` (SPEC 01M5XZ9Z68V75VXF5Z66C708T4, требование 18; ANSWER-1 п. 5).
    """
    # Не-push вызов (fetch, worktree, rev-parse…) проверку не проходит
    # вовсе: argv и поведение такого вызова — ровно прежние.
    if any(word in PUSH_SUBCOMMANDS for word in args):
        argv = ["-C", str(repo), *args]
        refusal = _awaiting_human_refusal(argv, task_id)
        if refusal is not None:
            return _refused(["git", *argv], refusal)
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
        return _refused(["git", *argv], plan.refusal, text, plan.code)
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
        return _refused(["git", *argv], plan.refusal, code=plan.code)
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
        return _refused(["git", *argv], plan.refusal, text=False,
                        code=plan.code)
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
