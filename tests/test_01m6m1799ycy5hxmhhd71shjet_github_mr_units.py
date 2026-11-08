"""Функции MR хостинга GitHub через `gh` (`open_mr`, `mr_status`, `undraft_mr`, `assign_mr`), закрытый список вызовов `forge.github_call`, исполнитель по имени — на уровне `forge` и `github_adapter.open_forge_mr`.

Группа: долгоживущий
Красен до реализации: у `forge._GitHub` нет `open_mr`/`mr_status`/`undraft_mr`/`assign_mr` — `forge` отвечает «не реализовано для github» без вызова `gh`, функции `forge.github_call` нет (AttributeError), `github_adapter.mr_assignee` не принимает проект и знает только целый id, у `forge.MergeRequest` нет булева признака «уже существует». Методы AC-16 зелены с рождения: они держат прежнее поведение (семь функций — «не реализовано для github», запись «сверка автора — после адаптера»).

Окружение (фикстура `lab`) — песочница `initialized_tmp_root` (пути
`config` во временном каталоге, БД после `init`), записи вымышленных
проектов — в локальном слое (`targets.local_path()`); пара `github` +
`target-human` включена подменой `targets.SUPPORTED_PAIRS`. Подменены
публичные точки: `ci.gh` — шпион `gh` (`FakeGh`: пишет позиционные
аргументы и именованные, отвечает заготовкой сценария: код выхода, stdout,
stderr; PR для `pr view` — словарь полей сценария), транспорт GitLab
`gitlab_adapter.transport` — шпион, который отказывает, и
`gitcmd.hosting_token` — связка ключей не читается. Настоящего `gh` и
GitHub тест не трогает.

Связки «команда — FSM — git» здесь нет: свойства — ответы функций
`forge`, их вызовы `gh` и запись ссылки на MR в БД (`open_forge_mr`).
Гейт мержа, вход в `verifying` и `mr-sync` — в соседнем файле этой же
задачи с суффиксом `github_mr_gate`.

Имена веток, владельцев, номера PR и тексты — из `random`, зерно
печатается и входит в текст каждого провала.

Провалидировано временным стабом (удалён, не закоммичен): четыре функции
`_GitHub` через `forge.github_call` с закрытым списком, булево поле
`already_exists`, `ASSIGNEE_BY_NAME` и `mr_assignee(policy, target)`,
сохранение ссылки при `iid` с причиной — все методы файла зелёные.
"""
import dataclasses
import json
import random
import re
import subprocess

import pytest

from orchestrator import (ci, config, forge, github_adapter, gitlab_adapter,
                          idgen, store, targets)

FIELDS = ("number,url,title,state,isDraft,assignees,baseRefName,"
          "headRefName,headRefOid,mergeCommit")
REFUSAL = "вызов gh не разрешён адаптеру GitHub — gh не запущен: "
NOT_IMPLEMENTED = "не реализовано для github"
NOT_NUMERIC = "не числовой id"
OLD_NOT_NUMERIC = "исполнитель не числовой id — не назначен"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
HEX = "0123456789abcdef"
# Поля `forge.MergeRequest`, известные до задачи: признак «уже существует»
# — иное булево поле (имя выбирает разработчик, требование 3).
KNOWN_MR_FIELDS = {"iid", "url", "title", "state", "draft", "assignee",
                   "reason", "target_branch", "source_branch", "sha",
                   "merge_commit_sha", "squash_commit_sha"}
NAME_RULE = re.compile(r"[A-Za-z0-9](?:-?[A-Za-z0-9])*")

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


class FakeGh:
    """Шпион `ci.gh`: вызов — в `calls` (позиционные аргументы строками и
    именованные), ответ — по сценарию."""

    def __init__(self):
        self.calls: list = []
        self.create = (0, "", "")
        self.view = None
        self.ready = (0, "", "")
        self.edit = (0, "", "")
        self.pr: dict = {}
        self.answer = None

    def __call__(self, *args, **kwargs):
        argv = [str(a) for a in args]
        self.calls.append((argv, dict(kwargs)))
        if self.answer is not None:
            return self.answer
        head = argv[:2]
        if head == ["pr", "create"]:
            return subprocess.CompletedProcess(argv, *self.create)
        if head == ["pr", "view"]:
            if self.view is not None:
                return subprocess.CompletedProcess(argv, *self.view)
            data = dict(self.pr)
            if "number" not in data and len(argv) > 2 and argv[2].isdigit():
                data["number"] = int(argv[2])
            return subprocess.CompletedProcess(argv, 0, json.dumps(data), "")
        if head == ["pr", "ready"]:
            code, out, err = self.ready
            if code == 0:
                self.pr["isDraft"] = False
            return subprocess.CompletedProcess(argv, code, out, err)
        if head == ["pr", "edit"]:
            code, out, err = self.edit
            if code == 0 and len(argv) > 3 and "=" in argv[3]:
                self.pr.setdefault("assignees", []).append(
                    {"login": argv[3].split("=", 1)[1]})
            return subprocess.CompletedProcess(argv, code, out, err)
        return subprocess.CompletedProcess(argv, 1, "",
                                           "вызов gh вне сценария теста")

    def argvs(self) -> list:
        return [argv for argv, _kwargs in self.calls]

    def seen(self, *prefix) -> list:
        return [argv for argv in self.argvs() if argv[:len(prefix)] == list(prefix)]


