"""AC-8: PLAN.md несёт приложение к `docs/invariants.md`, дополняющее строку инварианта 38 находкой смены параметризации.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё не написан (его пишет developer) — `artifact_text("PLAN.md")` отдаёт `None`, приложения к `docs/invariants.md` нет, а в строке `| 38 |` базы нет ни `parametrize`, ни `pytest.param(`.

Источник PLAN.md — ссылка документов задачи через помощник пульта
(`_pult.artifact_text`); приложения разбираются тем же
`scripts/guard.py::plan_appendices`, которым их разбирает гейт
приложений PLAN (разделы «## Приложение…», блоки ```diff). Применимость
и итоговый текст — наложением (`git apply --cached`) на дерево базы
диффа задачи (`_pult.DIFF_BASE`) во временном индексе: рабочая копия и
её индекс не меняются. Приложение, уже лежащее в базе (Оператор внёс его
в main раньше прогона), признаётся по обратному наложению — тогда
итоговый текст и есть текст базы.

Образец — планка AC-10 части 2 (`refs/artifacts/
01M56TNX1WWKV8PVQ94FT4ZJQB`, `acceptance_tests/
test_ac10_invariants_attachment.py`), исполненная на её гейте.
Провалидировано вручную до сдачи: на PLAN.md-фикстуре с приложением,
дописывающим в строку `| 38 |` `parametrize` и `pytest.param(`, оба
метода зелёные; на приложении без `pytest.param(` — красный второй.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _pult  # noqa: E402
from _pult import artifact_text  # noqa: E402

sys.path.insert(0, str(_pult.CODE_ROOT))

from scripts import guard  # noqa: E402

TARGET = "docs/invariants.md"
ROW_PREFIX = "| 38 |"
NEW_FORMS = ("parametrize", "pytest.param(")
OLD_FORMS = ("@skip", "@skipIf", "@skipUnless", "@expectedFailure",
             "@pytest.mark.skip", "skipif", "xfail", "pytest.skip(",
             "имя-метка", "pytestmark", "allow_module_level=True",
             "pytest.importorskip(")


def _git(index: str, *args: str):
    env = dict(os.environ, GIT_INDEX_FILE=index)
    return subprocess.run(["git", "-C", str(_pult.CODE_ROOT), *args],
                          env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def invariants_after_appendices(plan_text: str) -> tuple:
    """(текст `docs/invariants.md` после наложения приложений PLAN на
    дерево базы, ошибка). Ошибка непустая — приложения нет либо оно не
    накладывается на базу ни прямо, ни обратно."""
    appendices, errors = guard.plan_appendices(plan_text)
    diffs = [a.diff for a in appendices if TARGET in a.paths]
    if not diffs:
        return None, (f"в PLAN.md нет приложения к {TARGET} "
                      f"(ошибки разбора: {errors})")
    base = _pult.DIFF_BASE
    if not base:
        return None, "база диффа задачи не определена при выкладке"
    with tempfile.TemporaryDirectory(prefix="ac8-") as tmp:
        index = str(Path(tmp) / "index")
        res = _git(index, "read-tree", base)
        if res.returncode:
            return None, f"read-tree {base}: {res.stderr}"
        for number, diff in enumerate(diffs, 1):
            patch = Path(tmp) / f"appendix-{number}.diff"
            patch.write_text(diff, encoding="utf-8")
            forward = _git(index, "apply", "--cached", str(patch))
            if forward.returncode == 0:
                continue
            reverse = _git(index, "apply", "--check", "--cached", "--reverse",
                           str(patch))
            if reverse.returncode:
                return None, (f"приложение {number} к {TARGET} не "
                              f"накладывается на базу {base} ни прямо, ни "
                              f"обратно:\n{forward.stderr}\n{reverse.stderr}")
        shown = _git(index, "cat-file", "blob", f":{TARGET}")
        if shown.returncode:
            return None, f"чтение {TARGET} из индекса: {shown.stderr}"
        return shown.stdout, ""


def row_38(text: str) -> str | None:
    rows = [line for line in text.splitlines() if line.startswith(ROW_PREFIX)]
    return rows[0] if len(rows) == 1 else None


class InvariantsAttachmentTest(unittest.TestCase):

    def patched(self) -> str:
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md задачи нет в ссылке документов")
        text, error = invariants_after_appendices(plan)
        self.assertEqual("", error, error)
        return text

    def test_ac8_invariants_appendix_applies_to_base(self):
        """PLAN.md несёт приложение к `docs/invariants.md`, и оно накладывается на дерево базы диффа задачи.

        Разбор разделов «## Приложение…» PLAN.md гейтовым
        `guard.plan_appendices` находит блок ```diff с путём
        `docs/invariants.md`; `git apply --cached` во временном индексе
        дерева базы проходит (либо приложение уже в базе — обратное
        наложение проходит).

        Ловит мутацию: правка инварианта внесена в код ветки или
        записана в PLAN.md вне блока ```diff раздела «## Приложение» —
        приложения нет; хедер хунка не совпадает с диапазоном файла базы —
        `git apply` отказывает.
        """
        self.patched()

    def test_ac8_row_38_names_parametrize_and_keeps_old_forms(self):
        """После наложения строка `| 38 |` несёт `parametrize` и `pytest.param(` и сохраняет прежние формы пропуска.

        Итоговый текст `docs/invariants.md` содержит ровно одну строку,
        начинающуюся с `| 38 |`; в ней есть `parametrize`, `pytest.param(`
        и каждый элемент прежнего перечня — `@skip`, `@skipIf`,
        `@skipUnless`, `@expectedFailure`, `@pytest.mark.skip`, `skipif`,
        `xfail`, `pytest.skip(`, `имя-метка`, `pytestmark`,
        `allow_module_level=True`, `pytest.importorskip(`.

        Ловит мутацию: приложение дописывает находку параметризации в
        другую строку или новой строкой таблицы — в строке 38 её нет;
        забыта форма `pytest.param(`; перечень переписан с потерей
        прежнего элемента (`pytest.importorskip(`, `@expectedFailure`).
        """
        row = row_38(self.patched())
        self.assertIsNotNone(row, f"в {TARGET} нет единственной строки "
                                  f"«{ROW_PREFIX}» после наложения")
        for needle in NEW_FORMS + OLD_FORMS:
            with self.subTest(needle=needle):
                self.assertIn(needle, row, f"строка инварианта 38 после "
                                           f"наложения не несёт «{needle}»")


if __name__ == "__main__":
    unittest.main()
