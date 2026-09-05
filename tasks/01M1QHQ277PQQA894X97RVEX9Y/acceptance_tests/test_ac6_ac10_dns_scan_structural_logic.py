"""AC-6 и AC-10 (tasks/01M1QHQ277PQQA894X97RVEX9Y/SPEC.md).

AC-6: «Новый структурный тест в `tests/test_invariants.py` проверяет:
ни один файл `tests/**/*.py` не содержит адреса вида
`http(s)://<DNS-имя>`, кроме `localhost`/`127.0.0.1`; допустимые
исключения перечислены именованной константой с обоснованием на
каждую строку.»
AC-10: «Структурный тест из AC-6 красный на синтетической фикстуре,
содержащей DNS-имя (доказательство, что тест действительно ловит
нарушение, а не декорация...).»

Сам структурный тест требования 3 — protected-path unified-diff-
приложение к PLAN.md (требование 3, AC-8): `tests/test_invariants.py`
на диске ветки задачи не получит этот тест никогда (Оператор применяет
дифф отдельно после `merge_gate`, тот же порядок, что ANSWER-1
`01M1KVGD18P9H5WR7VM8TGPV1T`) — поэтому здесь проверяется не САМ
защищённый файл, а СОБСТВЕННАЯ копия его логики (`_util.
find_dns_addresses`, реализующая правило AC-6 буквально), тем же
приёмом, что `_util.py::refs_snapshot`/`diff_refs` в
`tasks/01M1KVGD18P9H5WR7VM8TGPV1T/acceptance_tests/
test_ac2_invariant_check_sensitivity.py` — испытывается СОСТОЯТЕЛЬНОСТЬ
правила, а не наличие конкретного файла.

Зелёный с рождения: `_util.find_dns_addresses` — код этой же приёмочной
планки, не код задачи; его поведение не зависит от того, реализован ли
перехват сетевых git-команд, а только от того, верно ли написан сам
сканер.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _util import find_dns_addresses  # noqa: E402


class DnsAddressScanIsSoundTest(unittest.TestCase):

    def test_ac6_localhost_and_loopback_addresses_are_not_flagged(self):
        """Строки с `http://localhost:...` и `http://127.0.0.1:...` — не
        нарушение: AC-6 явно исключает оба имени из правила.

        Ловит мутацию: сканер вообще не делает исключений (флагует
        ВСЁ, включая `localhost`/`127.0.0.1`) — фикстура ниже содержит
        оба имени и ожидает пустой результат.
        """
        text = (
            'url = "http://localhost:8080/x"\n'
            'url2 = "http://127.0.0.1:9/y"\n'
        )
        self.assertEqual([], find_dns_addresses(text))

    def test_ac10_synthetic_dns_name_fixture_is_flagged(self):
        """Синтетическая фикстура с DNS-именем, отсутствующим в реальном
        репозитории, — сканер обязан её найти (доказательство ловли, не
        декорации, тем же приёмом, что и у остальных инвариантов
        `docs/invariants.md`).

        Ловит мутацию: сканер ищет только буквальный `example.invalid`
        (частный случай существующих фикстур репозитория) вместо общего
        правила «http(s)://<DNS-имя>» — синтетическое имя ниже
        намеренно другое (`ci-mirror.internal-test.example`) и не
        встречается ни в одном реальном файле репозитория.
        """
        text = 'url: https://ci-mirror.internal-test.example/repo.git\n'
        hits = find_dns_addresses(text)
        self.assertEqual(
            ["https://ci-mirror.internal-test.example/repo.git"], hits)

    def test_ac6_host_that_merely_starts_with_the_loopback_ip_is_still_flagged(self):
        """`127.0.0.1.evil.example` — хост, который лишь НАЧИНАЕТСЯ с
        `127.0.0.1`, но целиком является DNS-именем, не самим loopback,
        — обязан быть пойман, не пропущен как «похожий на локальный».

        Ловит мутацию: сравнение хоста через `.startswith("127.0.0.1")`
        вместо точного равенства всей хост-части — эта фикстура ловит
        именно такую ошибку сравнения (ложное исключение).
        """
        text = 'url = "http://127.0.0.1.evil.example/x"\n'
        hits = find_dns_addresses(text)
        self.assertEqual(["http://127.0.0.1.evil.example/x"], hits)


if __name__ == "__main__":
    unittest.main()
