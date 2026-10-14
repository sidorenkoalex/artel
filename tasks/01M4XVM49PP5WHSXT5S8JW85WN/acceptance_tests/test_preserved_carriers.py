"""Сохранение названных SPEC носителей при адресной миграции этой задачи.

Группа: разовый
Зелёный с рождения: исходные носители ещё не изменены; тест удерживает их имена и прежние assertions при миграции.

carriers.txt — снимок assertions исходных методов из AC-9–AC-14.
Сравнение AST не зависит от форматирования, комментариев и сообщений
ошибок. Дополнительные assertions допустимы. Смысловая проверка области
сценариев, потока управления и инвентаризации остаётся у AC-15: наличие
assertion в тексте не доказывает его достижимость. Поведение разрешённых
прогонов удерживают сами прежние носители, которые не дублируются здесь.
"""
import ast
from collections import Counter
import json
from pathlib import Path
import shlex
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT


def assertion_signatures(node):
    result = []
    for item in ast.walk(node):
        if (isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)
                and item.func.attr.startswith("assert")):
            item.keywords = [kw for kw in item.keywords if kw.arg != "msg"]
            arity = {"assertTrue": 1, "assertFalse": 1,
                     "assertIsNone": 1, "assertIsNotNone": 1}.get(item.func.attr, 2)
            if item.func.attr not in ("assertRaises", "assertRaisesRegex",
                                      "assertWarns", "assertWarnsRegex"):
                item.args = item.args[:arity]
            result.append(ast.dump(item, include_attributes=False))
        elif isinstance(item, ast.Assert):
            result.append(ast.dump(item.test, include_attributes=False))
    return Counter(result)


class PreservedCarriersTest(unittest.TestCase):
    def retained(self, ac):
        data = json.loads(Path(__file__).with_name("carriers.txt").read_text())
        for carrier in data[str(ac)]:
            filename, cls, method = (carrier[key] for key in ("file", "class", "method"))
            address = f"{filename}::{cls}::{method}"
            with self.subTest(carrier=address):
                tree = ast.parse((Path(CODE_ROOT) / filename).read_text())
                classes = [node for node in tree.body
                           if isinstance(node, ast.ClassDef) and node.name == cls]
                self.assertTrue(classes, f"Удалён/переименован класс {address}")
                methods = [node for node in classes[0].body
                           if isinstance(node, ast.FunctionDef) and node.name == method]
                self.assertTrue(methods, f"Удалён/переименован метод {address}")
                actual = assertion_signatures(methods[0])
                expected = Counter(carrier["assertions"])
                self.assertFalse(expected - actual,
                                 f"Не сохранены прежние assertions {address}: {expected - actual}")
                for decorator in (*classes[0].decorator_list, *methods[0].decorator_list):
                    names = [node.attr if isinstance(node, ast.Attribute) else node.id
                             for node in ast.walk(decorator)
                             if isinstance(node, (ast.Attribute, ast.Name))]
                    self.assertFalse(set(names) & {"skip", "skipIf", "skipUnless", "xfail", "expectedFailure"},
                                     f"Отключён носитель {address}")

    def test_ac9_readonly_outcomes_keep_original_assertions(self):
        """При смене роли сценария остаются зелёный/красный исходы и запрет записи журнала.

        Ловит мутацию: удалена проверка кода 1, зелёного отчёта, отсутствия
        исключения или пустого журнала — соответствующая assertion теряется.
        """
        self.retained(9)

    def test_ac10_deferred_journal_keeps_original_assertions(self):
        """Адресная миграция сохраняет носитель отложенной записи и её досыла.

        Ловит мутацию: удалена проверка отсутствия записи до досыла либо
        появления записи после штатных входов пульта.
        """
        self.retained(10)

    def test_ac11_both_lock_directions_keep_original_assertions(self):
        """Метод общего замка и обе его проверки сохраняют прежние исходы.

        Ловит мутацию: исчезла проверка id держателя, незапущенного pytest
        или исхода «прогон не начат» в одном направлении блокировки.
        """
        self.retained(11)

    def test_ac12_profile_limit_and_timeout_keep_original_assertions(self):
        """Носитель профильного предела сохраняет предел, источник и код таймаута.

        Ловит мутацию: проверка переданного предела/источника либо точного
        исхода timeout с кодом 1 удалена или смягчена.
        """
        self.retained(12)

    def test_ac13_branch_and_base_log_paths_keep_original_assertions(self):
        """Смена области роли сохраняет проверки путей логов ветки и базы.

        Ловит мутацию: удалён запрет внешних логов, проверка лога базы или
        существования названных в отчёте путей.
        """
        self.retained(13)

    def test_ac14_gate_reuse_metrics_and_ci_carriers_are_retained(self):
        """Адресные носители полного гейта, reuse, метрик и команда CI сохраняются.

        Ловит мутацию: удалена assertion одного из названных в матрице
        свойств либо из CI убран полный pytest tests с прежним timeout.
        """
        self.retained(14)
        workflow = (Path(CODE_ROOT) / ".github/workflows/ci.yml").read_text()
        commands = [shlex.split(line.strip().replace(";", " ; ")) for line in workflow.splitlines()
                    if "python3 -m pytest tests" in line and not line.lstrip().startswith("#")]
        expected = shlex.split("python3 -m pytest tests -n auto -p no:cacheprovider -p timeout -p xdist -o timeout=120")
        self.assertTrue(any(all(token in command for token in expected) for command in commands),
                        "Полная команда CI с прежними флагами/пределом отсутствует")