class Lab:
    """Песочница проектов, шпионы `gh` и транспорта GitLab."""

    def __init__(self, sb, monkeypatch):
        self.sb = sb
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.gh = FakeGh()
        self.transport_calls: list = []
        self.token_calls: list = []
        self.entries: dict = {}

        def transport(*args, **kwargs):
            self.transport_calls.append(args)
            raise OSError("транспорт GitLab закрыт сценарием теста")

        def hosting_token(*args, **kwargs):
            self.token_calls.append(args)
            return None, "связка ключей закрыта сценарием теста"

        monkeypatch.setattr(ci, "gh", self.gh)
        monkeypatch.setattr(gitlab_adapter, "transport", transport)
        # Подмена по пути: связка ключей не читается (SPEC, общие условия).
        monkeypatch.setattr("orchestrator.gitcmd.hosting_token", hosting_token)
        monkeypatch.setattr(targets, "SUPPORTED_PAIRS",
                            set(targets.SUPPORTED_PAIRS)
                            | {("github", "target-human")})

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def hexsha(self) -> str:
        return "".join(self.rng.choice(HEX) for _ in range(40))

    def login(self) -> str:
        """Имя по правилу имён GitHub: буквы, цифры, одиночный `-` внутри."""
        return f"{self.word(3)}-{self.word(4)}{self.rng.randrange(10)}"

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def project(self, *, forge_name: str = "github", url: str | None = None,
                gate: str = "target-human", **policy) -> tuple:
        """Запись проекта в локальном слое; `policy` — поля раздела
        `policy` (значение — текст YAML, `None` — поля нет). Возвращает
        (имя, владелец, имя репозитория, `url` записи)."""
        name = f"proj{self.word()}"
        owner = f"own{self.word(4)}"
        if url is None:
            url = f"https://localhost/{owner}/{name}"
        lines = "".join(f"      {key}: {value}\n" for key, value in policy.items()
                        if value is not None)
        self.entries[name] = ENTRY.format(name=name, base=config.MAIN_BRANCH,
                                          gate=gate, policy=lines,
                                          forge=forge_name, url=url)
        local = targets.local_path()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text("targets:\n" + "".join(self.entries.values()),
                         encoding="utf-8")
        return name, owner, name, url

    def pr_fields(self, number: int, url: str, *, branch: str = "",
                  draft: bool = False, assignees: list | None = None,
                  state: str = "OPEN", merge_commit: str | None = None) -> dict:
        return {"number": number, "url": url, "title": f"Заголовок {self.word()}",
                "state": state, "isDraft": draft,
                "assignees": [{"login": a} for a in assignees or []],
                "baseRefName": config.MAIN_BRANCH,
                "headRefName": branch or f"task/{self.word()}",
                "headRefOid": self.hexsha(),
                "mergeCommit": ({"oid": merge_commit} if merge_commit else None)}

    def task(self, target: str) -> str:
        task = idgen.new_task_id()
        branch = f"task/{task.lower()}-{self.word()}"
        store.insert_task(self.conn, task, f"Задача {self.word()}", "merge_gate",
                          branch, target, config.DEFAULT_BUDGET_USD)
        return task

    def row(self, task: str):
        return store.get_task(self.conn, task)

    def actions(self, task: str) -> list:
        return [r["action"] for r in store.task_steps(self.conn, task)]

    def journal(self, task: str) -> str:
        return "\n".join(f"{r['action']} | {r['detail'] or ''}"
                         for r in store.task_steps(self.conn, task))

    def where(self, res=None) -> str:
        calls = "\n".join(f"{argv} {kwargs}" for argv, kwargs in self.gh.calls)
        return self.note(f"\n--- результат: {res!r}\n--- gh:\n{calls}")


@pytest.fixture
def lab(initialized_tmp_root, monkeypatch):
    return Lab(initialized_tmp_root, monkeypatch)


def exists_flags(res) -> list:
    """Значения булевых полей `MergeRequest` вне известных до задачи."""
    return [getattr(res, f.name) for f in dataclasses.fields(res)
            if f.name not in KNOWN_MR_FIELDS and f.default is False]


def allowed(argv: list) -> bool:
    """Форма вызова из закрытого списка требования 7."""
    def name_ok(value: str) -> bool:
        return len(value) <= 39 and NAME_RULE.fullmatch(value) is not None

    if argv[:3] == ["pr", "create", "--head"]:
        if len(argv) < 10 or [argv[i] for i in (4, 6, 8)] != \
                ["--base", "--title", "--body"]:
            return False
        rest = argv[10:]
        if rest[:1] == ["--draft"]:
            rest = rest[1:]
        if rest and rest[0].startswith("--assignee="):
            if not name_ok(rest[0].split("=", 1)[1]):
                return False
            rest = rest[1:]
        return rest == []
    if argv[:2] == ["pr", "view"]:
        return len(argv) == 5 and argv[2].isdigit() and argv[3:] == ["--json", FIELDS]
    if argv[:2] == ["pr", "ready"]:
        return len(argv) == 3 and argv[2].isdigit()
    if argv[:2] == ["pr", "edit"]:
        return (len(argv) == 4 and argv[2].isdigit()
                and argv[3].startswith("--add-assignee=")
                and name_ok(argv[3].split("=", 1)[1]))
    return False


# ------------------------------------------------------------------- AC-1


@pytest.mark.parametrize("draft, with_assignee", [
    (True, True), (True, False), (False, True), (False, False)])
