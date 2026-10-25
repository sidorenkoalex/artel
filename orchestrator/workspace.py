"""Рабочая поверхность задачи: область проекта (ADR-0021 п.1, этап 2; до
него — git worktree в `.artel/worktrees/<id>`, SPEC T045).

У любого проекта, включая артель, есть клон `.artel/projects/<имя>/repo`
(`origin` — поле `url` записи `targets.yaml`) и своя git-рабочая копия
клона на каждую задачу `.artel/projects/<имя>/worktrees/<id>/` (SPEC
01M42PENCS26D0656X8FR7DFA7, требование 1). Ветка задачи, её рабочая копия
и вся их git-жизнь — в клоне: git главной копии пульта в ходе задачи не
меняется (требование 2). Решение Оператора 27.08 (P3, «параллельные
сессии») остаётся в силе: агентные шаги задачи исполняются в её
собственной рабочей копии, не в общей.

Клон заводится идемпотентно (`ensure_clone`): существующий каталог клона не
трогается. Хуки защиты `main` клона — из пина: `core.hooksPath` —
абсолютный `<config.ROOT>/scripts/git-hooks` (требование 6), а не
`scripts/git-hooks` проверяемого кода клона.

Все операции идут через `gitcmd` с явным репозиторием клона.
"""
import os
import shutil
import sys
from pathlib import Path

from . import config, gitcmd, lease, repo_context, store, targets


def area_consistent() -> bool:
    """Пути пульта согласованы (`repo_context.projects_root`). Иначе — так
    бывает у песочницы, подменившей корень, но не область проектов: клон и рабочие
    копии ушли бы в боевую `.artel/projects`, а ссылки документов — в её
    `origin` (инцидент 04.10.2026, задача 01M42PENCS26D0656X8FR7DFA7: 80
    тестовых ссылок `refs/artifacts/*` в боевом origin). При рассогласовании
    клон не заводится и git в нём не спрашивается."""
    return repo_context.projects_root() != repo_context.NO_AREA


AREA_MISMATCH_REASON = ("корень пульта config.ROOT подменён, а область "
                        "проектов config.PROJECTS — боевая: пути пульта "
                        "рассогласованы")


def repo(target: str) -> Path:
    """Клон проекта `target` (`repo_context.clone_path`)."""
    return repo_context.clone_path(target)


def hooks_path() -> Path:
    """Хуки защиты `main` из пина пульта — абсолютный путь (требование 6)."""
    return config.ROOT / "scripts" / "git-hooks"


def task_target(task_id: str) -> str:
    """Проект задачи по БД; БД нет или она непригодна (`store.db_usable`) —
    нет и строки задачи, проект тот же, что дал бы `store.task_target`
    (артель); БД ради чтения не заводится."""
    if not store.db_usable():
        return config.DEFAULT_TARGET
    return store.task_target(store.db(), task_id)


def task_repo(task_id: str) -> Path:
    """Клон проекта задачи — репозиторий её ветки, рабочей копии и ссылки
    документов (ADR-0021 п.1)."""
    return repo(task_target(task_id))


def set_clone_hooks(clone: Path) -> str | None:
    """`core.hooksPath` клона — абсолютный путь пина; `None` — поставлено,
    иначе причина."""
    res = gitcmd.in_repo(clone, "config", "core.hooksPath", str(hooks_path()))
    if res is None or res.returncode != 0:
        return ((res.stderr or "").strip()[:200] if res is not None
                else "git не ответил") or "git config вернул ненулевой код"
    return None


