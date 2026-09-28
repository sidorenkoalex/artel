"""AC-12 — раздел паритета безопасности роли `docs/stack.md`: строка про
защищённые настройки сбора тестов есть, таблица паритета не тронута, её
сторож зелёный.

Источник — SPEC.md, «Критерии приёмки»:

AC-12. Раздел «Паритет безопасности роли…» `docs/stack.md` несёт строку,
называющую `conftest.py` и `pyproject.toml` защищёнными настройками
сбора тестов; таблица паритета в этом разделе не изменена, и
`tests/test_stack_parity_table.py` зелёный.

«Строка» ищется АБЗАЦЕМ, а не физической строкой файла: проза документа
жёстко переносится по ~72 символам, и одно предложение критерия неизбежно
ляжет на три-четыре строки — поиск по физической строке требовал бы от
разработчика сложить `conftest.py`, `pyproject.toml` и слово
«защищённые» в одну строку вопреки формату документа.

«Таблица не изменена» проверяется ДИФФОМ задачи, а не снимком строк
таблицы: снимок утверждал бы сегодняшний состав чужой таблицы, которую
Оператор правит своими задачами, и краснел бы от их законного развития.
База диффа — `gitcmd.diff_base` (точка расхождения с `origin/<основная>`,
не с локальной веткой: локальная отстаёт от origin на всё смерженное
после пина, и дифф от неё принёс бы чужие правки `docs/stack.md`), и
считается она в ЧЕКАУТЕ ПЛАНКИ (`repo=`), а не в `config.ROOT`: пульт
гоняет планку и из worktree задачи, чей HEAD — ветка задачи, тогда как
HEAD главной копии стоит на пине.

Красен до реализации: строки (абзаца) про настройки сбора тестов в разделе паритета `docs/stack.md` ещё нет — `test_ac12_parity_section_names_test_settings_as_protected` падает.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _protected  # noqa: E402
from orchestrator import gitcmd  # noqa: E402

STACK_MD_REL = "docs/stack.md"
STACK_MD = _protected.REPO_ROOT / "docs" / "stack.md"
PARITY_TABLE_SENTINEL_REL = "tests/test_stack_parity_table.py"

#: Раздел ищется по НАЧАЛУ заголовка, а не по имени целиком: хвост
#: формулировки («…: запрет у Claude → чем закрыт у Codex») — проза
#: Оператора, и планка не обязана её замораживать.
_PARITY_SECTION = re.compile(
    r"^##\s+Паритет безопасности роли.*?$(.*?)(?=^##\s|\Z)", re.M | re.S)

#: Подстроки, которые обязан нести абзац критерия: оба имени файла и
#: корень слова «защищённый» (обе орфографии — с «ё» и без).
_REQUIRED_SUBSTRINGS = ("conftest.py", "pyproject.toml")
_PROTECTED_WORDS = ("защищённ", "защищен")


def _parity_section_body() -> str:
    text = STACK_MD.read_text(encoding="utf-8")
    match = _PARITY_SECTION.search(text)
    return match.group(1) if match else ""


def _prose_paragraphs(body: str) -> list:
    """Абзацы тела раздела БЕЗ строк таблицы: строка таблицы — не проза, а
    правка самой таблицы, которую вторая половина критерия запрещает."""
    prose_lines = [line for line in body.splitlines()
                   if not line.lstrip().startswith("|")]
    paragraphs, current = [], []
    for line in prose_lines:
        if line.strip():
            current.append(line)
            continue
        if current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


class ParityProseTest(unittest.TestCase):

    def test_ac12_parity_section_names_test_settings_as_protected(self):
        """Раздел паритета `docs/stack.md` несёт абзац прозы, в котором
        разом названы `conftest.py`, `pyproject.toml` и защищённость.

        Ловит мутацию: строку вписали в другой раздел документа (например
        в «Модели: каталог, ярусы, тариф» ниже или в вводную прозу
        документа) — то есть паритет безопасности роли Codex остаётся без
        объяснения, чем закрыт обход через подмену окружения pytest.
        Наблюдаемое расхождение: поиск по абзацам ИМЕННО этого раздела
        ничего не находит, и `assertTrue` краснеет, хотя слово
        `conftest.py` в файле присутствует.
        """
        body = _parity_section_body()
        self.assertTrue(
            body,
            f"{STACK_MD_REL}: раздел «Паритет безопасности роли…» не найден "
            f"— искать строку критерия негде")

        paragraphs = _prose_paragraphs(body)
        matching = [p for p in paragraphs
                    if all(s in p for s in _REQUIRED_SUBSTRINGS)
                    and any(w in p for w in _PROTECTED_WORDS)]
        self.assertTrue(
            matching,
            f"{STACK_MD_REL}, раздел «Паритет безопасности роли…»: ни один "
            f"абзац прозы не называет разом conftest.py, pyproject.toml и "
            f"защищённость. Абзацы раздела: {paragraphs}")

    def test_ac12_parity_table_rows_are_untouched_by_the_task_diff(self):
        """Дифф задачи по `docs/stack.md` не добавляет и не удаляет ни
        одной строки таблицы (строки, начинающейся с `|`).

        Ловит мутацию: строку критерия вписали НОВОЙ строкой таблицы
        паритета (заманчиво: раздел — про таблицу) либо дописали её в
        ячейку существующей строки «Посторонние файлы и защищённые пути».
        Наблюдаемое расхождение: в `git diff <база> -- docs/stack.md`
        появляется строка, начинающаяся с `+|` или `-|`; сторож
        `tests/test_stack_parity_table.py` при этом остаётся зелёным
        (запрет он опознаёт по подстрокам), то есть без этой проверки
        правка таблицы прошла бы молча.
        """
        # `repo=` обязателен: без него `diff_base` считает merge-base в
        # `config.ROOT` (главная копия пульта, её HEAD — пин, а не ветка
        # задачи), а `git diff` ниже идёт в чекауте самой планки — база и
        # дифф разъехались бы по разным деревьям.
        base = gitcmd.diff_base("HEAD", repo=_protected.REPO_ROOT)
        self.assertIsNotNone(
            base,
            "git не ответил на определение базы сравнения (merge-base с "
            "origin/<основная> либо локальной) — сверять дифф не с чем")

        res = subprocess.run(
            ["git", "diff", base, "--", STACK_MD_REL],
            cwd=_protected.REPO_ROOT, capture_output=True, text=True,
            timeout=60)
        self.assertEqual(
            0, res.returncode,
            f"git diff {base} -- {STACK_MD_REL} отказал: {res.stderr}")

        changed_table_rows = [line for line in res.stdout.splitlines()
                              if line[:2] in ("+|", "-|")]
        self.assertEqual(
            [], changed_table_rows,
            f"дифф задачи меняет строки таблицы паритета {STACK_MD_REL} — "
            f"критерий требует тронуть только прозу раздела")

    def test_ac12_parity_table_sentinel_is_green(self):
        """Сторож таблицы паритета `tests/test_stack_parity_table.py`
        проходит на дереве задачи — отдельным прогоном pytest в корне
        репозитория.

        Ловит мутацию: строку вписали внутрь таблицы так, что разбор
        сторожа принял её за строку-запрет без имени живой проверки
        `doctor` и без честной пометки «не закрыт» (его AC-2). Наблюдаемое
        расхождение: код возврата прогона становится ненулевым, и планка
        краснеет — тогда как проверка диффа выше видит только факт правки
        таблицы, а не её последствие для сторожа.
        """
        res = subprocess.run(
            [sys.executable, "-m", "pytest", PARITY_TABLE_SENTINEL_REL,
             "-p", "no:cacheprovider", "-q"],
            cwd=_protected.REPO_ROOT, capture_output=True, text=True,
            timeout=90)
        self.assertEqual(
            0, res.returncode,
            f"{PARITY_TABLE_SENTINEL_REL} красный:\n"
            f"{res.stdout[-3000:]}\n{res.stderr[-3000:]}")


if __name__ == "__main__":
    unittest.main()
