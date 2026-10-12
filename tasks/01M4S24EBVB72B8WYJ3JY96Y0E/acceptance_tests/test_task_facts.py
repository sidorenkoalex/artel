"""Факты ветки задачи К-3б: значение предела справочника ядра в `config`
(AC-8) и свежесть `docs/codebase-map.md` на голове ветки (AC-14).
Поведение брифа и шага после мержа (AC-1…AC-12) держат долгоживущие
файлы `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py` и
`tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`.

Группа: разовый

Красен до реализации: константы `config.CORE_REFERENCE_MAX_BYTES` ещё нет, а после чекпоинта шага test_author (пульт коммитит в ветку долгоживущие файлы `tests/` этой задачи) карта головы ветки их не знает — сверка карты с выводом генератора расходится, пока разработчик не перегенерирует карту.

Планка провалидирована временным стабом реализации (константа, модуль `reference_cache`, компонент брифа, шаг после мержа): этот файл и оба долгоживущих файла зелёные, заявленные мутации (`sha=merge_sha`, перехват перечнем трёх типов, обработчик вне `try`, вызов до push, размер в символах, `note` в хэшируемом тексте) краснят их; стаб удалён, не закоммичен.

Карта сверяется с генератором на дереве ГОЛОВЫ ветки (`git archive HEAD`
во временный каталог), а не на рабочем дереве: незакоммиченные правки в
сверку не попадают. Строка `built_at_sha` не сверяется — генератор не
может записать в карту sha коммита, который её же и несёт (тот же
приём, что джоб свежести карты в CI).
"""
# AC-13: skip — проверяется ревью и guard
import subprocess
import sys
import tarfile
import io
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

MAP_REL = "docs/codebase-map.md"


def _git(*args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(CODE_ROOT), *args],
                            capture_output=True, timeout=60)
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: "
                             f"{result.stderr.decode('utf-8', 'replace')}")
    return result.stdout


def _without_built_at(text: str) -> str:
    return "\n".join(line for line in text.splitlines()
                     if not line.startswith("built_at_sha:"))


class LimitValueTest(unittest.TestCase):

    def test_ac8_limit_constant_is_32768_bytes(self):
        """Константа предела справочника ядра в `orchestrator/config.py`
        ветки задачи равна 32 768.

        Ловит мутацию: константа не заведена или заведена другим значением
        (например 32 000 или 65 536) — атрибута нет или значение разойдётся.
        """
        if str(CODE_ROOT) not in sys.path:
            sys.path.insert(0, str(CODE_ROOT))
        from orchestrator import config
        self.assertEqual(config.CORE_REFERENCE_MAX_BYTES, 32_768)


class CodebaseMapFreshTest(unittest.TestCase):

    def test_ac14_committed_map_matches_generator_output_at_head(self):
        """Дерево головы ветки выгружено во временный каталог, генератор
        карты этого же дерева собирает текст карты по нему.

        Закоммиченный `docs/codebase-map.md` головы совпадает с собранным
        текстом построчно, кроме строки `built_at_sha`.

        Ловит мутацию: разработчик поменял `*.py` в `orchestrator/`,
        `scripts/` или `tests/` (новая функция, новый модуль, новый импорт)
        и не перегенерировал карту — секции карты разойдутся с выводом
        генератора.
        """
        head = _git("rev-parse", "HEAD").decode().strip()
        committed = _git("show", f"HEAD:{MAP_REL}").decode("utf-8")
        with tempfile.TemporaryDirectory(prefix="k3b-map-") as tmp:
            with tarfile.open(fileobj=io.BytesIO(_git("archive", "HEAD")),
                              mode="r:") as archive:
                archive.extractall(tmp, filter="data")
            sys.path.insert(0, tmp)
            try:
                for name in [m for m in sys.modules
                             if m == "scripts" or m.startswith("scripts.")]:
                    del sys.modules[name]
                from scripts import codebase_map
                modules, resolved, imported_by = codebase_map.build_modules(Path(tmp))
                generated = codebase_map.render(modules, resolved, imported_by, head)
            finally:
                sys.path.remove(tmp)
                for name in [m for m in sys.modules
                             if m == "scripts" or m.startswith("scripts.")]:
                    del sys.modules[name]
        self.assertEqual(_without_built_at(committed), _without_built_at(generated),
                         f"{MAP_REL} головы {head[:8]} не совпадает с выводом "
                         f"python3 scripts/codebase_map.py")


if __name__ == "__main__":
    unittest.main()
