"""`guard.TEST_METHOD` считает `async def test_…` как одноимённый `def test_…` (AC-9).

Группа: долгоживущий
Красен до реализации: `guard.TEST_METHOD` заякорен на `^\\s*def` — строка `async def test_x(` в число тестовых методов не входит, и выдача по тексту с `async def` короче выдачи по тому же тексту с `def`.

Модульный тест без песочницы: свойство — разбор текста регулярным
выражением. Имена методов, отступы, пробелы после `def`, аргументы и
доля асинхронных методов — случайные при каждом запуске; зерно
печатается и входит в текст каждого провала.
"""
import random
import unittest

from scripts import guard

ALPHABET = "abcdefghijklmnopqrstuvwxyz"


class AsyncTestMethodTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def layout(self) -> list:
        """[(имя, отступ, пробел после `def`, аргументы)] — 1..5 методов
        с разными именами `test_<x>`."""
        names: list = []
        count = self.rng.randrange(1, 6)
        while len(names) < count:
            name = "test_" + "".join(self.rng.choice(ALPHABET)
                                     for _ in range(6))
            if name not in names:
                names.append(name)
        return [(name, self.rng.choice(("", "    ", "        ")),
                 self.rng.choice((" ", "  ", "\t")),
                 self.rng.choice(("self", "", "self, client", "*args")))
                for name in names]

    @staticmethod
    def source(layout: list, asynchronous: set) -> str:
        """Текст файла по `layout`: у имён из `asynchronous` — `async def`,
        у остальных — `def`; прочее одинаково."""
        lines = ["import unittest", "", ""]
        for name, indent, gap, args in layout:
            keyword = "async def" if name in asynchronous else "def"
            lines += [f"{indent}{keyword}{gap}{name}({args}):",
                      f"{indent}    assert ready()", ""]
        return "\n".join(lines) + "\n"

    def test_ac9_async_test_method_counted_like_def(self):
        """Тот же файл, где часть `def test_…` заменена на `async def test_…`, даёт `TEST_METHOD` те же имена в том же порядке.

        На восьми случайных файлах: методы `test_<x>` с отступами
        модуля, класса и вложенности, разными пробелами после `def` и
        разными аргументами; в одном тексте все объявлены `def`, в другом
        — случайная непустая часть тех же методов объявлена `async def`.
        `TEST_METHOD.findall` по обоим текстам даёт один и тот же список —
        список всех имён файла: каждое асинхронное имя входит в число
        тестовых методов, число совпадает.

        Ловит мутацию: якорь остаётся `^\\s*def` — асинхронные имена
        выпадают из выдачи, список короче; `async` допускается только без
        отступа (`^(async\\s+)?def` без `\\s*` перед `async`) — выпадают
        асинхронные методы класса.
        """
        for attempt in range(8):
            layout = self.layout()
            names = [name for name, *_rest in layout]
            asynchronous = set(self.rng.sample(
                names, self.rng.randrange(1, len(names) + 1)))
            plain = self.source(layout, set())
            mixed = self.source(layout, asynchronous)
            with self.subTest(attempt=attempt):
                self.assertEqual(names, guard.TEST_METHOD.findall(plain),
                                 f"зерно: {self.seed}; фикстура:\n{plain}")
                self.assertEqual(
                    names, guard.TEST_METHOD.findall(mixed),
                    f"зерно: {self.seed}; async-методы {sorted(asynchronous)} "
                    f"не учтены как def:\n{mixed}")


if __name__ == "__main__":
    unittest.main()
