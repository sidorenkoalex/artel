"""Приёмочный тест T096 — AC-7 (tasks/T096/SPEC.md, «Критерии приёмки»).

AC-7: Любые правки `orchestrator/report.py` в диффе (если есть)
ограничены классом «цвет/отступ» — значениями CSS-токенов, цветов,
паддингов и размеров шрифта внутри существующих правил `_STYLE`; ни
одна функция рендера, HTML-структура, добавленный или удалённый
CSS-класс/селектор не меняется. Расхождение, требующее такого
структурного изменения, в `orchestrator/report.py` не применяется —
только описано в `docs/design-system.md` как задача вне объёма.

Механическая, не семантическая проверка (в духе
`tasks/T083/acceptance_tests/test_ac4_prod_code_unchanged.py`): unittest
не умеет судить, «цвет» или «отступ» именно поменялся внутри правила
CSS — но умеет проверить структурный костяк AC-7 дословно:
- весь код Python вне литерала `_STYLE` (функции рендера, HTML-сборка)
  побайтово идентичен merge-base;
- внутри `_STYLE` не появился и не исчез ни один CSS-селектор/класс;
- внутри каждого сохранившегося селектора не появилось и не исчезло ни
  одно CSS-свойство (имя объявления) — то есть правки, если они есть,
  могут менять только ЗНАЧЕНИЯ существующих объявлений (цвет/токен/
  отступ/размер шрифта), что и требует AC-7.

Зелёный с рождения: на ветке задачи `orchestrator/report.py` пока не
менялся вовсе (нет коммитов разработчика) — оба под-теста проходят
вырожденно (файл идентичен себе). Тест краснеет, если будущий коммит
добавит/удалит селектор, добавит/удалит CSS-свойство внутри правила или
тронет код вне `_STYLE`.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402

REPORT_PATH_REL = "orchestrator/report.py"

STYLE_RE = re.compile(r'_STYLE = """(.*?)"""', re.DOTALL)
RULE_RE = re.compile(r'([^{}]+)\{([^{}]*)\}')


def _git(*args):
    res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                         capture_output=True, text=True, check=True)
    return res.stdout


def _extract_style_block(source: str) -> tuple:
    """Возвращает (текст_вне_STYLE, содержимое_STYLE)."""
    m = STYLE_RE.search(source)
    if not m:
        return source, None
    outside = source[:m.start()] + source[m.end():]
    return outside, m.group(1)


def _parse_rules(style_text: str) -> dict:
    """selector(strip) -> set(имена CSS-свойств внутри правила)."""
    rules = {}
    for selector, body in RULE_RE.findall(style_text):
        selector = selector.strip()
        props = set()
        for decl in body.split(";"):
            decl = decl.strip()
            if not decl:
                continue
            name = decl.split(":", 1)[0].strip()
            if name:
                props.add(name)
        rules[selector] = props
    return rules


class Ac7ReportPyCosmeticOnlyTest(unittest.TestCase):

    def setUp(self):
        branch = _git("rev-parse", "--abbrev-ref", "HEAD").strip()
        if branch == config.MAIN_BRANCH:
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = _git("merge-base", config.MAIN_BRANCH, branch).strip()

        old_source = _git("show", f"{merge_base}:{REPORT_PATH_REL}")
        new_path = REPO_ROOT / REPORT_PATH_REL
        new_source = new_path.read_text(encoding="utf-8")

        self.old_outside, self.old_style = _extract_style_block(old_source)
        self.new_outside, self.new_style = _extract_style_block(new_source)

        self.assertIsNotNone(
            self.old_style,
            "merge-base orchestrator/report.py не содержит `_STYLE = "
            '"""..."""` — тест не может извлечь границы стиля')

    def test_ac7_code_outside_style_block_is_unchanged(self):
        self.assertIsNotNone(
            self.new_style,
            "orchestrator/report.py в ветке больше не содержит "
            '`_STYLE = """..."""` литерал в ожидаемой форме — '
            'структурное изменение вне допуска AC-7')

        self.assertEqual(
            self.old_outside, self.new_outside,
            "orchestrator/report.py: код вне литерала _STYLE изменён — "
            "AC-7 разрешает править только значения внутри существующих "
            "правил _STYLE, не функции рендера и не HTML-структуру")

    def test_ac7_no_css_selector_or_property_added_or_removed(self):
        if self.new_style is None:
            self.skipTest("покрыто test_ac7_code_outside_style_block_is_unchanged")

        old_rules = _parse_rules(self.old_style)
        new_rules = _parse_rules(self.new_style)

        old_selectors = set(old_rules)
        new_selectors = set(new_rules)
        self.assertEqual(
            old_selectors, new_selectors,
            f"CSS-селекторы внутри _STYLE изменились — добавлены "
            f"{new_selectors - old_selectors}, удалены "
            f"{old_selectors - new_selectors}; AC-7 запрещает "
            f"добавление/удаление CSS-класса/селектора")

        for selector in old_selectors:
            self.assertEqual(
                old_rules[selector], new_rules[selector],
                f"внутри правила {selector!r} изменился набор "
                f"CSS-свойств (добавлено "
                f"{new_rules[selector] - old_rules[selector]}, удалено "
                f"{old_rules[selector] - new_rules[selector]}) — AC-7 "
                f"разрешает менять только значения существующих "
                f"объявлений, не набор свойств")


if __name__ == "__main__":
    unittest.main()
