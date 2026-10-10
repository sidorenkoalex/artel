"""Правило сетевых адресов `tests/`: проверка долгоживущих файлов и инвариант 35.

Группа: долгоживущий

Красен до реализации: `scripts/guard.py` ещё не знает признака адреса `http(s)://<DNS-имя>` — `long_lived_errors_from_files` на файле с таким адресом молчит (AC-1, AC-6, AC-7 красны); пропуск loopback и именованных исключений (AC-2, AC-5) зелен с рождения — до реализации признака нет вовсе.

Адрес считается по правилу инварианта 35: шаблон `http(s)://…`, хост
сравнивается точно (`localhost`/`127.0.0.1` пропущены, хост, лишь
начинающийся с них, — нет), именованные исключения — по паре (имя файла,
хост). Свойство проверяется через публичный вход признаков долгоживущего
файла (`guard.long_lived_errors_from_files` — тот же узел, что отказ
выхода из `tests_writing`): ошибки файла с адресом сравниваются с
ошибками того же файла, где на месте адреса — простой текст, поэтому
тест не зависит от формулировки чужих признаков. Инвариант 35 зовётся
своим классом `tests/test_invariants.py::NoNetworkAddressesInTestsTest`
над временным деревом `tests/` (подменён `config.ROOT`).

Адреса в исходнике этого файла собраны по частям (`SEP`): сам файл лежит
в `tests/` и обязан проходить и инвариант 35, и рубеж `in_dev`.
"""
import random
import re
import string
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import config
from scripts import guard
from tests import test_invariants

SEP = ":" + "//"
GROUP_LINE = "Группа" + ": " + guard.GROUP_LONG_LIVED
TLDS = ("test", "example", "org", "com", "io", "net", "invalid")
EXCEPTION_PAIRS = (("test_github_adapter.py", "github.com"),
                   ("test_ci_status.py", "api.github.com"),
                   ("test_sandbox.py", "example.invalid"),
                   ("test_sandbox.py", "127.0.0.1.evil.example"))


def url(host: str, scheme: str = "https", tail: str = "") -> str:
    return f"{scheme}{SEP}{host}{tail}"


def random_dns_host(rng: random.Random) -> str:
    labels = ["".join(rng.choice(string.ascii_lowercase)
                      for _ in range(rng.randint(2, 8)))
              for _ in range(rng.randint(1, 3))]
    return ".".join(labels + [rng.choice(TLDS)])


def random_tail(rng: random.Random) -> str:
    port = f":{rng.randint(1, 65535)}" if rng.random() < 0.5 else ""
    path = rng.choice(("", "/", "/x", "/repo.git", "/api/v1?q=1"))
    return port + path


def fixture_source(value: str, pad: int) -> tuple[str, int]:
    """(текст долгоживущего файла, номер строки со значением `value`)."""
    head = ["'''Фикстура долгоживущего файла.", "", GROUP_LINE, "'''",
            "import unittest", ""]
    head += [f"# заполнитель {i}" for i in range(pad)]
    lineno = len(head) + 1
    body = [f"ADDRESS = {value!r}", "", "",
            "class FixtureTest(unittest.TestCase):", "",
            "    def test_fixture(self):",
            "        '''Фикстурный метод.", "",
            "        Ловит мутацию: фикстура — значение пустое.",
            "        '''",
            "        self.assertTrue(ADDRESS)", ""]
    return "\n".join(head + body), lineno


