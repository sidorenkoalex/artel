"""AC-5, AC-6 — 01M3F7BYE82S9AQCBSP1RTQQTR: ADR «Провайдеры ролей»
приложен к PLAN.md применимым диффом и несёт решения 20.09 и 22.09.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. К PLAN.md приложен unified-диф нового файла ADR «Провайдеры ролей:
исполнитель шага за интерфейсом провайдера» в каталоге ADR, и `git apply
--check` на этом дифе проходит на чистом дереве.
AC-6. Текст ADR из AC-5 несёт решения 20.09 и 22.09 (интерфейс
провайдера, каталог моделей и ярусы, авторизация по подписке, запрет сети
роли под Codex, разрешение смешанных ярусов, доллар по тарифу), принцип
«защита роли — песочница провайдера плюс гейты пульта, а не текст правил»
и ссылку на таблицу паритета в docs/stack.md.

Приложение разбирается ТЕМ ЖЕ разбором, которым его читает пульт на
мерже (`scripts/guard.py::plan_appendices`), а не своим регулярным
выражением рядом: приложение, которое планка признала, а пульт нет, —
худший из исходов. Текст PLAN.md читается из артефактной ветки задачи
(`gitcmd.show`), диска рабочей копии планка не касается.

Чистое дерево для `git apply --check` — пустой временный каталог: диф
AC-5 создаёт НОВЫЙ файл, и такой каталог и есть дерево, в котором его
предобраза нет; заодно прогон планки не трогает ни рабочую копию, ни
список worktree пульта.

Красен до реализации: PLAN.md задачи ещё не написан (его создаёт роль
developer) — `_util.plan_text()` отдаёт None, и оба теста падают на
первом же assert об отсутствующем приложении.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import config  # noqa: E402
from scripts import guard  # noqa: E402

ADR_DIR = "docs/adr/"

#: Предметы, которые AC-6 требует от текста ADR: (что именно, набор
#: альтернатив опознания — альтернатива срабатывает, когда в добавленных
#: строках диффа есть ВСЕ её подстроки).
ADR_TOPICS = (
    ("решение 20.09", (("20.09",), ("2026-09-20",))),
    ("решение 22.09", (("22.09",), ("2026-09-22",))),
    ("интерфейс провайдера", (("интерфейс", "провайдер"),)),
    ("каталог моделей и ярусы",
     (("каталог", "ярус"), ("models.yaml", "ярус"))),
    ("авторизация по подписке", (("подписк",),)),
    ("запрет сети роли под Codex",
     (("сет", "codex"), ("network", "codex"))),
    ("разрешение смешанных ярусов", (("смешан",),)),
    ("доллар по тарифу", (("тариф",),)),
    ("принцип «песочница провайдера плюс гейты пульта, а не текст правил»",
     (("песочниц", "гейт", "правил"),)),
    ("ссылка на таблицу паритета в docs/stack.md",
     (("stack.md", "паритет"),)),
)


def _adr_appendix():
    """(приложение PLAN.md к каталогу ADR, причина отсутствия) —
    первое приложение, чьи пути ведут в `docs/adr/`."""
    text = _util.plan_text()
    if text is None:
        return None, ("PLAN.md не найден в артефактной ветке задачи — "
                      "приложение ADR обязана дать роль developer")
    appendices, errors = guard.plan_appendices(text)
    for appendix in appendices:
        if any(path.startswith(ADR_DIR) for path in appendix.paths):
            return appendix, ""
    return None, (f"в PLAN.md нет приложения ```diff с заголовком "
                  f"diff --git a/{ADR_DIR}… (разобранные приложения: "
                  f"{[a.paths for a in appendices]}; ошибки разбора: "
                  f"{errors})")


def _added_lines(diff: str) -> str:
    """Добавленные строки диффа (без заголовка `+++`) одним текстом."""
    return "\n".join(line[1:] for line in diff.splitlines()
                     if line.startswith("+") and not line.startswith("+++"))


class AdrDiffAttachmentTest(unittest.TestCase):

    def test_ac5_plan_attaches_a_new_adr_file_diff_that_applies(self):
        """PLAN.md несёт приложение с unified-диффом НОВОГО файла в
        каталоге ADR, и `git apply --check` на этом дифе проходит в
        чистом дереве (пустой временный каталог); если файл ADR в дереве
        пульта уже существует (Оператор применил приложение), дифф
        обязан накладываться на него обратно.

        Ловит мутацию: диф собран руками, и заголовок хунка (`@@ -0,0
        +1,N @@`) называет не то число строк, что несёт блок, — `git
        apply --check` отвечает ненулевым кодом («corrupt patch»), и
        приложение, которое Оператор не смог бы применить на мерже, не
        уедет в approved под видом готового.
        """
        appendix, reason = _adr_appendix()
        self.assertIsNotNone(appendix, reason)

        paths = [p for p in appendix.paths if p.startswith(ADR_DIR)]
        self.assertTrue(
            "new file mode" in appendix.diff or "/dev/null" in appendix.diff,
            f"приложение к {paths} не создаёт НОВЫЙ файл (в дифе нет ни "
            f"'new file mode', ни '/dev/null') — AC-5 говорит о новом ADR")

        with tempfile.TemporaryDirectory() as clean_tree:
            result = subprocess.run(
                ["git", "apply", "--check", "-"], cwd=clean_tree,
                input=appendix.diff, capture_output=True, text=True)
        self.assertEqual(
            0, result.returncode,
            f"git apply --check на чистом дереве отказал: {result.stderr}")

        for path in paths:
            if not (config.ROOT / path).is_file():
                continue
            reverse = subprocess.run(
                ["git", "apply", "--check", "--reverse", "-"],
                cwd=config.ROOT, input=appendix.diff,
                capture_output=True, text=True)
            self.assertEqual(
                0, reverse.returncode,
                f"{path} уже существует в дереве пульта, но приложенный "
                f"дифф не накладывается на него обратно — значит, это "
                f"дифф другого файла с тем же именем: {reverse.stderr}")

    def test_ac6_adr_text_carries_the_decisions_the_principle_and_the_link(self):
        """Добавленные строки приложенного диффа (то есть текст самого
        ADR) несут все десять предметов AC-6: обе даты решений, шесть их
        пунктов, принцип защиты роли и ссылку на таблицу паритета в
        docs/stack.md.

        Ловит мутацию: ADR пишется как пересказ одного разговора и
        теряет пункт, который ни в одном другом документе не записан, —
        разрешение смешанных ярусов или доллар по тарифу; subTest
        назовёт потерянный предмет поимённо.
        """
        appendix, reason = _adr_appendix()
        self.assertIsNotNone(appendix, reason)

        text = _added_lines(appendix.diff).lower()
        self.assertTrue(text.strip(), "приложенный дифф ADR не добавляет "
                                      "ни одной строки текста")

        for topic, alternatives in ADR_TOPICS:
            with self.subTest(topic=topic):
                self.assertTrue(
                    any(all(part in text for part in alt)
                        for alt in alternatives),
                    f"текст ADR не несёт предмет «{topic}» (AC-6); искали "
                    f"любую из групп подстрок: {alternatives}")


if __name__ == "__main__":
    unittest.main()
