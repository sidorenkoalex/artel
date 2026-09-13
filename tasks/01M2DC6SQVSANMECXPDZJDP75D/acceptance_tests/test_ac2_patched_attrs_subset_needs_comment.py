"""AC-2 — 01M2DC6SQVSANMECXPDZJDP75D: сохранившийся частичный
`PATCHED_ATTRS` обязан ссылаться на исключённый путь `config` где-то в
теле своего класса (обоснование сужения) — иначе AC-2 требует расширить
его до полного набора `tests.sandbox.ALL_CONFIG_ATTRS`.

Источник — SPEC.md, «Критерии приёмки»:

AC-2. Каждое сохранившееся подмножество `PATCHED_ATTRS` в `tests/*.py`
несёт комментарий, объясняющий, почему полный `ALL_CONFIG_ATTRS`
избыточен для этого класса; любое подмножество без такого комментария
расширено до полного набора (класс наследует `TmpRootTest.PATCHED_ATTRS`
без переопределения списком).

Критерий не формализует «объясняет достаточно хорошо» (содержательность
формулировки — предмет ревью по дифу, тот же класс критерия, что и
`tasks/01M283NC4JJXK7QS68Y9ET8TBK/acceptance_tests/
test_ac6_coding_standards_skill_update.py` — формулировка текста, не
проверяемый факт). Механически проверяемая часть — САМ ФАКТ присутствия
объяснения: класс с сужённым `PATCHED_ATTRS` обязан упоминать в своём
исходном тексте (докстринг класса или `#`-комментарий рядом с
`PATCHED_ATTRS`) хотя бы одно имя ИСКЛЮЧЁННОГО пути `config` — класс без
единого такого упоминания «объяснением» не назвать ни при каком
прочтении (это и есть проверяемая нижняя планка критерия).

Красен до реализации: сегодня 8 классов `tests/*.py` несут собственный
`PATCHED_ATTRS`-подмножество, не упоминающее НИ ОДНОГО из исключённых
путей `config` нигде в своём теле (например,
`tests/test_agent_failure.py:_AgentFailureTmpRootTest` сужает до 7 из 10
путей и не называет ни `PROJECTS`, ни `TARGETS`, ни `BACKUP_MARKER` —
SPEC «Контекст»); `test_ac2_custom_patched_attrs_subsets_mention_an_
excluded_path` находит эти 8 нарушителей и падает. Единственный
сегодняшний класс с настоящим подмножеством, уже упоминающий исключённый
путь, — `tests/test_doctor.py:_RoleHomeReferenceTmpRootTest` (упоминает
`ROOT` в докстринге); `tests/test_git_fixation.py:_GitFixationTmpRootTest`
несёт литерально полный набор (10 из 10), поэтому в подмножества не
попадает вовсе. Зелёный с рождения:
`test_ac2_synthetic_subset_without_mention_is_caught` — самопроверка
сканера на подставных классах, не на реальном дереве `tests/`; стаб
корректной реализации (временное добавление строки-комментария с
именем `"TARGETS"` в докстринг `_AgentFailureTmpRootTest` подтвердило,
что класс перестаёт попадать в `offenders`; правка отменена `git
checkout` без коммита).
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

REPO_ROOT = Path(__file__).resolve().parents[3]
TESTS_DIR = REPO_ROOT / "tests"
EXCLUDED_FILES = {"test_invariants.py"}

ALL_CONFIG_ATTRS = {
    "DB", "TASKS", "LOGS", "ROOT", "PROJECTS", "TARGETS",
    "ROLE_HOME", "ROLE_CONFIG_DIR", "BACKUP_MARKER", "WORKTREES",
}


def _own_patched_attrs_classes(sources: dict) -> list:
    """[(метка "файл:класс", исходный_текст_класса, множество_значений)]
    для КАЖДОГО класса, задающего `PATCHED_ATTRS` литеральным
    кортежем/списком (не `PATCHED_ATTRS = TmpRootTest.PATCHED_ATTRS` —
    атрибутное выражение, не Tuple/List, не считается «собственным
    подмножеством»: это и есть «наследование без переопределения
    списком» из формулировки AC-2)."""
    result = []
    for relname, src in sources.items():
        tree = ast.parse(src, filename=relname)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for stmt in node.body:
                if not (isinstance(stmt, ast.Assign)
                        and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)
                        and stmt.targets[0].id == "PATCHED_ATTRS"):
                    continue
                if not isinstance(stmt.value, (ast.Tuple, ast.List)):
                    continue
                values = {elt.value for elt in stmt.value.elts
                         if isinstance(elt, ast.Constant)
                         and isinstance(elt.value, str)}
                class_src = ast.get_source_segment(src, node) or ""
                result.append((f"{relname}:{node.name}", class_src, values))
    return result


def _real_tests_sources() -> dict:
    return {
        str(p.relative_to(REPO_ROOT)): p.read_text(encoding="utf-8")
        for p in sorted(TESTS_DIR.glob("*.py"))
        if p.name not in EXCLUDED_FILES
    }


def _unexplained_subsets(entries: list) -> list:
    """Из списка `_own_patched_attrs_classes` — подмножества
    (`values != ALL_CONFIG_ATTRS`), чей исходный текст класса не содержит
    имени НИ ОДНОГО исключённого пути."""
    offenders = []
    for label, class_src, values in entries:
        missing = ALL_CONFIG_ATTRS - values
        if not missing:
            continue
        mentioned = {attr for attr in missing if attr in class_src}
        if not mentioned:
            offenders.append(label)
    return offenders


class PatchedAttrsSubsetsMentionExcludedPathTest(unittest.TestCase):

    def test_ac2_custom_patched_attrs_subsets_mention_an_excluded_path(self):
        """Каждый класс `tests/*.py` (кроме `test_invariants.py`) с
        литеральным подмножеством `PATCHED_ATTRS` называет в своём
        исходном тексте хотя бы один из исключённых путей `config`.

        Ловит мутацию: новый или существующий класс сужает
        `PATCHED_ATTRS` (например, убирает `WORKTREES`/`BACKUP_MARKER`
        при копипасте песочницы под новый файл) и не оставляет ни
        одного слова о том, какой путь исключён и почему — офендер
        появляется в списке, `assertEqual([], ...)` красит тест.
        """
        offenders = _unexplained_subsets(
            _own_patched_attrs_classes(_real_tests_sources()))
        self.assertEqual(
            [], offenders,
            f"класс(ы) с сужённым PATCHED_ATTRS не упоминают НИ ОДНОГО "
            f"исключённого пути config нигде в своём теле (AC-2 требует "
            f"комментарий-обоснование либо расширение до полного набора): "
            f"{offenders}")

    def test_ac2_synthetic_subset_without_mention_is_caught(self):
        """Сканер ловит синтетический класс с подмножеством без единого
        упоминания исключённого пути и НЕ ловит класс, упоминающий
        исключённый путь в докстринге, и класс с полным набором.

        Ловит мутацию: сканер путает «докстринг непустой» с «докстринг
        упоминает конкретный исключённый путь» — тогда `_Dirty` (докстринг
        есть, но ни один исключённый путь не назван) ложно считался бы
        объяснённым.
        """
        dirty = (
            "class _Dirty(TmpRootTest):\n"
            '    """Обычная песочница для этого файла."""\n'
            "    PATCHED_ATTRS = ('ROOT', 'DB', 'TASKS')\n")
        explained = (
            "class _Explained(TmpRootTest):\n"
            '    """ROOT остаётся настоящим деревом — читает docs/."""\n'
            "    PATCHED_ATTRS = ('DB', 'TASKS')\n")
        full = (
            "class _Full(TmpRootTest):\n"
            "    PATCHED_ATTRS = ('DB', 'TASKS', 'LOGS', 'ROOT', "
            "'PROJECTS', 'TARGETS', 'ROLE_HOME', 'ROLE_CONFIG_DIR', "
            "'BACKUP_MARKER', 'WORKTREES')\n")

        entries = _own_patched_attrs_classes({"synthetic.py": dirty + explained + full})
        offenders = _unexplained_subsets(entries)

        self.assertEqual(["synthetic.py:_Dirty"], offenders)


if __name__ == "__main__":
    unittest.main()
