"""Юнит-тесты режима артефактной ветки guard (01M1R66X5SMD3ZEDCVAJ0DR7K2,
требования 1-5).

Приёмочные тесты задачи (`tasks/01M1R66X5SMD3ZEDCVAJ0DR7K2/
acceptance_tests/test_ac1_*.py` … `test_ac9_*.py`) уже закрывают AC-1..
AC-9 чёрным ящиком через `guard.main()`/`fsm.guard_refuses` — они
зафиксированы `tests_writing` и не дублируются здесь. Этот файл
проверяет напрямую `guard.is_draft_lenient`/`guard.
basic_frontmatter_errors`/`guard.check_content` и граничные случаи,
которые приёмочная планка не обязана перечислять поимённо: тип вне
DRAFT_LENIENT_TYPES, отсутствие поля `type`/`status` целиком,
`schema_version` отсутствует у уже «готового» (не draft) артефакта (не
должно стать новой ошибкой), и параметр `artifact_branch_mode` по
умолчанию (тот же приём, что `tests/test_guard_zones.py`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import guard  # noqa: E402


class IsDraftLenientTest(unittest.TestCase):
    """Предикат требования 2/3: только четыре типа, только буквально
    `status: draft`."""

    def test_spec_draft_is_lenient(self):
        """Ловит мутацию: `is_draft_lenient` возвращает константу `False`
        (или роняет проверку `type`) — тогда ни один черновик, включая
        базовый случай `spec`/`draft`, не получил бы льготный режим
        требования 2."""
        self.assertTrue(guard.is_draft_lenient({"type": "spec", "status": "draft"}))

    def test_plan_review_test_report_draft_are_lenient(self):
        """Ловит мутацию: реализация проверяет только `spec` (по образцу
        уже существующей zone-проверки), забыв остальные три типа
        требования 2."""
        for atype in ("plan", "review", "test_report"):
            with self.subTest(тип=atype):
                self.assertTrue(
                    guard.is_draft_lenient({"type": atype, "status": "draft"}))

    def test_tz_questions_answer_draft_are_not_lenient(self):
        """Требование 3: три типа вне DRAFT_LENIENT_TYPES не входят в
        льготный режим ни при каком статусе, включая `draft`.

        Ловит мутацию: `DRAFT_LENIENT_TYPES` расширили до всех типов
        (например, скопировали множество валидных `type` целиком) —
        тогда `tz`/`questions`/`answer` со `status: draft` тоже стали бы
        льготными вопреки требованию 3."""
        for atype in ("tz", "questions", "answer"):
            with self.subTest(тип=atype):
                self.assertFalse(
                    guard.is_draft_lenient({"type": atype, "status": "draft"}))

    def test_non_draft_status_is_not_lenient(self):
        """Ловит мутацию: сравнение статуса ослаблено до "не ready" вместо
        буквального "== draft" (например, `status != "ready"`) — тогда
        любой из этих "сданных" статусов ошибочно попал бы в льготный
        режим требования 2."""
        for status in ("ready", "approved", "changes_requested", "escalate", ""):
            with self.subTest(status=status):
                self.assertFalse(
                    guard.is_draft_lenient({"type": "spec", "status": status}))

    def test_missing_status_is_not_lenient(self):
        """Отсутствие поля `status` целиком — то же самое, что пустая
        строка (`meta.get("status") or ""`), не `draft`.

        Ловит мутацию: `meta["status"] == "draft"` вместо
        `meta.get("status")` уронил бы `KeyError`, а не корректный
        `False` — этот тест поймал бы и падение, и ошибочное
        приравнивание отсутствия поля к `draft`."""
        self.assertFalse(guard.is_draft_lenient({"type": "spec"}))

    def test_missing_type_is_not_lenient(self):
        """Ловит мутацию: `meta.get("type", "spec")` (подстановка
        дефолтного типа вместо `None`) сделала бы артефакт без поля
        `type` неотличимым от `spec`/`draft` и ошибочно льготным."""
        self.assertFalse(guard.is_draft_lenient({"status": "draft"}))

    def test_unknown_type_with_draft_status_is_not_lenient(self):
        """Ловит мутацию: проверка членства в `DRAFT_LENIENT_TYPES`
        заменена на "тип не пустой" (`bool(meta.get("type"))`) — тогда
        любой тип, включая несуществующий, прошёл бы льготный режим."""
        self.assertFalse(
            guard.is_draft_lenient({"type": "nonsense", "status": "draft"}))


class BasicFrontmatterErrorsTest(unittest.TestCase):
    """Требование 2, первая часть: task/type/schema_version на месте,
    schema_version не выше SUPPORTED_SCHEMA_VERSION — и ничего сверх
    этого."""

    def test_clean_meta_has_no_errors(self):
        """Ловит мутацию: базовая проверка ошибочно требует что-то сверх
        task/type/schema_version (например, забытый `author_role` из
        полной проверки `_content_errors`) — тогда даже корректный
        черновик получил бы ложную ошибку."""
        meta = {"task": "T1", "type": "spec", "status": "draft",
                "schema_version": 4}
        self.assertEqual(guard.basic_frontmatter_errors("label", meta), [])

    def test_missing_task_is_an_error(self):
        """Ловит мутацию: `BASIC_META_FIELDS` растеряла `task` (осталось
        только `type`) — тогда черновик без идентификатора задачи прошёл
        бы базовую проверку молча, вопреки требованию 2."""
        meta = {"type": "spec", "status": "draft", "schema_version": 4}
        errors = guard.basic_frontmatter_errors("label", meta)
        self.assertTrue(any("task" in e for e in errors), errors)

    def test_missing_schema_version_is_an_error(self):
        """Отличие от `_content_errors`/`schema_errors`: там отсутствие
        `schema_version` — версия 1 по умолчанию, не ошибка. Здесь, в
        базовой проверке черновика, поле обязано быть НА МЕСТЕ
        (требование 2, буквально «schema_version на месте»).

        Ловит мутацию: разработчик переиспользует голый `schema_errors`
        без отдельной проверки присутствия поля — тогда черновик без
        `schema_version` вовсе прошёл бы базовую проверку молча.
        """
        meta = {"task": "T1", "type": "spec", "status": "draft"}
        errors = guard.basic_frontmatter_errors("label", meta)
        self.assertTrue(any("schema_version" in e for e in errors), errors)

    def test_schema_version_present_but_zero_is_not_reported_as_missing(self):
        """Значение `0` — ложно в булевом контексте, но ПРИСУТСТВУЕТ в
        frontmatter: единственная жалоба — от `schema_errors` («не целое
        число ≥ 1»), не задвоенная жалоба «поле отсутствует».

        Ловит мутацию: проверка присутствия через `not meta.get(...)`
        вместо `"schema_version" not in meta` задвоила бы сообщение для
        этого значения.
        """
        meta = {"task": "T1", "type": "spec", "status": "draft",
                "schema_version": 0}
        errors = guard.basic_frontmatter_errors("label", meta)
        self.assertEqual(len(errors), 1, errors)
        self.assertNotIn("не заполнены", errors[0])

    def test_too_new_schema_version_is_an_error_with_the_version_named(self):
        """Ловит мутацию: `basic_frontmatter_errors` не зовёт
        `schema_errors` (переизобретает свою, более слабую проверку
        границы) — тогда `schema_version` выше
        `SUPPORTED_SCHEMA_VERSION` прошёл бы базовую проверку черновика
        молча, вопреки требованию 2 («schema_version не выше
        SUPPORTED_SCHEMA_VERSION остаётся ошибкой»)."""
        meta = {"task": "T1", "type": "spec", "status": "draft",
                "schema_version": guard.SUPPORTED_SCHEMA_VERSION + 1}
        errors = guard.basic_frontmatter_errors("label", meta)
        self.assertTrue(
            any(str(guard.SUPPORTED_SCHEMA_VERSION + 1) in e for e in errors),
            errors)


class CheckContentDefaultIsUnaffectedTest(unittest.TestCase):
    """AC-1 на уровне функции: без аргумента `artifact_branch_mode`
    (или с явным `False`) `check_content` не отличим от поведения до
    этой задачи — draft-документ с разбитым содержимым отказывает так
    же, как «сданный»."""

    DRAFT_SPEC_NO_SECTIONS = """---
