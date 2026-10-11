"""AC-11: Инвариант входа «пульт исполняется только из главной копии, не
из git-worktree» (`orchestrator/artel.py::_refuse_if_worktree`, T056) не
изменён и не ослаблен — существующий тест на него остаётся зелёным без
правки его проверяемого утверждения.

Эта задача (A7) меняет соседнюю механику того же файла (`_cmd_approve_
merge_gate`, доступ к `config.ROOT` при `approve`) — реальный риск
регрессии именно T056: правка, трогающая порядок ранних проверок
`artel.main()`/область видимости `config.ROOT`, могла бы задеть
`_refuse_if_worktree` побочно. Тест ниже — не пересказ существующего
`tests/test_invariants.py::MainCopyGuardTest` (импортировать и повторно
прогнать ЕГО файл из этого небезопасно: оба несут одноимённый локальный
модуль `_sandbox.py` в РАЗНЫХ каталогах — `python3 -m unittest discover`
грузит все файлы `acceptance_tests/` ОДНИМ процессом, и второй импорт
`_sandbox` подхватил бы уже закэшированный чужой модуль), а
самостоятельная проверка ТОГО ЖЕ утверждения тем же приёмом (фейковый
gitlink-файл `ROOT/.git`, без реального `git worktree add`) — если
разработчик тронет `_refuse_if_worktree` или порядок вызова в `artel.
main()`, этот тест покраснеет независимо от `tests/test_invariants.py`.

Зелёный с рождения: `_refuse_if_worktree` эта задача не меняет — тесты
ниже проверяют СУЩЕСТВУЮЩЕЕ поведение (сверено с `tests/test_invariants.
py::MainCopyGuardTest`, прецедент-тест инварианта T056) и обязаны
проходить уже сегодня; их красный цвет после реализации A7 — сигнал
регрессии этого инварианта, а не ожидаемое состояние «до реализации».
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import artel, config  # noqa: E402


class WorktreeInvariantStillRefusesAfterA7Test(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.sandbox = Path(tmp.name).resolve()
        self.main_copy = self.sandbox / "main"
        self.worktree = self.sandbox / "worktree"
        self.worktree.mkdir(parents=True)
        (self.worktree / ".git").write_text(
            f"gitdir: {self.main_copy}/.git/worktrees/T001\n", encoding="utf-8")

    def test_ac11_worktree_root_still_refuses_via_main(self):
        """`artel.main()`, запущенный с `config.ROOT`, указывающим на
        git-worktree (файл-ссылка `ROOT/.git`), по-прежнему отказывает
        `SystemExit` с сообщением, называющим и worktree, и главную
        копию — не проходит ни при каком аргументе команды.

        Ловит мутацию: любую правку `artel.main()`/диспетчера команд A7
        (например перенос вызова `_refuse_if_worktree()` ПОСЛЕ разбора
        аргументов, затрагивающих новую команду обновления пина, AC-14),
        из-за которой guard перестаёт срабатывать РАНЬШЕ остальной
        логики — тест перестанет ловить `SystemExit` или потеряет
        сообщение.
        """
        with mock.patch.object(config, "ROOT", self.worktree), \
             mock.patch.object(sys, "argv", ["artel.py", "status"]):
            with self.assertRaises(SystemExit) as ctx:
                artel.main()

        message = str(ctx.exception)
        self.assertIn(str(self.worktree), message)
        self.assertIn(str(self.main_copy), message)
        self.assertIn("перезапуст", message.lower())

    def test_ac11_main_copy_directory_is_still_not_refused(self):
        """Контроль: обычный каталог (`.git` — каталог, не файл) — guard
        не срабатывает, `_refuse_if_worktree()` не бросает."""
        (self.main_copy / ".git").mkdir(parents=True)

        with mock.patch.object(config, "ROOT", self.main_copy):
            try:
                artel._refuse_if_worktree()
            except SystemExit:
                self.fail("guard отказал в главной копии — A7 не должна "
                         "была это изменить")

    def test_ac11_sandbox_without_dot_git_is_still_not_refused(self):
        """Контроль: временный каталог без `.git` вовсе (обычная тестовая
        песочница A7 — `RealGitSandbox`/`ArtelSelfTargetSandbox` этой же
        задачи) — guard не срабатывает."""
        bare = self.sandbox / "bare"
        bare.mkdir()

        with mock.patch.object(config, "ROOT", bare):
            try:
                artel._refuse_if_worktree()
            except SystemExit:
                self.fail("guard отказал вне worktree и вне главной "
                         "копии — A7 не должна была это изменить")


if __name__ == "__main__":
    unittest.main()
