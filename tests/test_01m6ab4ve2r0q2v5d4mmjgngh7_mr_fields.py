"""Поля `forge.MergeRequest` о ветках и коммитах MR: `gitlab_adapter.mr_status` переносит их из ответа GitLab.

Группа: долгоживущий
Красен до реализации: у `forge.MergeRequest` нет полей `target_branch`, `source_branch`, `sha`, `merge_commit_sha`, `squash_commit_sha` — `getattr` результата `mr_status` падает `AttributeError`.

Окружение — подмены публичных точек: `gitlab_adapter.transport` —
поддельный сервер GitLab API v4 (ответ на
`GET /projects/:id/merge_requests/:n`), `targets.target` — запись проекта
`forge: gitlab`, `keychain.token` — токен слота записи, окружение без роли.
Свойство — чистый разбор ответа адаптером, без песочницы git.

Значения полей ответа (имена веток, sha, iid) порождаются модулем `random`
при каждом запуске; зерно печатается и входит в текст провала.

Провалидировано временным стабом (удалён, не закоммичен): пять полей
`MergeRequest` с умолчанием `None` и их перенос в `_merge_request` — оба
метода зелёные.
"""
import json
import random
import urllib.parse

import pytest

from orchestrator import config, forge, gitlab_adapter, keychain, targets

GL = "glfields"
FIELDS = ("target_branch", "source_branch", "sha", "merge_commit_sha",
          "squash_commit_sha")
HEX = "0123456789abcdef"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"


class Server:
    """Поддельный GitLab: на GET MR отвечает телом `self.mr`, иное — 404."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.iid = rng.randrange(1, 10 ** 5)
        self.mr: dict = {}
        self.calls: list = []

    def transport(self, method, url, headers=None, body=None, timeout=None,
                  *args, **kwargs):
        path = urllib.parse.urlsplit(url).path
        self.calls.append((str(method).upper(), path))
        head = {"Content-Type": "application/json"}
        if str(method).upper() == "GET" and path.endswith(
                f"/merge_requests/{self.iid}"):
            return 200, head, json.dumps(self.mr).encode("utf-8")
        return 404, head, json.dumps({"message": "404 Not Found"}).encode("utf-8")

    def target(self, name: str) -> dict:
        if name != GL:
            raise targets.TargetsError(f"target '{name}' не объявлен (тест)")
        return {"forge": "gitlab", "url": f"https://localhost/grp/{GL}",
                "base": config.MAIN_BRANCH, "token_slot": f"{GL}-token",
                "no_paths": [], "project_skills": [], "merge_gate": "operator"}


@pytest.fixture
def server(monkeypatch):
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    fake = Server(random.Random(seed))
    fake.seed = seed
    monkeypatch.setenv(config.ARTEL_ROLE_ENV, "")
    monkeypatch.setattr(gitlab_adapter, "transport", fake.transport)
    monkeypatch.setattr(targets, "target", fake.target)
    monkeypatch.setattr(keychain, "token", lambda *a, **k: "glpat-fixture")
    return fake


def sha(rng: random.Random) -> str:
    return "".join(rng.choice(HEX) for _ in range(40))


def word(rng: random.Random) -> str:
    return "".join(rng.choice(ALPHABET) for _ in range(7))


def base_reply(server: Server) -> dict:
    return {"iid": server.iid, "title": f"MR {word(server.rng)}",
            "state": server.rng.choice(["opened", "merged", "closed"]),
            "draft": False,
            "web_url": f"https://localhost/grp/{GL}/-/merge_requests/{server.iid}"}


def test_ac1_mr_status_carries_branch_and_commit_fields(server):
    """Ответ GitLab с `target_branch`, `source_branch`, `sha`, `merge_commit_sha`, `squash_commit_sha` — одноимённые поля результата `mr_status` равны им.

    Сценарий: подделка сервера отвечает на GET MR телом с пятью полями
    (случайные имена веток и sha, у `merge_commit_sha`/`squash_commit_sha`
    — разные значения). `forge.mr_status` записи `forge: gitlab`
    возвращает `MergeRequest`, каждое из пяти полей которого равно
    значению своего ключа ответа; прежние поля (`iid`, `state`) тоже
    разобраны, причины отказа нет.

    Ловит мутацию: поле перенесено из соседнего ключа (`sha` из
    `merge_commit_sha`, `source_branch` из `target_branch`) — значение
    поля результата другое; либо поле не перенесено вовсе — `None`.
    """
    rng = server.rng
    reply = base_reply(server)
    expected = {"target_branch": f"base-{word(rng)}",
                "source_branch": f"task/{word(rng)}", "sha": sha(rng),
                "merge_commit_sha": sha(rng), "squash_commit_sha": sha(rng)}
    reply.update(expected)
    server.mr = reply
    result = forge.mr_status(GL, server.iid)
    note = f"зерно: {server.seed}; ответ {reply}; результат {result}"
    assert result.reason == "", note
    assert result.iid == server.iid and result.state == reply["state"], note
    for name in FIELDS:
        assert getattr(result, name) == expected[name], f"{note}; поле {name}"


@pytest.mark.parametrize("absent", ["все", "часть"])
def test_ac1_missing_fields_are_none(server, absent):
    """Ответ GitLab без полей о ветках и коммитах — эти поля результата `mr_status` равны `None`.

    Сценарий: «все» — тело ответа без всех пяти ключей; «часть» —
    случайная часть ключей есть, остальных нет. Отсутствующие в ответе
    поля результата — `None`, присутствующие — значения ответа; созданный
    без аргументов `forge.MergeRequest()` несёт все пять полей `None`.

    Ловит мутацию: отсутствующий ключ даёт пустую строку или значение
    соседнего ключа вместо `None`; либо у полей `MergeRequest` нет
    умолчания `None` (создание без аргументов падает или даёт иное).
    """
    rng = server.rng
    reply = base_reply(server)
    present = set()
    if absent == "часть":
        present = set(rng.sample(FIELDS, rng.randint(1, len(FIELDS) - 1)))
    values = {name: (f"b-{word(rng)}" if "branch" in name else sha(rng))
              for name in present}
    reply.update(values)
    server.mr = reply
    result = forge.mr_status(GL, server.iid)
    note = f"зерно: {server.seed}; ответ {reply}; результат {result}"
    assert result.reason == "", note
    for name in FIELDS:
        assert getattr(result, name) == values.get(name), f"{note}; поле {name}"
    empty = forge.MergeRequest()
    for name in FIELDS:
        assert getattr(empty, name) is None, f"{note}; умолчание {name}"
