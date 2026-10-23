"""`pin-update`: после успешного сдвига пина главная копия снимает ссылки
отслеживания `origin`, чьих веток в `origin` больше нет
(`git remote prune origin`); сбой уборки сдвиг пина не отменяет, отказ
`pin-update` уборку не вызывает.

Группа: долгоживущий
Красен до реализации: `pin.cmd_pin_update` заканчивается отчётом о циклах и `git remote prune origin` не зовёт — ссылка `origin/task/<x>` без ветки в `origin` остаётся, строк «ссылки origin без ветки на origin сняты: N» и «уборка ссылок origin не выполнена: …» нет (AC-1, AC-2). Метод AC-3 зелен и до реализации — он держит порядок «отказ канарейки раньше уборки», который реализация обязана не сломать.

Планка провалидирована временным стабом уборки в `orchestrator/pin.py` (все методы зелёные, стаб удалён, не закоммичен).

Связка «`pin.cmd_pin_update` — настоящий git главной копии песочницы с bare
`origin` — журнал БД» (`tests.sandbox.SyncedOriginConnSandbox`, тот же
приём, что у `tests/test_pin.py`): целевой sha — коммит, уже лежащий в
`origin`, на который главная копия ещё не сдвинута; «пин сдвинут» — HEAD
главной копии стал этим sha. Подменены только цвет CI
(`ci.main_line_status`) и возраст зелёного прогона канарейки
(`canary.merges_since_last_green_run`); для сбоя и шпиона уборки — запуск
git (`gitcmd.git`, через который идёт и `gitcmd.in_repo`), остальные вызовы
git уходят в настоящий git. Сеть не участвует: `origin` — локальный bare.

Имена веток задач и число живых ссылок порождаются при каждом запуске от
зерна; зерно печатается и входит в текст провала.
"""
import contextlib
import io
import random
import re
import subprocess
import unittest
from unittest import mock

from orchestrator import canary, ci, config, pin, store
from tests.sandbox import SyncedOriginConnSandbox

ULID_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
PRUNED_LINE = "ссылки origin без ветки на origin сняты: "
WARNING_LINE = "уборка ссылок origin не выполнена: "


def is_remote_prune(args) -> bool:
    """Вызов git — `remote prune` (напрямую в главной копии или через
    `-C <путь>` `gitcmd.in_repo`)."""
    words = [str(a) for a in args]
    return "remote" in words and "prune" in words


