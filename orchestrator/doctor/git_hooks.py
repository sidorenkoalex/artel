"""Пакет orchestrator/doctor -- git-хуки защиты main главной копии.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
import hashlib
import os
from pathlib import Path

from orchestrator import doctor


# --- git-хуки защиты main главной копии (SPEC ---------------------------
# 01M2XMCC837R5CX9M58VARK85G, требования 4-5, AC-10/AC-11) ---------------

# Каталог хуков в репозитории и значение `core.hooksPath`, которым они
# включаются: относительный путь от корня рабочего дерева — git считает
# его от каталога, где хук запускается, так что каждая рабочая копия
# (главная и worktree задачи) берёт хуки из своего дерева.
HOOKS_PATH = "scripts/git-hooks"
HOOK_NAMES = ("pre-commit", "pre-push")
GIT_HOOKS_CHECK = "git-hooks"


def _inside_work_tree() -> bool:
    """`config.ROOT` — рабочее дерево git; `False` — git не ответил или
    каталог не репозиторий (песочницы тестов без `git init`)."""
    res = doctor.gitcmd.git("rev-parse", "--is-inside-work-tree")
    return (res is not None and res.returncode == 0
            and res.stdout.strip() == "true")


def _hooks_path_config() -> str:
    """Значение `core.hooksPath` репозитория `config.ROOT`; пустая строка —
    не задано или git не ответил."""
    res = doctor.gitcmd.git("config", "--get", "core.hooksPath")
    if res is None or res.returncode != 0:
        return ""
    return res.stdout.strip()


def _hook_files() -> list:
    return [doctor.config.ROOT / HOOKS_PATH / name for name in HOOK_NAMES]


def _is_executable(path) -> bool:
    return bool(path.stat().st_mode & 0o111)


def check_git_hooks() -> doctor.Check:
    """Хуки защиты main включены в главной копии (требование 5): `ok` при
    `core.hooksPath = scripts/git-hooks` и исполняемых файлах обоих
    хуков; `fail` с подсказкой `doctor --fix` иначе — путь не задан или
    задан другим, файла хука нет либо он без бита исполнения (git молча
    пропускает неисполняемый хук, защиты бы не было).

    `config.ROOT` не git-репозиторий или git не ответил — `skip`
    (честный пропуск, требование 9 SPEC/AC-13): сверять нечего, это
    песочница без `git init`, а не главная копия с выключенной защитой —
    тот же приём деградации, что у `check_root_pin` при недоступном
    origin, только не `ok`: об отсутствии сверки сказано прямо.
    """
    if not _inside_work_tree():
        return doctor.Check(GIT_HOOKS_CHECK, "skip",
                            "config.ROOT — не git-репозиторий (git не "
                            "ответил) — хуки не сверены")
    problems = []
    hooks_path = _hooks_path_config()
    if hooks_path != HOOKS_PATH:
        problems.append(f"core.hooksPath = {hooks_path or '(не задан)'}, "
                        f"ожидается {HOOKS_PATH}")
    for path in _hook_files():
        rel = f"{HOOKS_PATH}/{path.name}"
        if not path.is_file():
            problems.append(f"{rel}: файла нет")
        elif not _is_executable(path):
            problems.append(f"{rel}: без бита исполнения")
    if problems:
        return doctor.Check(GIT_HOOKS_CHECK, "fail",
                            "; ".join(problems) + " — включи: doctor --fix")
    return doctor.Check(GIT_HOOKS_CHECK, "ok",
                        f"core.hooksPath = {HOOKS_PATH}, хуки "
                        f"{', '.join(HOOK_NAMES)} исполняемы")


def _fix_git_hooks() -> None:
    """`doctor --fix` (требование 4): `git config core.hooksPath
    scripts/git-hooks` в главной копии и бит исполнения файлам хуков.

    Репозиторный конфиг, не `--global`/`init.templateDir` (требование 9):
    временные репозитории тестов и клоны внешних target'ов конфигурацию
    главной копии не наследуют. Бит ставится поверх текущего режима
    (`| 0o111`), не фиксированным `0o755`, — прочие биты файла не
    трогаются. Не git-репозиторий / git не ответил — ничего не пишется,
    строка вывода называет причину (тот же честный пропуск, что `skip`
    у `check_git_hooks`).
    """
    if not _inside_work_tree():
        print(f"  [FIX] {GIT_HOOKS_CHECK}: config.ROOT — не git-репозиторий "
              f"(git не ответил) — хуки не включены")
        return
    res = doctor.gitcmd.git("config", "core.hooksPath", HOOKS_PATH)
    if res is None or res.returncode != 0:
        reason = ((res.stderr or "").strip()[:200] if res is not None
                  else "") or "git не ответил"
        print(f"  [FIX] {GIT_HOOKS_CHECK}: core.hooksPath не выставлен: "
              f"{reason}")
        return
    made_executable, missing = [], []
    for path in _hook_files():
        if not path.is_file():
            missing.append(path.name)
        elif not _is_executable(path):
            os.chmod(path, path.stat().st_mode | 0o111)
            made_executable.append(path.name)
    detail = f"core.hooksPath = {HOOKS_PATH}"
    if made_executable:
        detail += f"; бит исполнения: {', '.join(made_executable)}"
    if missing:
        detail += f"; нет файлов: {', '.join(missing)}"
    print(f"  [FIX] {GIT_HOOKS_CHECK}: {detail}")


# --- хуки клонов проектов (SPEC 01M42PENCS26D0656X8FR7DFA7, требование 6,
# AC-11) ----------------------------------------------------------------
# Клон проекта (`.artel/projects/<имя>/repo`) и его рабочие копии задач
# берут хуки защиты main из ПИНА пульта — абсолютный `<config.ROOT>/
# scripts/git-hooks`, не `scripts/git-hooks` проверяемого кода клона:
# относительный путь git считал бы от рабочего дерева клона, и хуки
# приходили бы из кода задачи.

CLONE_HOOKS_CHECK = "clone-hooks"
PROJECT_CLONES_CHECK = "project-clones"


def _project_names() -> list:
    try:
        return list(doctor.targets.load())
    except doctor.targets.TargetsError:
        return []


def _clone_hooks_value(clone) -> str:
    res = doctor.gitcmd.in_repo(clone, "config", "--get", "core.hooksPath")
    if res is None or res.returncode != 0:
        return ""
    return res.stdout.strip()


def check_clone_hooks() -> list:
    """Строка на каждый проект `targets.yaml`: клона нет — `warn`
    (`doctor --fix` заведёт); `core.hooksPath` клона не задан или не равен
    абсолютному пути пина — `warn` с именем проекта и клона. Клоны проектов
    `target-human` сверяет отдельная строка `clone-push-hook`
    (`_check_push_hook_clones`)."""
    expected = str(doctor.workspace.hooks_path())
    missing, wrong, human = [], [], []
    for name in _project_names():
        clone = doctor.workspace.repo(name)
        if not clone.exists():
            missing.append(f"{name}: клона {clone} нет")
            continue
        if doctor.workspace.is_target_human(name):
            human.append((name, clone))
            continue
        value = _clone_hooks_value(clone)
        if value != expected:
            wrong.append(f"клон {name} ({clone}): core.hooksPath = "
                         f"{value or '(не задан)'}, ожидается {expected}")
    checks = [doctor.Check(PROJECT_CLONES_CHECK, "warn",
                           "; ".join(missing) + " — заведи: doctor --fix")
              if missing else
              doctor.Check(PROJECT_CLONES_CHECK, "ok", "клоны проектов на месте")]
    checks.append(doctor.Check(CLONE_HOOKS_CHECK, "warn",
                               "; ".join(wrong) + " — почини: doctor --fix")
                  if wrong else
                  doctor.Check(CLONE_HOOKS_CHECK, "ok",
                               f"core.hooksPath клонов = {expected}"))
    if human:
        checks.append(_check_push_hook_clones(human))
    return checks


# --- хук белого списка клонов проектов target-human (SPEC -----------------
# 01M6EZXVFGCHB1S4W45AWJ0QH6, требование 8) --------------------------------
# Эталон хука — содержимое в коммите HEAD главной копии пульта, не файл на
# диске: правку файла на диске строка и ловит. Эталон файла политики —
# текст по текущей записи проекта (`workspace.push_policy_text`).

PUSH_HOOK_CHECK = "clone-push-hook"
PUSH_HOOK_NAMES = ("pre-push", "pre-commit")


def _hook_rel(hook: str) -> str:
    return f"{HOOKS_PATH}/{doctor.gitcmd.TARGET_HUMAN_HOOKS}/{hook}"


def _reference_hooks() -> tuple[dict | None, str]:
    """({имя хука: содержимое в HEAD главной копии}, причина пропуска)."""
    if not _inside_work_tree():
        return None, "config.ROOT — не git-репозиторий (git не ответил)"
    texts = {}
    for hook in PUSH_HOOK_NAMES:
        try:
            res = doctor.gitcmd.read(doctor.config.ROOT, "show",
                                     f"HEAD:{_hook_rel(hook)}")
        except OSError as exc:
            return None, f"git show HEAD:{_hook_rel(hook)}: {exc}"
        if res.returncode != 0:
            return None, f"в HEAD главной копии нет {_hook_rel(hook)}"
        texts[hook] = res.stdout
    return texts, ""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hook_findings(directory: Path, reference: dict) -> list:
    findings = []
    for hook, text in reference.items():
        path = directory / hook
        if not path.is_file():
            findings.append(f"{path}: файла нет")
            continue
        actual = _sha256(path.read_bytes())
        if actual != _sha256(text):
            findings.append(f"{path}: sha256 {actual[:12]} — не эталон "
                            f"HEAD:{_hook_rel(hook)}")
        if not _is_executable(path):
            findings.append(f"{path}: без бита исполнения")
    return findings


def _worktree_paths(clone: Path) -> list:
    """Рабочие копии задач клона (`git worktree list`), кроме самого клона."""
    res = doctor.gitcmd.in_repo(clone, "worktree", "list", "--porcelain")
    if res is None or res.returncode != 0:
        return []
    paths = [Path(line[len("worktree "):]) for line in res.stdout.splitlines()
             if line.startswith("worktree ")]
    own = Path(clone).resolve()
    return [p for p in paths if p.resolve() != own and p.exists()]


def _worktree_hooks_values(worktree: Path) -> list:
    """Значения `core.hooksPath` из конфигурации самой рабочей копии
    (`config.worktree` её каталога git)."""
    res = doctor.gitcmd.in_repo(worktree, "rev-parse", "--absolute-git-dir")
    if res is None or res.returncode != 0 or not res.stdout.strip():
        return []
    own = Path(res.stdout.strip()) / "config.worktree"
    if not own.is_file():
        return []
    res = doctor.gitcmd.in_repo(worktree, "config", "--file", str(own),
                                "--get-all", "core.hooksPath")
    if res is None or res.returncode != 0:
        return []
    return [v for v in res.stdout.splitlines() if v]


def _push_hook_findings(name: str, clone: Path, reference: dict) -> list:
    expected = doctor.workspace.project_hooks_path(name)
    findings = []
    value = _clone_hooks_value(clone)
    if not value or not doctor.gitcmd.same_dir(value, expected):
        findings.append(f"core.hooksPath клона = {value or '(не задан)'}, "
                        f"ожидается {expected}")
    directory = Path(value) if value and os.path.isabs(value) else expected
    findings += _hook_findings(directory, reference)
    path, error = doctor.workspace.push_policy_path(clone)
    if error is not None:
        findings.append(error)
    else:
        try:
            entry = doctor.targets.target(name)
            want = doctor.workspace.push_policy_text(name, entry).encode("utf-8")
        except doctor.targets.TargetsError as exc:
            want = None
            findings.append(f"эталон файла политики не собран: {exc}")
        if want is not None:
            # Сумма по цели ссылки дала бы эталон — ссылка сама расхождение
            # (REVIEW R3-F1); `--fix` заменяет её обычным файлом.
            if path.is_symlink():
                findings.append(f"файл политики {path} — символическая ссылка "
                                f"на {os.readlink(path)}")
            elif not path.is_file():
                findings.append(f"файла политики {path} нет")
            else:
                try:
                    actual = path.read_bytes()
                except OSError as exc:
                    actual = None
                    findings.append(f"файл политики {path} не читается: {exc}")
                if actual is not None and _sha256(actual) != _sha256(want):
                    findings.append(f"файл политики {path}: sha256 "
                                    f"{_sha256(actual)[:12]} — не эталон по "
                                    f"записи")
    for worktree in _worktree_paths(clone):
        for wt_value in _worktree_hooks_values(worktree):
            if not doctor.gitcmd.same_dir(wt_value, expected):
                findings.append(f"core.hooksPath рабочей копии {worktree} = "
                                f"{wt_value}, ожидается {expected}")
    return [f"клон {name} ({clone}): {f}" for f in findings]


def _check_push_hook_clones(human: list) -> doctor.Check:
    """Строка `clone-push-hook` по клонам проектов `target-human` (`human`
    — пары (имя, клон)): хуки каталога, куда указывает `core.hooksPath`
    клона, против эталона из HEAD (сумма и бит исполнения), файл политики
    против эталона по записи, `core.hooksPath` клона и рабочих копий задач.
    `config.ROOT` не репозиторий или в HEAD нет файла хука — `skip`
    (ANSWER-1 п. 5)."""
    reference, why = _reference_hooks()
    if reference is None:
        return doctor.Check(PUSH_HOOK_CHECK, "skip", f"{why} — хуки клонов "
                            f"target-human не сверены")
    findings = []
    for name, clone in human:
        findings += _push_hook_findings(name, clone, reference)
    if findings:
        return doctor.Check(PUSH_HOOK_CHECK, "fail",
                            "; ".join(findings) + " — почини: doctor --fix")
    return doctor.Check(PUSH_HOOK_CHECK, "ok",
                        f"хуки и файл политики клонов target-human — эталон "
                        f"({', '.join(n for n, _c in human)})")


def _fix_push_hook_clone(name: str, clone: Path, reference: dict | None,
                         why: str) -> None:
    """`doctor --fix` клона проекта `target-human`: файлы хуков каталога
    пульта проекта — из HEAD с битом исполнения, файл политики — эталон,
    `core.hooksPath` клона — каталог пульта проекта."""
    expected = doctor.workspace.project_hooks_path(name)
    done = []
    if reference is None:
        print(f"  [FIX] {PUSH_HOOK_CHECK}: клон {name}: хуки не восстановлены "
              f"— {why}")
    else:
        for hook, text in reference.items():
            path = expected / hook
            try:
                if not path.is_file() or path.read_bytes() != text:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(text)
                    done.append(f"{hook} из HEAD")
                if not _is_executable(path):
                    os.chmod(path, path.stat().st_mode | 0o111)
                    done.append(f"бит исполнения {hook}")
            except OSError as exc:
                print(f"  [FIX] {PUSH_HOOK_CHECK}: клон {name}: {path}: {exc}")
    error = doctor.workspace.write_push_policy(clone, name)
    print(f"  [FIX] {PUSH_HOOK_CHECK}: клон {name}: "
          + (error if error else "файл политики — эталон"))
    value = _clone_hooks_value(clone)
    if not value or not doctor.gitcmd.same_dir(value, expected):
        error = doctor.workspace.set_clone_hooks(clone, name)
        done.append(error if error else f"core.hooksPath = {expected}")
    if done:
        print(f"  [FIX] {PUSH_HOOK_CHECK}: клон {name}: {'; '.join(done)}")


def _fix_project_clones() -> None:
    """`doctor --fix`: недостающий клон каждого проекта заводится
    (`workspace.ensure_clone`, хуки пина ставятся там же); существующему —
    `core.hooksPath` = абсолютный путь пина, если стоит другое значение;
    клону проекта `target-human` — хуки, файл политики и `core.hooksPath`
    к эталону (`_fix_push_hook_clone`)."""
    expected = str(doctor.workspace.hooks_path())
    reference = why = None
    for name in _project_names():
        clone = doctor.workspace.repo(name)
        if not clone.exists():
            _path, error = doctor.workspace.ensure_clone(name)
            print(f"  [FIX] {PROJECT_CLONES_CHECK}: "
                  + (error if error else f"заведён клон {name} — {clone}"))
            continue
        if doctor.workspace.is_target_human(name):
            if why is None:
                reference, why = _reference_hooks()
            _fix_push_hook_clone(name, clone, reference, why)
            continue
        if _clone_hooks_value(clone) == expected:
            continue
        error = doctor.workspace.set_clone_hooks(clone)
        print(f"  [FIX] {CLONE_HOOKS_CHECK}: "
              + (f"клон {name}: {error}" if error
                 else f"клон {name}: core.hooksPath = {expected}"))