def test_ac1_open_mr_create_argv_order_then_view(lab, draft, with_assignee):
    """`forge.open_mr` для `forge: github`: точный argv `pr create`, затем `pr view` номера; `repo` — `url` записи; поля результата — из чтения.

    Сценарий: запись `forge: github` с https-`url`; `pr create` отвечает
    кодом 0 и адресом `<url записи>/pull/<n>` (n случайно). Первый вызов шпиона —
    ровно `pr create --head <ветка> --base <база> --title <заголовок>
    --body <текст>`, затем `--draft` только у черновика, затем
    `--assignee=<имя>` одним элементом только с исполнителем; второй —
    `pr view <n> --json <набор требования 4>`. У каждого вызова `repo` —
    `url` записи. Результат: `iid` — n, `url` — адрес, заголовок и ветки —
    из ответа чтения, `reason` пуст.

    Ловит мутацию: `--draft` ставится всегда или порядок флагов иной
    (argv `pr create` не совпадает со списком); `--assignee` двумя
    элементами (`--assignee`, `<имя>`); `repo` не передан (вызов без
    `--repo` ушёл бы в репозиторий артели); номер берётся не из адреса
    либо результат не дочитан `pr view` (заголовок пуст).
    """
    name, _owner, _repo, url = lab.project()
    number = lab.rng.randrange(1, 10 ** 5)
    pr_url = f"{url}/pull/{number}"
    branch, base = f"task/{lab.word()}", config.MAIN_BRANCH
    title, body = f"Задача {lab.word()}", f"Описание {lab.word()} {lab.word()}"
    login = lab.login() if with_assignee else None
    lab.gh.create = (0, f"{pr_url}\n", "")
    lab.gh.pr = lab.pr_fields(number, pr_url, branch=branch, draft=draft,
                              assignees=[login] if login else [])
    res = forge.open_mr(name, branch, base, title, body, draft, login)
    where = lab.where(res)
    expected = ["pr", "create", "--head", branch, "--base", base,
                "--title", title, "--body", body]
    if draft:
        expected.append("--draft")
    if login:
        expected.append(f"--assignee={login}")
    assert len(lab.gh.calls) >= 2, where
    assert lab.gh.calls[0][0] == expected, where
    assert lab.gh.calls[1][0] == ["pr", "view", str(number), "--json", FIELDS], where
    assert all(kwargs.get("repo") == url for _a, kwargs in lab.gh.calls), where
    assert res.reason == "", where
    assert res.iid == number and res.url == pr_url, where
    assert res.title == lab.gh.pr["title"], where
    assert res.source_branch == branch, where
    assert res.target_branch == base, where


def url_case(lab, case: str) -> tuple:
    """(`url` записи, stdout `pr create`, ожидаемый номер или None)."""
    owner, repo = f"own{lab.word(4)}", f"rep{lab.word(4)}"
    number = lab.rng.randrange(1, 10 ** 5)
    good = f"https://localhost/{owner}/{repo}/pull/{number}"
    if case == "https .git":
        return f"https://localhost/{owner}/{repo}.git", good, number
    if case == "scp":
        return f"git@localhost:{owner}/{repo}", good, number
    if case == "регистр":
        return (f"https://localhost/{owner.capitalize()}/{repo.upper()}.git",
                f"https://localhost/{owner}/{repo}/pull/7", 7)
    if case == "чужой владелец":
        return (f"https://localhost/{owner}/{repo}",
                f"https://localhost/drug{lab.word(4)}/{repo}/pull/{number}", None)
    if case == "другое имя":
        return (f"https://localhost/{owner}/{repo}",
                f"https://localhost/{owner}/drug{lab.word(4)}/pull/7", None)
    if case == "хвост files":
        return (f"https://localhost/{owner}/{repo}",
                f"https://localhost/{owner}/{repo}/pull/7/files", None)
    return (f"https://localhost/{owner}/{repo}",
            f"https://localhost/{owner}/{repo}/pull/7x", None)


@pytest.mark.parametrize("case", [
    "https .git", "scp", "регистр", "чужой владелец", "другое имя",
    "хвост files", "хвост 7x"])
def test_ac1_pr_number_parsed_by_owner_and_name(lab, case):
    """Номер PR через `open_forge_mr`: владелец и имя адреса PR сверяются с `url` записи разбором https/scp без учёта регистра; хвост — ровно номер.

    Сценарий по параметру: `url` записи `https://localhost/<владелец>/<имя>.git`
    или `git@localhost:<владелец>/<имя>` при stdout `pr create`
    `https://localhost/<владелец>/<имя>/pull/<n>` — номер разобран, ссылка на
    MR в БД задачи — (n, адрес); `url` `…/Owner/REPO.git` при stdout
    `…/owner/repo/pull/7` — номер 7, ссылка сохранена; адрес PR чужого
    владельца, того же владельца с другим именем, хвост `…/pull/7/files` и
    `…/pull/7x` — результат с причиной, `iid` `None`, ссылки в БД нет.

    Ловит мутацию: адрес PR сравнивается с адресом проекта буквально по
    префиксу (вид `.git` и scp не совпадут — номера нет); сравнение с
    учётом регистра; владелец или имя не сверяются (чужой PR сохранён
    ссылкой); номер берётся первым числом после `/pull/` (`7/files` и
    `7x` дают 7).
    """
    url, stdout, number = url_case(lab, case)
    name, *_rest = lab.project(url=url, draft_mr="false")
    task = lab.task(name)
    lab.gh.create = (0, stdout + "\n", "")
    lab.gh.pr = lab.pr_fields(number or 7, stdout,
                              branch=lab.row(task)["branch"])
    res = github_adapter.open_forge_mr(lab.conn, task, lab.row(task),
                                       lab.hexsha(), draft=False)
    where = lab.where(res) + f"\n--- url записи {url}, stdout {stdout}"
    link = store.mr_link(lab.row(task))
    assert lab.gh.seen("pr", "create"), where
    if number is None:
        assert res.reason, where
        assert res.iid is None, where
        assert link == (None, None), where
        return
    assert res.iid == number, where
    assert link == (number, stdout), where


# ------------------------------------------------------------------- AC-2


@pytest.mark.parametrize("stdout", [
    "", "Creating pull request for task into main\n",
    "https://localhost/{owner}/{repo}/pull/\n",
    "https://localhost/{owner}/{repo}/issues/12\n"])
