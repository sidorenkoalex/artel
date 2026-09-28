"""AC-10, AC-11 — вердикт всех шести мест сверки не изменился на прежних
12 записях; `guard.protected_zones` опознаёт новые пути и отсеивает
незащищённый, сохраняя прежнюю сортировку.

Источник — SPEC.md, «Критерии приёмки»:

AC-10. Вердикт на прежних 12 записях не изменился: каждое из шести мест
требования 5 считает защищёнными `gates.yaml`,
`.github/workflows/ci.yml`, `docs/adr/0001-foo.md`, `templates/SPEC.md`
и не считает защищёнными `orchestrator/store.py`, `tests/test_store.py`.

AC-11. `guard.protected_zones(["templates/SPEC.md",
"orchestrator/store.py", "conftest.py", "tests/sub/conftest.py"])`
возвращает `["conftest.py", "templates/SPEC.md",
"tests/sub/conftest.py"]` — прежний порядок сортировки, новые пути
опознаны, незащищённый отсеян.

Шесть мест спрашиваются через `_protected.place_verdicts` — там же
описано, как список путей каждого места сводится к вердикту.

Красен до реализации: `conftest.py` и `tests/sub/conftest.py` перечнем ещё не покрыты — `protected_zones` отдаёт только `["templates/SPEC.md"]`, и метод AC-11 падает на неравенстве.

Метод AC-10 в этом файле зелен с первого прогона намеренно: он держит
существующее поведение шести мест на прежних 12 записях — требование 6
запрещает его менять. Заявка на мутацию у него при этом есть (регрессия
самой этой правки) — см. его докстринг.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _protected  # noqa: E402
from scripts import guard  # noqa: E402

#: Вход и ожидаемый выход AC-11 — дословно из критерия.
AC11_ZONES = ["templates/SPEC.md", "orchestrator/store.py", "conftest.py",
              "tests/sub/conftest.py"]
AC11_EXPECTED = ["conftest.py", "templates/SPEC.md", "tests/sub/conftest.py"]


class LegacyVerdictUnchangedTest(unittest.TestCase):

    def test_ac10_all_six_places_keep_the_legacy_verdict(self):
        """Каждое из шести мест требования 5 отвечает «защищён» на
        `gates.yaml`, `.github/workflows/ci.yml`, `docs/adr/0001-foo.md`,
        `templates/SPEC.md` и «не защищён» на `orchestrator/store.py`,
        `tests/test_store.py`.

        Метод держит существующее поведение (требование 6 запрещает его
        менять), поэтому до правки разработчика зелен — но заявка у него
        есть, и она про саму эту правку.

        Ловит мутацию: общий помощник потерял префиксную формулу для
        записей БЕЗ маски — сверяет всё точным равенством либо по
        последнему компоненту пути («раз маска так, пусть и остальное
        так»). Наблюдаемое расхождение: `.github/workflows/ci.yml` и
        `docs/adr/0001-foo.md` перестают быть защищёнными во ВСЕХ шести
        местах разом — гейт зон пускает правку воркфлоу CI на `review`,
        джоб `protected-paths` её не красит, `guard.protected_zones` не
        помечает зону, — то есть задача про усиление защиты тихо снимает
        её с двух защищённых каталогов.
        """
        for path in _protected.LEGACY_PROTECTED_SAMPLES:
            verdicts = _protected.place_verdicts(path)
            for place, verdict in verdicts.items():
                with self.subTest(path=path, place=place):
                    self.assertTrue(
                        verdict, f"{place} перестало считать {path} "
                                 f"защищённым")
        for path in _protected.LEGACY_UNPROTECTED_SAMPLES:
            verdicts = _protected.place_verdicts(path)
            for place, verdict in verdicts.items():
                with self.subTest(path=path, place=place):
                    self.assertFalse(
                        verdict, f"{place} стало ложно считать {path} "
                                 f"защищённым")


class ProtectedZonesTest(unittest.TestCase):

    def test_ac11_protected_zones_recognizes_new_paths_and_sorts(self):
        """`guard.protected_zones` на смешанном списке зон возвращает три
        защищённых элемента в лексикографическом порядке, отсеяв
        `orchestrator/store.py`.

        Ловит мутацию: `protected_zones`, перейдя с `zone_lock._covered_by`
        на общего помощника, потеряла сортировку (`return [z for z in
        set(zones) if …]`). Наблюдаемое расхождение: порядок элементов
        приходит из `set` — недетерминированный между запусками, и вместо
        `["conftest.py", "templates/SPEC.md", "tests/sub/conftest.py"]`
        возвращается, например, `["tests/sub/conftest.py",
        "templates/SPEC.md", "conftest.py"]`; пометка защищённых зон в
        отказе гейта SPEC перестаёт быть воспроизводимой.
        """
        self.assertEqual(guard.protected_zones(AC11_ZONES), AC11_EXPECTED)


if __name__ == "__main__":
    unittest.main()
