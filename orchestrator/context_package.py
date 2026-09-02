"""Опись компонентов и дисциплина частей контекстных пакетов — общий слой
брифа разработчика (`brief.developer_brief`) и ревью-пакета
(`review.review_package`), tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X.

Источник проблемы: сборка контекста единым документом уже была (T011,
T028, T029), но без дисциплины размера — роль перечитывает уже
включённое, инструмент чтения молча усекает длинный файл/diff, а
неограниченный diff уходит ревьюверу молча. Здесь — две меры против
этого: опись (путь/размер/sha256 на каждый включённый целиком компонент,
AC-1) и деление итогового текста на пронумерованные части без потери
хвоста, когда он крупнее потолка (AC-5/AC-6/AC-9/AC-10) — вместо
прежнего `review.truncate_diff`/`truncate_package`.
"""
import hashlib

from . import config

FILE_CAP_REASON = "превышен лимит файла"


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render_component(label: str, text: str) -> str:
    """Часть пакета для одного целиком-включаемого компонента.

    Под потолком файла (`config.CONTEXT_FILE_MAX_BYTES`) — тело целиком, а
    заголовок несёт путь/размер/sha256 (AC-1). Крупнее — тело не идёт в
    пакет вовсе: заголовок несёт путь/размер/причину пропуска, роль
    обязана прочитать такой компонент адресно инструментом чтения (AC-2).

    Размер и sha256 считаются по ИСХОДНОМУ (не подрезанному `.strip()`)
    тексту — опись обязана отвечать байт в байт содержимому, которое
    действительно читал бы инструмент чтения этого же пути.
    """
    size = len(text.encode("utf-8"))
    if size > config.CONTEXT_FILE_MAX_BYTES:
        return (
            f"### {label} — {size} байт — пропущен: {FILE_CAP_REASON} "
            f"(потолок {config.CONTEXT_FILE_MAX_BYTES} байт)\n\n"
            f"[содержимое не показано — {FILE_CAP_REASON}; читай {label} "
            f"адресно инструментом чтения]\n"
        )
    sha = sha256_of(text)
    return f"### {label} — {size} байт, sha256={sha}\n\n{text.strip()}\n"


def split_into_parts(text: str) -> list[str]:
    """Части текста по границам строк, каждая не крупнее
    `config.CONTEXT_PART_MAX_BYTES` байт — ни одна строка не разрывается
    (AC-5). Жадное накопление: строка, что не помещается в текущую часть,
    открывает следующую целиком со своей строки."""
    cap = config.CONTEXT_PART_MAX_BYTES
    lines = text.splitlines(keepends=True)
    parts: list[str] = []
    current: list[str] = []
    size = 0
    for line in lines:
        line_size = len(line.encode("utf-8"))
        if current and size + line_size > cap:
            parts.append("".join(current))
            current, size = [], 0
        current.append(line)
        size += line_size
    if current:
        parts.append("".join(current))
    return parts or [text]


def _pack_components(components: list[str], sep: str) -> list[str]:
    """Части, каждая не крупнее `config.CONTEXT_PART_MAX_BYTES`, но
    упакованные по границам КОМПОНЕНТОВ, а не по границам строк всего
    текста вслепую (R1-F1, REVIEW.md итерация 1, major): компонент, чей
    собственный размер под потолком части, обязан попасть в одну часть
    целиком — иначе большие соседние компоненты (SPEC/PLAN/прошлый
    REVIEW под потолком файла, но уже сами по себе близкие к потолку
    части) могли подвести накопленный размер тела почти вплотную к
    границе части и разорвать diff (или любой другой компонент) пополам
    между двумя «ЧАСТЬ N/M», хотя его собственный размер (AC-8) далеко
    меньше потолка.

    Компонент крупнее потолка части сам по себе — внутренний случай, не
    новый: делится по строкам той же функцией `split_into_parts`, что и
    раньше, и его куски идут отдельными законченными частями, не
    смешиваясь со строками соседних компонентов.

    Разделитель `sep` — своя атомарная единица упаковки (пустая или
    однобайтовая «\\n», как в текущих вызывающих), поэтому конкатенация
    возвращённых частей побайтово равна `sep.join(components)` (AC-6)
    независимо от того, где именно прошли границы частей.
    """
    cap = config.CONTEXT_PART_MAX_BYTES
    parts: list[str] = []
    current: list[str] = []
    size = 0

    def flush() -> None:
        nonlocal current, size
        if current:
            parts.append("".join(current))
            current, size = [], 0

    for i, component in enumerate(components):
        if i:
            unit = sep + component
        else:
            unit = component
        unit_size = len(unit.encode("utf-8"))
        if unit_size > cap:
            flush()
            parts.extend(split_into_parts(unit))
            continue
        if current and size + unit_size > cap:
            flush()
        current.append(unit)
        size += unit_size
    flush()
    return parts


def discipline(components: list[str], sep: str = "\n") -> tuple[str, int]:
    """(итоговый_текст, число_частей) — компоненты, склеенные `sep`, как
    есть под потолком части и 0 частей (AC-8), иначе — деление на
    пронумерованные части с sha256 каждой (AC-5/AC-6/AC-9) и явной
    инструкцией прочитать все части по порядку (AC-7) — без потери
    хвоста (AC-10, замена `truncate_diff`/`truncate_package`).

    Принимает СПИСОК компонентов (не готовый склеенный текст), чтобы
    деление на части могло уважать их границы (R1-F1) — вызывающий код
    передаёт те же куски, что раньше сам склеивал через `sep.join`, здесь
    `sep.join(components)` — тот же итоговый текст под потолком части, что
    и раньше, побайтово идентичный.

    Части, которые несёт манифест (для sha256 и для AC-6 «конкатенация
    частей побайтово равна целому»), — чистые срезы исходного текста по
    границам компонентов (или строк — для компонента крупнее потолка
    части); заголовки вида «--- ЧАСТЬ N/M ---» в возвращаемом тексте —
    только разметка для роли, не часть самих частей.
    """
    text = sep.join(components)
    size = len(text.encode("utf-8"))
    if size <= config.CONTEXT_PART_MAX_BYTES:
        return text, 0
    parts = _pack_components(components, sep)
    rendered = [
        f"Текст ниже — {size} байт, больше потолка части "
        f"{config.CONTEXT_PART_MAX_BYTES} байт — поделён на {len(parts)} "
        f"пронумерованных частей. Прочитай все части по порядку, прежде "
        f"чем действовать; конкатенация частей по номеру равна целому "
        f"тексту.\n"
    ]
    for i, part in enumerate(parts, start=1):
        part_bytes = len(part.encode("utf-8"))
        part_sha = sha256_of(part)
        rendered.append(
            f"--- ЧАСТЬ {i}/{len(parts)} ({part_bytes} байт, "
            f"sha256={part_sha}) ---\n\n{part}"
        )
    return "\n".join(rendered), len(parts)