def test_ac2_create_ok_without_address_is_refusal(lab, stdout):
    """`pr create` с кодом 0 без разбираемого адреса — причина без `iid`; `open_forge_mr` не пишет ни ссылку, ни «MR открыт».

    Сценарий: запись `forge: github`; `pr create` отвечает кодом 0, а stdout
    — пустой, текст без адреса, адрес `…/pull/` без номера или адрес
    `…/issues/12`. `forge.open_mr`: непустая причина, `iid` `None`, шпион
    видел `pr create`. `open_forge_mr` на той же заготовке: ссылки на MR в
    БД задачи нет, записи журнала «MR открыт» нет.

    Ловит мутацию: код выхода 0 сам считается успехом (результат без
    причины, `iid` пуст или 0); либо `open_forge_mr` пишет ссылку
    `(None, None)`-образную и «MR открыт» при результате без `iid`.
    """
    name, owner, repo, _url = lab.project(draft_mr="false")
    lab.gh.create = (0, stdout.format(owner=owner, repo=repo), "")
    lab.gh.pr = lab.pr_fields(12, f"https://localhost/{owner}/{repo}/pull/12")
    res = forge.open_mr(name, f"task/{lab.word()}", config.MAIN_BRANCH,
                        "Заголовок", "Текст", False, None)
    where = lab.where(res)
    assert res.reason, where
    assert res.iid is None, where
    assert lab.gh.seen("pr", "create"), where
    task = lab.task(name)
    res = github_adapter.open_forge_mr(lab.conn, task, lab.row(task),
                                       lab.hexsha(), draft=False)
    where = lab.where(res) + "\n--- журнал:\n" + lab.journal(task)
    assert store.mr_link(lab.row(task)) == (None, None), where
    assert github_adapter.MR_OPENED_ACTION not in lab.actions(task), where


# ------------------------------------------------------------------- AC-5


@pytest.mark.parametrize("kind", ["gh", "422"])
def test_ac5_already_exists_flag_without_iid(lab, kind):
    """Отказ `pr create` «уже существует» (проверка `gh` с адресом PR в stderr и отказ сервера 422) — признак «уже существует», `iid` `None`.

    Сценарий: запись `forge: github`; `pr create` — код 1, stderr: `a pull
    request for branch "<ветка>" into branch "<база>" already exists:` и
    адрес `<url записи>/pull/<n>`, либо текст отказа сервера с `A pull request
    already exists`. Результат `forge.open_mr`: новое булево поле
    `MergeRequest` (вне известных до задачи) истинно, `iid` `None`, причина
    непуста.

    Ловит мутацию: адрес из stderr «already exists» разобран номером (`iid`
    — n); признак не ставится по одному из двух текстов (все новые булевы
    поля ложны); признак не заведён вовсе.
    """
    name, _owner, _repo, url = lab.project()
    branch = f"task/{lab.word()}"
    number = lab.rng.randrange(1, 10 ** 5)
    if kind == "gh":
        stderr = (f'a pull request for branch "{branch}" into branch '
                  f'"{config.MAIN_BRANCH}" already exists:\n{url}/pull/{number}\n')
    else:
        stderr = (f"pull request create failed: GraphQL: A pull request already "
                  f"exists for {lab.word()}:{branch}. (createPullRequest)\n")
    lab.gh.create = (1, "", stderr)
    lab.gh.pr = lab.pr_fields(number, f"{url}/pull/{number}", branch=branch)
    res = forge.open_mr(name, branch, config.MAIN_BRANCH, "Заголовок", "Текст",
                        False, None)
    where = lab.where(res)
    assert res.iid is None, where
    assert res.reason, where
    assert True in exists_flags(res), where


# ------------------------------------------------------------------- AC-6


def test_ac6_other_create_refusal_has_no_exists_flag(lab):
    """Отказ `pr create` иным текстом — шпион видел `pr create`, признака «уже существует» нет, причина непуста.

    Сценарий: запись `forge: github`; `pr create` — код 1 со случайным из
    отказов (нет коммитов между ветками, нет прав, сбой сети). Результат
    `forge.open_mr`: все новые булевы поля `MergeRequest` ложны, `iid`
    `None`.

    Ловит мутацию: признак «уже существует» ставится на любой отказ `pr
    create` (гейт эскалировал бы вместо отказа); либо отказ не зовёт `gh`
    вовсе (прежнее «не реализовано»).
    """
    name, *_rest = lab.project()
    stderr = lab.rng.choice([
        "pull request create failed: GraphQL: No commits between main and "
        f"task/{lab.word()} (createPullRequest)\n",
        f"GraphQL: {lab.word()} does not have the correct permissions to "
        "execute `CreatePullRequest`\n",
        "error connecting to api.localhost\n"])
    lab.gh.create = (1, "", stderr)
    res = forge.open_mr(name, f"task/{lab.word()}", config.MAIN_BRANCH,
                        "Заголовок", "Текст", False, None)
    where = lab.where(res)
    assert lab.gh.seen("pr", "create"), where
    assert res.reason and res.iid is None, where
    assert True not in exists_flags(res), where


# ------------------------------------------------------------------- AC-7


@pytest.mark.parametrize("state, mapped", [
    ("OPEN", "opened"), ("MERGED", "merged"), ("CLOSED", "closed")])
