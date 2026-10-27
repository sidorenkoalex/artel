"""Приложение PLAN задачи к `tests/test_invariants.py` применимо и добавляет два теста инвариантов требования 8.

Группа: разовый
Красен до реализации: PLAN.md задачи в ссылке документов ещё нет — приложения к `tests/test_invariants.py` нет, `artifact_text("PLAN.md")` отвечает `None`.

Факт этой задачи: PLAN читается помощником пульта из ссылки документов
той ревизии, с которой выложена планка (`_pult.artifact_text`), приложения
разбираются `scripts/guard.plan_appendices` — тем же разбором, которым их
применяет гейт мержа; применимость — `_pult.apply_check` к дереву HEAD
рабочей копии (`tests/test_invariants.py` защищён, ветка задачи его не
меняет, поэтому в HEAD он тот же, что в `base`).

Разбор и счёт новых тестов провалидированы временным PLAN с приложением,
добавляющим в `tests/test_invariants.py` два метода (подмена
`artifact_text`, удалена): зелёный; PLAN без приложения и приложение с
одним методом — красные.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, apply_check, artifact_text  # noqa: E402

sys.path.insert(0, str(CODE_ROOT))
from scripts import guard  # noqa: E402

INVARIANTS = "tests/test_invariants.py"
NEW_TEST = re.compile(r"^\+\s*def (test_\w+)\(")


def invariants_appendices() -> list:
    text = artifact_text("PLAN.md")
    assert text, "PLAN.md задачи в ссылке документов нет"
    appendices, _errors = guard.plan_appendices(text)
    return [a for a in appendices if INVARIANTS in a.paths]


def test_ac19_invariants_appendix_applies_and_adds_two_tests():
    """Приложение PLAN к `tests/test_invariants.py` применяется к дереву и добавляет не меньше двух тестовых методов.

    Сценарий: PLAN задачи из ссылки документов, разделы «## Приложение»
    разобраны правилом гейта мержа. Среди приложений есть приложение,
    задевающее `tests/test_invariants.py`; `git apply --check` каждого
    такого приложения к HEAD согласен; добавленных строк `def test_…`
    в них не меньше двух (тест «нет слияния, отправки base и отправки в
    ветку задачи в `awaiting_human`» и тест «MR открывается или снимается
    с черновика только для подтверждённой головы с зелёным CI»).

    Ловит мутацию: приложение с устаревшим хедером хунка (`git apply
    --check` отказывает); либо приложение несёт только один из двух тестов
    требования 8; либо дифф огорожен голым ``` и не разбирается как
    приложение (приложения к пути нет).
    """
    found = invariants_appendices()
    assert found, f"в PLAN нет приложения к {INVARIANTS}"
    for appendix in found:
        answer = apply_check(appendix.diff)
        assert answer == "", f"приложение к {INVARIANTS} не применяется: {answer}"
    added = [m.group(1) for a in found for line in a.diff.splitlines()
             for m in [NEW_TEST.match(line)] if m]
    assert len(set(added)) >= 2, f"новых тестов в приложении: {added}"
