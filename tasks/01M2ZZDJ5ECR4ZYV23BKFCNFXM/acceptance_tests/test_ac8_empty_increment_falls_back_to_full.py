"""AC-8 — 01M2ZZDJ5ECR4ZYV23BKFCNFXM: пустой инкремент при непустых
правках — откат на полный diff от базы вердикта, названная причина и
алерт.

Источник — SPEC.md, «Критерии приёмки»:

AC-8. Инкрементальный diff пуст, а diff кодовой ветки от базы вердикта
до головы (без каталога `tasks/<id>/`) не пуст — пакет несёт полный diff
от базы вердикта; заметка под diff'ом и запись журнала «ревью-пакет
собран» несут причину «инкрементальный diff пуст при непустых правках —
показан полный»; по завершении шага сборки промпта ревьювера (не только
самой функции пакета) алерт `kind=warning` с той же причиной в тексте
остаётся открытым.

Красен до реализации: отката нет вовсе — сегодня инкрементальный diff
собирается по всему дереву, причина «инкрементальный diff пуст при
непустых правках — показан полный» не встречается ни в тексте пакета,
ни в журнале, ни в алертах, а сам сценарий (ветка после базы вердикта
несёт только merge-коммит подтяжки main) ещё и берёт другую базу —
предпоследнюю запись журнала.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402
from orchestrator import alerts  # noqa: E402

MAIN_EDIT = f"{_sandbox.MAIN_MARK}-только-подтяжка"


class EmptyIncrementFallsBackTest(_sandbox.ReviewPackagePlankSandbox):

    def setUp(self):
        super().setUp()
        # С базы вердикта у ветки нет ни одного СОБСТВЕННОГО коммита —
        # только merge-коммит подтяжки main: инкремент по правилу
        # требования 6 пуст, а diff от базы вердикта не пуст.
        self.verdict_sha = self.developer_commit(f"{_sandbox.DEV_MARK}-база\n")
        self.journal_verdict_anchor(self.verdict_sha, iteration=1)
        self.merge_sha = self.main_pull_merge(f"{MAIN_EDIT}\n")
        self.journal_fixation(self.merge_sha)
        self.journal_transition("review")
        self.journal_fixation(self.merge_sha)

    def open_warnings(self) -> list:
        return [row["message"] for row in alerts.open_alerts(self.conn, "warning")
                if row["target"] == self.TASK]

    def test_ac8_package_shows_the_full_diff_from_the_verdict_base(self):
        """Инкремент пуст, а правки с базы вердикта есть — пакет обязан
        показать полный diff от базы вердикта, а не пустой инкремент.

        Ловит мутацию: пустой результат инкремента отдаётся ревьюверу
        как есть («изменений нет») — ровно тот дефект 20.09, ради
        которого критерий и заведён: assertIn по содержимому правок
        покраснеет.
        """
        text = self.build_prompt(reviewed_iter=1)

        self.assertIn(MAIN_EDIT, text,
                      "при пустом инкременте показывается полный diff от "
                      "базы вердикта")
        self.assertIn(self.verdict_sha, _sandbox.after_diff(text),
                      "полный diff отката считается от базы вердикта")

    def test_ac8_note_and_journal_carry_the_fallback_reason(self):
        """Причина отката названа дословно и в заметке под diff'ом, и в
        записи журнала «ревью-пакет собран».

        Ловит мутацию: причина доносится только текстом пакета, а в
        журнал не попадает (или наоборот) — дефект такого класса снова
        станет невидимым по журналу, и одна из двух проверок покраснеет.
        """
        text = self.build_prompt(reviewed_iter=1)

        self.assertIn(_sandbox.FALLBACK_REASON, _sandbox.after_diff(text),
                      "заметка под diff'ом не называет причину отката")
        details = self.journal_details(_sandbox.PACKAGE_ACTION)
        self.assertTrue(details, "записи «ревью-пакет собран» нет в журнале")
        self.assertIn(_sandbox.FALLBACK_REASON, details[-1],
                      "запись журнала о сборке пакета не называет причину "
                      "отката")

    def test_ac8_warning_alert_stays_open_after_the_prompt_is_built(self):
        """Алерт `kind=warning` с той же причиной остаётся ОТКРЫТЫМ по
        завершении всего шага сборки промпта, а не только внутри функции
        пакета.

        Ловит мутацию: алерт заводится самим сборщиком пакета под
        источником «diff не собран», а шаг сборки промпта следом зовёт
        закрытие алертов того же источника — алерт гаснет в ту же
        секунду, и Оператор снова не видит дефекта.
        """
        self.build_prompt(reviewed_iter=1)

        messages = self.open_warnings()
        self.assertTrue(
            any(_sandbox.FALLBACK_REASON in message for message in messages),
            f"открытого warning с причиной отката нет: {messages}")


if __name__ == "__main__":
    unittest.main()
