"""AC-12 (tasks/01M3FQ2V77QNK95Z599DM124QN/SPEC.md): тот же узел на гейте
мержа — находка без мандата переводит задачу в `escalated` с тем же
текстом отказа, что на переходе in_dev -> verifying; молчание git на базе
сравнения гейт мержа не останавливает (fail-open).

Красен до реализации: узла сравнения нет вовсе, `_cmd_approve_merge_gate`
сегодня знает только о защищённых путях в диффе — ветка с удалённым
файлом тестов проходит гейт мержа и доходит до `done`, задача не
эскалирует (проверено прогоном: исход `("done",)`).

Вторая половина AC-12 (`test_ac12_silent_diff_base_does_not_stop_the_
merge_gate`) зелена с рождения и обязана такой остаться: сегодня рубежа
нет и он не останавливает мерж просто потому, что его нет, — после
реализации он не останавливает мерж уже осознанно, fail-open требования
7. Тест сохранения поведения, а не работы; он краснеет ровно на
мутации «fail-closed перенесён на гейт мержа дословно с перехода», что
проверено стабом.
"""
import sys
import unittest
from contextlib import suppress
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import MergeGateSandbox, REFUSAL_ACTION  # noqa: E402
from orchestrator import gitcmd  # noqa: E402


class MergeGateTestIntegrityTest(MergeGateSandbox):

    def setUp(self):
        super().setUp()
        self.remove("tests/test_doomed.py")
        self.commit()

    def test_ac12_finding_without_mandate_escalates_on_merge_gate(self):
        """`approve` из `merge_gate` на ветке, удаляющей файл тестов без
        мандата Оператора: задача обязана уйти в `escalated`, а detail
        эскалации — нести тот же текст, что отказ на переходе (путь
        удалённого файла и сам факт удаления).

        Ловит мутацию: узел сравнения подключён только к `in_dev ->
        verifying` — ветка, дошедшая до гейта мержа другим маршрутом
        (ручной `advance` Оператора, повторный заход после эскалации,
        подтяжка main, добавившая удаление уже после `verifying`),
        сливается в main без единого слова, и ручная сверка удалённых
        тестов, которую задача снимает с Оператора, оказывается снята
        впустую.
        """
        outcome = self.approve()

        self.assertNotEqual(
            ("done",), outcome.result,
            f"merge не имеет права завершиться при находке неослабления; "
            f"журнал: {outcome.journal}")
        self.assertEqual("escalated", outcome.state, outcome.journal)
        merged_detail = "\n".join(detail for _, detail in outcome.steps)
        self.assertIn("tests/test_doomed.py", merged_detail, outcome.journal)
        self.assertIn("удалён", merged_detail, outcome.journal)

    def test_ac12_silent_diff_base_does_not_stop_the_merge_gate(self):
        """git молчит на определении базы сравнения: гейт мержа НЕ
        останавливает задачу этим рубежом — ни отказа с его именем, ни
        эскалации по нему (fail-open, требование 7), хотя тот же дифф в
        рабочем git эскалировал бы (сценарий выше).

        Ловит мутацию: fail-closed перенесён на гейт мержа дословно из
        обёртки перехода — сломанный git начинает останавливать мерж
        там, где состояние уже не тронуто, соседний рубеж защищённых
        путей ведёт себя ровно наоборот, а тот же дифф уже проходил
        fail-closed рубеж на in_dev -> verifying.
        """
        with mock.patch.object(gitcmd, "diff_base", return_value=None), \
             suppress(SystemExit):
            # SystemExit подавлен намеренно: предмет утверждения — только
            # поведение НОВОГО рубежа; сломанный `diff_base` вправе
            # уронить любой узел НИЖЕ по маршруту мержа, и это не делает
            # находку неослабления причиной остановки.
            self.approve()

        steps = self.steps()
        journal = "\n".join(f"{action}: {detail}" for action, detail in steps)
        self.assertNotIn(
            REFUSAL_ACTION, [action for action, _ in steps],
            f"на молчащем git гейт неослабления тестов на мерже не "
            f"высказывается вовсе (AC-12); журнал: {journal}")
        self.assertNotIn(
            "tests/test_doomed.py", journal,
            f"находка не собрана — базы сравнения нет; называть её гейту "
            f"мержа нечем (AC-12); журнал: {journal}")


if __name__ == "__main__":
    unittest.main()
