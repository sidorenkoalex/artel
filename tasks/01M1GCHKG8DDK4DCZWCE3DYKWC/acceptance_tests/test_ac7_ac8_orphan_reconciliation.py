"""AC-7: обнаружив в журнале запись «agent run started» без терминальной
пары при мёртвом держателе lease, рекон дописывает терминальное событие
«шаг оборван смертью сессии `<id>`».

AC-8: повторное обнаружение того же самого оборванного шага не создаёт
вторую терминальную запись — на один оборванный шаг ровно одно событие
обрыва (идемпотентность).

Требование 4 SPEC оставляет выбор носителя рекона за разработчиком
(«run, auto, status или doctor»). Тест не гадает единственный
правильный вариант — он последовательно зовёт ДВА наиболее вероятных
НЕмутирующих кандидата, `doctor.check_leases` (уже владеет и строкой
`leases`, и фактом мёртвого pid — SPEC, «Материалы», прямая ссылка на
`orchestrator/doctor.py:685`) и `catalog.cmd_status` (уже обязана
показать держателя lease по AC-11), и проверяет результат после обоих:
рекон, реализованный в ЛЮБОМ из них, делает тест зелёным. `run`/`auto`
не задействованы — это мутирующие команды текущей задачи, требующие
реального запуска агента (SPEC явно не называет их предпочтительным
местом, а `doctor`/`status` — единственные, для которых сценарий
воспроизводим без побочных эффектов запуска процесса-агента).

Красный до реализации: сегодня ни `doctor.check_leases`, ни `catalog.
cmd_status` не читают журнал задачи вовсе — осиротевший «agent run
started» остаётся висеть без пары бесконечно.
"""
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, doctor, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTaskTest, capture, dead_pid  # noqa: E402

HOLDER_SESSION = "sess-holder-orphaned"


def _terminal_orphan_events(steps) -> list:
    return [s for s in steps
           if "оборван" in (s["action"] or "") + (s["detail"] or "")
           and HOLDER_SESSION in (s["action"] or "") + (s["detail"] or "")]


class OrphanReconciliationTest(LeaseTaskTest):

    def setUp(self):
        super().setUp()
        # Держатель lease мёртв на ЭТОМ host — предпосылка рекона (SPEC
        # требование 4: "...при мёртвом держателе lease").
        self.insert_lease(self.TASK, HOLDER_SESSION, dead_pid(),
                          socket.gethostname(), store.now())
        # «agent run started» без терминальной пары — шаг начался и
        # оборвался вместе с процессом держателя, ни одно из финальных
        # событий runner.py ("agent run finished"/"FAILED"/"TIMEOUT"/
        # "SKIPPED") в журнал так и не попало.
        self.insert_step(self.TASK, "developer", "agent run started",
                         "попытка 1/3, лог: /dev/null")

    def _reconcile(self):
        doctor.check_leases(store.db())
        capture(catalog.cmd_status)

    def test_ac7_orphaned_step_gets_a_terminal_event_naming_the_dead_session(self):
        """Журнал несёт «agent run started» без терминальной пары, а
        держатель lease мёртв на этом host: один прогон рекона
        (`doctor.check_leases` либо `catalog.cmd_status`) обязан
        дописать терминальное событие обрыва, называющее мёртвую сессию.

        Ловит мутацию: рекон ищет осиротевший шаг сравнением ПОСЛЕДНЕГО
        события журнала с литералом «agent run started» вместо поиска
        любого такого события без терминальной пары ГДЕ УГОДНО в
        журнале — если между стартовавшим и оборвавшимся шагом уже
        появилось другое событие (например, «lease перехвачен» от
        последующей сессии), эта упрощённая проверка молча пропустит
        реальный обрыв.
        """
        self._reconcile()

        events = _terminal_orphan_events(self.steps())
        self.assertTrue(
            events,
            f"осиротевший шаг («agent run started» без терминальной "
            f"пары при мёртвом держателе lease {HOLDER_SESSION}) не "
            f"получил терминальное событие обрыва (AC-7): "
            f"{self.steps()}")

    def test_ac8_repeated_reconciliation_does_not_duplicate_the_terminal_event(self):
        """Тот же осиротевший шаг, что и в предыдущем тесте, но рекон
        прогоняется трижды подряд: терминальное событие обрыва должно
        появиться ровно один раз, не по одному на каждый прогон.

        Ловит мутацию: разработчик реализует идемпотентность проверкой
        временного окна («не дублировать, если такое же событие уже
        было в последние N секунд») вместо явной проверки «терминальная
        запись для ЭТОГО оборванного шага уже существует» — рекон,
        вызванный трижды подряд БЕЗ задержки между вызовами (как в этом
        тесте), при таймер-основанной защите может случайно не
        задедуплицировать вовсе или, наоборот, задедуплицировать по
        неверному признаку, если между прогонами появится другой
        осиротевший шаг с тем же временным окном.
        """
        self._reconcile()
        self._reconcile()
        self._reconcile()

        events = _terminal_orphan_events(self.steps())
        self.assertTrue(events, f"обрыв так и не получил терминального "
                        f"события даже после нескольких проходов рекона "
                        f"(AC-7 — предпосылка AC-8): {self.steps()}")
        self.assertEqual(
            len(events), 1,
            f"повторное обнаружение того же оборванного шага создало "
            f"больше одного терминального события (AC-8, "
            f"идемпотентность): {events}")


if __name__ == "__main__":
    unittest.main()
