"""Тесты разбора YAML и карты ролей (см. tasks/T017/SPEC.md, требования 1–2).

Один парсер на систему — значит, у него один набор правил, и правила эти
проверяются здесь: типизация скаляров, frontmatter (включая его отсутствие),
блочные отображения roles.yaml и отказы на неподдерживаемых конструкциях.

Отдельно проверяется главное следствие требования 1: состав скилов роли
меняется правкой roles.yaml, без правки кода.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (artifacts, config, models, roles,  # noqa: E402
                          yamlmini)
from scripts import guard  # noqa: E402
from tests.sandbox import TmpPlanPathTest  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

ARTIFACT = """---
task: T017
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 1
iteration: 2
budget_usd: 12.5
draft: false
token_slot: null
title: "25"
---

# PLAN: разбор
"""


class ScalarTest(unittest.TestCase):
    """Типизация значений: тип поля виден читателю, а не додумывается им."""

    def test_types_are_recognised(self):
        for raw, expected in (("1", 1), ("-3", -3), ("12.5", 12.5),
                              ("1e3", 1000.0), ("true", True), ("False", False),
                              ("null", None), ("~", None), ("", None),
                              ("T017", "T017"), ("main", "main")):
            with self.subTest(значение=raw):
                self.assertEqual(yamlmini.scalar(raw), expected)

    def test_int_and_float_are_not_the_same_type(self):
        self.assertIsInstance(yamlmini.scalar("1"), int)
        self.assertIsInstance(yamlmini.scalar("1.0"), float)

    def test_quoted_number_stays_a_string(self):
        """Кавычки — форма записи: `"25"` остаётся строкой, как в YAML."""
        self.assertEqual(yamlmini.scalar('"25"'), "25")
        self.assertEqual(yamlmini.scalar("'25'"), "25")

    def test_trailing_comment_is_cut(self):
        self.assertEqual(yamlmini.scalar("draft   # draft | ready"), "draft")

    def test_quoted_value_with_a_comment_loses_both_quotes(self):
        """Комментарий на строке значения — по шаблону; кавычки — привычка.

        Вместе они и ломали разбор: проверка кавычек стояла на строке
        с комментарием, последний символ был не кавычкой, и значение
        доезжало до guard в виде `'"ready"'` (T017, ревью 1).
        """
        for raw in ('"ready"   # draft | ready | approved',
                    "'ready'  # комментарий",
                    '"ready"'):
            with self.subTest(значение=raw):
                self.assertEqual(yamlmini.scalar(raw), "ready")

    def test_hash_inside_quotes_stays_in_the_value(self):
        """Комментарий срезается за закрывающей кавычкой, а не до неё."""
        self.assertEqual(yamlmini.scalar('"a # b"'), "a # b")
        self.assertEqual(yamlmini.scalar('"a # b"  # хвост'), "a # b")

    def test_broken_quoting_stays_a_plain_scalar(self):
        """Кавычки не закрыты или покрывают не всё — значение не в кавычках.

        Гадать за автора парсер не должен, а падать ему нельзя: тот же разбор
        читает frontmatter на пути FSM, где трейсбек запрещён.
        """
        self.assertEqual(yamlmini.scalar('"ready'), '"ready')
        self.assertEqual(yamlmini.scalar('"ready" лишнее'), '"ready" лишнее')

    def test_hash_without_a_space_is_part_of_the_value(self):
        """`#` открывает комментарий только после пробела — правило YAML."""
        self.assertEqual(yamlmini.scalar("task#1"), "task#1")

    def test_nan_and_inf_stay_strings(self):
        """float() их принимает, YAML в такой записи — нет; числом не станут."""
        for raw in ("nan", "inf", "-inf"):
            with self.subTest(значение=raw):
                self.assertIsInstance(yamlmini.scalar(raw), str)


class FrontmatterTest(unittest.TestCase):
    """Frontmatter артефакта: значения с типами, отсутствие блока — None."""

    def test_values_are_typed(self):
        meta = yamlmini.frontmatter(ARTIFACT)

        self.assertEqual(meta["task"], "T017")
        self.assertEqual(meta["schema_version"], 1)
        self.assertEqual(meta["iteration"], 2)
        self.assertEqual(meta["budget_usd"], 12.5)
        self.assertIs(meta["draft"], False)
        self.assertIsNone(meta["token_slot"])
        self.assertEqual(meta["title"], "25", "кавычки оставляют строку строкой")
        self.assertEqual(meta["status"], "ready", "комментарий не часть значения")

    def test_quoted_values_next_to_template_comments_are_read(self):
        """Шаблон поставляет `status:` с комментарием, автор берёт значение
        в кавычки — до читателя должно доехать значение, а не его запись."""
        meta = yamlmini.frontmatter('---\ntask: "T017"  # идентификатор\n'
                                    'status: "ready"        # draft | ready\n---\n')

        self.assertEqual(meta, {"task": "T017", "status": "ready"})

    def test_no_frontmatter_is_none(self):
        """None — блока нет вовсе; на нём guard говорит «нет frontmatter»."""
        self.assertIsNone(yamlmini.frontmatter("# PLAN\n\nтекст\n"))

    def test_block_without_fields_is_an_empty_mapping(self):
        self.assertEqual(yamlmini.frontmatter("---\n\n---\n"), {})

    def test_fence_must_open_the_file(self):
        self.assertIsNone(yamlmini.frontmatter("\n---\ntask: T017\n---\n"))

    def test_comment_lines_are_not_fields(self):
        """Закомментированное поле полем не становится (шаблон SPEC.md)."""
        meta = yamlmini.frontmatter("---\ntask: T017\n# budget_usd: 25\n---\n")

        self.assertEqual(meta, {"task": "T017"})


class ArtifactsReadTest(TmpPlanPathTest):
    """`artifacts.frontmatter` — тот же разбор, что у guard, плюс файл."""

    def test_reader_and_guard_see_the_same_fields(self):
        self.path.write_text(ARTIFACT, encoding="utf-8")

        self.assertEqual(artifacts.frontmatter(self.path),
                         yamlmini.frontmatter(ARTIFACT))

    def test_missing_file_is_empty(self):
        self.assertEqual(artifacts.frontmatter(self.path), {})

    def test_undecodable_file_is_empty_and_guard_names_it(self):
        """Нечитаемый файл: FSM не двигает задачу, guard называет причину."""
        self.path.write_bytes(b"---\ntask: T\xff17\n---\n")

        self.assertEqual(artifacts.frontmatter(self.path), {})
        self.assertTrue(any("не прочитан" in e for e in guard.check(self.path)))


class MappingTest(unittest.TestCase):
    """Блочные отображения: вложенность по отступу и потоковые списки."""

    def test_nested_mapping_and_flow_list(self):
        text = ("roles:\n"
                "  developer:\n"
                "    executor: agent\n"
                "    skills: [a, b, c]   # список скилов\n"
                "  analyst:\n"
                "    token_slot: null\n"
                "token_fallback: artel-token\n")

        self.assertEqual(yamlmini.mapping(text), {
            "roles": {"developer": {"executor": "agent",
                                    "skills": ["a", "b", "c"]},
                      "analyst": {"token_slot": None}},
            "token_fallback": "artel-token"})

    def test_empty_flow_list(self):
        self.assertEqual(yamlmini.mapping("skills: []\n"), {"skills": []})

    def test_key_without_value_and_without_block_is_null(self):
        self.assertEqual(yamlmini.mapping("a:\nb: 1\n"), {"a": None, "b": 1})

    def test_comments_and_blank_lines_are_skipped(self):
        self.assertEqual(yamlmini.mapping("# шапка\n\nk: v\n"), {"k": "v"})

    def test_unsupported_shapes_refuse_loudly(self):
        """Чего парсер не умеет — то ошибка с номером строки, а не полразбора."""
        for name, text in (("блочный список", "roles:\n  - developer\n"),
                           ("строка без двоеточия", "roles\n"),
                           ("рваный отступ", "a: 1\n   b: 2\n"),
                           ("незакрытый список", "skills: [a, b\n"),
                           ("мусор после списка", "skills: [a] лишнее\n"),
                           ("кавычки в списке", 'skills: [a, "b, c"]\n'),
                           ("табуляция в отступе", "roles:\n\tdeveloper: 1\n")):
            with self.subTest(случай=name):
                with self.assertRaises(yamlmini.YamlError):
                    yamlmini.mapping(text)

    def test_the_real_roles_file_parses(self):
        """Формат roles.yaml не менялся — он и есть предмет разбора."""
        data = yamlmini.mapping(
            (REPO_ROOT / "roles.yaml").read_text(encoding="utf-8"))

        self.assertIn("developer", data["roles"])
        self.assertEqual(data["token_fallback"], "artel-token")


class RolesTest(unittest.TestCase):
    """Состав скилов роли берётся из roles.yaml — правка файла меняет промпт."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "roles.yaml"
        patcher = mock.patch.object(config, "ROLES", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, text: str) -> None:
        self.path.write_text(text, encoding="utf-8")

    def test_skills_come_from_the_file(self):
        self.write("roles:\n  developer:\n    skills: [conventions-core]\n")

        self.assertEqual(roles.skills("developer"), ["conventions-core"])

    def test_editing_the_file_changes_the_skills_without_touching_code(self):
        """Критерий приёмки 1: состав меняется правкой roles.yaml."""
        self.write("roles:\n  developer:\n    skills: [a, b]\n")
        self.assertEqual(roles.skills("developer"), ["a", "b"])

        self.write("roles:\n  developer:\n    skills: [a, b, c]\n")

        self.assertEqual(roles.skills("developer"), ["a", "b", "c"])

    def test_order_is_the_order_of_the_file(self):
        self.write("roles:\n  developer:\n    skills: [z, a, m]\n")

        self.assertEqual(roles.skills("developer"), ["z", "a", "m"])

    def test_every_refusal_names_its_reason(self):
        cases = {
            "файла нет": None,
            "не разобрано": "roles:\n  - developer\n",
            "нет раздела roles": "token_fallback: artel-token\n",
            "роль не описана": "roles:\n  reviewer:\n    skills: [a]\n",
            "роль без skills": "roles:\n  developer:\n    executor: agent\n",
            "skills не список": "roles:\n  developer:\n    skills: одна-строка\n",
        }
        for name, text in cases.items():
            with self.subTest(случай=name):
                if text is None:
                    self.path.unlink(missing_ok=True)
                else:
                    self.write(text)

                with self.assertRaises(roles.RolesError) as raised:
                    roles.skills("developer")

                self.assertIn(str(self.path), str(raised.exception))

    def test_the_repository_file_answers_for_both_agent_roles(self):
        """Контроль на настоящем roles.yaml: роли конвейера скилы имеют."""
        with mock.patch.object(config, "ROLES", REPO_ROOT / "roles.yaml"):
            for role in ("developer", "reviewer"):
                with self.subTest(роль=role):
                    names = roles.skills(role)

                    self.assertIn("conventions-core", names)
                    for name in names:
                        self.assertTrue(
                            (REPO_ROOT / "skills" / f"{name}.md").exists(),
                            f"скил {name} назван в roles.yaml, но файла нет")