def task_id(rng: random.Random) -> str:
    return "01" + "".join(rng.choice("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
                          for _ in range(24))


def address_errors(name: str, address: str, rng: random.Random
                   ) -> tuple[list[str], int, str]:
    """(ошибки, которых нет у того же файла без адреса; строка адреса; метка)."""
    label = f"tests/{name}"
    pad = rng.randint(3, 40)
    with_address, lineno = fixture_source(address, pad)
    baseline, _ = fixture_source("простой текст без адреса", pad)
    tid = task_id(rng)
    errors = guard.long_lived_errors_from_files([(label, with_address)], tid)
    base_errors = guard.long_lived_errors_from_files([(label, baseline)], tid)
    return [e for e in errors if e not in base_errors], lineno, label


def invariant_catches(name: str, address: str) -> bool:
    """Краснеет ли инвариант 35 на дереве `tests/` из одного файла `name`."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "tests").mkdir()
        text, _ = fixture_source(address, 2)
        (root / "tests" / name).write_text(text, encoding="utf-8")
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(
            test_invariants.NoNetworkAddressesInTestsTest)
        result = unittest.TestResult()
        with mock.patch.object(config, "ROOT", root):
            suite.run(result)
    return bool(result.failures or result.errors)


class NetworkAddressRuleTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def test_ac1_dns_address_refused_naming_file_and_line(self):
        """Долгоживущий файл с адресом `http(s)://<DNS-имя>` получает ошибку признака.

        Сценарий: адрес из критерия (хост `example.test`, путь `/x`) и случайные
        DNS-адреса (схема, хост, порт, путь — от зерна) кладутся строковой
        константой на случайную строку долгоживущего файла со случайным
        именем. Ошибки файла сравниваются с ошибками того же файла, где на
        месте адреса — простой текст: появляется ошибка, называющая метку
        файла и номер строки адреса.

        Ловит мутацию: признак адреса не добавлен в `long_lived_sign_hits`
        (или добавлен, но без номера строки) — новой ошибки с меткой файла
        и номером строки нет, выход из `tests_writing` пропускает файл.
        """
        cases = [url("example.test", "https", "/x")]
        cases += [url(random_dns_host(self.rng),
                      self.rng.choice(("http", "https")), random_tail(self.rng))
                  for _ in range(6)]
        for address in cases:
            name = f"test_fixture_{self.rng.randint(0, 10**6)}.py"
            with self.subTest(address=address, name=name):
                extra, lineno, label = address_errors(name, address, self.rng)
                self.assertTrue(
                    any(label in e and re.search(rf"\b{lineno}\b", e)
                        for e in extra),
                    f"зерно {self.seed}: нет ошибки адреса {address} с "
                    f"{label} и строкой {lineno}: {extra}")

    def test_ac2_loopback_address_not_refused(self):
        """Адрес на `127.0.0.1` или `localhost` не даёт ошибки признака.

        Сценарий: `http://127.0.0.1:8080`, `localhost` и случайные порты и
        пути к ним в долгоживущем файле — набор ошибок совпадает с набором
        того же файла без адреса.

        Ловит мутацию: исключённые хосты не вычитаются (или сравниваются с
        портом в хосте, `127.0.0.1:8080` != `127.0.0.1`) — у файла с
        loopback-адресом появляется лишняя ошибка.
        """
        cases = [url("127.0.0.1", "http", ":8080"), url("localhost", "http"),
                 url("localhost", "https", ":8443/x")]
        cases += [url(self.rng.choice(("127.0.0.1", "localhost")),
                      self.rng.choice(("http", "https")), random_tail(self.rng))
                  for _ in range(4)]
        for address in cases:
            with self.subTest(address=address):
                extra, _, _ = address_errors("test_fixture_loopback.py",
                                             address, self.rng)
                self.assertEqual([], extra,
                                 f"зерно {self.seed}: адрес {address}")

    def test_ac5_named_exceptions_pass(self):
        """Каждая из четырёх пар (файл, хост) исключения не даёт ошибки признака.

        Сценарий: файл с именем из пары несёт адрес с хостом той же пары
        (схема, порт и путь — от зерна): набор ошибок совпадает с набором
        того же файла без адреса.

        Ловит мутацию: именованные исключения не перенесены в правило guard
        (или ключуются полным путём `tests/<имя>`, а не именем файла) —
        файл исключения получает ошибку признака.
        """
        for name, host in EXCEPTION_PAIRS:
            address = url(host, self.rng.choice(("http", "https")),
                          random_tail(self.rng))
            with self.subTest(name=name, address=address):
                extra, _, _ = address_errors(name, address, self.rng)
                self.assertEqual([], extra,
                                 f"зерно {self.seed}: {name} / {address}")

    def test_ac6_guard_and_invariant_agree(self):
        """Функция guard и инвариант 35 одинаково ловят и пропускают каждый случай.

        Сценарий: таблица (имя файла, адрес, ожидание) — DNS-адрес,
        loopback, четыре пары исключения, хост исключения в чужом файле,
        `127.0.0.1.evil.example` и `localhost.<домен>` вне пары. Для
        каждой строки ответ guard (есть ли ошибка признака) и ответ
        инварианта (краснеет ли его класс над деревом из одного файла)
        совпадают между собой и с ожиданием.

        Ловит мутацию: guard сравнивает хост префиксом
        (`startswith("127.0.0.1")`) или ключует исключение одним хостом без
        имени файла — `127.0.0.1.evil.example` вне `test_sandbox.py` или
        `github.com` в `test_ci_status.py` пропущены guard, но пойманы
        инвариантом.
        """
        dns = random_dns_host(self.rng)
        cases = [("test_fixture_dns.py", url(dns, "https", "/x"), True),
                 ("test_fixture_lo.py", url("127.0.0.1", "http", ":8080"), False),
                 ("test_fixture_lh.py", url("localhost", "http", "/x"), False),
                 ("test_fixture_evil.py", url("127.0.0.1.evil.example", "http"),
                  True),
                 ("test_fixture_lhd.py", url("localhost." + dns, "https"), True),
                 ("test_ci_status.py", url("github.com", "https", "/o/r"), True),
                 ("test_github_adapter.py", url("api.github.com", "https"), True),
                 ("test_fixture_inv.py", url("example.invalid", "http"), True)]
        cases += [(name, url(host, "https", random_tail(self.rng)), False)
                  for name, host in EXCEPTION_PAIRS]
        for name, address, expected in cases:
            with self.subTest(name=name, address=address):
                extra, _, _ = address_errors(name, address, self.rng)
                by_guard = bool(extra)
                by_invariant = invariant_catches(name, address)
                self.assertEqual(
                    (expected, expected), (by_guard, by_invariant),
                    f"зерно {self.seed}: (ожидание, ожидание) против "
                    f"(guard, инвариант) для {name} / {address}")

    def test_ac7_guard_sees_dns_address(self):
        """Текст с DNS-адресом не проходит ни признаки guard, ни инвариант 35.

        Сценарий: случайный DNS-адрес в файле со случайным именем — guard
        возвращает непустой набор новых ошибок, а инвариант 35, который
        после приложения зовёт ту же функцию guard, краснеет над деревом
        из этого файла.

        Ловит мутацию: функция правила guard возвращает пусто на тексте с
        DNS-адресом — новых ошибок нет, инвариант 35 зеленеет на дереве с
        адресом.
        """
        for _ in range(3):
            address = url(random_dns_host(self.rng),
                          self.rng.choice(("http", "https")), random_tail(self.rng))
            name = f"test_fixture_{self.rng.randint(0, 10**6)}.py"
            with self.subTest(name=name, address=address):
                extra, _, _ = address_errors(name, address, self.rng)
                self.assertNotEqual([], extra,
                                    f"зерно {self.seed}: guard молчит на {address}")
                self.assertTrue(invariant_catches(name, address),
                                f"зерно {self.seed}: инвариант молчит на {address}")


if __name__ == "__main__":
    unittest.main()
