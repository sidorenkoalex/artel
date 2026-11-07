"""Отправка коммита базы в ветку отчёта базы `ci_base_branch` проекта `target-human`: белый список единой точки `gitcmd`, хук `pre-push` клона, эталон файла политики, `kill` и уборка задачи; записи без `ci_base` — прежние правила.

Группа: разовый
Красен до реализации: поля компонента `ci_base`/`ci_base_branch`/`ci_base_push_options` загрузчик записей отказывает «неизвестное поле», клон проекта не заводится, а белый список и хук `pre-push` отказывают любой отправке вне шаблона веток задач и любой принудительной отправке; тесты записей без `ci_base` (AC-14, эталон политики AC-11) зелёные с рождения — держат прежние правила.

Почему разовый: предмет файла — сама единая точка отправки `gitcmd` и
настоящий git, а долгоживущий файл `tests/` не импортирует `gitcmd` и не
зовёт git через `subprocess` (`scripts/guard.py`, признаки «git-модуль» и
«git-вызов»). Свойство кода держит планка этой задачи.

Провалидировано временным стабом реализации (удалён, не закоммичен):
поля записи, ключ `ci_base_branch=` эталона политики, пропуск белого
списка по свежему sha `origin/<base>` и пропуск хука — все методы файла
зелёные; мутации «проверка по локальной ссылке» и «хук не пропускает» —
красные.

Связка, которую держит файл: «запись проекта в локальном слое песочницы —
`workspace.ensure_clone` (клон, `core.hooksPath`, файл политики) — единая
точка отправки `gitcmd.in_repo` (белый список, эталон политики, `-c
core.hooksPath`) — настоящий хук `scripts/git-hooks/target-human/pre-push`
— голый `origin` во временном каталоге». Стенд — `real_git`: `config.ROOT`
— настоящий git-репозиторий, в него закоммичен каталог `scripts/git-hooks`
проверяемого дерева. `HOME` — временный каталог, переменные `GIT_*`
процесса сняты, сети нет: `url` записи — путь голого репозитория.

Отправка идёт настоящим git; ветку в `origin` тест читает сам
(`ls-remote` голого репозитория). Прямая отправка мимо `gitcmd` (обычный
`git push` из клона) проверяет хук как вторую линию: её белый список не
видит, хук срабатывает по постоянному `core.hooksPath` клона.

Имена проектов, компонентов, заданий, веток и параметров отправки — из
`random`; зерно печатается и входит в текст провала.
"""
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from orchestrator import (cleanup, config, gitcmd, idgen, store, targets,
                          workspace)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

REAL_RUN = subprocess.run
LETTERS = "abcdefghijkmnpqrstuvwxyz"
HOOK_PREFIX = "pre-push (target-human)"
REFUSED = gitcmd.PUSH_REFUSED_ACTION
OLD_FOREIGN_BRANCH = "не ветка живой задачи проекта"


def clean_env() -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k not in (gitcmd.PULT_MARKER_ENV,
                                                     config.ARTEL_TASK_ENV)}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git(repo: Path, *args: str, check: bool = True):
    res = REAL_RUN(["git", "-C", str(repo), *args], capture_output=True,
                   text=True, env=clean_env(), timeout=60,
                   start_new_session=True)
    if check:
        assert res.returncode == 0, f"git {' '.join(args)} в {repo}: {res.stderr}"
    return res


def out(repo: Path, *args: str) -> str:
    return git(repo, *args).stdout.strip()


