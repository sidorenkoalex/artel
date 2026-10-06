"""AC-17: карта кодовой базы описывает итог трёх частей этапа 3 ADR-0021.

Группа: разовый
Красен до реализации: строки «Назначение» карты на main не называют ни перечня защищённых путей проекта, ни сверки проверок пункта 8 с репозиторием проекта — их первые строки докстрингов модулей задача ещё не переписала.

Карта (`docs/codebase-map.md` рабочей копии задачи) строится из ПЕРВЫХ
строк докстрингов модулей (`scripts/codebase_map.py::extract_purpose`),
поэтому критерий сверяется по строкам «Назначение» модулей `orchestrator/`
— и вдобавок сверяется, что эти строки карты совпадают с тем, что
генератор строит по самой ветке (карта пересобрана, а не дописана руками).
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _pult  # noqa: E402

CODE_ROOT = Path(_pult.CODE_ROOT)
sys.path.insert(0, str(CODE_ROOT))

from scripts import codebase_map  # noqa: E402

_SECTION = re.compile(r"^## (?P<path>\S+)\s*$")
_PURPOSE = re.compile(r"^\*\*Назначение:\*\* (?P<text>.*)$")


def map_purposes(text: str) -> dict:
    """{путь модуля: строка «Назначение»} из текста карты."""
    purposes, current = {}, None
    for line in text.splitlines():
        m = _SECTION.match(line)
        if m:
            current = m.group("path")
            continue
        m = _PURPOSE.match(line)
        if m and current is not None:
            purposes[current] = m.group("text").strip()
    return purposes


def orchestrator_purposes(purposes: dict) -> dict:
    return {p: t for p, t in purposes.items() if p.startswith("orchestrator/")}


def names_test_profile(text: str) -> bool:
    low = text.lower()
    return "профил" in low and "тест" in low and "проект" in low


def names_protected_paths(text: str) -> bool:
    low = text.lower()
    return "защищ" in low and "пут" in low and "проект" in low


def names_item8_repo(text: str) -> bool:
    low = text.lower()
    if "repo_context" in low:
        return True
    return ("репозитори" in low and "проект" in low and "провер" in low)


class CodebaseMapStage3Test(unittest.TestCase):

    def setUp(self):
        path = CODE_ROOT / "docs" / "codebase-map.md"
        self.map_text = path.read_text(encoding="utf-8")
        self.purposes = orchestrator_purposes(map_purposes(self.map_text))
        self.assertTrue(self.purposes,
                        "в карте не нашлось ни одной строки «Назначение» "
                        "модулей orchestrator/ — разбор карты не сработал")

    def _which(self, predicate) -> list:
        return sorted(p for p, t in self.purposes.items() if predicate(t))

    def test_ac17_map_names_profile_protected_paths_and_project_repo(self):
        """Карта ветки называет профиль тестов проекта, перечень защищённых путей проекта и сверку проверок пункта 8 с репозиторием проекта.

        Сценарий: читается `docs/codebase-map.md` рабочей копии задачи,
        из неё — строки «Назначение» модулей `orchestrator/`. Среди них
        обязана быть строка о профиле тестов проекта, строка о перечне
        защищённых путей проекта и строка о сверке проверок с репозиторием
        проекта (`repo_context`, либо слова «репозиторий», «проект»,
        «проверка» в одной строке).

        Ловит мутацию: разработчик переписал докстринги модулей, но первая
        строка `repo_context.py`/модулей гейтов осталась прежней («Репозиторный
        контекст target'а…») — в карте нет ни строки о защищённых путях
        проекта, ни о сверке проверок с его репозиторием, и тест краснеет
        с перечнем недостающего.
        """
        missing = []
        if not self._which(names_test_profile):
            missing.append("профиль тестов проекта")
        if not self._which(names_protected_paths):
            missing.append("перечень защищённых путей проекта")
        if not self._which(names_item8_repo):
            missing.append("сверка проверок пункта 8 с репозиторием проекта "
                           "(repo_context)")
        self.assertEqual(missing, [],
                         "строки «Назначение» карты не называют: "
                         + "; ".join(missing))

    def test_ac17_map_rebuilt_from_branch_docstrings(self):
        """Строки «Назначение» карты совпадают с тем, что генератор карты строит по исходникам ветки.

        Сценарий: `scripts/codebase_map.build_modules` по корню рабочей
        копии даёт назначение каждого модуля `orchestrator/` (первая строка
        докстринга); то же назначение обязана нести карта
        `docs/codebase-map.md` — иначе карта дописана руками или не
        пересобрана после правки докстрингов.

        Ловит мутацию: разработчик поправил первую строку докстринга
        `orchestrator/repo_context.py`, но не перезапустил
        `scripts/codebase_map.py` — строка «Назначение» карты расходится с
        докстрингом, тест называет модуль и обе строки.
        """
        modules, _, _ = codebase_map.build_modules(CODE_ROOT)
        built = {m.rel_path.as_posix(): m.purpose for m in modules
                 if m.rel_path.as_posix().startswith("orchestrator/")}
        diverged = [f"{path}: карта «{self.purposes.get(path)}» != "
                    f"докстринг «{purpose}»"
                    for path, purpose in sorted(built.items())
                    if self.purposes.get(path) != purpose]
        self.assertEqual(diverged, [],
                         "карта не пересобрана по ветке:\n"
                         + "\n".join(diverged))


if __name__ == "__main__":
    unittest.main()
