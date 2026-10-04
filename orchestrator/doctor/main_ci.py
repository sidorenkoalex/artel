"""Пакет orchestrator/doctor -- цвет CI main артели (SPEC
01M3SF7DPFGEZ7VYEGGXGTX49E, требование 3, AC-3).

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""

from orchestrator import doctor

MAIN_CI_CHECK = "main-ci"


def check_main_ci() -> doctor.Check:
    """Цвет CI main от головы origin/main — тем же определением, что у
    `pin-update` и гейта мержа (`ci.main_line_status`: каждая проверка — с
    последнего коммита первой родительской линии, где она исполнялась).
    До этой строки красный main был виден только на странице GitHub, а
    документный коммит поверх него показывал там зелёную голову.

    `ok` — все проверки зелёные; `fail` — коммит падения и упавшие
    проверки; `warn` — проверка ещё идёт, `gh` не ответил либо origin не
    опрошен (сверка не проведена — не зелёный и не красный).
    """
    origin_sha, fetch_reason = doctor.fetch_origin_main_sha()
    if not origin_sha:
        detail = f"origin/{doctor.config.MAIN_BRANCH} не опрошен — цвет CI main не сверен"
        if fetch_reason:
            detail += f": {fetch_reason}"
        return doctor.Check(MAIN_CI_CHECK, "warn", detail)
    # Линия — в главной копии, куда `fetch_origin_main_sha` принёс голову:
    # клон артели может отставать от origin или отсутствовать (ревью
    # 01M42PENCS26D0656X8FR7DFA7, R1-F1).
    status = doctor.ci.main_line_status(origin_sha,
                                        repo=doctor.config.ROOT)
    if status.kind == doctor.ci.MAIN_GREEN:
        return doctor.Check(MAIN_CI_CHECK, "ok", status.note)
    if status.kind == doctor.ci.MAIN_RED:
        return doctor.Check(MAIN_CI_CHECK, "fail",
                            f"{status.note} — сначала починить main; следующий "
                            f"мерж и pin-update откажут")
    return doctor.Check(MAIN_CI_CHECK, "warn", status.note)
