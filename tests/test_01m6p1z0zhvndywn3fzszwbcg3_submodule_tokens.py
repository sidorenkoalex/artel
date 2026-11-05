"""Отдельный токен подмодулей внешнего проекта: поле `machine.submodule_tokens`, выбор пароля помощником учётных данных по адресу, извлечение подмодулей клона и строка `doctor` `project-submodules-<проект>`.

Группа: долгоживущий
Красен до реализации: раздел `machine` локального слоя не знает поля `submodule_tokens` — запись с ним отказывает «неизвестное поле» и сценарии с полем не строятся, поле в записи слоя репозитория молча принимается, помощник пульта выдаёт пароль по одному хосту без пути (адрес подмодуля получает пароль проекта), `credential.useHttpPath` не ставится, подмодуль с паролем, отличным от пароля проекта, не извлекается; эталон записи без поля (AC-2), отказ без поля (AC-4) и отсутствие строки у `operator` без поля (AC-5) зелены с рождения — они держат прежнее поведение; варианты AC-3 «другой порт»/«другой хост» до реализации зелены тривиально (запись с полем не загружается, помощника нет — пусто).

Окружение (раздел «Безопасность тестов» SPEC): корень пульта — песочница
`tmp_root`; записи проектов — в локальном слое песочницы
(`targets.local_path()`), имена проектов, групп, путей подмодулей и пароли
порождаются модулем `random` при каждом запуске, зерно печатается и входит в
текст провала. Слот связки ключей — подмена публичной `keychain.token`
словарём слотов теста, каждое чтение слота записывается. Хостинг — вымышленный
`localhost` (в `tests/` адреса только на loopback — инвариант 35; другой
хост — `127.0.0.1`): хостинговые git-вызовы пульта перехватываются подменой
`subprocess.run` (argv и окружение записываются) и не исполняются; ответ
`ls-remote` даёт модель хостинга теста — она проверяет пароль, который в
окружении вызова отдаёт `git credential fill` по адресу пробы. Единственная
настоящая сеть — `http.server` на `127.0.0.1` (AC-4). Прочие git-вызовы идут к
настоящему git.

Каждый git-вызов теста — с `GIT_TERMINAL_PROMPT=0`, `GIT_CONFIG_NOSYSTEM=1`,
`GIT_CONFIG_GLOBAL` на пустой файл песочницы, без `GIT_ASKPASS`/`SSH_ASKPASS`,
с пределом времени 60 с в своей группе процессов: подмена `subprocess.run`
ставит `timeout` и вызовам внутри пульта. Исход «пусто» у `git credential
fill` — в выводе нет строки `password=`.
"""
import base64
import contextlib
import functools
import http.server
import os
import random
import shutil
import string
import subprocess
import threading
import urllib.parse
from collections import namedtuple
from pathlib import Path

import pytest

from orchestrator import (ci, config, doctor, gitlab_adapter, keychain,
                          repo_context, targets, workspace)
from orchestrator.doctor import misc_checks
from tests.sandbox import artel_target_entry, network_guarded_real_run

LIMIT = 60
HOST = "localhost"
HOST_OTHER_CASE = "LocalHost"
OTHER_HOST = "127.0.0.1"
# Схемы адресов собираются из частей: литерал `схема://хост` в `tests/`
# допустим только на loopback (инвариант 35, `scripts/guard.py`).
HTTPS = "https" + "://"
HTTP = "http" + "://"
SSH = "ssh" + "://"
OTHER_PORT = "8443"
LETTERS = "abcdefghijkmnopqrstuvwxyz"
SUBCOMMANDS = ("fetch", "pull", "ls-remote", "push", "clone", "submodule update")
# Текст помощника учётных данных пульта на origin/main 77e9ca9c
# (`HOSTING_CREDENTIAL_HELPER`, orchestrator/gitcmd.py:51-56) — литерал.
HELPER_TEXT = (
    '!f() { test "$1" = get || exit 0; h=; while IFS= read -r l; do '
    'case "$l" in host=*) h="${l#host=}";; esac; done; '
    'test "$h" = "${ARTEL_HOSTING_HOST}" || exit 0; '
    'echo username=x-access-token; '
    'echo "password=${ARTEL_HOSTING_TOKEN}"; }; f')

Call = namedtuple("Call", "argv env")
Sub = namedtuple("Sub", "path url slot password")


# --- окружение сценария -----------------------------------------------------

def word(rng: random.Random, prefix: str, size: int = 6) -> str:
    return prefix + "".join(rng.choice(LETTERS) for _ in range(size))


def secret(rng: random.Random, prefix: str) -> str:
    return prefix + "".join(rng.choice(string.hexdigits.lower())
                            for _ in range(24))


def fmt(template: str, **values) -> str:
    """Адрес по шаблону: `{https}`/`{http}`/`{ssh}` — схемы, `{host}` — хост
    записи, `{other}` — другой хост, `{case}` — хост записи в другом регистре."""
    return template.format(https=HTTPS, http=HTTP, ssh=SSH, host=HOST,
                           other=OTHER_HOST, case=HOST_OTHER_CASE,
                           port=OTHER_PORT, **values)


def git_words(argv: list) -> list:
    """Слова git-вызова после ведущих `-C <путь>`/`-c <ключ=знач>`."""
    words = list(argv[1:])
    while len(words) >= 2 and words[0] in ("-C", "-c"):
        words = words[2:]
    return words


def is_git(argv: list) -> bool:
    return bool(argv) and Path(str(argv[0])).name == "git"


def hosting_name(words: list) -> str | None:
    """Имя хостинговой подкоманды (`submodule update` — двумя словами)."""
    if words[:2] == ["submodule", "update"]:
        return "submodule update"
    if words and words[0] in ("fetch", "pull", "ls-remote", "push", "clone"):
        return words[0]
    return None


def config_pairs(env: dict) -> list:
    """(ключ, значение) конфигурации git из `GIT_CONFIG_KEY_n`/`VALUE_n`."""
    try:
        count = int(env.get("GIT_CONFIG_COUNT") or 0)
    except ValueError:
        count = 0
    return [(env.get(f"GIT_CONFIG_KEY_{i}"), env.get(f"GIT_CONFIG_VALUE_{i}"))
            for i in range(count)]


