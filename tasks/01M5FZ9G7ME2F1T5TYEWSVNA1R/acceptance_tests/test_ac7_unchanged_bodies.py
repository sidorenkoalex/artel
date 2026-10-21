"""AC-7: дифф задачи не меняет тела прежних функций прогона и реестра, ветки `_cmd_canary` и подписи `_run_one_task`/`cmd_canary`.

Группа: разовый
Зелёный с рождения: до реализации ветка равна базе — тела и подписи совпадают; тест краснеет, только если реализация перепишет прежние функции вместо новой функции подкоманды.

Почему разовый: проверяется разница ветки задачи с базой (`DIFF_BASE`
помощника пульта) — после мержа проверять её не на чем.

Тело сравнивается разбором (`ast.dump` без номеров строк, без
докстринга): комментарии и докстринги — не тело. База — текст файла в
ревизии `DIFF_BASE` (`git show`), ветка — файл рабочей копии `CODE_ROOT`.
Для `_cmd_canary` прежние инструкции тела обязаны остаться в прежнем
порядке, а добавленные — нести строку `run-task` (вставка разбора
подкоманды).
"""
import ast
import inspect
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

from orchestrator import canary  # noqa: E402

CANARY_REL = "orchestrator/canary.py"
ARTEL_REL = "orchestrator/artel.py"
UNCHANGED = ("cmd_canary", "_run_one_task", "_live_run_record",
             "_report_drive_failure", "live_runs", "live_marks", "registry_view",
             "_drop_live_record", "_mark_follows_record", "cmd_canary_live",
             "live_run_note", "refuse_main_move_during_canary")
SIGNED = ("_run_one_task", "cmd_canary")


def base_text(rel: str) -> str:
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "show", f"{DIFF_BASE}:{rel}"],
                         capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        raise AssertionError(f"git show {DIFF_BASE}:{rel}: {res.stderr}")
    return res.stdout


def branch_text(rel: str) -> str:
    return (Path(CODE_ROOT) / rel).read_text(encoding="utf-8")


def functions(text: str) -> dict:
    tree = ast.parse(text)
    return {node.name: node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def body(node) -> list:
    statements = list(node.body)
    if (statements and isinstance(statements[0], ast.Expr)
            and isinstance(statements[0].value, ast.Constant)
            and isinstance(statements[0].value.value, str)):
        statements = statements[1:]
    return statements


def shape(node) -> str:
    return ast.dump(ast.Module(body=body(node), type_ignores=[]))


def params(node) -> list:
    """(имя, вид, текст значения по умолчанию, текст аннотации) параметров из разбора."""
    a = node.args
    positional = [*a.posonlyargs, *a.args]
    defaults = [None] * (len(positional) - len(a.defaults)) + list(a.defaults)
    kinds = (["POSITIONAL_ONLY"] * len(a.posonlyargs)
             + ["POSITIONAL_OR_KEYWORD"] * len(a.args))
    out = [(p.arg, kind, None if d is None else ast.unparse(d),
            None if p.annotation is None else ast.unparse(p.annotation))
           for p, kind, d in zip(positional, kinds, defaults)]
    if a.vararg is not None:
        out.append((a.vararg.arg, "VAR_POSITIONAL", None, None))
    for p, d in zip(a.kwonlyargs, a.kw_defaults):
        out.append((p.arg, "KEYWORD_ONLY", None if d is None else ast.unparse(d),
                    None if p.annotation is None else ast.unparse(p.annotation)))
    if a.kwarg is not None:
        out.append((a.kwarg.arg, "VAR_KEYWORD", None, None))
    return out


class UnchangedBodiesTest(unittest.TestCase):
    """База диффа задачи и рабочая копия кода."""

    def test_ac7_old_bodies_unchanged(self):
        """Тела `cmd_canary`, `_run_one_task`, `_live_run_record`, `_report_drive_failure` и функций чтения и уборки реестра в ветке — те же, что в базе.

        Ловит мутацию: приём записи реестра выделен из `_live_run_record` в
        общий помощник (тело `_live_run_record` меняется), строка «оборвана
        сигналом» вынесена из `cmd_canary`, либо `_run_one_task` получил
        ветку для подкоманды — разбор тела отличается от базы.
        """
        base, branch = functions(base_text(CANARY_REL)), functions(branch_text(CANARY_REL))
        for name in UNCHANGED:
            with self.subTest(функция=name):
                self.assertIn(name, base, f"{name} нет в базе {DIFF_BASE}")
                self.assertIn(name, branch, f"{name} нет в ветке")
                self.assertEqual(shape(branch[name]), shape(base[name]),
                                 f"тело {name} изменено")

    def test_ac7_cmd_canary_branches_only_gain_run_task(self):
        """`_cmd_canary` в ветке: прежние инструкции тела (ветки `pool-seal`, `live`, `--detach`, `--k`) — в прежнем порядке, добавленные несут `run-task`.

        Ловит мутацию: разбор `run-task` встроен внутрь прежней ветки
        (например, в условие `--detach`) либо ветка `live`/`pool-seal`
        переписана — прежняя инструкция не находится в ветке без изменений.
        """
        base = body(functions(base_text(ARTEL_REL))["_cmd_canary"])
        branch = body(functions(branch_text(ARTEL_REL))["_cmd_canary"])
        wanted = [ast.dump(s) for s in base]
        got = [ast.dump(s) for s in branch]
        i = 0
        extra = []
        for statement, dumped in zip(branch, got):
            if i < len(wanted) and dumped == wanted[i]:
                i += 1
            else:
                extra.append(ast.unparse(statement))
        self.assertEqual(i, len(wanted),
                         f"прежняя инструкция _cmd_canary №{i + 1} не найдена без "
                         f"изменений:\n{ast.unparse(base[min(i, len(base) - 1)])}")
        for text in extra:
            self.assertIn("run-task", text, f"добавлено в _cmd_canary не о run-task:\n{text}")

    def test_ac7_signatures_unchanged(self):
        """Подписи `_run_one_task` и `cmd_canary` в ветке совпадают с базой: разбором и `inspect.signature` загруженного модуля.

        Ловит мутацию: `_run_one_task` получил новый параметр (например,
        `parent_pid` или флаг подкоманды) либо `cmd_canary` — флаг
        параллельного режима; состав или вид параметров расходится с базой.
        """
        base, branch = functions(base_text(CANARY_REL)), functions(branch_text(CANARY_REL))
        for name in SIGNED:
            with self.subTest(функция=name):
                expected = params(base[name])
                self.assertEqual(params(branch[name]), expected, f"подпись {name}")
                self.assertEqual(ast.dump(branch[name].returns or ast.Constant(None)),
                                 ast.dump(base[name].returns or ast.Constant(None)),
                                 f"аннотация возврата {name}")
                live = inspect.signature(getattr(canary, name))
                self.assertEqual([(p.name, p.kind.name) for p in live.parameters.values()],
                                 [(n, k) for n, k, _d, _a in expected],
                                 f"inspect.signature({name})")


if __name__ == "__main__":
    unittest.main()
