"""Сторож главной копии пульта: алерт об изменениях, появившихся за время шага роли.

Группа: долгоживущий
Красен до реализации: сторожа главной копии после шага роли нет — шаг, за время которого в главной копии изменился файл, не поднимает никакого алерта (AC-2, AC-4, AC-5, AC-6, AC-7, AC-8 падают на «алерта нет»); AC-3 держит отсутствие алерта и зелен уже сейчас.

Связка «шаг роли — чекпоинт — git главной копии — таблица алертов»: шаг
гоняется целиком через публичный `runner.run_agent_once` в песочнице с
настоящим git (`tests.sandbox.RealGitSandbox` + синхронный origin).
Главная копия пульта — репозиторий песочницы (`config.ROOT`); рабочая
копия задачи — настоящий worktree, который заводит сам пульт. Подставной
агент (`runner.spawn_agent`) пишет обязательный артефакт роли в свой
`cwd` и, по сценарию, меняет отслеживаемый файл главной копии — так, как
это 05.10 сделал запущенный ролью генератор карты; завершение — rc=0,
ненулевой rc или таймаут. Алерты читаются публичным
`alerts.open_alerts`: «алерт шага» — новый открытый алерт, в тексте
которого есть id задачи. Идентификаторы задач, роли, файлы и коды
возврата порождаются `random` при каждом запуске; зерно печатается и
входит в текст каждого провала.
"""
import random
import re
import subprocess
import time
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import alerts, config, keychain, runner, stack, store
from tests.sandbox import FakeProc, RealGitSandbox

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijklmnopqrstuvwxyz"
RESULT_LINE = '{"type": "result", "total_cost_usd": 0.001}\n'

# Роль, состояние задачи, где она работает, и её обязательный артефакт
# (путь внутри каталога задачи) — шаг с ним завершается исходом "ok".
ROLES = (
    ("analyst", "spec_writing", ("SPEC.md",)),
    ("test_author", "tests_writing", ("acceptance_tests", "test_plank.py")),
    ("developer", "in_dev", ("PLAN.md",)),
    ("reviewer", "review", ("REVIEW.md",)),
)
ROLE_STATE = {role: state for role, state, _ in ROLES}
ROLE_ARTIFACT = {role: artifact for role, _, artifact in ROLES}

# Глаголы утверждения авторства правки (рус./англ. основы).
ATTRIBUTION_VERBS = ("изменил", "изменен", "изменён", "записал", "написал",
                     "переписал", "внес", "внёс", "испортил", "changed",
                     "modified", "wrote")


def random_task_id(rng: random.Random) -> str:
    """Идентификатор формы ULID (26 знаков алфавита Крокфорда)."""
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def claims_authorship(message: str, role: str) -> bool:
    """Текст утверждает, что правку сделала роль: «<роль> [≤3 слова]
    изменила…» в одном предложении без отрицания «не»/«кто» между ними,
    либо «ролью <роль>»/«by <роль>»."""
    for found in re.finditer(re.escape(role), message):
        clause = re.split(r"[.;:!?\n(—]", message[found.end():], maxsplit=1)[0]
        for word in re.findall(r"\w+", clause)[:4]:
            low = word.lower()
            if low in ("не", "кто", "not", "who"):
                break
            if low.startswith(ATTRIBUTION_VERBS):
                return True
    return bool(re.search(rf"(ролью|by)\s+{re.escape(role)}", message,
                          re.IGNORECASE))


class TimeoutProc(FakeProc):
    """Агент, не уложившийся в таймаут шага: ожидание с пределом бросает
    `TimeoutExpired`, после снятия процесса `wait()` отдаёт -9."""

    def wait(self, timeout=None) -> int:
        if timeout is not None:
            raise subprocess.TimeoutExpired("агент", timeout)
        return -9

    def kill(self) -> None:
        pass


