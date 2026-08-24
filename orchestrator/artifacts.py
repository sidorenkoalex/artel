"""Чтение артефактов задачи: frontmatter и свежесть вердикта ревьювера."""
from pathlib import Path

from . import yamlmini


def frontmatter(path: Path) -> dict:
    """Frontmatter артефакта; пустой словарь — файла нет либо блока нет.

    Разбор общий с guard'ом (`yamlmini`): читатель и валидатор обязаны
    видеть в одном файле одно и то же, иначе расхождение форматов
    обнаруживается чужим сбоем, а не проверкой (SPEC T017, требование 2).
    Нечитаемый файл — тоже пустой словарь: FSM из-за него не двигает
    задачу, а причину назовёт guard на том же переходе.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    return yamlmini.frontmatter(text) or {}


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
