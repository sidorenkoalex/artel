"""Пакет orchestrator/doctor -- пин запущенной версии относительно main артели.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""

from orchestrator import doctor


# --- пин запущенной версии (A7, Stage1, требования 5-6, AC-13) ----------

def check_root_pin() -> doctor.Check:
    """Расхождение пина `config.ROOT` (HEAD главной копии — Stage0
    удерживает его от изменения переходом `merge_gate -> done`,
    `orchestrator/fsm_merge_gate.py`) с текущим HEAD `refs/heads/
    <MAIN_BRANCH>` main артели (её `origin`) — информационно, никогда
    не блокирует прогон doctor (AC-13): пин обновляет только Оператор
    отдельной командой `pin-update` (Stage1, AC-14), не doctor сам.

    `git ls-remote origin` — единственный опрос без единого локального
    side-effect (не трогает объектную базу/индекс/HEAD ROOT, в отличие
    от `git fetch`): доктор не имеет права двигать что-либо сам.

    Git не ответил (нет origin, сеть недоступна, песочница без
    настоящего git) — сверять не с чем, `ok` тем же приёмом деградации,
    что и у остальных git-примитивов doctor'а: отсутствие ответа — не
    расхождение и не повод для warn.
    """
    root_sha = doctor.gitcmd.head_sha()
    ls = doctor.gitcmd.git("ls-remote", "origin", f"refs/heads/{doctor.config.MAIN_BRANCH}")
    if ls is None or ls.returncode != 0 or not ls.stdout.strip() or not root_sha:
        return doctor.Check("root-pin", "ok",
                     "main артели (origin) не опрошен — пин не сверен")
    origin_sha = ls.stdout.split()[0]
    if origin_sha == root_sha:
        return doctor.Check("root-pin", "ok", f"пин {root_sha} сходится с main "
                     f"артели {origin_sha}")
    return doctor.Check("root-pin", "warn",
                 f"пин {root_sha} отстал от main артели {origin_sha} — "
                 f"обнови: artel.py pin-update {origin_sha}")


# --- непушенные коммиты пина (SPEC 01M297HFSKV3GVZJ9YF20FZEZE) ----------

def fetch_origin_main_sha() -> tuple[str, str]:
    """(sha, "") — голова `origin/<MAIN_BRANCH>` ПОСЛЕ `git fetch origin
    <MAIN_BRANCH>` в `config.ROOT`; ("", причина) — fetch не удался.

    Тонкая обёртка `gitcmd.fetch_head_sha` — общая точка для `check_
    pin_unpushed` здесь и `catalog.cmd_new` (требования 2-3): оба обязаны
    видеть РЕЗУЛЬТАТ ОДНОГО И ТОГО ЖЕ критерия, не две независимые
    реализации сверки с origin, которые могут разойтись."""
    return doctor.gitcmd.fetch_head_sha("origin", doctor.config.MAIN_BRANCH)


def unpushed_commits(root_sha: str, origin_sha: str) -> list[tuple[str, str]]:
    """[(sha, первая строка сообщения), ...] коммитов `root_sha`,
    которых нет в `origin_sha` — пусто, если `root_sha` совпадает с
    `origin_sha` или является его предком (не расхождение), либо `git
    log` не ответил (нечего перечислять — вызывающий код уже знает по
    пустому списку, что «непушенных коммитов нет», тот же вырожденный
    случай, что и «нет расхождения»)."""
    if not root_sha or doctor.gitcmd.is_ancestor(root_sha, origin_sha):
        return []
    res = doctor.gitcmd.git("log", f"{origin_sha}..{root_sha}",
                            "--format=%H %s")
    if res is None or res.returncode != 0:
        return []
    lines = [ln for ln in res.stdout.splitlines() if ln.strip()]
    return [tuple(ln.split(" ", 1)) if " " in ln else (ln, "") for ln in lines]


def check_pin_unpushed() -> doctor.Check:
    """Непушенные коммиты HEAD `config.ROOT` относительно `origin/
    <MAIN_BRANCH>` (SPEC 01M297HFSKV3GVZJ9YF20FZEZE, требование 2) — в
    отличие от соседнего `check_root_pin` (`ls-remote`, никогда `fail`),
    эта проверка блокирует doctor `fail`: непушенный документный коммит
    в главной копии — как раз тот инцидент 11.09, который эта задача
    чинит, не информационная деградация.

    `git fetch origin <MAIN_BRANCH>` не удался — `warn`, не `ok` (AC-6):
    отсутствие ответа origin — это «сверка не проведена», не «пин ушёл
    вперёд» и не «пин синхронен» — оба остальных статуса были бы ложным
    сигналом в любую сторону.
    """
    root_sha = doctor.gitcmd.head_sha()
    origin_sha, fetch_reason = fetch_origin_main_sha()
    if not origin_sha:
        detail = "сверка с origin невозможна"
        if fetch_reason:
            detail += f": {fetch_reason}"
        return doctor.Check("pin-unpushed", "warn", detail)
    commits = unpushed_commits(root_sha, origin_sha)
    if not commits:
        return doctor.Check("pin-unpushed", "ok",
                     f"HEAD {root_sha} совпадает с origin/"
                     f"{doctor.config.MAIN_BRANCH} {origin_sha} или "
                     f"является его предком")
    listing = "; ".join(f"{sha[:7]} {msg}" for sha, msg in commits)
    return doctor.Check("pin-unpushed", "fail",
                 f"HEAD {root_sha} ушёл вперёд origin/"
                 f"{doctor.config.MAIN_BRANCH} {origin_sha} — непушенные "
                 f"коммиты: {listing}. Документные коммиты — только через "
                 f"`note`; выровнять пин — `pin --to <предок>` + "
                 f"`pin-update <sha>`")

