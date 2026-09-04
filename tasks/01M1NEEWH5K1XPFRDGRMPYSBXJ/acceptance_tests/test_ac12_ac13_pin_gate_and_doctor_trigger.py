"""AC-12 + AC-13 (SPEC.md), общая песочница (обе меряют одну и ту же
«свежесть» последнего зелёного прогона канарейки в мержах main —
общая константа N, буквально по тексту AC-13: «та же константа, что в
AC-12»):

AC-12. Команда обновления пина отказывает, если на целевом sha main
нет зелёного прогона канарейки не старше N мержей (N — константа);
отказ именован и указывает команду запуска канарейки.

AC-13. Doctor поднимает алерт `kind=trigger`, когда число мержей main
с момента последнего зелёного прогона канарейки достигает N.

N — `config.CANARY_PIN_STALE_MERGES` (имя — соглашение этого теста,
SPEC называет только «константа», не имя атрибута `config.py`; тест
читает значение ДИНАМИЧЕСКИ, не литералом — тот же принцип, что и у
остальных порогов `config.py`, `skills/test-authoring.md`: «Оператор
крутит константу, тест переживает поворот»).

«Зелёный прогон канарейки на sha main» сеется НАСТОЯЩИМ прогоном
`canary --k 1` в момент, когда `origin` (bare-remote этой песочницы,
`_sandbox.py::CanarySandbox.setUp`) стоит на исходном коммите
(`sha0` — тот же, что при инициализации репозитория): интеграционный
приём (сеять предпосылку РЕАЛЬНОЙ командой, не прямой записью в БД по
угаданной схеме) — тот же, каким T065 и остальные приёмочные тесты
этой задачи проверяют механику, а не свои же догадки о её внутреннем
устройстве.

Красен до реализации ОБОИХ критериев: `canary --k` падает на разборе
аргументов уже на сеющем прогоне — предпосылка «есть зелёный прогон на
sha0» не выполняется, `pin-update` тогда либо ещё не отказывает вовсе
(команды-предохранителя нет), либо отказывает по другой, не относящейся
к делу причине; `doctor` не знает атрибута `config.CANARY_PIN_STALE_MERGES`
(`AttributeError` — красный тест по отсутствию константы задачи, не по
опечатке песочницы).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox  # noqa: E402

POOL_TEMPLATES = {
    "malaya-pravka.md": "Добавь маленькую синтетическую фичу X с тестами.",
}


class PinGateAndDoctorTriggerTest(CanarySandbox):

    def setUp(self):
        super().setUp()
        self.write_pool_templates(POOL_TEMPLATES)
        from orchestrator import config
        self.N = config.CANARY_PIN_STALE_MERGES
        self.sha0 = self.origin_main_sha()
        out = self.run_canary_pool(1)
        self.assertNotIn(
            "[SystemExit]", out,
            f"сеющий прогон канарейки на sha0={self.sha0} не выполнился:\n{out}")

    def test_ac12_pin_update_refuses_once_main_outran_the_green_canary_by_n_merges(self):
        """До N мержей от `sha0` (зелёный прогон) — `pin-update` на
        текущий `origin`/main проходит; на N-м мерже — отказывает,
        сообщение называет причину (устарелость канарейки) и команду
        её перезапуска.

        Ловит мутацию: разработчик добавляет гейт, но сравнивает с
        НЕПРАВИЛЬНОЙ гранью (`>` вместо `>=`, или считает мержи от
        неверной точки отсчёта) — гейт сработает на N+1 вместо N (или
        не сработает вовсе), и `assertRaises`/сообщение по имени
        команды не найдут отказа именно там, где его ожидает SPEC.
        """
        just_under_sha = self.advance_origin_main(self.N - 1)
        out_ok = self.run_pin_update(just_under_sha)
        self.assertNotIn(
            "[SystemExit]", out_ok,
            f"pin-update отказал за {self.N - 1} мержей до N={self.N} от "
            f"зелёного прогона — гейт слишком строг:\n{out_ok}")

        at_n_sha = self.advance_origin_main(1)  # итого N мержей от sha0
        # `run_pin_update` (через CLI-диспетчер, `_sandbox.py::run_cli`)
        # глотает `SystemExit` в текст возврата — здесь же нужен сам
        # факт отказа исключением, поэтому вызываем модуль напрямую.
        from orchestrator import pin
        with self.assertRaises(SystemExit) as ctx:
            pin.cmd_pin_update(at_n_sha)
        message = str(ctx.exception).lower()
        self.assertTrue(
            "canary" in message or "канаре" in message,
            f"отказ pin-update не называет команду запуска канарейки: "
            f"{ctx.exception}")

    def test_ac13_doctor_raises_a_trigger_alert_once_n_merges_are_reached(self):
        """До N мержей от зелёного прогона — открытых триггеров про
        канарейку нет; на N-м мерже `doctor` заводит `kind=trigger`
        алерт (видимый через `alerts.open_alerts(conn, "trigger")`).

        Ловит мутацию: `doctor` считает мержи, но не заводит алерт
        (только предупреждение в stdout, как `check_root_pin`,
        `orchestrator/doctor.py`, — AC-13 прямо требует ИМЕННО
        `kind=trigger`, не просто текст) — тогда после N-го мержа
        `alerts.open_alerts(conn, "trigger")` не содержит ни одной
        новой строки про канарейку.
        """
        from orchestrator import alerts, doctor, store

        self.advance_origin_main(self.N - 1)
        conn = store.db()
        triggers_before = alerts.open_alerts(conn, "trigger")
        self.capture(doctor.cmd_doctor)
        triggers_mid = alerts.open_alerts(conn, "trigger")
        canary_triggers_mid = [a for a in triggers_mid
                               if "canary" in a["message"].lower()
                               or "канаре" in a["message"].lower()]
        self.assertEqual(
            len(canary_triggers_mid), 0,
            f"doctor поднял триггер про канарейку раньше N={self.N} мержей: "
            f"{canary_triggers_mid}")

        self.advance_origin_main(1)  # итого N мержей от зелёного прогона
        self.capture(doctor.cmd_doctor)
        triggers_after = alerts.open_alerts(conn, "trigger")
        canary_triggers_after = [a for a in triggers_after
                                 if "canary" in a["message"].lower()
                                 or "канаре" in a["message"].lower()]
        self.assertGreaterEqual(
            len(canary_triggers_after), 1,
            f"doctor не поднял kind=trigger алерт про канарейку на "
            f"N={self.N}-м мерже: открытые триггеры {triggers_after}")


if __name__ == "__main__":
    unittest.main()