@pytest.mark.parametrize("draft", [True, False])
@pytest.mark.parametrize("assigned", [True, False])
@pytest.mark.parametrize("with_merge_commit", [True, False])
def test_ac7_mr_status_maps_view_fields(lab, state, mapped, draft, assigned,
                                        with_merge_commit):
    """`forge.mr_status` для github: argv `pr view <n> --json <набор>`, `repo` — `url` записи, поля по таблице требования 4.

    Сценарий: ответ `pr view` со `state` по параметру, `isDraft`,
    `assignees` (1–3 исполнителя или пусто), `mergeCommit` (`{"oid": sha}`
    или `null`), ветками и `headRefOid`. Результат: `state` —
    `opened`/`merged`/`closed`; `draft` — `isDraft`; `assignee` — `login`
    первого, пусто — `None`; `target_branch`/`source_branch`/`sha` —
    `baseRefName`/`headRefName`/`headRefOid`; `merge_commit_sha` — `oid`
    или `None`; `squash_commit_sha` — `None`; argv — ровно `pr view <n>
    --json <набор>`.

    Ловит мутацию: `state` отдаётся как есть (`OPEN`); `assignee` — последний
    из списка или весь список; `mergeCommit: null` роняет разбор или даёт
    строку; `squash_commit_sha` заполняется коммитом вливания (сверка
    `mr-sync` взяла бы его дважды); ветки перепутаны местами; набор полей
    `--json` иной.
    """
    name, _owner, _repo, url = lab.project()
    number = lab.rng.randrange(1, 10 ** 5)
    logins = [lab.login() for _ in range(lab.rng.randint(1, 3))] if assigned else []
    merge = lab.hexsha() if with_merge_commit else None
    lab.gh.pr = lab.pr_fields(number, f"{url}/pull/{number}", draft=draft,
                              assignees=logins, state=state, merge_commit=merge)
    res = forge.mr_status(name, number)
    where = lab.where(res)
    assert lab.gh.calls and lab.gh.calls[0][0] == [
        "pr", "view", str(number), "--json", FIELDS], where
    assert all(kwargs.get("repo") == url for _a, kwargs in lab.gh.calls), where
    assert res.reason == "", where
    assert res.iid == number and res.url == f"{url}/pull/{number}", where
    assert res.title == lab.gh.pr["title"], where
    assert res.state == mapped, where
    assert res.draft is draft, where
    assert res.assignee == (logins[0] if logins else None), where
    assert res.target_branch == lab.gh.pr["baseRefName"], where
    assert res.source_branch == lab.gh.pr["headRefName"], where
    assert res.sha == lab.gh.pr["headRefOid"], where
    assert res.merge_commit_sha == merge, where
    assert res.squash_commit_sha is None, where


# ------------------------------------------------------------------- AC-8


@pytest.mark.parametrize("stdout", [
    "<html>502 Bad Gateway</html>", "", '{"url": "x", "state": "OPEN"}',
    "[1, 2, 3]"])
def test_ac8_view_not_json_or_without_number_is_refusal_without_404(lab, stdout):
    """`pr view` с кодом 0, но вывод не JSON или JSON без `number` — причина без `(404)`.

    Сценарий: ответ `pr view` — код 0, stdout по параметру (HTML, пусто,
    объект без `number`, список). `forge.mr_status`: непустая причина, в ней
    нет `(404)`.

    Ловит мутацию: разбор падает исключением на не-JSON; отсутствие
    `number` даёт результат без причины (`iid` `None` при пустом
    `reason`); отказ разбора назван «не найден» (`(404)`).
    """
    name, *_rest = lab.project()
    lab.gh.view = (0, stdout, "")
    res = forge.mr_status(name, lab.rng.randrange(1, 10 ** 5))
    where = lab.where(res)
    assert lab.gh.seen("pr", "view"), where
    assert res.reason, where
    assert "(404)" not in res.reason, where


# ------------------------------------------------------------------ AC-11


@pytest.mark.parametrize("draft", [True, False])
def test_ac11_undraft_ready_only_for_draft(lab, draft):
    """`forge.undraft_mr` для github: черновик — `pr ready <n>` ровно один раз и результат нового чтения; не черновик — без `pr ready`.

    Сценарий: PR номера n в ответе `pr view` — черновик или нет.
    Черновик: шпион видел `pr ready <n>` ровно один раз, результат —
    `draft` `False` (новое чтение после `pr ready`). Не черновик: `pr ready`
    не вызван, результат — чтение (`draft` `False`). У каждого вызова
    `repo` — `url` записи.

    Ловит мутацию: `pr ready` зовётся всегда (для не черновика тоже) или
    дважды; результат собирается из первого чтения (`draft` `True` после
    снятия); `repo` у `pr ready` не передан.
    """
    name, _owner, _repo, url = lab.project()
    number = lab.rng.randrange(1, 10 ** 5)
    lab.gh.pr = lab.pr_fields(number, f"{url}/pull/{number}", draft=draft)
    res = forge.undraft_mr(name, number)
    where = lab.where(res)
    ready = lab.gh.seen("pr", "ready")
    assert ready == ([["pr", "ready", str(number)]] if draft else []), where
    assert res.reason == "" and res.iid == number, where
    assert res.draft is False, where
    assert lab.gh.seen("pr", "view"), where
    assert all(kwargs.get("repo") == url for _a, kwargs in lab.gh.calls), where


def test_ac11_undraft_ready_refusal_is_reason(lab):
    """Отказ `pr ready` для черновика — шпион видел `pr ready`, результат с причиной.

    Сценарий: PR — черновик; `pr ready` отвечает кодом 1 со случайным
    текстом. `forge.undraft_mr`: причина непуста.

    Ловит мутацию: код выхода `pr ready` не проверяется — результат нового
    чтения без причины.
    """
    name, _owner, _repo, url = lab.project()
    number = lab.rng.randrange(1, 10 ** 5)
    lab.gh.pr = lab.pr_fields(number, f"{url}/pull/{number}", draft=True)
    lab.gh.ready = (1, "", f"GraphQL: отказ {lab.word()}\n")
    res = forge.undraft_mr(name, number)
    where = lab.where(res)
    assert lab.gh.seen("pr", "ready", str(number)), where
    assert res.reason, where


# ------------------------------------------------------------------ AC-12


def test_ac12_assign_edit_one_element_then_view(lab):
    """`forge.assign_mr` для github: `pr edit <n> --add-assignee=<login>` одним элементом, затем чтение; `repo` — `url` записи.

    Сценарий: случайный `login` по правилу имён. Шпион видел ровно argv
    `pr edit <n> --add-assignee=<login>`, после него — `pr view`; результат
    без причины, `assignee` — первый из `assignees` нового чтения.

    Ловит мутацию: флаг и значение двумя элементами (`--add-assignee`,
    `<login>`); `--assignee` вместо `--add-assignee`; результат без чтения
    после правки; `repo` не передан.
    """
    name, _owner, _repo, url = lab.project()
    number = lab.rng.randrange(1, 10 ** 5)
    login = lab.login()
    lab.gh.pr = lab.pr_fields(number, f"{url}/pull/{number}")
    res = forge.assign_mr(name, number, login)
    where = lab.where(res)
    argvs = lab.gh.argvs()
    edit = ["pr", "edit", str(number), f"--add-assignee={login}"]
    assert edit in argvs, where
    assert any(a[:2] == ["pr", "view"] for a in argvs[argvs.index(edit) + 1:]), where
    assert all(kwargs.get("repo") == url for _a, kwargs in lab.gh.calls), where
    assert res.reason == "", where
    assert res.assignee == login, where


