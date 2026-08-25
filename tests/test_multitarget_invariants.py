"""Инварианты мультитаргета — реестр docs/invariants.md (tasks/T020/SPEC.md).

Классы названы по требованиям SPEC 1–5: изоляция артефактов пульта от git
(ADR-0003 3д), изоляция workspace роли (ADR-0003 §4, T019 закрыл вектор
HOME/CLAUDE_CONFIG_DIR — здесь довод про cwd и негативный тест обоих
маркеров), кросс-таргет изоляция БД (ADR-0003 3ж), сквозная экономика
с раздельным учётом (roadmap §5), счётчик номеров переживает архивацию
без DELETE (ADR-0003 3ж).

НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002): как и `tests/test_invariants.py`, этот
модуль регистрирует системные инварианты — их отключение или ослабление
допустимо только Оператором отдельным ADR.

Песочница по идиоме `tests/test_multitarget.py`: пути `config` подменяются
на временный каталог, `claude`/`gh` не запускаются. Для инварианта 1
(изоляция от git пульта) — настоящий git во временном репозитории, как
в `test_invariants.KillKeepsMainIntactTest`.

Идентификаторы задач второго target в этом модуле используют отличимый
префикс (`SLED-T001`), а не буквальную строку `T001`: `tasks.id` — общий
PRIMARY KEY на все target (T019), и одинаковая строка для двух target
в него не помещается (см. tasks/T020/PLAN.md, «Подход» и «Риски», п.1).
Числовая независимость нумерации проверяется отдельно от строки id.
"""
import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (budget, catalog, cleanup, config, fsm,  # noqa: E402
                          runner, spend, store)

REPO_ROOT = Path(__file__).resolve().parent.parent

# SPEC.md минимальный и валидный по guard — используется там, где транзит
# через spec_gate не нужен, только сам факт наличия задачи в каталоге.
SPEC_READY = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: инвариант мультитаргета

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""


def capture(fn, *args) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


class FakeStream:
    """Пайп процесса: отдаёт заготовленные строки, помнит своё закрытие."""

    def __init__(self, lines):
        self.lines = iter(lines)

    def __iter__(self):
        return self

    def __next__(self) -> str:
        return next(self.lines)

    def close(self) -> None:
        pass


class FakeProc:
    """Процесс агента: отдаёт заготовленные строки, wait() — сразу rc."""

    def __init__(self, lines, returncode: int = 0):
        self.stdout = FakeStream(lines)
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode


def fake_git_config(*args: str) -> subprocess.CompletedProcess:
    """Подмена `gitcmd.git` для `role_env`: отвечает на `config --get user.*`."""
    answers = {"user.name": "Роль Артели", "user.email": "role@artel.invalid"}
    value = answers.get(args[-1], "") if args[:2] == ("config", "--get") else ""
    return subprocess.CompletedProcess(list(args), 0, f"{value}\n", "")