task: T1
type: spec
author_role: analyst
status: draft
schema_version: 1
---

# SPEC: фикстура
"""

    def test_default_call_reports_full_content_errors_for_a_draft(self):
        """Ловит мутацию: `check_content` без явного параметра ошибочно
        включает льготный режим по умолчанию (например, дефолт
        `artifact_branch_mode: bool = True`) — тогда черновик без единой
        обязательной секции прошёл бы вызов без нового параметра молча,
        нарушая AC-1 (поведение без режима не меняется ни на бит)."""
        errors = guard.check_content("label", self.DRAFT_SPEC_NO_SECTIONS)
        self.assertTrue(
            any("отсутствует обязательная секция" in e for e in errors), errors)

    def test_explicit_false_matches_the_default(self):
        """Ловит мутацию: значение параметра по умолчанию расходится с
        явным `False` (например, дефолт — не `bool`, а `None`, который
        где-то по пути трактуется иначе) — тогда AC-1 держался бы только
        случайно, а два эквивалентных вызова расходились бы в
        результате."""
        default = guard.check_content("label", self.DRAFT_SPEC_NO_SECTIONS)
        explicit = guard.check_content("label", self.DRAFT_SPEC_NO_SECTIONS,
                                       artifact_branch_mode=False)
        self.assertEqual(default, explicit)

    def test_mode_true_on_a_lenient_draft_returns_only_basic_errors(self):
        """Требование 2: с режимом включённым, тот же черновик без единой
        секции возвращает ТОЛЬКО базовые нарушения (здесь — ни одного,
        frontmatter в порядке), не содержательные.

        Ловит мутацию: `check_content(..., artifact_branch_mode=True)`
        по-прежнему зовёт `_content_errors` напрямую, минуя ветвление
        `is_draft_lenient` — тогда даже с включённым режимом черновик
        получил бы полный список содержательных ошибок вместо пустого."""
        errors = guard.check_content("label", self.DRAFT_SPEC_NO_SECTIONS,
                                     artifact_branch_mode=True)
        self.assertEqual(errors, [])

    def test_mode_true_on_a_non_lenient_type_is_unaffected(self):
        """Требование 3: `questions` со `status: draft` — режим не меняет
        результат `check_content` по сравнению с выключенным.

        Ловит мутацию: ветвление на льготность применено ДО проверки
        типа (то есть распространено на все типы, а не только
        DRAFT_LENIENT_TYPES) — тогда `questions`/`draft` тоже получил бы
        урезанный список ошибок вместо полного, нарушая требование 3."""
        text = """---
task: T1
type: questions
author_role: analyst
status: draft
schema_version: 1
---

# QUESTIONS: фикстура
"""
        off = guard.check_content("label", text, artifact_branch_mode=False)
        on = guard.check_content("label", text, artifact_branch_mode=True)
        self.assertEqual(off, on)
        self.assertTrue(any("Вопросы" in e for e in off), off)


if __name__ == "__main__":
    unittest.main()