def test_ac12_assign_edit_refusal_is_reason(lab):
    """Отказ `pr edit` — шпион видел `pr edit`, результат с причиной.

    Сценарий: `pr edit` отвечает кодом 1 со случайным текстом.
    `forge.assign_mr`: причина непуста.

    Ловит мутацию: код выхода `pr edit` не проверяется — результат чтения
    без причины.
    """
    name, _owner, _repo, url = lab.project()
    number = lab.rng.randrange(1, 10 ** 5)
    lab.gh.pr = lab.pr_fields(number, f"{url}/pull/{number}")
    lab.gh.edit = (1, "", f"could not add assignee: {lab.word()}\n")
    res = forge.assign_mr(name, number, lab.login())
    where = lab.where(res)
    assert lab.gh.seen("pr", "edit", str(number)), where
    assert res.reason, where


# ------------------------------------------------------------------ AC-13


def test_ac13_four_functions_call_only_closed_list(lab):
    """Четыре функции `_GitHub` напрямую через `forge`: шпион видел `pr create`, `pr view`, `pr ready`, `pr edit` и только формы закрытого списка; ни `api`, ни `pr merge/close/comment`; транспорт GitLab не зван.

    Сценарий: запись `forge: github`; по очереди `forge.open_mr`
    (черновик с исполнителем), `forge.mr_status`, `forge.undraft_mr`
    (PR — черновик), `forge.assign_mr`. Каждый argv шпиона — форма
    требования 7 (сверка всего argv, включая хвост), среди них хотя бы по
    одному `pr create`, `pr view`, `pr ready`, `pr edit`; ни одного `api`,
    `pr merge`, `pr close`, `pr comment`; шпион транспорта GitLab пуст.

    Ловит мутацию: `undraft_mr` снимает черновик через `api -X PATCH`;
    `assign_mr` — `pr edit --assignee` или `api`; `mr_status` читает
    `--json` с иным набором; реестр отдаёт для github функции GitLab
    (транспорт GitLab зван).
    """
    name, _owner, _repo, url = lab.project()
    number = lab.rng.randrange(1, 10 ** 5)
    lab.gh.create = (0, f"{url}/pull/{number}\n", "")
    lab.gh.pr = lab.pr_fields(number, f"{url}/pull/{number}", draft=True)
    login = lab.login()
    results = [
        forge.open_mr(name, f"task/{lab.word()}", config.MAIN_BRANCH,
                      f"Заголовок {lab.word()}", f"Текст {lab.word()}", True, login),
        forge.mr_status(name, number),
        forge.undraft_mr(name, number),
        forge.assign_mr(name, number, login)]
    where = lab.where(results) + f"\n--- транспорт: {lab.transport_calls}"
    argvs = lab.gh.argvs()
    for head in (["pr", "create"], ["pr", "view"], ["pr", "ready"], ["pr", "edit"]):
        assert any(a[:2] == head for a in argvs), where + f"\nнет {head}"
    assert [a for a in argvs if not allowed(a)] == [], where
    assert not [a for a in argvs if a[:1] == ["api"]], where
    assert not [a for a in argvs
                if a[:2] in (["pr", "merge"], ["pr", "close"], ["pr", "comment"])], where
    assert lab.transport_calls == [], where


# ------------------------------------------------------------------ AC-14


def refused_forms(lab) -> list:
    login = lab.login()
    return [
        ["pr", "edit", "7", "--base", "x"], ["pr", "merge", "7"],
        ["pr", "close", "7"], ["pr", "comment", "7"],
        ["pr", "view", "7", "--json", "number"], ["pr", "ready", "7", "--undo"],
        ["pr", "edit", "7", f"--add-assignee={login}", "--base", "x"],
        ["pr", "view", "7a", "--json", FIELDS], ["pr", "ready", "7a"],
        ["api", "-X", "POST", "repos/o/r/pulls/7/merge"],
        ["api", "repos/o/r/pulls"],
        ["pr", "edit", "7", "--add-assignee=@me"],
        ["pr", "edit", "7", "--add-assignee=@copilot"],
        ["pr", "create", "--head", f"task/{lab.word()}", "--base",
         config.MAIN_BRANCH, "--title", "Заголовок", "--body", "Текст",
         "--assignee=a,b"]]


def test_ac14_github_call_refuses_out_of_list_without_gh(lab):
    """`forge.github_call` вне закрытого списка — `CompletedProcess` код 1, stderr с префиксом отказа, `ci.gh` не вызван.

    Сценарий: запись `forge: github`; `github_call` с каждой формой AC-14:
    лишний хвост (`--base x`, `--undo`), иной набор `--json`, номер `7a`,
    `pr merge/close/comment`, `api` чтения и записи, исполнитель `@me`,
    `@copilot`, `a,b`. Каждый ответ — `subprocess.CompletedProcess` с кодом
    1 и stderr, начинающимся с `вызов gh не разрешён адаптеру GitHub — gh
    не запущен: `; шпион `ci.gh` пуст.

    Ловит мутацию: сверка по префиксу формы (хвост после разрешённой формы
    пропущен в `gh`); номер не проверяется на десятичность; `api` разрешён
    чтением; значение исполнителя не сверяется с правилом имён (`@me`
    уходит в `gh`).
    """
    name, *_rest = lab.project()
    for argv in refused_forms(lab):
        res = forge.github_call(name, *argv)
        where = lab.where(res) + f"\n--- argv {argv}"
        assert isinstance(res, subprocess.CompletedProcess), where
        assert res.returncode == 1, where
        assert str(res.stderr).startswith(REFUSAL), where
    assert lab.gh.calls == [], lab.where()


