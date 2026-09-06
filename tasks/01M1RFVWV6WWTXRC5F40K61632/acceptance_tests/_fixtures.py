"""Общие фикстуры приёмочных тестов 01M1RFVWV6WWTXRC5F40K61632.

Не test_*.py — unittest discover его не подхватит, это общий модуль,
импортируемый остальными файлами каталога.

Карта строится РЕАЛЬНЫМ рендерером `scripts.codebase_map.render` на
синтетических `ModuleInfo` (тот же приём, что и в
tasks/01M1RFQ52S0VD22J628TXX96XS/acceptance_tests/_fixtures.py — сосед
по кодовой базе, тоже вокруг codebase_map.py): формат карты остаётся
байт-в-байт тем же, что выдаёт генератор сегодня, вместо копии,
рассинхронизирующейся с ним при следующей правке `render()`.

`map_stats` не специфицирована SPEC на уровне точных имён полей сверх
`bytes_total`/`sections_total`/`bytes_by_dir`/`top_sections`/
`bytes_projection` (AC-1..AC-4) — схема `bytes_by_dir` (словарь по
`codebase_map.MODULE_DIRS`) и `top_sections` (список словарей
`{"name": <rel-path>, "bytes": <int>}`, по убыванию размера) выбрана
здесь как единственная конкретизация, совместимая с буквальным текстом
критериев; она же и есть локальная планка для разработчика.
"""
import re
from pathlib import Path

from scripts import codebase_map

SHA = "a" * 40


def build_map(modules_spec: list, sha: str = SHA) -> str:
    """Карта из спецификации `[(rel_path, purpose, n_functions,
    importers_of), ...]` — `render()` настоящего генератора, без ручной
    сборки markdown-строки.

    `n_functions` растягивает секцию управляемым числом строк
    «Публичные функции»; `importers_of` — список rel_path, «импортирующих»
    этот модуль (растягивает «Импортируется» тем же управляемым образом).
    Оба рычага — без хрупкой арифметики байт напрямую по markdown.
    """
    modules = [
        codebase_map.ModuleInfo(
            Path(rel), purpose, [f"func_{i:03d}" for i in range(n_funcs)], [])
        for rel, purpose, n_funcs, _ in modules_spec
    ]
    resolved_imports = {rel: [] for rel, *_ in modules_spec}
    imported_by = {rel: sorted(importers)
                  for rel, _, _, importers in modules_spec}
    return codebase_map.render(modules, resolved_imports, imported_by, sha)


def section_headers(map_text: str) -> list:
    """Заголовки секций `## <путь>` по порядку появления в тексте."""
    return re.findall(r"^## (.+)$", map_text, re.M)


def section_block(map_text: str, rel: str) -> str:
    """Текст секции `## {rel}` до следующего заголовка секции (или до
    конца текста)."""
    marker = f"## {rel}"
    start = map_text.index(marker)
    rest = map_text[start + len(marker):]
    next_marker = rest.find("\n## ")
    body = rest if next_marker == -1 else rest[:next_marker]
    return marker + body


def expected_stats(map_text: str) -> dict:
    """Эталон `map_stats` для сравнения, посчитанный напрямую от текста
    карты той же логикой «секция = `## ` до следующего `## ` или EOF»,
    единственной структурной опорой формата (см. `codebase_map.render`)."""
    headers = section_headers(map_text)
    bytes_by_dir = {d: 0 for d in codebase_map.MODULE_DIRS}
    sizes = []
    for h in headers:
        block = section_block(map_text, h)
        size = len(block.encode("utf-8"))
        top_dir = h.split("/")[0]
        bytes_by_dir[top_dir] = bytes_by_dir.get(top_dir, 0) + size
        sizes.append((h, size))
    top_sections = sorted(sizes, key=lambda t: -t[1])[:5]
    return {
        "bytes_total": len(map_text.encode("utf-8")),
        "sections_total": len(headers),
        "bytes_by_dir": bytes_by_dir,
        "top_sections": [{"name": n, "bytes": b} for n, b in top_sections],
    }
