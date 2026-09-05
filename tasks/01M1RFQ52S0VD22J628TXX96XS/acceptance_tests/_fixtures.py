"""Общие фикстуры для приёмочных тестов 01M1RFQ52S0VD22J628TXX96XS.

Не test_*.py — unittest discover его не подхватит, это общий модуль,
импортируемый остальными файлами каталога.

Карта строится РЕАЛЬНЫМ рендерером `scripts.codebase_map.render` на
синтетических `ModuleInfo`, а не собирается вручную строкой: формат
остаётся байт-в-байт тем же, что выдаёт генератор сегодня, вместо
копии, рассинхронизирующейся с ним при следующей правке `render()`.
Три секции фикстуры — по одной на каждый вид, который различают
правила проекции (AC-2/AC-3): `orchestrator/*`, `scripts/*`, `tests/*`.
У каждой — НЕПУСТЫЕ «Импортирует»/«Импортируется» (не «—»), чтобы тест
различал «блок удалён проекцией» от «блок и так был пуст».
"""
import re
from pathlib import Path

from scripts import codebase_map

SHA = "a" * 40

FOO = codebase_map.ModuleInfo(
    Path("orchestrator/foo.py"), "Оркестрирует нечто важное.",
    ["do_thing", "run_it"], [])
BAR = codebase_map.ModuleInfo(
    Path("scripts/bar.py"), "Скрипт вспомогательный.", ["run_bar"], [])
BAZ = codebase_map.ModuleInfo(
    Path("tests/test_baz.py"), "Тестирует нечто важное.", ["helper"], [])

RESOLVED_IMPORTS = {
    "orchestrator/foo.py": ["scripts/bar.py"],
    "scripts/bar.py": [],
    "tests/test_baz.py": ["orchestrator/foo.py", "scripts/bar.py"],
}
IMPORTED_BY = {
    "orchestrator/foo.py": ["tests/test_baz.py"],
    "scripts/bar.py": ["orchestrator/foo.py", "tests/test_baz.py"],
    "tests/test_baz.py": [],
}


def small_map(sha: str = SHA) -> str:
    """Карта трёх видов секций — маленькая, для покомпонентных проверок
    правил проекции и сборки брифа."""
    return codebase_map.render([FOO, BAR, BAZ], RESOLVED_IMPORTS, IMPORTED_BY, sha)


def oversized_map(threshold_bytes: int, sha: str = SHA) -> str:
    """Карта, чей ПОЛНЫЙ текст превышает `threshold_bytes` минимум в
    полтора раза, а ПРОЕКЦИЯ — нет: разбухание — только в блоке
    «Импортируется» секции `orchestrator/foo.py`, который проекция
    отбрасывает целиком для `orchestrator/*` (AC-2). Запас в полтора
    раза — чтобы мелкая будущая правка `render()` (лишний пробел,
    другой разделитель) не превратила тест в такой, что зависит от
    точной арифметики байтов на границе потолка.
    """
    padding = [f"orchestrator/mod_padding_{i:06d}.py" for i in range(8000)]
    imported_by = dict(IMPORTED_BY)
    imported_by["orchestrator/foo.py"] = padding
    text = codebase_map.render([FOO, BAR, BAZ], RESOLVED_IMPORTS, imported_by, sha)
    assert len(text.encode("utf-8")) > threshold_bytes * 1.5, (
        "фикстура недостаточно раздута для теста потолка размера — "
        "поправь число путей-заполнителей в oversized_map")
    return text


def section_block(map_text: str, rel: str) -> str:
    """Текст секции `## {rel}` до следующего заголовка секции (или до
    конца текста) — сравнение по всему тексту ловило бы содержимое
    ЧУЖОЙ секции."""
    marker = f"## {rel}"
    start = map_text.index(marker)
    rest = map_text[start + len(marker):]
    next_marker = rest.find("\n## ")
    body = rest if next_marker == -1 else rest[:next_marker]
    return marker + body


def section_headers(map_text: str) -> list:
    """Заголовки секций `## <путь>` по порядку появления в тексте."""
    return re.findall(r"^## (.+)$", map_text, re.M)


def header_block(map_text: str) -> str:
    """Текст до первого заголовка секции — шапка (frontmatter, заголовок
    «# Codebase-map пульта», строка про автогенерацию)."""
    idx = map_text.index("\n## ")
    return map_text[:idx]
