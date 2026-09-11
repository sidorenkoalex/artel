"""Пакет orchestrator/doctor -- свежесть ветки активной задачи относительно main.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""

from orchestrator import doctor


# --- свежесть ветки (SPEC T051, требование 8) -----------------------------

def check_branch_freshness(conn) -> list[doctor.Check]:
    """Активная (нетерминальная) задача, чья ветка отстала от
    `config.MAIN_BRANCH` больше чем на `config.STALE_BRANCH_WARN_COMMITS`
    коммитов, — предупреждение (AC-5).

    Не incident, в отличие от `check_orphans`/`check_leases`: отставание
    ветки — ожидаемое и самоустраняющееся состояние параллельной работы
    (roadmap §4 п.2а), не операционный дефект с жизненным циклом ack —
    тем же приёмом, что `check_cli_version`/`check_target_layout`
    (информационный warn, не incident, ничего не заводит в `alerts`).

    Ветка ещё не существует в git или git не ответил
    (`gitcmd.commits_behind` вернул `None`) — сверять не с чем, задача
    молча пропускается (требование 9: тот же приём деградации, что у
    остальных git-примитивов, на которые уже опирается doctor).

    Репозиторный контекст target'а (SPEC 01M1R5B33CC7E6BZK085XV3ZCX,
    AC-5): для target ≠ self сверка идёт с `origin/<base>` клона
    контекста target'а (`orchestrator/repo_context.py`), не с локальным
    `config.MAIN_BRANCH` `config.ROOT`, где ветки внешнего target нет
    вовсе — свежий `git fetch origin <base>` там нужен явно (в отличие
    от self, чей `config.MAIN_BRANCH` уже обновляется прочей механикой
    пульта). Для self — прежнее поведение байт-в-байт (без fetch,
    сравнение с локальным `config.MAIN_BRANCH`). Контекст не читается
    (targets.yaml сломан/неизвестный target) или fetch не удался —
    задача молча пропускается, тем же вырожденным случаем, что и
    неответивший git выше.
    """
    stale = []
    for t in doctor.store.all_tasks(conn):
        if t["state"] in ("done", "killed") or not t["branch"]:
            continue
        target_name = t["target"] or doctor.config.DEFAULT_TARGET
        if target_name == doctor.config.DEFAULT_TARGET:
            behind = doctor.gitcmd.commits_behind(t["branch"])
        else:
            ctx = doctor.repo_context.resolve(target_name)
            if ctx is None:
                continue
            fetch = doctor.gitcmd.in_repo(ctx.path, "fetch", "-q", "origin",
                                          ctx.base)
            if fetch is None or fetch.returncode != 0:
                continue
            behind = doctor.gitcmd.commits_behind(
                t["branch"], base=f"origin/{ctx.base}", repo=ctx.path)
        if behind is not None and behind > doctor.config.STALE_BRANCH_WARN_COMMITS:
            stale.append((t, behind))
    if not stale:
        return [doctor.Check("branch-freshness", "ok",
                      f"нет активных задач с веткой отставшей больше "
                      f"{doctor.config.STALE_BRANCH_WARN_COMMITS} коммитов от "
                      f"{doctor.config.MAIN_BRANCH}")]
    return [doctor.Check("branch-freshness", "warn",
                  f"{t['id']}: ветка {t['branch']} отстала от "
                  f"{doctor.config.MAIN_BRANCH} на {behind} коммитов")
           for t, behind in stale]


