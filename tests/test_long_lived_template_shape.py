"""Форма шаблона `long_lived` и пример пути: свойства вне долгоживущих файлов задачи 01M5AA5TS90RDJ2AFXB882WTPD.

Сверка последнего сегмента шаблона с масками `tests` — только у компонента
с правилом-меткой (команда не pytest); пример пути шаблона без `<dir>`
совпадает с прежней склейкой префикса и «<имя>.py»; комментарий над
вызовом теста — блок `/* … */` из нескольких строк.
"""
import unittest

from orchestrator import config, targets
from scripts import guard

TASK = "01ABCDEFGHJKMNPQRSTVWXYZ01"


def entry(fields: dict) -> dict:
    return {"forge": "github", "url": "file:///nonexistent/p",
            "base": config.MAIN_BRANCH, "token_slot": "p-token",
            "no_paths": [], "project_skills": [], "merge_gate": "operator",
            "components": {"app": dict(fields)}}


def pytest_fields(template: str) -> dict:
    return {"command": ["python3", "-m", "pytest"],
            "weakening_scope": ["tests/**"],
            "mutation_claim_scope": ["tests/**"],
            "tests": ["tests/check_*.py"], "long_lived": template}


class TemplateMasksOnlyForLabelledRuleTest(unittest.TestCase):

    def test_pytest_component_template_not_checked_against_masks(self):
        """Компонент на pytest с масками `tests`, не подходящими под шаблон, проходит запись: правило у него не метка.

        Ловит мутацию: сверка с масками применена к любому компоненту с
        `tests` (признак pytest-команды не проверяется) — запись отказывает
        «последний сегмент не подходит под маски tests».
        """
        targets.check("p", entry(pytest_fields("tests/test_<id>_<name>.py")))

    def test_vitest_like_component_template_checked_against_masks(self):
        """Тот же шаблон у компонента не на pytest с теми же масками — отказ записи, называющий маски.

        Ловит мутацию: признак «команда не pytest» перевёрнут — компонент
        с правилом-меткой проходит без сверки.
        """
        fields = dict(pytest_fields("tests/test_<id>_<name>.py"),
                      command=["npx", "vitest", "run"])
        with self.assertRaises(targets.TargetsError) as caught:
            targets.check("p", entry(fields))
        self.assertIn("tests/check_*.py", str(caught.exception))


class ExampleParityTest(unittest.TestCase):

    def test_example_without_dir_equals_prefix_form(self):
        """Пример пути шаблона без `<dir>`, оканчивающегося на `<name>.py`, равен прежней склейке префикса и «<имя>.py»/«*.py».

        Ловит мутацию: `<id>` подставлен в исходном регистре или `<name>`
        не заменён — пример артели расходится с прежним текстом подсказок.
        """
        for directory, template in (("tests", "test_<id>_<name>.py"),
                                    ("backend/tests", "test_<id>_<name>.py")):
            prefix = guard.long_lived_path_prefix(TASK, directory, template)
            for name in ("<имя>", "*"):
                self.assertEqual(
                    guard.long_lived_example(TASK, directory, template, name),
                    f"{prefix}{name}.py")


class MultilineBlockClaimTest(unittest.TestCase):

    def test_multiline_block_comment_claim_above_call(self):
        """Заявка во второй строке многострочного блока `/* … */` над вызовом засчитана; блок, отделённый пустой строкой, — нет.

        Ловит мутацию: из блока берётся только последняя строка перед `*/`
        — заявка во второй строке не найдена, ложный отказ; пустая строка
        не обрывает поиск — второй вызов проходит.
        """
        source = ("// Группа: долгоживущий\n"
                  "/*\n * Пояснение.\n * Ловит мутацию: сумма другая.\n"
                  " * Ещё строка.\n */\n"
                  "it('AC-1: первый', () => {});\n"
                  "/* Ловит мутацию: оторвана. */\n\n"
                  "it('AC-1: второй', () => {});\n")
        rule = guard.PlankRule(components=(guard.PlankComponent(
            "web", ("*.test.jsx",), guard.LABEL_AC, guard.MARKER_SLASH),))
        errors = guard.long_lived_errors_from_files(
            [("src/a.test.jsx", source)], TASK, rule=rule)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("тест «AC-1: второй»", errors[0])


if __name__ == "__main__":
    unittest.main()