def allowed_forms(lab) -> list:
    branch, login = f"task/{lab.word()}", lab.login()
    create = ["pr", "create", "--head", branch, "--base", config.MAIN_BRANCH,
              "--title", f"Заголовок {lab.word()}", "--body", f"Текст {lab.word()}"]
    return [create, create + ["--draft"], create + [f"--assignee={login}"],
            create + ["--draft", f"--assignee={login}"],
            ["pr", "view", "7", "--json", FIELDS], ["pr", "ready", "7"],
            ["pr", "edit", "7", "--add-assignee=alice"]]


def test_ac14_github_call_passes_allowed_forms_with_repo(lab):
    """Разрешённые формы — `ci.gh` вызван ровно с этими позиционными аргументами и `repo` — `url` записи; `github_call` отдаёт его ответ.

    Сценарий: запись `forge: github` с https-`url`; шпион отвечает
    случайными кодом и stdout. Для `pr create` в четырёх сочетаниях
    `--draft`/`--assignee=<имя>`, `pr view 7 --json <набор>`, `pr ready 7`,
    `pr edit 7 --add-assignee=alice`: последний вызов шпиона — ровно argv
    формы с `repo` = `url`, ответ `github_call` — ответ шпиона.

    Ловит мутацию: `repo` не передаётся (вызов ушёл бы в репозиторий
    артели); argv переставляется или дополняется; закрытый список
    отказывает разрешённой форме (`--draft` с `--assignee`).
    """
    name, _owner, _repo, url = lab.project()
    for argv in allowed_forms(lab):
        lab.gh.answer = subprocess.CompletedProcess(
            argv, lab.rng.choice([0, 1]), f"ответ {lab.word()}", "")
        res = forge.github_call(name, *argv)
        where = lab.where(res) + f"\n--- argv {argv}"
        assert lab.gh.calls, where
        called, kwargs = lab.gh.calls[-1]
        assert called == argv, where
        assert kwargs.get("repo") == url, where
        assert (res.returncode, res.stdout) == (lab.gh.answer.returncode,
                                                lab.gh.answer.stdout), where
        lab.gh.calls.clear()


def test_ac14_github_call_refuses_unresolved_project_and_artel(lab):
    """Проект без разрешённого контекста и артель — код 1 без `ci.gh`; у артели stderr непуст.

    Сценарий: `github_call` для имени проекта без записи (`repo_context.
    resolve` даёт `None`) с `pr ready 7`; `github_call` для артели
    (`config.DEFAULT_TARGET`) с разрешённой формой `pr ready 7`. Оба ответа —
    код 1, у артели stderr непуст; шпион `ci.gh` пуст.

    Ловит мутацию: для артели `repo` пуст и вызов уходит в `gh` без
    `--repo` (PR с тем же номером в репозитории артели); проект без
    контекста зовёт `gh` с `repo=None`.
    """
    lab.project()
    missing = f"nety{lab.word()}"
    res = forge.github_call(missing, "pr", "ready", "7")
    assert res.returncode == 1, lab.where(res)
    res = forge.github_call(config.DEFAULT_TARGET, "pr", "ready", "7")
    assert res.returncode == 1, lab.where(res)
    assert str(res.stderr).strip(), lab.where(res)
    assert lab.gh.calls == [], lab.where()


# ------------------------------------------------------------------ AC-15


def created_argv(lab) -> list:
    created = lab.gh.seen("pr", "create")
    return created[0] if created else []


@pytest.mark.parametrize("value, flag", [
    ("alice", "--assignee=alice"), ("42", "--assignee=42"),
    ('"@copilot"', None), ('"@me"', None), ('"a,b"', None), ('"-x"', None),
    ('"a b"', None), (None, None)])
def test_ac15_github_assignee_by_name_in_create(lab, value, flag):
    """GitHub: `mr_assignee` `alice` и `42` — флаг `--assignee=` в `pr create`; `@copilot`, `@me`, `a,b`, `-x`, `a b` и отсутствие поля — без флага, запись «исполнитель MR» без «не числовой id».

    Сценарий: запись `forge: github` + `target-human` с `policy.mr_assignee`
    по параметру; `open_forge_mr` задачи, `pr create` и `pr view` отвечают
    успехом. Имя и целое — в argv `pr create` ровно элемент
    `--assignee=<значение>`. Неназначаемое значение и отсутствие поля — в
    argv нет элемента с `--assignee`, в журнале задачи есть запись
    «исполнитель MR», её текст без подстроки «не числовой id».

    Ловит мутацию: исполнитель по имени не принят для GitHub (`alice` не
    уходит в `pr create`); значение с `@`, запятой, ведущим `-` или
    пробелом уходит флагом; запись о неназначенном для GitHub — прежним
    текстом «исполнитель не числовой id».
    """
    name, _owner, _repo, url = lab.project(draft_mr="false", mr_assignee=value)
    task = lab.task(name)
    number = lab.rng.randrange(1, 10 ** 5)
    lab.gh.create = (0, f"{url}/pull/{number}\n", "")
    lab.gh.pr = lab.pr_fields(number, f"{url}/pull/{number}",
                              branch=lab.row(task)["branch"])
    res = github_adapter.open_forge_mr(lab.conn, task, lab.row(task),
                                       lab.hexsha(), draft=False)
    where = lab.where(res) + "\n--- журнал:\n" + lab.journal(task)
    argv = created_argv(lab)
    assert argv, where
    flags = [a for a in argv if a.startswith("--assignee")]
    if flag is not None:
        assert flags == [flag], where
        return
    assert flags == [], where
    rows = [r for r in store.task_steps(lab.conn, task)
            if r["action"] == github_adapter.MR_ASSIGNEE_ACTION]
    assert rows, where
    assert all(NOT_NUMERIC not in (r["detail"] or "") for r in rows), where


