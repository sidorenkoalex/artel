"""Ограничения отправки в ветку отчёта базы `ci_base_branch` (`ci_base:
branch`, SPEC 01M6TT4FKD1JWSJFVJ7328K03Y, требования 2, 6): белый список
единой точки `gitcmd`, хук `pre-push` клона `target-human`, неудаление
ветки уборкой задач, отправка базы только при прочитанном конвейере.

Планка задачи — разовая; здесь — долгоживущий минимум тех же свойств
безопасности (REVIEW итерации 1, R1-F1, R1-F2). Стенд — `real_git`:
`config.ROOT` — настоящий git-репозиторий, в него закоммичен каталог
`scripts/git-hooks` проверяемого дерева. Записи проектов — в локальном
слое, `url` записи — путь голого репозитория во временном каталоге,
`HOME` — временный, переменные `GIT_*` процесса сняты, сети нет.
Отправка идёт настоящим git; ветку в `origin` тест читает `ls-remote`.
"""
import os
import shutil
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (cleanup, config, forge, gitcmd, idgen, store,
                          targets, workspace)
from orchestrator.advance_gates import outcome_integrity

REAL_RUN = subprocess.run
CODE_ROOT = Path(__file__).resolve().parent.parent
HOOK_PREFIX = "pre-push (target-human)"
REFUSED = gitcmd.PUSH_REFUSED_ACTION
CBB = "artel-base-guard"
JOB = "tests-guard"


def clean_env() -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k not in (gitcmd.PULT_MARKER_ENV,
                                                     config.ARTEL_TASK_ENV)}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git(repo: Path, *args: str, check: bool = True, env: dict | None = None):
    res = REAL_RUN(["git", "-C", str(repo), *args], capture_output=True,
                   text=True, env=env if env is not None else clean_env(),
                   timeout=60)
    if check:
        assert res.returncode == 0, f"git {' '.join(args)} в {repo}: {res.stderr}"
    return res


def out(repo: Path, *args: str) -> str:
    return git(repo, *args).stdout.strip()


def entry_text(name: str, url: str) -> str:
    lines = [f"  {name}:", "    description:",
             f"      base: {config.MAIN_BRANCH}", "      components:",
             "        unit:", "          command: [python3, -m, pytest]",
             "          report: junit-xml", "          long_lived_dir: tests",
             "          long_lived_name: test_<id>_<name>.py",
             "          full_suite: ci", f"          ci_job: {JOB}",
             "          ci_base: branch", f"          ci_base_branch: {CBB}",
             "          ci_base_push_options: [ci.variable=GUARD=1]",
             "    policy:", "      no_paths: []", "      project_skills: []",
             "      merge_gate: target-human", "      components:",
             "        unit:", "          weakening_scope: [tests/**]",
             "          mutation_claim_scope: [tests/test_*.py]",
             "    machine:", "      forge: gitlab", f"      url: {url}",
             f"      token_slot: {name}-token"]
    return "\n".join(lines) + "\n"


class Stand:
    """Проект `target-human` GitLab с компонентом `ci_base: branch` и его
    клон, заведённый пультом (`workspace.ensure_clone`)."""

    def __init__(self, monkeypatch, tmp_path: Path):
        self.tmp = tmp_path
        home = tmp_path / "home"
        home.mkdir()
        (home / ".gitconfig").write_text(
            "[user]\n\tname = artel tests\n\temail = artel@example.invalid\n"
            "[protocol \"file\"]\n\tallow = always\n"
            "[init]\n\tdefaultBranch = main\n", encoding="utf-8")
        monkeypatch.setenv("HOME", str(home))
        for name in list(os.environ):
            if name.startswith("GIT_") or name in (gitcmd.PULT_MARKER_ENV,
                                                   config.ARTEL_TASK_ENV):
                monkeypatch.delenv(name, raising=False)
        root = Path(config.ROOT)
        shutil.copytree(CODE_ROOT / "scripts" / "git-hooks",
                        root / "scripts" / "git-hooks",
                        ignore=shutil.ignore_patterns("__pycache__"),
                        dirs_exist_ok=True)
        git(root, "add", "-A", "scripts")
        git(root, "commit", "-q", "--no-verify", "-m", "хуки пульта")
        self.name = "qguard"
        self.bare = tmp_path / "qguard.git"
        git(tmp_path, "init", "-q", "--bare", "-b", config.MAIN_BRANCH,
            str(self.bare))
        seed = tmp_path / "seed"
        git(tmp_path, "init", "-q", "-b", config.MAIN_BRANCH, str(seed))
        for n in (1, 2):
            (seed / "app.py").write_text(f"APP = {n}\n", encoding="utf-8")
            git(seed, "add", "-A")
            git(seed, "commit", "-q", "--no-verify", "-m", f"коммит {n}")
        git(seed, "push", "-q", "--no-verify", str(self.bare),
            f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        local = targets.local_path()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text("targets:\n" + entry_text(self.name, str(self.bare)),
                         encoding="utf-8")
        self.clone, error = workspace.ensure_clone(self.name)
        assert error is None, error

    def older_main(self) -> str:
        return out(self.clone, "rev-parse",
                   f"refs/remotes/origin/{config.MAIN_BRANCH}~1")

    def origin_sha(self, branch: str) -> str:
        text = out(self.bare, "ls-remote", str(self.bare), f"refs/heads/{branch}")
        return text.split()[0] if text.split() else ""

    def task(self, suffix: str) -> tuple:
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-{suffix}"
        git(self.clone, "branch", "-f", branch, config.MAIN_BRANCH)
        store.insert_task(store.db(), task_id, "Задача", "in_dev", branch,
                          self.name, config.DEFAULT_BUDGET_USD)
        return task_id, branch

    def side_commit(self) -> str:
        """Коммит клона поверх `main`, которого нет в `origin`."""
        git(self.clone, "checkout", "-q", "-B", "side", config.MAIN_BRANCH)
        (self.clone / "side.py").write_text("S = 1\n", encoding="utf-8")
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-q", "--no-verify", "-m", "сбоку",
            env=dict(clean_env(), **{gitcmd.PULT_MARKER_ENV: "1"}))
        sha = out(self.clone, "rev-parse", "HEAD")
        git(self.clone, "checkout", "-q", config.MAIN_BRANCH)
        return sha

    def pult_push(self, *words: str, task_id: str | None = None):
        if task_id is None:
            return gitcmd.in_repo(self.clone, "push", *words)
        return gitcmd.in_repo(self.clone, "push", *words, task_id=task_id)