def inherit_identity(clone: Path) -> None:
    """Идентичность коммитера главной копии (`runner.git_identity`: её
    `git config --get user.name/user.email`, локальный слой и глобальный) —
    в локальный конфиг клона. `git clone` локальный конфиг не переносит, а
    коммиты задачи (подтяжка `main`, мерж, чекпоинты), шедшие до этапа 2 в
    главной копии с её идентичностью, теперь идут в клоне и его рабочих
    копиях: без переноса там, где идентичность задана только в главной
    копии, они отказывали бы «Committer identity unknown». Не задана и в
    главной копии — клону нечего переносить, прежний исход git."""
    from . import runner  # лениво: `runner` импортирует этот модуль
    identity = runner.git_identity()
    for option, names in runner.GIT_IDENTITY:
        value = identity.get(names[-1])
        if value:
            gitcmd.in_repo(clone, "config", option, value)


def ensure_clone(target: str) -> tuple[Path, str | None]:
    """Клон проекта `target` есть; (путь, причина отказа) — `None` при
    успехе. Существующий каталог клона не трогается вовсе (повторный вызов
    ничего не меняет). Нет клона — `git clone <url записи>` с хуками пина
    и ссылками документов из `origin` (`_fetch_docs_refs`); неудача
    `git clone` — каталог недоделанного клона убирается, причина называет
    клон и адрес. Отката на главную копию нет."""
    clone = repo(target)
    if not area_consistent():
        return clone, f"клон {clone} не заведён: {AREA_MISMATCH_REASON}"
    if clone.exists():
        return clone, None
    try:
        url = targets.target(target)["url"]
    except targets.TargetsError as exc:
        return clone, f"клон {clone} не заведён: {exc}"
    clone.parent.mkdir(parents=True, exist_ok=True)
    res = gitcmd.in_repo(clone.parent, "clone", "--quiet", url, clone.name)
    if res is None or res.returncode != 0:
        shutil.rmtree(clone, ignore_errors=True)
        detail = ((res.stderr or "").strip()[:300] if res is not None
                  else "git не ответил")
        return clone, f"клон {clone} из {url} не заведён: {detail}"
    hooks_error = set_clone_hooks(clone)
    if hooks_error is not None:
        return clone, f"клону {clone} не поставлены хуки: {hooks_error}"
    inherit_identity(clone)
    _fetch_docs_refs(clone)
    return clone, None


def _fetch_docs_refs(clone: Path) -> None:
    """Ссылки документов `refs/artifacts/*` из `origin` — в только что
    заведённый клон (SPEC 01M446WV7S94FTZGJCGMPJ667F, требование 1):
    `git clone` их не приносит, и без них `doctor` видел бы каждую
    закрытую задачу «без локальной ссылки». Узел тот же, что у
    `docs --fetch-all` — сдвиг только вперёд. Неудача не отменяет
    заведение клона: причина — одной строкой. Каталога клона нет, хотя
    `git clone` ответил успехом, — fetch'у некуда класть ссылки, git не
    спрашивается."""
    from . import artifact_branch  # лениво: `artifact_branch` импортирует этот модуль
    if not clone.is_dir():
        print(f"клон {clone}: ссылки документов refs/artifacts/* из origin "
              f"не подтянуты — каталога клона нет после git clone; "
              f"повтор: artel.py docs --fetch-all")
        return
    outcomes, reason = artifact_branch.fetch_all_from_origin(clone)
    if outcomes is None:
        print(f"клон {clone}: ссылки документов refs/artifacts/* из origin "
              f"не подтянуты — {reason}; повтор: artel.py docs --fetch-all")


def path(task_id: str, target: str | None = None) -> Path:
    """Рабочая копия задачи в области её проекта: `.artel/projects/<имя>/
    worktrees/<id>/` (требование 1). `target` не назван — по БД."""
    target = target or task_target(task_id)
    return repo_context.projects_root() / target / "worktrees" / task_id


def registered_paths(clone: Path | None = None) -> list[str]:
    """Пути всех рабочих копий клона; первая запись — сам клон. Клон не
    назван — клон артели. Пустой список — git не ответил (вырожденный
    случай песочниц без реального git)."""
    if clone is None:
        clone = repo(config.DEFAULT_TARGET)
    res = gitcmd.in_repo(clone, "worktree", "list", "--porcelain")
    if res is None or res.returncode != 0:
        return []
    return [line.split(" ", 1)[1] for line in res.stdout.splitlines()
           if line.startswith("worktree ")]