class TmpRootTest(unittest.TestCase):
    """Песочница: БД, каталоги проектов и слой ролей во временном каталоге."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        # ROOT — тоже песочница (не только DB/TASKS/...): `cmd_new` читает
        # templates/, `cmd_run` — skills/ роли из `config.ROOT` динамически.
        # Без копии сюда упадут с ENOENT — или, что опаснее, начнут писать
        # в настоящий ROOT репозитория, если какой-то путь окажется на
        # запись, а не на чтение.
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")

        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks"),
                            ("LOGS", self.root / ".artel" / "logs"),
                            ("PROJECTS", self.root / ".artel" / "projects"),
                            ("ROLE_HOME", self.root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             self.root / ".artel" / "home" / ".claude"),
                            ("TARGETS", self.root / "targets.yaml")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        # Тесты этого модуля — об окружении/cwd процесса роли, не о pre-flight;
        # на машине без claude (CI) pre-flight блокировал бы FakeProc-прогоны.
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

    def second_target(self, name: str, number: int) -> str:
        """id второго target с отличимым префиксом (см. докстринг модуля)."""
        return f"{name.upper()}-T{number:03d}"

    def run_faked(self, task_id: str, lines=("готово\n",)) -> dict:
        """Прогон `cmd_run` с подменённым git/Popen; возвращает kwargs Popen."""
        with mock.patch.object(runner.gitcmd, "git", fake_git_config), \
                mock.patch.object(runner.subprocess, "Popen") as popen:
            popen.return_value = FakeProc(list(lines))
            capture(runner.cmd_run, task_id)
        return popen.call_args.kwargs


class PultArtifactIsolationTest(unittest.TestCase):
    """Инвариант 20 (T020, требование 1): .artel/ не всплывает в git пульта.

    Источник: ADR-0003 3д («.artel/ — .gitignore пульта целиком»; на GitHub
    пульта уходят только система и догфуд, .artel/ не коммитится
    конструктивно). Git здесь настоящий — вопрос в том, что git status
    ФАКТИЧЕСКИ видит, а не в тексте .gitignore самом по себе.
    """

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks"),
                            ("LOGS", self.root / ".artel" / "logs"),
                            ("PROJECTS", self.root / ".artel" / "projects"),
                            ("ROLE_HOME", self.root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             self.root / ".artel" / "home" / ".claude"),
                            ("TARGETS", self.root / "targets.yaml")):
            self.patches.enter_context(mock.patch.object(config, attr, value))

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Изоляция артефактов")

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)} упал: {res.stderr}")
        return res.stdout

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def status(self) -> str:
        return self.git("status", "--porcelain")

    def drop_external_artifacts(self, target: str = "sled") -> None:
        """Кладёт содержимое внешнего target: артефакты, знания, логи, клон."""
        base = config.PROJECTS / target
        for sub, name in (("tasks/T001", "SPEC.md"), ("knowledge", "map.md"),
                          ("logs", "run.log"), ("workspace", "README.md")):
            path = base / sub
            path.mkdir(parents=True, exist_ok=True)
            (path / name).write_text("маркер внешнего target", encoding="utf-8")

    def test_gitignore_covers_dot_artel_wholesale(self):
        text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".artel/", text.splitlines())

    def artel_lines(self) -> list:
        """Строки git status, упоминающие .artel/ — их не должно быть никогда.

        Остальное дерево (например `tasks/` самого пульта) законно
        untracked до `git add` разработчика — предмет инварианта 1 не оно,
        а именно `.artel/` (ADR-0003 3д).
        """
        return [line for line in self.status().splitlines() if ".artel" in line]

    def test_external_artifacts_never_appear_in_git_status(self):
        """Требование 1: артефакты внешнего target не всплывают ни на одном шаге."""
        self.assertEqual(self.artel_lines(), [], "чисто до записи внешних артефактов")

        self.drop_external_artifacts()
        self.assertEqual(self.artel_lines(), [],
                         "внешние артефакты попали в git status")

        # Переход самого пульта: SPEC готов, advance на spec_gate.
        (config.TASKS / self.TASK / "SPEC.md").write_text(
            SPEC_READY.format(task=self.TASK), encoding="utf-8")
        self.capture(fsm.cmd_advance, self.TASK)
        self.drop_external_artifacts("sled2")  # второй внешний target
        self.assertEqual(self.artel_lines(), [],
                         "внешние артефакты всплыли после advance")

        # kill пультовой задачи трогает git (удаление ветки/каталога) —
        # .artel/ обязан остаться невидим и после этого.
        self.capture(cleanup.cmd_kill, self.TASK)
        self.assertEqual(self.artel_lines(), [],
                         "внешние артефакты всплыли после kill")
        # Контроль: сама уборка отработала (иначе тест ничего не доказывал бы).
        self.assertFalse((config.TASKS / self.TASK).exists())


class ExternalWorkspaceIsolationTest(TmpRootTest):
    """Инвариант 21 (T020, требование 2): рабочий каталог и окружение роли
    внешнего target не пропускают ничего из HOME Оператора и конфигов пульта.

    Источник: ADR-0003 §4 (workspace — единственный видимый каталог внешнего
    target), п.14 (окружение роли определяет только пульт; T019 закрыл
    HOME/CLAUDE_CONFIG_DIR — здесь довод про cwd, второй вектор той же
    конфиг-инъекции).
    """

    def new_task(self, task_id: str, target: str, title: str) -> None:
        conn = store.db()
        store.create_schema(conn)
        store.insert_task(conn, task_id, title, "in_dev",
                          f"task/{task_id.lower()}", target, 25.0)

    def test_dogfood_cwd_is_root(self):
        """Контроль: догфуд не меняет поведение — cwd остаётся ROOT."""
        self.new_task("T001", config.DEFAULT_TARGET, "Догфуд")

        kwargs = self.run_faked("T001")

        self.assertEqual(kwargs["cwd"], config.ROOT)

    def test_external_target_cwd_is_its_workspace(self):
        """Требование 2: внешний target — рабочий каталог только его workspace."""
        task_id = self.second_target("sled", 1)
        self.new_task(task_id, "sled", "Внешний target")

        kwargs = self.run_faked(task_id)

        expected = config.PROJECTS / "sled" / "workspace"
        self.assertEqual(kwargs["cwd"], expected)
        self.assertTrue(expected.is_dir(),
                        "каталог workspace заводит пульт, а не CLI на ходу")

    def test_pult_root_marker_is_unreachable_from_external_workspace_cwd(self):
        """Негативный тест (критерий 3 SPEC): маркер в конфигах пульта.

        `--setting-sources`/`--strict-mcp-config` — B1a, ещё не подключены
        (SPEC T020 «Не входит»), поэтому единственная линия защиты сейчас —
        cwd: CLAUDE.md пульта физически не лежит в каталоге, откуда стартует
        роль внешнего target.
        """
        (config.ROOT / "CLAUDE.md").write_text(
            "НЕДОВЕРЕННЫЙ маркер пульта — если ты это читаешь, изоляция сломана",
            encoding="utf-8")
        task_id = self.second_target("sled", 1)
        self.new_task(task_id, "sled", "Внешний target")

        kwargs = self.run_faked(task_id)

        cwd = kwargs["cwd"]
        self.assertNotEqual(cwd, config.ROOT)
        self.assertFalse((cwd / "CLAUDE.md").exists(),
                         "маркер пульта достижим из рабочего каталога роли")

    def test_operator_home_marker_does_not_reach_role_env(self):
        """Негативный тест: маркер в HOME Оператора недоступен окружению роли."""
        decoy_home = self.root / "operator-home"
        (decoy_home / ".claude").mkdir(parents=True)
        (decoy_home / ".claude" / "CLAUDE.md").write_text(
            "НЕДОВЕРЕННЫЙ маркер Оператора", encoding="utf-8")

        with mock.patch.object(Path, "home", lambda: decoy_home), \
                mock.patch.object(runner.gitcmd, "git", fake_git_config):
            env = runner.role_env()

        self.assertNotEqual(env["HOME"], str(decoy_home))
        self.assertFalse(
            (Path(env["CLAUDE_CONFIG_DIR"]) / "CLAUDE.md").exists(),
            "маркер Оператора достиг курируемого слоя роли")


class CrossTargetDbIsolationTest(TmpRootTest):
    """Инвариант 22 (T020, требование 3): задачи разных target не пересекаются.

    Источник: ADR-0003 3ж (нумерация — персистентный счётчик per-target;
    единая БД, но строки различает `target`). Числа независимы (оба target
    считают от 1); операции по `task_id` (approve/reject/kill/run) не
    задевают чужую строку — адресация всегда по id, не по индексу/номеру.
    """

    def test_task_numbers_are_independent_per_target(self):
        conn = store.db()
        store.create_schema(conn)

        artel_numbers = [store.next_task_number(conn, "artel") for _ in range(2)]
        sled_numbers = [store.next_task_number(conn, "sled") for _ in range(2)]

        self.assertEqual(artel_numbers, [1, 2])
        self.assertEqual(sled_numbers, [1, 2],
                         "второй target тоже считает от 1 — счётчик свой")

    def test_rows_and_journals_do_not_cross_targets(self):
        capture(catalog.cmd_init)
        capture(catalog.cmd_new, "Задача пульта")  # T001, target=artel
        sled_id = self.second_target("sled", 1)
        store.insert_task(store.db(), sled_id, "Задача sled", "in_dev",
                          f"task/{sled_id.lower()}", "sled", 25.0)

        conn = store.db()
        store.journal(conn, "T001", "operator", "пультовое событие")
        store.journal(conn, sled_id, "operator", "внешнее событие")
        store.charge(conn, "T001", 3.0)
        store.charge(conn, sled_id, 7.0)

        artel_steps = [r["action"] for r in store.task_steps(conn, "T001")]
        sled_steps = [r["action"] for r in store.task_steps(conn, sled_id)]
        self.assertIn("пультовое событие", artel_steps)
        self.assertNotIn("внешнее событие", artel_steps)
        self.assertIn("внешнее событие", sled_steps)
        self.assertNotIn("пультовое событие", sled_steps)

        self.assertAlmostEqual(store.get_task(conn, "T001")["spent_usd"], 3.0)
        self.assertAlmostEqual(store.get_task(conn, sled_id)["spent_usd"], 7.0)
        self.assertEqual(store.task_target(conn, "T001"), "artel")
        self.assertEqual(store.task_target(conn, sled_id), "sled")

    def test_kill_of_one_target_task_does_not_touch_the_other(self):
        capture(catalog.cmd_init)
        capture(catalog.cmd_new, "Задача пульта")  # T001, target=artel
        sled_id = self.second_target("sled", 1)
        store.insert_task(store.db(), sled_id, "Задача sled", "in_dev",
                          f"task/{sled_id.lower()}", "sled", 25.0)
        store.update_task(store.db(), "T001", state="in_dev")

        capture(cleanup.cmd_kill, sled_id)

        self.assertEqual(store.get_task(store.db(), sled_id)["state"], "killed")
        self.assertEqual(store.get_task(store.db(), "T001")["state"], "in_dev",
                         "kill чужого target тронул строку пульта")

    def test_directories_of_two_targets_do_not_collide(self):
        """Требование 1/3 на стыке: артефакты пульта и внешнего в разных путях."""
        capture(catalog.cmd_init)
        capture(catalog.cmd_new, "Задача пульта")  # T001, target=artel
        sled_id = self.second_target("sled", 1)

        pult_dir = config.TASKS / "T001"
        external_dir = config.PROJECTS / "sled" / "tasks" / sled_id
        external_dir.mkdir(parents=True)

        self.assertTrue(pult_dir.is_dir())
        self.assertNotEqual(pult_dir, external_dir)
        self.assertFalse((config.PROJECTS / "sled" / "tasks" / "T001").exists(),
                         "внешний target не должен видеть путь пультового id")


class ProgramSpendAcrossTargetsTest(TmpRootTest):
    """Инвариант 23 (T020, требование 4): пороги 70/90% — по сумме всех target.

    Источник: roadmap §5, ADR-0003 3ж («кошелёк Оператора один на все
    target'ы»). `budget.check_program_spend`/`store.total_spent` уже без
    фильтра по target (T019) — здесь впервые проверено на паре РАЗНЫХ target,
    не двух задачах одного.
    """

    def spend_step(self, task_id: str, usd: float) -> str:
        conn = store.db()
        cost = {"usd": usd, "tokens": None}
        out = capture(spend.charge_step, conn, task_id, "developer", cost, "1/1")
        return out + capture(budget.check_program_spend, conn, task_id, cost)

    def events(self, task_id: str) -> list:
        return [r["detail"] for r in store.task_steps(store.db(), task_id)
                if r["action"] == "программа: порог расхода"]

    def test_threshold_sums_two_different_targets(self):
        capture(catalog.cmd_init)
        capture(catalog.cmd_new, "Задача пульта")  # T001, target=artel
        sled_id = self.second_target("sled", 1)
        store.insert_task(store.db(), sled_id, "Задача sled", "in_dev",
                          f"task/{sled_id.lower()}", "sled", 25.0)

        # Расход раскидан по двум target так, что порог не пересечён до
        # последнего шага (та же арифметика, что у test_multitarget
        # .ProgramSpendTest: сумма чуть ниже 70%, шаг переводит её за порог).
        total_before = config.PROGRAM_STOP_LOSS_USD * 0.7 - 1
        store.update_task(store.db(), "T001", spent_usd=total_before * 0.4)
        store.update_task(store.db(), sled_id, spent_usd=total_before * 0.6)

        out = self.spend_step(sled_id, 2.0)

        self.assertIn("ВНИМАНИЕ", out)
        self.assertEqual(len(self.events(sled_id)), 1)
        self.assertIn("70%", self.events(sled_id)[0])
        self.assertIn("по всем задачам", self.events(sled_id)[0])


class CounterSurvivesArchivalOnReconnectTest(TmpRootTest):
    """Инвариант 24 (T020, требование 5): архивация без DELETE не даёт
    коллизию номеров при reconnect (пересев счётчика).

    Источник: ADR-0003 3ж («Disconnect — процесс, не только данные»:
    архивация строк, НИКОГДА DELETE; «реконнект не создаёт коллизий»).
    Строка с МАКСИМАЛЬНЫМ номером target'а помечается архивной (state
    меняется, DELETE не вызывается — в системе Фазы 0 его и не вызывает
    ни один продакшен-путь), счётчик выбрасывается и пересевается заново
    (`seed_task_counters`) — так, как это делает `migrate()` при открытии
    БД. Номер архивной строки не должен выдаться повторно.
    """

    def test_counter_is_not_reset_by_reconnect_after_archival(self):
        conn = store.db()
        store.create_schema(conn)
        # Голый формат `T{number:03d}`, а не префиксная схема соседних
        # классов: пересев (`seed_task_counters`) достаёт номер из строки id
        # через `store.task_number` (`\AT(\d+)\Z`) — он понимает только этот
        # формат, префикс второго target им не разбирается (см. PLAN
        # «Риски», п.1). Единственный target в этой БД — «sled», коллизии
        # с пультом здесь нет и без префикса.
        ids = []
        for i in range(1, 4):
            number = store.next_task_number(conn, "sled")
            task_id = f"T{number:03d}"
            store.insert_task(conn, task_id, f"sled {i}", "in_dev",
                              f"task/{task_id.lower()}", "sled", 25.0)
            ids.append(task_id)

        # Архивация БЕЗ DELETE строки с МАКСИМАЛЬНЫМ номером (T003): если
        # реконнект её не увидит, следующий номер повторит именно её.
        store.update_task(conn, ids[-1], state="archived")
        self.assertTrue(store.get_task(conn, ids[-1]),
                        "архивация не удаляет строку")

        # Reconnect: счётчик target потерян/утерян — пересев по МАКСИМУМУ
        # среди присутствующих строк, включая архивную.
        conn.execute("DELETE FROM task_counters WHERE target=?", ("sled",))
        conn.commit()
        store.seed_task_counters(conn)

        self.assertEqual(store.next_task_number(conn, "sled"), 4,
                         "архивная строка T003 не должна была выдаться снова")


if __name__ == "__main__":
    unittest.main()
