"""Пакет orchestrator/doctor -- предел числа процессов шага роли и запас пользователя.

SPEC 01M6KB0FS809DG55K9A20CYKJE, требование 6: значения берутся теми же
функциями `runner`, что и шаг, — строка не показывает предела, которого
у шага нет.
"""

from orchestrator import doctor

ROLE_NPROC_CHECK = "role-nproc"
UNAVAILABLE_MARK = "счёт недоступен"
DEFAULT_MARK = "значение по умолчанию"


def check_role_nproc() -> doctor.Check:
    runner = doctor.runner
    maxproc, outcome = runner._read_maxprocperuid()
    limit = runner.role_nproc_limit()
    maxproc_text = str(maxproc) if outcome == "ok" else "недоступен"
    parts = [f"kern.maxprocperuid {maxproc_text}", f"предел шага {limit}"]
    status = "ok"
    try:
        count = runner._user_process_count()
    except Exception as exc:
        parts.append(f"процессов пользователя — {UNAVAILABLE_MARK} ({exc})")
        status = "warn"
    else:
        parts.append(f"процессов пользователя {count}")
        if count >= limit:
            parts.append("запас исчерпан — шаг роли не стартует")
            status = "warn"
    if outcome != "ok":
        parts.append(f"{DEFAULT_MARK} "
                     f"{doctor.config.ROLE_NPROC_FALLBACK_MAXPROC}")
    return doctor.Check(ROLE_NPROC_CHECK, status, "; ".join(parts))
