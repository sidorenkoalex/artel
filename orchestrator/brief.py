"""Бриф роли одним документом: SPEC/TZ + карта кодовой базы + конвенции
(tasks/T028).

Компоненты клеятся в текст промпта, а не выдаются инструкцией «прочитай
файл X сам» (SPEC T028, требование 2) — роль получает контекст без
повторных чтений репозитория. Свежесть карты — ленивая сверка при сборке
брифа тем же способом, каким уже пользуется CI-джоба `codebase-map`
(`.github/workflows/ci.yml`, tasks/T027): диапазон `built_at_sha..HEAD`
по путям `orchestrator/*.py`, `scripts/*.py`, `tests/*.py`. Расхождение —
регенерация до сборки; сбой регенерации — алерт и честная пометка в
тексте, не молчаливая выдача стухшей карты (ADR-0003 §3б).
"""
import hashlib
import re
import subprocess

from . import alerts, config, gitcmd, store

MAP_REL = "docs/codebase-map.md"
CONVENTIONS_REL = "CLAUDE.md"
# Те же три glob'а, что и у CI-джобы codebase-map — общий способ сверки
# свежести карты (SPEC T028, требование 5).
MAP_WATCH_GLOBS = ("orchestrator/*.py", "scripts/*.py", "tests/*.py")
HEADER = "--- БРИФ РОЛИ ---"


def component_hash(text: str) -> str:
    """sha256 содержимого компонента: журнал остаётся верным содержимому,
    а не статической меткой (SPEC T028, требование 8)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _built_at_sha(map_text: str) -> str:
    match = re.search(r"^built_at_sha:\s*(\S+)", map_text, re.M)
    return match.group(1) if match else ""


def _stale_paths(base_sha: str) -> list[str]:
    """Пути `orchestrator/scripts/tests`, изменившиеся между `base_sha` и
    HEAD; git не ответил — считаем «расхождений нет» (то же вырожденное
    решение, каким уже пользуется `gitcmd.diff_paths`: молчание git не
    повод регенерировать карту вслепую на каждом шаге)."""
    res = gitcmd.git("diff", "--name-only", base_sha, "HEAD", "--",
                     *MAP_WATCH_GLOBS)
    if res.returncode != 0:
        return []
    return [p for p in res.stdout.splitlines() if p]


def _regenerate_map() -> subprocess.CompletedProcess:
    """Перегон `scripts/codebase_map.py` в корне пульта — тот же генератор,
    которым уже пользуется CI-джоба `codebase-map` (tasks/T027)."""
    return subprocess.run(["python3", "scripts/codebase_map.py"],
                          cwd=config.ROOT, capture_output=True, text=True)


def fresh_map_text(conn, task_id: str) -> str:
    """Текст `docs/codebase-map.md`, свежей или честно помеченной стухшей.

    Расхождение по `MAP_WATCH_GLOBS` в диапазоне `built_at_sha..HEAD` —
    регенерация до сборки брифа (требование 5, 6, AC-5, AC-6); сбой
    регенерации — алерт (`alerts.raise_alert`, дедуп по (target, kind,
    source, message) уже встроен) и явная пометка в начале текста с
    использованным `built_at_sha` и путями расхождения, карта — прежняя,
    непереписанная версия (требование 7, AC-7).
    """
    text = (config.ROOT / MAP_REL).read_text(encoding="utf-8")
    base_sha = _built_at_sha(text)
    stale = _stale_paths(base_sha)
    if not stale:
        return text
    regen = _regenerate_map()
    if regen.returncode == 0:
        return (config.ROOT / MAP_REL).read_text(encoding="utf-8")
    reason = regen.stderr.strip()[:200] or f"код возврата {regen.returncode}"
    message = f"регенерация {MAP_REL} не удалась: {reason}"
    alerts.raise_alert(conn, store.task_target(conn, task_id), "incident",
                       "brief.codebase_map", message)
    note = (
        f"[КАРТА НЕАКТУАЛЬНА: {message}. Использованный built_at_sha="
        f"{base_sha or '—'}. Пути расхождения: {', '.join(stale)}.]\n\n")
    return note + text


def _journal_component(conn, task_id: str, role: str, label: str,
                       text: str) -> str:
    """Хэш компонента — в журнал шага; собранный кусок текста — брифу."""
    store.journal(conn, task_id, role, "бриф: компонент",
                  f"{label}: sha256={component_hash(text)}")
    return f"### {label}\n\n{text.strip()}\n"


def developer_brief(conn, task_id: str) -> str:
    """Бриф роли developer: SPEC задачи + карта + конвенции проекта одним
    документом (требования 1, 3, 4, 8)."""
    spec_text = (config.TASKS / task_id / "SPEC.md").read_text(
        encoding="utf-8")
    map_text = fresh_map_text(conn, task_id)
    conventions_text = (config.ROOT / CONVENTIONS_REL).read_text(
        encoding="utf-8")
    parts = [
        _journal_component(conn, task_id, "developer",
                           f"tasks/{task_id}/SPEC.md", spec_text),
        _journal_component(conn, task_id, "developer", MAP_REL, map_text),
        _journal_component(conn, task_id, "developer", CONVENTIONS_REL,
                           conventions_text),
    ]
    return f"{HEADER}\n\n" + "\n".join(parts)


def analyst_map_component(conn, task_id: str) -> str:
    """Добавка к входу analyst: карта тем же механизмом, что у developer
    (требование 9) — TZ.md остаётся прежним, отдельно не читаемым здесь
    входом, скилы и остальной вход роли не меняются."""
    map_text = fresh_map_text(conn, task_id)
    part = _journal_component(conn, task_id, "analyst", MAP_REL, map_text)
    return f"{HEADER}\n\n{part}"
