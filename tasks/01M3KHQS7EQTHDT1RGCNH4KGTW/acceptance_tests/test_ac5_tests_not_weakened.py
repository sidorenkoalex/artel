"""Приёмочные тесты 01M3KHQS7EQTHDT1RGCNH4KGTW — AC-5 (SPEC.md).

Критерий состоит из трёх утверждений; два проверяются здесь, третье —
уже существующим узлом пульта:

1. «тест, чей сценарий требует немедленной остановки `auto` на занятой
   зоне без флага, подменяет `config.AUTO_WAIT_ZONE_DEFAULT` на `False` в
   самом сценарии» — статическая сверка файлов `tests/`. Признак такого
   сценария — обращение тестового метода к `config.AUTO_STOP_ZONE_WAIT`:
   немедленная остановка наблюдается ИМЕННО по этой причине (её же
   называет AC-2), и назвать её, не упомянув имя, нельзя.
2. «число тестовых методов в изменённых файлах не уменьшилось и
   пропусков в них не появилось» — сверка изменённых файлов `tests/` с
   точкой расхождения ветки задачи с главной веткой. База — `gitcmd.
   diff_base` (`origin/<main>`, если ref заведён), разбор методов и
   маркеров пропуска — `scripts/guard.py`: «что считается тестовым
   методом» здесь и на гейте решает один код.
3. «полный набор `tests/` зелёный» в планку не переписывается: его
   гоняет сам автогейт приёмки (`orchestrator/fsm_autogate.py:254` ->
   `acceptance.full_suite` -> `pytest tests`) и CI ветки. Прогон планки
   идёт с потолком в 120 секунд на файл (`acceptance._pytest_command`) —
   полный набор в него не укладывается, а его дубль внутри планки
   раздваивал бы вердикт о зелени набора.

Зелёный с рождения: до правки разработчика ни один файл `tests/` от
главной ветки не отличается (перечень изменённых пуст), и ни один
тестовый метод `tests/` не обращается к `config.AUTO_STOP_ZONE_WAIT`
(проверено `grep` по дереву 28.09). Оба теста сторожат саму правку —
содержательными они становятся ровно тогда, когда разработчик трогает
`tests/`.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, gitcmd  # noqa: E402
from scripts import guard  # noqa: E402

#: Корень дерева кода под проверкой — тот же, от которого пульт гоняет
#: `tests/` (`orchestrator/config.py::ROOT`).
REPO_ROOT = Path(config.ROOT).resolve()
TESTS_DIR = "tests"

SETTING = "AUTO_WAIT_ZONE_DEFAULT"
IMMEDIATE_STOP_MARKER = "AUTO_STOP_ZONE_WAIT"


def _base_ref() -> str:
    """Точка расхождения ветки задачи с главной веткой тем же узлом,
    каким её считает пульт (`gitcmd.diff_base`). Пустая строка — git не
    ответил."""
    return gitcmd.diff_base(gitcmd.current_branch() or "HEAD") or ""


def _text_at(ref: str, rel: str):
    """Текст файла `rel` в дереве `ref`; `None` — файла там нет."""
    return gitcmd.show(ref, rel)[0]


def _text_on_disk(rel: str):
    path = REPO_ROOT / rel
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _tests_files_on_disk() -> list:
    return sorted(p.relative_to(REPO_ROOT).as_posix()
                  for p in (REPO_ROOT / TESTS_DIR).rglob("*.py"))


def _changed_tests_files(ref: str) -> list:
    """Пути `tests/**/*.py`, чей текст на диске отличается от текста в
    дереве `ref` (в том числе добавленные и удалённые)."""
    base = [p for p in (gitcmd.ls_tree_files(ref, TESTS_DIR) or [])
            if p.endswith(".py")]
    return [rel for rel in sorted(set(base) | set(_tests_files_on_disk()))
            if _text_at(ref, rel) != _text_on_disk(rel)]


def _patches_setting_off(node: ast.AST) -> bool:
    """`True` — поддерево `node` подменяет настройку значением `False`:
    вызов, среди аргументов которого есть и литерал с именем настройки
    (`mock.patch.object(config, "AUTO_WAIT_ZONE_DEFAULT", False)`,
    `mock.patch("orchestrator.config.AUTO_WAIT_ZONE_DEFAULT", False)`), и
    литерал `False`."""
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        args = [a for a in sub.args if isinstance(a, ast.Constant)]
        named = any(isinstance(a.value, str) and SETTING in a.value
                    for a in args)
        off = any(a.value is False for a in args)
        if named and off:
            return True
    return False


def _immediate_stop_scenarios_without_patch(rel: str, source: str) -> list:
    """Имена тестовых методов файла, чей сценарий требует немедленной
    остановки `auto` на занятой зоне (обращается к
    `config.AUTO_STOP_ZONE_WAIT`), но ни сам метод, ни его класс —
    носитель `setUp` и помощников сценария — настройку в `False` не
    подменяют."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    # (метод, область сценария): у метода класса область — весь класс
    # (`setUp` и помощники подменяют настройку так же законно, как и сам
    # метод), у функции уровня модуля — она сама.
    functions = (ast.FunctionDef, ast.AsyncFunctionDef)
    scopes = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            scopes += [(sub, node) for sub in node.body
                       if isinstance(sub, functions)]
        elif isinstance(node, functions):
            scopes.append((node, node))
    found = []
    for node, scope in scopes:
        if not node.name.startswith("test_"):
            continue
        segment = ast.get_source_segment(source, node) or ""
        if IMMEDIATE_STOP_MARKER not in segment:
            continue
        if _patches_setting_off(scope):
            continue
        found.append(f"{rel}::{node.name}")
    return found


