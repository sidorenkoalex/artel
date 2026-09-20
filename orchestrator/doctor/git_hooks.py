"""Пакет orchestrator/doctor -- git-хуки защиты main главной копии.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
import os

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
