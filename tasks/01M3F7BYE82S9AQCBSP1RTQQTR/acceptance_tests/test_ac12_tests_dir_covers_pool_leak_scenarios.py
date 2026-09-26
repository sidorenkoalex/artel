"""AC-12 — 01M3F7BYE82S9AQCBSP1RTQQTR: тест в `tests/` показывает оба
сценария проверки утечки пула.

Источник — SPEC.md, «Критерии приёмки»:

AC-12. Тест в tests/ показывает: синтетический лог шага роли на Codex с
именем каталога пула в содержимом поднимает срабатывание проверки (отказ
и incident-алерт), а файл сессии Оператора `*.session.log` с тем же
именем внутри оставляет проверку зелёной.

Планка проверяет не наличие тестов, а их различающую силу: кандидаты
(тестовые методы `tests/`, чей сценарий — метод, его `setUp` и
помощники — зовёт `check_role_log_pool_leak`)
прогоняются под двумя подменёнными реализациями проверки — «как было до
правки» (читает КАЖДЫЙ `*.log`, включая записи сессий) и «слепой»
(всегда зелено, ни одного алерта). На каждой подмене обязан покраснеть
хотя бы один кандидат: первая ловит сторону сессии Оператора, вторая —
сторону лога шага.

Красен до реализации: подмена «как было до правки» сегодня совпадает с
настоящей реализацией — ни один тест `tests/` на ней не краснеет
(сценария с `*.session.log` там ещё нет), и assert о покрасневших
кандидатах падает.
"""
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import alerts, config, doctor  # noqa: E402

CHECK_NAME = "canary-pool-leak"
CHECK_FUNCTION = "check_role_log_pool_leak"


def _legacy_check(conn):
    """Проверка в том виде, в каком она жила ДО правки требования 7:
    читает каждый файл `*.log` каталога логов, не различая логи шагов
    ролей и записи сессий Оператора."""
    if not config.LOGS.is_dir():
        return doctor.Check(CHECK_NAME, "ok", "логов ролей ещё нет")
    marker = config.CANARY_POOL_DIRNAME
    leaking = []
    for path in sorted(config.LOGS.glob("*.log")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if marker in text:
            leaking.append(path.name)
    if not leaking:
        return doctor.Check(CHECK_NAME, "ok",
                            "логи ролей не упоминают каталог пула канарейки")
    for name in leaking:
        alerts.raise_alert(
            conn, None, "incident", "doctor.canary-pool-leak",
            f"лог роли {name} упоминает каталог пула канарейки ({marker})")
    return doctor.Check(CHECK_NAME, "fail",
                        f"логи ролей упоминают каталог пула: "
                        f"{', '.join(leaking)}")


def _blind_check(conn):
    """Проверка, которая не находит ничего и никогда."""
    return doctor.Check(CHECK_NAME, "ok",
                        "логи ролей не упоминают каталог пула канарейки")


@contextmanager
def _check_replaced_by(stub):
    with mock.patch.object(doctor, CHECK_FUNCTION, stub):
        yield


class TestsDirCoversPoolLeakScenariosTest(unittest.TestCase):

    def setUp(self):
        self.ids = _util.test_methods_mentioning(CHECK_FUNCTION)
        self.assertTrue(
            self.ids,
            f"в tests/ нет тестового метода, чей сценарий зовёт "
            f"{CHECK_FUNCTION} (AC-12)")
        self.outcomes = _util.run_test_methods(self.ids)
        self.assertEqual(
            [], _util.failing(self.outcomes),
            "тест(ы) tests/ про утечку пула не проходят на сегодняшнем "
            "коде: " + repr(self.outcomes))

    def bodies(self) -> str:
        return "\n".join(_util.method_source(*test_id).lower()
                         for test_id in self.ids).lower()

    def test_ac12_the_operator_session_side_is_covered_and_discriminating(self):
        """Среди тестов `tests/`, зовущих проверку, есть тест про файл
        сессии Оператора, и на реализации «читает каждый *.log» (то есть
        на состоянии до правки) хотя бы один из них краснеет.

        Ловит мутацию: сценарий сессии Оператора описан только в
        докстринге («проверка теперь их не читает»), а ассерт по-прежнему
        смотрит лог роли — тест остаётся зелёным и на старой реализации,
        и ложные срабатывания 21.09 вернутся незамеченными.
        """
        self.assertTrue(
            "session.log" in self.bodies(),
            "ни один тест tests/ про утечку пула не называет файл сессии "
            "Оператора (*.session.log) — сторона AC-12 не покрыта; "
            "проверены: " + _util.describe(self.ids))

        with _check_replaced_by(_legacy_check):
            mutated = _util.run_test_methods(_util.passing(self.outcomes))

        self.assertTrue(
            _util.failing(mutated),
            "ни один тест tests/ не покраснел на реализации, читающей "
            "каждый *.log каталога логов — проверены: "
            + _util.describe(self.ids))

    def test_ac12_the_codex_step_log_side_is_covered_and_discriminating(self):
        """Среди тех же тестов есть тест про лог шага роли на Codex, и
        на «слепой» реализации (всегда зелено, ни одного алерта) хотя бы
        один из них краснеет.

        Ловит мутацию: сужение по имени файла написано так широко, что
        под него не попадает ни один лог шага, — проверка молчит всегда,
        а набор `tests/` этого не замечает, потому что смотрит только на
        сторону сессий Оператора.
        """
        bodies = self.bodies()
        self.assertTrue(
            "codex" in bodies or "json" in bodies,
            "ни один тест tests/ про утечку пула не описывает лог шага "
            "роли на Codex (синтетический JSONL) — сторона AC-12 не покрыта")

        with _check_replaced_by(_blind_check):
            mutated = _util.run_test_methods(_util.passing(self.outcomes))

        self.assertTrue(
            _util.failing(mutated),
            "ни один тест tests/ не покраснел на проверке, которая ничего "
            "не находит, — проверены: " + _util.describe(self.ids))


if __name__ == "__main__":
    unittest.main()
