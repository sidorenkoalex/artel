"""AC-6 (tasks/01M2YWRB9HWW99R57HWGP2M7MQ/SPEC.md): бриф роли analyst,
собранный после возврата AC-1, несёт раздел «Причина возврата» с дословным
текстом причины Оператора.

Бриф analyst собирает `orchestrator/brief.py::analyst_map_component` — это
и есть «бриф роли analyst» в смысле критерия: `runner.py` подаёт роли
именно её результат. Раздел ищется по `brief.RETURN_REASON_HEADER`, а не по
литералу «Причина возврата»: константа — существующий адрес раздела
(SPEC, «Материалы»), и её переименование не должно тихо обесценить планку.

Карта репозитория кладётся фикстурой во временный `config.ROOT` со свежим
`built_at_sha`: без неё сборщик полез бы сверять свежесть карты пульта и
регенерировать её (тот же приём, что `tests/test_brief.py::BriefUnitTest`).

Красен до реализации: `_RETURN_TRIGGER_STATES` (orchestrator/brief.py) не
содержит `spec_gate`, а сам возврат ещё не состоится — `_return_context`
вернёт `None`, и раздела в брифе не будет вовсе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402
from orchestrator import brief, store  # noqa: E402

# Карта со свежим `built_at_sha` — фикстура временного дерева песочницы.
MAP_FRESH = ("---\nbuilt_at_sha: aaaa000011112222333344445555666677778888\n"
             "---\n\n# Карта\n")


class AnalystBriefAfterTheSpecGateReturnTest(_sandbox.SpecGateRejectSandbox):

    def setUp(self):
        super().setUp()
        docs = self.root / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "codebase-map.md").write_text(MAP_FRESH, encoding="utf-8")

    def analyst_brief(self) -> str:
        return brief.analyst_map_component(store.db(), self.TASK)

    def test_ac6_analyst_brief_carries_the_operator_reason_verbatim(self):
        """Оператор отклонил SPEC на гейте с причиной; следующий бриф
        analyst этой задачи открывается разделом «Причина возврата», и в
        нём стоит текст Оператора дословно — аналитик переписывает SPEC,
        видя, что именно не так.

        Ловит мутацию: `spec_gate` добавлен в `_RETURN_TRIGGER_STATES` со
        стороны эскалации (ветка `prev_state == "escalated"` расширена
        вместо обычной) — `_return_context` пойдёт искать запись `state ->
        escalated`, не найдёт её и подставит в раздел `None` вместо
        причины Оператора.
        """
        out = self.reject_from("spec_gate", _sandbox.REASON)
        self.assertEqual(
            self.state(), "spec_writing",
            f"возврат AC-1 не состоялся — предпосылка AC-6 не проверена; "
            f"вывод команды: {out!r}")

        text = self.analyst_brief()

        self.assertIn(brief.RETURN_REASON_HEADER, text)
        self.assertIn(_sandbox.REASON, text)

    def test_ac6_the_section_is_absent_without_a_return(self):
        """Контроль по той же задаче: первый визит `spec_writing` (запись
        входа в журнале есть, но предшественника у неё нет — задача
        только заведена) раздела «Причина возврата» не даёт. Раздел
        появляется именно от возврата, а не оттого, что он теперь
        приклеен к каждому брифу этой роли.

        Ловит мутацию: `spec_gate` учтён не сравнением предшественника, а
        безусловной выдачей раздела для `spec_writing` (`_return_context`
        перестал возвращать `None` при `prev_state is None`) — аналитик
        получал бы раздел с пустой причиной на каждом первом заходе.
        """
        self.enter_state("spec_writing", "первый вход аналитика")

        text = self.analyst_brief()

        self.assertNotIn(brief.RETURN_REASON_HEADER, text)


if __name__ == "__main__":
    unittest.main()
