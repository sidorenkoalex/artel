"""Справка команды `answer` (`orchestrator/artel.py`) и `docs/operator-session.md` описывают мандат тестов на гейте SPEC (AC-8).

Группа: разовый
Красен до реализации: ни справка `artel.py` (докстринг модуля, его печатает `artel.py --help`), ни `docs/operator-session.md` не говорят об `answer` на гейте SPEC — абзаца с `answer` и `spec_gate`/«гейт SPEC» нет вовсе.

Разовый: проверяется текст документации этой ветки (что задача дописала),
а не поведение кода — формулировки справки и документа Оператор вправе
переписать после мержа.

Как планка читает «содержат» (SPEC не фиксирует формулировки буквально):
текст режется на блоки — абзацы между пустыми строками, а в списке каждый
пункт `- …` отдельно. Ищется блок, называющий `answer` и гейт SPEC
(`spec_gate` либо «гейт(е) SPEC»); окно — этот блок и два следующих. В окне
обязаны быть (без учёта регистра): «аудит» (после вердикта аудита),
«approve» (перед approve), «sha» и «голы…»/«без sha» (sha копировать
после мандата или голый approve), «жизн…» (действует всю жизнь задачи),
«reject» и «перечит…» (после reject и новой редакции SPEC перечитать).
Файлы читаются из корня рабочей копии кода (`_pult.CODE_ROOT`).
"""
import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

ROOT = Path(CODE_ROOT)

GATE_RE = re.compile(r"spec_gate|гейт\w*\s+SPEC", re.I)
BLOCK_SPLIT_RE = re.compile(r"\n\s*\n|\n(?=\s*[-*]\s)")
REQUIRED = (
    ("после вердикта аудита", re.compile(r"аудит", re.I)),
    ("перед approve", re.compile(r"approve", re.I)),
    ("sha для approve", re.compile(r"\bsha\b", re.I)),
    ("или голый approve", re.compile(r"голы\w*|без\s+sha", re.I)),
    ("действует всю жизнь задачи", re.compile(r"жизн\w*", re.I)),
    ("после reject", re.compile(r"reject", re.I)),
    ("перечитать мандат", re.compile(r"перечит\w*", re.I)),
)


def blocks(text: str) -> list[str]:
    return [b for b in BLOCK_SPLIT_RE.split(text) if b.strip()]


def windows(text: str) -> list[str]:
    """Окна «блок про answer на гейте SPEC + два следующих»."""
    parts = blocks(text)
    return ["\n".join(parts[i:i + 3]) for i, block in enumerate(parts)
            if "answer" in block and GATE_RE.search(block)]


class HelpAndDocTest(unittest.TestCase):

    def assert_described(self, label: str, text: str) -> None:
        found = windows(text)
        self.assertTrue(found, f"{label}: нет абзаца, где `answer` и гейт SPEC "
                               f"названы вместе")
        best = min(found, key=lambda w: sum(not rx.search(w) for _n, rx in REQUIRED))
        missing = [name for name, rx in REQUIRED if not rx.search(best)]
        self.assertEqual(missing, [], f"{label}: в описании answer на гейте SPEC "
                                      f"не сказано: {missing}\n---\n{best}")

    def test_ac8_answer_help_describes_spec_gate_mandate_order(self):
        """Справка `artel.py` (докстринг модуля): мандат на гейте SPEC — после аудита, перед approve, sha после мандата или голый approve, действует всю жизнь задачи, после reject перечитать.

        Ловит мутацию: справку не дописали (или дописали только факт приёма
        на `spec_gate` без порядка «мандат → approve» и без оговорки о
        reject) — окна с `answer` на гейте SPEC нет либо в нём нет одного
        из пунктов.
        """
        source = (ROOT / "orchestrator" / "artel.py").read_text(encoding="utf-8")
        self.assert_described("orchestrator/artel.py", ast.get_docstring(ast.parse(source)) or "")

    def test_ac8_operator_session_doc_describes_spec_gate_mandate_order(self):
        """`docs/operator-session.md`: тот же порядок мандата на гейте SPEC и оговорка о reject.

        Ловит мутацию: правку сделали только в справке `artel.py`, документ
        сессии Оператора не тронут — окна с `answer` на гейте SPEC в нём нет.
        """
        text = (ROOT / "docs" / "operator-session.md").read_text(encoding="utf-8")
        self.assert_described("docs/operator-session.md", text)


if __name__ == "__main__":
    unittest.main()
