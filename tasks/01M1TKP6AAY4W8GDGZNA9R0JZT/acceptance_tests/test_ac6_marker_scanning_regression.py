"""AC-6 (SPEC.md, требование 3): разбор маркеров планки `# AC-n:
manual|skip` и «Красен до реализации»/«Зелёный с рождения»
(`scripts/guard.py::scan_acceptance_tests`/`scan_redness_markers`) не
меняется этой задачей — `scripts/guard.py` даже не входит в зону
(`zones:` SPEC.md не называет `scripts/`), переход раннера на pytest
(требования 1, 2) физически не может задеть статический текстовый
разбор, не исполняющий содержимое файлов.

Зелёный с рождения: `guard.py` не входит в зону задачи и не правится ни
одним из требований SPEC — регресс-тест фиксирует его СЕГОДНЯШНЕЕ
поведение на конкретной синтетической планке и обязан оставаться
зелёным и до, и после реализации требований 1/2/4/6/8 (иначе сам факт
разработки этой задачи случайно задел бы файл вне заявленной зоны).

Образцы планки (`MIXED_PLANK`/`NO_MARKER_PLANK`) — в `_util.py`, НЕ
буквальным текстом здесь: они несут настоящий синтаксис пометки критерия
(решётка, номер, вид, тире, причина — см. `AC_MARKER` в guard.py), и
guard сканирует разметку любого `test_*.py` на диске текстом, без
разбора «это код или строковый литерал-фикстура» — будь этот текст
здесь, guard читал бы его как настоящую разметку ЭТОЙ задачи и искажал
бы трассируемость AC-2/AC-3 (см. докстринг
`_util.py`)."""
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT))

from scripts import guard  # noqa: E402
from _util import MIXED_PLANK, NO_MARKER_PLANK  # noqa: E402


class MarkerScanningRegressionTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

    def write_plank(self, content: str, name: str = "test_ac.py") -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def test_ac6_scan_acceptance_tests_reads_test_and_markers_unchanged(self):
        """На планке с одним тестом AC-1 и пометками manual/skip для AC-2/
        AC-3 — `scan_acceptance_tests` находит тест AC-1 и обе пометки с
        правильным видом и причиной, ровно как до перехода на pytest
        (guard.py статически читает текст файла, прогон не участвует).

        Ловит мутацию: любая правка `scripts/guard.py` вне зоны этой
        задачи (например, «заодно поправили формат» при переносе
        документации по pytest) меняет разбор AC_MARKER/TEST_AC —
        `assertEqual` на конкретный набор ниже откажет.
        """
        self.write_plank(MIXED_PLANK)
        tested, markers = guard.scan_acceptance_tests(self.tdir)

        self.assertEqual(tested, {1})
        self.assertEqual(markers, {
            2: ("manual", "Оператор проверяет глазами на приёмке"),
            3: ("skip", "временно не тестируется, обоснование в PLAN.md"),
        })

    def test_ac6_scan_redness_markers_unchanged(self):
        """Планка с корректным маркером красноты в докстринге модуля —
        `scan_redness_markers` не выдаёт ошибок; планка БЕЗ маркера —
        выдаёт ровно одну ошибку по имени файла.

        Ловит мутацию: правка `scripts/guard.py` (вне зоны) меняет
        регулярку `REDNESS_MARKER` (например, требует другую пунктуацию)
        — `assertEqual([], ...)` на планке с уже принятым форматом
        маркера откажет.
        """
        self.write_plank(MIXED_PLANK, name="test_ok.py")
        self.assertEqual(guard.scan_redness_markers(self.tdir), [])

        self.write_plank(NO_MARKER_PLANK, name="test_missing_marker.py")
        errors = guard.scan_redness_markers(self.tdir)
        matching = [e for e in errors if "test_missing_marker.py" in e]
        self.assertEqual(len(matching), 1, errors)


if __name__ == "__main__":
    unittest.main()
