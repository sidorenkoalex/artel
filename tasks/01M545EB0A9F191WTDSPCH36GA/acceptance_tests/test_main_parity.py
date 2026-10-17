"""Шаг роли задачи артели и шаг провайдера Codex совпадают с main.

Группа: разовый

Зелёный с рождения: критерии AC-1 и AC-5 требуют, чтобы задача не меняла того, что шаг передаёт в запуск агента, — бриф, окружение и argv задачи артели на Claude, argv Codex для задачи артели и внешнего проекта; до реализации код ветки и есть код базы, и сверка сходится; покраснеет файл только от правки, задевшей эти шаги.

Файл провалидирован прогоном на дереве базы и на рабочей копии: оба
процесса сценария доходят до запуска агента, нормализованные бриф,
окружение и argv совпадают — и на коде ветки, и на временном стабе
реализации (меры только для задачи не артели). Мутация стаба
«`GIT_CONFIG_NOSYSTEM=1` у всех задач» красит AC-1 по окружению. Стаб
удалён.

Как сверяется: «main» — дерево базы ветки задачи (`DIFF_BASE` помощника
пульта `_pult.py`, точка расхождения с `origin/<основная ветка>`),
выгруженное `git archive` во временный каталог. Один и тот же сценарий
(`_parity_scenario.py`, лёгкая песочница переходов `tests/sandbox.py` того
же дерева, `runner.cmd_run` с подменённым `runner.spawn_agent`) запускается
отдельным процессом на дереве базы и на рабочей копии `CODE_ROOT` с
одинаковыми параметрами; сравнивается то, что шаг передал в первый запуск
агента. Перед сравнением из текста убираются значения, разные у любых двух
прогонов: временный корень песочницы, путь дерева, id задачи, случайные
граничные маркеры брифа (32 hex) и суммы sha256 (64 hex) — сумма SPEC
задачи зависит от id.

Состояние шага (`tests_writing` либо `review`) и имя внешнего проекта
выбираются модулем `random`; зерно печатается и входит в текст провала.
"""
import difflib
import io
import json
import random
import re
import string
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

# AC-7: escalate — SPEC не называет точку вызова проверки project_skills без сборки брифа (модуль, имя, аргументы, форма исхода), тест без неё не написать; варианты: А) публичная функция brief.project_skills_refusal(target: str, entry: dict) -> str | None — None нет отказа, строка — текст отказа, тот же, что входит в отказ шага; Б) иное имя/форма — назовите; В) снять AC-7 до части 2 (doctor). Дефолт при молчании — А.
#
# Остальные критерии: AC-1 — здесь и в долгоживущем файле
# tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py (там же AC-2,
# AC-3, AC-4, AC-6, AC-8); AC-5 — здесь.

SCENARIO = Path(__file__).resolve().parent / "_parity_scenario.py"
STATES = ("tests_writing", "review")
ARTEL = "artel"
ARTEL_WHITELIST = "Bash(git:*),Bash(python3:*)"
HEX32 = re.compile(r"\b[0-9a-f]{32}\b")
HEX64 = re.compile(r"\b[0-9a-f]{64}\b")


def scenario(tree: Path, params: dict) -> dict:
    """Итог сценария шага на дереве `tree`: первый вызов запуска агента."""
    proc = subprocess.run(
        [sys.executable, str(SCENARIO), str(tree),
         json.dumps(params, ensure_ascii=False)],
        cwd=str(tree), capture_output=True, text=True, timeout=100)
    lines = [line for line in proc.stdout.splitlines() if line.startswith("{")]
    if proc.returncode != 0 or not lines:
        raise AssertionError(f"сценарий на {tree} упал (rc={proc.returncode}):\n"
                             f"{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}")
    return json.loads(lines[-1])


def normalized(outcome: dict, tree: Path, value) -> str:
    result = outcome["result"]
    text = json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True)
    for raw, mark in ((result["root"], "<ROOT>"), (str(tree), "<TREE>"),
                      (result["task"], "<TASK>"),
                      (result["task"].lower(), "<task>")):
        text = text.replace(raw, mark)
    text = HEX64.sub("<SHA256>", text)
    return HEX32.sub("<HEX32>", text)


class MainParityTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="artel-main-parity-")
        cls.base_tree = Path(cls.tmp.name).resolve() / "base"
        cls.base_tree.mkdir()
        archive = subprocess.run(
            ["git", "-C", str(CODE_ROOT), "archive", "--format=tar", DIFF_BASE],
            capture_output=True, timeout=100)
        if archive.returncode != 0:
            raise AssertionError(f"git archive {DIFF_BASE} не выгружен: "
                                 f"{archive.stderr.decode(errors='replace')}")
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
            if hasattr(tarfile, "data_filter"):
                tar.extractall(cls.base_tree, filter="data")
            else:
                tar.extractall(cls.base_tree)
        cls.code_tree = Path(CODE_ROOT).resolve()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rnd = random.Random(self.seed)

    def note(self, text: str) -> str:
        return f"зерно {self.seed}, база {DIFF_BASE}. {text}"

    def pair(self, params: dict) -> tuple:
        """(итог на базе, итог на рабочей копии); оба дошли до запуска."""
        outcomes = []
        for tree in (self.base_tree, self.code_tree):
            outcome = scenario(tree, params)
            result = outcome["result"]
            self.assertFalse(outcome["errors"], self.note(
                f"{params}, дерево {tree}: сценарий упал:\n{outcome['errors']}"))
            self.assertTrue(result.get("calls"), self.note(
                f"{params}, дерево {tree}: агент не запущен: "
                f"{result.get('refusal')}\n{result.get('stdout', '')[-3000:]}"))
            outcomes.append(outcome)
        return outcomes[0], outcomes[1]

    def assert_same(self, base: dict, code: dict, key: str, why: str) -> None:
        left = normalized(base, self.base_tree, base["result"]["calls"][0][key])
        right = normalized(code, self.code_tree, code["result"]["calls"][0][key])
        if left != right:
            diff = "\n".join(list(difflib.unified_diff(
                left.splitlines(), right.splitlines(), "main", "ветка",
                lineterm="", n=1))[:80])
            self.fail(self.note(f"{why}: {key} шага расходится с main:\n{diff}"))

    def test_ac1_artel_claude_step_brief_env_argv_match_main(self):
        """Шаг задачи артели на Claude передаёт в запуск агента то же, что main.

        Сценарий: задача артели в случайном агентском состоянии, роль шага
        на провайдере Claude; сценарий шага прогнан на дереве базы ветки и
        на рабочей копии. Промпт (бриф роли), окружение и argv первого
        запуска агента после нормализации совпадают; значение
        `--allowedTools` argv рабочей копии целиком равно
        `Bash(git:*),Bash(python3:*)`.

        Ловит мутацию: меры для роли внешнего проекта задели задачу артели —
        `GIT_CONFIG_NOSYSTEM` в окружении шага артели, белый список с
        `artel.py` у всех задач, заголовок или пустой блок проектных
        скилов в брифе артели при `project_skills: []`; любое из них даёт
        расхождение нормализованного промпта, окружения или argv."""
        params = {"state": self.rnd.choice(STATES), "provider": "claude",
                  "target": ARTEL}

        base, code = self.pair(params)

        why = f"артель, Claude, {params['state']}"
        for key in ("prompt", "env", "argv"):
            self.assert_same(base, code, key, why)
        argv = code["result"]["calls"][0]["argv"]
        self.assertIn("--allowedTools", argv, self.note(f"{why}: {argv}"))
        self.assertEqual(argv[argv.index("--allowedTools") + 1],
                         ARTEL_WHITELIST, self.note(f"{why}: {argv}"))

    def test_ac5_codex_step_argv_matches_main_for_artel_and_external(self):
        """argv шага роли на Codex совпадает с main — у артели и у внешнего проекта.

        Сценарий: агентские роли шага — на провайдере Codex; задача артели
        и задача внешнего проекта (случайное имя, `project_skills: []`) в
        случайном агентском состоянии; сценарий шага прогнан на дереве базы
        ветки и на рабочей копии. argv первого запуска агента после
        нормализации совпадает в обоих случаях.

        Ловит мутацию: смена сигнатуры `command` протащила в argv Codex
        что-то от проекта задачи (флаг с проектом, белый список Claude,
        иной порядок или каталог `--add-dir`) — argv шага расходится с
        main."""
        external = "proekt" + "".join(self.rnd.choices(string.ascii_lowercase,
                                                       k=6))
        state = self.rnd.choice(STATES)
        for target in (ARTEL, external):
            with self.subTest(target=target):
                params = {"state": state, "provider": "codex",
                          "target": target}

                base, code = self.pair(params)

                why = f"Codex, проект {target}, {state}"
                argv = code["result"]["calls"][0]["argv"]
                self.assertEqual(Path(argv[0]).name, "codex",
                                 self.note(f"{why}: {argv}"))
                self.assert_same(base, code, "argv", why)


if __name__ == "__main__":
    unittest.main()
