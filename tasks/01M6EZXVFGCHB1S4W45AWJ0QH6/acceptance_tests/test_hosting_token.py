"""Токен слота `token_slot` в клоне проекта и клоне его подмодулей; помощник учётных данных пульта отдаёт пароль только хосту адреса записи.

Группа: разовый
Красен до реализации: `clone` нет в `HOSTING_SUBCOMMANDS` — `ensure_clone` клонирует без `ARTEL_HOSTING_TOKEN` и помощника пульта, подмодули не клонируются вовсе; помощник `HOSTING_CREDENTIAL_HELPER` отдаёт `password=<токен>` на запрос `get` с любым `host`.

Группа «разовый» — по правилу guard, не по смыслу свойства: предмет —
окружение git-вызовов `gitcmd` и ответ настоящего `git credential fill`
(`scripts/guard.py::_GIT_MODULES`, `SIGN_GIT_CALL`).

Стенд — `_stand.Stand` поверх `real_git` (`keychain.token` подменён
песочницей поддельной связкой ключей: токен `test-token-<слот>`). AC-15:
шпион журналирует каждый вызов `subprocess.run`/`Popen` с окружением и
передаёт его настоящему git; `origin` проекта — bare-репозиторий с
подмодулем из другого bare. AC-17: адрес записи — `https://localhost/…`;
шпион хостинговый вызов не исполняет, а лишь запоминает его окружение и
argv; в этом окружении (и с опциями `-c credential…` из argv) настоящий
`git credential fill` задаёт помощнику запрос `get` для хоста записи и для
иного хоста. Зерно `random` печатается и входит в текст провала.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _stand import OPERATOR, REAL_RUN, Stand, git, subcommand  # noqa: E402

from orchestrator import gitcmd, keychain, repo_context, targets, workspace  # noqa: E402


@pytest.fixture
def stand(real_git, monkeypatch, tmp_path):
    return Stand(real_git, monkeypatch, tmp_path)


def carries_token(call: dict, token: str) -> bool:
    """Вызов несёт токен слота: значение в `ARTEL_HOSTING_TOKEN` окружения
    и помощник пульта (читающий эту переменную) в конфигурации вызова —
    окружением `GIT_CONFIG_*` либо `-c` в argv."""
    env, argv = call["env"], call["argv"]
    helper = any(gitcmd.HOSTING_TOKEN_ENV in value for key, value in env.items()
                 if key.startswith("GIT_CONFIG_VALUE_")) or any(
        gitcmd.HOSTING_TOKEN_ENV in word for word in argv)
    return env.get(gitcmd.HOSTING_TOKEN_ENV) == token and helper


def is_submodule_clone(call: dict) -> bool:
    argv, sub = call["argv"], subcommand(call["argv"])
    if sub == "clone":
        return any(word.startswith("--recurse-submodules") for word in argv)
    return sub == "submodule" and "update" in argv


# -------------------------------------------------------------------- AC-15

def test_ac15_clone_and_submodules_carry_slot_token(stand, monkeypatch):
    """Подготовка клона проекта с `token_slot`, чей `origin` содержит подмодуль: токен слота виден в клоне проекта и в клоне подмодулей, подмодуль извлечён.

    Сценарий: `workspace.ensure_clone` под шпионом, передающим вызовы
    настоящему git; вызов `clone` проекта и вызов, клонирующий подмодули
    (`clone --recurse-submodules` либо `submodule update`), несут
    `ARTEL_HOSTING_TOKEN` = токен слота и помощник пульта; в клоне
    `sub/<файл>` равен файлу коммита подмодуля.

    Ловит мутацию: `clone` не добавлен в хостинговые подкоманды (клон идёт
    без токена); подмодули клонируются отдельным вызовом мимо `gitcmd`
    (`subprocess` без `hosting_env`) либо не клонируются вовсе.
    """
    name = stand.name()
    content = f"подмодуль {stand.name('s')}\n"
    sub_bare = stand.bare_with_commit(f"{name}-sub", files={"sub.txt": content})
    bare = stand.bare_with_commit(name, submodule=sub_bare)
    stand.declare(name, OPERATOR, str(bare))
    stand.spy(monkeypatch, execute_push=True)
    clone, error = workspace.ensure_clone(name)
    assert error is None, stand.note(f"ensure_clone: {error}")
    token = keychain.token(f"{name}-token")
    clones = [c for c in stand.calls if subcommand(c["argv"]) == "clone"]
    assert clones and any(carries_token(c, token) for c in clones), \
        stand.note(f"вызовы clone без токена слота: {[c['argv'] for c in clones]}")
    subs = [c for c in stand.calls if is_submodule_clone(c)]
    assert subs, stand.note(f"нет вызова клона подмодулей: "
                            f"{[c['argv'] for c in stand.calls]}")
    assert all(carries_token(c, token) for c in subs), \
        stand.note(f"клон подмодулей без токена слота: {[c['argv'] for c in subs]}")
    extracted = clone / "sub" / "sub.txt"
    assert extracted.is_file() and extracted.read_text(encoding="utf-8") == content, \
        stand.note(f"подмодуль не извлечён: {extracted}")


def test_ac15_clone_without_slot_goes_without_token(stand, monkeypatch):
    """Подготовка клона проекта без подмодулей и без `token_slot` идёт без токена, как прежде.

    Сценарий: `targets.load` отдаёт запись без поля `token_slot`;
    `workspace.ensure_clone` под шпионом заводит клон; ни один вызов
    `clone` не несёт `ARTEL_HOSTING_TOKEN`.

    Ловит мутацию: токен ставится клону любого внешнего проекта (слот по
    умолчанию от имени проекта) либо отсутствие поля даёт отказ клона.
    """
    name = stand.name()
    bare = stand.bare_with_commit(name)
    stand.declare(name, OPERATOR, str(bare))
    real_load = targets.load

    def load():
        entries = {k: dict(v) for k, v in real_load().items()}
        entries[name].pop("token_slot", None)
        return entries

    monkeypatch.setattr(targets, "load", load)
    assert "token_slot" not in targets.target(name)
    stand.spy(monkeypatch, execute_push=True)
    clone, error = workspace.ensure_clone(name)
    assert error is None and clone.is_dir(), stand.note(f"ensure_clone: {error}")
    clones = [c for c in stand.calls if subcommand(c["argv"]) == "clone"]
    assert clones, stand.note("вызова clone нет")
    assert not any(gitcmd.HOSTING_TOKEN_ENV in c["env"] for c in clones), \
        stand.note("клон без token_slot несёт токен")


# -------------------------------------------------------------------- AC-17

def credential_fill(clone: Path, call: dict, url: str) -> object:
    """`git credential fill` для `url` в окружении и с `-c credential…`
    хостингового вызова `call`; без системного слоя и запроса в терминал."""
    env = dict(call["env"])
    for name in ("GIT_ASKPASS", "SSH_ASKPASS"):
        env.pop(name, None)
    env.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1")
    argv, pairs = call["argv"], []
    for i in range(len(argv) - 1):
        if argv[i] == "-c" and argv[i + 1].lower().startswith("credential"):
            pairs += ["-c", argv[i + 1]]
    return REAL_RUN(["git", "-C", str(clone), *pairs, "credential", "fill"],
                    input=f"url={url}\n\n", capture_output=True, text=True,
                    env=env, timeout=60)


@pytest.mark.parametrize("sub", ["fetch", "ls-remote"])
def test_ac17_helper_gives_password_only_for_record_host(stand, monkeypatch, sub):
    """Помощник из окружения хостингового вызова проекта с `token_slot`: на `get` с `host` записи — `password=<токен>`, с иным `host` — ни `password=`, ни токена.

    Сценарий: клон проекта с `origin` = `https://localhost/team/<имя>` (адрес
    записи); `gitcmd.in_repo(<клон>, sub, "origin")` под шпионом, который
    запоминает окружение вызова; в нём `git credential fill` для адреса
    записи отдаёт `password=<токен слота>`, для `https://<иной хост>/…` —
    вывод без `password=` и без токена.

    Ловит мутацию: помощник пульта отвечает на любой `get` без сверки
    `host` (подмодуль на чужом хосте получает токен слота) либо сверка
    `host` отсекает и хост самой записи.
    """
    name = stand.name()
    url = f"https://localhost/team/{name}"
    stand.declare(name, OPERATOR, url)
    clone = repo_context.clone_path(name)
    clone.mkdir(parents=True)
    git(clone, "init", "-q", "-b", "main")
    git(clone, "remote", "add", "origin", url)
    stand.spy(monkeypatch, fake_hosting=True)
    res = gitcmd.in_repo(clone, sub, "origin")
    assert res.returncode == 0, stand.note(f"{sub}: {res.stderr}")
    calls = [c for c in stand.calls if subcommand(c["argv"]) == sub]
    assert calls, stand.note(f"вызова {sub} нет")
    token = keychain.token(f"{name}-token")
    own = credential_fill(clone, calls[-1], url)
    assert f"password={token}\n" in own.stdout, \
        stand.note(f"хост записи: {own.stdout!r} {own.stderr!r}")
    other_host = f"{stand.name('h')}.example.invalid"
    other = credential_fill(clone, calls[-1], f"https://{other_host}/team/{name}")
    assert "password=" not in other.stdout, stand.note(f"иной хост: {other.stdout!r}")
    assert token not in other.stdout + other.stderr, stand.note("токен в выводе")
