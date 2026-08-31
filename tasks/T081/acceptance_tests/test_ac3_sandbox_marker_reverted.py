"""AC-3 (tasks/T081/SPEC.md): `tasks/T075/acceptance_tests/_sandbox.py`
содержит маркер `# AC-2: escalate — критерий сформулирован противоречиво,
тест не пишется` естественной строкой (без конкатенации литерала), и
полный набор тестов репозитория остаётся зелёным.

Красен до реализации: `_sandbox.py` сейчас собирает маркер конкатенацией
`"# AC-2: esca" + "late — ..."` (временный обход T075, коммит 7cb7e25) —
натуральная строка-маркер в исходнике отсутствует, а обходной код ещё на
месте.
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

SANDBOX_PATH = (REPO_ROOT / "tasks" / "T075" / "acceptance_tests"
                / "_sandbox.py")

NATURAL_MARKER = re.compile(
    r"^# AC-2: escalate — критерий сформулирован противоречиво, "
    r"тест не пишется\s*$", re.M)


class SandboxMarkerRevertedTest(unittest.TestCase):

    def test_ac3_marker_is_a_natural_one_line_string(self):
        content = SANDBOX_PATH.read_text(encoding="utf-8")

        self.assertRegex(
            content, NATURAL_MARKER,
            "_sandbox.py обязан нести маркер '# AC-2: escalate — ...' "
            "естественной строкой (SPEC T081, AC-3)")

    def test_ac3_concatenation_workaround_is_gone(self):
        content = SANDBOX_PATH.read_text(encoding="utf-8")

        self.assertNotIn(
            'esca" + "late', content,
            "конкатенация литерала обхода T075 (коммит 7cb7e25) обязана "
            "быть развёрнута обратно к естественной записи (SPEC T081, "
            "AC-3, требование 2)")


# AC-3: skip — вторая половина критерия («полный набор тестов
# репозитория остаётся зелёным») уже исполняется штатным CI-гейтом
# (.github/workflows/ci.yml, джоб python, `unittest discover -s tests
# -v`) на каждый коммит ветки задачи и требуется merge_gate
# (orchestrator/fsm.py, cmd_approve при state == "merge_gate") — тот же
# довод, что
# tasks/T064/acceptance_tests/test_ac4_existing_checks_not_weakened.py и
# tasks/T053/acceptance_tests/test_ac7_full_suite_regression.py.
# Дублирующий здесь subprocess-прогон всего набора tests/ ловил бы
# окружение машины, а не дефект задачи, и не даёт новой гарантии сверх
# штатного гейта. Первая половина критерия (маркер естественной строкой,
# без конкатенации) покрыта тестами выше.
