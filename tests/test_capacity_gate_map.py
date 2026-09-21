"""Юнит-тесты исключения `docs/codebase-map.md` из меры гейта ёмкости
(SPEC 01M31DRD81092HB69J0MAKZMGH, требование 5) — углы, не закрытые
приёмочной планкой задачи.

Планка (`tasks/01M31DRD81092HB69J0MAKZMGH/acceptance_tests/
test_ac5_ac7_capacity_gate_map.py`) разбирает pathspec поддельным git и
проверяет наблюдаемое свойство «карта в мере не участвует». Здесь —
буквальная форма вызова (`:!docs/codebase-map.md` в pathspec первой меры)
и общий узел второй цифры `_excluded_note` сам по себе: планка не
различает «карта исключена pathspec'ом» и «карта вычтена из размера после
измерения», а эти два способа расходятся на переименованиях и бинарных
файлах.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, gitcmd, review  # noqa: E402
from orchestrator.advance_gates import capacity  # noqa: E402
from orchestrator import fsm_advance, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

TASK_ID = "T001"
BRANCH = "task/t001-x"


class CapacityGateMapPathspecTest(TmpRootTest):
    """Форма вызова git: карта исключена тем же приёмом `:!`, каким
    исключены артефакты задачи."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.t = {"title": "Карта в мере гейта", "branch": BRANCH}
        self.calls = []

    def _recording_git(self, *args) -> subprocess.CompletedProcess:
        argv = list(args)
        if argv[:1] == ["diff"]:
            self.calls.append(argv)
        if argv[:2] == ["rev-parse", "--verify"]:
            return subprocess.CompletedProcess(argv, 1, "", "")
        if argv[:1] == ["merge-base"]:
            return subprocess.CompletedProcess(argv, 0, "basesha0\n", "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    def test_code_measure_excludes_the_map_by_pathspec_not_by_subtraction(self):
        """Первый (решающий) вызов `git diff` несёт в pathspec исключение
        `:!docs/codebase-map.md` рядом с `:!tasks/<id>/`.

        Ловит мутацию: карта не исключается pathspec'ом, а её объём
        вычитается из измеренного размера постфактум — на переименовании
        карты или на её бинарном представлении вычитаемое расходится с
        реальным вкладом, и потолок снова сверяется не с тем числом.
        """
        with mock.patch.object(gitcmd, "git", self._recording_git):
            fsm_advance._capacity_gate_refuses(self.conn, TASK_ID, self.t,
                                               "in_dev")

        self.assertTrue(self.calls, "гейт обязан спросить git о diff кода")
        code_call = self.calls[0]
        self.assertIn(f":!{capacity.MAP_REL}", code_call,
                      f"карта обязана быть исключена pathspec'ом: {code_call}")
        self.assertIn(f":!tasks/{TASK_ID}/", code_call,
                      f"исключение артефактов задачи обязано остаться: "
                      f"{code_call}")

    def test_map_measure_is_not_requested_when_the_code_fits_the_ceiling(self):
        """Код уложился в потолок — гейт пропускает переход, не спрашивая
        git об отдельной мере карты.

        Ловит мутацию: вторая мера считается безусловно, до сравнения с
        потолком — каждый зелёный переход платит лишним вызовом git, а
        сбой git на мере карты (который отказа не отменяет по построению)
        получает шанс уронить проход по fail-closed первой меры.
        """
        with mock.patch.object(gitcmd, "git", self._recording_git):
            refused = fsm_advance._capacity_gate_refuses(
                self.conn, TASK_ID, self.t, "in_dev")

        self.assertFalse(refused)
        map_calls = [c for c in self.calls if capacity.MAP_REL in c]
        self.assertEqual(map_calls, [],
                         f"мера карты на проходном переходе лишняя: {map_calls}")


class ExcludedNoteTest(unittest.TestCase):
    """Общий узел цифр исключённых частей `_excluded_note`."""

    @staticmethod
    def _part(diff: str, reason: str = ""):
        return lambda *a, **kw: (diff, 0, reason)

    def test_note_is_bytes_zero_or_unknown_but_never_an_invented_number(self):
        """Три исхода одной функции: байты содержимого, «0 байт» на реально
        пустом diff и «неизвестен» со словами git при сбое.

        Ловит мутацию: пустой diff измерен как байты строки-плейсхолдера
        `review.EMPTY_DIFF_TEXT` (27 байт), а сбой git — как 0 байт: обе
        подмены выдают Оператору вымышленное число вместо честного
        «нечего» и «не знаю».
        """
        body = "diff --git a/x b/x\n+" + "y" * 100
        cases = [(body, f"{len(body.encode('utf-8'))} байт"),
                 (review.EMPTY_DIFF_TEXT, "0 байт (изменений нет)")]
        for diff, expected in cases:
            with self.subTest(diff=diff[:20]):
                with mock.patch.object(capacity, "_review_git_diff_part",
                                       self._part(diff)):
                    self.assertEqual(
                        capacity._excluded_note("base", BRANCH, ("docs/",),
                                                None),
                        expected)

        failing = self._part("(не собран: fatal: bad object)",
                             "fatal: bad object")
        with mock.patch.object(capacity, "_review_git_diff_part", failing):
            note = capacity._excluded_note("base", BRANCH, ("docs/",), None)
        self.assertIn("неизвестен", note)
        self.assertIn("bad object", note)
        placeholder = len(review.EMPTY_DIFF_TEXT.encode("utf-8"))
        self.assertNotIn(f"{placeholder} байт", note)

    def test_note_pathspec_reaches_git_verbatim(self):
        """Pathspec, которым узел мерит исключённую часть, доходит до
        `review.git_diff_part` как есть — тем же кортежем.

        Ловит мутацию: узел склеивает pathspec в одну строку или
        подставляет свой — мера карты начинает считать не карту, и вторая
        цифра отказа перестаёт относиться к названному в ней пути.
        """
        seen = {}

        def part(base, branch, *flags, pathspec=(), repo=None):
            seen["pathspec"] = pathspec
            seen["repo"] = repo
            return review.EMPTY_DIFF_TEXT, 0, ""

        with mock.patch.object(capacity, "_review_git_diff_part", part):
            capacity._excluded_note("base", BRANCH, (capacity.MAP_REL,),
                                    "/tmp/clone")

        self.assertEqual(seen["pathspec"], (capacity.MAP_REL,))
        self.assertEqual(seen["repo"], "/tmp/clone")


class MapRelIdentityTest(unittest.TestCase):
    """Имя карты — то же, что у генератора и у остальных её читателей."""

    def test_map_rel_matches_the_generator_output_path(self):
        """`capacity.MAP_REL` совпадает с путём, по которому карту пишет
        `scripts/codebase_map.py`, и с записью в `config.COMMON_ZONES`.

        Ловит мутацию: в гейте заведено своё написание пути (скажем,
        `docs/codebase_map.md`) — исключение молча перестаёт срабатывать,
        и мера снова включает карту, не сломав ни одного теста формы.
        """
        from scripts import codebase_map

        self.assertEqual(capacity.MAP_REL, codebase_map.OUTPUT_PATH.as_posix())
        self.assertIn(capacity.MAP_REL, config.COMMON_ZONES)


if __name__ == "__main__":
    unittest.main()
