"""Вызовы git в корне репозитория, вопросы к ветке задачи и к произвольному
репозиторию (артефактные git-репо внешних target, ADR-0003 3д, tasks/T021)."""
import subprocess
from pathlib import Path

from . import config


def git(*args: str) -> subprocess.CompletedProcess:
    """git в корне репозитория; исход разбирает вызывающий.

    Ошибка запуска (git не установлен) — такой же ненулевой код возврата,
    как и ошибка самой команды: уборке достаточно знать, что ответа нет.
    """
    try:
        return subprocess.run(["git", *args], cwd=config.ROOT,
                              capture_output=True, text=True)
    except OSError as exc:
        return subprocess.CompletedProcess(args, 1, "", str(exc))


def current_branch() -> str:
    """Ветка под HEAD; пустая строка — git не ответил.

    `res is None` — заглушки `gitcmd.git` в тестах, не связанных с git,
    отвечают `None` тем же приёмом, что и у `head_sha` (T031: эта функция
    впервые попадает на горячий путь `set_state` через `on_foreign_branch`,
    где такие заглушки уже встречаются).
    """
    res = git("rev-parse", "--abbrev-ref", "HEAD")
    return res.stdout.strip() if res is not None and res.returncode == 0 else ""


def branch_exists(branch: str) -> bool:
    """`res is None` — тот же вырожденный случай, что у `head_sha`: заглушки
    `gitcmd.git` в тестах, не связанных с git, отвечают `None`."""
    res = git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    return res is not None and res.returncode == 0


def branch_merged(branch: str) -> bool:
    """Смержена ли ветка в main — тем же критерием, каким git защищает `-d`."""
    res = git("branch", "--merged", config.MAIN_BRANCH, "--list", branch)
    return res.returncode == 0 and bool(res.stdout.strip())


def commits_behind(branch: str, base: str | None = None) -> int | None:
    """Число коммитов `base` (по умолчанию `config.MAIN_BRANCH`), которых
    нет в `branch`; `None` — git не ответил, `branch`/`base` не существует,
    или ответ не разобрать как число (SPEC T051, требование 2).

    `base` — параметр, не читается через `config.MAIN_BRANCH` как значение
    по умолчанию аргумента (оно вычислилось бы один раз при определении
    функции и не увидело бы подмену `config.MAIN_BRANCH` в тестах, тот же
    приём, что у остальных примитивов модуля). `res is None`/непустой,
    но нечисловой вывод — тот же вырожденный случай «git не ответил
    осмысленно», что у `head_sha`/`is_clean`: заглушки `gitcmd.git` в
    тестах, не связанных с git (SPEC T051, требование 9), отвечают пустым
    выводом с кодом 0 на любую нераспознанную команду и не должны
    трактоваться как «ноль коммитов».
    """
    res = git("rev-list", "--count", f"{branch}..{base or config.MAIN_BRANCH}")
    if res is None or res.returncode != 0:
        return None
    text = res.stdout.strip()
    return int(text) if text.isdigit() else None


def is_ancestor(ancestor: str, descendant: str) -> bool:
    """`ancestor` — предок `descendant` (или тот же коммит) тем же
    критерием, каким это понимает сам git (`merge-base --is-ancestor`).

    Несуществующий/несвязанный sha даёт ненулевой код возврата — тот же
    `False`, что и «не предок» (ANSWER-1
    01M1NGFK3N6MRMYGCC09H975V3 п.3: прогон с чужой историей не считается
    вовсе, не «бесконечно старый»)."""
    res = git("merge-base", "--is-ancestor", ancestor, descendant)
    return res is not None and res.returncode == 0


def merges_between(sha_from: str, sha_to: str) -> int | None:
    """Число merge-коммитов на отрезке `sha_from..sha_to` (ANSWER-1
    01M1NGFK3N6MRMYGCC09H975V3 п.3: «возраст» зелёного прогона канарейки
    относительно целевого sha) — тот же вырожденный случай `None`, что и
    `commits_behind`: git не ответил, либо ответ не разобрать числом."""
    res = git("rev-list", "--count", "--merges", f"{sha_from}..{sha_to}")
    if res is None or res.returncode != 0:
        return None
    text = res.stdout.strip()
    return int(text) if text.isdigit() else None


