"""Приёмочные тесты T102 — AC-1..AC-5 (tasks/T102/SPEC.md): `new`
отказывает на нераспознанном вводе ДО расходования номера задачи и до
создания ветки/worktree, называя нераспознанное и показывая правильную
форму вызова.

Красен до реализации: сегодня `orchestrator/artel.py` разбирает `new`
как `catalog.cmd_new(rest[0], tz_path=_tz_arg(rest))` — первый
позиционный аргумент становится названием, всё остальное нераспознанное
(лишний позиционный AC-1, неизвестный флаг AC-2, `--help`/`-h` как
название AC-3, название с `-` AC-5) молча проглатывается, и `cmd_new`
доходит до конца ЦЕЛИКОМ — заводит настоящую задачу с мусорным
названием (буквально инциденты T097/T098/T099 из «Контекста» SPEC.md).
Поэтому песочница здесь — тот же полный стенд, что и в
`test_new_regression_existing_forms.py` (копия `templates/`, `fake_git`
вместо `gitcmd.git`, `cmd_init`): без него сегодняшний баг не
воспроизвести — разбор долетел бы до настоящего git на не-репозитории и
упал по СОВСЕМ другой причине, чем отсутствие кода задачи. `new` совсем
без аргументов (AC-4) — особый случай: сегодня `rest[0]` на пустом
списке роняет необработанный `IndexError` ещё до вызова `cmd_new`
(тест падает ошибкой, не проваленным assert-ом — тот же диагноз: нужного
кода ещё нет).

Форма вызова `new "<название>" [--tz <файл>]` — существующая
каноническая формулировка самой команды (`orchestrator/artel.py`,
докстрока `main()`, строка «Команды:»); тест проверяет, что сообщение
ссылается на неё, а не выдумывает собственную обязательную форму текста
сверх того, что уже документировано.
"""
import io
import shutil
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artel, catalog, config, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest, fake_git  # noqa: E402

USAGE_FORM = 'new "<название>"'


class NewRejectsUnrecognizedArgsTest(TmpRootTest):
    """Полный стенд (`templates/` + `fake_git` + `cmd_init`) — сегодняшний
    баг (AC-1/2/3/5) не молча «ничего не делает», а доходит до конца
    `cmd_new` и заводит настоящую задачу; без рабочего git-пути этот
    прогон падал бы по не относящейся к задаче причине (настоящий git
    на каталоге без `.git`), маскируя дефект, который эта задача чинит."""

    PATCHED_ATTRS = ("DB", "TASKS", "LOGS", "WORKTREES", "ROOT")

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.capture(catalog.cmd_init)

    def _invoke_new(self, rest: list) -> tuple:
        """Гоняет `artel.py new <rest...>` через `main()`; возвращает
        (объединённый_текст, SystemExit|None). Объединённый текст —
        stdout ПЛЮС сообщение исключения, потому что сегодня неизвестно,
        каким из двух каналов реализация T102 донесёт форму вызова и
        имя нераспознанного аргумента до Оператора."""
        buf = io.StringIO()
        exc = None
        with mock.patch.object(sys, "argv", ["artel.py", "new", *rest]):
            try:
                with redirect_stdout(buf):
                    artel.main()
            except SystemExit as e:
                exc = e
        message = "" if exc is None or exc.code is None else str(exc.code)
        return buf.getvalue() + message, exc

    def _assert_no_task_spent(self) -> None:
        conn = store.db()
        self.assertIsNone(
            conn.execute("SELECT 1 FROM tasks WHERE id='T001'").fetchone(),
            "отказ не должен был создать задачу T001")
        self.assertEqual(
            store.peek_task_number(conn, config.DEFAULT_TARGET), 1,
            "счётчик номеров задач не должен быть израсходован отказом")
        self.assertFalse(
            (config.WORKTREES / "T001").exists(),
            "отказ не должен был завести worktree/ветку задачи")

    # ------------------------------------------------------------ AC-1

    def test_ac1_extra_positional_argument_rejected_before_task_created(self):
        text, exc = self._invoke_new(["Название", "лишнее"])

        self.assertIsNotNone(
            exc, "лишний позиционный аргумент обязан отказывать (SystemExit)")
        self.assertIn("лишнее", text,
                      "сообщение обязано называть нераспознанный аргумент")
        self.assertIn(USAGE_FORM, text,
                      "сообщение обязано показывать правильную форму вызова")
        self._assert_no_task_spent()

    # ------------------------------------------------------------ AC-2

    def test_ac2_unknown_flag_rejected_before_task_created(self):
        text, exc = self._invoke_new(["Название", "--unknown"])

        self.assertIsNotNone(
            exc, "неизвестный флаг обязан отказывать (SystemExit)")
        self.assertIn("--unknown", text,
                      "сообщение обязано называть нераспознанный флаг")
        self.assertIn(USAGE_FORM, text,
                      "сообщение обязано показывать правильную форму вызова")
        self._assert_no_task_spent()

    # ------------------------------------------------------------ AC-3

    def test_ac3_help_long_flag_prints_usage_without_task(self):
        text, _exc = self._invoke_new(["--help"])

        self.assertIn(USAGE_FORM, text,
                      "`new --help` обязан печатать правильную форму вызова")
        self._assert_no_task_spent()

    def test_ac3_help_short_flag_prints_usage_without_task(self):
        text, _exc = self._invoke_new(["-h"])

        self.assertIn(USAGE_FORM, text,
                      "`new -h` обязан печатать правильную форму вызова")
        self._assert_no_task_spent()

    # ------------------------------------------------------------ AC-4

    def test_ac4_no_arguments_prints_usage_without_task(self):
        text, _exc = self._invoke_new([])

        self.assertIn(USAGE_FORM, text,
                      "`new` без аргументов обязан печатать форму вызова")
        self._assert_no_task_spent()

    # ------------------------------------------------------------ AC-5

    def test_ac5_dash_prefixed_short_flag_like_title_rejected(self):
        """«-x» — нераспознанный флаг, не `--help`/`-h`: единственный из
        двух примеров SPEC, отличающий AC-5 от AC-3 буквально (второй
        пример SPEC, «--help», как единственный аргумент уже целиком
        описан отдельным критерием AC-3 — см.
        test_ac5_dash_prefixed_help_like_title_not_created_as_task ниже,
        который проверяет только общий для обоих критериев инвариант «не
        стало названием задачи», не переопределяя точный путь отказа,
        закреплённый AC-3)."""
        text, exc = self._invoke_new(["-x"])

        self.assertIsNotNone(
            exc, "название, начинающееся с «-», обязано отказывать")
        self.assertIn("-x", text,
                      "сообщение обязано называть нераспознанный аргумент")
        self.assertIn(USAGE_FORM, text,
                      "сообщение обязано показывать правильную форму вызова")
        self._assert_no_task_spent()

    def test_ac5_dash_prefixed_help_like_title_not_created_as_task(self):
        """`new "--help"` — второй пример AC-5. Тот же argv, что и AC-3
        `new --help`: этим токеном нельзя стать названием задачи ни в
        одном из двух прочтений (форма справки по AC-3, либо отказ по
        AC-5) — тест проверяет только это общее пересечение, не
        конкретный канал (SystemExit/return), который остаётся за
        AC-3."""
        _text, _exc = self._invoke_new(["--help"])

        conn = store.db()
        self.assertIsNone(
            conn.execute(
                "SELECT 1 FROM tasks WHERE title='--help'").fetchone(),
            "«--help» не должен был стать названием задачи (T097)")
        self._assert_no_task_spent()


if __name__ == "__main__":
    unittest.main()
