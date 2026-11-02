"""Переписанный долгоживущий тест В1.2 `test_ac9_in_dev_gate_of_ci_component_judges_local_checkouts`: утверждает отсутствие выписок и чтений отчётов у `ci` на `in_dev` и ловлю находки на `verifying` с возвратом в `in_dev`.

Группа: разовый
Красен до реализации: метод в файле В1.2 ещё прежний — утверждает наличие выписок (`assert box.checkouts`) и отказ на `in_dev`, а `verifying` и возврат из него в его коде не встречаются.

Факт задачи — правка конкретного метода чужого долгоживущего файла по
мандату ANSWER-1: после мержа проверять её не на чем. Метод читается из
рабочей копии кода (`CODE_ROOT` помощника пульта) разбором `ast`: тело без
докстринга, утверждения — узлы `assert`. Прогон самого метода — `pytest`
по узлу в корне рабочей копии.
"""
import ast
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

REL = "tests/test_01m5xzskk8h096fd3cpn05bqnm_ci_outcome_gate.py"
NAME = "test_ac9_in_dev_gate_of_ci_component_judges_local_checkouts"
NEGATIVE = ("== []", "== ()", "== set()", "== 0", "not ")
REPORT_READS = ("gate_reads", "forge.calls", "job_test_report", "report_reads")


def method():
    """(код тела без докстринга, тексты утверждений) метода `NAME`."""
    text = (Path(CODE_ROOT) / REL).read_text(encoding="utf-8")
    tree = ast.parse(text)
    found = [n for n in tree.body
             if isinstance(n, ast.FunctionDef) and n.name == NAME]
    assert found, f"метода {NAME} нет в {REL}"
    func = found[0]
    body = func.body[1:] if ast.get_docstring(func) is not None else func.body
    code = "\n".join(ast.get_source_segment(text, node) or "" for node in body)
    asserts = [ast.get_source_segment(text, node) or ""
               for stmt in body for node in ast.walk(stmt)
               if isinstance(node, ast.Assert)]
    return code, asserts


def test_ac14_rewritten_test_asserts_no_checkouts_and_no_report_reads_on_in_dev():
    """Тело переписанного метода утверждает отсутствие выписок и отсутствие чтений отчётов CI у `ci` на `in_dev`.

    Сценарий: метод `NAME` читается из рабочей копии кода; среди его
    утверждений есть утверждение о шпионе выписок (`checkouts`) в
    отрицательной форме (`== []`, `not …`) и утверждение о чтениях отчётов
    хостинга (`gate_reads`/`forge.calls`/`job_test_report`) в
    отрицательной форме.

    Ловит мутацию: метод оставлен прежним — `assert box.checkouts`
    утверждает наличие выписок; утверждение о выписках снято вовсе.
    """
    _code, asserts = method()
    assert any("checkouts" in a and any(m in a for m in NEGATIVE)
               for a in asserts), asserts
    assert any(any(r in a for r in REPORT_READS) and any(m in a for m in NEGATIVE)
               for a in asserts), asserts


def test_ac14_rewritten_test_asserts_verifying_returns_finding_to_in_dev():
    """Тело переписанного метода ведёт сценарий до `verifying` и утверждает возврат находки в `in_dev`.

    Сценарий: код тела метода (без докстринга) упоминает состояние
    `verifying` и действие или вид находки «сломан правкой»
    (`BROKEN_ACTION`/`BROKEN`/«сломан правкой»/`refusal(`); среди
    утверждений — утверждение о состоянии `in_dev`.

    Ловит мутацию: метод проверяет только уход в `verifying` без опроса
    `verifying` и возврата — `verifying` в коде нет, утверждения о
    `in_dev` нет или находка не читается.
    """
    code, asserts = method()
    assert "verifying" in code, code
    assert any("in_dev" in a for a in asserts), asserts
    assert any(m in code for m in ("BROKEN", "сломан правкой", "refusal(")), code


def test_ac14_rewritten_test_passes():
    """Переписанный метод зелёный на коде задачи.

    Сценарий: `python -m pytest <файл>::<метод>` в корне рабочей копии
    кода; код выхода 0, метод не пропущен (в выводе «1 passed»).

    Ловит мутацию: метод переписан под устройство, которого код не
    даёт, — красен; метод помечен пропуском — «1 skipped» вместо
    «1 passed».
    """
    res = subprocess.run(
        [sys.executable, "-m", "pytest", f"{REL}::{NAME}", "-q",
         "-p", "no:cacheprovider"],
        cwd=str(CODE_ROOT), capture_output=True, text=True, timeout=110)
    out = res.stdout + res.stderr
    assert res.returncode == 0, out[-3000:]
    assert "1 passed" in out, out[-3000:]
