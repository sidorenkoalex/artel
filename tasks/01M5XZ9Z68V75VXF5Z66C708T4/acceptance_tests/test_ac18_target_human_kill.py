"""`kill` задачи проекта `target-human` после первой отправки её ветки: сервер не трогается, локальные хвосты убираются, ссылка на MR — в журнале.

Группа: разовый
Красен до реализации: `kill` задачи внешнего проекта зовёт удаление ветки в `origin` (`push origin --delete <ветка>`) — у проекта `target-human` его отказывает белый список отправок записью «отправка отказана», а у GitHub ещё и `gh pr close`; ссылки на MR в журнале нет (столбцов `mr_iid`/`mr_url` нет — `store.update_task` отказывает).

Связка «команда `kill` — FSM — база — git»: пульт — настоящий
git-репозиторий (`origin_real_git`) со своим bare-`origin`; внешний проект
`target-human` — клон по адресу `repo_context.resolve(<проект>).path` со
своим bare-`origin`, в котором уже есть ветка задачи (первая отправка) и
`refs/artifacts/<id>`. У задачи — рабочая копия (`git worktree add` по
адресу `workspace.path`), локальная ветка в клоне и локальный каталог
`config.TASKS/<id>`. Поддержка `target-human`/`gitlab` — подменой
`targets.SUPPORTED_MERGE_GATES`/`SUPPORTED_FORGES` в тесте. Шпионы:
обёртки `gitcmd.git`/`gitcmd.in_repo` (argv каждого вызова), `ci.gh`
(вызовы `gh`, ответ — успех), `gitlab_adapter.transport` (запросы к
GitLab, ответ — отказ). Имя проекта, id задачи, номер и адрес MR — из
`random`, зерно печатается и входит в текст провала.

Группа разовая не по природе свойства, а по правилу долгоживущих файлов:
им запрещены импорт `orchestrator.gitcmd` и вызов git через `subprocess`
(`scripts/guard.py`, признак «git-история — факт задачи»), а критерий
требует шпиона argv `gitcmd.git`/`gitcmd.in_repo` и настоящего git.
"""
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from orchestrator import (ci, cleanup, config, gitcmd, gitlab_adapter, repo_context,
                          store, targets, workspace)
from tests.sandbox import ARTEL_TEST_PROFILE, capture

ID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnopqrstuvwxyz"
REAL_RUN = subprocess.run

# (состояние задачи на момент kill, запись «ветка отправлена» старого вида)
CASES = [
    ("in_dev", False), ("in_dev", True), ("verifying", False),
    ("review", False), ("acceptance", False), ("merge_gate", False),
    ("awaiting_human", False), ("escalated", False),
]


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