def _registered(clone: Path, wt_path: Path) -> bool:
    """Сравнение по `Path.resolve()` с обеих сторон (AC-2 T045): регистрация
    в `git worktree list` идёт по разрешённому пути (символическая ссылка
    macOS `/var` -> `/private/var` в `tempfile.mkdtemp()`, SPEC
    01M1SC3Y20YBTTJVQDJBF2NDQW)."""
    resolved = wt_path.resolve()
    return any(Path(p).resolve() == resolved for p in registered_paths(clone))


def _fetched_base(clone: Path, base: str) -> tuple[str, str]:
    """(sha, "") — свежая голова `<base>` в `origin` клона (свежесть клона
    перед заведением рабочей копии, требование 1); ("", причина) — fetch не
    удался. Приватная ссылка `fetch_ref_sha` — без общего `FETCH_HEAD`
    (SPEC 01M2ARQGY51B99YNP9PY806AN1) и без обновления ссылок отслеживания
    (SPEC 01M42NBCADGSGTCBZB8NKBVDVH, требование 2): их блокировка чужим
    процессом не должна пропускать шаг роли."""
    return gitcmd.fetch_ref_sha("origin", base, repo=clone,
                                tracking_refs=False)


def ensure(task_id: str, branch: str,
           target: str | None = None) -> tuple[Path, str | None]:
    """Создаёт (если нет) рабочую копию задачи на её ветке в клоне проекта;
    идемпотентно. (путь, причина отказа) — причина `None` при успехе.

    Идемпотентность — по факту регистрации в `git worktree list` клона, не
    по существованию каталога на диске. Клона нет — заводится
    (`ensure_clone`); не завёлся — отказ без отката на главную копию.
    Ветки ещё нет в клоне — заводится от свежего `origin/<база>` (SPEC
    01M297HFSKV3GVZJ9YF20FZEZE, требование 1): `fetch` идёт ПЕРЕД самим
    `git worktree add -b`; fetch не удался — именованный отказ БЕЗ отката
    на локальную базу (AC-3 той задачи).

    Копия внешнего проекта — и новая, и уже зарегистрированная — на каждом
    вызове приводится к копии без агентской обвязки (`_exclude_wrapper`);
    сбой — причина отказа, роль в копии с обвязкой не стартует."""
    target = target or task_target(task_id)
    wt_path = path(task_id, target)
    clone, clone_error = ensure_clone(target)
    if clone_error is not None:
        return wt_path, clone_error
    if _registered(clone, wt_path):
        return wt_path, _exclude_wrapper(wt_path, target, task_id)
    if gitcmd.branch_exists(branch, repo=clone):
        res = gitcmd.in_repo(clone, "worktree", "add", str(wt_path), branch)
    else:
        ctx = repo_context.resolve(target)
        base = ctx.base if ctx is not None else config.MAIN_BRANCH
        origin_sha, fetch_reason = _fetched_base(clone, base)
        if not origin_sha:
            reason = "база ветки недоступна: fetch origin не удался"
            if fetch_reason:
                reason += f": {fetch_reason}"
            return wt_path, reason
        res = gitcmd.in_repo(clone, "worktree", "add", "-b", branch,
                             str(wt_path), origin_sha)
    if res is None or res.returncode != 0:
        reason = (res.stderr.strip()[:300] if res is not None and res.stderr
                  else f"git worktree add вернул {res.returncode if res else '—'}")
        return wt_path, reason
    return wt_path, _exclude_wrapper(wt_path, target, task_id)


