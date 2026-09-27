"""AC-12 задачи 01M3FQ3JVC3DGGM33XCX8TC7ME — раздел «Запуски и рабочие
копии» docs/operator-session.md и неослабление существующих тестов.

Красен до реализации: раздел «Запуски и рабочие копии» не называет ни
флага осознанного принятия красного набора, ни каталога, где лежит лог
полного набора, — ни того, ни другого ещё нет.

Зелёный с рождения: методы про существующие tests/test_fsm_autogate.py,
tests/test_acceptance.py, tests/test_plan_appendix.py — тесты сохранения:
эти файлы зелёные и сегодня, и критерий требует их такими оставить.
"""
import ast
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

REPO_ROOT = Path(__file__).resolve().parents[3]
SESSION_DOC_REL = "docs/operator-session.md"
SECTION_TITLE = "Запуски и рабочие копии"

# Файлы набора, которые критерий требует оставить зелёными и не
# ослабленными, и их замеры на момент написания планки: (число тестовых
# методов, число ассертов). Оба — нижние границы: расти можно, убывать
# нельзя.
EXISTING_SUITE_BASELINE = {
    "tests/test_fsm_autogate.py": (17, 34),
    "tests/test_acceptance.py": (10, 21),
    "tests/test_plan_appendix.py": (30, 76),
}

ASSERT_CALL = re.compile(r"\bassert\w*\(")


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _section_body(text: str, title: str) -> str:
    """Тело раздела `## <title>` до следующего заголовка `## ` — тот же
    приём, что `guard.section_body` применяет к артефактам."""
    lines = text.splitlines()
    body: list[str] = []
    inside = False
    for line in lines:
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip() == title
            continue
        if inside:
            body.append(line)
    return "\n".join(body)


def _test_method_count(source: str) -> int:
    tree = ast.parse(source)
    return sum(1 for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name.startswith("test_"))


class SessionDocSectionTest(unittest.TestCase):

    def section(self) -> str:
        body = _section_body(_read(SESSION_DOC_REL), SECTION_TITLE)
        self.assertNotEqual(
            body.strip(), "",
            f"в {SESSION_DOC_REL} нет раздела «{SECTION_TITLE}»")
        return body

    def test_ac12_section_names_what_the_acceptance_autogate_checks(self):
        """Раздел называет, что проверяет автогейт приёмки, и что гоняет
        `approve` в acceptance — полный набор tests/ в рабочей копии
        ветки задачи.

        Ловит мутацию: правка документации ограничена флагом (самой
        заметной новинкой), а про то, ЧТО именно теперь гоняется на
        приёмке, в разделе по-прежнему ни слова.
        """
        body = self.section()

        self.assertIn("автогейт", body.lower(),
                      f"раздел «{SECTION_TITLE}» не называет автогейт приёмки")
        self.assertIn("approve", body,
                      f"раздел «{SECTION_TITLE}» не называет approve")
        self.assertIn("tests/", body,
                      f"раздел «{SECTION_TITLE}» не называет полный набор "
                      f"tests/")

    def test_ac12_section_names_how_to_accept_a_red_suite(self):
        """Раздел называет, как принять красный набор осознанно — флагом
        `--accept-red` с основанием.

        Ловит мутацию: флаг заведён в коде и в справке `artel.py`, но
        протокол сессии о нём не знает — Оператор при красном наборе на
        приёмке снова остаётся без описанного выхода.
        """
        body = self.section()

        self.assertIn("--accept-red", body,
                      f"раздел «{SECTION_TITLE}» не называет флаг осознанного "
                      f"принятия красного набора")

    def test_ac12_section_names_where_the_full_suite_log_lives(self):
        """Раздел называет, где лежит лог полного набора — каталог логов
        ролей `.artel/logs`.

        Ловит мутацию: путь лога назван только в detail записи журнала —
        чтобы узнать, куда смотреть, Оператору сначала нужно получить
        отказ.
        """
        body = self.section()

        self.assertIn(".artel/logs", body,
                      f"раздел «{SECTION_TITLE}» не называет каталог, где "
                      f"лежит лог полного набора")


class ExistingSuiteNotWeakenedTest(unittest.TestCase):

    def test_ac12_existing_test_files_stay_green(self):
        """Три файла набора, которых задача касается (автогейт, прогон
        приёмки, приложения PLAN), проходят целиком после правки.

        Ловит мутацию: разбор вывода подменил возврат `run_full_suite` с
        `(bool, str)` на что-то иное, и существующие тесты этих модулей
        падают — «не ослаблены» превращается в «переписаны под новый
        возврат».
        """
        res = subprocess.run(
            [sys.executable, "-m", "pytest", *EXISTING_SUITE_BASELINE, "-q",
             "-p", "no:cacheprovider", "-p", "timeout", "-o", "timeout=120"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=600)

        self.assertEqual(res.returncode, 0,
                         "существующие тесты не зелёные:\n"
                         + (res.stdout + res.stderr)[-3000:])

    def test_ac12_existing_test_files_did_not_lose_tests_or_asserts(self):
        """Ни число тестовых методов, ни число ассертов в этих файлах не
        уменьшилось против замера на момент написания планки: зелёность
        достигается правкой кода, не снятием проверок.

        Ловит мутацию: тест, мешающий новой форме detail (например,
        `assertEqual` на прежнюю константную фразу автогейта), удалён или
        его ассерт выкинут вместо того, чтобы обновить сам detail через
        Оператора.
        """
        for rel, (tests_floor, asserts_floor) in EXISTING_SUITE_BASELINE.items():
            source = _read(rel)
            with self.subTest(file=rel):
                self.assertGreaterEqual(
                    _test_method_count(source), tests_floor,
                    f"{rel}: тестовых методов стало меньше {tests_floor}")
                self.assertGreaterEqual(
                    len(ASSERT_CALL.findall(source)), asserts_floor,
                    f"{rel}: ассертов стало меньше {asserts_floor}")


if __name__ == "__main__":
    unittest.main()
