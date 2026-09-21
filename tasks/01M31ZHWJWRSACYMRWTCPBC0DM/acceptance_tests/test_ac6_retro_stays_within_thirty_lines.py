"""AC-6 — 01M31ZHWJWRSACYMRWTCPBC0DM: RETRO задачи, дошедшей до `done`,
остаётся в пределах 30 строк, и существующая проверка
`tests/test_retro.py` остаётся зелёной.

Источник — SPEC.md, «Критерии приёмки»:

AC-6. RETRO задачи, дошедшей до `done`, остаётся в пределах 30 строк —
существующая проверка `tests/test_retro.py` зелёная.

Планка гоняет ОДИН файл `tests/test_retro.py`, названный критерием
поимённо, а не весь набор `tests/`: полный прогон — предмет CI
(`.github/workflows/ci.yml`) и автогейта приёмки, и повторять его внутри
теста планки значило бы гонять его дважды под чужим таймаутом
(skills/test-authoring.md, решение Оператора 05.09; тот же приём, что у
планки 01M31ZHSA6HMH40C2JTDPQJQNZ, AC-15).

Зелёный с рождения: сегодняшний блок стоимости отводит роли одну короткую
строку, поэтому RETRO любого набора ролей в 30 строк укладывается уже
сейчас — это тест СОХРАНЕНИЯ потолка, который правка блока стоимости
(доллары + сумма + четыре вида + провайдер + модель на каждую роль) как
раз и способна пробить.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tokens  # noqa: E402
from orchestrator import retro, stack, store  # noqa: E402

MERGE_SHA = "0fedcba9" * 5

#: Потолок объёма RETRO пути `done` — число названо критерием дословно.
LINE_LIMIT = 30

RETRO_TEST_FILE = "tests/test_retro.py"

#: Запас под таймаутом ОДНОГО теста планки (`stack.PER_TEST_TIMEOUT_SEC` —
#: тем же числом её гоняет гейт приёмки): прогон обязан упасть своим
#: отказом с хвостом вывода, а не быть срезанным таймаутом снаружи.
TIMEOUT_SEC = max(30, stack.PER_TEST_TIMEOUT_SEC - 30)


class RetroLineLimitTest(_tokens.TokensSandbox):

    def setUp(self):
        super().setUp()
        # Худший реальный случай блока стоимости: КАЖДАЯ роль-агент карты
        # исполнителей отработала свои шаги с полной разбивкой, у задачи
        # есть и верхняя оценка неучтённой стоимости (отдельная строка), и
        # эскалация в журнале.
        for number, role in enumerate(_tokens.agent_roles(), start=1):
            self.charge(self.TASK, role, _tokens.DEV_USD, _tokens.DEV_TOKENS,
                        model=_tokens.DEV_MODEL, provider=_tokens.DEV_PROVIDER,
                        attempt=number)
        store.update_task(self.conn, self.TASK, spent_estimate_usd=7.0,
                          review_iters=2, accept_rejects=1)
        store.journal(self.conn, self.TASK, "fsm", "state -> escalated",
                      "исчерпаны попытки агента\nхвост лога 1\nхвост лога 2")

    def test_ac6_done_retro_of_every_agent_role_fits_thirty_lines(self):
        """RETRO задачи, у которой отработали ВСЕ роли-агенты карты
        исполнителей, не длиннее 30 строк.

        Ловит мутацию: разбивка по видам, провайдер и модель добавляются
        роли отдельными строками (`{actor}:` / `  виды: …` / `  провайдер:
        …`) — по три строки на роль вместо одной, и файл перевалит за
        потолок ровно так, как предупреждает SPEC («число строк блока
        стоимости растёт с числом ролей»).
        """
        text = retro.build_done(self.conn, self.TASK, MERGE_SHA)

        lines = text.splitlines()
        self.assertLessEqual(
            len(lines), LINE_LIMIT,
            f"RETRO пути done — {len(lines)} строк при потолке "
            f"{LINE_LIMIT}:\n{text}")


class ExistingRetroTestsStayGreenTest(unittest.TestCase):

    def test_ac6_existing_retro_test_file_stays_green(self):
        """`tests/test_retro.py` целиком проходит тем же интерпретатором,
        которым идёт сама планка.

        Ловит мутацию: блок стоимости переписан так, что прежние
        ожидания расходятся с новым форматом (например
        `test_build_done_aggregates_cost_per_actor_across_events` ждёт
        «developer: $1.50, 15 токенов», а печатается уже другое), и
        обновить их разработчик забыл — прогон вернёт ненулевой код, тест
        напечатает хвост вывода pytest.
        """
        command = [sys.executable, "-m", "pytest", RETRO_TEST_FILE,
                   "-p", "no:cacheprovider", "-q"]

        result = subprocess.run(command, cwd=_tokens.REPO_ROOT,
                                capture_output=True, text=True,
                                timeout=TIMEOUT_SEC)

        tail = (result.stdout + result.stderr)[-2000:]
        self.assertEqual(0, result.returncode,
                         f"прогон {RETRO_TEST_FILE} не зелёный:\n{tail}")


if __name__ == "__main__":
    unittest.main()
