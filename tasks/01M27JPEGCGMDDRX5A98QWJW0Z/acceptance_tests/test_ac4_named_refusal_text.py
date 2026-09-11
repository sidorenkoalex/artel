"""AC-4 (tasks/01M27JPEGCGMDDRX5A98QWJW0Z/SPEC.md): отказы AC-2/AC-3
(гейт зон, `fsm_advance._zones_gate`) несут ДОСЛОВНО именованный текст
«защищённый путь <путь> — правит только Оператор коммитом в main;
предложи правку приложением к PLAN (unified-дифф)» с конкретным задетым
путём (или перечнем путей, если их несколько) вместо `<путь>`.

Песочница — та же лёгкая `TmpRootTest`, что `test_ac2_ac3_zones_gate_
protected_path.py`: `gitcmd.diff_base`/`gitcmd.diff_names` подменены
напрямую.

Красен до реализации: гейт зон сегодня вообще не знает о защищённых
путях — на диффе, трогающем `CLAUDE.md`/`gates.yaml`, переход либо
молча проходит (путь в `zones`), либо отказывает СВОИМ текстом «дифф
трогает файлы вне заявленных zones...», не именованным текстом AC-4:
оба теста здесь не находят ожидаемую строку в журнале и падают на
`assertTrue`.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm_advance, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class NamedRefusalTextZonesGateTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"

    def _journal_details(self) -> list:
        return [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=?", (self.task_id,))]

    def test_ac4_refusal_detail_carries_the_named_text_with_the_exact_path(self):
        """Отказ по диффу, трогающему единственный защищённый путь
        `CLAUDE.md`, несёт ДОСЛОВНО именованный текст AC-4 с этим путём
        на месте `<путь>`.

        Ловит мутацию: разработчик формулирует свой текст отказа
        («CLAUDE.md — защищённый путь, правку делает Оператор» или
        любая другая перефразировка) вместо буквального именованного
        текста AC-4 — Оператор и брифинг следующего шага developer не
        смогут узнать отказ по стандартной формулировке.
        """
        t = {"title": "Тест", "branch": "task/t001-x",
             "zones": "CLAUDE.md", "zones_extension": None}
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                               return_value=["CLAUDE.md"]):
            fsm_advance._zones_gate_refuses(
                self.conn, self.task_id, t, "task/t001-x", "PLAN\n")

        expected = ("защищённый путь CLAUDE.md — правит только Оператор "
                   "коммитом в main; предложи правку приложением к PLAN "
                   "(unified-дифф)")
        details = self._journal_details()
        self.assertTrue(any(expected in d for d in details), details)

    def test_ac4_multiple_protected_paths_are_all_named_in_the_refusal(self):
        """Дифф трогает сразу два защищённых пути (`gates.yaml`,
        `CLAUDE.md`) — отказ обязан перечислить ОБА, не только первый
        найденный.

        Ловит мутацию: код называет только первый найденный защищённый
        путь и останавливается на нём — Оператор не узнает из одного
        отказа про второй нарушенный путь.
        """
        t = {"title": "Тест", "branch": "task/t001-x",
             "zones": "gates.yaml,CLAUDE.md", "zones_extension": None}
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                               return_value=["gates.yaml", "CLAUDE.md"]):
            fsm_advance._zones_gate_refuses(
                self.conn, self.task_id, t, "task/t001-x", "PLAN\n")

        combined = " ".join(self._journal_details())
        self.assertIn("gates.yaml", combined)
        self.assertIn("CLAUDE.md", combined)


if __name__ == "__main__":
    unittest.main()