@pytest.fixture
def stand(real_git, monkeypatch, tmp_path):
    return Stand(monkeypatch, tmp_path)


def text_of(res) -> str:
    return (res.stderr or "") + (res.stdout or "")


# --- белый список: принудительная отправка ---------------------------------

def test_whitelist_force_only_when_every_refspec_goes_to_ci_base_branch(stand):
    """Принудительная отправка через `gitcmd` пропускается только когда каждый refspec идёт в `ci_base_branch`: одна она — проходит; она вместе с веткой живой задачи — отказ «флаг --force вне белого списка», в `origin` ничего не изменилось.

    Ловит мутацию: `--force` пропускается, если хоть один refspec (а не
    каждый) идёт в `ci_base_branch`, — смешанная отправка проходит и
    принудительно переписывает ветку задачи в `origin`.
    """
    sha = stand.older_main()
    res = stand.pult_push("--force", "origin", f"{sha}:refs/heads/{CBB}")
    assert res.returncode == 0, text_of(res)
    assert stand.origin_sha(CBB) == sha
    task_id, branch = stand.task("mix")
    tip = out(stand.clone, "rev-parse", f"refs/remotes/origin/{config.MAIN_BRANCH}")
    res = stand.pult_push("--force", "origin", f"{tip}:refs/heads/{CBB}",
                          f"{branch}:refs/heads/{branch}", task_id=task_id)
    assert res.returncode != 0, "смешанная принудительная отправка прошла"
    assert "флаг --force вне белого списка" in text_of(res), text_of(res)
    assert stand.origin_sha(CBB) == sha
    assert stand.origin_sha(branch) == ""


# --- белый список: источник — предок свежего origin/<base> ------------------

def test_whitelist_refuses_non_ancestor_into_ci_base_branch(stand):
    """Отправка через `gitcmd` в `ci_base_branch` sha, не являющегося предком `origin/<base>`, — отказ единой точки до git, ветки в `origin` нет.

    Ловит мутацию: белый список не проверяет источник отправки в
    `ci_base_branch` — отказ даёт только хук (нет текста отказа единой
    точки «отправка отказана»).
    """
    sha = stand.side_commit()
    res = stand.pult_push("--force", "origin", f"{sha}:refs/heads/{CBB}")
    assert res.returncode != 0, "коммит вне main ушёл в ci_base_branch"
    assert REFUSED in text_of(res), text_of(res)
    assert stand.origin_sha(CBB) == ""


def test_whitelist_checks_fresh_origin_base_not_local_tracking_ref(stand):
    """Локальная `refs/remotes/origin/<base>` клона сдвинута на коммит `X` вне `<base>` в `origin`: отправка `X` в `ci_base_branch` через `gitcmd` отказана белым списком (сверка с свежим sha `origin`), а ссылка отслеживания клона не переписана проверкой.

    Ловит мутацию: белый список сверяет предка с локальной
    `refs/remotes/origin/<base>` (или проверку предка снимает) — `X`
    проходит и белый список, и хук (он смотрит ту же локальную ссылку), `X`
    оказывается в `origin`; проверка фетчем с записью в ссылку
    отслеживания — локальная ссылка возвращена на `origin`.
    """
    x = stand.side_commit()
    ref = f"refs/remotes/origin/{config.MAIN_BRANCH}"
    git(stand.clone, "update-ref", ref, x)
    res = stand.pult_push("--force", "origin", f"{x}:refs/heads/{CBB}")
    assert res.returncode != 0, "X ушёл в ci_base_branch"
    assert REFUSED in text_of(res), text_of(res)
    assert stand.origin_sha(CBB) == ""
    assert out(stand.clone, "rev-parse", ref) == x