def hosting_vars(env: dict) -> dict:
    """Переменные эталона AC-2: счётчик, ключи и значения конфигурации git из
    окружения, `ARTEL_HOSTING_*`."""
    return {k: v for k, v in env.items()
            if k == "GIT_CONFIG_COUNT" or k.startswith(
                ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_", "ARTEL_HOSTING_"))}


def address_key(url: str) -> tuple:
    """Адрес модели хостинга: (хост с портом в нижнем регистре, путь без
    `.git` и завершающей черты)."""
    parts = urllib.parse.urlsplit(url)
    path = parts.path.rstrip("/").removesuffix(".git").lstrip("/")
    return parts.netloc.lower(), path


def plain(text: str) -> str:
    return text.replace("`", "")


class Pult:
    """Песочница пульта: окружение git, подмена связки ключей и перехват
    `subprocess.run`."""

    def __init__(self, sandbox, monkeypatch, tmp_path: Path, seed: int):
        self.sandbox = sandbox
        self.monkeypatch = monkeypatch
        self.tmp = tmp_path
        self.seed = seed
        self.rng = random.Random(seed)
        self.empty_global = tmp_path / "gitconfig-empty"
        self.empty_global.write_text("", encoding="utf-8")
        home = tmp_path / "home"
        home.mkdir()
        for name in list(os.environ):
            if name.startswith(("GIT_", "ARTEL_HOSTING_")) or name in (
                    "SSH_ASKPASS", config.ARTEL_ROLE_ENV):
                monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
        monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(self.empty_global))
        self.slots: dict = {}
        self.reads: list = []
        monkeypatch.setattr(keychain, "token", self.read_slot)
        self.calls: list = []
        self.answer = None
        self.live = False
        self.scenes: list = []
        monkeypatch.setattr(subprocess, "run", self.run)

    # связка ключей
    def read_slot(self, slot, *args, **kwargs):
        self.reads.append(slot)
        return self.slots.get(slot)

    # перехват процессов
    def run(self, cmd, *args, **kwargs):
        argv = ([os.fsdecode(a) for a in cmd] if isinstance(cmd, (list, tuple))
                else [os.fsdecode(cmd)])
        env = kwargs.get("env")
        env = dict(os.environ if env is None else env)
        self.calls.append(Call(argv, env))
        text = bool(kwargs.get("text") or kwargs.get("universal_newlines")
                    or kwargs.get("encoding"))
        if not is_git(argv):
            return self.completed(argv, 127, "", "песочница: процесс не "
                                  "запускается", text)
        kwargs["timeout"] = min(kwargs.get("timeout") or LIMIT, LIMIT)
        kwargs["start_new_session"] = True
        words = git_words(argv)
        if hosting_name(words) is not None and not self.live:
            reply = self.answer(argv, env, words) if self.answer else None
            code, out, err = reply or (0, "", "")
            return self.completed(argv, code, out, err, text)
        return network_guarded_real_run(cmd, *args, **kwargs)

    @staticmethod
    def completed(argv, code, out, err, text):
        if text:
            return subprocess.CompletedProcess(argv, code, out, err)
        return subprocess.CompletedProcess(argv, code, out.encode(), err.encode())

    def hosting_calls(self, name: str | None = None, since: int = 0) -> list:
        out = []
        for call in self.calls[since:]:
            if not is_git(call.argv):
                continue
            found = hosting_name(git_words(call.argv))
            if found is not None and (name is None or found == name):
                out.append(call)
        return out

    # настоящий git теста
    def git_env(self, env: dict | None = None, trace: bool = False) -> dict:
        env = dict(os.environ if env is None else env)
        for name in ("GIT_ASKPASS", "SSH_ASKPASS", "GIT_TRACE"):
            env.pop(name, None)
        env.update(GIT_CONFIG_GLOBAL=str(self.empty_global),
                   GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
        if trace:
            env["GIT_TRACE"] = "1"
        return env

    def git(self, repo: Path, *args: str) -> subprocess.CompletedProcess:
        res = network_guarded_real_run(
            ["git", "-C", str(repo), "-c", "user.name=artel tests",
             "-c", "user.email=artel@example.invalid",
             "-c", "commit.gpgsign=false", *args],
            capture_output=True, text=True, env=self.git_env(),
            timeout=LIMIT, start_new_session=True)
        if res.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} в {repo}: {res.stderr}")
        return res

    def fill(self, env: dict, url: str, trace: bool = False) -> tuple:
        """(пароли, stderr) `git credential fill` по `url` в окружении `env`."""
        res = network_guarded_real_run(
            ["git", "credential", "fill"], input=f"url={url}\n\n",
            capture_output=True, text=True, env=self.git_env(env, trace),
            cwd=str(self.tmp), timeout=LIMIT, start_new_session=True)
        return ([line[len("password="):] for line in res.stdout.splitlines()
                 if line.startswith("password=")], res.stderr)

    def passwords(self, env: dict, url: str) -> list:
        return self.fill(env, url)[0]

    # записи проектов
    def scene(self, **kwargs) -> "Scene":
        scene = Scene(self, **kwargs)
        self.scenes.append(scene)
        return scene

    def write_layer(self) -> None:
        text = "targets:\n" + "".join(s.record_text() for s in self.scenes)
        local = targets.local_path()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(text, encoding="utf-8")

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"


class Scene:
    """Запись вымышленного внешнего проекта и его клон."""

    def __init__(self, pult: Pult, *, gate: str = "operator",
                 url: str | None = None, suffix: str = ".git"):
        self.pult = pult
        rng = pult.rng
        self.name = word(rng, "proj")
        self.group = word(rng, "grp")
        self.gate = gate
        self.url = url or fmt("{https}{host}/{group}/{name}{suffix}", group=self.group,
                                   name=self.name, suffix=suffix)
        self.slot = f"{self.name}-hosting"
        self.password = secret(rng, "projpw")
        pult.slots[self.slot] = self.password
        self.field: dict = {}
        self.modules: list = []
        self.with_field = False
        self.clone = config.PROJECTS / self.name / "repo"

    def sub(self, url: str | None = None, *, in_field: bool = True,
            in_gitmodules: bool = True, password: str | None = "random",
            path: str | None = None) -> Sub:
        rng = self.pult.rng
        leaf = word(rng, "sub")
        path = path or f"libs/{leaf}"
        url = fmt(url or "{https}{host}/{group}/{leaf}.git", group=self.group,
                  leaf=leaf)
        slot = f"{self.name}-{leaf}-slot"
        if password == "random":
            password = secret(rng, "subpw")
        if in_field:
            self.with_field = True
            self.field[path] = slot
            self.pult.slots[slot] = password
        if in_gitmodules:
            self.modules.append((path, url))
        return Sub(path, url, slot, password)

    def record_text(self) -> str:
        lines = [f"  {self.name}:",
                 "    description:", f"      base: {config.MAIN_BRANCH}",
                 "      test_profile:", "        command: [python3, -m, pytest]",
                 "        long_lived_dir: tests",
                 "        long_lived_name: test_<id>_<name>.py",
                 "    policy:", "      no_paths: []", "      project_skills: []",
                 f"      merge_gate: {self.gate}",
                 "      weakening_scope: [tests/**/*.py]",
                 "      mutation_claim_scope: [tests/test_*.py]",
                 "    machine:", "      forge: github", f"      url: {self.url}",
                 f"      token_slot: {self.slot}"]
        if self.with_field:
            lines.append("      submodule_tokens:")
            lines += [f"        {path}: {slot}" for path, slot in self.field.items()]
        return "\n".join(lines) + "\n"

    def gitmodules_text(self, modules: list | None = None) -> str:
        modules = self.modules if modules is None else modules
        return "".join(f'[submodule "{path}"]\n\tpath = {path}\n\turl = {url}\n'
                       for path, url in modules)

    def make_clone(self, dest: Path | None = None, gitmodules: str | None = None) -> Path:
        """Клон — настоящий локальный git-репозиторий с `.gitmodules` (в дереве
        и в коммите) и `origin` = `url` записи; сети нет."""
        dest = self.clone if dest is None else dest
        dest.mkdir(parents=True, exist_ok=True)
        self.pult.git(dest, "init", "-q", "-b", config.MAIN_BRANCH)
        text = self.gitmodules_text() if gitmodules is None else gitmodules
        (dest / "README").write_text(f"{self.name}\n", encoding="utf-8")
        files = ["README"]
        if text is not False:
            (dest / ".gitmodules").write_text(text, encoding="utf-8")
            files.append(".gitmodules")
        self.pult.git(dest, "add", *files)
        self.pult.git(dest, "commit", "-q", "--no-verify", "-m", "init")
        self.pult.git(dest, "remote", "add", "origin", self.url)
        return dest

    def entry(self) -> dict:
        return targets.target(self.name)

    def ctx(self, path: Path | None = None) -> "repo_context.RepoContext":
        return repo_context.RepoContext(
            path=Path(self.clone if path is None else path), remote="origin",
            base=config.MAIN_BRANCH, target=self.name)

    def call(self, name: str, path: Path | None = None) -> tuple:
        """(исход, argv, окружение) хостингового вызова пульта `name` по клону
        проекта (у `clone` — из каталога проекта)."""
        pult = self.pult
        args = {"fetch": ("fetch", "-q", "origin"),
                "pull": ("pull", "-q", "--ff-only"),
                "ls-remote": ("ls-remote", "origin"),
                "push": ("push", "-q", "origin",
                         f"HEAD:refs/heads/probe-{pult.rng.randrange(10**6)}"),
                "clone": ("clone", "--quiet", self.url,
                          f"copy-{pult.rng.randrange(10**6)}"),
                "submodule update": ("submodule", "update", "--init",
                                     "--recursive", "--quiet")}[name]
        if path is None:
            path = self.clone.parent if name == "clone" else self.clone
        since = len(pult.calls)
        res = repo_context.git(self.ctx(path), *args)
        calls = pult.hosting_calls(name, since)
        call = calls[0] if calls else Call(None, {})
        return res, path, args, call

    def fake_clone(self, then=None):
        """Ответ на `git clone` пульта: каталог клона — настоящий локальный
        репозиторий с `.gitmodules` сценария; `then` — действие после него."""
        def answer(argv, env, words):
            if words[:1] != ["clone"]:
                return None
            parent = Path(argv[argv.index("-C") + 1]) if "-C" in argv else config.ROOT
            self.make_clone(parent / words[-1])
            if then is not None:
                then()
            return 0, "", ""
        return answer


class Hosting:
    """Модель хостинга для `ls-remote`: адрес → пароль, который он принимает."""

    def __init__(self, pult: Pult):
        self.pult = pult
        self.accepts: dict = {}
        self.probes: list = []

    def allow(self, url: str, password: str | None) -> None:
        self.accepts[address_key(url)] = password

    def answer(self, argv, env, words):
        if words[:1] != ["ls-remote"]:
            return None
        address = next((w for w in words[1:] if not w.startswith("-")), "")
        got = self.pult.passwords(env, address)
        self.probes.append((address, env, got))
        need = self.accepts.get(address_key(address))
        if need and got == [need]:
            return 0, "0" * 40 + "\tHEAD\n", ""
        return 128, "", "remote: HTTP Basic: Access denied\n"


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


@pytest.fixture
def pult(tmp_root, monkeypatch, tmp_path, seed):
    return Pult(tmp_root, monkeypatch, tmp_path, seed)


def submodules_line(scene: Scene) -> tuple:
    """(строка `project-submodules-<проект>` или None, все строки текстом)."""
    checks = list(doctor.project_entry_checks(scene.name, scene.entry()))
    shown = "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in checks)
    found = [c for c in checks if c.name == f"project-submodules-{scene.name}"]
    return (found[0] if found else None), shown


# --- AC-1: поле записи ------------------------------------------------------

def layer_record(name: str, field_lines: list) -> str:
    return ("targets:\n"
            f"  {name}:\n"
            f"    description:\n      base: {config.MAIN_BRANCH}\n"
            "      test_profile:\n        command: [python3, -m, pytest]\n"
            "        long_lived_dir: tests\n"
            "        long_lived_name: test_<id>_<name>.py\n"
            "    policy:\n      no_paths: []\n      project_skills: []\n"
            "      merge_gate: operator\n"
            "      weakening_scope: [tests/**/*.py]\n"
            "      mutation_claim_scope: [tests/test_*.py]\n"
            "    machine:\n      forge: github\n"
            f"      url: {HTTPS}{HOST}/grp/{name}.git\n"
            f"      token_slot: {name}-hosting\n"
            + "".join(f"      {line}\n" for line in field_lines))


def load_local(name: str, field_lines: list) -> tuple:
    """(плоская запись, None) — загрузилась; (None, текст отказа) — нет."""
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(layer_record(name, field_lines), encoding="utf-8")
    try:
        return targets.target(name), None
    except targets.TargetsError as exc:
        return None, str(exc)


def test_ac1_local_record_with_field_loads_into_flat_record(tmp_root, seed):
    """Запись локального слоя с `machine.submodule_tokens` загружается, поле — в плоской записи.

    Сценарий: случайное число (1–3) пар «путь подмодуля → слот» со случайными
    именами в разделе `machine`; `targets.target` отдаёт запись, её поле
    `submodule_tokens` равно записанному отображению.

    Ловит мутацию: поле не объявлено в `LOCAL_FIELDS["machine"]` (отказ
    «неизвестное поле») либо не перенесено `_flatten` — в плоской записи
    поля нет или оно отличается.
    """
    rng = random.Random(seed)
    name = word(rng, "rec")
    mapping = {f"libs/{word(rng, 's')}": word(rng, "slot-")
               for _ in range(rng.randint(1, 3))}
    lines = ["submodule_tokens:"] + [f"  {p}: {s}" for p, s in mapping.items()]
    entry, error = load_local(name, lines)
    assert error is None, f"зерно: {seed}; запись с полем не загрузилась: {error}"
    assert entry.get("submodule_tokens") == mapping, f"зерно: {seed}; {entry}"


@pytest.mark.parametrize("variant, lines", [
    ("пустой путь", ["submodule_tokens:", "  : {slot}"]),
    ("пустой слот", ["submodule_tokens:", '  {path}: ""']),
    ("слот без значения", ["submodule_tokens:", "  {path}:"]),
    ("строка вместо отображения", ["submodule_tokens: {slot}"]),
    ("список вместо отображения", ["submodule_tokens: [{path}, {slot}]"]),
])
def test_ac1_bad_field_value_refused_naming_field(tmp_root, seed, variant, lines):
    """Негодное значение поля в локальном слое — отказ загрузки с именем поля.

    Сценарий: та же запись с допустимым значением поля сначала загружается
    (контроль — поле объявлено), затем вариант `variant` (пустой путь, пустой
    слот, путь без слота, не отображение) — `targets.target` отказывает
    `TargetsError`, текст называет `submodule_tokens` и не говорит
    «неизвестное поле».

    Ловит мутацию: проверка формы поля пропущена (пустой путь/слот или
    строка вместо отображения загружается) либо отказ не называет поле.
    """
    rng = random.Random(seed)
    name = word(rng, "rec")
    path, slot = f"libs/{word(rng, 's')}", word(rng, "slot-")
    entry, error = load_local(name, ["submodule_tokens:", f"  {path}: {slot}"])
    assert error is None, f"зерно: {seed}; контрольная запись не загрузилась: {error}"
    entry, error = load_local(name, [ln.format(path=path, slot=slot) for ln in lines])
    note = f"зерно: {seed}; вариант «{variant}»"
    assert entry is None, f"{note}: запись загрузилась: {entry}"
    assert "submodule_tokens" in error, f"{note}: отказ без имени поля: {error}"
    assert "неизвестное" not in error, f"{note}: поле не объявлено: {error}"


def test_ac1_field_in_repo_layer_refused(tmp_root, seed):
    """Поле `submodule_tokens` в записи слоя репозитория — отказ загрузки с именем поля.

    Сценарий: `targets.yaml` песочницы — запись артели и плоская запись
    внешнего проекта; без поля `targets.load` её принимает (контроль), с
    полем `submodule_tokens` — `TargetsError`, текст называет поле.

    Ловит мутацию: проверка записи по-прежнему не отвергает неизвестное
    плоское поле — поле в слое репозитория принимается и доходит до
    помощника в обход локального слоя.
    """
    rng = random.Random(seed)
    name = word(rng, "rec")
    flat = (f"  {name}:\n    forge: github\n"
            f"    url: {HTTPS}{HOST}/grp/{name}.git\n"
            f"    base: {config.MAIN_BRANCH}\n    token_slot: {name}-hosting\n"
            "    no_paths: []\n    project_skills: []\n    merge_gate: operator\n")
    head = "targets:\n" + artel_target_entry()
    config.TARGETS.write_text(head + flat, encoding="utf-8")
    assert name in targets.load(), f"зерно: {seed}; контрольная запись не загрузилась"
    config.TARGETS.write_text(
        head + flat + "    submodule_tokens:\n"
        f"      libs/{word(rng, 's')}: {word(rng, 'slot-')}\n", encoding="utf-8")
    with pytest.raises(targets.TargetsError, match="submodule_tokens"):
        targets.load()


# --- AC-2: окружение и argv хостингового вызова ------------------------------

@pytest.mark.parametrize("name", SUBCOMMANDS)
def test_ac2_record_without_field_env_and_argv_unchanged(pult, name):
    """Запись без поля: переменные помощника и argv хостингового вызова — литералы прежнего кода.

    Сценарий: запись проекта без `submodule_tokens`, клон с подмодулем в
    `.gitmodules`; унаследованные `GIT_CONFIG_*` сняты фикстурой. Вызов
    `name` пульта (`repo_context.git`) перехвачен: argv — ровно `git -C
    <путь> <аргументы>`, переменные `GIT_CONFIG_COUNT`/`KEY_n`/`VALUE_n` и
    `ARTEL_HOSTING_*` равны литералу теста (сброс помощников, текст
    помощника 77e9ca9c, токен слота проекта, хост записи);
    `credential.useHttpPath` не выставлен.

    Ловит мутацию: общий помощник переписан под выбор по пути для всех
    записей (текст `GIT_CONFIG_VALUE_1` другой), `useHttpPath` или новая
    переменная `ARTEL_HOSTING_*` ставится и записи без поля, либо argv
    получает `-c credential.useHttpPath=true`.
    """
    scene = pult.scene()
    scene.sub(in_field=False)
    pult.write_layer()
    scene.make_clone()
    res, path, args, call = scene.call(name)
    note = pult.msg(f"{name}: {res.stderr}")
    assert call.argv == ["git", "-C", str(path), *args], note
    assert hosting_vars(call.env) == {
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "credential.helper",
        "GIT_CONFIG_VALUE_0": "",
        "GIT_CONFIG_KEY_1": "credential.helper",
        "GIT_CONFIG_VALUE_1": HELPER_TEXT,
        "ARTEL_HOSTING_TOKEN": scene.password,
        "ARTEL_HOSTING_HOST": HOST,
    }, note
    keys = [k.lower() for k, _v in config_pairs(call.env)]
    assert "credential.usehttppath" not in keys, note


@pytest.mark.parametrize("name", SUBCOMMANDS)
def test_ac2_record_with_field_sets_use_http_path(pult, name):
    """Запись с полем: `credential.useHttpPath=true` в окружении каждого хостингового вызова.

    Сценарий: запись с `submodule_tokens` на подмодуль хоста записи; вызов
    `name` пульта перехвачен, в его окружении среди пар
    `GIT_CONFIG_KEY_n`/`VALUE_n` есть `credential.useHttpPath` = `true`. Для
    `push` дополнительно: `git credential fill` по адресу проекта в этом
    окружении отдаёт ровно пароль проекта.

    Ловит мутацию: `useHttpPath` ставится не всем подкомандам (например,
    забыт `clone` или `submodule update`), либо окружение `push` собрано
    иначе и адрес проекта не получает пароль проекта.
    """
    scene = pult.scene()
    scene.sub()
    pult.write_layer()
    scene.make_clone()
    res, path, args, call = scene.call(name)
    note = pult.msg(f"{name}: {res.stderr}")
    assert call.argv is not None, f"{note}: хостинговый вызов не дошёл до git"
    pairs = [(k.lower(), (v or "").lower()) for k, v in config_pairs(call.env)]
    assert ("credential.usehttppath", "true") in pairs, f"{note}: {pairs}"
    if name == "push":
        assert pult.passwords(call.env, scene.url) == [scene.password], note


def test_ac2_hosting_token_callers_do_not_read_submodule_slots(pult):
    """Вызыватели `hosting_token` для записи с полем читают только слот проекта.

    Сценарий: запись с двумя подмодулями в `submodule_tokens`. Окружение
    `gh` проекта (`doctor` `misc_checks.gh_env`), `ci.gh` с `repo=` адресом
    проекта и `gitlab_adapter.token_user` вызваны; среди чтений
    `keychain.token` нет слотов подмодулей, `gh_env` отдаёт `GH_TOKEN`
    слота проекта.

    Ловит мутацию: `hosting_token` читает слоты подмодулей (например, чтобы
    заранее собрать карту паролей) — их имена появляются в чтениях связки.
    """
    scene = pult.scene()
    subs = [scene.sub(), scene.sub()]
    pult.write_layer()
    env, refusal = misc_checks.gh_env(scene.name, scene.entry())
    assert refusal is None and env["GH_TOKEN"] == scene.password, pult.msg(str(refusal))
    ci.gh("pr", "view", "probe", repo=scene.url)
    with contextlib.suppress(Exception):
        gitlab_adapter.token_user(scene.name)
    assert scene.slot in pult.reads, pult.msg(str(pult.reads))
    for sub in subs:
        assert sub.slot not in pult.reads, pult.msg(f"прочитан слот {sub.slot}")


# --- AC-3: выбор пароля по адресу -------------------------------------------

@pytest.mark.parametrize("name", ("fetch", "pull", "ls-remote", "push",
                                  "submodule update"))
def test_ac3_submodule_address_gets_its_slot_project_gets_project(pult, name):
    """Адрес подмодуля — пароль его слота, адрес проекта — пароль проекта, другой хост — пусто.

    Сценарий: `url` записи без `.git`; подмодуль в поле и в `.gitmodules`
    клона на хосте записи. В окружении вызова `name` `git credential fill`:
    по адресу подмодуля — ровно пароль слота подмодуля; по адресу проекта
    без `.git` и с `.git` (`path=<группа>/<проект>.git`) — ровно пароль
    проекта; по адресу проекта на другом хосте — ничего.

    Ловит мутацию: помощник выбирает по хосту (подмодуль получает пароль
    проекта), сравнивает путь без снятия `.git` (адрес проекта с `.git` —
    пусто), либо выдаёт пароль любому хосту.
    """
    scene = pult.scene(suffix="")
    sub = scene.sub()
    pult.write_layer()
    scene.make_clone()
    res, path, args, call = scene.call(name)
    note = pult.msg(f"{name}: {res.stderr}")
    assert call.argv is not None, f"{note}: хостинговый вызов не дошёл до git"
    assert pult.passwords(call.env, sub.url) == [sub.password], note
    assert pult.passwords(call.env, scene.url) == [scene.password], note
    assert pult.passwords(call.env, scene.url + ".git") == [scene.password], note
    other = fmt("{https}{other}/{group}/{name}.git", group=scene.group,
                name=scene.name)
    assert pult.passwords(call.env, other) == [], note


def test_ac3_third_address_and_prefix_get_project_not_submodule(pult):
    """Третий адрес хоста — пароль проекта; адрес с префиксом подмодуля — не пароль подмодуля.

    Сценарий: запись с подмодулем в поле; в окружении `fetch` пульта адрес
    `<группа>/<случайное имя>.git` того же хоста получает ровно пароль
    проекта, адрес `<группа>/<подмодуль>-other.git` — не пароль подмодуля.

    Ловит мутацию: сравнение адресов по префиксу (`<подмодуль>-other`
    получает пароль подмодуля) либо прочие адреса хоста остаются без пароля.
    """
    scene = pult.scene()
    sub = scene.sub()
    pult.write_layer()
    scene.make_clone()
    res, path, args, call = scene.call("fetch")
    third = fmt("{https}{host}/{group}/{leaf}.git", group=scene.group,
                leaf=word(pult.rng, "third"))
    prefix = sub.url.removesuffix(".git") + "-other.git"
    assert pult.passwords(call.env, third) == [scene.password], pult.msg(third)
    assert sub.password not in pult.passwords(call.env, prefix), pult.msg(prefix)


@pytest.mark.parametrize("variant, module_url, request_url, expect", [
    ("относительный адрес", "../{leaf}.git", "{https}{host}/{group}/{leaf}.git", "sub"),
    ("схема http", "{http}{host}/{group}/{leaf}.git", "{http}{host}/{group}/{leaf}.git", "sub"),
    ("имя хоста в другом регистре", "{https}{case}/{group}/{leaf}.git",
     "{https}{case}/{group}/{leaf}.git", "sub"),
    ("то же имя хоста, другой порт", "{https}{host}:{port}/{group}/{leaf}.git",
     "{https}{host}:{port}/{group}/{leaf}.git", "empty"),
    ("другой хост", "{https}{other}/{group}/{leaf}.git",
     "{https}{other}/{group}/{leaf}.git", "empty"),
])
def test_ac3_submodule_address_forms(pult, variant, module_url, request_url, expect):
    """Формы адреса подмодуля из поля в `.gitmodules` клона: чей пароль получает запрос к нему.

    Сценарий: подмодуль в поле, его адрес в `.gitmodules` клона — вариант
    `variant`; в окружении `fetch` пульта запрос `request_url`: относительный
    адрес (разрешён от `url` записи), схема http и имя хоста в другом регистре
    — ровно пароль слота подмодуля; тот же хост на другом порту и другой хост
    — ничего, и `keychain.token` слот подмодуля не читал; пароль подмодуля
    не выдан ни адресу проекта, ни тому же пути на хосте записи.

    Ловит мутацию: относительный адрес не разрешается от `url` записи;
    хост сравнивается с учётом регистра или по схеме; хост — без порта
    (`_remote_kind`), и адрес на другом порту получает пароль подмодуля;
    другой хост не исключён и слот читается.
    """
    scene = pult.scene()
    leaf = word(pult.rng, "sub")
    sub = scene.sub(module_url.replace("{leaf}", leaf), path=f"libs/{leaf}")
    pult.write_layer()
    scene.make_clone()
    res, path, args, call = scene.call("fetch")
    url = fmt(request_url, group=scene.group, leaf=leaf)
    got = pult.passwords(call.env, url)
    note = pult.msg(f"вариант «{variant}», запрос {url}: {got}")
    if expect == "sub":
        assert got == [sub.password], note
    else:
        assert got == [], note
        assert sub.slot not in pult.reads, f"{note}: слот подмодуля прочитан"
        same_path = fmt("{https}{host}/{group}/{leaf}.git", group=scene.group,
                         leaf=leaf)
        for probe in (same_path, scene.url):
            assert sub.password not in pult.passwords(call.env, probe), \
                f"{note}: пароль подмодуля выдан {probe}"


def test_ac3_clone_gitmodules_wins_over_task_worktree(pult):
    """Расхождение `.gitmodules` клона и рабочей копии задачи — выбор по клону.

    Сценарий: в `.gitmodules` клона путь подмодуля указывает на адрес A, в
    `.gitmodules` рабочей копии задачи (`worktrees/<id>` проекта) — на адрес
    B того же хоста. `fetch` пульта из рабочей копии: в его окружении адрес
    A получает пароль слота подмодуля, адрес B — не пароль подмодуля.

    Ловит мутацию: `.gitmodules` читается из каталога вызова (рабочей копии
    задачи), а не из клона `workspace.repo(<проект>)`.
    """
    scene = pult.scene()
    sub = scene.sub()
    pult.write_layer()
    scene.make_clone()
    other = fmt("{https}{host}/{group}/{leaf}.git", group=scene.group,
                leaf=word(pult.rng, "wt"))
    worktree = config.PROJECTS / scene.name / "worktrees" / word(pult.rng, "T")
    scene.make_clone(worktree, gitmodules=scene.gitmodules_text([(sub.path, other)]))
    res, path, args, call = scene.call("fetch", path=worktree)
    assert pult.passwords(call.env, sub.url) == [sub.password], pult.msg(sub.url)
    assert sub.password not in pult.passwords(call.env, other), pult.msg(other)


# --- AC-4: клон с подмодулем на локальном сервере ----------------------------

class AuthHandler(http.server.SimpleHTTPRequestHandler):
    """Статическая отдача репозиториев с проверкой пароля по префиксу пути."""

    def authorized(self) -> bool:
        need = next((pw for prefix, pw in self.server.passwords.items()
                     if self.path.startswith(prefix)), None)
        if need is None:
            self.send_error(404)
            return False
        header = self.headers.get("Authorization", "")
        if header.startswith("Basic "):
            raw = base64.b64decode(header[6:]).decode("utf-8", "replace")
            if raw.partition(":")[2] == need:
                return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="sandbox"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def do_GET(self):
        if self.authorized():
            super().do_GET()

    def do_HEAD(self):
        if self.authorized():
            super().do_HEAD()

    def log_message(self, *args):
        pass


@contextlib.contextmanager
def serving(root: Path, passwords: dict):
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(AuthHandler, directory=str(root)))
    server.passwords = passwords
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(LIMIT)


