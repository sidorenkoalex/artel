"""AC-5 — 01M3H3JRBD544GQ10SS3DBGEVP: охват analyst в постоянных тестах и
неослабление названных файлов.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. Тесты подтверждают включение analyst в перечень, строки входа и
дома роли для analyst на Codex и отсутствие строк Codex на пульте без
Codex; `tests/test_doctor.py`, `tests/test_models_doctor.py`,
`tests/test_providers.py`, `tests/test_providers_codex.py` и
`tests/test_runner_model_preflight.py` остаются зелёными и не
ослабляются.

Критерий распадается на три половины с разной проверяемостью, и все три
проверяются здесь исполнением:

1. «Тесты подтверждают …» — структурно: среди тестовых методов `tests/`
   обязан найтись метод на каждое из четырёх названных свойств. Сверка
   текстовая (по исходнику метода), потому что предмет — САМО НАЛИЧИЕ
   постоянного теста, а не его вердикт: вердикт даёт прогон ниже.
2. «остаются зелёными» — прогон ровно этих пяти файлов отдельным
   процессом pytest. Это не полный набор `tests/` (его гоняет CI, и
   skills/test-authoring.md запрещает автору планки его прогон) — это
   тесты затронутых задачей модулей, названные критерием поимённо.
3. «не ослабляются» — состав тестовых методов пяти файлов сверяется с их
   составом в ТОЧКЕ РАСХОЖДЕНИЯ ветки с main (не с сегодняшним диском:
   набор, из которого метод убрали веткой, иначе сузился бы сам собой), и
   ни один уцелевший метод не выключен пропуском.

Красен до реализации: постоянных тестов на включение analyst в перечень и
на его строки Codex в `tests/` нет ни одного — структурная половина
краснеет по всем трём свойствам про analyst. Остальные половины — тесты
сохранения существующего поведения: они краснеют, если правка удалит,
переименует, заглушит или уронит чужой тест.
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, doctor, gitcmd, stack  # noqa: E402

from _analyst import ANALYST  # noqa: E402

#: Файлы, названные критерием поимённо.
NAMED_SUITES = (
    "tests/test_doctor.py",
    "tests/test_models_doctor.py",
    "tests/test_providers.py",
    "tests/test_providers_codex.py",
    "tests/test_runner_model_preflight.py",
)

_SKIP_DECORATORS = ("skip", "skipIf", "skipUnless", "expectedFailure")

#: Как тест может адресовать перечень ролей предполёта.
LIST_MARKERS = ("agent_roles",)
#: Как тест может адресовать строку подписочного входа Codex — значением
#: имени строки либо любым из её адресов в коде: константа и функция
#: переименованию не подлежат молча, но писать тест вправе через любую.
LOGIN_MARKERS = (doctor.CODEX_AUTH_CHECK, "CODEX_AUTH_CHECK",
                 "check_codex_chatgpt_auth")
#: То же для строки сверки развёрнутого дома роли Codex.
HOME_MARKERS = ("codex-role-home", "check_codex_role_home")

#: Потолок прогона пяти файлов: заведомо ниже таймаута ОТДЕЛЬНОГО теста
#: планки (`stack.PER_TEST_TIMEOUT_SEC` — крутилка пульта, не литерал),
#: чтобы истёкший прогон отказывал названной причиной, а не обрывался
#: таймаутом раннера без диагностики.
SUITE_TIMEOUT_SEC = stack.PER_TEST_TIMEOUT_SEC * 3 // 4


def method_sources(source: str) -> dict:
    """{`Класс.метод`: исходник метода} тестовых методов модуля."""
    found = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and item.name.startswith("test"):
                found[f"{node.name}.{item.name}"] = ast.get_source_segment(
                    source, item) or ""
    return found


def _decorator_names(node) -> list:
    names = []
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        names.append(target.attr if isinstance(target, ast.Attribute)
                     else getattr(target, "id", ""))
    return names


def skipped_methods(source: str) -> set:
    """{`Класс.метод`} тестовых методов, выключенных декоратором
    `unittest.skip*`/`expectedFailure` (на методе или на его классе) либо
    вызовом `self.skipTest(...)` в теле."""
    skipped = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ClassDef):
            continue
        class_skipped = any(name in _SKIP_DECORATORS
                            for name in _decorator_names(node))
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not item.name.startswith("test"):
                continue
            body_skips = any(
                isinstance(call.func, ast.Attribute)
                and call.func.attr == "skipTest"
                for call in ast.walk(item) if isinstance(call, ast.Call))
            if class_skipped or body_skips or any(
                    name in _SKIP_DECORATORS for name in _decorator_names(item)):
                skipped.add(f"{node.name}.{item.name}")
    return skipped


def merge_base() -> str:
    """sha точки расхождения ветки задачи с базой интеграции: `origin/main`,
    а при его отсутствии — локальная основная ветка."""
    for ref in (f"origin/{config.MAIN_BRANCH}", config.MAIN_BRANCH):
        res = subprocess.run(["git", "merge-base", ref, "HEAD"],
                             cwd=config.ROOT, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    raise AssertionError("точка расхождения ветки с main не вычислена — "
                         "сверять состав тестов не с чем")


def all_test_sources() -> dict:
    """{`файл::Класс.метод`: исходник} по всем `tests/*.py` ветки."""
    found = {}
    for path in sorted((config.ROOT / "tests").glob("test_*.py")):
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(config.ROOT)
        for name, body in method_sources(source).items():
            found[f"{rel}::{name}"] = body
    return found


class AnalystCoverageTest(unittest.TestCase):
    """Постоянные тесты `tests/`, подтверждающие охват analyst."""

    @classmethod
    def setUpClass(cls):
        cls.sources = all_test_sources()

    def covered(self, *groups) -> list:
        """Тестовые методы, чей исходник содержит хотя бы один маркер из
        КАЖДОЙ группы (группа — набор равноправных способов адресовать
        одно и то же)."""
        return sorted(
            name for name, body in self.sources.items()
            if all(any(marker in body for marker in group) for group in groups))

    def test_ac5_permanent_tests_cover_the_analyst_list_and_its_codex_lines(self):
        """В `tests/` есть постоянный тест на каждое из четырёх свойств
        критерия: analyst в перечне ролей, строка подписочного входа
        analyst на Codex, строка дома роли Codex для него и отсутствие
        строк Codex на пульте без Codex.

        Ловит мутацию: охват оставлен приёмочной планкой этой задачи
        («планка же зелёная») — планка уходит вместе с каталогом задачи, и
        следующая правка перечня ролей или склейки провайдерских строк
        снова уводит analyst из предполёта молча, как уже увела его смена
        провайдера. Непокрытое свойство будет названо.
        """
        wanted = {
            "analyst в перечне ролей предполёта": ((ANALYST,), LIST_MARKERS),
            "строка входа Codex для analyst": ((ANALYST,), LOGIN_MARKERS),
            "строка дома роли Codex для analyst": ((ANALYST,), HOME_MARKERS),
            "отсутствие строк Codex на пульте без Codex": (
                ("assertNotIn",), LOGIN_MARKERS + HOME_MARKERS),
        }

        uncovered = [what for what, groups in wanted.items()
                     if not self.covered(*groups)]

        self.assertEqual(
            [], uncovered,
            "свойства критерия без постоянного теста в tests/: "
            + "; ".join(uncovered))


class NamedSuitesTest(unittest.TestCase):
    """Пять названных файлов: зелёные и не ослабленные."""

    def local_source(self, rel: str) -> str:
        path = config.ROOT / rel
        self.assertTrue(path.is_file(), f"{rel}: файла нет в ветке")
        return path.read_text(encoding="utf-8")

    def baseline_source(self, base: str, rel: str) -> str:
        text, reason = gitcmd.show(base, rel)
        self.assertIsNotNone(
            text, f"{base}:{rel} не прочитан: {reason} — файл обязан "
                  f"существовать в точке расхождения")
        return text

    def test_ac5_named_suites_stay_green(self):
        """Прогон ровно пяти названных файлов отдельным процессом pytest
        завершается кодом 0.

        Ловит мутацию: смена источника перечня ролей ломает существующий
        тест, опирающийся на прежний состав (`tests/test_providers.py`
        сверяет число строк `token` с длиной перечня, а
        `tests/test_providers_codex.py` — что ни одна роль пульта не идёт
        на `codex`), и это остаётся незамеченным до CI: хвост вывода
        pytest назовёт упавший тест здесь.
        """
        command = [sys.executable, "-m", "pytest", *NAMED_SUITES, "-q",
                   "-p", "no:cacheprovider"]
        try:
            res = subprocess.run(command, cwd=config.ROOT, capture_output=True,
                                 text=True, timeout=SUITE_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            self.fail(f"прогон названных файлов не уложился в "
                      f"{SUITE_TIMEOUT_SEC}с — тест зависает либо ждёт сеть")

        self.assertEqual(res.returncode, 0,
                         (res.stdout + res.stderr)[-3000:])

    def test_ac5_named_suites_keep_every_test_method(self):
        """Каждый тестовый метод пяти файлов, существовавший в точке
        расхождения ветки с main, существует в ветке под тем же именем.

        Ловит мутацию: тест, покрасневший от нового перечня ролей
        (например `tests/test_providers_codex.py::…_a_pult_without_a_codex_
        role_gets_neither_the_line_nor_the_call`), удалён или переименован
        вместо приведения к новому поведению — исчезнувшее имя будет
        названо.
        """
        base = merge_base()
        gone = []
        for rel in NAMED_SUITES:
            before = set(method_sources(self.baseline_source(base, rel)))
            after = set(method_sources(self.local_source(rel)))
            gone.extend(f"{rel}::{name}" for name in sorted(before - after))

        self.assertEqual(
            [], gone,
            "тестовые методы точки расхождения исчезли из ветки — удаление "
            "или переименование теста это ослабление проверки (AC-5): "
            + ", ".join(gone))

    def test_ac5_no_named_suite_method_is_skipped(self):
        """Ни один тестовый метод пяти файлов не выключен
        `unittest.skip*`/`expectedFailure`/`self.skipTest(...)`.

        Ловит мутацию: тест, мешающий новому перечню ролей, заглушен
        `@unittest.skip("починим позже")` — прогон остаётся зелёным, а
        проверка исчезает; имя заглушённого метода будет названо.
        """
        muted = []
        for rel in NAMED_SUITES:
            muted.extend(f"{rel}::{name}" for name
                         in sorted(skipped_methods(self.local_source(rel))))

        self.assertEqual(
            [], muted,
            "тестовые методы выключены пропуском вместо приведения к новому "
            "поведению (AC-5): " + ", ".join(muted))


if __name__ == "__main__":
    unittest.main()
