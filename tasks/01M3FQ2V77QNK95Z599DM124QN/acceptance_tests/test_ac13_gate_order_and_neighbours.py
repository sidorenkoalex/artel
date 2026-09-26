"""AC-13 (tasks/01M3FQ2V77QNK95Z599DM124QN/SPEC.md): новый рубеж стоит на
in_dev -> verifying сразу ПОСЛЕ гейта заявки мутации и ДО гейта отработки
замечаний ревью; на диффе, задевающем оба, первым отказывает гейт заявки
мутации; четыре названных файла `tests/` остаются зелёными и не
ослабленными.

Порядок сверяется по исходному тексту `fsm_advance.in_dev` (`inspect.
getsource`), а не по журналу одного прогона: обёртки `in_dev` зовутся
каждая своим `if ...: return False`, и порядок их вызова — это и есть
порядок строк в теле обработчика; воспроизводить весь переход целиком
(PLAN.md, подтяжка main, ёмкость, зоны, лок планки, origin, прогон
планки) ради одного факта о соседстве дороже и хрупче, чем прочитать
само тело.

Красен до реализации: `_test_integrity_gate_refuses` не упомянут в теле
`fsm_advance.in_dev` и не существует как имя модуля `fsm_advance` —
`test_ac13_new_gate_stands_between_mutation_claim_and_review_rework` и
`test_ac13_both_gates_refuse_on_a_diff_tripping_both` падают на этом.
Сверка четырёх существующих файлов `tests/`
(`test_ac13_named_existing_test_files_stay_green_and_unweakened`)
зелена с рождения: она проверяет СОХРАНЕНИЕ сегодняшнего поведения — то
самое, что задача обязана не сломать.
"""
import inspect
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import REPO_ROOT, TestIntegritySandbox, pytest_run  # noqa: E402
from orchestrator import fsm_advance  # noqa: E402

NAMED_TEST_FILES = (
    "tests/test_mutation_claim_gate.py",
    "tests/test_fsm_advance_gate_smoke.py",
    "tests/test_protected_paths_gate.py",
    "tests/test_zones_gate.py",
)

# Маркеры пропуска/ожидаемого провала — те же, что перечисляет требование
# 1 (класс находки «г»): ни один из четырёх названных файлов не вправе их
# завести, иначе «остались зелёными» куплено выключением тестов.
SKIP_MARKER_RE = re.compile(
    r"@(?:unittest\.)?(?:skip|skipIf|skipUnless|expectedFailure)\b"
    r"|@pytest\.mark\.(?:skip|skipif|xfail)\b"
    r"|self\.skipTest\(|pytest\.skip\(")

# Тот же `tests/test_alpha.py`, но с ТРЕТЬИМ методом без заявки «Ловит
# мутацию» — предмет соседнего гейта заявки мутации.
ALPHA_WITH_UNCLAIMED_TEST = '''"""Фикстура базового дерева: обычный файл тестов верхнего уровня."""
import unittest


class AlphaTest(unittest.TestCase):

    def test_alpha_one(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(True)

    def test_alpha_two(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertEqual(1, 1)

    def test_alpha_three(self):
        """Докстринг без заявки мутации."""
        self.assertEqual(3, 3)
'''


class GateOrderInInDevTest(unittest.TestCase):

    def test_ac13_new_gate_stands_between_mutation_claim_and_review_rework(self):
        """В теле `fsm_advance.in_dev` вызов `_test_integrity_gate_refuses`
        стоит ПОСЛЕ вызова `_mutation_claim_gate` и ДО вызова
        `_review_rework_gate_refuses`.

        Ловит мутацию: новый рубеж поставлен ПЕРЕД гейтом заявки мутации
        (интуитивно «сначала целостность, потом заявка») — на диффе,
        задевающем оба, меняется старшинство отказов, а вместе с ним
        журнал и stdout уже существующих сценариев, которые
        `tests/test_fsm_advance_gate_smoke.py` сверяет байт-в-байт.
        """
        source = inspect.getsource(fsm_advance.in_dev)
        claim = source.find("_mutation_claim_gate")
        integrity = source.find("_test_integrity_gate_refuses")
        rework = source.find("_review_rework_gate_refuses")

        self.assertNotEqual(-1, integrity,
                            "тело in_dev не зовёт _test_integrity_gate_refuses")
        self.assertNotEqual(-1, claim, "тело in_dev не зовёт _mutation_claim_gate")
        self.assertNotEqual(-1, rework,
                            "тело in_dev не зовёт _review_rework_gate_refuses")
        self.assertLess(claim, integrity,
                        "новый рубеж обязан стоять ПОСЛЕ гейта заявки мутации")
        self.assertLess(integrity, rework,
                        "новый рубеж обязан стоять ДО гейта отработки замечаний")


