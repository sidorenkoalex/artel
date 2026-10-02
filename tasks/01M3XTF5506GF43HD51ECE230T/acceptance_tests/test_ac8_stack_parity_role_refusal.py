"""AC-8 — раздел «Паритет безопасности роли» `docs/stack.md` не подаёт
признак окружения как границу.

Раздел ищется по началу заголовка (`## Паритет безопасности роли`), до
следующего заголовка второго уровня. Проза проверяется корнями слов, а не
фразами: формулировка — дело разработчика, критерий требует смысла:
признак отсекает ошибочный вызов; процесс, сменивший и `HOME`, и
`ARTEL_ROLE`, его обходит; граница — песочница клиента роли и гейты пульта;
у Claude песочница — `permissions.deny` с перечнем того, что он реально
запрещает. «Реально запрещает» для команд пульта сверяется с курируемым
`settings.json` референса дома роли: каждая команда `artel.py`, которую
отказывает его `permissions.deny`, названа в разделе.

Группа: разовый
Красен до реализации: раздел ещё говорит, что непустой ARTEL_ROLE достаточен для отказа, строка «Отказ команд пульта из-под роли» несёт голое «да» — про ошибочный вызов, обход и permissions.deny в разделе ни слова.
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plank  # noqa: E402

STACK_MD_REL = "docs/stack.md"
PARITY_TABLE_TEST_REL = "tests/test_stack_parity_table.py"
ROLE_SETTINGS_REL = "docs/reference/role-home/claude/settings.json"
ROW_TITLE = "Отказ команд пульта из-под роли"

_SECTION = re.compile(r"^##\s+Паритет безопасности роли.*?$(.*?)(?=^##\s|\Z)",
                      re.M | re.S)
_DENIED_ARTEL = re.compile(r"^Bash\(python3 orchestrator/artel\.py (.+?):\*\)$")


def section_body() -> str:
    text = (_plank.REPO_ROOT / STACK_MD_REL).read_text(encoding="utf-8")
    match = _SECTION.search(text)
    return match.group(1) if match else ""


def row_cells(body: str) -> list | None:
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.lstrip().startswith("|") and cells and ROW_TITLE in cells[0]:
            return cells
    return None


def bare(cell: str) -> str:
    return re.sub(r"[*`_.,;:!\s]", "", cell).lower()


class StackParityRoleRefusalTest(unittest.TestCase):
    def setUp(self):
        self.body = section_body()
        self.assertTrue(self.body, f"{STACK_MD_REL}: раздел «Паритет "
                                   f"безопасности роли» не найден")
        self.lowered = self.body.lower()

    def test_ac8_row_has_no_bare_yes(self):
        """Ни одна ячейка строки «Отказ команд пульта из-под роли» не равна голому «да».

        Ловит мутацию: прозу раздела переписали, а строка таблицы осталась
        «| да | да |» — ячейка после снятия разметки равна «да».
        """
        cells = row_cells(self.body)
        self.assertIsNotNone(cells, f"строки «{ROW_TITLE}» в разделе нет")
        self.assertEqual([], [c for c in cells if bare(c) == "да"],
                         f"ячейки строки: {cells}")

    def test_ac8_section_says_marker_only_cuts_mistaken_calls(self):
        """Раздел говорит, что признак отсекает ошибочный вызов и обходится сменой HOME и ARTEL_ROLE.

        Ловит мутацию: в разделе осталась формулировка «непустой ARTEL_ROLE
        достаточен для отказа» без оговорки — нет ни корня «ошибочн», ни
        корня «обход», и тест краснеет.
        """
        self.assertIn("ошибочн", self.lowered, "нет «признак отсекает ошибочный вызов»")
        self.assertIn("обход", self.lowered, "нет «процесс роли признак обходит»")
        self.assertIn("HOME", self.body)
        self.assertIn("ARTEL_ROLE", self.body)

    def test_ac8_section_names_boundary_and_claude_deny_list(self):
        """Граница — песочница клиента роли и гейты пульта; у Claude — `permissions.deny` с перечнем.

        Каждая команда `artel.py`, отказанная `permissions.deny` курируемого
        `settings.json` референса дома роли, названа в разделе.

        Ловит мутацию: раздел упоминает `deny`-правила общими словами, не
        называя `permissions.deny` и того, что он запрещает из команд пульта
        (`init`, `doctor --restore`), — тест краснеет на отсутствующем имени.
        """
        self.assertIn("песочниц", self.lowered)
        self.assertIn("гейт", self.lowered)
        self.assertIn("границ", self.lowered)
        self.assertIn("permissions.deny", self.body)
        settings = json.loads((_plank.REPO_ROOT / ROLE_SETTINGS_REL)
                              .read_text(encoding="utf-8"))
        denied = [m.group(1) for rule in settings["permissions"]["deny"]
                  if (m := _DENIED_ARTEL.match(rule))]
        self.assertTrue(denied, f"{ROLE_SETTINGS_REL}: нет запретов команд artel.py")
        self.assertEqual([], [cmd for cmd in denied if cmd not in self.body],
                         f"команды, отказанные permissions.deny: {denied}")

    def test_ac8_parity_table_test_unchanged_and_green(self):
        """`tests/test_stack_parity_table.py` не тронут диффом задачи и проходит.

        Ловит мутацию: строку переписали без имени живой проверки `doctor` и
        без пометки «не закрыт» — сторож таблицы краснеет; либо сторож
        «поправили» под новую строку — дифф от базы задачи не пуст.
        """
        base = _plank.diff_base()
        self.assertIsNotNone(base, "git не ответил на базу диффа задачи")
        diff = subprocess.run(["git", "diff", "--stat", base, "--",
                               PARITY_TABLE_TEST_REL],
                              cwd=_plank.REPO_ROOT, capture_output=True,
                              text=True, timeout=60)
        self.assertEqual(0, diff.returncode, diff.stderr)
        self.assertEqual("", diff.stdout.strip(),
                         f"{PARITY_TABLE_TEST_REL} изменён задачей")
        res = _plank.run_pytest([PARITY_TABLE_TEST_REL])
        self.assertEqual(0, res.returncode, _plank.tail(res))


if __name__ == "__main__":
    unittest.main()
