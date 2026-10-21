"""PLAN.md задачи несёт доказательство неослабления: прежние утверждения изменённых тестов и их место, таблицу трёх мутаций, трёхкратный зелёный прогон, замер дескрипторов до и после (AC-18).

Группа: разовый

Красен до реализации: PLAN.md задачи ещё нет — `artifact_text("PLAN.md")` отдаёт `None`.

PLAN.md читается из ссылки документов задачи помощником пульта
(`_pult.artifact_text`). Проверка — по составу: суть доказательства
сверяет ревьюер, тест держит, что каждая из его частей в PLAN есть.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import artifact_text  # noqa: E402

CHANGED_TESTS = (
    "test_ac1_outcome_carries_relative_assertion_location",
    "test_ac9_timeout_kills_group_not_green",
    "test_ac3_timeout_kills_group_and_failure_cleanup_is_bounded",
    "test_ac6_silent_gh_and_origin_bounded_and_noted",
)
CHANGED_FILES = (
    "test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py",
    "test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py",
    "test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py",
    "test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py",
)


class PlanProofTest(unittest.TestCase):

    def test_ac18_plan_carries_non_weakening_proof(self):
        """PLAN.md называет каждый изменённый тест с его прежними утверждениями, таблицу трёх мутаций, трёхкратный прогон каждого файла и замер дескрипторов до и после.

        Сценарий: текст PLAN.md из ссылки документов. В нём: имя каждого из
        четырёх изменённых методов и каждого из четырёх файлов; прежние
        утверждения — тексты `assertLessEqual(elapsed`,
        `assertGreaterEqual(self.silence.hits` и утверждения `two_sided`
        (`outcome.refusals`); таблица (строки с `|`), где названы три
        мутации — пары `-c`/`lowSpeed`, предел числом вместо
        `GH_TIMEOUT_SEC`, «отказ» — и исходы «красн…»; упоминание трёх
        подряд прогонов («трижды»/«3 раза»/«три прогона»/«×3»); замер
        дескрипторов («дескриптор»/«fd») с «до» и «после» и не меньше двух
        чисел рядом.

        Ловит мутацию: PLAN сдан без таблицы мутаций или без замера
        дескрипторов до починки; доказательство перечисляет только
        `project_kill_cleanup`, пропуская `two_sided` и `report_outcome`.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md нет в ссылке документов")
        low = plan.lower()
        for name in CHANGED_TESTS + CHANGED_FILES:
            self.assertIn(name, plan, f"PLAN не называет {name}")
        for text in ("assertLessEqual(elapsed", "assertGreaterEqual(self.silence.hits",
                     "outcome.refusals"):
            self.assertIn(text, plan, f"PLAN не приводит прежнее утверждение {text}")
        rows = [line for line in plan.splitlines() if line.count("|") >= 3]
        table = "\n".join(rows).lower()
        self.assertTrue(rows, "в PLAN нет таблицы")
        self.assertTrue("-c" in table or "lowspeed" in table, "таблица без мутации «пуш без -c»")
        self.assertIn("gh_timeout_sec", table, "таблица без мутации «предел числом»")
        self.assertIn("отказ", table, "таблица без мутации «срабатывание как отказ»")
        self.assertGreaterEqual(table.count("красн"), 6,
                                "таблица без исходов «до — красный, после — красный»")
        self.assertTrue(re.search(r"трижды|3 раза|три прогона|три раза|×\s*3|x3|3×", low),
                        "PLAN не называет трёхкратного прогона")
        fd_lines = [line for line in low.splitlines()
                    if ("дескриптор" in line or re.search(r"\bfd\b", line))
                    and len(re.findall(r"\d+", line)) >= 2]
        self.assertTrue(fd_lines, "PLAN без замера числа дескрипторов")
        near = "\n".join(fd_lines)
        self.assertTrue("до" in near and "после" in near,
                        f"замер дескрипторов без «до»/«после»: {fd_lines}")


if __name__ == "__main__":
    unittest.main()