# Агентская обвязка внешнего проекта вне диска его рабочей копии (SPEC
# 01M5T19041XE2KB6A52F0AT0NF, требование 9; ADR-0003 п.14): файлы
# остаются в дереве git ветки, на диске рабочей копии их нет — git
# sparse-checkout без конусов, настройка только этой копии (`config.worktree`
# при `extensions.worktreeConfig`, его включает сам `git sparse-checkout`).
# Пути обвязки ещё и отбиты игнором копии (`core.excludesFile` её
# `config.worktree`): без него `git add -A` чекпоинта выходит кодом 1 на
# неотслеживаемом файле вне определения sparse-checkout
# (`.claude/settings.local.json`, оставленном CLI роли).
WRAPPER_EXCLUDE_FILE = "artel-agent-wrapper-exclude"
_GLOB_SPECIALS = ("\\", "*", "?", "[")


def _wrapper_pattern(path: str) -> str:
    """Шаблон gitignore-формы пути обвязки: маска `**/…` — как есть (любая
    глубина), прочий путь — от корня копии, спецсимволы шаблона экранированы."""
    if path.startswith(config.PROTECTED_PATH_ANY_DIR_MASK):
        return path
    for ch in _GLOB_SPECIALS:
        path = path.replace(ch, "\\" + ch)
    return "/" + path


def _wrapper_pathspec(path: str) -> str:
    """Pathspec git того же пути: маска — glob, прочий путь — буквально."""
    if path.startswith(config.PROTECTED_PATH_ANY_DIR_MASK):
        return f":(glob){path}**" if path.endswith("/") else f":(glob){path}"
    return f":(literal){path}"


def wrapper_covers(rel: str, wrapper) -> bool:
    """Путь копии `rel` покрыт списком обвязки так же, как его исключают
    шаблоны sparse-checkout (`_wrapper_pattern`): маска — формулой
    `config.is_protected_path`, прочий путь — сам он или путь внутри него."""
    for path in wrapper:
        if path.startswith(config.PROTECTED_PATH_ANY_DIR_MASK):
            if config.is_protected_path(rel, (path,)):
                return True
        elif rel == path.rstrip("/") or rel.startswith(path.rstrip("/") + "/"):
            return True
    return False


def wrapper_file_on_disk(wt_path: Path, wrapper) -> str | None:
    """Первый (по обходу) файл рабочей копии под списком обвязки; `None` —
    таких нет. Каталог `.git` и вложенные репозитории не обходятся."""
    for current, dirs, files in os.walk(wt_path):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        base = Path(current).relative_to(wt_path).as_posix()
        for name in sorted(files):
            rel = name if base == "." else f"{base}/{name}"
            if name != ".git" and wrapper_covers(rel, wrapper):
                return rel
    return None


def _git_failure(res, what: str) -> str | None:
    if res is not None and res.returncode == 0:
        return None
    detail = ((res.stderr or res.stdout or "").strip()[:300] if res is not None
              else "git не ответил")
    return f"{what}: {detail or f'код {res.returncode}'}"


WRAPPER_UNRESOLVED_ACTION = "wrapper_markers_only"


def _note_unresolved_wrapper(task_id: str, target: str, wt_path: Path) -> None:
    """Пометка: копия приведена только по стандартным маркерам — запись
    проекта не разрешена, её `agent_wrapper` не прочитан. Журнал задачи,
    если её строка есть в БД (та же запись повторно не пишется: `ensure`
    зовут каждый шаг и гейт); иначе — stderr."""
    text = (f"обвязка рабочей копии {wt_path} исключена только по стандартным "
            f"маркерам {', '.join(config.AGENT_WRAPPER_MARKERS)}, без "
            f"agent_wrapper: {repo_context.unresolved_reason(target)}")
    if store.db_usable():
        conn = store.db()
        if store.task_exists(conn, task_id):
            seen = conn.execute(
                "SELECT 1 FROM steps WHERE task_id = ? AND action = ?"
                " AND detail = ? LIMIT 1",
                (task_id, WRAPPER_UNRESOLVED_ACTION, text)).fetchone()
            if seen is None:
                store.journal(conn, task_id, "orchestrator",
                              WRAPPER_UNRESOLVED_ACTION, text, target=target)
            return
    print(text, file=sys.stderr)