class Ac5ImmediateStopScenariosPatchTheSettingTest(unittest.TestCase):

    def test_ac5_immediate_stop_scenarios_patch_the_default_off(self):
        """Ни один тест `tests/` не опирается на прежнее значение
        настройки неявно: сценарий, который требует немедленной остановки
        `auto` на занятой зоне без флага (обращается к
        `config.AUTO_STOP_ZONE_WAIT`), подменяет
        `config.AUTO_WAIT_ZONE_DEFAULT` на `False` сам.

        Ловит мутацию: разработчик оставляет (или дописывает) в `tests/`
        сценарий немедленной остановки, полагаясь на значение из
        `orchestrator/config.py`, — тест зелен ровно до следующего
        поворота этой крутилки Оператором, после чего чужая правка красит
        исправную ветку. Сканирование называет файл и метод.
        """
        offenders = []
        for rel in _tests_files_on_disk():
            source = _text_on_disk(rel)
            if source is None:
                continue
            offenders += _immediate_stop_scenarios_without_patch(rel, source)

        self.assertEqual(
            offenders, [],
            f"сценарии немедленной остановки `auto` на занятой зоне не "
            f"подменяют config.{SETTING} = False в самом сценарии: "
            f"{offenders}")


class Ac5ChangedTestsNotWeakenedTest(unittest.TestCase):

    def test_ac5_changed_tests_keep_methods_and_gain_no_skips(self):
        """Для каждого файла `tests/`, чей текст отличается от текста в
        точке расхождения с главной веткой: тестовых методов не меньше,
        чем было, и ни одного НОВОГО маркера пропуска (`@skip`,
        `skipTest`, `expectedFailure`) относительно базы.

        Ловит мутацию: сценарий, мешающий включению настройки, вместо
        подмены `config.AUTO_WAIT_ZONE_DEFAULT` выключается `@unittest.
        skip` либо вырезается целиком — набор `tests/` зеленеет, а
        свойство, которое этот метод сторожил, больше никем не
        проверяется; сверка с базой называет исчезнувшие имена.
        """
        base = _base_ref()
        self.assertTrue(
            base, "git не ответил на запрос точки расхождения ветки задачи "
                  "с главной веткой — сверять изменённые файлы не с чем")

        for rel in _changed_tests_files(base):
            with self.subTest(file=rel):
                base_source = _text_at(base, rel)
                head_source = _text_on_disk(rel)
                before = guard.qualified_test_methods(base_source)
                after = guard.qualified_test_methods(head_source)

                self.assertGreaterEqual(
                    len(after), len(before),
                    f"{rel}: было {len(before)} тестовых методов, стало "
                    f"{len(after)}; исчезли: "
                    f"{sorted(set(before) - set(after))}")

                skips_before = guard.test_skip_markers(base_source)
                new_skips = {
                    name: sorted(markers - skips_before.get(name, set()))
                    for name, markers
                    in guard.test_skip_markers(head_source).items()
                    if markers - skips_before.get(name, set())}
                self.assertEqual(
                    new_skips, {},
                    f"{rel}: в изменённом файле появились пропуски: "
                    f"{new_skips}")


if __name__ == "__main__":
    unittest.main()