# --- хук pre-push: вторая линия ---------------------------------------------

def test_hook_passes_only_ancestor_of_origin_base_into_ci_base_branch(stand):
    """Прямой `git push --force` из клона мимо `gitcmd` (работает только хук): предок `origin/<base>` в `ci_base_branch` — проходит; коммит вне `origin/<base>` — отказ хука, ветка не сдвинулась.

    Ловит мутацию: хук пропускает в `ci_base_branch` любой sha (проверка
    `merge-base --is-ancestor` снята) — коммит вне `main` уходит в
    `origin`; хук не читает ключ `ci_base_branch=` — отказ первой
    отправки.
    """
    first = stand.older_main()
    res = stand.pult_push("--force", "origin", f"{first}:refs/heads/{CBB}")
    assert res.returncode == 0, text_of(res)
    tip = out(stand.clone, "rev-parse", f"refs/remotes/origin/{config.MAIN_BRANCH}")
    res = git(stand.clone, "push", "--force", "origin",
              f"{tip}:refs/heads/{CBB}", check=False)
    assert res.returncode == 0, text_of(res)
    assert stand.origin_sha(CBB) == tip
    res = git(stand.clone, "push", "--force", "origin",
              f"{stand.side_commit()}:refs/heads/{CBB}", check=False)
    assert res.returncode != 0, "хук пропустил коммит вне origin/main"
    assert HOOK_PREFIX in text_of(res), text_of(res)
    assert stand.origin_sha(CBB) == tip


# --- уборка задач не трогает ci_base_branch ---------------------------------

def test_kill_and_merged_cleanup_keep_ci_base_branch(stand):
    """`kill` задачи и уборка ветки смерженной задачи не удаляют `ci_base_branch` в `origin`.

    Ловит мутацию: уборка задачи удаляет и ветку отчёта базы проекта
    (ветки `origin` вне шаблона задач или ветку отправленной базы) —
    `ci_base_branch` в `origin` нет.
    """
    sha = stand.older_main()
    res = stand.pult_push("--force", "origin", f"{sha}:refs/heads/{CBB}")
    assert res.returncode == 0, text_of(res)
    killed, killed_branch = stand.task("kill")
    merged, merged_branch = stand.task("done")
    for branch in (killed_branch, merged_branch):
        git(stand.clone, "push", "-q", "--no-verify", "origin",
            f"{sha}:refs/heads/{branch}")
    cleanup.cmd_kill(killed, confirmed=True, reason="сценарий уборки")
    assert stand.origin_sha(CBB) == sha, "kill удалил ci_base_branch"
    cleanup.cleanup_merged_remote(
        store.db(), merged, merged_branch,
        out(stand.clone, "rev-parse", f"refs/remotes/origin/{config.MAIN_BRANCH}"))
    assert stand.origin_sha(CBB) == sha, "уборка удалила ci_base_branch"


# --- отправка базы только при прочитанном конвейере (R1-F2) -----------------

UNREAD = forge.PipelineStatus(forge.UNKNOWN, "HTTP 502 Bad Gateway",
                              http_status=502)
NO_PIPELINE = forge.PipelineStatus(forge.NONE, "у коммита нет конвейера")


@pytest.mark.parametrize("status, pushed", [(UNREAD, False),
                                            (NO_PIPELINE, True)])
def test_base_push_only_when_pipeline_read(initialized_tmp_root, status,
                                           pushed):
    """Задания базы не видно: конвейер не прочитан (`unknown`, HTTP 502) — ожидание без отправки; конвейера у коммита нет — отправка базы; в обоих случаях на `verifying` — ожидание базы (`_BasePending`).

    Ловит мутацию: сбой чтения конвейера приравнен к «задания нет вовсе» —
    при HTTP 502 пульт принудительно отправляет базу, у которой задание,
    возможно, уже идёт (лишний конвейер CI).
    """
    sha = "a" * 40
    calls = []
    with mock.patch.object(forge, "pipeline_status", return_value=status), \
            mock.patch.object(outcome_integrity, "_push_ci_base",
                              side_effect=lambda *a: calls.append(a) or "ок"):
        attempt = outcome_integrity._ci_attempt("qguard", sha, JOB)
        assert attempt.report is None and attempt.pending
        assert attempt.unread is (not pushed)
        missing = outcome_integrity._NoBaseReport("нет отчёта базы", attempt)
        with pytest.raises(outcome_integrity._BasePending):
            outcome_integrity._ci_base_unfit(store.db(), "T1", Path("."),
                                             "qguard", {}, sha, missing, True)
    assert bool(calls) is pushed, calls
