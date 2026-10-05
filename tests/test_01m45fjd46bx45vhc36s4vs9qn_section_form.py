"""Форма раздела SPEC «Меняемое поведение» в CLI `scripts/guard.py` (AC-1,
AC-2 — первая половина; вторая, отказ `advance` из `spec_writing`, — в
соседнем долгоживущем файле сценариев смены поведения).

Группа: долгоживущий

Красен до реализации: guard форму раздела не проверяет — SPEC с негодной
строкой раздела проходит с кодом 0 и выводом «GUARD: ок». Годные SPEC
(`test_ac1_*`) зелёны с рождения: они держат то, что guard уже делает, —
годный раздел и его отсутствие не дают нарушений.

Сценарий: SPEC-файл во временном каталоге, `python3 scripts/guard.py
<SPEC.md>` отдельным процессом из корня репозитория — тот вызов, которым
analyst проверяет SPEC перед сдачей. Имена файла, класса и метода,
литералы «было → стало» и номера требований — из `random`; зерно
печатается и входит в текст каждого провала.
"""
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GUARD = REPO / "scripts" / "guard.py"
OK_OUTPUT = "GUARD: ок (1 файлов)\n"
REQUIREMENTS = 6

SPEC_TEXT = """---
task: T001
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/
budget_usd: 30
---

# SPEC: фикстура формы раздела

## Контекст

Фикстура.

## Требования

{requirements}

## Критерии приёмки

AC-1. Фикстурный критерий.
{section}
## Не входит

Ничего.
"""


def word(rng: random.Random, length: int = 6) -> str:
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                   for _ in range(length))


class SectionFormTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.path = f"tests/test_{word(self.rng)}.py"
        self.cls = f"{word(self.rng).capitalize()}Test"

    def note(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"

    def method(self) -> str:
        return f"test_{word(self.rng)}"

    def pair(self) -> str:
        old = self.rng.choice((repr(self.rng.randrange(100)),
                               repr(word(self.rng, 4))))
        new = self.rng.choice((repr(self.rng.randrange(100, 200)),
                               repr(word(self.rng, 5))))
        return f"`{old}` → `{new}`"

    def line(self, method: str, pairs: int = 1, req=None, path=None,
             qualified=None) -> str:
        """Годная строка раздела; параметры подменяют её части."""
        name = qualified or f"{path or self.path}::{self.cls}::{method}"
        text = "; ".join(self.pair() for _ in range(pairs))
        number = self.rng.randrange(1, REQUIREMENTS + 1) if req is None else req
        return f"- `{name}`: {text} (требование {number})"

    def guard(self, section) -> tuple:
        """(код возврата, вывод) guard на SPEC с разделом `section`
        (`None` — раздела нет)."""
        body = "" if section is None else (
            "\n## Меняемое поведение\n\nСмены ожидания фикстуры.\n\n"
            + "\n".join(section) + "\n")
        requirements = "\n".join(f"{n}. Требование номер {n}."
                                 for n in range(1, REQUIREMENTS + 1))
        spec = self.dir / "SPEC.md"
        spec.write_text(SPEC_TEXT.format(requirements=requirements,
                                         section=body), encoding="utf-8")
        res = subprocess.run([sys.executable, str(GUARD), str(spec)],
                             cwd=REPO, capture_output=True, text=True,
                             timeout=120)
        return res.returncode, res.stdout + res.stderr

    def test_ac1_valid_section_one_and_two_pairs_passes(self):
        """Годный раздел — строки с одной и с двумя парами, свободный текст — проходит без нарушений.

        Ловит мутацию: разбор пар по `; ` не сделан и вторая пара читается
        как часть первой — строка с двумя парами становится нарушением;
        строка без `- ` (свободный текст раздела) считается негодной
        строкой — код 1.
        """
        section = [self.line(self.method(), 1), self.line(self.method(), 2),
                   "Свободный текст раздела без маркера списка."]
        code, out = self.guard(section)
        self.assertEqual((code, out), (0, OK_OUTPUT), self.note(out))

    def test_ac1_spec_without_section_output_unchanged(self):
        """SPEC без раздела — тот же вывод, что до задачи: код 0 и «GUARD: ок (1 файлов)».

        Ловит мутацию: отсутствие раздела считается нарушением формы или
        печатает новое предупреждение — код или вывод иные.
        """
        code, out = self.guard(None)
        self.assertEqual((code, out), (0, OK_OUTPUT), self.note(out))

    def assert_violation(self, section: list, named: str) -> None:
        code, out = self.guard(section)
        context = self.note(f"раздел:\n{chr(10).join(section)}\nвывод:\n{out}")
        self.assertNotEqual(code, 0, context)
        self.assertIn(named, out, context)

    def test_ac2_path_outside_tests_is_violation(self):
        """Путь метода не под `tests/` — ненулевой код, нарушение называет строку.

        Ловит мутацию: путь не проверяется на префикс `tests/` — код 0.
        """
        path = f"scripts/test_{word(self.rng)}.py"
        method = self.method()
        self.assert_violation([self.line(self.method()),
                               self.line(method, path=path)], path)

    def test_ac2_name_without_class_is_violation(self):
        """Имя `путь::метод` без класса — ненулевой код, нарушение называет строку.

        Ловит мутацию: квалифицированное имя проверяется только на `::`
        после пути — имя без класса проходит с кодом 0.
        """
        method = self.method()
        self.assert_violation([self.line(self.method()),
                               self.line(method, qualified=f"{self.path}::{method}")],
                              method)

    def test_ac2_empty_old_side_is_violation(self):
        """Пустое «было» — ненулевой код, нарушение называет строку.

        Ловит мутацию: пустая сторона в обратных кавычках принимается за
        значение — код 0.
        """
        method = self.method()
        bad = f"- `{self.path}::{self.cls}::{method}`: `` → `{self.rng.randrange(9)}` (требование 1)"
        self.assert_violation([self.line(self.method()), bad], method)

    def test_ac2_empty_new_side_is_violation(self):
        """Пустое «стало» — ненулевой код, нарушение называет строку.

        Ловит мутацию: проверяется непустота только левой стороны пары —
        код 0.
        """
        method = self.method()
        bad = f"- `{self.path}::{self.cls}::{method}`: `{self.rng.randrange(9)}` → `` (требование 1)"
        self.assert_violation([self.line(self.method()), bad], method)

    def test_ac2_missing_requirement_reference_is_violation(self):
        """Нет «(требование N)» — ненулевой код, нарушение называет строку.

        Ловит мутацию: ссылка на требование необязательна в разборе
        строки — код 0.
        """
        method = self.method()
        bad = self.line(method).rsplit(" (требование", 1)[0]
        self.assert_violation([self.line(self.method()), bad], method)

    def test_ac2_requirement_number_absent_is_violation(self):
        """Номер N, которого нет в «Требования», — ненулевой код, нарушение называет строку.

        Ловит мутацию: номер требования не сверяется с разделом
        «Требования» — код 0.
        """
        method = self.method()
        number = REQUIREMENTS + self.rng.randrange(1, 50)
        self.assert_violation([self.line(self.method()),
                               self.line(method, req=number)], method)

    def test_ac2_repeated_method_is_violation(self):
        """Один и тот же метод назван дважды — ненулевой код, нарушение называет его.

        Ловит мутацию: повтор метода не отслеживается — код 0.
        """
        method = self.method()
        self.assert_violation([self.line(method), self.line(self.method()),
                               self.line(method)], method)


if __name__ == "__main__":
    unittest.main()