class Stand:
    """Пульт, проект `target-human` с `forge` и его задача после первой
    отправки ветки."""

    def __init__(self, sb, seed: int, forge: str, monkeypatch):
        self.sb = sb
        self.seed = seed
        self.rng = random.Random(seed)
        self.forge = forge
        sb.add_origin()
        sb.git("push", "-q", "origin", f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.target = "h" + "".join(self.rng.choice(LETTERS) for _ in range(7))
        entry = (f"  {self.target}:\n    forge: {forge}\n"
                 f"    url: https://localhost/team/{self.target}\n"
                 f"    base: {config.MAIN_BRANCH}\n"
                 f"    token_slot: {self.target}-token\n"
                 f"    no_paths: []\n    project_skills: []\n"
                 f"    merge_gate: target-human\n")
        config.TARGETS.write_text(
            "targets:\n"
            f"  {config.DEFAULT_TARGET}:\n    forge: github\n"
            f"    url: https://localhost/team/{config.DEFAULT_TARGET}\n"
            f"    base: {config.MAIN_BRANCH}\n"
            f"    token_slot: {config.DEFAULT_TARGET}-token\n"
            f"    no_paths: []\n    project_skills: []\n"
            f"    merge_gate: operator\n" + ARTEL_TEST_PROFILE + entry,
            encoding="utf-8")
        monkeypatch.setattr(targets, "SUPPORTED_MERGE_GATES",
                            ("operator", "target-human"))
        monkeypatch.setattr(targets, "SUPPORTED_FORGES", ("github", "gitlab"))
        assert targets.target(self.target)["merge_gate"] == "target-human"

        self.calls = []
        real_git, real_in_repo = gitcmd.git, gitcmd.in_repo

        def spy_git(*args, **kwargs):
            self.calls.append(list(args))
            return real_git(*args, **kwargs)

        def spy_in_repo(repo, *args, **kwargs):
            self.calls.append(["-C", str(repo), *args])
            return real_in_repo(repo, *args, **kwargs)

        monkeypatch.setattr(gitcmd, "git", spy_git)
        monkeypatch.setattr(gitcmd, "in_repo", spy_in_repo)
        self.gh_calls = []

        def fake_gh(*args, **kwargs):
            self.gh_calls.append(list(args))
            return subprocess.CompletedProcess(["gh", *args], 0, "", "")

        monkeypatch.setattr(ci, "gh", fake_gh)
        self.gitlab_requests = []

        def fake_transport(method, url, headers, body, timeout):
            self.gitlab_requests.append((method, url, body))
            raise OSError("GitLab в песочнице недоступен")

        monkeypatch.setattr(gitlab_adapter, "transport", fake_transport)

        self.clone = Path(repo_context.resolve(self.target).path)
        self.clone.mkdir(parents=True, exist_ok=True)
        self.pgit("init", "-q", "-b", config.MAIN_BRANCH)
        self.pgit("config", "user.email", "project@example.invalid")
        self.pgit("config", "user.name", "project tests")
        (self.clone / "README.md").write_text("проект\n", encoding="utf-8")
        self.pgit("add", "README.md")
        self.pgit("commit", "-q", "-m", "init")
        self.bare = sb.root.parent / f"{sb.root.name}-{self.target}-origin.git"
        REAL_RUN(["git", "init", "-q", "--bare", "-b", config.MAIN_BRANCH,
                  str(self.bare)], check=True, capture_output=True)
        sb.addCleanup(shutil.rmtree, self.bare, ignore_errors=True)
        self.pgit("remote", "add", "origin", str(self.bare))
        self.pgit("push", "-q", "origin", f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def why(self, text: str) -> str:
        return f"{text} (зерно {self.seed}, проект {self.target}, forge {self.forge})"

    def pgit(self, *args: str) -> str:
        return REAL_RUN(["git", "-C", str(self.clone), *args], check=True,
                        capture_output=True, text=True).stdout.strip()

    def origin_has(self, ref: str) -> bool:
        return bool(REAL_RUN(["git", "--git-dir", str(self.bare), "for-each-ref", ref],
                             check=True, capture_output=True, text=True).stdout.strip())

    def clone_has(self, ref: str) -> bool:
        return bool(self.pgit("for-each-ref", ref))

    def task(self, state: str, legacy: bool) -> dict:
        """Задача в `state`: ветка с коммитом отправлена в `origin` проекта
        (запись «ветка отправлена» текущего или старого вида), ссылка
        документов — в клоне и в `origin`, рабочая копия, локальный каталог
        задачи и ссылка на MR в БД."""
        task_id = "01UNITHUMAN" + "".join(self.rng.choice(ID_ALPHABET) for _ in range(11))
        branch = f"task/{task_id.lower()}-x"
        self.pgit("checkout", "-q", "-b", branch, config.MAIN_BRANCH)
        (self.clone / f"{task_id}.txt").write_text("работа\n", encoding="utf-8")
        self.pgit("add", f"{task_id}.txt")
        self.pgit("commit", "-q", "-m", f"{task_id}: работа")
        sha = self.pgit("rev-parse", "HEAD")
        self.pgit("checkout", "-q", config.MAIN_BRANCH)
        self.pgit("push", "-q", "origin", branch)
        docs = self.sb.root.parent / f"{self.sb.root.name}-docs-{task_id}"
        (docs / "tasks" / task_id).mkdir(parents=True)
        (docs / "tasks" / task_id / "SPEC.md").write_text("спека\n", encoding="utf-8")
        for args in (("init", "-q"), ("add", "-A"),
                     ("-c", "user.name=t", "-c", "user.email=t@t.invalid",
                      "commit", "-q", "-m", f"{task_id}: документы")):
            REAL_RUN(["git", "-C", str(docs), *args], check=True, capture_output=True)
        self.sb.addCleanup(shutil.rmtree, docs, ignore_errors=True)
        ref = f"refs/artifacts/{task_id}"
        self.pgit("fetch", "-q", str(docs), f"HEAD:{ref}")
        self.pgit("push", "-q", "origin", f"{ref}:{ref}")

        store.insert_task(store.db(), task_id, "Задача проекта", "in_dev",
                          branch, self.target, 25.0)
        action = gitcmd.PUSH_SENT_LEGACY_ACTION if legacy else gitcmd.PUSH_SENT_ACTION
        store.journal(store.db(), task_id, "orchestrator", action, f"{sha} {branch}")
        wt = workspace.path(task_id, self.target)
        wt.parent.mkdir(parents=True, exist_ok=True)
        self.pgit("worktree", "add", "-q", str(wt), branch)
        tdir = config.TASKS / task_id
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "NOTE.md").write_text("локальная копия\n", encoding="utf-8")
        iid = self.rng.randrange(2, 10 ** 5)
        url = f"https://localhost/team/{self.target}/-/merge_requests/{iid}"
        store.update_task(store.db(), task_id, mr_iid=iid, mr_url=url)
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
        conn.commit()
        return {"id": task_id, "branch": branch, "ref": ref, "wt": wt,
                "tdir": tdir, "url": url, "iid": iid}


@pytest.fixture
def stand_for(origin_real_git, seed, monkeypatch):
    return lambda forge: Stand(origin_real_git, seed, forge, monkeypatch)


def is_delete_push(argv: list) -> bool:
    if "push" not in argv:
        return False
    tail = argv[argv.index("push") + 1:]
    return "--delete" in tail or "-d" in tail or any(
        w.startswith(":") or w.startswith("+:") for w in tail)


@pytest.mark.parametrize("forge", ["gitlab", "github"])
@pytest.mark.parametrize("state,legacy", CASES,
                         ids=[f"{s}{'-legacy' if old else ''}" for s, old in CASES])
def test_ac18_kill_target_human_keeps_server_cleans_local(stand_for, forge, state, legacy):
    """`kill` задачи `target-human` после первой отправки: ни удаления ветки на сервере, ни закрытия MR/PR; локальные хвосты убраны; ссылка MR — в журнале.

    Сценарий: проект `target-human` (`forge` gitlab или github), задача в
    одном из состояний после первой отправки ветки — `in_dev` (после
    возврата, в том числе с записью «ветка отправлена» старого вида без
    двоеточия), `verifying`, `review`, `acceptance`, `merge_gate`,
    `awaiting_human`, `escalated`; у задачи ссылка на MR (`mr_iid`,
    `mr_url`). `cleanup.cmd_kill(id)`:
    - задача в `killed`;
    - среди argv `gitcmd.git`/`gitcmd.in_repo` нет отправки с `--delete`
      (и удаления формой `:<ветка>`); в журнале задачи нет записи
      «отправка отказана»;
    - `gh pr close` не звался; к GitLab не было запросов, меняющих MR
      (только чтение `GET`, если оно вообще было);
    - ветка задачи в `origin` проекта на месте;
    - рабочая копия, локальная ветка в клоне и каталог `config.TASKS/<id>`
      убраны;
    - `refs/artifacts/<id>` на месте в клоне и в `origin`;
    - адрес MR (`mr_url`) есть в журнале задачи.

    Ловит мутацию: признак «ветка отправлена» берётся перечнем состояний
    (например только `awaiting_human`/`merge_gate`), а не записью журнала —
    в `in_dev`/`review` уборка зовёт `push --delete`; запись старого вида
    без двоеточия не узнаётся — в варианте `in_dev-legacy` удаление
    попытается уйти и будет отказано белым списком; исключение
    `target-human` сделано только для GitHub (закрытие PR) — на GitLab
    удаление ветки остаётся; `gh pr close` по-прежнему зовётся; ссылка MR
    в журнал не пишется; под исключение попала и локальная уборка —
    рабочая копия или ветка остаются.
    """
    st = stand_for(forge)
    t = st.task(state, legacy)
    assert st.origin_has(f"refs/heads/{t['branch']}"), st.why("предусловие: ветка в origin")
    assert t["wt"].exists() and t["tdir"].exists(), st.why("предусловие: хвосты на месте")
    st.calls.clear()
    rows_before = len(store.task_steps(store.db(), t["id"]))

    out = capture(cleanup.cmd_kill, t["id"])

    rows = store.task_steps(store.db(), t["id"])
    journal = "\n".join(f"{r['action']} | {r['detail'] or ''}" for r in rows)
    assert store.get_task(store.db(), t["id"])["state"] == "killed", st.why(out)
    deletes = [c for c in st.calls if is_delete_push(c)]
    assert deletes == [], st.why(f"kill пытался удалить ветку на сервере: {deletes}")
    refused = [r["detail"] for r in rows[rows_before:]
               if r["action"] == gitcmd.PUSH_REFUSED_ACTION]
    assert refused == [], st.why(f"в журнале «отправка отказана»: {refused}")
    closes = [c for c in st.gh_calls if "close" in c]
    assert closes == [], st.why(f"PR закрыт: {closes}")
    changing = [r for r in st.gitlab_requests if r[0] != "GET"]
    assert changing == [], st.why(f"запросы к GitLab, меняющие MR: {changing}")
    assert st.origin_has(f"refs/heads/{t['branch']}"), st.why("ветка удалена в origin")
    assert not t["wt"].exists(), st.why(f"рабочая копия осталась:\n{out}\n{journal}")
    assert not st.clone_has(f"refs/heads/{t['branch']}"), st.why(
        f"локальная ветка осталась:\n{out}\n{journal}")
    assert not t["tdir"].exists(), st.why(f"каталог задачи остался:\n{out}\n{journal}")
    assert st.clone_has(t["ref"]), st.why("ссылки документов нет в клоне")
    assert st.origin_has(t["ref"]), st.why("ссылки документов нет в origin")
    assert t["url"] in journal, st.why(f"ссылки MR нет в журнале:\n{journal}")
