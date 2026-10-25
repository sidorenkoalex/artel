"""Свой игнор рабочей копии без обвязки (`core.excludesFile` её
`config.worktree`, SPEC 01M5T19041XE2KB6A52F0AT0NF, требование 9) не теряет
игнор, действовавший до него: глобальный файл игнора git.

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`, фикстура
`real_git`), внешний проект — клон с bare `origin`
(`tests.sandbox.make_project_repo`). Глобальный конфиг git подменён пустым
файлом (`GIT_CONFIG_GLOBAL`), глобальный игнор — `$XDG_CONFIG_HOME/git/ignore`
во временном каталоге.
"""
import os
from unittest import mock

import pytest

from orchestrator import config, idgen, store, workspace
from tests.sandbox import artel_target_entry, make_project_repo

EXT = "vnesh"
EXT_ENTRY = """  vnesh:
    forge: github
    url: http://localhost/vnesh
    base: main
    token_slot: vnesh-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


@pytest.fixture
def sb(real_git, tmp_path):
    (tmp_path / "git").mkdir()
    (tmp_path / "git" / "ignore").write_text("*.dsstore\n", encoding="utf-8")
    (tmp_path / "gitconfig").write_text("", encoding="utf-8")
    with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "",
                                      "XDG_CONFIG_HOME": str(tmp_path),
                                      "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig")}):
        yield real_git


def test_global_ignore_survives_own_excludes_file(sb):
    """Файл, игнорируемый глобальным игнором git, остаётся игнорируемым в копии без обвязки, а неотслеживаемый файл обвязки — тоже.

    Сценарий: в `main` проекта — `src/m.py` и `CLAUDE.md`; `ensure` задачи;
    в копии появились `src/x.dsstore` (под глобальным игнором) и
    `.claude/settings.local.json` (под обвязкой) — `git status --porcelain`
    пуст.

    Ловит мутацию: свой файл игнора копии пишется без текста прежнего
    глобального игнора (`_inherited_excludes` не дописан) — `src/x.dsstore`
    виден неотслеживаемым и попал бы в `git add -A` чекпоинта.
    """
    clone = make_project_repo(EXT)
    config.TARGETS.write_text("targets:\n" + artel_target_entry() + EXT_ENTRY,
                              encoding="utf-8")
    for rel in ("src/m.py", "CLAUDE.md"):
        (clone / rel).parent.mkdir(parents=True, exist_ok=True)
        (clone / rel).write_text(f"{rel}\n", encoding="utf-8")
    sb.git("-C", str(clone), "add", "-A")
    sb.git("-C", str(clone), "commit", "-q", "-m", "проект")
    sb.git("-C", str(clone), "push", "-q", "origin", config.MAIN_BRANCH)
    task_id = idgen.new_task_id()
    branch = f"task/{task_id.lower()}-ign"
    store.insert_task(store.db(), task_id, "Фикстура игнора", "in_dev", branch,
                      EXT, config.DEFAULT_BUDGET_USD)
    wt, error = workspace.ensure(task_id, branch)
    assert error is None, error
    assert not (wt / "CLAUDE.md").exists()
    (wt / "src" / "x.dsstore").write_text("x\n", encoding="utf-8")
    (wt / ".claude").mkdir()
    (wt / ".claude" / "settings.local.json").write_text("{}\n", encoding="utf-8")
    assert sb.git("-C", str(wt), "status", "--porcelain") == ""
