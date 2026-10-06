"""Приложения PLAN на дереве полного прогона ветки задачи (SPEC
01M46C776SZEMYPBQGPNJN1TXY): общий узел наложения приложений для гейта
мержа, автогейта приёмки, `approve` в `acceptance` и `suite-run`.

Код задачи вправе краснеть без приложений PLAN к защищённым путям
(прецедент 05.10, 01M45FJVGQT1K0P8HDEXZX6HS7: профиль в `targets.yaml`,
песочница `tests/test_invariants.py`). До этой задачи приложения
накладывали только CI ветки и гейт мержа, а автогейт и approve гоняли
набор в рабочей копии без них: 14 инвариантов были красны по построению,
приёмка шла через `approve --accept-red`, роль чинила то, что чинить не
должна.

Прогон с приложениями идёт на ВРЕМЕННОМ дереве (`git worktree add
--detach` в клоне задачи): рабочая копия задачи, её индекс, ветка и ссылки
не трогаются, дерево убирается на любом исходе (`finally`). Отказ наложения
и сбой git — отказ без прогона, а не прогон без приложений (fail-closed).
"""
import contextlib
import shutil
import tempfile
from pathlib import Path
from typing import Callable, NamedTuple

from scripts import guard

from . import artifact_branch, artifact_source, gitcmd, repo_context, workspace
from .advance_gates.plan_appendix import git_apply

# Признак прогона на дереве с приложениями — в записи журнала, detail и
# отчёте `suite-run` (требование 5): по нему прогон с приложениями
# отличается от прогона рабочей копии.
WITH_APPENDICES = "с приложениями PLAN"


class Inapplicable(NamedTuple):
    """Приложение, не легшее на дерево: номер в порядке PLAN (с 1),
    само приложение и ответ git."""
    number: int
    appendix: guard.PlanAppendix
    answer: str


def apply_in_order(tree: Path, appendices: list,
                   already_applied: Callable[[int, guard.PlanAppendix], bool]
                   | None = None) -> tuple[list[str], Inapplicable | None]:
    """Приложения ПОДРЯД, в порядке PLAN, одно поверх другого — тем же
    `git_apply`, что гейт применимости на выходе `in_dev`: приложение,
    опирающееся на строку предыдущего, ложится только так.

    `already_applied(номер, приложение)` спрашивается про приложение, не
    легшее прямым `git apply`: `True` — оно уже есть в дереве и
    пропускается (гейт мержа: уже наложено в подтянутом main, SPEC
    01M443HV9SJYVYQTHJSQ87QV68).

    (пути наложенных приложений без повторов, `None`) — всё легло; (пути
    до отказа, `Inapplicable`) — первое неприменимое, дальше не
    накладывается."""
    paths: list[str] = []
    for number, appendix in enumerate(appendices, 1):
        answer = git_apply(tree, appendix)
        if answer and already_applied is not None and already_applied(
                number, appendix):
            continue
        if answer:
            return paths, Inapplicable(number, appendix, answer)
        paths.extend(p for p in appendix.paths if p not in paths)
    return paths, None


def read_plan(conn, task_id: str) -> tuple[list, list[str], str]:
    """(приложения, ошибки разбора, причина непрочитанного PLAN) — PLAN.md
    задачи из ссылки документов (`artifact_source.resolve`), тот же
    источник, что у гейта мержа. Непрочитанный PLAN — `([], [], причина)`:
    решает вызывающий (гейт мержа — «приложений нет» с записью журнала)."""
    branch, _foreign = artifact_source.resolve(conn, task_id)
    text, reason = artifact_branch.show(task_id, branch,
                                        f"tasks/{task_id}/PLAN.md")
    if text is None:
        return [], [], f"PLAN.md не читается с ветки {branch}: {reason}"
    appendices, errors = guard.plan_appendices(text)
    return appendices, errors, ""


class SuiteTree(NamedTuple):
    """Корень полного прогона ветки.

    `root` — каталог прогона (рабочая копия либо временное дерево);
    `None` — прогона не будет, причина в `refusal`. `note` — признак
    «с приложениями PLAN» и пути наложенных; пусто — прогон в рабочей
    копии, как до задачи. `warning` — PLAN не прочитан, прогон идёт без
    приложений (тот же исход, что на гейте мержа)."""
    root: Path | None
    note: str
    refusal: str
    warning: str

    def mark(self, detail: str) -> str:
        """`detail` с признаком прогона на дереве с приложениями либо с
        причиной, по которой PLAN не прочитан и прогон шёл без них."""
        if self.note:
            return f"{detail} [{self.note}]"
        if self.warning:
            return f"{detail} [без приложений PLAN: {self.warning}]"
        return detail


def _rev_sha(wt: Path, branch: str | None) -> str:
    if branch is None:
        return gitcmd.head_sha(wt)
    return gitcmd.branch_head_sha(branch, repo=wt)


def _git_reason(res) -> str:
    if res is None:
        return "git не ответил"
    return ((res.stderr or res.stdout or "").strip()[:300]
            or f"git вернул {res.returncode}")


