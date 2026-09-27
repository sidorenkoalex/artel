"""AC-8 — 01M3HST1381E1FZCYAN2TSB1F3: каталог клона удаляется вместе с
домом роли клона и перенесённым указателем.

Источник — SPEC.md, «Критерии приёмки»:

AC-8. После прогона — в том числе после отказа AC-5 и при исключении внутри
блока клона — каталог клона удалён вместе с домом роли клона и
скопированным в него указателем; в главной копии пульта следа переноса нет.

Каталоги клона наблюдаются по факту их создания: `tempfile.mkdtemp` с
префиксом клона — единственный способ, которым `_ephemeral_clone` их
заводит (его докстринг), и перехват этого вызова даёт перечень каталогов, не
угадывая имён.

Три пути критерия названы им поимённо и разыграны по отдельности: штатный
прогон, отказ проверки входа (AC-5) и исключение, брошенное ВНУТРИ блока
клона (наблюдение планки прерывает прогон именно там).

«В главной копии пульта следа переноса нет» проверяется тем, что в ней
наблюдаемо: дом роли пульта остался тем же деревом файлов, и каталога
`Library/` в корне пульта не появилось.

Красен до реализации: указателя в доме клона сегодня не появляется, поэтому
третий метод (сверка «указателя нет, потому что удалён весь каталог клона, а
не потому что его туда и не кладут») опирается на предпосылку о том, что
указатель в клоне был — и падает на её отсутствии.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from orchestrator import config  # noqa: E402

#: Первый сегмент пути указателя — каталог, которого в корне главной копии
#: пульта после прогона быть не должно.
LIBRARY_DIR = _util.POINTER_REL.split("/")[0]


class CloneRemovedWithThePointerTest(_util.CodexClonePlankSandbox):

    def test_ac8_clone_dirs_are_gone_on_all_three_paths(self):
        """Каждый временный каталог клона удалён — и после штатного
        прогона, и после отказа проверки входа, и после исключения внутри
        блока клона.

        Ловит мутацию: перенос указателя или проверка входа вставлены в
        `_ephemeral_clone` ДО `try:` (или уборка переехала из `finally`) —
        отказ проверки входа оставлял бы на диске каталог клона вместе со
        скопированным указателем, и каждый неудачный прогон копил бы такие
        каталоги в `/tmp`.
        """
        scenarios = [
            ("штатный прогон", {"set_name": _util.SET_NAME}),
            ("отказ проверки входа",
             {"set_name": _util.SET_NAME,
              "spy": _util.RunSpy(status=_util.NOT_LOGGED_IN)}),
            ("исключение внутри блока клона",
             {"set_name": _util.SET_NAME,
              "probe": lambda: {"root": Path(config.ROOT)}}),
        ]
        for label, kwargs in scenarios:
            with self.subTest(scenario=label):
                outcome = self.run_canary(**kwargs)

                self.assertTrue(outcome.clone_dirs,
                                f"эфемерного клона не было вовсе: "
                                f"{outcome.text}")
                alive = [str(path) for path in outcome.clone_dirs
                         if path.exists()]
                self.assertEqual([], alive, "каталоги клона остались на диске")

    def test_ac8_no_trace_of_the_transfer_in_the_main_copy(self):
        """В главной копии пульта следа переноса нет: дом роли пульта —
        то же дерево файлов, каталога `Library/` в корне пульта не
        появилось.

        Ловит мутацию: указатель копируется «через» рабочее дерево пульта
        (временный файл рядом с корнем, второй экземпляр в доме роли) —
        главная копия обрастала бы следами каждого прогона, а изоляция
        канарейки v2 («ничего не течёт в `config.ROOT` пульта») перестала бы
        держаться.
        """
        before = _util.snapshot(self.pult_home)

        self.run_canary(set_name=_util.SET_NAME)

        self.assertEqual(before, _util.snapshot(self.pult_home))
        self.assertFalse((self.root / LIBRARY_DIR).exists(),
                         f"в корне главной копии появился {LIBRARY_DIR}/")

    def test_ac8_the_pointer_existed_in_the_clone_and_died_with_it(self):
        """Указатель в доме роли клона действительно был — и исчез вместе с
        каталогом клона, а не «не появлялся вовсе».

        Ловит мутацию: уборка клона переписана на выборочное удаление
        («убрать всё, кроме дома роли» — например, чтобы не трогать
        скопированный указатель) — дом роли клона с копией указателя
        Оператора оставался бы в `/tmp` после каждого прогона, то есть
        адрес связки ключей Оператора утекал бы за пределы пульта.
        """
        outcome = self.clone_probe(
            _util.SET_NAME,
            lambda: {"root": Path(config.ROOT),
                     "pointer": Path(config.ROLE_HOME) / _util.POINTER_REL,
                     "exists": (Path(config.ROLE_HOME)
                                / _util.POINTER_REL).is_file()})

        self.assertTrue(outcome.probe, "наблюдение внутри клона не снято")
        self.assertTrue(outcome.probe["exists"],
                        "предпосылка: указатель в доме роли клона был "
                        f"({outcome.probe['pointer']})")
        self.assertFalse(outcome.probe["pointer"].exists(),
                         "указатель остался на диске после прогона")
        self.assertFalse(outcome.probe["root"].exists(),
                         "каталог клона остался на диске после прогона")


if __name__ == "__main__":
    unittest.main()
