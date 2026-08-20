"""Чтение артефактов задачи: frontmatter и свежесть вердикта ревьювера."""
import re
from pathlib import Path


def frontmatter(path: Path) -> dict:
    if not path.exists():
        return {}
    m = re.match(r"\A---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.S)
    if not m:
        return {}
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.split("#")[0].strip()
    return meta


def fresh_verdict_iteration(meta: dict, reviewed_iter: int) -> int | None:
    """Номер итерации вердикта, если он новее уже учтённого, иначе None.

    Вердикт учитывается FSM ровно один раз: после возврата задачи в in_dev
    прежний REVIEW.md не двигает её обратно в acceptance. Нечитаемый или
    отсутствующий `iteration` трактуем как несвежий — доказательства нового
    прогона ревьювера нет.
    """
    raw = str(meta.get("iteration", "")).strip()
    if not raw.isdigit():
        return None
    iteration = int(raw)
    return iteration if iteration > reviewed_iter else None
