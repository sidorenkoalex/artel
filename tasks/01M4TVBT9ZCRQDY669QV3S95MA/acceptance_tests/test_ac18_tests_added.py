"""AC-18: ветка задачи добавляет в tests/ тесты с заявками на мутации перечня требования 7.

Группа: разовый
Зелёный с рождения: долгоживущие файлы планки этой задачи сами лежат в tests/ (tests/test_<id>_min_uses_field.py, tests/test_<id>_reference.py) и несут заявки «Ловит мутацию» на каждую мутацию перечня требования 7; тест сторожит, что ветка их не потеряет и что настоящий targets.yaml веткой не тронут.

Факт задачи — состав её диффа: файлы берутся `changed_paths()` помощника
пульта (закоммиченный дифф от базы плюс неотслеживаемые файлы), текст —
из рабочей копии `CODE_ROOT`. Мутация перечня требования 7 считается
заявленной, если в тексте заявки «Ловит мутацию: …» какого-либо метода
файлов tests/ ветки есть все опорные слова этой мутации.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, changed_paths  # noqa: E402

CLAIM = "Ловит мутацию:"

#: Мутации перечня требования 7 SPEC и опорные слова их заявки.
MUTATIONS = (
    ("повод reference поднял алерт", ("reference", "алерт")),
    ("повод reference — алерт через источник brief.core_reference",
     ("brief.core_reference",)),
    ("запись журнала команды ушла на DEFAULT_TARGET", ("DEFAULT_TARGET",)),
    ("get_reference по задаче перестал давать прежний результат", ("get_reference",)),
    ("граница 90%: ровно 90% — «в пределе»", ("90%",)),
    ("reference выполнилась из окружения роли", ("окружения роли",)),
    ("порог из настройки не передан генератору", ("порог", "config")),
    ("порог не участвует в сверке кэша", ("порог", "кэш")),
    ("неверное min_uses принято", ("min_uses",)),
    ("reference на неизвестном проекте создал каталоги/кэш или вызвал git",
     ("неизвестном проекте", "git")),
    ("reference без клона не отказал", ("без клона",)),
    ("сводка не называет «больше предела»", ("больше предела",)),
    ("reference поднял или снял алерт брифа", ("алерт брифа",)),
    ("target-init упал или удалил клон при сбое сборки", ("target-init", "клон")),
)


def claim_text(doc: str) -> str:
    """Текст заявки «Ловит мутацию: …» докстринга — до пустой строки."""
    if CLAIM not in doc:
        return ""
    rest = doc.split(CLAIM, 1)[1]
    return rest.split("\n\n", 1)[0]


def added_test_files() -> list:
    return sorted(path for path in changed_paths()
                  if path.startswith("tests/") and Path(path).name.startswith("test_")
                  and path.endswith(".py") and (Path(CODE_ROOT) / path).is_file())


def methods_of(source: str) -> list:
    tree = ast.parse(source)
    return [node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test")]


class MutationClaimsTest(unittest.TestCase):

    def test_ac18_tests_claim_every_requirement7_mutation_targets_yaml_untouched(self):
        """Новые тесты tests/ ветки заявляют каждую мутацию требования 7; targets.yaml не тронут.

        Сценарий: среди путей задачи есть файлы `tests/test_*.py`; для
        каждой мутации перечня требования 7 у какого-либо их тестового
        метода найдётся заявка «Ловит мутацию» со всеми опорными словами
        мутации; `targets.yaml` среди путей задачи нет.

        Ловит мутацию: ветка не добавила тестов tests/ на перечень
        требования 7 (или потеряла одну из заявок), либо тесты правят
        настоящий `targets.yaml` (файл в диффе).
        """
        paths = changed_paths()
        self.assertNotIn("targets.yaml", paths, "ветка меняет настоящий targets.yaml")
        files = added_test_files()
        self.assertTrue(files, f"в tests/ нет новых файлов тестов: {paths}")
        claims = []
        for rel in files:
            source = (Path(CODE_ROOT) / rel).read_text(encoding="utf-8")
            for node in methods_of(source):
                claims.append(claim_text(ast.get_docstring(node) or "").casefold())
        for label, words in MUTATIONS:
            with self.subTest(mutation=label):
                self.assertTrue(
                    [c for c in claims if all(w.casefold() in c for w in words)],
                    f"нет заявки со словами {words}")


if __name__ == "__main__":
    unittest.main()
