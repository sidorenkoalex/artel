"""Сохранение конкретной прежней проверки remote same_host_ok в этой задаче.

Группа: разовый
Зелёный с рождения: три существующих assertions remote same_host_ok пока сохранены; AC-2 запрещает их ослаблять при исправлении.
"""
import ast
import unittest
from pathlib import Path


class ExistingAssertionsTest(unittest.TestCase):
    def test_ac2_existing_remote_assertions_are_preserved(self):
        """Исправление сохраняет вид и аргументы всех прежних assertions.

        Ловит мутацию: удаление сравнения всей строки либо замена его на
        проверку одного поля теряет исходный assertion и красит планку.
        """
        root = next(p for p in Path(__file__).resolve().parents
                    if (p / "orchestrator" / "lease.py").is_file())
        tree = ast.parse((root / "tests" / "test_lease.py").read_text(encoding="utf-8"))
        cls = next(n for n in tree.body
                   if isinstance(n, ast.ClassDef) and n.name == "OwnSessionLiveOtherPidTest")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name ==
                      "test_holder_on_different_host_with_same_host_ok_returns_none_false_without_mutation")
        calls = [ast.dump(n, include_attributes=False) for n in ast.walk(method)
                 if isinstance(n, ast.Call)]
        for expression in ("self.assertIsNone(refusal)", "self.assertFalse(fresh)",
                           "self.assertEqual(dict(self.row()), before)"):
            with self.subTest(assertion=expression):
                self.assertIn(ast.dump(ast.parse(expression).body[0].value,
                                       include_attributes=False), calls)
