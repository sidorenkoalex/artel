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


