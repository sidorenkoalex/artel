"""Пакет orchestrator/doctor -- recovery-сверка журнала БД со ссылками документов задач target'а.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""

from orchestrator import doctor


# --- recovery-сверка (требование 4) -------------------------------------

def recovery_check(conn, target: str) -> list[doctor.Check]:
    """Журнал БД ↔ ссылка документов задачи target'а: голова
    `refs/artifacts/<id>` против зафиксированного sha — единая логика для
    ЛЮБОГО объявленного target, включая артель (A7, требование 2, AC-3).
    Сверка HEAD главной копии пульта (`config.ROOT`) в объём этой проверки
    не входит — та отдельная забота doctor-проверки пина (`check_root_pin`,
    AC-13).

    Чистоты и `fsck` репозитория фиксации области проекта больше нет:
    репозиторий упразднён (ADR-0021 п.2, этап 1, часть б2), у ссылки нет
    рабочей копии, которая могла бы быть грязной. Сверка sha от наличия
    каталога `.artel/projects/<target>/.git` не зависит.

    Авто-ack (SPEC T088, требования 2-4, 6) зовётся на каждом прогоне для
    КОНКРЕТНОГО target (`_auto_ack_gone` получает `target=target`).
    """
    results = []
    latest = doctor.store.latest_fixed_sha(conn, target)
    current = (doctor.artifact_branch.ref_head(latest["id"])
               if latest is not None else "")
    # Фиксация документов — коммит ссылки `refs/artifacts/<id>` (ADR-0021
    # п.3, инвариант 25): голова ссылки сверяется с зафиксированным sha.
    # Фиксация прежнего устройства — коммит отдельного репозитория
    # фиксации `.artel/projects/<target>/`, в объектной базе репозитория
    # задачи его нет: сверять его со ссылкой не с чем. Признак — именно
    # отсутствие объекта, а не «не предок головы»: ссылку, переписанную
    # мимо пульта на коммит вне её истории, сверка обязана видеть
    # расхождением.
    sha_mismatch = bool(latest is not None and current
                        and current != latest["fixed_sha"]
                        and _commit_exists(latest["id"], latest["fixed_sha"]))
    if sha_mismatch:
        message = (f"sha головы {current} разошёлся с зафиксированным "
                  f"{latest['fixed_sha']} ({latest['id']})")
        doctor.alerts.raise_alert(conn, target, "incident", "doctor.recovery.sha", message)
        results.append(doctor.Check("recovery-sha", "fail", message))
    else:
        results.append(doctor.Check("recovery-sha", "ok", "sha головы сходится с журналом"))
    doctor._auto_ack_gone(conn, "doctor.recovery.sha", lambda _msg: sha_mismatch,
                  target=target)
    return results


def _commit_exists(task_id: str, sha: str) -> bool:
    """Коммит `sha` есть в репозитории ссылки документов задачи
    (`artifact_branch.task_repo`): git пульта для артели, клон проекта для
    внешнего target."""
    repo = doctor.artifact_branch.task_repo(task_id)
    if repo == doctor.config.ROOT:
        return doctor.gitcmd.commit_exists(sha)
    return doctor.gitcmd.commit_exists(sha, repo=repo)
