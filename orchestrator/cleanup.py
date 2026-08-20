"""kill switch и уборка хвостов задачи: каталог артефактов и ветка."""
import shutil

from . import config, gitcmd, store


def artifacts_in_main(task_id: str) -> bool | None:
    """Есть ли каталог задачи в дереве main. None — git не ответил.

    Достаточно самого факта наличия: артефакты задачи, убитой после
    мержа, — история (docs/design.md §6), её не трогаем целиком.
    """
    res = gitcmd.git("ls-tree", "-r", "--name-only", config.MAIN_BRANCH, "--",
                     f"tasks/{task_id}")
    if res.returncode != 0:
        return None
    return bool(res.stdout.strip())


def artifacts_tracked_here(task_id: str) -> bool | None:
    """Отслеживается ли каталог задачи здесь и сейчас. None — git не ответил.

    Смотрит индекс, а не дерево HEAD: закоммиченный в текущую ветку и
    просто добавленный `git add` каталоги одинаково опасны для rmtree.
    """
    res = gitcmd.git("ls-files", "--", f"tasks/{task_id}")
    if res.returncode != 0:
        return None
    return bool(res.stdout.strip())


def drop_task_dir(task_id: str) -> str:
    """Убирает каталог артефактов убитой задачи; строка — что вышло."""
    tdir = config.TASKS / task_id
    in_main = artifacts_in_main(task_id)
    if in_main is None:
        return f"каталог tasks/{task_id}/ оставлен: main не прочитан"
    if in_main:
        return f"каталог tasks/{task_id}/ оставлен: артефакты в main"
    if not tdir.exists():
        return f"каталога tasks/{task_id}/ нет"
    # Каталог убитой задачи мог уехать в чужую ветку через `git add -A`
    # разработчика — ровно инцидент T002 из SPEC. rmtree по отслеживаемым
    # файлам оставит в дереве удаления, которые следующий `git add -A`
    # утащит в тот же чужой коммит: мусор вместо уборки.
    tracked = artifacts_tracked_here(task_id)
    if tracked is None:
        return f"каталог tasks/{task_id}/ оставлен: индекс не прочитан"
    if tracked:
        here = gitcmd.current_branch()
        fix = ("сними его из индекса и повтори kill"
               if here == config.MAIN_BRANCH
               else f"перейди на {config.MAIN_BRANCH} и повтори kill")
        return (f"каталог tasks/{task_id}/ оставлен: отслеживается в "
                f"{here or 'текущей ветке'} — {fix}")
    try:
        shutil.rmtree(tdir)
    except OSError as exc:
        return f"каталог tasks/{task_id}/ не удалён: {exc}"
    return f"удалён каталог tasks/{task_id}/"


def drop_task_branch(branch: str) -> str:
    """Убирает локальную ветку убитой задачи; строка — что вышло."""
    if not branch:
        # Строка задачи из БД прошлых версий: ветка не записана — искать нечего.
        return "ветка задачи не записана — нечего удалять"
    if not gitcmd.branch_exists(branch):
        return f"локальной ветки {branch} нет"
    if gitcmd.branch_merged(branch):
        return f"ветка {branch} оставлена: смержена в {config.MAIN_BRANCH}"
    # -D, а не -d: удалить надо именно неслитую ветку, а на ней `-d` откажет.
    res = gitcmd.git("branch", "-D", branch)
    if res.returncode != 0:
        return f"ветка {branch} не удалена: {res.stderr.strip()[:200]}"
    return f"удалена ветка {branch}"


def cleanup_killed_task(conn, task_id: str, branch: str) -> None:
    """Убирает хвосты убитой задачи и перечисляет сделанное в журнале.

    Уборка идёт после смены состояния и не может её отменить: kill switch
    обязан срабатывать всегда. Поэтому любой невыясненный факт (git
    промолчал, main не найден) — это «оставлено» со своей причиной, а не
    исключение. Логи прогонов в .artel/logs/ не трогаются — история
    наблюдаемости переживает задачу.
    """
    # Не `branch_exists`: кроме факта нужна причина — отсутствующий main и
    # неустановленный git разбираются Оператором по-разному.
    main = gitcmd.git("rev-parse", "--verify", "--quiet",
                      f"refs/heads/{config.MAIN_BRANCH}")
    if main.returncode != 0:
        reason = main.stderr.strip()[:200] or f"ветки {config.MAIN_BRANCH} нет"
        notes = [f"уборка пропущена: {reason} — сверять не с чем"]
    elif gitcmd.current_branch() == branch:
        # Агент работает в этом же дереве (cmd_run: cwd=ROOT), так что HEAD
        # вполне может стоять на ветке задачи. Удалить её git не даст, а
        # снести закоммиченный в неё каталог — оставить грязное дерево:
        # ровно тот мусор, ради которого уборка и заводилась.
        notes = [f"уборка пропущена: ветка {branch} сейчас checked out — "
                 f"перейди на {config.MAIN_BRANCH} и повтори kill"]
    else:
        notes = [drop_task_dir(task_id), drop_task_branch(branch)]

    store.journal(conn, task_id, "orchestrator", "уборка", "; ".join(notes))
    for note in notes:
        print(f"  {note}")


def cmd_kill(task_id: str) -> None:
    conn = store.db()
    t = store.get_task(conn, task_id)
    store.set_state(conn, task_id, "killed", "operator", "kill switch")
    cleanup_killed_task(conn, task_id, t["branch"])