def _exclude_wrapper(wt_path: Path, target: str, task_id: str) -> str | None:
    """Приводит рабочую копию внешнего проекта к копии без обвязки по
    ТЕКУЩЕМУ действующему списку (`repo_context.wrapper_paths`); `None` —
    приведена, иначе причина: роль в копии с обвязкой не стартует. Шаблоны
    совпали с записанными — sparse-checkout не трогается (повторный вызов
    идемпотентен). Неотслеживаемые и игнорируемые файлы под списком
    убираются с диска (`git clean -x` по путям обвязки). У артели — `None`
    без единого вызова git: её копия полная. Каталога копии нет — нечего
    приводить (регистрация без каталога — прежний исход `ensure`). Запись
    проекта не разрешена — копия приводится по стандартным маркерам с
    пометкой (`_note_unresolved_wrapper`), не отказ."""
    if repo_context.is_artel(target) or not wt_path.is_dir():
        return None
    ctx = repo_context.resolve(target)
    if ctx is None:
        # Без разрешённой записи `ensure` заводил копию и до обвязки: отказ
        # здесь был бы регрессией. Стандартные маркеры от записи не зависят —
        # исключаются они, без `agent_wrapper`, с пометкой о неполном списке.
        wrapper = targets.wrapper_paths()
        _note_unresolved_wrapper(task_id, target, wt_path)
    else:
        wrapper = repo_context.wrapper_paths(ctx)
    patterns = [_wrapper_pattern(path) for path in wrapper]
    wanted = ["/*", *(f"!{p}" for p in patterns)]
    what = f"обвязка рабочей копии {wt_path} не исключена"
    listed = gitcmd.in_repo(wt_path, "sparse-checkout", "list")
    if (listed is None or listed.returncode != 0
            or listed.stdout.splitlines() != wanted):
        failure = _git_failure(gitcmd.in_repo(
            wt_path, "sparse-checkout", "set", "--no-cone", *wanted),
            f"{what}: git sparse-checkout set")
        if failure is not None:
            return failure
    git_dir = gitcmd.in_repo(wt_path, "rev-parse", "--absolute-git-dir")
    failure = _git_failure(git_dir, f"{what}: git rev-parse")
    if failure is not None:
        return failure
    exclude = Path(git_dir.stdout.strip()) / WRAPPER_EXCLUDE_FILE
    if not exclude.parent.is_dir():
        return f"{what}: каталог git копии {exclude.parent} не найден"
    own = _inherited_excludes(wt_path, exclude)
    exclude.write_text("".join(f"{p}\n" for p in patterns) + own,
                       encoding="utf-8")
    failure = _git_failure(gitcmd.in_repo(
        wt_path, "config", "--worktree", "core.excludesFile", str(exclude)),
        f"{what}: git config --worktree core.excludesFile")
    if failure is not None:
        return failure
    return _git_failure(gitcmd.in_repo(
        wt_path, "clean", "-f", "-d", "-x", "-q", "--",
        *(_wrapper_pathspec(path) for path in wrapper)),
        f"{what}: git clean путей обвязки")


def _inherited_excludes(wt_path: Path, exclude: Path) -> str:
    """Текст файла игнора, действовавшего до своего `core.excludesFile`
    копии (глобальный или `$XDG_CONFIG_HOME/git/ignore`): свой файл копии
    его заменяет, и без переноса глобально игнорируемое (`.DS_Store`)
    попало бы в `git add -A` чекпоинта."""
    res = gitcmd.in_repo(wt_path, "config", "--path", "--get-all",
                         "core.excludesFile")
    values = ([v for v in res.stdout.splitlines() if v and v != str(exclude)]
              if res is not None and res.returncode == 0 else [])
    if values:
        source = Path(values[-1]).expanduser()
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        source = Path(xdg) / "git" / "ignore"
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    return text if text.endswith("\n") or not text else text + "\n"


