"""Миссии ролей не требуют от роли коммита кода; миссия developer сообщает,
что незакоммиченный код worktree по итогам шага коммитит пульт.

Группа: долгоживущий
Красен до реализации: пункт 4 миссии developer в orchestrator/role_prompt.py велит «закоммить код в ветку» и ничего не говорит о коммите пультом.

Миссия собирается штатным `role_prompt.mission_brief_package` для каждой из
четырёх ролей; компоненты брифа и ревью-пакета подменены пустыми —
предмет проверки только текст миссии. Номер задачи, ветка и рабочий
каталог порождаются при каждом запуске от зерна.

Разбор текста — по фразам (разделители `.`, `,`, `;`, `:`, `(`, `)`, `—`,
перевод строки): требование коммита — фраза с повелительным «закоммить»
либо с `git add`/`git commit` без отрицания в той же фразе.
"""
import random
import re
import unittest
from unittest import mock

from orchestrator import brief, review, role_prompt

ROLES = ("analyst", "test_author", "developer", "reviewer")
CLAUSE_SPLIT = re.compile(r"[.,;:()\n—]")
COMMIT_DEMAND = re.compile(r"\bзакоммить\b|\bgit\s+(?:add|commit)\b", re.I)
NEGATION = re.compile(r"\bне\b|\bнельзя\b|\bнеобязательн", re.I)
UNCOMMITTED = re.compile(r"незакоммич|не\s+закоммич", re.I)


def _missions(seed: int) -> dict[str, str]:
    rng = random.Random(seed)
    task_id = "01M" + "".join(rng.choice("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
                              for _ in range(23))
    t = {"branch": f"task/{task_id.lower()}-fixture-{rng.randrange(1000)}",
         "title": "Фикстура миссии", "reviewed_iter": rng.randrange(3)}
    cwd = f"/tmp/fixture-cwd-{rng.randrange(10 ** 6)}"
    missions = {}
    with mock.patch.object(brief, "analyst_map_component", return_value=""), \
            mock.patch.object(brief, "test_author_answer_component",
                              return_value=None), \
            mock.patch.object(brief, "developer_brief", return_value=""), \
            mock.patch.object(review, "review_package", return_value=""), \
            mock.patch.object(review, "previous_verdict_sha", return_value=""):
        for role in ROLES:
            mission, _brief, _package = role_prompt.mission_brief_package(
                None, task_id, t, role, cwd)
            missions[role] = mission
    return missions


def _clauses(text: str) -> list[str]:
    return [c.strip() for c in CLAUSE_SPLIT.split(text) if c.strip()]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"\.(?:\s|$)|\n", text) if s.strip()]


class RoleMissionsCommitContractTest(unittest.TestCase):

    def test_ac1_no_mission_demands_git_add_or_commit(self):
        """Миссии analyst/test_author/developer/reviewer собраны штатно на
        случайных номере задачи, ветке и каталоге.

        Наблюдение: ни в одной миссии нет фразы, требующей коммита —
        повелительного «закоммить» или `git add`/`git commit` без отрицания
        в той же фразе; в миссии developer нет «закоммить код».

        Ловит мутацию: пункт 4 миссии developer сохраняет «закоммить код в
        ветку» (или добавлено «выполни git add/git commit») — фраза с
        требованием коммита без отрицания найдётся.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        missions = _missions(seed)
        self.assertNotIn("закоммить код", missions["developer"].lower(),
                         f"зерно: {seed}\n{missions['developer']}")
        for role, mission in missions.items():
            demands = [c for c in _clauses(mission)
                       if COMMIT_DEMAND.search(c) and not NEGATION.search(c)]
            self.assertEqual(demands, [],
                             f"зерно: {seed}; миссия {role} требует коммита:\n"
                             f"{mission}")

    def test_ac1_developer_mission_says_pult_commits_uncommitted_code(self):
        """Миссия developer собрана штатно на случайных входах.

        Наблюдение: в ней есть предложение, где незакоммиченный код
        («незакоммич…»/«не закоммич…») связан с пультом, коммитом
        («коммит…») и шагом («шаг…») — сообщение о том, что по итогам шага
        его коммитит пульт.

        Ловит мутацию: из пункта 4 убрано требование коммита, но сообщение
        о коммите пультом не добавлено — предложения о пульте и
        незакоммиченном коде нет.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        mission = _missions(seed)["developer"]
        found = [s for s in _sentences(mission)
                 if UNCOMMITTED.search(s) and re.search(r"пульт", s, re.I)
                 and re.search(r"коммит", s, re.I)
                 and re.search(r"шаг", s, re.I)]
        self.assertTrue(found, f"зерно: {seed}; миссия developer не сообщает, "
                               f"что незакоммиченный код коммитит пульт:\n"
                               f"{mission}")


if __name__ == "__main__":
    unittest.main()
