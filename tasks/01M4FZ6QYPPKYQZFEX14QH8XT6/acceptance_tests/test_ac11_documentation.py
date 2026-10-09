"""Документация фоновых запусков описывает запуск без пары клиент/чат.

Группа: разовый
Красен до реализации: раздел «Фоновые запуски под наблюдением» ведёт `observe register`/`auto` с обязательной парой `--client`/`--chat`, а в `docs/stack.md` нет фразы о контракте запуска с `--observation`.

Документы читаются из рабочей копии кода (`CODE_ROOT` помощника пульта):
это правка `docs/` этой задачи, а не артефакт `tasks/`. Факт задачи —
содержимое текста на момент мержа; дальнейшая законная переписка
документов вправе его менять, поэтому группа — разовая.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

SECTION = "Фоновые запуски под наблюдением"
LAUNCH = re.compile(r"artel\.py\s+(run|auto)\b|observe\s+register\b")
LINE_REF = re.compile(
    r"operator-session\.md:\d+"
    r"|#L\d+"
    r"|\bстрок[аиеуойм]*\s+\d+"
    r"|\bстр\.\s*\d+"
    r"|\bline[s]?\s+\d+", re.IGNORECASE)


def _read(name: str) -> str:
    return (Path(CODE_ROOT) / "docs" / name).read_text(encoding="utf-8")


def _section(text: str) -> str:
    lines = text.splitlines()
    start = level = None
    for i, line in enumerate(lines):
        m = re.match(r"(#+)\s+(.*)", line)
        if m and m.group(2).strip().startswith(SECTION):
            start, level = i, len(m.group(1))
            break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = re.match(r"(#+)\s", lines[j])
        if m and len(m.group(1)) <= level:
            end = j
            break
    return "\n".join(lines[start:end])


def _logical_lines(text: str) -> list:
    """Строки с продолжениями `\\` в конце, склеенные в одну."""
    out, buf = [], ""
    for line in text.splitlines():
        if line.rstrip().endswith("\\"):
            buf += line.rstrip()[:-1] + " "
            continue
        out.append(buf + line)
        buf = ""
    if buf:
        out.append(buf)
    return out


class DocumentationTest(unittest.TestCase):

    def test_ac11_operator_session_and_stack_describe_launch_without_pair(self):
        """Раздел фоновых запусков без обязательной пары и без ссылок на строки; stack.md — фраза о `--observation`.

        В разделе «Фоновые запуски под наблюдением» `docs/operator-session.md`
        ни одна команда `artel.py run|auto` или `observe register` (с
        продолжениями строк `\\`) не несёт `--client`/`--chat` вне
        квадратных скобок необязательной части. Во всём документе нет
        ссылок на его места номерами строк. В `docs/stack.md` есть
        предложение о контракте запуска: в нём `--observation`, запуск
        (`run`/`auto` или «запуск») и пара клиент/чат как необязательная
        (требование 7 SPEC называет эту фразу).

        Ловит мутацию: в порядке раздела осталась прежняя команда
        `auto <id> --client claude --chat …` или `observe register --client …`;
        либо документ ссылается на себя «строка N»; либо фразу о контракте
        запуска в `docs/stack.md` не добавили.
        """
        doc = _read("operator-session.md")
        section = _section(doc)
        self.assertTrue(section, f"нет раздела «{SECTION}»")
        offenders = []
        for line in _logical_lines(section):
            if not LAUNCH.search(line):
                continue
            mandatory = re.sub(r"\[[^\]]*\]", "", line)
            if "--client" in mandatory or "--chat" in mandatory:
                offenders.append(line.strip())
        self.assertEqual(offenders, [], "команды с обязательной парой:\n" + "\n".join(offenders))
        refs = [m.group(0) for m in LINE_REF.finditer(doc)]
        self.assertEqual(refs, [], f"ссылки номерами строк: {refs}")

        stack = re.sub(r"\s+", " ", _read("stack.md"))
        sentences = re.split(r"(?<=[.;!?])\s+(?=[А-ЯA-Z`«(])", stack)
        contract = [s for s in sentences if "--observation" in s
                    and (re.search(r"\b(run|auto)\b", s) or re.search(r"запуск", s, re.I))
                    and re.search(r"клиент|чат|--client|--chat", s, re.I)
                    and re.search(r"не\s?обязат", s, re.I)]
        self.assertTrue(contract, "в docs/stack.md нет фразы о контракте запуска с --observation")


if __name__ == "__main__":
    unittest.main()
