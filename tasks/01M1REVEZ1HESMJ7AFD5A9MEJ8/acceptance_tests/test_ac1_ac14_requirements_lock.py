"""AC-1, AC-14 (tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/SPEC.md, требования 1, 6):
файл закреплённых версий в корне репозитория.

Красен до реализации: `requirements.lock` ещё не существует в корне
репозитория — `read_text` падает `FileNotFoundError` для оба теста.

Имя файла не зафиксировано буквально (SPEC: «requirements.lock либо
эквивалент») — REQUIREMENTS_LOCK_CANDIDATES перечисляет разумные
альтернативы; выбранный разработчиком путь обязан ещё и совпадать с
`orchestrator.config.REQUIREMENTS_LOCK`, если разработчик заводит такую
константу (естественный способ для `orchestrator/venv.py` и
`check_stack()` делить один и тот же путь, не дублируя литерал) — тест
читает её, если она есть, и делает `getattr` с дефолтом иначе.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT))

from _util import normalize_name, parse_pip_lock  # noqa: E402

# (каноническое имя пакета pip, допустимые написания top-level import,
# которые сканер «только стандартная библиотека» реально встретит в коде
# — хайфен в имени пакета никогда не бывает валидным идентификатором
# Python, поэтому запись в THIRD_PARTY_EXCEPTIONS обязана нести именно
# ИМПОРТИРУЕМОЕ имя модуля, а не написание PyPI).
CANONICAL_PACKAGES = ("pytest", "pytest-timeout", "pytest-xdist")


def _lock_path() -> Path:
    try:
        from orchestrator import config  # noqa: E402
        configured = getattr(config, "REQUIREMENTS_LOCK", None)
        if configured is not None:
            return Path(configured)
    except ImportError:
        pass
    return REPO_ROOT / "requirements.lock"


class RequirementsLockFileTest(unittest.TestCase):

    def test_ac1_lock_file_pins_exact_versions_of_the_three_packages(self):
        """Требование 1/AC-1: файл существует, формат `pip`, и несёт
        ТОЧНУЮ (`==`) версию каждого из `pytest`, `pytest-timeout`,
        `pytest-xdist` — не диапазон и не «последняя».

        Ловит мутацию: один из трёх пакетов записан диапазоном
        (`pytest>=7.0`) вместо точного пина — `parse_pip_lock` (который
        распознаёт только `==`) не найдёт его в разобранном словаре, и
        `assertIn` откажет.
        """
        path = _lock_path()
        self.assertTrue(
            path.exists(),
            f"файл закреплённых версий не найден ({path}) — требование 1")

        pinned = parse_pip_lock(path)
        for package in CANONICAL_PACKAGES:
            self.assertIn(
                normalize_name(package), pinned,
                f"{package} не закреплён точной версией (`==`) в "
                f"{path.name}: {sorted(pinned)}")

    def test_ac1_lock_file_also_pins_transitive_dependencies(self):
        """Требование 1/AC-1: «... и их транзитивных зависимостей» — файл
        обязан нести БОЛЬШЕ, чем только три верхнеуровневых пакета
        (например `iniconfig`, `packaging`, `pluggy`, `execnet` — реальные
        зависимости pytest/pytest-xdist).

        Ловит мутацию: разработчик закрепил только сами три пакета без
        транзитивных зависимостей (`pip install` без `pip freeze` полного
        окружения) — размер разобранного словаря останется равным 3,
        `assertGreater` откажет.
        """
        pinned = parse_pip_lock(_lock_path())
        self.assertGreater(
            len(pinned), len(CANONICAL_PACKAGES),
            f"файл закреплённых версий содержит только верхнеуровневые "
            f"пакеты без транзитивных зависимостей: {sorted(pinned)}")


class LockManifestConsistencyTest(unittest.TestCase):

    def test_ac14_every_manifest_exception_is_present_in_the_lock_file(self):
        """Требование 6/AC-14: набор пакетов файла закреплённых версий
        согласован со списком исключений манифеста
        (`orchestrator.stack.THIRD_PARTY_EXCEPTIONS`) — КАЖДАЯ запись
        исключений обязана реально встречаться в файле закреплённых
        версий (иначе манифест разрешает импорт пакета, которого
        воспроизводимая установка не поставит).

        Сверка идёт по имени, приведённому к PyPI-написанию
        (`_/-` эквивалентны, регистр не важен, PEP 503) — запись
        исключений несёт ИМПОРТИРУЕМОЕ имя модуля (`pytest_timeout`,
        `xdist`), а файл закреплённых версий — имя пакета PyPI
        (`pytest-timeout`, `pytest-xdist`); нормализация обеих сторон
        снимает это расхождение написания, не проблему согласованности.

        Красен до реализации (дополнительно к отсутствию файла):
        `orchestrator.stack` (ветка S1, 01M1RDCAFENSW2VVAPECHCVGMM) ещё
        не смержена в этом дереве — импорт падает `ModuleNotFoundError`.

        Ловит мутацию: разработчик добавил в THIRD_PARTY_EXCEPTIONS
        пакет, которого нет в файле закреплённых версий (опечатка в
        имени при переносе между манифестом и локом) — соответствующий
        `assertIn` откажет.
        """
        from orchestrator import stack  # noqa: E402 (см. докстринг класса)

        pinned = {normalize_name(name) for name in
                 parse_pip_lock(_lock_path())}
        # `xdist` — реальное импортируемое имя пакета `pytest-xdist`,
        # `pytest_timeout` — пакета `pytest-timeout`: сверка по обеим
        # правдоподобным нормализациям записи манифеста, не только по
        # буквальному PyPI-написанию (см. докстринг модуля).
        alt_pip_name = {"xdist": "pytest-xdist", "pytest_timeout": "pytest-timeout"}

        for name, reason in stack.THIRD_PARTY_EXCEPTIONS:
            candidate = alt_pip_name.get(name, name)
            self.assertIn(
                normalize_name(candidate), pinned,
                f"исключение манифеста {name!r} (причина: {reason!r}) не "
                f"найдено в файле закреплённых версий: {sorted(pinned)}")


if __name__ == "__main__":
    unittest.main()
