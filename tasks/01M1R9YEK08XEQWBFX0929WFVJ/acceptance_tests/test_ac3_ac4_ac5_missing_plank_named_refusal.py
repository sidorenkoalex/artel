"""Красен до реализации: сегодня `_pull_main_or_escalate` не различает
«планка не найдена в источнике» (нет `acceptance_tests/` в артефактной
ветке — легитимный вырожденный случай ТОЛЬКО когда `tests_writing`
пропущена SPEC'ом) от «планка реально прогналась и упала» — оба случая
уходят в один и тот же путь `acceptance.run` над (обычно отсутствующим)
worktree-каталогом. SPEC «Критерии приёмки» AC-3/AC-4/AC-5 требуют трёх
РАЗНЫХ исходов для трёх разных комбинаций (SPEC не пропустила
tests_writing + планки нет / планка есть и красная / SPEC легитимно
пропустила tests_writing + планки нет).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AcceptancePullSandbox, RED_TEST  # noqa: E402


class Ac3MissingPlankNamedRefusalTest(AcceptancePullSandbox):

    def test_ac3_no_acceptance_tests_in_artifact_branch_refuses_named_not_escalates(self):
        """SPEC артефактной ветки требует AC-разметку (`schema_version:
        2`, без `skip_tests`) — `tests_writing` не была легитимно
        пропущена. Артефактная ветка НЕ несёт `acceptance_tests/` вовсе
        (материализация находит пусто). Переход обязан отказать
        ИМЕНОВАННЫМ отказом «планка не найдена в источнике» (SPEC
        «Критерии приёмки» AC-3, дословная формулировка) — состояние
        задачи остаётся `acceptance` (не `escalated`, не `merge_gate`).

        Ловит мутацию: код по-прежнему трактует пустой результат
        материализации как «тесты не заведены» -> зелёный проход
        (перепутано с легитимным skip AC-5) — `assertEqual(self.state(),
        "acceptance")` здесь покраснеет, увидев `"merge_gate"`. Либо код
        трактует пустой результат как красную планку и эскалирует —
        тест покраснеет, увидев `"escalated"` вместо `"acceptance"`, и
        не найдёт фразу «не найдена» в выводе/журнале.
        """
        self.commit_artifact(self.spec_requires_tests())

        out = self.approve()

        self.assertEqual(
            self.state(), "acceptance",
            f"состояние обязано остаться acceptance (отказ, не переход); "
            f"вывод:\n{out}\nжурнал: {self.journal_details()}")
        combined = (out + "\n".join(self.journal_details())).lower()
        self.assertIn(
            "планка не найдена в источнике", combined,
            f"ожидался именованный отказ «планка не найдена в источнике» "
            f"(SPEC AC-3); получено: {combined}")


class Ac4RedPlankStillEscalatesTest(AcceptancePullSandbox):

    def test_ac4_genuinely_red_plank_keeps_old_escalation_message(self):
        """Артефактная ветка НЕСЁТ `acceptance_tests/` (материализация
        находит его), но тест внутри реально красный. AC-3's именованный
        отказ «планка не найдена в источнике» НЕ имеет права подменить
        собой существующую эскалацию «приёмочные тесты красные после
        подтяжки main» (SPEC AC-4) — она остаётся только для планки,
        которая реально прогналась и упала.

        Ловит мутацию: разработчик заворачивает ЛЮБОЙ не-True исход
        прогона планки (включая настоящую красноту) в новый именованный
        отказ AC-3 — тест не найдёт здесь фразу «красные после подтяжки»
        и/или увидит состояние, отличное от `escalated`.
        """
        files = dict(self.spec_requires_tests())
        files[f"tasks/{self.TASK}/acceptance_tests/test_red.py"] = RED_TEST
        self.commit_artifact(files)

        out = self.approve()

        self.assertEqual(self.state(), "escalated")
        combined = (out + "\n".join(self.journal_details())).lower()
        self.assertIn(
            "приёмочные тесты красные после подтяжки", combined,
            f"эскалация красной планки обязана нести прежний текст; "
            f"получено: {combined}")
        self.assertNotIn(
            "планка не найдена в источнике", combined,
            "именованный отказ AC-3 не должен подменять настоящую "
            "красноту (AC-4)")


class Ac5LegitimateSkipStaysGreenTest(AcceptancePullSandbox):

    def test_ac5_skip_tests_spec_with_no_plank_passes_green(self):
        """SPEC артефактной ветки легитимно пропускает `tests_writing`
        (`skip_tests` задан) и НЕ несёт `acceptance_tests/` вовсе —
        существующий вырожденный случай (SPEC AC-5): требования 1-2 его
        не меняют, переход обязан пройти зелёным (`merge_gate`), не
        отказать именованным отказом AC-3.

        Ловит мутацию: именованный отказ AC-3 применяется БЕЗУСЛОВНО к
        любому отсутствию `acceptance_tests/`, не проверяя `skip_tests`
        SPEC'а — тест увидит `state() == "acceptance"` вместо
        `"merge_gate"`.
        """
        self.commit_artifact(self.spec_skip_tests())

        out = self.approve()

        self.assertEqual(
            self.state(), "merge_gate",
            f"легитимный skip_tests обязан пройти зелёным; вывод:\n{out}\n"
            f"журнал: {self.journal_details()}")


if __name__ == "__main__":
    unittest.main()