def commit_committer_dates(since: str, until: str,
                           repo: Path | None = None) -> list[str] | None:
    """ISO8601 committer-даты (`%cI`, со смещением) коммитов диапазона
    `since..until` (SPEC T076, требование 1) — порядок вывода `git log`
    вызывающему коду не важен, каждая дата сверяется независимо
    (`fixation.refixate_after_rejected_transition`).

    `None` — git не ответил, либо диапазон недостижим (`since` не предок
    `until`, несуществующий sha — `res.returncode != 0`): вызывающий код
    обязан трактовать это как «неизвестно» и не перефиксировать
    (fail-closed, тот же принцип, что `fixation.check_integrity` при
    неответившем git).
    """
    args = ("log", "--format=%cI", f"{since}..{until}")
    res = in_repo(repo, *args) if repo else git(*args)
    if res is None or res.returncode != 0:
        return None
    return [ln for ln in res.stdout.splitlines() if ln.strip()]


def list_branches(prefix: str = "") -> list[str] | None:
    """Локальные ветки под `refs/heads/<prefix>`; `None` — git не ответил.

    Наблюдаемый мир для холодного старта (SPEC T049, требование 1):
    ветки `task/*` без строки БД — один из трёх источников максимума
    номеров задач (`orchestrator/coldstart.py`). Пустой список — легитимный
    ответ (веток с таким префиксом нет), тот же приём, что у
    `ls_tree_files` не путать с `None`.
    """
    res = git("for-each-ref", "--format=%(refname:short)", f"refs/heads/{prefix}")
    if res is None or res.returncode != 0:
        return None
    return [b for b in res.stdout.splitlines() if b]


def carpentry(repo: Path, args: list, env: dict, *,
             input: bytes | None = None, text: bool = True
             ) -> subprocess.CompletedProcess:
    """Плотницкая git-команда (read-tree/hash-object/update-index/write-tree/
    commit-tree — `artifact_branch.write_commit`) в `repo` со своим
    окружением (`GIT_INDEX_FILE`, для `commit-tree` — ещё и `GIT_AUTHOR_*`/
    `GIT_COMMITTER_*`): единая точка `subprocess.run` для всей плотницкой
    записи артефактной ветки (SPEC 01M1KVGD18P9H5WR7VM8TGPV1T, требования
    2-3) — раньше `artifact_branch.py` звал `subprocess.run` напрямую, в
    обход `gitcmd` и любой его подмены, и утекал в НАСТОЯЩИЙ репозиторий
    пульта из тестов, подменявших только `gitcmd.git` (SPEC «Контекст»).

    `tests/sandbox.py::TmpRootTest` патчит не эту функцию отдельно, а сам
    `gitcmd.subprocess.run` (тот же объект, что глобальный `subprocess.
    run`, — общий модуль-синглтон): патч перехватывает и эти вызовы тоже,
    без изменения точки подмены (`tests/01M1KVGD18P9H5WR7VM8TGPV1T/
    acceptance_tests/test_ac3_sandbox_default_covers_carpentry.py`).
    """
    return subprocess.run(["git", *args], cwd=repo, env=env,
                          capture_output=True, text=text, input=input)


