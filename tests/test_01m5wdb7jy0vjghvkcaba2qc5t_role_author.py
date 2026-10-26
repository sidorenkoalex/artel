"""Автор и коммиттер окружения роли — `commit_author` записи проекта, сильнее окружения сессии.

Группа: долгоживущий
Красен до реализации: `runner.role_env` берёт идентичность из git-конфига через `setdefault`, а поле `machine.commit_author` записи локального слоя не читается вовсе — `GIT_AUTHOR_*`/`GIT_COMMITTER_*` окружения роли не равны `commit_author`.

Связка «запись проекта локального слоя — `runner.role_env`»: клон
внешнего проекта (`tests.sandbox.make_project_repo`) в настоящем git
песочницы, запись проекта — в локальном слое (`targets.local_path()`)
с `machine.commit_author`. Окружение сессии (`os.environ`) задаёт иные
`GIT_AUTHOR_*`/`GIT_COMMITTER_*` либо не задаёт их вовсе. Имена и почты —
из `random`, зерно печатается и входит в текст провала.

Стаб реализации невозможен на сегодняшнем main: поле `commit_author`
вводит часть 1 деления (зависимость мержа), без неё запись с полем не
загружается.
"""
import os
import random
from unittest import mock

import pytest

from orchestrator import config, idgen, runner, stack, store, targets
from tests.sandbox import _stub_check_stack, make_project_repo

ALPHABET = "abcdefghijklmnopqrstuvwxyz"
IDENTITY = ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
            "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")

ENTRY = """  {name}:
    description:
      base: {base}
      test_profile:
        command: [python3, -m, pytest]
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
    policy:
      no_paths: []
      project_skills: []
      merge_gate: operator
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
    machine:
      forge: github
      url: https://localhost/team/{name}
      token_slot: {name}-token
      commit_author:
        name: {author}
        email: {email}
"""


def word(rng, size=8):
    return "".join(rng.choice(ALPHABET) for _ in range(size))


@pytest.fixture
def project(real_git):
    """Проект с `commit_author` в локальном слое и задача этого проекта."""
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    name = f"proj{word(rng, 6)}"
    make_project_repo(name)
    author = f"pult{word(rng)}"
    email = f"{author}@{word(rng, 5)}.example"
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text("targets:\n" + ENTRY.format(
        name=name, base=config.MAIN_BRANCH, author=author, email=email),
        encoding="utf-8")
    conn = store.db()
    task = idgen.new_task_id()
    store.insert_task(conn, task, "Фикстура автора", "in_dev",
                      f"task/{task.lower()}-{word(rng, 5)}", name,
                      config.DEFAULT_BUDGET_USD)
    real_git.use_role_map()
    return {"name": name, "author": author, "email": email, "task": task,
            "seed": seed, "rng": rng}


@pytest.mark.parametrize("session", ["иные", "нет"])
def test_ac9_role_env_carries_commit_author(project, session):
    """Окружение роли несёт `commit_author` автором и коммиттером при любом окружении сессии.

    Сценарий: окружение сессии задаёт `GIT_AUTHOR_*`/`GIT_COMMITTER_*`
    случайными иными значениями («иные») либо не задаёт их («нет»);
    `runner.role_env` шага разработчика задачи проекта несёт все четыре
    переменные, равные имени и почте `commit_author` записи.

    Ловит мутацию: `commit_author` кладётся через `setdefault`, как
    нынешняя идентичность из git-конфига, — при «иных» окружение роли
    несёт имя и почту сессии, а не `commit_author`.
    """
    rng = project["rng"]
    if session == "иные":
        foreign = {"GIT_AUTHOR_NAME": f"сессия {word(rng)}",
                   "GIT_AUTHOR_EMAIL": f"{word(rng)}@session.example",
                   "GIT_COMMITTER_NAME": f"сессия {word(rng)}",
                   "GIT_COMMITTER_EMAIL": f"{word(rng)}@session.example"}
    else:
        foreign = {}
    note = f"зерно: {project['seed']}; окружение сессии: {session}"
    with mock.patch.dict(os.environ, foreign), \
            mock.patch.object(stack, "check_stack", _stub_check_stack):
        for name in IDENTITY:
            if name not in foreign:
                os.environ.pop(name, None)
        env = runner.role_env("developer", project["task"],
                              project=project["name"])
    expected = {"GIT_AUTHOR_NAME": project["author"],
                "GIT_AUTHOR_EMAIL": project["email"],
                "GIT_COMMITTER_NAME": project["author"],
                "GIT_COMMITTER_EMAIL": project["email"]}
    got = {name: env.get(name) for name in IDENTITY}
    assert got == expected, f"{note}: {got}"
