"""Заголовок MR задачи внешнего проекта по `policy.mr_title_template`: черновой MR через транспорт адаптера GitLab и `gh pr create`.

Группа: долгоживущий
Красен до реализации: поля `mr_title_template` нет в `targets.LOCAL_FIELDS["policy"]` — запись проекта с ним не загружается («неизвестное поле»), MR не открывается; методы AC-2 (запись без поля) зелены с рождения — они держат прежний заголовок `<id>: <название>`.

Два пути открытия MR — две песочницы:

- путь (а), черновой MR через `forge.open_mr` (`github_adapter.
  ensure_forge_draft_mr`/`open_forge_mr`) на хостинге GitLab — песочница
  `initialized_tmp_root` (пути `config` во временном каталоге, БД после
  `init`); `gitlab_adapter.request` подменён сервером-дублёром в процессе
  теста (`GitLabDouble`: хранит MR и их заголовки, отвечает на POST/GET/PUT
  MR), `gitlab_adapter.transport` закрыт — сети нет; `forge.open_mr` не
  подменяется. Связка: «адаптер задачи — `forge` — адаптер GitLab —
  транспорт»;
- путь (б), `gh pr create` (`github_adapter.ensure_draft_mr`) на хостинге
  GitHub без гейта людей проекта — песочница `real_git` (настоящий git):
  клон проекта `make_project_repo` с голым `origin` рядом, ветка задачи с
  коммитом над базой; `ci.gh` подменён шпионом (`FakeGh`), отправка ветки
  уходит в локальный голый `origin`. Связка: «адаптер задачи — git клона —
  `gh`».

Записи проектов — в локальном слое песочницы (`targets.local_path()`);
настоящий локальный слой пульта не читается. Имена проектов, систем
ссылок, ключи и названия задач — от зерна `random`; зерно печатается и
входит в текст провала.

Провалидировано временным стабом (удалён, не закоммичен): поле в
`LOCAL_FIELDS["policy"]`/`DELIVERY_POLICY_FIELDS` с проверкой, сборка
заголовка по шаблону в обоих местах (`{id}`, `{ref}`, `{title}` по
порядку; без ссылки — умолчание и запись журнала) — все методы зелёные.
"""
import random
import re
import subprocess

import pytest

from orchestrator import (ci, config, forge, github_adapter, gitlab_adapter,
                          idgen, store)
from orchestrator import targets
from tests.sandbox import make_project_repo

LETTERS = "abcdefghijkmnopqrstuvwxyz"
DRAFT = "Draft: "
NOT_APPLIED = "шаблон заголовка MR не применён"
TEMPLATE = "{ref}: {title}"

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
      merge_gate: {gate}
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
{policy}    machine:
      forge: {forge}
      url: "{url}"
      token_slot: {name}-token
