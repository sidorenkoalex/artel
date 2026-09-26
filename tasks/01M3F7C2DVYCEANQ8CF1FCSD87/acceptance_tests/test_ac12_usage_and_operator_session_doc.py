"""AC-12: строка команды в usage пульта и в `docs/operator-session.md`.

Красен до реализации: ни текст usage `orchestrator/artel.py` (модульный
докстринг, который печатает `main` без аргументов), ни `docs/operator-session.md`
сегодня слова `ci-rerun` не содержат вовсе — обе сверки падают на отсутствии
строки.

Usage читается ИМПОРТОМ (`artel.__doc__`), а не разбором файла: usage —
это именно тот текст, который команда `artel.py` без аргументов печатает
Оператору. `docs/operator-session.md` — файл репозитория (не артефакт
задачи), читается с `REPO_ROOT` тем же приёмом, что и планки
01M2XMCC837R5CX9M58VARK85G/01M28NX0M2WTVC38XVN75N01XD.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artel  # noqa: E402

DOC = REPO_ROOT / "docs" / "operator-session.md"


class UsageAndDocTest(unittest.TestCase):

    def test_ac12_usage_carries_ci_rerun_command_line(self):
        """Текст usage несёт строку `ci-rerun <id> --reason "<основание>"`.

        Одна строка usage обязана назвать и команду, и её обязательный флаг —
        тем же видом, каким там уже стоит родственная `amend-tests <id>
        --reason "<основание>"`.

        Ловит мутацию: команда добавлена в таблицу диспетчера
        `orchestrator/artel.py`, но забыта в usage (либо названа там без
        `--reason`) — Оператор не узнаёт о ней и об обязательности основания
        из справки пульта.
        """
        usage = artel.__doc__ or ""
        lines = [line for line in usage.splitlines() if "ci-rerun" in line]

        self.assertTrue(
            lines,
            "текст usage orchestrator/artel.py не называет команду ci-rerun")
        self.assertTrue(
            any("--reason" in line for line in lines),
            f"строка usage команды обязана нести обязательный флаг "
            f"--reason; найдено: {lines}")

    def test_ac12_operator_session_doc_carries_command_and_main_rule(self):
        """`docs/operator-session.md` несёт строку о команде и правило main.

        Документ сессии Оператора — единственное место, откуда Оператор
        узнаёт не только о существовании команды, но и о правиле «красно и
        на main — не перезапускать»: без него команда читается как кнопка
        «жать до зелёного», ровно тот маскирующий дефект главной ветки
        повтор, против которого задача и заведена.

        Ловит мутацию: в документ добавлена только строка о команде, без
        правила про красноту main (или наоборот) — вторая сверка падает.
        """
        text = DOC.read_text(encoding="utf-8")

        # `assertTrue`, а не `assertIn`: сообщение `assertIn` вывалило бы в
        # отчёт весь документ сессии Оператора целиком.
        self.assertTrue(
            "ci-rerun" in text,
            f"{DOC.name} не называет команду ci-rerun")
        rule_lines = [line for line in text.splitlines()
                      if "main" in line and "перезапус" in line.lower()]
        self.assertTrue(
            rule_lines,
            f"{DOC.name} не несёт правила «красно и на main — не "
            f"перезапускать»")


if __name__ == "__main__":
    unittest.main()