def in_repo(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """git-команда в произвольном репозитории (не ROOT пульта) через `-C`.

    Не `subprocess.run(..., cwd=repo)` внутри `git()`: существующие тесты
    подменяют саму функцию `gitcmd.git` заглушками сигнатуры `(*args: str)`
    (мультитаргет, FSM, бюджет, автоцикл) — добавь `git()` параметр `cwd`,
    эти заглушки упали бы `TypeError` на неожиданном keyword-аргументе.
    `-C <repo>` остаётся обычным позиционным аргументом `git(*args)`, тем
    же вызовом, который заглушки уже умеют разобрать (tasks/T021 PLAN,
    «Подход»).
    """
    return git("-C", str(repo), *args)


def head_sha(repo: Path | None = None) -> str:
    """sha текущего HEAD; пустая строка — нет коммитов или git не ответил.

    `res is None` — не только реальный отказ `subprocess.run` (уже
    свёрнут в `git()` в `CompletedProcess` с ненулевым кодом), но и
    подмена `gitcmd.git` в тестах, не связанных с git вовсе
    (test_advance_guard.py: `lambda *a: None`, задачам которого сама
    фиксация артефактов не нужна) — тот же смысл «ответа нет».
    """
    res = in_repo(repo, "rev-parse", "HEAD") if repo else git("rev-parse", "HEAD")
    return res.stdout.strip() if res is not None and res.returncode == 0 else ""


def is_clean(*paths: str, repo: Path | None = None) -> bool | None:
    """Нет незакоммиченных изменений по путям; None — git не ответил.

    Без путей — вся рабочая копия репозитория (`repo`, если задан).
    """
    args = ("status", "--porcelain") + (("--", *paths) if paths else ())
    res = in_repo(repo, *args) if repo else git(*args)
    if res is None or res.returncode != 0:
        return None
    return not res.stdout.strip()


def check_ignore(paths) -> set[str] | None:
    """Пути из `paths`, которые `.gitignore` ПУЛЬТА (`config.ROOT`) считает
    игнорируемыми; `None` — git не ответил. Настоящий разбор `.gitignore`
    (`git check-ignore`), не самодельный список расширений (SPEC
    01M1KVG3KSCY47HWXWF5HM0E76, требование 1) — только так ловится
    директорное правило (например, `__pycache__/`), которое списком
    суффиксов не выразить.

    Батч одним вызовом `--stdin -z` на весь список путей шага, не по
    одному на файл. Путям не обязательно существовать на диске
    `config.ROOT` — `check-ignore` матчит их как строки пути, не как
    файлы (нужно для путей внешнего target, которых в рабочей копии
    пульта нет вовсе).
    """
    paths = list(paths)
    if not paths:
        return set()
    data = "".join(p + "\0" for p in paths).encode()
    try:
        res = subprocess.run(["git", "check-ignore", "-v", "-z", "--stdin"],
                             cwd=config.ROOT, input=data, capture_output=True)
    except OSError:
        return None
    if res.returncode not in (0, 1):
        return None
    fields = res.stdout.split(b"\0")
    ignored = set()
    i = 0
    while i + 3 < len(fields):
        pathname = fields[i + 3]
        if pathname:
            ignored.add(pathname.decode())
        i += 4
    return ignored


def diff_names(a: str, b: str, *paths: str) -> list[str] | None:
    """Пути, различающиеся между `a` и `b` под `paths`; `None` — git не
    ответил. В отличие от `diff_paths` (голое да/нет), отдаёт сами пути —
    нужно, чтобы отличить настоящую правку от разницы только в
    игнорируемых `.gitignore` файлах (SPEC 01M1KVG3KSCY47HWXWF5HM0E76,
    требование 3)."""
    res = git("diff", "--name-only", a, b, "--", *paths)
    if res is None or res.returncode != 0:
        return None
    return [p for p in res.stdout.splitlines() if p]


def diff_paths(a: str, b: str, *paths: str) -> bool | None:
    """True — ревизии `a` и `b` расходятся по путям; None — git не ответил.

    `git diff --quiet` кодирует ответ кодом возврата (0 — совпадают,
    1 — расходятся), не выводом: достаточно для проверки лока
    acceptance_tests/ (orchestrator/fsm.py, tasks/T023, требование 5)
    без парсинга самого диффа. Тот же вырожденный случай «git не ответил»,
    что у `is_clean`/`head_sha`: заглушка `gitcmd.git = lambda *a: None`
    в тестах, не связанных с git, возвращает `None` тем же приёмом.
    """
    res = git("diff", "--quiet", a, b, "--", *paths)
    if res is None or res.returncode not in (0, 1):
        return None
    return res.returncode == 1


def _origin_main_ref_exists() -> bool | None:
    """`refs/remotes/origin/<MAIN_BRANCH>` заведён в репозитории; `None` —
    git не ответил на саму проверку. Только чтение уже существующего
    локального ref — без `fetch`/`ls-remote`, никаких сетевых обращений
    (тесты не выходят в сеть, 01M1QHQ277…): ref обновляется механикой
    подтяжки и входа в `verifying`, эта функция его не актуализирует."""
    res = git("rev-parse", "--verify", "--quiet",
             f"refs/remotes/origin/{config.MAIN_BRANCH}")
    return None if res is None else res.returncode == 0


def diff_base(branch: str) -> str | None:
    """Одна точка правды для базы сравнения ветки задачи (tasks/
    01M1SG9T962WJJ31S282GWM0EN): merge-base `branch` с `refs/remotes/
    origin/<MAIN_BRANCH>`, если такой ref есть в репозитории; иначе —
    merge-base с локальным `config.MAIN_BRANCH`. Замена двухточечного
    сравнения с локальным `config.MAIN_BRANCH` целиком (гейт зон) и
    трёхточечного, но с той же устаревшей базой (гейт ёмкости, полный
    diff ревью-пакета) — локальный пин по построению отстаёт от
    `origin/main`, которую ветка задачи как раз подтягивает: точка
    расхождения с локальным main старее и тащит в дифф чужие коммиты.

    `None` — git не ответил ни на проверку существования ref, ни на саму
    команду `merge-base`: вызывающий код обязан отказать fail-closed
    (ADR-0002), не подставлять `None` дальше как базу diff'а.
    """
    exists = _origin_main_ref_exists()
    if exists is None:
        return None
    base_ref = (f"refs/remotes/origin/{config.MAIN_BRANCH}" if exists
               else config.MAIN_BRANCH)
    res = git("merge-base", base_ref, branch)
    if res is None or res.returncode != 0:
        return None
    return res.stdout.strip()


def diff_base_source(branch: str) -> str:
    """Название источника базы `diff_base(branch)` для журнала: `"origin/
    <MAIN_BRANCH>"` — ref заведён и был использован; иначе — локальный
    `config.MAIN_BRANCH` (tasks/01M1SG9T962WJJ31S282GWM0EN, требование 4:
    отказы гейтов зон/ёмкости обязаны называть, откуда взята база, не
    только её sha). Не зовёт `diff_base` повторно и не переиспользует её
    результат — только независимо повторяет тот же критерий наличия ref;
    git не ответивший на эту проверку — локальный `config.MAIN_BRANCH` тем
    же вырожденным откатом, что и у `diff_base` в этом случае (вызывающий
    код сюда доходит только когда `diff_base` уже вернула не-`None` базу,
    так что расхождение возможно только при флапе git между двумя
    вызовами)."""
    return (f"origin/{config.MAIN_BRANCH}" if _origin_main_ref_exists()
           else config.MAIN_BRANCH)


def has_no_remote(repo: Path) -> bool:
    """True — `git remote` пуст: ни одной записи (ADR-0003 3д, требование 7).

    Потребитель — doctor (A3); здесь только сама проверка.
    """
    res = in_repo(repo, "remote")
    return res is not None and res.returncode == 0 and not res.stdout.strip()


# --------------------------------------------------------------------------
# Ветко-корректные чтения артефактов задачи (SPEC T031): источник истины —
# ВЕТКА задачи, не рабочая копия пульта, которую чужой checkout (журнал
# T030, ~17:35 25.08.2026) может подменить у оркестратора под ногами.

def branch_head_sha(branch: str) -> str:
    """sha головы `branch` независимо от текущего чекаута; пустая строка —
    ветки нет в git или он не ответил (`res is None` — тот же вырожденный
    случай заглушек `gitcmd.git`, что у `head_sha`)."""
    res = git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    return res.stdout.strip() if res is not None and res.returncode == 0 else ""


def on_foreign_branch(branch: str) -> bool:
    """True — рабочее дерево ТОЧНО стоит не на `branch`, и `branch` реально
    существует в git: единственный случай, когда чтение с ВЕТКИ задачи
    безопасно и осмысленно предпочесть рабочей копии (SPEC T031).

    Иначе (своя ветка и так выписана; ветка ещё не создана ролью — легитимный
    ранний момент жизни задачи до первого `git checkout -b`, ADR-0003 3д;
    git не ответил на сам вопрос «какая ветка сейчас») — прежнее поведение,
    рабочая копия: вырожденный случай, на котором стоял весь стенд
    заглушек `gitcmd.git` до этой задачи, остаётся вырожденным и после неё.
    """
    current = current_branch()
    return bool(branch and current and current != branch
               and branch_exists(branch))


def show(branch: str, rel: str) -> tuple[str | None, str]:
    """(текст, "") — файл `rel` из `branch`; (None, причина) — файла там
    нет, или git не ответил.

    Не путать с `review.artifact_text`: та ещё откатывается на рабочее
    дерево, если файла в ветке нет (законно для ревью WIP-diff'а, T011);
    здесь ветка — источник истины БЕЗ отката на дерево (SPEC T031,
    AC-1/AC-2) — откат на прежнее поведение делает вызывающий код через
    `on_foreign_branch`, а не эта функция молча.
    """
    try:
        res = git("show", f"{branch}:{rel}")
    except UnicodeDecodeError as exc:
        # git отдаёт байты файла как есть; strict-декодирование внутри
        # subprocess роняло бы всю команду трейсбеком (тот же приём, что
        # у review.artifact_text, T011 ревью 2).
        return None, f"не прочитан: {exc}"
    if res is None:
        return None, "git не ответил"
    if res.returncode == 0:
        return res.stdout, ""
    return None, res.stderr.strip()[:200] or f"git show вернул {res.returncode}"


def remote_branch_sha(branch: str) -> str:
    """sha `branch` в `origin`; пустая строка — там такой ветки нет (ещё не
    публиковалась, либо разошлась по имени) или git не ответил.

    Адресуется полным `refs/heads/<branch>`, не голым именем ветки (SPEC
    01M1GS5HZ1JXFGKVR95HEW0AEZ, AC-2): `git ls-remote origin <branch>`
    неполным именем мог бы зацепить одноимённый тег — здесь сверяется
    именно голова ветки-задачи.
    """
    res = git("ls-remote", "origin", f"refs/heads/{branch}")
    if res is None or res.returncode != 0 or not res.stdout.strip():
        return ""
    return res.stdout.split()[0]


def fetch_head_sha(remote: str, ref: str) -> tuple[str, str]:
    """(sha, "") — голова `ref` в `remote` ПОСЛЕ `git fetch <remote> <ref>`
    (SPEC 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH, требование 1): `git fetch` не
    трогает HEAD и рабочее дерево ни при каком исходе, так что HEAD
    главной копии остаётся на месте. ("", причина) — `remote` недоступен
    (нет сети, `remote` не настроен, песочница) или git не ответил;
    причина — первые 200 символов stderr, тем же приёмом, что и у
    `show`/`drop`.

    Не `ls_remote`/`remote_branch_sha` (голый sha без объектов): вызывающему
    коду (`artifact_branch`, `doctor`) нужен РЕАЛЬНО присутствующий локально
    коммит — родитель плотницкой записи (`write_commit`, `read-tree
    parent`) обязан существовать в объектной базе, не только числиться sha
    на удалённой стороне.
    """
    res = git("fetch", remote, ref)
    if res is None:
        return "", "git не ответил"
    if res.returncode != 0:
        return "", (res.stderr.strip()[:200] or "git fetch вернул ненулевой код")
    head = git("rev-parse", "--verify", "--quiet", "FETCH_HEAD")
    if head is None or head.returncode != 0 or not head.stdout.strip():
        return "", "FETCH_HEAD не разрешён"
    return head.stdout.strip(), ""


def ls_tree_files(branch: str, rel_dir: str) -> list[str] | None:
    """Пути файлов под `rel_dir` в дереве `branch`; None — git не ответил.

    Пустой список — легитимный ответ (ветка есть, каталога в ней нет —
    тот же вырожденный случай, что у `guard.scan_acceptance_tests` для
    отсутствующей `acceptance_tests/` на диске), не путать с `None`.
    """
    res = git("ls-tree", "-r", "--name-only", branch, "--", rel_dir)
    if res is None or res.returncode != 0:
        return None
    return [p for p in res.stdout.splitlines() if p]