"""


class Seed:
    """Зерно сценария: печатается и входит в текст провала."""

    def __init__(self):
        self.value = random.randrange(1 << 30)
        print(f"зерно: {self.value}")
        self.rng = random.Random(self.value)

    def msg(self, text) -> str:
        return f"зерно: {self.value}; {text}"

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def key(self) -> str:
        return f"{self.word(3).upper()}-{self.rng.randrange(1, 10 ** 4)}"


def write_entry(name: str, *, forge_name: str, gate: str,
                system: str | None, template: str | None) -> None:
    """Запись проекта в локальном слое песочницы; `system` — `ref_required`, `template` — `mr_title_template` (None — поля нет)."""
    lines = f"      ref_required: {system}\n" if system else ""
    if template is not None:
        lines += f'      mr_title_template: "{template}"\n'
    host = "grp" if forge_name == "gitlab" else "own"
    text = ENTRY.format(name=name, base=config.MAIN_BRANCH, gate=gate,
                        policy=lines, forge=forge_name,
                        url=f"https://localhost/{host}/{name}")
    path = targets.local_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("targets:\n" + text, encoding="utf-8")


def new_task(conn, target: str, title: str, state: str, branch: str) -> str:
    task = idgen.new_task_id()
    store.insert_task(conn, task, title, state, branch, target,
                      config.DEFAULT_BUDGET_USD)
    return task


def add_ref(conn, task: str, system: str, key: str, at: str) -> None:
    store.insert_external_ref(conn, store.REF_KIND_TASK, task, system, key,
                              None, "test", at)


def journal_pairs(conn, task: str) -> list:
    return [(r["action"], r["detail"]) for r in store.task_steps(conn, task)]


# ------------------------------------------------------------ путь (а)

class GitLabDouble:
    """Сервер-дублёр на месте `gitlab_adapter.request`: хранит MR проекта (заголовок, признак черновика)."""

    def __init__(self, rng: random.Random):
        self.next_iid = rng.randrange(1, 10 ** 4)
        self.mrs: dict = {}
        self.calls: list = []

    def request(self, target, method, path, body=None):
        method = str(method).upper()
        self.calls.append((method, path, body))
        raw = path.partition("?")[0]
        if method == "POST" and raw.endswith("/merge_requests"):
            iid = self.next_iid
            self.next_iid += 1
            self.mrs[iid] = {
                "iid": iid, "title": body["title"], "state": "opened",
                "web_url": f"https://localhost/grp/{target}/-/merge_requests/{iid}",
                "source_branch": body["source_branch"],
                "target_branch": body["target_branch"]}
            return gitlab_adapter.Reply(201, {}, self.view(iid))
        found = re.search(r"/merge_requests/([0-9]+)$", raw)
        if found and int(found.group(1)) in self.mrs:
            iid = int(found.group(1))
            if method == "GET":
                return gitlab_adapter.Reply(200, {}, self.view(iid))
            if method == "PUT":
                self.mrs[iid].update(body or {})
                return gitlab_adapter.Reply(200, {}, self.view(iid))
        return gitlab_adapter.Reply(404, {}, None,
                                    reason=f"не найдено (404): {method} {path}")

    def view(self, iid: int) -> dict:
        mr = dict(self.mrs[iid])
        mr["draft"] = mr["title"].startswith(DRAFT)
        return mr

    def titles(self) -> list:
        return [mr["title"] for mr in self.mrs.values()]


class GitLabLab:
    """Песочница пути (а): проект GitLab с гейтом людей проекта, дублёр `request`."""

    def __init__(self, monkeypatch):
        self.seed = Seed()
        self.conn = store.db()
        self.server = GitLabDouble(self.seed.rng)

        def closed_transport(*args, **kwargs):
            raise OSError("транспорт GitLab закрыт сценарием теста")

        monkeypatch.setattr(gitlab_adapter, "request", self.server.request)
        monkeypatch.setattr(gitlab_adapter, "transport", closed_transport)
        self.name = "gl" + self.seed.word()

    def project(self, system: str | None, template: str | None) -> None:
        write_entry(self.name, forge_name="gitlab", gate="target-human",
                    system=system, template=template)

    def task(self, title: str) -> str:
        branch = f"task/{self.seed.word()}-{self.seed.word()}"
        return new_task(self.conn, self.name, title, "in_dev", branch)

    def open_draft(self, task: str):
        return github_adapter.ensure_forge_draft_mr(
            self.conn, task, store.get_task(self.conn, task))

    def note(self, task: str, res=None) -> str:
        return self.seed.msg(f"результат {res!r}; MR {self.server.mrs}; "
                             f"журнал {journal_pairs(self.conn, task)}")


@pytest.fixture
def gl(initialized_tmp_root, monkeypatch):
    return GitLabLab(monkeypatch)


def test_ac1_gitlab_draft_title_by_template_and_undraft(gl):
    """Черновой MR GitLab по шаблону `{ref}: {title}` — у дублёра `Draft: <ключ>: <название>`, после снятия черновика — `<ключ>: <название>`.

    Сценарий: запись GitLab с `ref_required: tracker` и
    `mr_title_template: "{ref}: {title}"`, задача со ссылкой
    `tracker:<ключ>`; `ensure_forge_draft_mr` открывает черновой MR —
    дублёр хранит один MR с заголовком `Draft: <ключ>: <название>`;
    `forge.undraft_mr` тем же транспортом снимает черновик — заголовок у
    дублёра `<ключ>: <название>`.

    Ловит мутацию: путь `forge.open_mr` собирает заголовок прежней
    формулой `<id>: <название>` (шаблон применён только к `gh pr create`)
    — у дублёра `Draft: <id>: …`; `{ref}` подставлен пустым или id задачи;
    шаблон применён и к префиксу (`<ключ>: Draft: …`).
    """
    gl.project("tracker", TEMPLATE)
    title = f"Задача {gl.seed.word()} {gl.seed.word()}"
    task = gl.task(title)
    key = gl.seed.key()
    add_ref(gl.conn, task, "tracker", key, store.now())
    res = gl.open_draft(task)
    assert res is None, gl.note(task, res)
    assert gl.server.titles() == [f"{DRAFT}{key}: {title}"], gl.note(task, res)
    iid = next(iter(gl.server.mrs))
    undrafted = forge.undraft_mr(gl.name, iid)
    assert not undrafted.reason, gl.note(task, undrafted)
    assert gl.server.titles() == [f"{key}: {title}"], gl.note(task, undrafted)


@pytest.mark.parametrize("empty_title", [False, True])
def test_ac2_forge_mr_without_field_keeps_old_title(gl, empty_title):
    """Запись без `mr_title_template`: MR через `forge.open_mr` — заголовок побайтно `<id>: <название>`, при пустом названии — `<id>: <id>`.

    Сценарий: запись GitLab с `ref_required` и без поля шаблона, у задачи
    есть ссылка системы; `open_forge_mr(draft=False)` — у дублёра один MR
    с заголовком `<id>: <название>` (или `<id>: <id>` при пустом
    названии).

    Ловит мутацию: умолчание шаблона — не `{id}: {title}` (например
    `{ref}: {title}` или id в нижнем регистре) — заголовок другой; пустое
    название даёт `<id>: ` вместо `<id>: <id>`.
    """
    system = "sys" + gl.seed.word(3)
    gl.project(system, None)
    title = "" if empty_title else f"Задача {gl.seed.word()}"
    task = gl.task(title)
    add_ref(gl.conn, task, system, gl.seed.key(), store.now())
    res = github_adapter.open_forge_mr(gl.conn, task, store.get_task(gl.conn, task),
                                       "", draft=False)
    assert not res.reason, gl.note(task, res)
    assert gl.server.titles() == [f"{task}: {title or task}"], gl.note(task, res)


@pytest.mark.parametrize("other_ref", [False, True])
@pytest.mark.parametrize("random_system", [False, True])
def test_ac6_gitlab_draft_without_ref_falls_back_and_journals(gl, other_ref,
                                                              random_system):
    """Путь (а): шаблон с `{ref}`, а ссылки системы `ref_required` у задачи нет — черновой MR `Draft: <id>: <название>`, запись журнала с действием и причиной, задача не остановлена.

    Сценарий: запись GitLab с `ref_required: <система>` (`tracker` или
    случайное имя) и `mr_title_template: "{ref}: {title}"`; у задачи нет
    ссылок либо есть ссылка другой системы. `ensure_forge_draft_mr`
    возвращает None (MR открыт), у дублёра один MR `Draft: <id>:
    <название>`; в журнале задачи есть запись с действием `шаблон
    заголовка MR не применён` и причиной `нет ссылки системы <система>`;
    состояние задачи прежнее.

    Ловит мутацию: без ссылки `{ref}` подставлен пустым — заголовок
    `Draft: : <название>`; ключ берётся из ссылки любой системы — заголовок
    с чужим ключом; запись журнала не пишется или называет не ту систему;
    отсутствие ссылки ведёт к отказу открытия MR (результат — причина,
    MR у дублёра нет).
    """
    system = ("sys" + gl.seed.word(3)) if random_system else "tracker"
    gl.project(system, TEMPLATE)
    title = f"Задача {gl.seed.word()}"
    task = gl.task(title)
    if other_ref:
        add_ref(gl.conn, task, "other" + gl.seed.word(3), gl.seed.key(),
                store.now())
    res = gl.open_draft(task)
    assert res is None, gl.note(task, res)
    assert gl.server.titles() == [f"{DRAFT}{task}: {title}"], gl.note(task, res)
    assert (NOT_APPLIED, f"нет ссылки системы {system}") in journal_pairs(
        gl.conn, task), gl.note(task, res)
    assert store.get_task(gl.conn, task)["state"] == "in_dev", gl.note(task, res)


# ------------------------------------------------------------ путь (б)

class FakeGh:
    """Шпион `ci.gh`: позиционные аргументы вызова — в `calls`; `pr create` отвечает адресом PR."""

    def __init__(self):
        self.calls: list = []

    def __call__(self, *args, **kwargs):
        argv = [str(a) for a in args]
        self.calls.append(argv)
        if argv[:2] == ["pr", "create"]:
            return subprocess.CompletedProcess(
                argv, 0, "https://localhost/own/x/pull/7\n", "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    def created_titles(self) -> list:
        return [argv[argv.index("--title") + 1] for argv in self.calls
                if argv[:2] == ["pr", "create"] and "--title" in argv]


class GhLab:
    """Песочница пути (б): проект GitHub без гейта людей проекта, клон с голым `origin`, шпион `gh`."""

    def __init__(self, sandbox, monkeypatch):
        self.sb = sandbox
        self.seed = Seed()
        self.conn = store.db()
        self.gh = FakeGh()
        monkeypatch.setattr(ci, "gh", self.gh)
        self.name = "gh" + self.seed.word()
        self.clone = make_project_repo(self.name)

    def project(self, system: str | None, template: str | None) -> None:
        write_entry(self.name, forge_name="github", gate="operator",
                    system=system, template=template)

    def task(self, title: str) -> str:
        """Задача с веткой в клоне и одним коммитом над базой."""
        branch = f"task/{self.seed.word()}-{self.seed.word()}"
        clone = str(self.clone)
        self.sb.git("-C", clone, "checkout", "-q", "-b", branch)
        (self.clone / f"{self.seed.word()}.txt").write_text("работа\n",
                                                            encoding="utf-8")
        self.sb.git("-C", clone, "add", "-A")
        self.sb.git("-C", clone, "commit", "-q", "-m", "правка")
        self.sb.git("-C", clone, "checkout", "-q", config.MAIN_BRANCH)
        return new_task(self.conn, self.name, title, "in_dev", branch)

    def open_mr(self, task: str) -> None:
        github_adapter.ensure_draft_mr(self.conn, task,
                                       store.get_task(self.conn, task))

    def note(self, task: str) -> str:
        return self.seed.msg(f"gh {self.gh.calls}; журнал "
                             f"{journal_pairs(self.conn, task)}")


@pytest.fixture
def ghl(real_git, monkeypatch):
    return GhLab(real_git, monkeypatch)


@pytest.mark.parametrize("empty_title", [False, True])
def test_ac2_gh_pr_create_without_field_keeps_old_title(ghl, empty_title):
    """Запись без `mr_title_template`: `gh pr create` получает заголовок побайтно `<id>: <название>`, при пустом названии — `<id>: <id>`.

    Сценарий: запись GitHub без гейта людей проекта, с `ref_required` и
    без поля шаблона; задача со ссылкой системы и коммитом над базой;
    `ensure_draft_mr` зовёт `gh pr create` один раз с `--title <id>:
    <название>` (или `<id>: <id>`).

    Ловит мутацию: умолчание шаблона на пути `gh` — не `{id}: {title}`;
    пустое название даёт `<id>: `.
    """
    system = "sys" + ghl.seed.word(3)
    ghl.project(system, None)
    title = "" if empty_title else f"Задача {ghl.seed.word()}"
    task = ghl.task(title)
    add_ref(ghl.conn, task, system, ghl.seed.key(), store.now())
    ghl.open_mr(task)
    assert ghl.gh.created_titles() == [f"{task}: {title or task}"], ghl.note(task)


@pytest.mark.parametrize("random_system", [False, True])
def test_ac6_gh_pr_create_without_ref_falls_back_and_journals(ghl, random_system):
    """Путь (б): шаблон с `{ref}`, ссылки системы `ref_required` у задачи нет — `gh pr create` с `<id>: <название>`, запись журнала с действием и причиной, задача не остановлена.

    Сценарий: запись GitHub без гейта людей проекта с `ref_required:
    <система>` (`tracker` или случайное имя) и `mr_title_template: "{ref}:
    {title}"`; у задачи ссылка другой системы, коммит над базой.
    `ensure_draft_mr` зовёт `gh pr create` с `--title <id>: <название>`,
    признак `draft_mr_created` выставлен; в журнале — запись с действием
    `шаблон заголовка MR не применён` и причиной `нет ссылки системы
    <система>`; состояние задачи прежнее.

    Ловит мутацию: правило умолчания без ссылки сделано только на пути
    `forge.open_mr` — на пути `gh` заголовок `: <название>` и записи
    журнала нет; запись называет систему ссылки задачи вместо
    `ref_required`.
    """
    system = ("sys" + ghl.seed.word(3)) if random_system else "tracker"
    ghl.project(system, TEMPLATE)
    title = f"Задача {ghl.seed.word()}"
    task = ghl.task(title)
    add_ref(ghl.conn, task, "other" + ghl.seed.word(3), ghl.seed.key(),
            store.now())
    ghl.open_mr(task)
    assert ghl.gh.created_titles() == [f"{task}: {title}"], ghl.note(task)
    row = store.get_task(ghl.conn, task)
    assert row["draft_mr_created"] == 1, ghl.note(task)
    assert (NOT_APPLIED, f"нет ссылки системы {system}") in journal_pairs(
        ghl.conn, task), ghl.note(task)
    assert row["state"] == "in_dev", ghl.note(task)


def test_ac9_gh_pr_create_first_ref_and_literal_ref_in_title(ghl):
    """`gh pr create` по шаблону `{ref}: {title}`: ключ — первой по порядку записи ссылки `tracker`, `{ref}` в названии остаётся буквальным.

    Сценарий: запись GitHub без гейта людей проекта с `ref_required:
    tracker` и `mr_title_template: "{ref}: {title}"`; задача с названием,
    в котором стоит `{ref}`, и двумя ссылками `tracker` — первой по
    времени записи `<ключ1>`, второй `<ключ2>`; ветка с коммитом над
    базой. `ensure_draft_mr` зовёт `gh pr create` с `--title <ключ1>:
    <название>`, где `{ref}` названия не раскрыт.

    Ловит мутацию: `{title}` подставлен раньше `{ref}` — `{ref}` из
    названия раскрылся ключом; ключ берётся из последней ссылки системы
    (`<ключ2>`); путь `gh` собирает прежний `<id>: <название>`.
    """
    ghl.project("tracker", TEMPLATE)
    title = f"Правка {{ref}} {ghl.seed.word()}"
    task = ghl.task(title)
    first, second = ghl.seed.key(), ghl.seed.key()
    while second == first:
        second = ghl.seed.key()
    add_ref(ghl.conn, task, "tracker", first, "2026-01-01T00:00:00Z")
    add_ref(ghl.conn, task, "tracker", second, "2026-01-02T00:00:00Z")
    ghl.open_mr(task)
    assert ghl.gh.created_titles() == [f"{first}: {title}"], ghl.note(task)