class PinPruneSandbox(SyncedOriginConnSandbox):
    """Главная копия на старом sha, в `origin` — целевой коммит поверх него;
    у главной копии ссылки `origin/task/*`: одна без ветки в `origin`,
    несколько — с веткой."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        (self.root / "pin_target.txt").write_text(
            f"{self.seed}\n", encoding="utf-8")
        self.git("add", "pin_target.txt")
        self.git("commit", "-q", "-m", "целевой коммит main")
        self.target = self.git("rev-parse", "HEAD").strip()
        self.git("push", "-q", "origin", config.MAIN_BRANCH)
        self.git("reset", "-q", "--hard", "HEAD~1")
        self.old = self.head()
        self.assertNotEqual(self.old, self.target)

        names = set()
        while len(names) < 1 + self.rng.randint(1, 3):
            names.add(self.branch_name())
        names = sorted(names)
        self.rng.shuffle(names)
        self.stale, self.live = names[0], names[1:]
        for name in self.live:
            self.git("push", "-q", "origin",
                     f"{self.old}:refs/heads/task/{name}")
            self.git("update-ref", f"refs/remotes/origin/task/{name}", self.old)
        self.git("update-ref", f"refs/remotes/origin/task/{self.stale}",
                 self.old)
        self.assertIn(self.ref(self.stale), self.tracking_refs(), self.ctx())

    def branch_name(self) -> str:
        ulid = "".join(self.rng.choice(ULID_ALPHABET) for _ in range(26))
        slug = "".join(self.rng.choice("abcdefghijklmnop") for _ in range(6))
        return f"{ulid}-{slug}"

    @staticmethod
    def ref(name: str) -> str:
        return f"refs/remotes/origin/task/{name}"

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def tracking_refs(self) -> set:
        out = self.git("for-each-ref", "--format=%(refname)",
                       "refs/remotes/origin/")
        return {line for line in out.splitlines() if line}

    def ctx(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"

    def pin_journal(self) -> list:
        return [row["action"] for row in store.task_steps(
            self.conn, config.PIN_UPDATE_JOURNAL_TASK_ID)]

    def run_pin_update(self, *, canary_age=0, git_reply=None):
        """`pin.cmd_pin_update(target)` с подменами канарейки и CI;
        `git_reply` — ответ подменённого `git remote prune` (не задан —
        настоящий git). Возвращает (вывод stdout+stderr, код выхода,
        аргументы всех вызовов git)."""
        real_git = pin.gitcmd.git
        calls = []

        def spy(*args):
            calls.append(args)
            if git_reply is not None and is_remote_prune(args):
                return git_reply(args)
            return real_git(*args)

        green = ci.MainLineStatus(ci.MAIN_GREEN, self.target, [], [], "",
                                  "CI main зелёный")
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with mock.patch.object(pin.gitcmd, "git", side_effect=spy), \
                mock.patch.object(ci, "main_line_status", return_value=green), \
                mock.patch.object(canary, "merges_since_last_green_run",
                                  return_value=canary_age), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            try:
                pin.cmd_pin_update(self.target)
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else (
                    0 if exc.code is None else 1)
        return out.getvalue() + err.getvalue(), code, calls


class PinUpdatePrunesStaleRefsTest(PinPruneSandbox):

    def test_ac1_successful_pin_update_drops_only_refs_gone_from_origin(self):
        """Успешный `pin-update` снимает ссылку без ветки в `origin`, живые оставляет.

        Сценарий: у главной копии `origin/task/<x>` (ветки в `origin` нет),
        `origin/task/<y…>` (ветки есть) и `origin/main`; `pin-update` на
        целевой sha с зелёными канарейкой и CI. После него ссылки
        `origin/task/<x>` нет, `origin/task/<y…>` и `origin/main` на месте,
        напечатано «ссылки origin без ветки на origin сняты: 1», HEAD — на
        целевом sha.

        Ловит мутацию: уборку не вызвали (или вызвали `git fetch -q origin
        main` без `--prune`) — ссылка `origin/task/<x>` остаётся в
        `for-each-ref`; либо N считается по всем строкам вывода `git
        remote prune` (заголовок «Pruning origin», «URL: …»), а не по
        строкам с `[pruned]`, — печатается «сняты: 3» вместо «сняты: 1».
        """
        output, code, _calls = self.run_pin_update()

        self.assertEqual(code, 0, self.ctx(output))
        self.assertEqual(self.head(), self.target,
                         self.ctx("пин не сдвинут\n" + output))
        refs = self.tracking_refs()
        self.assertNotIn(self.ref(self.stale), refs,
                         self.ctx(f"ссылка без ветки в origin осталась: {refs}"))
        for name in self.live:
            self.assertIn(self.ref(name), refs,
                          self.ctx(f"снята ссылка живой ветки {name}: {refs}"))
        self.assertIn(f"refs/remotes/origin/{config.MAIN_BRANCH}", refs,
                      self.ctx(str(refs)))
        counts = re.findall(re.escape(PRUNED_LINE) + r"(\d+)", output)
        self.assertEqual(counts, ["1"], self.ctx(output))


class PinUpdatePruneFailureTest(PinPruneSandbox):

    def test_ac2_prune_failure_keeps_moved_pin_and_exit_code(self):
        """Сбой `git remote prune origin` — предупреждение, пин сдвинут, код 0.

        Два вида сбоя (подменённый ответ git на `remote prune`): git
        вернул ошибку (случайный ненулевой код и текст причины) и git не
        ответил (`None`). В обоих случаях HEAD главной копии — на целевом
        sha, в журнале есть запись «pin обновлён», напечатана строка
        «уборка ссылок origin не выполнена: <причина>» (у ошибки — с её
        текстом), код выхода 0.

        Ловит мутацию: сбой уборки обработан `sys.exit(...)` (как отказы
        fetch/merge рядом) — код выхода становится ненулевым; либо ответ
        `None` разбирается как `res.returncode` — `AttributeError` вместо
        строки предупреждения; либо сбой проглочен молча — строки
        «уборка ссылок origin не выполнена: …» в выводе нет.
        """
        reason = f"fatal: подменённый сбой {self.rng.randint(1, 10 ** 6)}"
        rc = self.rng.randint(1, 128)
        variants = (
            ("ошибка git", lambda args: subprocess.CompletedProcess(
                list(args), rc, "", reason), reason),
            ("git не ответил", lambda args: None, ""),
        )
        start = self.head()
        for label, reply, expected_reason in variants:
            with self.subTest(сбой=label):
                self.git("reset", "-q", "--hard", start)
                before = self.pin_journal().count("pin обновлён")
                try:
                    output, code, calls = self.run_pin_update(git_reply=reply)
                except AttributeError as exc:
                    self.fail(self.ctx(f"{label}: сбой уборки уронил команду: {exc}"))
                self.assertTrue(any(is_remote_prune(a) for a in calls),
                                self.ctx(f"{label}: remote prune не вызван: {calls}"))
                self.assertEqual(code, 0, self.ctx(f"{label}: {output}"))
                self.assertEqual(self.head(), self.target,
                                 self.ctx(f"{label}: пин не сдвинут\n{output}"))
                self.assertEqual(self.pin_journal().count("pin обновлён"),
                                 before + 1,
                                 self.ctx(f"{label}: нет записи «pin обновлён»"))
                lines = [line for line in output.splitlines()
                         if WARNING_LINE in line]
                self.assertTrue(lines, self.ctx(f"{label}: нет предупреждения\n{output}"))
                tail = lines[0].split(WARNING_LINE, 1)[1].strip()
                self.assertTrue(tail, self.ctx(f"{label}: причина пуста: {lines[0]}"))
                if expected_reason:
                    self.assertIn(expected_reason, lines[0], self.ctx(output))


class PinUpdateRefusalSkipsPruneTest(PinPruneSandbox):

    def test_ac3_canary_refusal_never_calls_remote_prune(self):
        """Отказ `pin-update` по канарейке — `git remote prune` не вызван.

        Два вида «нет зелёного прогона»: возраст `None` (прогона нет) и
        возраст не меньше `config.CANARY_MAX_MERGES_SINCE_GREEN` (прогон
        слишком стар). Шпион на запуске git фиксирует, что ни одного вызова
        `remote prune` не было, команда отказала, HEAD не сдвинут, ссылка
        `origin/task/<x>` без ветки в `origin` на месте.

        Ловит мутацию: уборка поставлена сразу после `git fetch` (до
        проверки канарейки) или в `finally`/обработчик выхода команды —
        шпион видит вызов `remote prune`, а ссылка `origin/task/<x>`
        исчезает при отказе.
        """
        too_old = config.CANARY_MAX_MERGES_SINCE_GREEN + self.rng.randint(0, 5)
        for age in (None, too_old):
            with self.subTest(возраст=age):
                output, code, calls = self.run_pin_update(canary_age=age)
                self.assertNotEqual(code, 0, self.ctx(f"нет отказа: {output}"))
                pruned = [a for a in calls if is_remote_prune(a)]
                self.assertEqual(pruned, [],
                                 self.ctx(f"remote prune при отказе: {pruned}"))
                self.assertEqual(self.head(), self.old, self.ctx(output))
                self.assertIn(self.ref(self.stale), self.tracking_refs(),
                              self.ctx(output))


if __name__ == "__main__":
    unittest.main()
