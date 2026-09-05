"""AC-3 (tasks/01M1QHQ277PQQA894X97RVEX9Y/SPEC.md): «Адреса target'ов в
`tests/test_coldstart.py`, `tests/test_git_fixation.py`, `tests/
test_branch_freshness_gate.py` заменены на заведомо локальные и быстро
отказывающие (`file:///nonexistent/...` либо `http://127.0.0.1:9/...`).»

Красен до реализации: все три файла сегодня несут `url: https://
example.invalid/...` в своих YAML-фикстурах target'ов (`tests/
test_coldstart.py:118,126`, `tests/test_git_fixation.py:53,67,188`,
`tests/test_branch_freshness_gate.py:497`) — сканер находит их и
ассерт `assertEqual({}, offenders)` падает на непустом словаре.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _util import find_dns_addresses  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]

TARGET_FILES = (
    "tests/test_coldstart.py",
    "tests/test_git_fixation.py",
    "tests/test_branch_freshness_gate.py",
)


class FixtureAddressesAreLocalTest(unittest.TestCase):

    def test_ac3_named_fixture_files_have_no_dns_style_target_addresses(self):
        """Ни один из трёх названных файлов не содержит адреса вида
        `http(s)://<DNS-имя>` (`example.invalid` и любой другой) — все
        target-адреса заменены на локальные и быстро отказывающие.

        Ловит мутацию: разработчик заменил адрес только в ОДНОМ из трёх
        файлов, или только в ОДНОМ месте внутри файла (например, в
        `TARGETS_YAML`, но не во втором прямом вызове `gitcmd.in_repo`
        того же файла) — сканер проходит по каждому файлу отдельно и
        накапливает ВСЕ найденные нарушения в один словарь, попадающий
        в сообщение ассерта; частичная правка оставит непустую запись.
        """
        offenders = {}
        for rel in TARGET_FILES:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            hits = find_dns_addresses(text)
            if hits:
                offenders[rel] = hits
        self.assertEqual(
            {}, offenders,
            f"фикстурные DNS-адреса ещё не заменены на локальные: {offenders}")


if __name__ == "__main__":
    unittest.main()
