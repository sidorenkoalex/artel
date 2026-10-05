"""Юнит-тесты `orchestrator/project_profile.py` и правила имени
долгоживущего файла по профилю в `scripts/guard.py` (SPEC
01M45FJVGQT1K0P8HDEXZX6HS7, требования 1-2) — свойства, не покрытые
долгоживущими файлами задачи: семантика масок вне значений артели, команда
профиля не на Python, шаблон имени, отличный от артельного.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import project_profile, stack  # noqa: E402
from scripts import guard  # noqa: E402

TASK = "01M45FJVGQT1K0P8HDEXZX6HS7"


def _profile(**overrides) -> project_profile.Profile:
    values = {"command": ["python3", "-m", "pytest"],
              "long_lived_dir": "tests",
              "long_lived_name": "test_<id>_<name>.py",
              "weakening_scope": ["tests/**/*.py"],
              "mutation_claim_scope": ["tests/test_*.py"]}
    values.update(overrides)
    return project_profile.Profile.from_values(values)


class MaskMatchesTest(unittest.TestCase):

    def test_single_star_stays_inside_one_segment(self):
        """`*` — любые символы внутри одного сегмента пути, через `/` не
        переходит.

        Ловит мутацию: `*` переведён в `.*` — `src/a/b.js` подойдёт под
        `src/*.js`.
        """
        self.assertTrue(project_profile.mask_matches("src/*.js", "src/a.js"))
        self.assertFalse(project_profile.mask_matches("src/*.js", "src/a/b.js"))
        self.assertTrue(project_profile.mask_matches("spec/*_spec.rb",
                                                     "spec/user_spec.rb"))

    def test_double_star_in_the_middle_spans_zero_or_more_segments(self):
        """`**` в середине маски — любое число сегментов, включая ноль.

        Ловит мутацию: `**` в середине требует хотя бы один сегмент —
        `pkg/x_test.go` выпадет из `pkg/**/x_test.go`.
        """
        mask = "pkg/**/x_test.go"
        self.assertTrue(project_profile.mask_matches(mask, "pkg/x_test.go"))
        self.assertTrue(project_profile.mask_matches(mask, "pkg/a/b/x_test.go"))
        self.assertFalse(project_profile.mask_matches(mask, "lib/x_test.go"))

    def test_trailing_double_star_takes_everything_below(self):
        """Хвостовой `**` — всё под каталогом, но не соседний каталог с тем
        же префиксом имени.

        Ловит мутацию: маска превращена в проверку префикса строки —
        `testsuite/a.py` подойдёт под `tests/**`.
        """
        self.assertTrue(project_profile.mask_matches("tests/**", "tests/a/b.py"))
        self.assertFalse(project_profile.mask_matches("tests/**",
                                                      "testsuite/a.py"))

    def test_regex_characters_in_mask_are_literal(self):
        """Точка и прочие символы регулярных выражений в маске — буквальные.

        Ловит мутацию: сегмент маски не экранирован — `testsXpy` подойдёт
        под `tests.py`.
        """
        self.assertTrue(project_profile.mask_matches("tests.py", "tests.py"))
        self.assertFalse(project_profile.mask_matches("tests.py", "testsXpy"))


class ProfileValuesTest(unittest.TestCase):

    def test_non_python_command_passes_as_is(self):
        """Команда профиля, начинающаяся не с `python3`, идёт как есть: на
        интерпретатор пульта заменяется только `python3`.

        Ловит мутацию: первый элемент команды заменяется интерпретатором
        venv безусловно — `npx jest` превратится в `<python> jest`.
        """
        with mock.patch.object(stack, "pytest_python_executable",
                               return_value="/venv/bin/python"):
            self.assertEqual(_profile(command=["npx", "jest"]).pytest_command(),
                             ["npx", "jest"])
            self.assertEqual(_profile().pytest_command(),
                             ["/venv/bin/python", "-m", "pytest"])

    def test_scopes_come_from_their_own_fields(self):
        """Область неослабления и область заявки мутации — каждая из своего
        подполя профиля.

        Ловит мутацию: заявка мутации сверяется с `weakening_scope` —
        `spec/helpers/x.rb` попадёт в область заявки.
        """
        profile = _profile(weakening_scope=["spec/**/*.rb"],
                           mutation_claim_scope=["spec/*_spec.rb"])
        self.assertTrue(profile.in_weakening_scope("spec/helpers/x.rb"))
        self.assertFalse(profile.in_mutation_claim_scope("spec/helpers/x.rb"))
        self.assertTrue(profile.in_mutation_claim_scope("spec/user_spec.rb"))
        self.assertFalse(profile.in_weakening_scope(None))


class LongLivedTemplateTest(unittest.TestCase):

    def test_prefix_and_path_follow_custom_dir_and_template(self):
        """Префикс долгоживущего файла — `<каталог>/` и часть шаблона до
        `<name>` с подставленным id; признак пути — весь шаблон, включая
        хвост после `<name>`.

        Ловит мутацию: хвост шаблона после `<name>` не сверяется (зашит
        `.py` артели) — `spec/<id>__user_spec.py` сойдёт за файл шаблона
        `<id>__<name>_spec.rb`.
        """
        profile = _profile(long_lived_dir="spec",
                           long_lived_name="<id>__<name>_spec.rb")
        task = TASK.lower()
        self.assertEqual(profile.long_lived_prefix(TASK), f"spec/{task}__")
        self.assertTrue(profile.is_long_lived(TASK, f"spec/{task}__user_spec.rb"))
        self.assertFalse(profile.is_long_lived(TASK, f"spec/{task}__user_spec.py"))
        self.assertFalse(profile.is_long_lived(TASK, f"spec/{task}___spec.rb"))
        self.assertFalse(guard.is_long_lived_test_path(
            TASK, f"spec/{task}__user_spec.rb"))


if __name__ == "__main__":
    unittest.main()