class MainCopyWatchSandbox(RealGitSandbox):
    """Главная копия с набором отслеживаемых файлов, задачи — через store."""

    def setUp(self):
        super().setUp()
        self.seed = time.time_ns()
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.tracked = self.seed_tracked_files()
        self.add_synced_origin()
        # Карта ролей и слой моделей — фикстурой песочницы, не файлы
        # репозитория; согласованность стека (venv, CLI) — не предмет теста.
        self.use_role_map()
        stack_ok = [stack.StackCheck(name, "ok", "песочница")
                    for name in ("python", "git", "gh", "claude", "venv")]
        for patcher in (
                mock.patch.object(stack, "check_stack", lambda: list(stack_ok)),
                mock.patch.object(keychain, "token", lambda slot: "tok-test"),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda role, target: [])):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.conn = store.db()
        self.assertEqual(self.main_status(), "",
                         f"зерно {self.seed}: главная копия грязна до сценария")

    def token(self) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(10))

    def seed_tracked_files(self) -> list:
        """Отслеживаемые файлы главной копии: карта кода (инцидент 05.10) и
        несколько случайных путей; ни один путь не подстрока другого."""
        paths = [Path("docs") / "codebase-map.md"]
        paths += [Path(f"d{i}_{self.token()}") / f"f{i}_{self.token()}.txt"
                  for i in range(6)]
        for rel in paths:
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text("исходное\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "посев главной копии")
        self.rng.shuffle(paths)
        return [rel.as_posix() for rel in paths]

    def take_path(self) -> str:
        """Ещё не тронутый сценарием отслеживаемый путь главной копии."""
        return self.tracked.pop()

    def main_status(self) -> str:
        return self.git("status", "--porcelain")

    def modify(self, rel: str) -> str:
        text = f"правка шага {self.token()}\n"
        (self.root / rel).write_text(text, encoding="utf-8")
        return text

    def new_task(self, role: str) -> str:
        task_id = random_task_id(self.rng)
        store.insert_task(self.conn, task_id, "Задача", ROLE_STATE[role],
                          f"task/{task_id.lower()}-zadacha",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        return task_id

    def random_role(self) -> str:
        return self.rng.choice(ROLES)[0]

    def run_step(self, task_id: str, role: str, during=None, proc=None,
                 conn=None) -> str:
        """Шаг роли: подставной агент пишет обязательный артефакт роли в
        свой `cwd`, зовёт `during()` (правка главной копии, вложенный шаг
        другой задачи) и завершается процессом `proc()` (по умолчанию
        rc=0); возврат — исход `run_agent_once`."""
        conn = conn or self.conn
        seen = []

        def fake_agent(cmd, **kwargs):
            cwd = Path(kwargs["cwd"])
            seen.append(cwd)
            dest = cwd.joinpath("tasks", task_id, *ROLE_ARTIFACT[role])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("# артефакт шага\n", encoding="utf-8")
            if during is not None:
                during()
            return proc() if proc is not None else FakeProc([RESULT_LINE], 0)

        with mock.patch.object(runner, "spawn_agent", side_effect=fake_agent):
            outcome, reason, _cls = runner.run_agent_once(
                conn, task_id, role, "промпт шага", 1)
        self.assertEqual(len(seen), 1,
                         f"зерно {self.seed}: агент {role} задачи {task_id} "
                         f"не запущен ровно раз ({outcome}: {reason})")
        return outcome

    def alert_ids(self) -> set:
        return {row["id"] for row in alerts.open_alerts(self.conn)}

    def new_messages(self, before: set, task_id: str) -> list:
        """Тексты открытых алертов, заведённых после `before`, с id задачи."""
        return [row["message"] for row in alerts.open_alerts(self.conn)
                if row["id"] not in before and task_id in row["message"]]

    def assert_step_alert(self, messages: list, task_id: str, role: str,
                          rel: str, context: str) -> None:
        """Среди алертов есть алерт шага: id задачи, роль и путь в тексте."""
        self.assertTrue(
            any(role in m and rel in m for m in messages),
            f"зерно {self.seed}: {context} — нет алерта с задачей {task_id}, "
            f"ролью {role} и путём {rel}; алерты задачи: {messages}")


class Ac2ChangeDuringStepRaisesAlertTest(MainCopyWatchSandbox):

    def test_ac2_change_during_ok_step_raises_alert_without_blame(self):
        """За время шага (rc=0) в главной копии изменился отслеживаемый файл.

        На двух случайных задачах со случайной ролью подставной агент меняет
        случайный отслеживаемый файл главной копии и завершается rc=0. После
        шага есть новый открытый алерт, в тексте которого id задачи, роль и
        путь файла; ни один алерт задачи не утверждает, что файл изменила
        эта роль («<роль> … изменила», «ролью <роль>», «by <роль>»).

        Ловит мутацию: сверка главной копии не поставлена в нормальное
        завершение шага (`_finish_ok`/`commit_success_checkpoint`) — алерта
        нет; либо текст алерта не называет путь/роль; либо формулирует
        «роль <роль> задачи <id> изменила главную копию» — тест краснеет на
        утверждении авторства.
        """
        for _ in range(2):
            role = self.random_role()
            task_id = self.new_task(role)
            rel = self.take_path()
            before = self.alert_ids()
            with self.subTest(role=role, path=rel):
                outcome = self.run_step(task_id, role,
                                        during=lambda: self.modify(rel))
                self.assertEqual(outcome, "ok", f"зерно {self.seed}: {role}")
                messages = self.new_messages(before, task_id)
                self.assert_step_alert(messages, task_id, role, rel,
                                       "шаг rc=0")
                for message in messages:
                    self.assertFalse(
                        claims_authorship(message, role),
                        f"зерно {self.seed}: алерт приписывает правку роли: "
                        f"{message}")


class Ac3UnchangedMainCopyNoAlertTest(MainCopyWatchSandbox):

    def test_ac3_step_without_main_copy_change_raises_no_alert(self):
        """Шаг каждой роли, за время которого главная копия не менялась.

        Для каждой роли перечня — шаг rc=0 на свежей случайной задаче;
        агент пишет только свой артефакт в рабочую копию задачи. Главная
        копия после шага чиста, и нового открытого алерта с id задачи нет.

        Ловит мутацию: сторож поднимает алерт безусловно (на пустом списке
        появившихся путей) либо считает изменением саму рабочую копию
        задачи/каталог документов — появится алерт с id задачи.
        """
        for role, _state, _artifact in ROLES:
            with self.subTest(role=role):
                task_id = self.new_task(role)
                before = self.alert_ids()
                outcome = self.run_step(task_id, role)
                self.assertEqual(outcome, "ok", f"зерно {self.seed}: {role}")
                self.assertEqual(self.main_status(), "",
                                 f"зерно {self.seed}: шаг {role} без правки "
                                 f"главной копии оставил её грязной")
                self.assertEqual(self.new_messages(before, task_id), [],
                                 f"зерно {self.seed}: алерт на шаге без "
                                 f"изменений главной копии")


class Ac4PreexistingChangesNotReportedTest(MainCopyWatchSandbox):

    def test_ac4_preexisting_changes_neither_alert_nor_listed(self):
        """Главная копия грязна ещё до шага.

        Сначала до шага меняются один-два случайных отслеживаемых файла, и
        шаг случайной роли ничего не трогает — нового алерта с id задачи нет.
        Затем шаг другой задачи меняет ещё один файл — алерт есть, называет
        новый путь и не называет ни одного пути, бывшего до шага.

        Ловит мутацию: сторож сверяет не разницу «после минус до», а весь
        `git status` после шага — первая половина получит алерт на старой
        грязи, вторая — старые пути в тексте алерта.
        """
        old = [self.take_path() for _ in range(self.rng.randint(1, 2))]
        for rel in old:
            self.modify(rel)

        role = self.random_role()
        task_id = self.new_task(role)
        before = self.alert_ids()
        self.assertEqual(self.run_step(task_id, role), "ok",
                         f"зерно {self.seed}: {role}")
        self.assertEqual(self.new_messages(before, task_id), [],
                         f"зерно {self.seed}: алерт на изменениях, бывших "
                         f"до шага {old}")

        role = self.random_role()
        task_id = self.new_task(role)
        new = self.take_path()
        before = self.alert_ids()
        self.assertEqual(
            self.run_step(task_id, role, during=lambda: self.modify(new)),
            "ok", f"зерно {self.seed}: {role}")
        messages = self.new_messages(before, task_id)
        self.assert_step_alert(messages, task_id, role, new,
                               "новое изменение поверх старых")
        for message in messages:
            for rel in old:
                self.assertNotIn(rel, message,
                                 f"зерно {self.seed}: в алерте путь, бывший "
                                 f"до шага: {message}")


class Ac5TimeoutStepRaisesAlertTest(MainCopyWatchSandbox):

    def test_ac5_change_during_timed_out_step_raises_alert(self):
        """Шаг завершён по таймауту, за его время изменился файл главной копии.

        Подставной агент меняет случайный отслеживаемый файл и не
        укладывается в таймаут (`wait` с пределом бросает
        `TimeoutExpired`); исход шага — "timeout". На двух случайных
        задачах есть новый алерт с id задачи, ролью и путём.

        Ловит мутацию: сверка главной копии добавлена только в нормальное
        завершение и сбой, но не в `_finish_timeout`/
        `commit_timeout_checkpoint` — после таймаута алерта нет.
        """
        for _ in range(2):
            role = self.random_role()
            task_id = self.new_task(role)
            rel = self.take_path()
            before = self.alert_ids()
            with self.subTest(role=role, path=rel):
                outcome = self.run_step(
                    task_id, role, during=lambda: self.modify(rel),
                    proc=lambda: TimeoutProc([]))
                self.assertEqual(outcome, "timeout",
                                 f"зерно {self.seed}: {role}")
                self.assert_step_alert(self.new_messages(before, task_id),
                                       task_id, role, rel, "таймаут шага")


class Ac6FailedStepRaisesAlertTest(MainCopyWatchSandbox):

    def test_ac6_change_during_failed_step_raises_alert(self):
        """Агент завершился ненулевым кодом, за время шага изменился файл.

        Подставной агент меняет случайный отслеживаемый файл и выходит со
        случайным ненулевым кодом; исход шага — "failed". На двух случайных
        задачах есть новый алерт с id задачи, ролью и путём.

        Ловит мутацию: сверка главной копии не добавлена в `_finish_failed`/
        `commit_abnormal_checkpoint` — после сбоя агента алерта нет.
        """
        for _ in range(2):
            role = self.random_role()
            task_id = self.new_task(role)
            rel = self.take_path()
            rc = self.rng.choice((1, 2, 3, 127))
            before = self.alert_ids()
            with self.subTest(role=role, path=rel, rc=rc):
                outcome = self.run_step(
                    task_id, role, during=lambda: self.modify(rel),
                    proc=lambda: FakeProc([RESULT_LINE], rc))
                self.assertEqual(outcome, "failed",
                                 f"зерно {self.seed}: {role} rc={rc}")
                self.assert_step_alert(self.new_messages(before, task_id),
                                       task_id, role, rel, f"сбой rc={rc}")


class Ac7WatchRevertsNothingTest(MainCopyWatchSandbox):

    def test_ac7_fired_watch_keeps_change_and_task_state(self):
        """Сработавший сторож не откатывает правку и не трогает состояние задачи.

        Две задачи одной случайной роли в одном состоянии: шаг первой
        меняет файл главной копии (сторож срабатывает — алерт есть), шаг
        второй главную копию не трогает. После шага изменённый файл несёт
        ровно содержимое, оставленное шагом, и по-прежнему значится в
        `git status` главной копии; состояние первой задачи то же, что до
        шага, и то же, что у второй задачи после её шага без сторожа.

        Ловит мутацию: сторож «чинит» главную копию (`git checkout`/
        `git stash`/`git reset` изменённых путей) — содержимое файла
        вернётся к исходному; либо переводит задачу (эскалация, пауза) —
        состояние задачи разойдётся с состоянием задачи-близнеца.
        """
        role = self.random_role()
        task_id = self.new_task(role)
        twin = self.new_task(role)
        rel = self.take_path()
        state_before = store.get_task(self.conn, task_id)["state"]
        written = []
        before = self.alert_ids()

        self.run_step(task_id, role,
                      during=lambda: written.append(self.modify(rel)))
        self.assert_step_alert(self.new_messages(before, task_id), task_id,
                               role, rel, "сторож обязан был сработать")
        self.assertEqual((self.root / rel).read_text(encoding="utf-8"),
                         written[0],
                         f"зерно {self.seed}: изменённый файл откачен")
        self.assertIn(rel, self.main_status(),
                      f"зерно {self.seed}: правка пропала из git status")

        self.run_step(twin, role)
        state_after = store.get_task(self.conn, task_id)["state"]
        self.assertEqual(state_after, state_before,
                         f"зерно {self.seed}: сторож сменил состояние задачи")
        self.assertEqual(state_after,
                         store.get_task(self.conn, twin)["state"],
                         f"зерно {self.seed}: состояние расходится с шагом "
                         f"без сработавшего сторожа")


class Ac8OverlappingStepsNamedTest(MainCopyWatchSandbox):

    def test_ac8_overlapping_steps_of_two_tasks_name_each_other(self):
        """Два шага ролей разных задач пересекаются во времени.

        Шаг A (случайная роль) идёт; его подставной агент запускает внутри
        себя полный шаг B другой задачи (другая роль), агент которого
        меняет файл главной копии, — шаг B целиком лежит внутри шага A.
        Алерт, заведённый к концу шага B, называет задачу и роль B и задачу
        и роль A; алерт, заведённый к концу шага A, — задачу и роль A и
        задачу и роль B. Оба называют путь. Проверяется на двух парах.

        Ловит мутацию: алерт перечисляет только шаги, идущие В МОМЕНТ
        сверки (живые лизы/открытые шаги), а не все пересекавшиеся с этим
        шагом — алерт шага A не назовёт уже завершившийся шаг B; либо
        перечень соседних шагов не выводится вовсе.
        """
        for _ in range(2):
            role_a, role_b = self.rng.sample([r for r, _s, _a in ROLES], 2)
            task_a = self.new_task(role_a)
            task_b = self.new_task(role_b)
            rel = self.take_path()
            before = self.alert_ids()
            after_b = {}

            def during_a():
                outcome_b = self.run_step(task_b, role_b,
                                          during=lambda: self.modify(rel),
                                          conn=store.db())
                after_b["outcome"] = outcome_b
                after_b["ids"] = self.alert_ids()

            with self.subTest(a=(task_a, role_a), b=(task_b, role_b)):
                self.assertEqual(self.run_step(task_a, role_a,
                                               during=during_a), "ok",
                                 f"зерно {self.seed}: шаг A {role_a}")
                self.assertEqual(after_b["outcome"], "ok",
                                 f"зерно {self.seed}: шаг B {role_b}")

                b_alerts = [row["message"]
                            for row in alerts.open_alerts(self.conn)
                            if row["id"] in after_b["ids"] - before
                            and rel in row["message"]]
                a_alerts = [row["message"]
                            for row in alerts.open_alerts(self.conn)
                            if row["id"] not in after_b["ids"]
                            and rel in row["message"]]
                for name, found in (("после шага B", b_alerts),
                                    ("после шага A", a_alerts)):
                    self.assertTrue(found, f"зерно {self.seed}: {name} нет "
                                           f"алерта с путём {rel}")
                    for message in found:
                        for task_id, role in ((task_a, role_a),
                                              (task_b, role_b)):
                            self.assertIn(task_id, message,
                                          f"зерно {self.seed}: {name} "
                                          f"алерт не называет задачу "
                                          f"{task_id}: {message}")
                            self.assertIn(role, message,
                                          f"зерно {self.seed}: {name} "
                                          f"алерт не называет роль {role}: "
                                          f"{message}")

    def test_ac8_lone_step_names_only_itself(self):
        """Шаг без пересекающихся во времени шагов других задач.

        Сначала целиком проходит шаг другой задачи (случайная роль, главную
        копию не трогает); он завершён ДО старта проверяемого шага —
        граница по порядку событий шага, а не по совпадению секунд. Затем
        шаг проверяемой задачи меняет файл главной копии. Его алерт
        называет эту задачу, её роль и путь и не называет задачу
        завершившегося раньше шага. Проверяется на двух парах.

        Ловит мутацию: перечень соседних шагов берётся не по пересечению
        промежутков, а «все шаги за последние N минут» или все задачи в
        работе — в алерт попадёт id задачи, чей шаг закончился до старта.
        """
        for _ in range(2):
            earlier_role = self.random_role()
            earlier = self.new_task(earlier_role)
            role = self.random_role()
            task_id = self.new_task(role)
            rel = self.take_path()
            with self.subTest(earlier=(earlier, earlier_role),
                              step=(task_id, role)):
                self.assertEqual(self.run_step(earlier, earlier_role), "ok",
                                 f"зерно {self.seed}: {earlier_role}")
                before = self.alert_ids()
                self.assertEqual(
                    self.run_step(task_id, role,
                                  during=lambda: self.modify(rel)),
                    "ok", f"зерно {self.seed}: {role}")
                messages = self.new_messages(before, task_id)
                self.assert_step_alert(messages, task_id, role, rel,
                                       "одиночный шаг")
                for message in messages:
                    self.assertNotIn(earlier, message,
                                     f"зерно {self.seed}: алерт называет "
                                     f"непересекавшийся шаг {earlier}: "
                                     f"{message}")


if __name__ == "__main__":
    unittest.main()
