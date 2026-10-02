"""Текст `docs/operator-gates.md` (AC-12), три приложения PLAN.md к
защищённым путям (AC-13) и тесты требования 10 в `tests/` (AC-14).

Группа: разовый

Красен до реализации: в `docs/operator-gates.md` нет ни слова об
изменённых утверждениях, PLAN.md задачи ещё нет в артефактной ветке, а в
`tests/test_guard_test_ast.py`/`tests/test_test_integrity_gate.py` нет
новых методов с заявками требования 10. Вторая половина AC-14
(`test_ac14_existing_methods_keep_their_assertions`) зелёная с рождения:
утверждения существующих тестов пока не тронуты, тест держит это против
подгонки их под новую запись журнала.

Источники. `docs/operator-gates.md` и файлы `tests/` — рабочая копия кода
задачи (`config.ROOT`; на гейте это дерево кодовой ветки). PLAN.md — только
артефактная ветка (`gitcmd.show`). База сравнения — `gitcmd.diff_base`
(точка расхождения с `origin/main`). Приложение накладывается `git apply`
на файл базы во временном каталоге; если оно уже применено в базе (прогон
после мержа), сверяется обратное наложение, и текстом «после» служит
база. Смысл текстов сверяется опорами (основы слов), не точной
формулировкой — кроме заявок «Ловит мутацию», формулировку которых
критерий берёт дословно из требования 10.
"""
import ast
import re
import subprocess
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from orchestrator import artifact_branch, config, gitcmd
from scripts import guard

TASK_ID = "01M3Y753QNG6TS5C7MTJS1MEV6"
GATES_DOC = "docs/operator-gates.md"
CHECKLIST = "skills/review-checklist.md"
INVARIANTS = "docs/invariants.md"
CODING = "skills/coding-standards.md"
GUARD_TESTS = "tests/test_guard_test_ast.py"
GATE_TESTS = "tests/test_test_integrity_gate.py"
SMOKE_TESTS = "tests/test_fsm_advance_gate_smoke.py"

CLAIMS = {
    GUARD_TESTS: (
        "сравнение утверждений выключено или сравнивает только число "
        "утверждений",
        "локальные имена, сообщение или корень импорта входят в ключ "
        "сравнения",
        "вспомогательные функции не разворачиваются",
    ),
    GATE_TESTS: (
        "находка об утверждениях не доходит до журнала либо блокирует "
        "переход",
        "находка заведена без имени метода либо под другим именем",
        "наблюдение есть только на одном рубеже либо не доходит до "
        "ревьювера",
        "двойная находка либо трейсбек на неразбираемом файле",
    ),
}


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("ё", "е").replace("Ё", "Е")).lower()


def section(text: str, title_prefix: str) -> str:
    """Тело раздела `## <заголовок, начинающийся с title_prefix>`."""
    match = re.search(rf"^##\s+{re.escape(title_prefix)}.*$", text, re.M)
    if match is None:
        return ""
    rest = text[match.end():]
    nxt = re.search(r"^##\s", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def numbered_item(body: str, n: int) -> str:
    """Текст пункта `n.` нумерованного списка раздела — до пункта `n+1.`
    или конца раздела."""
    match = re.search(rf"^{n}\.\s", body, re.M)
    if match is None:
        return ""
    rest = body[match.start():]
    nxt = re.search(rf"^{n + 1}\.\s", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def base_sha() -> str:
    base = gitcmd.diff_base("HEAD")
    if base is None:
        raise AssertionError("git не назвал базу ветки")
    return base


def base_text(path: str):
    text, _reason = gitcmd.show(base_sha(), path)
    return text


def head_text(path: str) -> str:
    return (config.ROOT / path).read_text(encoding="utf-8")


def assertion_texts(node) -> Counter:
    """Мультимножество утверждений метода в виде `ast.unparse` (форматирование
    не различается): `assert`, вызов атрибута `assert*`/`fail`,
    `pytest.raises`/`pytest.warns`."""
    found: Counter = Counter()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assert):
            found[ast.unparse(sub)] += 1
        elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            attr = sub.func.attr
            dotted = ast.unparse(sub.func)
            if attr.startswith("assert") or attr == "fail" \
                    or dotted in ("pytest.raises", "pytest.warns"):
                found[ast.unparse(sub)] += 1
    return found


class OperatorGatesDocTest(unittest.TestCase):

    def setUp(self):
        text = head_text(GATES_DOC)
        self.merge_section = section(text, "Гейт merge")
        self.escalation_section = section(text, "Гейт эскалации")
        self.assertTrue(self.merge_section, "нет раздела «Гейт merge»")
        self.assertTrue(self.escalation_section, "нет раздела «Гейт эскалации»")
        self.both = flat(self.merge_section + "\n" + self.escalation_section)

    def test_ac12_findings_list_rules_and_mandate_rule_in_operator_gates(self):
        """П. 4 гейта merge и п. 6 гейта эскалации называют изменённые утверждения; есть абзац о нормальной форме и правило мандата.

        Пункт 4 раздела «Гейт merge» и пункт 6 раздела «Гейт эскалации»
        говорят об утверждениях тестового метода, сохранившего имя. В
        двух разделах вместе есть абзац о том, что находка (удаление,
        смена вида, смена аргумента) и что нет (добавление, перестановка,
        локальное имя, сообщение, модуль импорта, форматирование), и
        правило мандата: заявка «Ловит мутацию» в base и head, мандат не
        выдаётся, если свойство перестало сторожиться, роль возвращает
        утверждение или добавляет равноценное, основание называет
        требование SPEC.

        Ловит мутацию: дополнение внесено только в один из двух пунктов —
        другой пункт без «утвержд…»; абзац о нормальной форме опускает
        «не находки» (сообщение, локальные имена, перестановку) — нет
        опоры; правило мандата без запрета выдачи или без основания из
        SPEC — нет опоры.
        """
        merge_item = flat(numbered_item(self.merge_section, 4))
        escalation_item = flat(numbered_item(self.escalation_section, 6))
        for label, item in (("п. 4 гейта merge", merge_item),
                            ("п. 6 гейта эскалации", escalation_item)):
            self.assertTrue(item, f"нет пункта: {label}")
            for stem in ("утвержден", "сохранивш"):
                self.assertIn(stem, item, f"{label}: нет опоры «{stem}»")
        for stem in ("удал", "вид", "аргумент", "добавл", "перестан",
                     "локальн", "сообщени", "импорт", "форматир",
                     "ловит мутацию", "base", "head", "не выда", "равноценн",
                     "основани", "требовани", "spec"):
            self.assertIn(stem, self.both, f"нет опоры «{stem}» в разделах "
                                           f"гейтов merge и эскалации")


def plan_text() -> str:
    text, reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                               f"tasks/{TASK_ID}/PLAN.md")
    if text is None:
        raise AssertionError(f"PLAN.md нет в артефактной ветке: {reason}")
    return text


