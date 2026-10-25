"""Пакет orchestrator/doctor -- дрейф конвенций внешнего проекта: файл пульта
`conventions.md` против `refs/heads/<base>` клона (SPEC
01M5T18K1YFBYA7MM1BBRV869A, требование 8).
"""
from orchestrator import doctor

PROJECT_CONVENTIONS_CHECK = "project-conventions"


def check_project_conventions(name: str) -> list:
    """Строка `project-conventions-<проект>` внешнего проекта; у артели
    строки нет — её конвенции живут в её же репозитории. Сверка только
    читает: файл не меняется, сеть не трогается (`conventions.drift`)."""
    if doctor.repo_context.is_artel(name):
        return []
    try:
        status, detail = doctor.conventions.drift(name)
    except Exception as exc:  # noqa: BLE001 — строка doctor, не падение команды
        status, detail = "warn", (f"сверка не выполнена: "
                                  f"{type(exc).__name__}: {exc}")
    return [doctor.Check(f"{PROJECT_CONVENTIONS_CHECK}-{name}", status,
                         f"проект {name}: {detail}")]
