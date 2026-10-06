"""Сторож: в модулях проверок пункта 8 нет прямого сравнения с `config.DEFAULT_TARGET`.

Группа: долгоживущий
Красен до реализации: `orchestrator/advance_gates/review.py` ещё сравнивает проект задачи с `config.DEFAULT_TARGET` (гейт «замечания ревью не отработаны») — сторож называет это место.

Модули проверок пункта 8 ADR-0021 — `orchestrator/advance_gates/*.py` и
гейт мержа `orchestrator/fsm_merge_gate.py` — узнают артель только
признаком проекта (`repo_context`), а не сравнением имени проекта с
`config.DEFAULT_TARGET`. Сторож разбирает их исходники `ast` (не
исполняет) и падает на любом сравнении `==`, `!=`, `in`, `not in`, один из
операндов которого — `DEFAULT_TARGET` (в любой записи: `config.`,
`doctor.config.`, голое имя) либо кортеж/список/множество с ним, называя
файл и строку.
"""
import ast
import random
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_OPS = (ast.Eq, ast.NotEq, ast.In, ast.NotIn)


def guarded_files(root: Path) -> list:
    """Исходники, которые стережёт сторож, — пути относительно `root`."""
    gates = sorted((root / "orchestrator" / "advance_gates").glob("*.py"))
    return [p.relative_to(root).as_posix()
            for p in gates + [root / "orchestrator" / "fsm_merge_gate.py"]]


def is_default_target_node(node) -> bool:
    if isinstance(node, ast.Attribute) and node.attr == "DEFAULT_TARGET":
        return True
    if isinstance(node, ast.Name) and node.id == "DEFAULT_TARGET":
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return any(is_default_target_node(e) for e in node.elts)
    return False


def default_target_comparisons(source: str, rel: str) -> list:
    """`[(файл, строка), …]` — сравнения с `DEFAULT_TARGET` в `source`."""
    found = []
    for node in ast.walk(ast.parse(source, filename=rel)):
        if not isinstance(node, ast.Compare):
            continue
        operands = [node.left, *node.comparators]
        for i, op in enumerate(node.ops):
            if not isinstance(op, FORBIDDEN_OPS):
                continue
            if (is_default_target_node(operands[i])
                    or is_default_target_node(operands[i + 1])):
                found.append((rel, node.lineno))
                break
    return found


def scan(root: Path, sources: dict = None) -> list:
    """Находки сторожа по всем стерегомым файлам; `sources` подменяет текст
    отдельных файлов (сценарий «в модуль добавили сравнение»)."""
    found = []
    for rel in guarded_files(root):
        text = (sources or {}).get(rel)
        if text is None:
            text = (root / rel).read_text(encoding="utf-8")
        found.extend(default_target_comparisons(text, rel))
    return found


def report(found: list) -> str:
    return "прямое сравнение с config.DEFAULT_TARGET в модулях проверок " \
           "пункта 8: " + ", ".join(f"{rel}:{line}" for rel, line in found)


# Формы сравнения, которые сторож обязан ловить (AC-14: `==`, `!=`, `in`,
# `not in`); `{x}` — левый операнд.
INJECTED_FORMS = (
    "{x} == config.DEFAULT_TARGET",
    "{x} != config.DEFAULT_TARGET",
    "config.DEFAULT_TARGET == {x}",
    "{x} in (config.DEFAULT_TARGET,)",
    "{x} not in (config.DEFAULT_TARGET, 'canary')",
    "{x} in {{config.DEFAULT_TARGET}}",
    "({x} or doctor.config.DEFAULT_TARGET) != doctor.config.DEFAULT_TARGET",
)


def module_level_insert_line(source: str) -> int:
    """Номер строки (1-based) сразу после последнего узла верхнего уровня
    модуля — место, куда вставка функции не ломает разбор."""
    tree = ast.parse(source)
    return max(getattr(n, "end_lineno", n.lineno) for n in tree.body) + 1