class Stand:
    """Стенд проектов `target-human` в локальном слое песочницы `real_git`."""

    def __init__(self, monkeypatch, tmp_path: Path):
        self.monkeypatch = monkeypatch
        self.tmp = tmp_path
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()
        self.entries: dict = {}
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
        shutil.copytree(Path(CODE_ROOT) / "scripts" / "git-hooks",
                        root / "scripts" / "git-hooks",
                        ignore=shutil.ignore_patterns("__pycache__"),
                        dirs_exist_ok=True)
        git(root, "add", "-A", "scripts")
        git(root, "commit", "-q", "--no-verify", "-m", "хуки пульта")

    def word(self, size: int = 6) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def bare(self, label: str) -> Path:
        bare = self.tmp / f"{label}.git"
        git(self.tmp, "init", "-q", "--bare", "-b", config.MAIN_BRANCH, str(bare))
        seed = self.tmp / f"seed-{label}"
        git(self.tmp, "init", "-q", "-b", config.MAIN_BRANCH, str(seed))
        (seed / "README").write_text(f"{label}\n", encoding="utf-8")
        git(seed, "add", "-A")
        git(seed, "commit", "-q", "--no-verify", "-m", f"init {label}")
        (seed / "app.py").write_text(f"APP = '{label}'\n", encoding="utf-8")
        git(seed, "add", "-A")
        git(seed, "commit", "-q", "--no-verify", "-m", f"второй {label}")
        git(seed, "push", "-q", "--no-verify", str(bare),
            f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        return bare

    def write_layer(self) -> None:
        local = targets.local_path()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text("targets:\n" + "".join(self.entries.values()),
                         encoding="utf-8")

    def gitlab_entry(self, name: str, url: str, ci_base: dict | None) -> str:
        comp, job = f"c{self.word()}", f"t{self.word()}"
        lines = [f"  {name}:", "    description:",
                 f"      base: {config.MAIN_BRANCH}", "      components:",
                 f"        {comp}:", "          command: [python3, -m, pytest]",
                 "          report: junit-xml", "          long_lived_dir: tests",
                 "          long_lived_name: test_<id>_<name>.py",
                 "          full_suite: ci", f"          ci_job: {job}"]
        for key, value in (ci_base or {}).items():
            lines.append(f"          {key}: {value}")
        lines += ["    policy:", "      no_paths: []", "      project_skills: []",
                  "      merge_gate: target-human", "      components:",
                  f"        {comp}:", "          weakening_scope: [tests/**]",
                  "          mutation_claim_scope: [tests/test_*.py]",
                  "    machine:", "      forge: gitlab", f"      url: {url}",
                  f"      token_slot: {name}-token"]
        return "\n".join(lines) + "\n"

    def github_entry(self, name: str, url: str) -> str:
        return (f"  {name}:\n"
                f"    description:\n      base: {config.MAIN_BRANCH}\n"
                f"      test_profile:\n        command: [python3, -m, pytest]\n"
                f"        long_lived_dir: tests\n"
                f"        long_lived_name: test_<id>_<name>.py\n"
                f"    policy:\n      no_paths: []\n      project_skills: []\n"
                f"      merge_gate: target-human\n"
                f"      weakening_scope: [tests/**/*.py]\n"
                f"      mutation_claim_scope: [tests/test_*.py]\n"
                f"    machine:\n      forge: github\n"
                f"      url: {url}\n"
                f"      token_slot: {name}-token\n")

    def project(self, kind: str = "branch"):
        """Проект `target-human` и его клон, заведённый пультом. `kind`:
        `branch` — компонент `full_suite: ci` с `ci_base: branch`; `plain`
        — тот же компонент без `ci_base`; `github` — запись GitHub с
        `test_profile`."""
        name = f"q{self.word()}"
        bare = self.bare(name)
        cbb = f"artel-base-{self.word()}"
        if kind == "branch":
            options = [f"ci.variable=AB_{self.word().upper()}=1",
                       f"V{self.word().upper()}=x"]
            text = self.gitlab_entry(name, str(bare), {
                "ci_base": "branch", "ci_base_branch": cbb,
                "ci_base_push_options": "[" + ", ".join(options) + "]"})
        elif kind == "plain":
            text = self.gitlab_entry(name, str(bare), None)
        else:
            text = self.github_entry(name, str(bare))
        self.entries[name] = text
        self.write_layer()
        clone, error = workspace.ensure_clone(name)
        assert error is None, self.note(f"клон не заведён: {error}")
        return name, clone, bare, cbb

    def task(self, name: str, clone: Path) -> tuple:
        """Живая задача проекта с веткой по шаблону (ветка есть в клоне)."""
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-{self.word()}"
        git(clone, "branch", "-f", branch, config.MAIN_BRANCH)
        store.insert_task(store.db(), task_id, "Задача", "in_dev", branch, name,
                          config.DEFAULT_BUDGET_USD)
        return task_id, branch

    def side_commit(self, clone: Path) -> str:
        """Коммит клона поверх `main`, которого нет в `origin`."""
        git(clone, "checkout", "-q", "-B", f"side-{self.word()}",
            config.MAIN_BRANCH)
        (clone / f"side_{self.word()}.py").write_text("S = 1\n", encoding="utf-8")
        git(clone, "add", "-A")
        env_commit = REAL_RUN(
            ["git", "-C", str(clone), "commit", "-q", "--no-verify", "-m", "сбоку"],
            capture_output=True, text=True, timeout=60, start_new_session=True,
            env=dict(clean_env(), **{gitcmd.PULT_MARKER_ENV: "1"}))
        assert env_commit.returncode == 0, env_commit.stderr
        sha = out(clone, "rev-parse", "HEAD")
        git(clone, "checkout", "-q", config.MAIN_BRANCH)
        return sha


@pytest.fixture
def stand(real_git, monkeypatch, tmp_path):
    return Stand(monkeypatch, tmp_path)


def origin_sha(bare: Path, branch: str) -> str:
    text = out(bare, "ls-remote", str(bare), f"refs/heads/{branch}")
    return text.split()[0] if text.split() else ""


def main_sha(clone: Path) -> str:
    return out(clone, "rev-parse", f"refs/remotes/origin/{config.MAIN_BRANCH}")


def older_main(clone: Path) -> str:
    """Предок вершины `origin/main` — не сама вершина."""
    return out(clone, "rev-parse", f"refs/remotes/origin/{config.MAIN_BRANCH}~1")


def pult_push(clone: Path, *words: str, task_id: str | None = None):
    args = ("push", *words)
    if task_id is None:
        return gitcmd.in_repo(clone, *args)
    return gitcmd.in_repo(clone, *args, task_id=task_id)


def direct_push(clone: Path, *words: str):
    """Обычный `git push` из клона мимо `gitcmd`: хуки клона срабатывают
    по его постоянному `core.hooksPath`."""
    return git(clone, "push", *words, check=False)


def refused(res) -> str:
    return (res.stderr or "") + (res.stdout or "")


# ---------------------------------------------------------------- AC-10


@pytest.mark.parametrize("force", [False, True])
def test_ac10_whitelist_passes_ci_base_branch_ancestor_push(stand, force):
    """Белый список пропускает отправку и принудительную отправку sha — предка `origin/<base>` — ровно в `ci_base_branch`: ветка в `origin` стоит на этом sha.

    Сценарий (по случаю): проект `target-human` GitLab с компонентом
    `ci_base: branch`; через единую точку `gitcmd.in_repo` отправка
    `<sha>:refs/heads/<ci_base_branch>` (принудительная — с `--force`),
    где sha — предок вершины `origin/main` (не сама вершина). Код 0, в
    голом `origin` ветка `ci_base_branch` — на этом sha; повторная
    принудительная отправка вершины `main` (сдвиг ветки) тоже проходит.

    Ловит мутацию: белый список не знает `ci_base_branch` — прежний отказ
    «не ветка живой задачи проекта»; флаг `--force` остался вне белого
    списка для `ci_base_branch` — отказ «флаг --force»; хук не пропускает
    ветку вне шаблона задач — отказ хука, ветки в `origin` нет.
    """
    name, clone, bare, cbb = stand.project()
    sha = older_main(clone)
    flags = ("--force",) if force else ()
    res = pult_push(clone, *flags, "origin", f"{sha}:refs/heads/{cbb}")
    assert res.returncode == 0, stand.note(refused(res))
    assert origin_sha(bare, cbb) == sha, stand.note(refused(res))
    tip = main_sha(clone)
    res = pult_push(clone, "--force", "origin", f"{tip}:refs/heads/{cbb}")
    assert res.returncode == 0, stand.note(refused(res))
    assert origin_sha(bare, cbb) == tip, stand.note(refused(res))


@pytest.mark.parametrize("case", ["иная ветка", "иная ветка --force",
                                  "ветка задачи --force"])
def test_ac10_whitelist_refuses_other_branches_and_foreign_force(stand, case):
    """Отправка через белый список в иную ветку вне шаблона задач — прежний отказ белого списка; принудительная отправка в любую ветку, кроме `ci_base_branch`, — отказ; в `origin` ничего не появилось.

    Сценарий (по случаю): проект `ci_base: branch`; через `gitcmd.in_repo`
    (а) отправка sha — предка `origin/main` — в случайную ветку вне
    шаблона задач и не `ci_base_branch`: отказ с прежним текстом «… — не
    ветка живой задачи проекта»; (б) то же с `--force`; (в) принудительная
    отправка ветки живой задачи проекта. Код не 0, причина — отказ единой
    точки («отправка отказана»), ветки в `origin` нет.

    Ловит мутацию: исключение `ci_base_branch` в белом списке сделано для
    любой ветки вне шаблона (или снят запрет флага `--force` целиком) —
    отправка проходит, ветка появляется в `origin`.
    """
    name, clone, bare, cbb = stand.project()
    sha = older_main(clone)
    if case == "ветка задачи --force":
        task_id, branch = stand.task(name, clone)
        res = pult_push(clone, "--force", "origin",
                        f"{sha}:refs/heads/{branch}", task_id=task_id)
        target = branch
    else:
        target = f"other-{stand.word()}"
        flags = ("--force",) if case.endswith("--force") else ()
        res = pult_push(clone, *flags, "origin", f"{sha}:refs/heads/{target}")
    assert res.returncode != 0, stand.note(f"отправка в {target} прошла")
    assert REFUSED in refused(res), stand.note(refused(res))
    if case == "иная ветка":
        assert OLD_FOREIGN_BRANCH in refused(res), stand.note(refused(res))
    assert origin_sha(bare, target) == "", stand.note(refused(res))


@pytest.mark.parametrize("force", [False, True])
def test_ac10_whitelist_refuses_non_ancestor_into_ci_base_branch(stand, force):
    """Отправка в `ci_base_branch` sha, не являющегося предком `origin/<base>`, — отказ белого списка с причиной, ветки в `origin` нет.

    Сценарий (по случаю): проект `ci_base: branch`; в клоне коммит поверх
    `main`, которого нет в `origin`; через `gitcmd.in_repo` отправка его
    sha в `ci_base_branch` (с `--force` и без). Код не 0, вывод — отказ
    единой точки («отправка отказана») с непустой причиной, ветки
    `ci_base_branch` в `origin` нет.

    Ловит мутацию: «источник не проверен» — белый список пропускает любой
    sha в `ci_base_branch`; коммит вне `main` уходит в `origin`.
    """
    name, clone, bare, cbb = stand.project()
    sha = stand.side_commit(clone)
    flags = ("--force",) if force else ()
    res = pult_push(clone, *flags, "origin", f"{sha}:refs/heads/{cbb}")
    assert res.returncode != 0, stand.note("коммит вне main ушёл в ci_base_branch")
    text = refused(res)
    assert REFUSED in text, stand.note(text)
    assert text.split(REFUSED, 1)[1].strip(), stand.note(text)
    assert origin_sha(bare, cbb) == "", stand.note(text)


def test_ac10_whitelist_checks_fresh_origin_base_not_local_ref(stand):
    """Локальная `refs/remotes/origin/<base>` клона сдвинута на коммит `X` вне `<base>` в `origin`: отправка `X` в `ci_base_branch` — отказ белого списка по свежему sha `origin`, а не пропуск по локальной ссылке.

    Сценарий: проект `ci_base: branch`; в клоне коммит `X` поверх `main`,
    в `origin` его нет; тест сдвигает `refs/remotes/origin/main` клона на
    `X` (как могла бы роль: общий каталог git клона под её управлением).
    `X` — предок локальной ссылки и не предок `main` голого `origin`.
    Через `gitcmd.in_repo` отправка `X` в `ci_base_branch` (`--force`):
    код не 0, отказ единой точки («отправка отказана», а не только отказ
    хука), ветки в `origin` нет.

    Ловит мутацию: «проверка по локальной ссылке» — белый список сверяет
    предка с `refs/remotes/origin/<base>` клона; отправку `X` пропускает,
    хук по той же ссылке тоже пропускает — `X` в `origin`.
    """
    name, clone, bare, cbb = stand.project()
    x = stand.side_commit(clone)
    git(clone, "update-ref", f"refs/remotes/origin/{config.MAIN_BRANCH}", x)
    res = pult_push(clone, "--force", "origin", f"{x}:refs/heads/{cbb}")
    assert res.returncode != 0, stand.note("X ушёл в ci_base_branch")
    assert REFUSED in refused(res), stand.note(refused(res))
    assert origin_sha(bare, cbb) == "", stand.note(refused(res))


# ---------------------------------------------------------------- AC-11


@pytest.mark.parametrize("force", [False, True])
def test_ac11_real_push_passes_hook_into_ci_base_branch(stand, force):
    """Настоящая отправка через `gitcmd` sha — предка `origin/<base>` — в `ci_base_branch` проходит хук `pre-push` клона `target-human`; прямая отправка такого sha мимо `gitcmd` хук тоже пропускает.

    Сценарий (по случаю): клон `target-human` с каталогом хуков пульта
    `scripts/git-hooks/target-human`, голый `origin`. (1) Через
    `gitcmd.in_repo` отправка предка вершины `main` в `ci_base_branch`
    (`--force` — по случаю): код 0, ветка в `origin` на этом sha.
    (2) Обычный `git push` из клона (белый список не участвует, работает
    только хук по `core.hooksPath` клона) вершины `main` в
    `ci_base_branch`: код 0, ветка в `origin` на вершине.

    Ловит мутацию: «хук не пропускает» — хук не читает ключ
    `ci_base_branch=` файла политики (или эталон его не пишет) и отказывает
    ветке не по шаблону — обе отправки с кодом не 0, ветки в `origin` нет.
    """
    name, clone, bare, cbb = stand.project()
    sha = older_main(clone)
    flags = ("--force",) if force else ()
    res = pult_push(clone, *flags, "origin", f"{sha}:refs/heads/{cbb}")
    assert res.returncode == 0, stand.note(refused(res))
    assert origin_sha(bare, cbb) == sha, stand.note(refused(res))
    assert out(clone, "config", "--get", "core.hooksPath"), stand.note(
        "у клона нет core.hooksPath")
    tip = main_sha(clone)
    res = direct_push(clone, *flags, "origin", f"{tip}:refs/heads/{cbb}")
    assert res.returncode == 0, stand.note(refused(res))
    assert origin_sha(bare, cbb) == tip, stand.note(refused(res))


@pytest.mark.parametrize("case", ["иная ветка", "не предок"])
def test_ac11_hook_refuses_other_branch_and_non_ancestor(stand, case):
    """Хук `pre-push` клона — вторая линия: прямая отправка мимо `gitcmd` в иную ветку вне шаблона или sha — не предка `origin/<base>` — в `ci_base_branch` отказана хуком.

    Сценарий (по случаю): проект `ci_base: branch`; первая отправка
    пульта в `ci_base_branch` прошла (файл политики записан эталоном).
    Обычный `git push --force` из клона: (а) предка `main` в случайную
    ветку вне шаблона задач; (б) коммита поверх `main`, которого нет в
    `origin`, в `ci_base_branch`. Код не 0, вывод — отказ хука
    («pre-push (target-human)»), в `origin` ветка не появилась или не
    сдвинулась.

    Ловит мутацию: хук пропускает по ключу `ci_base_branch=` любую ветку
    вне шаблона либо не проверяет предка `origin/<base>` — отправка
    проходит.
    """
    name, clone, bare, cbb = stand.project()
    first = older_main(clone)
    res = pult_push(clone, "--force", "origin", f"{first}:refs/heads/{cbb}")
    assert res.returncode == 0, stand.note(refused(res))
    if case == "иная ветка":
        target = f"other-{stand.word()}"
        res = direct_push(clone, "--force", "origin",
                          f"{main_sha(clone)}:refs/heads/{target}")
        expected = ""
    else:
        target = cbb
        res = direct_push(clone, "--force", "origin",
                          f"{stand.side_commit(clone)}:refs/heads/{cbb}")
        expected = first
    assert res.returncode != 0, stand.note(f"хук пропустил отправку в {target}")
    assert HOOK_PREFIX in refused(res), stand.note(refused(res))
    assert origin_sha(bare, target) == expected, stand.note(refused(res))


@pytest.mark.parametrize("kind", ["plain", "github"])
def test_ac11_policy_text_without_ci_base_unchanged(stand, kind):
    """У записи без `ci_base` эталон файла политики — прежние четыре строки, без ключа `ci_base_branch`.

    Сценарий (по случаю): проект `target-human` GitLab с компонентом
    `full_suite: ci` без `ci_base`; проект GitHub с `test_profile`.
    `gitcmd.push_policy_text(<проект>, <запись>)` — ровно
    `project=…\\nbase=main\\nbranch_template=<умолчание>\\n
    artifacts_prefix=refs/artifacts/\\n`, и файл политики клона,
    записанный пультом, — тот же текст.

    Ловит мутацию: эталон пишет ключ `ci_base_branch=` (пустой или с
    именем по умолчанию) любой записи — текст отличается от прежнего.
    """
    name, clone, bare, _cbb = stand.project(kind)
    expected = (f"project={name}\nbase={config.MAIN_BRANCH}\n"
                f"branch_template={targets.DEFAULT_BRANCH_TEMPLATE}\n"
                f"artifacts_prefix=refs/artifacts/\n")
    assert gitcmd.push_policy_text(name, targets.target(name)) == expected
    policy = clone / ".git" / workspace.PUSH_POLICY_NAME
    assert policy.read_text(encoding="utf-8") == expected


# ---------------------------------------------------------------- AC-12


def test_ac12_kill_and_cleanup_keep_ci_base_branch(stand):
    """`kill` задачи и уборка ветки смерженной задачи не удаляют `ci_base_branch` в `origin`.

    Сценарий: проект `ci_base: branch`; пульт отправил предка `main` в
    `ci_base_branch`; две живые задачи проекта, ветка каждой отправлена в
    `origin` (обычным `git push` мимо пульта — записи «ветка отправлена»
    нет, `kill` убирает ветку задачи в `origin`). `cleanup.cmd_kill`
    первой задачи (`--yes`, причина) и `cleanup.cleanup_merged_remote`
    второй (смерженный main — вершина `origin/main`). После обоих
    `ci_base_branch` в `origin` стоит на прежнем sha.

    Ловит мутацию: уборка задачи удаляет и ветку отчёта базы проекта
    (например, все ветки `origin` вне шаблона задач или ветку, на которую
    задача отправляла базу) — `ci_base_branch` в `origin` нет.
    """
    name, clone, bare, cbb = stand.project()
    sha = older_main(clone)
    res = pult_push(clone, "--force", "origin", f"{sha}:refs/heads/{cbb}")
    assert res.returncode == 0, stand.note(refused(res))
    killed, killed_branch = stand.task(name, clone)
    merged, merged_branch = stand.task(name, clone)
    for branch in (killed_branch, merged_branch):
        git(clone, "push", "-q", "--no-verify", "origin",
            f"{sha}:refs/heads/{branch}")
    cleanup.cmd_kill(killed, confirmed=True, reason=f"сценарий {stand.word()}")
    assert origin_sha(bare, cbb) == sha, stand.note("kill удалил ci_base_branch")
    cleanup.cleanup_merged_remote(store.db(), merged, merged_branch,
                                  main_sha(clone))
    assert origin_sha(bare, cbb) == sha, stand.note(
        "уборка смерженной задачи удалила ci_base_branch")


# ---------------------------------------------------------------- AC-14


@pytest.mark.parametrize("kind", ["plain", "github"])
def test_ac14_records_without_ci_base_keep_old_push_rules(stand, kind):
    """Записи без `ci_base` (GitLab и GitHub): отправка в ветку вне шаблона задач и принудительная отправка — прежние отказы белого списка с прежними текстами; прямая отправка мимо `gitcmd` в ветку вне шаблона — прежний отказ хука.

    Сценарий (по случаю): проект `target-human` GitLab без `ci_base` и
    проект GitHub с `test_profile`. Через `gitcmd.in_repo`: отправка предка
    `main` в случайную ветку вне шаблона — отказ «… — не ветка живой
    задачи проекта»; та же отправка с `--force` — отказ «флаг --force вне
    белого списка». Обычный `git push` из клона в ветку вне шаблона —
    отказ хука «ветка не по шаблону». Ни одна ветка не появилась в
    `origin`.

    Ловит мутацию: пропуск ветки вне шаблона или флага `--force` в белом
    списке либо в хуке не ограничен записью с `ci_base: branch` — отправка
    у прежней записи проходит.
    """
    name, clone, bare, _cbb = stand.project(kind)
    sha = older_main(clone)
    target = f"other-{stand.word()}"
    res = pult_push(clone, "origin", f"{sha}:refs/heads/{target}")
    assert res.returncode != 0 and OLD_FOREIGN_BRANCH in refused(res), \
        stand.note(refused(res))
    res = pult_push(clone, "--force", "origin", f"{sha}:refs/heads/{target}")
    assert res.returncode != 0 and "флаг --force вне белого списка" in \
        refused(res), stand.note(refused(res))
    # Файл политики пульт пишет перед своей отправкой; отказанная отправка
    # до него не дошла — его кладёт заведение клона.
    res = direct_push(clone, "origin", f"{sha}:refs/heads/{target}")
    assert res.returncode != 0, stand.note(refused(res))
    assert HOOK_PREFIX in refused(res) and "ветка не по шаблону" in \
        refused(res), stand.note(refused(res))
    assert origin_sha(bare, target) == "", stand.note(refused(res))