def git_apply(cwd: str, diff: str, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "apply", *flags, "-"], cwd=cwd, input=diff,
                          capture_output=True, text=True)


class PlanAppendicesTest(unittest.TestCase):

    def setUp(self):
        appendices, errors = guard.plan_appendices(plan_text())
        self.assertEqual([], errors, f"приложения PLAN не разобраны: {errors}")
        self.appendices = appendices

    def appendix(self, path: str) -> tuple:
        """(добавленные строки, текст файла после приложения) для `path`;
        приложение обязано накладываться на базу ветки (прямо либо, после
        мержа, обратно)."""
        mine = [a for a in self.appendices if path in a.paths]
        self.assertTrue(mine, f"в PLAN.md нет приложения к {path}")
        diff = "".join(a.diff for a in mine)
        added = [line[1:] for line in diff.splitlines()
                 if line.startswith("+") and not line.startswith("+++")
                 and line[1:].strip()]
        self.assertTrue(added, f"приложение к {path} ничего не добавляет")
        before = base_text(path)
        self.assertIsNotNone(before, f"{path} нет в базе ветки")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / path
            target.parent.mkdir(parents=True)
            target.write_text(before, encoding="utf-8")
            check = git_apply(tmp, diff, "--check")
            if check.returncode == 0:
                applied = git_apply(tmp, diff)
                self.assertEqual(0, applied.returncode, applied.stderr)
                return added, target.read_text(encoding="utf-8")
            reverse = git_apply(tmp, diff, "--check", "--reverse")
            self.assertEqual(
                0, reverse.returncode,
                f"приложение к {path} не проходит git apply --check на базе "
                f"ни прямо, ни обратно:\n{check.stderr}\n{reverse.stderr}")
            return added, before

    def assert_added_inside(self, added: list, body: str, where: str) -> None:
        self.assertTrue(body, f"нет раздела {where}")
        outside = [line for line in added if line.strip() not in body]
        self.assertEqual([], outside, f"строки приложения легли вне {where}")

    def test_ac13_three_appendices_apply_and_carry_requirements_7_8_9(self):
        """Три приложения PLAN к защищённым путям накладываются на базу и несут требования 7, 8 и 9.

        `skills/review-checklist.md`: добавленное целиком в «Фазе B» и
        говорит о сверке утверждений изменённого метода с базой, мандате
        либо требовании SPEC, замечании major, сужении данных (`setUp`,
        `subTest`), переносе под условие и помощниках глубже первого
        уровня. `docs/invariants.md`: строка инварианта 38 после
        приложения называет утверждение метода, сохранившего имя, и виды
        утверждений. `skills/coding-standards.md`: добавленное целиком в
        «Тестах» говорит, что сохранение имени не разрешает менять
        утверждения, и требует эскалации до сдачи шага с перечнем
        `tests/<файл>.py::<Класс>::<метод>`, старым и новым утверждением и
        требованием SPEC.

        Ловит мутацию: одно из трёх приложений отсутствует или не
        накладывается на базу (неверный хедер хунка); пункт чек-листа
        лёг вне Фазы B; строка 38 не дополнена (приложение правит другую
        строку); пункт стандартов лёг вне раздела «Тесты» или опускает
        эскалацию до сдачи шага.
        """
        added, after = self.appendix(CHECKLIST)
        self.assert_added_inside(added, section(after, "Фаза B"), "«Фазы B»")
        text = flat("\n".join(added))
        for stem in ("утвержден", "base", "мандат", "spec", "major", "setup",
                     "subtest", "услови", "глубже"):
            self.assertIn(stem, text, f"{CHECKLIST}: нет опоры «{stem}»")

        _added, after = self.appendix(INVARIANTS)
        row = next((line for line in after.splitlines()
                    if line.startswith("| 38 |")), "")
        self.assertTrue(row, f"{INVARIANTS}: нет строки инварианта 38")
        row = flat(row)
        for stem in ("утвержден", "сохранивш", "assert", "fail",
                     "pytest.raises", "pytest.warns", "сообщени", "локальн",
                     "импорт"):
            self.assertIn(stem, row, f"{INVARIANTS}, строка 38: нет «{stem}»")

        added, after = self.appendix(CODING)
        self.assert_added_inside(added, section(after, "Тесты"), "«Тестов»")
        joined = "\n".join(added)
        text = flat(joined)
        for stem in ("утвержден", "сохран", "эскал", "до сдачи", "стар",
                     "нов", "требовани", "spec"):
            self.assertIn(stem, text, f"{CODING}: нет опоры «{stem}»")
        self.assertRegex(joined, r"tests/\S+\.py::\S+::\S+",
                         f"{CODING}: нет перечня tests/<файл>.py::<Класс>::<метод>")