class GateTargetGuardTest(unittest.TestCase):

    def test_ac14_guarded_gates_have_no_default_target_comparison(self):
        """Сторож проходит на ветке: ни в одном модуле `advance_gates/*.py` и в `fsm_merge_gate.py` нет сравнения с `DEFAULT_TARGET`.

        Сценарий: разбираются исходники всех стерегомых файлов рабочего
        дерева; находок быть не должно, а провал перечисляет каждое место
        `файл:строка`.

        Ловит мутацию: в `orchestrator/advance_gates/review.py` оставлена
        (или возвращена) развилка `store.task_target(conn, task_id) !=
        config.DEFAULT_TARGET` гейта «замечания ревью не отработаны» —
        сторож краснеет строкой `orchestrator/advance_gates/review.py:<N>`.
        """
        files = guarded_files(ROOT)
        self.assertIn("orchestrator/fsm_merge_gate.py", files)
        self.assertTrue(any(f.startswith("orchestrator/advance_gates/")
                            for f in files),
                        "сторож не нашёл ни одного модуля advance_gates")
        found = scan(ROOT)
        self.assertEqual(found, [], report(found))

    def test_ac14_injected_comparison_is_named_with_file_and_line(self):
        """В модуль гейта на случайную позицию добавлено сравнение с `DEFAULT_TARGET` — сторож называет этот файл и эту строку.

        Сценарий: для нескольких случайно выбранных стерегомых файлов и
        случайной формы сравнения (`==`, `!=`, `in`, `not in`, кортеж,
        множество, `doctor.config.`) в конец модуля дописывается функция с
        таким сравнением; разбор подменённого текста обязан вернуть находку
        ровно с этим файлом и номером строки сравнения, и текст отчёта
        сторожа несёт `файл:строка`. Зерно печатается и входит в текст
        провала.

        Ловит мутацию: сторож сравнивает только `==`/`!=` и пропускает
        `in`/`not in` (или смотрит лишь на `config.DEFAULT_TARGET`, не на
        `doctor.config.DEFAULT_TARGET`/кортеж с ним) — на такой форме
        находки нет, и тест краснеет с зерном и формой.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        files = guarded_files(ROOT)
        cases = [(rng.choice(files), form) for form in INJECTED_FORMS]
        for rel, form in cases:
            with self.subTest(file=rel, form=form, seed=seed):
                original = (ROOT / rel).read_text(encoding="utf-8")
                at = module_level_insert_line(original)
                lines = original.splitlines()
                var = rng.choice(["target", "t_name", "project"])
                injected = [
                    "",
                    "",
                    f"def _guard_probe_{rng.randrange(10**6)}({var}):",
                    f"    if {form.format(x=var)}:",
                    "        return True",
                    "    return False",
                ]
                text = "\n".join(lines[:at - 1] + injected + lines[at - 1:])
                compare_line = at + 3
                found = scan(ROOT, {rel: text})
                self.assertIn((rel, compare_line), found,
                              f"зерно {seed}: сторож не нашёл «{form}» в "
                              f"{rel}:{compare_line}; находки: {found}")
                self.assertIn(f"{rel}:{compare_line}", report(found),
                              f"зерно {seed}: отчёт не называет место")

    def test_ac14_non_comparison_uses_are_not_flagged(self):
        """Упоминание `DEFAULT_TARGET` не в сравнении (умолчание `or`, вызов, присваивание) сторож не считает находкой.

        Сценарий: в случайный стерегомый модуль дописывается функция с
        допустимыми формами — `t or config.DEFAULT_TARGET`, передача
        аргументом, присваивание; находок в дописанных строках нет.
        Зерно печатается.

        Ловит мутацию: сторож ищет подстроку `DEFAULT_TARGET` в тексте, а не
        сравнение в дереве разбора — категория «значение по умолчанию»
        (SPEC «Не входит») красила бы сторожа, и тест краснеет на
        дописанной строке.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        rel = rng.choice(guarded_files(ROOT))
        original = (ROOT / rel).read_text(encoding="utf-8")
        at = module_level_insert_line(original)
        lines = original.splitlines()
        injected = [
            "",
            "",
            "def _guard_probe_allowed(t):",
            "    name = t or config.DEFAULT_TARGET",
            "    other = resolve(config.DEFAULT_TARGET)",
            "    return name, other",
        ]
        text = "\n".join(lines[:at - 1] + injected + lines[at - 1:])
        probe_lines = set(range(at, at + len(injected)))
        found = [f for f in scan(ROOT, {rel: text})
                 if f[0] == rel and f[1] in probe_lines]
        self.assertEqual(found, [],
                         f"зерно {seed}: допустимые формы помечены: {found}")


if __name__ == "__main__":
    unittest.main()