class BothGatesRefuseTest(TestIntegritySandbox):

    def test_ac13_both_gates_refuse_on_a_diff_tripping_both(self):
        """Дифф задевает оба рубежа сразу: в `tests/test_alpha.py`
        появился новый тест БЕЗ заявки «Ловит мутацию» (предмет гейта
        заявки мутации) и одновременно удалён `tests/test_doomed.py`
        (предмет нового рубежа). Оба гейта обязаны отказать по
        отдельности — а первым из них, по порядку тела `in_dev`
        (сверяется тестом выше), высказывается гейт заявки мутации.

        Ловит мутацию: новый рубеж «поглощает» соседний — реализация
        переносит проверку заявки мутации внутрь общего узла сравнения
        `tests/` (соблазн: оба читают одну базу и один список файлов), и
        `_mutation_claim_gate` перестаёт отказывать самостоятельно,
        отчего его собственные тесты и снимок stdout в
        `test_fsm_advance_gate_smoke.py` теряют предмет.
        """
        self.write("tests/test_alpha.py", ALPHA_WITH_UNCLAIMED_TEST)
        self.remove("tests/test_doomed.py")
        self.commit()

        t = self.conn.execute("SELECT * FROM tasks WHERE id=?",
                              (self.TASK,)).fetchone()
        claim_refusal = fsm_advance._mutation_claim_gate(
            self.conn, self.TASK, t, self.branch)
        self.assertIsNotNone(
            claim_refusal,
            "гейт заявки мутации обязан отказать новому тесту без заявки")
        self.assertIn("гейт заявки мутации", claim_refusal.action)

        outcome = self.run_gate()
        self.assertTrue(outcome.refused,
                        f"новый рубеж обязан отказать удалению файла тестов "
                        f"на том же диффе; журнал: {outcome.journal}")


class NamedExistingTestsStayGreenTest(unittest.TestCase):

    def test_ac13_named_existing_test_files_stay_green_and_unweakened(self):
        """Четыре названных AC-13 файла `tests/` существуют, несут
        `test_file_deleted_in_head_is_skipped` (гейт заявки мутации не
        меняется, требование 8), не завели ни одного маркера пропуска и
        проходят прогоном зелёными.

        Ловит мутацию: чтобы новый рубеж «не мешал», разработчик гасит
        мешающий сценарий соседнего гейта — снимает
        `test_file_deleted_in_head_is_skipped` (SPEC «Не входит» это
        прямо запрещает) или вешает на него `@unittest.skip`; и то и
        другое здесь краснеет, хотя полный прогон CI остался бы
        зелёным.
        """
        for rel in NAMED_TEST_FILES:
            path = REPO_ROOT / rel
            self.assertTrue(path.is_file(), f"{rel} удалён — AC-13 запрещает")
            text = path.read_text(encoding="utf-8")
            marker = SKIP_MARKER_RE.search(text)
            self.assertIsNone(
                marker,
                f"{rel} завёл маркер пропуска "
                f"{marker.group(0) if marker else ''} — это ослабление "
                f"существующего теста (AC-13, ADR-0002)")

        claim_text = (REPO_ROOT / "tests/test_mutation_claim_gate.py").read_text(
            encoding="utf-8")
        self.assertIn(
            "def test_file_deleted_in_head_is_skipped", claim_text,
            "AC-13 называет этот сценарий поимённо: гейт заявки мутации "
            "сохраняет молчаливый пропуск удалённого в head файла")

        res = pytest_run(*NAMED_TEST_FILES)
        self.assertEqual(
            0, res.returncode,
            f"названные AC-13 файлы обязаны остаться зелёными:\n"
            f"{res.stdout[-3000:]}\n{res.stderr[-2000:]}")


if __name__ == "__main__":
    unittest.main()