class RequirementTenTestsTest(unittest.TestCase):

    def new_methods(self, path: str) -> dict:
        head = guard.qualified_test_methods(head_text(path))
        base = guard.qualified_test_methods(base_text(path))
        return {name: node for name, node in head.items() if name not in base}

    def test_ac14_new_methods_carry_requirement_10_claims(self):
        """Новые методы двух файлов `tests/` несут «Ловит мутацию» с формулировками требования 10.

        В каждом из `tests/test_guard_test_ast.py` и
        `tests/test_test_integrity_gate.py` есть новые (не из базы)
        тестовые методы, у каждого — непустая заявка «Ловит мутацию: …»,
        и среди их докстрингов встречается каждая формулировка
        требования 10 своего файла (10а–в и 10г–ж).

        Ловит мутацию: тесты требования 10 положены в другой файл —
        формулировки в этих двух не найдутся; у нового метода нет
        заявки; заявка перефразирована (сверка дословная по
        нормализованным пробелам).
        """
        for path, claims in CLAIMS.items():
            methods = self.new_methods(path)
            self.assertTrue(methods, f"{path}: новых тестовых методов нет")
            docs = []
            for name, node in methods.items():
                doc = ast.get_docstring(node) or ""
                self.assertRegex(doc, r"Ловит мутацию:\s*\S",
                                 f"{path}::{name}: нет заявки «Ловит мутацию»")
                docs.append(flat(doc))
            joined = " ".join(docs)
            for claim in claims:
                self.assertIn(flat(claim), joined,
                              f"{path}: нет заявки «{claim}»")

    def test_ac14_existing_methods_keep_their_assertions(self):
        """Существующие методы тестов гейта и смоука сохранены, их утверждения не правятся.

        Для каждого тестового метода базы в `tests/test_guard_test_ast.py`,
        `tests/test_test_integrity_gate.py` и
        `tests/test_fsm_advance_gate_smoke.py` метод есть в рабочей копии,
        и мультимножество его утверждений (`ast.unparse`) то же, что в
        базе.

        Ловит мутацию: разработчик подогнал ожидаемый текст журнала в
        существующем тесте гейта или смоуке под новую запись — утверждение
        метода изменится; существующий метод удалён или переименован.
        """
        for path in (GUARD_TESTS, GATE_TESTS, SMOKE_TESTS):
            base = guard.qualified_test_methods(base_text(path))
            self.assertTrue(base, f"{path}: в базе нет тестовых методов")
            head = guard.qualified_test_methods(head_text(path))
            for name, node in base.items():
                self.assertIn(name, head, f"{path}::{name} исчез")
                self.assertEqual(assertion_texts(node),
                                 assertion_texts(head[name]),
                                 f"{path}::{name}: утверждения изменены")


if __name__ == "__main__":
    unittest.main()
