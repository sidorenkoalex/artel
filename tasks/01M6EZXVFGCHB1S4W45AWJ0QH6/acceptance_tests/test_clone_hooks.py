"""Каталог хуков `target-human` в клоне проекта: `core.hooksPath`, файл политики, правила `pre-push` и `pre-commit`; прежние хуки главной копии и клона проекта `operator`.

Группа: разовый
Красен до реализации: каталога `scripts/git-hooks/target-human` нет — `ensure_clone` ставит клону прежний `<config.ROOT>/scripts/git-hooks` и не пишет `artel-push-policy`, а прежний `pre-push` пропускает тег, удаление ветки, ветку не по шаблону, `refs/notes/*`, любую отправку при `ARTEL_PULT_GIT=1` и не знает файла политики.

Группа «разовый» — не по смыслу свойства (оно обязано держаться и после
мержа), а по правилу guard: долгоживущему файлу закрыт вызов git через
`subprocess` (`scripts/guard.py::SIGN_GIT_CALL`), а предмет критериев —
сами хуки git в настоящем клоне.

Стенд — `_stand.Stand` поверх `real_git`: каталог `scripts/git-hooks`
проверяемого дерева скопирован в `config.ROOT` и закоммичен; проект с
bare-`origin` во временном каталоге; клон заводит `workspace.ensure_clone`.
Отправки и коммиты — прямым настоящим git из клона (не через пульт): так
работает роль или Оператор из оболочки. Отказ хука отличается от прочих
сбоев контрольным повтором той же команды с `--no-verify` — он проходит.
Имена проектов, веток и тегов порождаются `random`; зерно печатается и
входит в текст провала.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _stand import (OPERATOR, POLICY_TAIL, TARGET_HUMAN, Stand, clean_env,  # noqa: E402
                    git, out, ref_sha, refs_of)

from orchestrator import config, doctor, idgen  # noqa: E402

KINDS = ["base", "tag", "delete", "nontemplate"]
IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


@pytest.fixture
def stand(real_git, monkeypatch, tmp_path):
    return Stand(real_git, monkeypatch, tmp_path)


def prepare(stand, clone: Path, bare: Path, kind: str) -> str:
    """Готовит отправку вида `kind` в клоне; отдаёт её refspec."""
    if kind == "base":
        branch = stand.template_branch()
        stand.commit_branch(clone, branch)
        return f"refs/heads/{branch}:refs/heads/{config.MAIN_BRANCH}"
    if kind == "tag":
        tag = "v" + stand.name("")
        git(clone, "tag", tag)
        return f"refs/tags/{tag}:refs/tags/{tag}"
    if kind == "delete":
        branch = stand.template_branch()
        git(bare, "update-ref", f"refs/heads/{branch}",
            out(bare, "rev-parse", config.MAIN_BRANCH))
        return f":refs/heads/{branch}"
    branch = "feature/" + stand.name("")
    stand.commit_branch(clone, branch)
    return f"refs/heads/{branch}:refs/heads/{branch}"


def push_argv(form: str, verify: bool, dest: str, spec: str) -> list:
    """argv git отправки формой `form`; `verify=False` — с `--no-verify`."""
    skip = [] if verify else ["--no-verify"]
    if form == "alias":
        return ["-c", "alias.p=push", "p", *skip, dest, spec]
    if form == "bang":
        return ["-c", "alias.p=!git push", "p", *skip, dest, spec]
    return ["push", *skip, dest, spec]


def assert_hook_refuses(stand, clone: Path, bare: Path, argv_of, env: dict,
                        what: str) -> None:
    """Отправка `argv_of(True)` — ненулевой код, ссылки `origin` прежние;
    та же отправка с `--no-verify` проходит (отказ дал именно хук)."""
    before = refs_of(bare)
    res = git(clone, *argv_of(True), env=env, check=False)
    assert res.returncode != 0, stand.note(f"{what}: хук пропустил\n{res.stderr}")
    assert refs_of(bare) == before, stand.note(f"{what}: ссылки origin изменились")
    control = git(clone, *argv_of(False), env=env, check=False)
    assert control.returncode == 0, stand.note(
        f"{what}: и с --no-verify отказ — отказ не хука\n{control.stderr}")


# --------------------------------------------------------------------- AC-1

@pytest.mark.parametrize("base, template", [
    ("main", None),
    ("develop", "feat/{id}/{slug}"),
])
def test_ac1_clone_gets_human_hooks_path_and_policy(stand, base, template):
    """Клон проекта `target-human`, заведённый `ensure_clone`: `core.hooksPath` и файл политики.

    Сценарий: запись проекта с `base` и `branch_template` (поля нет — шаблон
    по умолчанию), клон заводит пульт. `core.hooksPath` клона — абсолютный
    `<config.ROOT>/scripts/git-hooks/target-human`; `<клон>/.git/
    artel-push-policy` побайтно равен четырём строкам по записи.

    Ловит мутацию: клону `target-human` ставится прежний
    `<config.ROOT>/scripts/git-hooks` либо относительный путь; файл
    политики не пишется, пишется с `base` main вместо `base` записи или с
    шаблоном по умолчанию при заданном `policy.branch_template`.
    """
    name, clone, _bare = stand.project(TARGET_HUMAN, base=base,
                                       branch_template=template)
    value = out(clone, "config", "--get", "core.hooksPath")
    assert Path(value).is_absolute(), stand.note(f"core.hooksPath {value!r}")
    assert Path(value).resolve() == stand.human_hooks_dir().resolve(), \
        stand.note(f"core.hooksPath {value!r}")
    policy = stand.policy_path(clone)
    assert policy.is_file(), stand.note(f"нет {policy}")
    assert policy.read_bytes() == stand.expected_policy(name), \
        stand.note(f"{policy.read_bytes()!r}")


def test_ac1_manual_commit_to_clone_main_refused_by_pre_commit(stand):
    """Ручной коммит на `main` клона `target-human` без `ARTEL_PULT_GIT` — отказ хука `pre-commit`.

    Сценарий: в клоне (HEAD — `main`) `git commit --allow-empty` без маркера
    пульта: код ненулевой, `main` прежний; тот же коммит с
    `ARTEL_PULT_GIT=1` проходит — отказ дал хук, не иная причина.

    Ловит мутацию: в каталоге `target-human` нет `pre-commit` (перевод клона
    на отдельный каталог снял защиту `main`) — ручной коммит проходит.
    """
    _name, clone, _bare = stand.project(TARGET_HUMAN)
    assert out(clone, "symbolic-ref", "--short", "HEAD") == config.MAIN_BRANCH
    before = out(clone, "rev-parse", config.MAIN_BRANCH)
    res = git(clone, "commit", "-q", "--allow-empty", "-m", "ручной",
              env=clean_env(), check=False)
    assert res.returncode != 0, stand.note(f"коммит прошёл: {res.stdout}")
    assert out(clone, "rev-parse", config.MAIN_BRANCH) == before, \
        stand.note("main клона сдвинут")
    marked = git(clone, "commit", "-q", "--allow-empty", "-m", "пульт",
                 env=clean_env(ARTEL_PULT_GIT="1"), check=False)
    assert marked.returncode == 0, stand.note(f"с маркером отказ: {marked.stderr}")


# --------------------------------------------------------------------- AC-2

@pytest.mark.parametrize("kind", KINDS)
def test_ac2_pre_push_refuses_forbidden_pushes(stand, kind):
    """Хук `pre-push` клона `target-human` отказывает отправке в `base`, тега, удаления ветки, ветки не по шаблону.

    Сценарий: отправка по адресу `origin` (путь bare) из клона; код
    ненулевой, ссылки `origin` прежние; с `--no-verify` та же отправка
    проходит.

    Ловит мутацию: хук пропускает `refs/tags/*` (проверяет только
    `refs/heads/*`), пропускает удаление (нулевой sha не разбирается),
    сверяет только `base`, а не шаблон ветки, либо в клон попадает прежний
    `pre-push`, защищающий одну `main`.
    """
    _name, clone, bare = stand.project(TARGET_HUMAN)
    spec = prepare(stand, clone, bare, kind)
    assert_hook_refuses(stand, clone, bare,
                        lambda verify: push_argv("plain", verify, str(bare), spec),
                        clean_env(), f"{kind} ({spec})")


# --------------------------------------------------------------------- AC-3

@pytest.mark.parametrize("form", ["alias", "bang", "remote-name", "marker"])
@pytest.mark.parametrize("kind", KINDS)
def test_ac3_pre_push_refuses_in_every_form(stand, kind, form):
    """Те же запрещённые отправки отказываются хуком через `-c alias.p=push`, `!`-псевдоним, короткое имя `origin` и при `ARTEL_PULT_GIT=1`.

    Сценарий: форма `form` отправки вида `kind` из клона `target-human`; код
    ненулевой, ссылки `origin` прежние; та же форма с `--no-verify` проходит.

    Ловит мутацию: хук `target-human` начинается прежним
    `[ "$ARTEL_PULT_GIT" = 1 ] && exit 0` — отправка с маркером проходит;
    правила держит не хук, а только `gitcmd` — псевдоним и короткое имя из
    оболочки проходят.
    """
    _name, clone, bare = stand.project(TARGET_HUMAN)
    spec = prepare(stand, clone, bare, kind)
    env = clean_env(ARTEL_PULT_GIT="1") if form == "marker" else clean_env()
    plain = "plain" if form in ("remote-name", "marker") else form
    assert_hook_refuses(stand, clone, bare,
                        lambda verify: push_argv(plain, verify, "origin", spec),
                        env, f"{kind} формой {form} ({spec})")


# --------------------------------------------------------------------- AC-4

def test_ac4_template_branch_and_artifacts_ref_pass(stand):
    """Отправка ветки по шаблону и ссылки `refs/artifacts/<id>` из клона `target-human` проходит хук.

    Сценарий: ветка `task/<id>-<slug>` с новым коммитом и ссылка
    `refs/artifacts/<id>` отправляются в `origin` без `--no-verify`; код 0,
    обе ссылки на `origin` с sha клона.

    Ловит мутацию: хук сверяет имя ветки с шаблоном целиком как литерал
    (подстановки `{id}`/`{slug}` не раскрыты) либо отказывает любой ссылке
    вне `refs/heads/*`, включая `artifacts_prefix`.
    """
    _name, clone, bare = stand.project(TARGET_HUMAN)
    branch = stand.template_branch()
    sha = stand.commit_branch(clone, branch)
    res = git(clone, "push", "origin", f"refs/heads/{branch}:refs/heads/{branch}",
              env=clean_env(), check=False)
    assert res.returncode == 0, stand.note(f"ветка {branch}: {res.stderr}")
    assert ref_sha(bare, f"refs/heads/{branch}") == sha, stand.note(branch)
    ref = f"refs/artifacts/{idgen.new_task_id()}"
    git(clone, "update-ref", ref, sha)
    res = git(clone, "push", "origin", f"{ref}:{ref}", env=clean_env(), check=False)
    assert res.returncode == 0, stand.note(f"{ref}: {res.stderr}")
    assert ref_sha(bare, ref) == sha, stand.note(ref)


# --------------------------------------------------------------------- AC-5

@pytest.mark.parametrize("state", [
    "missing",
    pytest.param("unreadable", marks=pytest.mark.skipif(
        IS_ROOT, reason="под root файл без прав читается — состояние не воспроизвести")),
    "no-branch-template",
])
def test_ac5_broken_policy_refuses_any_push_naming_path(stand, state):
    """Файла политики нет, он не читается или в нём нет ключа `branch_template` — хук отказывает даже ветке по шаблону, причина называет путь файла.

    Сценарий: состояние `state` файла `<клон>/.git/artel-push-policy`, затем
    отправка ветки по шаблону в `origin`: код ненулевой, в stderr —
    `.git/artel-push-policy`, ссылки `origin` прежние.

    Ловит мутацию: хук при отсутствии файла или ключа подставляет шаблон по
    умолчанию и пропускает ветку `task/…`; отказ без пути файла в причине.
    """
    _name, clone, bare = stand.project(TARGET_HUMAN)
    policy = stand.policy_path(clone)
    if state == "missing":
        policy.unlink(missing_ok=True)
    elif state == "unreadable":
        policy.write_bytes(policy.read_bytes() if policy.exists() else b"")
        policy.chmod(0)
    else:
        kept = [line for line in policy.read_text(encoding="utf-8").splitlines(True)
                if not line.startswith("branch_template=")] if policy.exists() else []
        policy.write_text("".join(kept), encoding="utf-8")
    try:
        branch = stand.template_branch()
        stand.commit_branch(clone, branch)
        before = refs_of(bare)
        res = git(clone, "push", "origin", f"refs/heads/{branch}:refs/heads/{branch}",
                  env=clean_env(), check=False)
    finally:
        if policy.exists():
            policy.chmod(0o644)
    assert res.returncode != 0, stand.note(f"{state}: хук пропустил")
    assert POLICY_TAIL in res.stderr, stand.note(f"{state}: путь не назван\n{res.stderr}")
    assert refs_of(bare) == before, stand.note(f"{state}: ссылки origin изменились")


# --------------------------------------------------------------------- AC-6

def test_ac6_main_copy_hooks_unchanged(stand, tmp_path):
    """Главная копия с `core.hooksPath = scripts/git-hooks`: отправка в `main` без маркера отказывается, с маркером проходит.

    Сценарий: у `config.ROOT` — bare-`origin`; новый коммит на `main` (с
    маркером); `git push origin main` без `ARTEL_PULT_GIT` — код ненулевой,
    `main` на `origin` прежний; с `ARTEL_PULT_GIT=1` — `main` на `origin`
    равен новому коммиту.

    Ловит мутацию: прежний `scripts/git-hooks/pre-push` заменён хуком
    `target-human` (маркер больше не пропускает отправку в `main`) либо
    перестал защищать `main`.
    """
    root = Path(config.ROOT)
    bare = tmp_path / "pult.git"
    git(root, "init", "-q", "--bare", "-b", config.MAIN_BRANCH, str(bare))
    git(root, "config", "core.hooksPath", "scripts/git-hooks")
    git(root, "remote", "add", "origin", str(bare))
    git(root, "push", "-q", "origin", config.MAIN_BRANCH,
        env=clean_env(ARTEL_PULT_GIT="1"))
    before = ref_sha(bare, f"refs/heads/{config.MAIN_BRANCH}")
    git(root, "commit", "-q", "--allow-empty", "-m", "пульт",
        env=clean_env(ARTEL_PULT_GIT="1"))
    sha = out(root, "rev-parse", "HEAD")
    res = git(root, "push", "origin", config.MAIN_BRANCH, env=clean_env(), check=False)
    assert res.returncode != 0, stand.note("главная копия: push в main без маркера прошёл")
    assert ref_sha(bare, f"refs/heads/{config.MAIN_BRANCH}") == before
    res = git(root, "push", "origin", config.MAIN_BRANCH,
              env=clean_env(ARTEL_PULT_GIT="1"), check=False)
    assert res.returncode == 0, stand.note(f"с маркером отказ: {res.stderr}")
    assert ref_sha(bare, f"refs/heads/{config.MAIN_BRANCH}") == sha


def test_ac6_operator_clone_keeps_old_hooks(stand):
    """Клон проекта `github` + `operator`: прежний `<config.ROOT>/scripts/git-hooks`, отправка в `main` без маркера — отказ, с маркером — проходит.

    Сценарий: клон заводит `ensure_clone`; коммит на `main` клона с
    маркером; `git push origin main` без маркера — код ненулевой, `main` на
    `origin` прежний; с `ARTEL_PULT_GIT=1` — `main` на `origin` = коммит.

    Ловит мутацию: каталог `target-human` ставится клонам всех внешних
    проектов (признак проекта не через `merged_by_project_people`) — клон
    `operator` получает чужой путь и отказ отправки с маркером.
    """
    _name, clone, bare = stand.project(OPERATOR)
    value = out(clone, "config", "--get", "core.hooksPath")
    assert Path(value).resolve() == stand.hooks_dir().resolve(), \
        stand.note(f"core.hooksPath {value!r}")
    before = ref_sha(bare, f"refs/heads/{config.MAIN_BRANCH}")
    git(clone, "commit", "-q", "--allow-empty", "-m", "пульт",
        env=clean_env(ARTEL_PULT_GIT="1"))
    sha = out(clone, "rev-parse", "HEAD")
    res = git(clone, "push", "origin", config.MAIN_BRANCH, env=clean_env(), check=False)
    assert res.returncode != 0, stand.note("клон operator: push в main без маркера прошёл")
    assert ref_sha(bare, f"refs/heads/{config.MAIN_BRANCH}") == before
    res = git(clone, "push", "origin", config.MAIN_BRANCH,
              env=clean_env(ARTEL_PULT_GIT="1"), check=False)
    assert res.returncode == 0, stand.note(f"с маркером отказ: {res.stderr}")
    assert ref_sha(bare, f"refs/heads/{config.MAIN_BRANCH}") == sha


def test_ac6_clone_hooks_line_warns_for_operator_clone(stand, tmp_path):
    """Строка `clone-hooks` по клону проекта `operator` с неверным `core.hooksPath` — `warn`, как прежде.

    Сценарий: при верном значении проект в detail строки не назван; после
    `core.hooksPath` = чужой путь строка `clone-hooks` — `warn`, detail
    называет проект.

    Ловит мутацию: `check_clone_hooks` перестаёт сверять клоны проектов не
    `target-human` либо даёт им `fail` вместо прежнего `warn`.
    """
    name, clone, _bare = stand.project(OPERATOR)

    def line():
        found = [c for c in doctor.check_clone_hooks() if c.name == "clone-hooks"]
        assert len(found) == 1, stand.note(f"строки clone-hooks: {found}")
        return found[0]

    assert name not in line().detail, stand.note(line().detail)
    git(clone, "config", "core.hooksPath", str(tmp_path / "chuzhie"))
    broken = line()
    assert broken.status == "warn", stand.note(f"{broken.status}: {broken.detail}")
    assert name in broken.detail, stand.note(broken.detail)


# -------------------------------------------------------------------- AC-18

def test_ac18_notes_ref_refused(stand):
    """Отправка `refs/notes/x` из клона `target-human` отказывается хуком, ссылки на `origin` нет.

    Сценарий: локальная `refs/notes/x` на коммит клона, `git push origin
    refs/notes/x:refs/notes/x`: код ненулевой, на `origin` её нет; с
    `--no-verify` она проходит.

    Ловит мутацию: хук отказывает только `refs/tags/*`, а прочие ссылки вне
    `refs/heads/*` и `artifacts_prefix` пропускает.
    """
    _name, clone, bare = stand.project(TARGET_HUMAN)
    git(clone, "update-ref", "refs/notes/x", out(clone, "rev-parse", "HEAD"))
    spec = "refs/notes/x:refs/notes/x"
    before = refs_of(bare)
    res = git(clone, "push", "origin", spec, env=clean_env(), check=False)
    assert res.returncode != 0, stand.note("refs/notes/x прошла")
    assert ref_sha(bare, "refs/notes/x") == "" and refs_of(bare) == before
    control = git(clone, "push", "--no-verify", "origin", spec, env=clean_env(),
                  check=False)
    assert control.returncode == 0, stand.note(control.stderr)


def test_ac18_artifacts_ref_delete_passes(stand):
    """Удаление ранее отправленной `refs/artifacts/<id>` из клона `target-human` проходит хук.

    Сценарий: `refs/artifacts/<id>` отправлена в `origin`, затем `git push
    origin :refs/artifacts/<id>` без `--no-verify`: код 0, ссылки на
    `origin` больше нет.

    Ловит мутацию: хук отказывает любому удалению (нулевой sha) без разбора
    префикса ссылки — удаление ссылки документов не проходит.
    """
    _name, clone, bare = stand.project(TARGET_HUMAN)
    ref = f"refs/artifacts/{idgen.new_task_id()}"
    git(clone, "update-ref", ref, out(clone, "rev-parse", "HEAD"))
    res = git(clone, "push", "origin", f"{ref}:{ref}", env=clean_env(), check=False)
    assert res.returncode == 0 and ref_sha(bare, ref), stand.note(res.stderr)
    res = git(clone, "push", "origin", f":{ref}", env=clean_env(), check=False)
    assert res.returncode == 0, stand.note(f"удаление {ref}: {res.stderr}")
    assert ref_sha(bare, ref) == "", stand.note(f"{ref} осталась на origin")


def test_ac18_empty_branch_template_refuses_naming_path(stand):
    """Ключ `branch_template=` с пустым значением — отправка ветки отказывается хуком, причина называет путь файла политики.

    Сценарий: в файле политики строка `branch_template=` пуста, остальные
    ключи прежние; отправка ветки `task/<id>-<slug>` в `origin`: код
    ненулевой, в stderr — `.git/artel-push-policy`, ссылки прежние.

    Ловит мутацию: хук проверяет только наличие ключа, а не непустое
    значение — пустой шаблон совпадает с любой веткой либо с ошибкой без
    пути файла.
    """
    _name, clone, bare = stand.project(TARGET_HUMAN)
    policy = stand.policy_path(clone)
    lines = policy.read_text(encoding="utf-8").splitlines(True) if policy.exists() else []
    policy.write_text("".join("branch_template=\n" if line.startswith("branch_template=")
                              else line for line in lines), encoding="utf-8")
    branch = stand.template_branch()
    stand.commit_branch(clone, branch)
    before = refs_of(bare)
    res = git(clone, "push", "origin", f"refs/heads/{branch}:refs/heads/{branch}",
              env=clean_env(), check=False)
    assert res.returncode != 0, stand.note("ветка прошла при пустом шаблоне")
    assert POLICY_TAIL in res.stderr, stand.note(res.stderr)
    assert refs_of(bare) == before
