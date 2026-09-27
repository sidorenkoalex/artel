"""AC-7 — 01M3HST1381E1FZCYAN2TSB1F3: дом роли пульта прогон не меняет ни
на одном пути, связку ключей не трогает.

Источник — SPEC.md, «Критерии приёмки»:

AC-7. Прогон не меняет дом роли пульта ни на одном пути (успех, отказ
требования 3, отказ требования 4): содержимое дома роли пульта до и после
команды совпадает; команда, меняющая связку ключей по умолчанию
(`security default-keychain -s`), прогоном не зовётся, и содержимое связки
ключей прогон не читает.

Три пути критерия разыгрываются по отдельности: успех (указатель есть, вход
подтверждён), отказ требования 3 (указателя в доме роли пульта нет) и отказ
требования 4 (вход домом клона не подтверждён).

«Содержимое до и после совпадает» — снимок {путь -> байты} всего дерева
дома роли пульта, а не перечень имён: перезапись указателя тем же именем и
другими байтами (именно её даёт ошибка в HOME у `security default-keychain
-s`) перечнем имён не ловится.

Обе половины второго утверждения держит один наблюдаемый факт: `security` —
единственный CLI, которым пульт способен и переписать указатель
(`default-keychain -s`), и прочитать связку (`orchestrator/keychain.py`:
`find-generic-password`). Ни одного его запуска среди перехваченных
процессов — значит ни того, ни другого не было.

Зелёный с рождения: это тест СОХРАНЕНИЯ существующего поведения — сегодня
переноса нет, дом роли пульта прогон не трогает и `security` не зовёт, и
критерий требует, чтобы так и осталось. Краснеет ровно тогда, когда
реализация переноса тронет дом роли ПУЛЬТА или позовёт `security` вместо
копии файла — то есть на том исходе, которого требование 1 избегает
выбором копии.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402

#: Флаг команды, переписывающей указатель связки ключей по умолчанию —
#: назван критерием поимённо.
DEFAULT_KEYCHAIN_SET = "default-keychain"


class PultRoleHomeUntouchedTest(_util.CodexClonePlankSandbox):

    def scenarios(self) -> list:
        """(название, приготовление, аргументы прогона) трёх путей
        критерия.

        Приготовление каждого пути засевает дом роли пульта ЗАНОВО и
        полностью, а не доверяет состоянию после предыдущего: путь «указателя
        нет» его удаляет, и молчаливое наследование этого состояния увело бы
        третий путь (вход не подтверждён) в отказ второго, оставив тест
        зелёным на не той ветке.
        """
        return [
            ("успех", self.seed_pult_role_home,
             {"set_name": _util.SET_NAME}),
            ("отказ требования 3: указателя нет",
             lambda: self.seed_pult_role_home(with_pointer=False),
             {"set_name": _util.SET_NAME}),
            ("отказ требования 4: вход не подтверждён",
             self.seed_pult_role_home,
             {"set_name": _util.SET_NAME,
              "spy": _util.RunSpy(status=_util.NOT_LOGGED_IN)}),
        ]

    def test_ac7_pult_role_home_content_is_identical_before_and_after(self):
        """На каждом из трёх путей содержимое дома роли пульта до и после
        команды совпадает байт-в-байт.

        Ловит мутацию: перенос сделан через `security default-keychain -d
        user -s <путь>` с HOME клона — ошибка в HOME вызова (или его
        наследование от процесса пульта) перепишет указатель ПУЛЬТА, и
        Оператор потеряет собственный вход, сохранив зелёный прогон.
        """
        for label, prepare, kwargs in self.scenarios():
            with self.subTest(scenario=label):
                prepare()
                before = _util.snapshot(self.pult_home)
                self.assertTrue(before, "предпосылка: дом роли пульта не пуст")

                self.run_canary(**kwargs)

                self.assertEqual(before, _util.snapshot(self.pult_home))

    def test_ac7_the_run_never_calls_the_keychain_command(self):
        """Ни на одном из трёх путей прогон не запускает `security` — ни с
        `default-keychain`, ни с чем-либо ещё.

        Ловит мутацию: путь связки ключей выясняется вызовом `security`
        (вместо чтения того же указателя, который и так копируется) —
        прогон начал бы спрашивать связку у системы, то есть читать то, что
        требование 5 запрещает читать, и зависеть от наличия `security` в
        системе.
        """
        for label, prepare, kwargs in self.scenarios():
            with self.subTest(scenario=label):
                prepare()

                outcome = self.run_canary(**kwargs)

                self.assertEqual([], outcome.spy.keychain_calls(),
                                 "прогон позвал CLI связки ключей")
                self.assertEqual(
                    [], [argv for argv in outcome.spy.calls
                         if DEFAULT_KEYCHAIN_SET in argv],
                    "прогон позвал команду смены связки по умолчанию")


if __name__ == "__main__":
    unittest.main()