def _carry_uncommitted(wt: Path, tree: Path) -> str:
    """Незакоммиченные правки рабочей копии (изменённые, удалённые и
    неотслеживаемые не игнорируемые файлы) — копией файлов во временное
    дерево; рабочая копия только читается. Пустая строка — перенесено,
    иначе причина отказа."""
    listings = []
    try:
        for args in (("diff", "--name-only", "--no-renames", "-z", "HEAD"),
                     ("ls-files", "--others", "--exclude-standard", "-z")):
            res = gitcmd.in_repo(wt, *args)
            if res is None or res.returncode != 0:
                return (f"незакоммиченные правки рабочей копии не прочитаны: "
                        f"{_git_reason(res)}")
            listings.append(res.stdout)
    except UnicodeDecodeError as exc:
        return f"незакоммиченные правки рабочей копии не прочитаны: {exc}"
    paths = sorted({p for text in listings for p in text.split("\0") if p})
    try:
        for rel in paths:
            src, dst = wt / rel.rstrip("/"), tree / rel.rstrip("/")
            if dst.is_symlink() or dst.is_file():
                dst.unlink()
            elif dst.is_dir():
                shutil.rmtree(dst)
            if not (src.is_symlink() or src.exists()):
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir() and not src.is_symlink():
                shutil.copytree(src, dst, symlinks=True)
            else:
                shutil.copy2(src, dst, follow_symlinks=False)
    except OSError as exc:
        return f"незакоммиченные правки рабочей копии не перенесены: {exc}"
    return ""


def _inapplicable_refusal(failure: Inapplicable) -> str:
    paths = ", ".join(failure.appendix.paths)
    return (f"приложение {failure.number} PLAN ({paths}) не накладывается на "
            f"дерево прогона: {failure.answer} — полный набор не запускался")


def _prepared(wt: Path, branch: str | None, appendices: list,
              tree: Path) -> tuple[str, str]:
    """Временное дерево `tree` с наложенными приложениями: (признак с
    путями, "") либо ("", причина отказа)."""
    sha = _rev_sha(wt, branch)
    if not sha:
        what = f"голова ветки {branch}" if branch else "HEAD рабочей копии"
        return "", (f"дерево прогона с приложениями PLAN не подготовлено: "
                    f"{what} не прочитана — полный набор не запускался")
    res = gitcmd.in_repo(wt, "worktree", "add", "--detach", str(tree), sha)
    if res is None or res.returncode != 0:
        return "", (f"дерево прогона с приложениями PLAN не подготовлено: "
                    f"git worktree add: {_git_reason(res)} — полный набор не "
                    f"запускался")
    if branch is None:
        error = _carry_uncommitted(wt, tree)
        if error:
            return "", f"{error} — полный набор не запускался"
    already: list[int] = []

    def in_tree(number: int, appendix) -> bool:
        if git_apply(tree, appendix, "--reverse", "--check"):
            return False
        already.append(number)
        return True

    paths, failure = apply_in_order(tree, appendices, in_tree)
    if failure is not None:
        return "", _inapplicable_refusal(failure)
    note = f"{WITH_APPENDICES}: {', '.join(paths) or 'нет новых правок'}"
    if already:
        note += (f"; уже в дереве: приложения "
                 f"{', '.join(str(n) for n in already)}")
    return note, ""


@contextlib.contextmanager
def suite_tree(conn, task_id: str, wt: Path, branch: str | None = None):
    """Корень полного прогона ветки задачи (`SuiteTree`) на время блока
    `with` (требования 1-4).

    Задача не артели или PLAN без приложений — рабочая копия `wt`, как до
    задачи (требование 3). Иначе — временное дерево: `branch` задан —
    голова этой ветки (автогейт, approve); `None` — HEAD рабочей копии с
    её незакоммиченными правками (`suite-run`). Поверх — приложения PLAN
    подряд (`apply_in_order`); приложение, уже наложенное в дереве
    (подтянутый main его несёт), пропускается тем же правилом, что на
    гейте мержа.

    Отказ разбора, наложения или git — `root=None` с причиной, прогона нет.
    Временное дерево снимается с учёта клона и удаляется на любом исходе,
    включая исключение внутри блока (требование 2)."""
    target = workspace.task_target(task_id)
    if not repo_context.is_artel(repo_context.resolve(target)):
        yield SuiteTree(wt, "", "", "")
        return
    appendices, errors, unread = read_plan(conn, task_id)
    if errors:
        yield SuiteTree(None, "", (f"приложения PLAN не разобраны: "
                                   f"{'; '.join(errors)} — полный набор не "
                                   f"запускался"), "")
        return
    if not appendices:
        yield SuiteTree(wt, "", "", unread)
        return
    holder = Path(tempfile.mkdtemp(prefix="artel-appendix-suite-"))
    tree = holder / "tree"
    try:
        note, refusal = _prepared(wt, branch, appendices, tree)
        if refusal:
            yield SuiteTree(None, "", refusal, "")
        else:
            yield SuiteTree(tree, note, "", "")
    finally:
        gitcmd.in_repo(wt, "worktree", "remove", "--force", str(tree))
        shutil.rmtree(holder, ignore_errors=True)
        gitcmd.in_repo(wt, "worktree", "prune")