def on_task_branch(task_id: str, branch: str,
                   target: str | None = None) -> bool | None:
    """True/False — рабочая копия существует и стоит/не стоит на ветке
    задачи; `None` — ещё не заведена (сверять не с чем, AC-8 T045)."""
    target = target or task_target(task_id)
    wt_path = path(task_id, target)
    if not _registered(repo(target), wt_path):
        return None
    res = gitcmd.in_repo(wt_path, "rev-parse", "--abbrev-ref", "HEAD")
    if res is None or res.returncode != 0:
        return None
    return res.stdout.strip() == branch


def remove(task_id: str, target: str | None = None) -> str:
    """Убирает рабочую копию задачи (`kill`/`done`); строка — что вышло
    (по образцу `cleanup.drop_task_dir`/`drop_task_branch`)."""
    target = target or task_target(task_id)
    clone = repo(target)
    wt_path = path(task_id, target)
    if not _registered(clone, wt_path):
        return f"worktree {wt_path} не найден — нечего убирать"
    res = gitcmd.in_repo(clone, "worktree", "remove", "--force", str(wt_path))
    if res is None or res.returncode != 0:
        reason = (res.stderr.strip()[:200] if res is not None and res.stderr
                  else f"git worktree remove вернул {res.returncode if res else '—'}")
        return f"worktree {wt_path} не убран: {reason}"
    return f"убран worktree {wt_path}"


def cmd_workspace(task_id: str, session_id: str | None = None) -> None:
    """CLI `workspace <id>` (AC-1, AC-2 T045): создаёт или выдаёт путь
    существующей рабочей копии задачи.

    Берёт lease задачи перед работой (SPEC T044, требование 2) — тем же
    приёмом, что `runner.cmd_run`/`cleanup.cmd_kill`: `git worktree add`
    невозможно безопасно сериализовать иначе (review T045 итерация 1,
    замечание 1).

    Префикс -> полный id (SPEC T094, требование 3, AC-3) резолвится в
    `lease.run_task_command`, до lease (REVIEW T094 итерация 1, замечание 1).
    """
    lease.run_task_command(task_id, session_id, _cmd_workspace)


def cmd_worktree_db_clean(task_id: str) -> None:
    """CLI `worktree-db-clean <id>` (SPEC 01M4FYTB8QWJNHYCP35K8QC4E3,
    требование 6): файлы БД пульта (`store.TREE_DB_FILES`) из рабочей копии
    задачи — в каталог логов пульта `config.LOGS`, под именем с id задачи и
    меткой времени. Перенос, а не удаление: кто завёл файл, не установлено,
    и содержимое — улика. Существующие файлы логов не перезаписываются.
    Файлов нет — сообщение и успешный выход, ничего не меняется."""
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    wt_path = path(task_id, store.task_target(conn, task_id))
    found = store.tree_db_files(wt_path)
    if not found:
        print(f"[{task_id}] в рабочей копии {wt_path} файлов БД пульта нет — "
              f"переносить нечего")
        return
    logs = Path(config.LOGS)
    logs.mkdir(parents=True, exist_ok=True)
    stamp = store.now().replace(" ", "T").replace(":", "")
    for rel in found:
        source = wt_path / rel
        name = f"{task_id}-worktree-{stamp}-{Path(rel).name}"
        dest = logs / name
        number = 1
        while dest.exists():
            number += 1
            dest = logs / f"{name}.{number}"
        shutil.move(str(source), str(dest))
        print(f"[{task_id}] перенесён {source} → {dest}")


def _cmd_workspace(conn, task_id: str) -> None:
    t = store.get_task(conn, task_id)
    wt_path, error = ensure(task_id, t["branch"], store.task_target(conn, task_id))
    if error is not None:
        sys.exit(f"[{task_id}] worktree не создан: {error}")
    print(f"[{task_id}] worktree: {wt_path}")
