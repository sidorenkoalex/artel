"""Владелец токена проекта: `gitlab_adapter.token_user` отдаёт `username`, `name` и адрес учётной записи (`commit_email`, иначе `email`) ответа `GET /user`; адаптеры других хостингов новых полей не заполняют.

Группа: долгоживущий
Красен до реализации: у `forge.TokenUser` нет полей `name` и `commit_email` — обращение к ним даёт `AttributeError`, адаптер GitLab кладёт в результат только `username`; тест «другие хостинги полей не заполняют» держит то, что уже так, и зелен с рождения.

Провалидировано временным стабом реализации (удалён, не закоммичен): все
методы зелёные.

Модульный тест без песочницы `config`: запись проекта отдаёт подменённый
`targets.target`, токен — подменённый `gitcmd.hosting_token`, ответ
`GET /user` — подменённый `gitlab_adapter.transport` (в сеть запрос не
уходит). Для хостинга без адаптера GitLab запрос `gh` подменён
(`forge.github_call`) ответом с логином, именем и адресом — заполнить поля
ему есть из чего.

Логины, имена и адреса порождаются модулем `random` при каждом запуске;
зерно печатается и входит в текст провала.
"""
import json
import random
import subprocess

import pytest

from orchestrator import forge, gitlab_adapter, targets

LETTERS = "abcdefghijkmnopqrstuvwxyz"
TOKEN = "glpat-token-user-test"


def word(rng: random.Random, prefix: str, size: int = 7) -> str:
    return prefix + "".join(rng.choice(LETTERS) for _ in range(size))


def entry(name: str, kind: str) -> dict:
    return {"forge": kind, "url": f"https://localhost/team/{name}", "base": "main",
            "token_slot": f"{name}-token", "no_paths": [], "project_skills": [],
            "merge_gate": "target-human"}


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


@pytest.fixture
def api(monkeypatch):
    """Записи проектов и ответ `GET /user`: тест кладёт тело в `state["user"]`."""
    state = {"records": {}, "user": {}, "sent": []}

    def target(name):
        if name not in state["records"]:
            raise targets.TargetsError(f"target '{name}' не объявлен")
        return state["records"][name]

    def transport(method, url, headers, body, timeout):
        state["sent"].append((method, url))
        if url.endswith("/api/v4/user"):
            return 200, {}, json.dumps(state["user"]).encode("utf-8")
        return 404, {}, b""

    monkeypatch.setattr(targets, "target", target)
    monkeypatch.setattr("orchestrator.gitcmd.hosting_token", lambda name, e: (TOKEN, None))
    monkeypatch.setattr(gitlab_adapter, "transport", transport)
    return state


def test_ac1_gitlab_token_user_carries_name_and_address(api, seed):
    """Ответ `GET /user` с `username`, `name`, `commit_email` (и отличным `email`) — все три в `TokenUser`; без `commit_email` — `email`; без обоих — адреса нет.

    Сценарий: три случайные записи GitLab; для каждой ответ API —
    случайные `username` и отображаемое `name` (различны) и адреса. При
    `commit_email` и `email` в ответе `commit_email` результата — именно
    `commit_email`; без `commit_email` — `email`; без обоих поле адреса
    пусто (`None` или пустая строка). `username` и `name` переданы как
    есть во всех трёх формах.

    Ловит мутацию: адаптер берёт `email` прежде `commit_email` (первый
    случай даст `email`); запасной `email` не читается (второй случай —
    пусто); `name` результата заполнен `username` или наоборот; поле
    адреса при пустом ответе заполнено чем-то (`username`, пустой
    `email` по умолчанию в виде текста).
    """
    rng = random.Random(seed)
    for _ in range(3):
        name = word(rng, "p")
        api["records"][name] = entry(name, "gitlab")
        username, display = word(rng, "bot-"), word(rng, "Бот ")
        commit_email = f"{word(rng, 'commit-')}@localhost"
        email = f"{word(rng, 'mail-')}@localhost"
        forms = [
            ({"username": username, "name": display, "commit_email": commit_email,
              "email": email}, commit_email),
            ({"username": username, "name": display, "email": email}, email),
            ({"username": username, "name": display}, None),
        ]
        for reply, address in forms:
            api["user"] = reply
            user = gitlab_adapter.token_user(name)
            note = f"зерно: {seed}; проект {name}; ответ {reply}; результат {user}"
            assert user.reason == "", note
            assert user.username == username, note
            assert user.name == display, note
            if address is None:
                assert not user.commit_email, note
            else:
                assert user.commit_email == address, note


def test_ac1_forge_token_user_routes_new_fields_for_gitlab(api, seed):
    """`forge.token_user` записи GitLab отдаёт те же `name` и `commit_email`, что адаптер.

    Сценарий: случайная запись `forge: gitlab`; ответ `GET /user` с
    `username`, `name`, `commit_email`. Результат `forge.token_user` несёт
    все три значения.

    Ловит мутацию: реестр `forge` пересобирает `TokenUser` только из
    `username` (новые поля теряются на пути через `forge._call`).
    """
    rng = random.Random(seed)
    name = word(rng, "p")
    api["records"][name] = entry(name, "gitlab")
    username, display = word(rng, "bot-"), word(rng, "Бот ")
    commit_email = f"{word(rng, 'commit-')}@localhost"
    api["user"] = {"username": username, "name": display, "commit_email": commit_email}
    user = forge.token_user(name)
    note = f"зерно: {seed}; проект {name}; результат {user}"
    assert (user.username, user.name, user.commit_email) == (username, display,
                                                             commit_email), note


def test_ac1_other_hostings_leave_new_fields_empty(api, monkeypatch, seed):
    """Хостинги реестра, кроме GitLab, полей `name`/`commit_email` в `forge.token_user` не заполняют.

    Сценарий: для каждого значения `forge` из `forge.IMPLEMENTATIONS`,
    реализация которого — не адаптер GitLab, — случайная запись; запрос
    `gh` подменён ответом с логином, именем и адресом, `GET /user`
    GitLab — тоже. Результат `forge.token_user` — `name` и `commit_email`
    пусты.

    Ловит мутацию: новые поля заполняются вне адаптера GitLab — общим
    путём реестра (`forge._call` дописывает адрес из ответа GitLab любому
    хостингу) или реализацией GitHub по ответу `gh api user`.
    """
    rng = random.Random(seed)
    login, display = word(rng, "gh-"), word(rng, "Имя ")
    address = f"{word(rng, 'gh-')}@localhost"
    reply = json.dumps({"login": login, "name": display, "email": address})
    monkeypatch.setattr(forge, "github_call", lambda target, *args: (
        subprocess.CompletedProcess(["gh", *args], 0, reply, "")))
    api["user"] = {"username": login, "name": display, "commit_email": address}
    others = [kind for kind, impl in forge.IMPLEMENTATIONS.items()
              if impl is not gitlab_adapter]
    assert others, f"зерно: {seed}; в реестре нет хостингов, кроме GitLab"
    for kind in others:
        name = word(rng, "p")
        api["records"][name] = entry(name, kind)
        user = forge.token_user(name)
        note = f"зерно: {seed}; хостинг {kind}; проект {name}; результат {user}"
        assert getattr(user, "name", None) is None, note
        assert getattr(user, "commit_email", None) is None, note
