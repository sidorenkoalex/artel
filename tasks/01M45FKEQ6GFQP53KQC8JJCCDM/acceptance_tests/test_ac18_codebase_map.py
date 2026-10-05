"""AC-18: карта кодовой базы на ветке свежа и называет профиль тестов,
защищённые пути проекта и перевод проверок на признак проекта.

Группа: разовый
Красен до реализации: ни одна строка «Назначение» разделов `orchestrator/` карты сегодня не говорит ни о профиле тестов, ни о защищённых путях проекта, ни о признаке проекта — докстрингов этапа 3 ещё нет, а карта не пересобрана с новыми файлами `tests/` задачи.

Карта строится генератором ветки (`scripts/codebase_map.py`, функции
`build_modules`/`render`, тот же код, что запускает CI) в памяти, без записи
файла; сверка свежести, как в джобе CI `codebase-map`, — без строки
`built_at_sha:`. «Разделы модулей» — разделы `## orchestrator/…` карты, их
строка `**Назначение:**` (первая строка докстринга модуля). Файл разовый:
формулировки — итог этой задачи, дальше карту держит джоб свежести CI.
"""
import importlib.util
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

ROOT = Path(CODE_ROOT)
MAP = ROOT / "docs" / "codebase-map.md"


def generated_map() -> str:
    spec = importlib.util.spec_from_file_location(
        "codebase_map_of_branch", ROOT / "scripts" / "codebase_map.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    modules, resolved, imported_by = module.build_modules(ROOT)
    return module.render(modules, resolved, imported_by, "x")


def without_sha(text: str) -> str:
    return "\n".join(line for line in text.splitlines()
                     if not line.startswith("built_at_sha:"))


def orchestrator_purposes(text: str) -> dict[str, str]:
    purposes = {}
    for section in re.split(r"(?m)^## ", text)[1:]:
        name = section.split("\n", 1)[0].strip()
        if not name.startswith("orchestrator/"):
            continue
        m = re.search(r"(?m)^\*\*Назначение:\*\* (.*)$", section)
        if m:
            purposes[name] = m.group(1).lower()
    return purposes


class CodebaseMapTest(unittest.TestCase):

    def test_ac18_map_matches_generator(self):
        """Карта на диске ветки совпадает с выводом генератора.

        Сценарий: генератор ветки собирает карту по исходникам рабочей
        копии; текст сверяется с `docs/codebase-map.md` без строки
        `built_at_sha:` — тем же правилом, что джоб свежести CI.

        Ловит мутацию: разработчик поправил докстринг модуля
        `orchestrator/` и не перезапустил `scripts/codebase_map.py` —
        «Назначение» раздела в файле расходится с выводом генератора.
        """
        self.assertEqual(without_sha(MAP.read_text(encoding="utf-8")),
                         without_sha(generated_map()),
                         "docs/codebase-map.md не совпадает с выводом "
                         "scripts/codebase_map.py — карта не пересобрана")

    def test_ac18_map_names_stage3_translation(self):
        """Разделы модулей карты называют три предмета этапа 3.

        Сценарий: в строках «Назначение» разделов `orchestrator/…` карты,
        собранной генератором ветки, ищутся: профиль тестов проекта
        («профил… тест…»), перечень защищённых путей проекта (одна строка
        называет защищённ… пут… и проект) и перевод проверок на признак
        проекта (одна строка называет признак и проект/артель/`repo_context`).

        Ловит мутацию: модуль профиля тестов проекта заведён с докстрингом,
        первая строка которого о другом («Разбор записи targets.yaml»), —
        в карте нет раздела, называющего профиль тестов, тест называет
        недостающий предмет.
        """
        purposes = orchestrator_purposes(generated_map())
        wanted = {
            "профиль тестов проекта":
                lambda p: re.search(r"профил\w*\s+(\w+\s+)?тест", p),
            "перечень защищённых путей проекта":
                lambda p: re.search(r"защищ\w*\s+(\w+\s+)?пут", p)
                and "проект" in p,
            "перевод проверок на признак проекта":
                lambda p: "признак" in p and any(
                    w in p for w in ("проект", "артел", "repo_context")),
        }
        missing = [what for what, hit in wanted.items()
                   if not any(hit(p) for p in purposes.values())]
        self.assertEqual(missing, [], "карта не называет в разделах модулей "
                                      "orchestrator/: " + ", ".join(missing))


if __name__ == "__main__":
    unittest.main()