class RolesModelTierTest(unittest.TestCase):
    """`roles.model_tier` — ярус роли из roles.yaml (SPEC
    01M3009Y9AGGY6ZCFA7H1HJ1TD, требование 5, AC-6), заменивший прежнее
    поле `model:` (SPEC 01M2DTT96FS25SHXP0HDTWARQH): модель, на которую
    указывает ярус, задаёт локальный слой пульта. Тот же приём песочницы,
    что `RolesTest` выше для `skills()`."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "roles.yaml"
        patcher = mock.patch.object(config, "ROLES", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, text: str) -> None:
        self.path.write_text(text, encoding="utf-8")

    def test_every_tier_of_the_closed_list_is_returned(self):
        """Ловит мутацию: `model_tier()` путает поле (читает `skills` или
        `token_slot`) либо возвращает булево наличие поля вместо самого
        значения `model_tier:`."""
        for tier in models.TIERS:
            with self.subTest(ярус=tier):
                self.write(f"roles:\n  developer:\n    skills: [a]\n"
                           f"    model_tier: {tier}\n")

                self.assertEqual(roles.model_tier("developer"), tier)

    def test_missing_field_is_a_refusal_not_a_default(self):
        """Ловит мутацию: отсутствие `model_tier:` трактуется как `None`
        и дефолт CLI — ровно то молчаливое поведение прежнего поля
        `model:`, которое требование 5 заменяет отказом."""
        self.write("roles:\n  developer:\n    skills: [a]\n")

        with self.assertRaises(roles.RolesError) as ctx:
            roles.model_tier("developer")

        self.assertIn("model_tier", str(ctx.exception))

    def test_value_outside_the_closed_list_is_a_roles_error(self):
        """Ловит мутацию: значение принимается как есть — ярус-опечатка
        (`turbo`) уехал бы в «ярус не назван в tiers:» локального слоя, и
        Оператор чинил бы не тот файл."""
        for value in ("turbo", "7", '""'):
            with self.subTest(значение=value):
                self.write(f"roles:\n  developer:\n    skills: [a]\n"
                           f"    model_tier: {value}\n")

                with self.assertRaises(roles.RolesError):
                    roles.model_tier("developer")

    def test_unknown_role_is_a_roles_error(self):
        """Ловит мутацию: роль, которой нет в карте, отдаёт ярус по
        умолчанию вместо отказа — шаг такой роли пошёл бы на модель, о
        которой карта исполнителей ничего не говорит."""
        self.write("roles:\n  developer:\n    skills: [a]\n"
                   "    model_tier: strong\n")

        with self.assertRaises(roles.RolesError):
            roles.model_tier("reviewer")


if __name__ == "__main__":
    unittest.main()
