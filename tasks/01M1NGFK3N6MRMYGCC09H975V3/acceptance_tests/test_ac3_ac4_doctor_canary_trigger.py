"""AC-3, AC-4 (tasks/01M1NGFK3N6MRMYGCC09H975V3/SPEC.md): `doctor`
поднимает алерт `kind=trigger` ровно когда число мержей main с
последнего зелёного прогона канарейки достигает `config.
CANARY_MAX_MERGES_SINCE_GREEN`, и не поднимает его, пока порог не
достигнут.

ANSWER-1 п.3 (Оператор): `doctor` считает возраст ЛОКАЛЬНО (`git
rev-list --count --merges S..T` в `config.ROOT`, T — локальная ветка main,
без обращения к сети — инвариант 35), алерт `kind=trigger, source=canary`
не дублируется, пока открыт (`store.open_alert_exists`); пустой журнал
(ни одного зелёного прогона) — тоже триггер, отдельным текстом «канарейка
ни разу не прогонялась» — вырожденный случай того же порога («возраст»
относительно отсутствующего прогона всегда «достиг» его).

Красен до реализации: `config.CANARY_MAX_MERGES_SINCE_GREEN` не
существует (`AttributeError` в фикстуре/тесте) — `doctor.all_checks`
сегодня не знает о журнале канарейки вовсе, ни один открытый алерт
`source=canary` не появится ни в одном из трёх сценариев.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import alerts, config, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import CanaryPinSandbox  # noqa: E402


def _canary_trigger_alerts(conn) -> list:
    return [a for a in alerts.open_alerts(conn, "trigger")
           if a["source"] == "canary"]


class DoctorCanaryTriggerTest(CanaryPinSandbox):

    def test_ac3_doctor_raises_trigger_alert_when_merges_since_green_reaches_n(self):
        """Зелёный прогон записан ровно `config.
        CANARY_MAX_MERGES_SINCE_GREEN` мержей назад (возраст == N, ровно
        порог, «достигает») — `doctor` поднимает алерт `kind=trigger`,
        `source=canary`.

        Ловит мутацию: сравнение возраста с порогом через строгое `>`
        вместо `>=` (off-by-one) — граничный возраст N ложно не считался
        бы «достигшим».
        """
        stale_sha = self.root_head_sha()
        self.insert_run(stale_sha, "green")
        self.merge_commit(count=config.CANARY_MAX_MERGES_SINCE_GREEN)

        self.all_checks()

        found = _canary_trigger_alerts(store.db())
        self.assertTrue(found, "ожидался триггер kind=trigger, source=canary")

    def test_ac3_doctor_raises_trigger_alert_when_canary_never_ran(self):
        """Журнал канарейки пуст — вырожденный случай того же порога:
        `doctor` поднимает триггер с текстом «канарейка ни разу не
        прогонялась» (ANSWER-1 п.3).

        Ловит мутацию: проверка ищет ПОСЛЕДНИЙ прогон напрямую (например,
        `MAX(created_at)` без проверки на пустой результат) и падает или
        молчит на пустой таблице, вместо трактовки пустого журнала как
        «порог всегда достигнут».
        """
        self.all_checks()

        found = _canary_trigger_alerts(store.db())
        self.assertTrue(
            any("ни разу не прогонялась" in (a["message"] or "") for a in found),
            [dict(a) for a in found])

    def test_ac4_doctor_does_not_raise_trigger_alert_when_merges_since_green_below_n(self):
        """Зелёный прогон записан на единицу МЕНЬШЕ порога (`config.
        CANARY_MAX_MERGES_SINCE_GREEN - 1` мержей назад) — `doctor` не
        поднимает триггер `source=canary`.

        Ловит мутацию: порог сравнивается нестрого в другую сторону
        (`>=` там, где по духу AC-4 нужно именно «меньше N — не триггер»)
        — возраст N-1 ложно тоже считался бы достигшим порога.
        """
        stale_sha = self.root_head_sha()
        self.insert_run(stale_sha, "green")
        self.merge_commit(count=config.CANARY_MAX_MERGES_SINCE_GREEN - 1)

        self.all_checks()

        found = _canary_trigger_alerts(store.db())
        self.assertFalse(found, [dict(a) for a in found])


if __name__ == "__main__":
    import unittest
    unittest.main()