def bare_repo(pult: Pult, bare: Path, seed_dir: Path, files: dict,
              gitlink: tuple | None = None) -> str:
    """Bare-репозиторий с одним коммитом (`update-server-info` — для
    статической отдачи); `gitlink` — (путь, sha) подмодуля. sha коммита."""
    bare.parent.mkdir(parents=True, exist_ok=True)
    pult.git(bare.parent, "init", "-q", "--bare", "-b", config.MAIN_BRANCH, str(bare))
    seed_dir.mkdir(parents=True)
    pult.git(seed_dir, "init", "-q", "-b", config.MAIN_BRANCH)
    for rel, text in files.items():
        (seed_dir / rel).write_text(text, encoding="utf-8")
    pult.git(seed_dir, "add", *files)
    if gitlink is not None:
        pult.git(seed_dir, "update-index", "--add", "--cacheinfo",
                 f"160000,{gitlink[1]},{gitlink[0]}")
    pult.git(seed_dir, "commit", "-q", "--no-verify", "-m", "init")
    pult.git(seed_dir, "push", "-q", str(bare),
             f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
    pult.git(bare, "update-server-info")
    return pult.git(seed_dir, "rev-parse", "HEAD").stdout.strip()


@pytest.mark.parametrize("with_field", [True, False])
def test_ac4_clone_and_submodule_over_http_server(pult, with_field):
    """Клон с подмодулем другого репозитория на локальном сервере: с полем — проходит, без поля — отказ.

    Сценарий: `http.server` на `127.0.0.1` отдаёт два bare-репозитория
    статикой; проект и подмодуль принимают разные пароли (проверка по
    префиксу пути). `url` записи и адрес `.gitmodules` — с `.git`. Пульт
    исполняет git по-настоящему. `workspace.ensure_clone` записи с
    `token_slot` и `submodule_tokens` — без отказа, файл подмодуля извлечён;
    записи с одним `token_slot` — отказ «подмодули не извлечены», как
    сейчас. Сервер останавливается в `finally`.

    Ловит мутацию: `submodule update` в `_clone_submodules` идёт с прежним
    окружением (пароль проекта для подмодуля — 401, клон не заведён), либо
    `useHttpPath` не ставится и помощник не видит пути подмодуля.
    """
    served = pult.tmp / "served"
    group, proj, leaf = (word(pult.rng, p) for p in ("grp", "proj", "sub"))
    proj_pw, sub_pw = secret(pult.rng, "projpw"), secret(pult.rng, "subpw")
    marker = word(pult.rng, "marker-", 10)
    passwords = {f"/{group}/{proj}.git/": proj_pw, f"/{group}/{leaf}.git/": sub_pw}
    with serving(served, passwords) as port:
        base = f"http://127.0.0.1:{port}/{group}"
        sub_sha = bare_repo(pult, served / group / f"{leaf}.git",
                            pult.tmp / "seed-sub", {"sub.txt": marker + "\n"})
        modules = (f'[submodule "libs/{leaf}"]\n\tpath = libs/{leaf}\n'
                   f"\turl = {base}/{leaf}.git\n")
        bare_repo(pult, served / group / f"{proj}.git", pult.tmp / "seed-proj",
                  {"README": "proj\n", ".gitmodules": modules},
                  gitlink=(f"libs/{leaf}", sub_sha))
        scene = pult.scene(url=f"{base}/{proj}.git")
        pult.slots[scene.slot] = proj_pw
        if with_field:
            scene.with_field = True
            scene.field[f"libs/{leaf}"] = f"{scene.name}-sub-slot"
            pult.slots[f"{scene.name}-sub-slot"] = sub_pw
        pult.write_layer()
        pult.live = True
        clone, error = workspace.ensure_clone(scene.name)
    if with_field:
        assert error is None, pult.msg(f"клон не заведён: {error}")
        text = (clone / "libs" / leaf / "sub.txt").read_text(encoding="utf-8")
        assert text == marker + "\n", pult.msg("подмодуль не извлечён")
    else:
        assert error is not None and "подмодули не извлечены" in error, \
            pult.msg(f"клон без поля: {error}")


# --- AC-5: строка doctor ----------------------------------------------------

def doctor_scene(pult: Pult, gate: str = "target-human") -> tuple:
    scene = pult.scene(gate=gate)
    hosting = Hosting(pult)
    pult.answer = hosting.answer
    return scene, hosting


def test_ac5_field_submodule_probed_with_its_slot(pult):
    """Подмодуль из поля проверяется паролем своего слота — `ok`.

    Сценарий: `merge_gate: target-human`, подмодуль из поля на хосте записи
    (схема https). Модель хостинга принимает на адресе подмодуля только пароль
    его слота. Строка `project-submodules-<проект>` — `ok`; в окружении
    вызова `ls-remote` пробы `git credential fill` по адресу подмодуля отдаёт
    пароль слота подмодуля, не пароль проекта.

    Ловит мутацию: проба подмодуля идёт с прежним окружением (токен
    проекта) — модель хостинга отказывает, строка `fail`.
    """
    scene, hosting = doctor_scene(pult)
    sub = scene.sub()
    hosting.allow(sub.url, sub.password)
    pult.write_layer()
    scene.make_clone()
    line, shown = submodules_line(scene)
    note = pult.msg(shown)
    assert line is not None and line.status == "ok", note
    probes = [p for p in hosting.probes if address_key(p[0]) == address_key(sub.url)]
    assert probes, f"{note}: пробы ls-remote подмодуля нет"
    for _address, env, got in probes:
        assert got == [sub.password], note
        assert scene.password not in pult.passwords(env, sub.url), note


# (вариант, адрес в .gitmodules, слот пуст, статус, должен содержать, не должен содержать)
AC5_CASES = [
    ("пустой слот", "{https}{host}/{group}/{leaf}.git", True, "fail", ["{slot}"], []),
    ("другой хост", "{https}{other}/{group}/{leaf}.git", False, "fail",
     ["другой хост", "{path}", "{other}"], []),
    ("тот же хост, другой порт", "{https}{host}:{port}/{group}/{leaf}.git", False, "fail",
     ["другой хост", "{path}", "{host}:{port}"], []),
    ("схема http, непустой слот", "{http}{host}/{group}/{leaf}.git", False, "warn",
     ["адрес {http}, токеном слота не проверяется"], ["не на хосте записи"]),
    ("схема http, пустой слот", "{http}{host}/{group}/{leaf}.git", True, "fail",
     ["{slot}"], []),
    ("схема ssh", "{ssh}git@{host}/{group}/{leaf}.git", False, "warn",
     ["ssh-адрес, токеном слота не проверяется"], []),
    ("ssh вида scp", "git@{host}:{group}/{leaf}.git", False, "warn",
     ["ssh-адрес, токеном слота не проверяется"], []),
]


@pytest.mark.parametrize("variant, module_url, empty, status, present, absent", AC5_CASES)
def test_ac5_field_submodule_outcomes(pult, variant, module_url, empty, status,
                                      present, absent):
    """Исход строки `project-submodules-<проект>` по адресу и слоту подмодуля из поля.

    Сценарий: `merge_gate: target-human`, один подмодуль из поля с адресом
    варианта в `.gitmodules` клона; модель хостинга принимает на адресе
    подмодуля только пароль его слота. Пустой слот (в том числе у схемы http)
    — `fail` с именем слота; другой хост и то же имя хоста на другом порту —
    `fail` «другой хост» с путём и хостом; схема http с непустым слотом —
    `warn` «адрес <схема http>, токеном слота не проверяется» без «не на хосте
    записи»; ssh-адрес (схема ssh и вид scp) — `warn` «ssh-адрес, токеном
    слота не проверяется».

    Ловит мутацию: хост сравнивается `_remote_kind` без порта (другой порт —
    не «другой хост»); подмодуль из поля на другом хосте остаётся прежним
    `warn`; схема http идёт прежней веткой «не на хосте записи»; пустой слот
    схемы http даёт `warn` вместо `fail`; ssh-адрес из поля даёт `fail`.
    """
    scene, hosting = doctor_scene(pult)
    leaf = word(pult.rng, "sub")
    sub = scene.sub(module_url.replace("{leaf}", leaf), path=f"libs/{leaf}",
                    password="" if empty else "random")
    hosting.allow(sub.url, sub.password)
    pult.write_layer()
    scene.make_clone()
    line, shown = submodules_line(scene)
    note = pult.msg(f"вариант «{variant}»\n{shown}")
    assert line is not None, note
    assert line.status == status, note
    detail = plain(line.detail)
    for text in present:
        assert fmt(text, slot=sub.slot, path=sub.path) in detail, note
    for text in absent:
        assert text not in detail, note


def test_ac5_host_in_other_case_is_record_host(pult):
    """Имя хоста записи в другом регистре — тот же хост, не `fail` «другой хост».

    Сценарий: адрес подмодуля из поля в `.gitmodules` клона —
    `LocalHost` при `url` записи на `localhost`;
    модель хостинга принимает пароль слота подмодуля. Строка не `fail`, в её
    тексте нет «другой хост».

    Ловит мутацию: имя хоста сравнивается с учётом регистра — подмодуль
    объявлен «другой хост», строка `fail`.
    """
    scene, hosting = doctor_scene(pult)
    sub = scene.sub("{https}{case}/{group}/{leaf}.git")
    hosting.allow(sub.url, sub.password)
    pult.write_layer()
    scene.make_clone()
    line, shown = submodules_line(scene)
    assert line is not None and line.status != "fail", pult.msg(shown)
    assert "другой хост" not in line.detail, pult.msg(shown)


@pytest.mark.parametrize("variant", ["путь не в .gitmodules", ".gitmodules нет",
                                     ".gitmodules без адресов"])
def test_ac5_field_paths_missing_from_gitmodules_warn(pult, variant):
    """Путь поля, которого нет в `.gitmodules` клона, — `warn` «путь не в .gitmodules» на каждый путь.

    Сценарий: в поле два пути. Варианты: `.gitmodules` клона называет
    другой подмодуль (не из поля, на хосте записи, доступен паролю
    проекта); `.gitmodules` в клоне нет; `.gitmodules` есть, но без адресов.
    Строка — `warn`, не `ok`; текст называет каждый путь поля и «путь не в
    .gitmodules».

    Ловит мутацию: ранний `ok` «подмодулей нет» без `.gitmodules` или без
    адресов остался и для записи с полем; путь поля без подмодуля молча
    пропускается.
    """
    scene, hosting = doctor_scene(pult)
    subs = [scene.sub(in_gitmodules=False), scene.sub(in_gitmodules=False)]
    if variant == "путь не в .gitmodules":
        other = scene.sub(in_field=False)
        hosting.allow(other.url, scene.password)
        gitmodules = None
    elif variant == ".gitmodules нет":
        gitmodules = False
    else:
        gitmodules = '[submodule "x"]\n\tpath = x\n'
    pult.write_layer()
    scene.make_clone(gitmodules=gitmodules)
    line, shown = submodules_line(scene)
    note = pult.msg(f"вариант «{variant}»\n{shown}")
    assert line is not None and line.status == "warn", note
    detail = plain(line.detail)
    assert "путь не в .gitmodules" in detail, note
    for sub in subs:
        assert sub.path in detail, note


def test_ac5_other_submodule_on_other_host_warns_as_before(pult):
    """Прочий подмодуль (не из поля) на другом хосте — прежний `warn`.

    Сценарий: подмодуль из поля доступен паролю своего слота, второй
    подмодуль — не из поля, на другом хосте. Строка — `warn`, текст
    называет второй подмодуль и «не на хосте записи».

    Ловит мутацию: правило «другой хост — fail» применено ко всем
    подмодулям записи, а не только к подмодулям из поля.
    """
    scene, hosting = doctor_scene(pult)
    sub = scene.sub()
    hosting.allow(sub.url, sub.password)
    other = scene.sub("{https}{other}/{group}/{leaf}.git", in_field=False)
    pult.write_layer()
    scene.make_clone()
    line, shown = submodules_line(scene)
    assert line is not None and line.status == "warn", pult.msg(shown)
    assert other.path in line.detail and "не на хосте записи" in line.detail, \
        pult.msg(shown)


@pytest.mark.parametrize("with_field", [True, False])
def test_ac5_operator_gate_line_only_with_field(pult, with_field):
    """`merge_gate: operator`: строка подмодулей есть с полем и отсутствует без поля.

    Сценарий: запись `operator`, клон с подмодулем на хосте записи; с
    `submodule_tokens` строка `project-submodules-<проект>` среди строк
    `doctor` есть, без поля — её нет, как сейчас.

    Ловит мутацию: условие заведения строки осталось только
    `merged_by_project_people` (у `operator` с полем строки нет) либо строка
    заводится всем записям.
    """
    scene, hosting = doctor_scene(pult, gate="operator")
    sub = scene.sub(in_field=with_field)
    hosting.allow(sub.url, sub.password if with_field else scene.password)
    pult.write_layer()
    scene.make_clone()
    line, shown = submodules_line(scene)
    assert (line is not None) == with_field, pult.msg(shown)


# --- AC-6: процесс роли -----------------------------------------------------

@pytest.mark.parametrize("empty_sub_slot", [False, True])
def test_ac6_role_process_refuses_before_keychain(pult, empty_sub_slot):
    """Процесс роли: хостинговый вызов записи с полем — прежний отказ, связка не читается.

    Сценарий: две записи — с `submodule_tokens` (слот подмодуля пустой либо
    нет) и без поля; признак процесса роли `ARTEL_ROLE`. `fetch` пульта по
    каждой отказан, тексты отказов совпадают с точностью до имени проекта,
    `keychain.token` не вызван ни разу.

    Ловит мутацию: для записи с полем слоты подмодулей читаются до проверки
    процесса роли, либо отказ процесса роли заменён отказом пустого слота.
    """
    scene = pult.scene()
    scene.sub(password="" if empty_sub_slot else "random")
    plain_scene = pult.scene()
    pult.write_layer()
    scene.make_clone()
    plain_scene.make_clone()
    pult.monkeypatch.setenv(config.ARTEL_ROLE_ENV, "developer")
    res, *_rest = scene.call("fetch")
    base, *_rest = plain_scene.call("fetch")
    note = pult.msg(f"{res.stderr} | {base.stderr}")
    assert res.returncode != 0 and base.returncode != 0, note
    assert (res.stderr.replace(scene.name, "<проект>")
            == base.stderr.replace(plain_scene.name, "<проект>")), note
    assert pult.reads == [], pult.msg(f"чтения связки: {pult.reads}")


@pytest.mark.parametrize("empty_sub_slot", [False, True])
def test_ac6_clone_submodules_in_role_process_keeps_role_refusal(pult, empty_sub_slot):
    """Извлечение подмодулей в процессе роли — прежний отказ процесса роли, слоты подмодулей не читаются.

    Сценарий: `workspace.ensure_clone` записи с полем; `git clone` проходит
    (ответ песочницы кладёт клон с `.gitmodules`), сразу после него процесс
    становится процессом роли — `_clone_submodules` идёт уже в нём. Отказ
    клона содержит текст отказа процесса роли (тот же, что у `fetch` этой
    записи в процессе роли), не называет слот подмодуля; после клона
    `keychain.token` не вызывается — в том числе при пустом слоте.

    Ловит мутацию: `_clone_submodules` сначала читает слоты подмодулей и
    отказывает «слот пуст» (отказ требования 4 раньше отказа роли), либо
    читает связку в процессе роли.
    """
    scene = pult.scene()
    sub = scene.sub(password="" if empty_sub_slot else "random")
    pult.write_layer()
    pult.monkeypatch.setenv(config.ARTEL_ROLE_ENV, "developer")
    refusal = scene.call("fetch")[0].stderr
    pult.monkeypatch.delenv(config.ARTEL_ROLE_ENV)
    marks: list = []

    def become_role():
        marks.append(len(pult.reads))
        pult.monkeypatch.setenv(config.ARTEL_ROLE_ENV, "developer")

    pult.answer = scene.fake_clone(then=become_role)
    clone, error = workspace.ensure_clone(scene.name)
    note = pult.msg(f"отказ роли «{refusal}»; исход {error}")
    assert marks, f"{note}: git clone не дошёл до песочницы"
    assert refusal and error is not None and refusal.strip() in error, note
    assert sub.slot not in error, note
    assert pult.reads[marks[0]:] == [], pult.msg(f"чтения после клона: {pult.reads}")


# --- AC-7: пароли не утекают ------------------------------------------------

def test_ac7_passwords_never_leak(pult, capsys):
    """Пароли проекта и подмодуля не попадают в журнал, вывод, argv, `GIT_CONFIG_VALUE_*` и трассу помощника.

    Сценарий: запись `target-human` с подмодулем из поля. Сыграны шесть
    хостинговых вызовов пульта, строки `doctor` записи (проба подмодуля
    принята моделью хостинга) и отказанный `fetch` (модель хостинга
    отказывает). Значений обоих паролей нет: в выводе (stdout/stderr) и
    текстах исходов, в файлах корня песочницы (журнал пульта, логи), в argv
    любого перехваченного процесса, ни в одной `GIT_CONFIG_VALUE_*`
    окружения хостинговых вызовов, в stderr `git credential fill` с
    `GIT_TRACE=1` в этих окружениях по адресам проекта и подмодуля.

    Ловит мутацию: пароль подмодуля вписан в текст помощника
    (`GIT_CONFIG_VALUE_n`) или в argv (`-c credential.<url>.helper=!echo
    password=…`), либо строка `doctor`/журнал печатает окружение вызова.
    """
    scene, hosting = doctor_scene(pult)
    sub = scene.sub()
    hosting.allow(sub.url, sub.password)
    pult.write_layer()
    scene.make_clone()
    texts = []
    for name in SUBCOMMANDS:
        res = scene.call(name)[0]
        texts += [res.stdout or "", res.stderr or ""]
    checks = doctor.project_entry_checks(scene.name, scene.entry())
    texts += [f"{c.name} {c.detail}" for c in checks]
    pult.answer = lambda argv, env, words: (128, "", "remote: denied\n")
    res = scene.call("fetch")[0]
    texts += [res.stdout or "", res.stderr or ""]
    out = capsys.readouterr()
    texts += [out.out, out.err]
    hosting_envs = [c.env for c in pult.hosting_calls()]
    assert len(hosting_envs) >= len(SUBCOMMANDS), pult.msg("вызовов нет")
    for value in (scene.password, sub.password):
        note = pult.msg(f"пароль {value[:8]}…")
        assert all(value not in t for t in texts), f"{note}: в выводе"
        for path in Path(config.ROOT).rglob("*"):
            if path.is_file() and not path.is_symlink():
                assert value.encode() not in path.read_bytes(), f"{note}: в {path}"
        for call in pult.calls:
            assert value not in " ".join(call.argv), f"{note}: в argv {call.argv[:4]}"
        for env in hosting_envs:
            for key, item in env.items():
                if key.startswith("GIT_CONFIG_VALUE_"):
                    assert value not in item, f"{note}: в {key}"
            for url in (scene.url, sub.url):
                _got, trace = pult.fill(env, url, trace=True)
                assert value not in trace, f"{note}: в трассе помощника"


# --- AC-8: пустой слот подмодуля и _clone_submodules -------------------------

@pytest.mark.parametrize("variant, module_url", [
    ("схема https на хосте записи", "{https}{host}/{group}/{leaf}.git"),
    ("схема http на хосте записи", "{http}{host}/{group}/{leaf}.git"),
])
def test_ac8_empty_slot_on_record_host_refuses_before_git(pult, variant, module_url):
    """Пустой слот подмодуля из `.gitmodules` клона на хосте записи — именованный отказ до `submodule update`.

    Сценарий: слот подмодуля пуст (`keychain.token` отдаёт пустую строку).
    Сначала по готовому клону `fetch` пульта той же записи проходит, а `git
    credential fill` по адресу подмодуля в его окружении — пусто. Затем клон
    убран, `workspace.ensure_clone` (клон — ответ песочницы с `.gitmodules`):
    отказ называет путь подмодуля и имя слота, `submodule update` не вызван.

    Ловит мутацию: пустой слот подмодуля заменяется токеном проекта (fill
    отдаёт пароль проекта), отказ пустого слота распространён на `fetch`,
    либо `_clone_submodules` запускает git и отказ даёт хостинг, а не пульт.
    """
    scene = pult.scene()
    leaf = word(pult.rng, "sub")
    sub = scene.sub(module_url.replace("{leaf}", leaf), path=f"libs/{leaf}", password="")
    pult.write_layer()
    scene.make_clone()
    res, path, args, call = scene.call("fetch")
    note = pult.msg(f"вариант «{variant}»: {res.stderr}")
    assert res.returncode == 0, f"{note}: fetch отказан"
    assert pult.passwords(call.env, sub.url) == [], note
    shutil.rmtree(scene.clone)
    since = len(pult.calls)
    pult.answer = scene.fake_clone()
    clone, error = workspace.ensure_clone(scene.name)
    note = pult.msg(f"вариант «{variant}»: {error}")
    assert error is not None, f"{note}: отказа нет"
    assert sub.path in error and sub.slot in error, note
    assert pult.hosting_calls("submodule update", since) == [], f"{note}: git вызван"


@pytest.mark.parametrize("variant, module_url, in_gitmodules", [
    ("путь не в .gitmodules", "{https}{host}/{group}/{leaf}.git", False),
    ("другое имя хоста", "{https}{other}/{group}/{leaf}.git", True),
    ("то же имя хоста, другой порт", "{https}{host}:{port}/{group}/{leaf}.git", True),
    ("схема ssh", "{ssh}git@{host}/{group}/{leaf}.git", True),
    ("ssh вида scp", "git@{host}:{group}/{leaf}.git", True),
])
def test_ac8_empty_slot_elsewhere_is_not_refusal(pult, variant, module_url, in_gitmodules):
    """Пустой слот пути вне `.gitmodules`, на другом хосте или с ssh-адресом — не отказ `_clone_submodules`.

    Сценарий: слот подмодуля из поля пуст; `workspace.ensure_clone` (клон —
    ответ песочницы, `submodule update` песочница принимает) отказа не даёт.
    Варианты: путь поля не в `.gitmodules` (там другой подмодуль), адрес на
    другом имени хоста, то же имя хоста на другом порту (хост — с портом),
    ssh-адрес на хосте записи (схема ssh и вид scp) — у ssh `keychain.token`
    слот подмодуля не читал.

    Ловит мутацию: отказ пустого слота дан любому пути поля (без проверки
    `.gitmodules`, хоста или вида адреса); хост сравнивается без порта
    (`_remote_kind`) — другой порт даёт отказ; слот ssh-подмодуля читается.
    """
    scene = pult.scene()
    leaf = word(pult.rng, "sub")
    sub = scene.sub(module_url.replace("{leaf}", leaf), path=f"libs/{leaf}",
                    password="", in_gitmodules=in_gitmodules)
    if not in_gitmodules:
        scene.sub(in_field=False)
    pult.write_layer()
    pult.answer = scene.fake_clone()
    clone, error = workspace.ensure_clone(scene.name)
    note = pult.msg(f"вариант «{variant}»")
    assert error is None, f"{note}: {error}"
    if "ssh" in variant:
        assert sub.slot not in pult.reads, f"{note}: слот ssh-подмодуля прочитан"