@pytest.mark.parametrize("policy, expected", [
    ({"mr_assignee": 42}, (42, "")),
    ({"mr_assignee": "alice"},
     (None, f"{OLD_NOT_NUMERIC}: policy.mr_assignee = 'alice'")),
    ({}, (None, f"{OLD_NOT_NUMERIC}: policy.mr_assignee не задан"))])
def test_ac15_assignee_without_project_or_hosting_keeps_old_answers(
        lab, monkeypatch, policy, expected):
    """`mr_assignee(policy)` без проекта и с проектом, хостинг которого не определён, — прежние ответы; GitLab и `alice` — не назначен прежней записью.

    Сценарий: `github_adapter.mr_assignee(policy)` без проекта; тот же вызов
    с именем проекта без записи, с проектом, запись которого не несёт
    `forge` (загрузчик записи подменён), и с проектом `forge: gitlab` —
    ответ ровно прежний: целое — `(42, "")`, `alice` — `None` и запись
    «исполнитель не числовой id — не назначен: policy.mr_assignee =
    'alice'», без поля — `None` и «… policy.mr_assignee не задан».

    Ловит мутацию: признак «по имени» берётся по умолчанию истинным, когда
    хостинг не определён (`alice` принят без проекта); новый текст записи
    GitHub пишется и для GitLab или вызова без проекта.
    """
    gitlab, *_rest = lab.project(forge_name="gitlab",
                                 url=f"https://localhost/grp/{lab.word()}")
    assert github_adapter.mr_assignee(dict(policy)) == expected, lab.note("без проекта")
    assert github_adapter.mr_assignee(dict(policy), f"nety{lab.word()}") == \
        expected, lab.note("проект без записи")
    assert github_adapter.mr_assignee(dict(policy), gitlab) == expected, \
        lab.note("проект gitlab")
    real = targets.target

    def without_forge(name):
        entry = dict(real(name))
        entry.pop("forge", None)
        return entry

    monkeypatch.setattr(targets, "target", without_forge)
    assert github_adapter.mr_assignee(dict(policy), gitlab) == expected, \
        lab.note("запись без forge")


def test_ac15_boolean_assignee_not_assigned(lab):
    """Булево значение `mr_assignee` для GitHub — не назначен, запись непуста.

    Сценарий: `github_adapter.mr_assignee({"mr_assignee": True|False},
    <проект github>)` — исполнитель `None`, текст записи о неназначенном
    непуст.

    Ловит мутацию: `True` проходит как целое 1 (`bool` — подкласс `int`)
    или как имя `"True"`.
    """
    name, *_rest = lab.project()
    for value in (True, False):
        assignee, note = github_adapter.mr_assignee({"mr_assignee": value}, name)
        assert assignee is None, lab.note(f"{value!r}: {assignee!r}")
        assert note, lab.note(f"{value!r}: пустая запись")


def test_ac15_registry_attribute_decides_by_name(lab, monkeypatch):
    """Вид исполнителя задаёт атрибут реализации `ASSIGNEE_BY_NAME` в реестре `forge.IMPLEMENTATIONS`, не литерал значения `forge`.

    Сценарий: реализация `forge.IMPLEMENTATIONS["github"]` подставлена под
    ключ `gitlab` — `mr_assignee` с проектом `forge: gitlab` принимает
    `alice`. Под ключ `github` подставлен объект без `ASSIGNEE_BY_NAME` —
    `mr_assignee` с проектом `forge: github` не назначает `alice` и
    назначает целое 42.

    Ловит мутацию: признак «по имени» — сравнение `forge.hosting(t) ==
    "github"` (подмена реестра его не меняет: gitlab отказывает `alice`,
    github принимает).
    """
    github, *_rest = lab.project()
    gitlab, *_rest = lab.project(forge_name="gitlab",
                                 url=f"https://localhost/grp/{lab.word()}")
    implementation = forge.IMPLEMENTATIONS["github"]
    monkeypatch.setitem(forge.IMPLEMENTATIONS, "gitlab", implementation)
    assignee, note = github_adapter.mr_assignee({"mr_assignee": "alice"}, gitlab)
    assert assignee == "alice", lab.note(f"gitlab с реализацией github: {note}")
    monkeypatch.setitem(forge.IMPLEMENTATIONS, "github", type("Bare", (), {})())
    assignee, note = github_adapter.mr_assignee({"mr_assignee": "alice"}, github)
    assert assignee is None, lab.note(f"github без признака: {assignee!r}")
    assignee, note = github_adapter.mr_assignee({"mr_assignee": 42}, github)
    assert assignee == 42, lab.note(f"github без признака, 42: {assignee!r} {note}")


# ------------------------------------------------------------------ AC-16


@pytest.mark.parametrize("call", [
    "token_user", "token_expiry", "protections", "project_info",
    "branch_pipeline"])
def test_ac16_other_functions_not_implemented_without_gh(lab, call):
    """`token_user`, `token_expiry`, `protections`, `project_info`, `branch_pipeline`, `job_result`, `job_test_report` для github — «не реализовано для github», `gh` не зван.

    Сценарий: запись `forge: github`; функция `forge` по параметру с
    аргументами интерфейса. Причина результата несёт «не реализовано для
    github», шпион `ci.gh` пуст, транспорт GitLab не зван.

    Ловит мутацию: реализация GitHub заводит функцию из этого списка (зовёт
    `gh api` — шпион не пуст, причины «не реализовано» нет); реестр отдаёт
    для github функцию GitLab.
    """
    name, *_rest = lab.project()
    sha = lab.hexsha()
    args = {"token_user": (), "token_expiry": (), "protections": (),
            "project_info": (), "branch_pipeline": (config.MAIN_BRANCH,),
            "job_result": (sha, "test"), "job_test_report": (sha, "test")}[call]
    res = getattr(forge, call)(name, *args)
    where = lab.where(res)
    assert NOT_IMPLEMENTED in res.reason, where
    assert lab.gh.calls == [], where
    assert lab.transport_calls == [], where
