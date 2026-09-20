"""Песочницы приёмочной планки 01M2YSHDKWFJN3XSJ618Z74FNF: гейт
применимости приложений на выходе `in_dev` (AC-5..AC-7) и применение
приложений на мерже (AC-8..AC-13).

Тонкая надстройка над `tests/sandbox.py::RealGitSandbox`: НАСТОЯЩИЙ git
нужен здесь по существу — предмет обоих критериев `git apply --check`/
`git apply` против настоящего дерева, заглушкой (`fake_git` лёгкой
песочницы отвечает успехом на любой неизвестный вызов) сценарий
«приложение неприменимо» не изобразить вовсе. Поэтому
`LightTransitionSandbox` здесь не годится, а её `disk_backed_show`/
`disk_backed_ls_tree_files`/`advance_from_in_dev` не копируются и не
переопределяются (skills/test-authoring.md, «Лёгкая песочница переходов —
не копия, импорт»): `gitcmd.show`/`ls_tree_files` работают в этих
сценариях по-настоящему, с настоящей артефактной ветки.

Две сборки, обе на одном общем корне:

- `InDevAppendixSandbox` — задача в `in_dev` с настоящей кодовой веткой и
  артефактной веткой; соседние гейты выхода `in_dev` подменены
  «пройдено», живым остаётся только НОВЫЙ гейт применимости (тем же
  приёмом одного живого узла, что `tasks/01M2XFSE8G3MBRHHQR38H53J1M/
  acceptance_tests/test_ac7_ac8_push_retry_on_moved_main.py` применяет к
  телу гейта мержа). Имени нового гейта планка не знает и не может знать
  (SPEC его не называет — «Новый гейт в пакете
  `orchestrator/advance_gates/`»), поэтому наблюдается ИСХОД перехода
  `fsm.cmd_advance`, а не вызов гейта по имени: любое место нового гейта
  в списке `in_dev` даёт один и тот же наблюдаемый исход.
- `MergeAppendixSandbox` — задача на `merge_gate` с bare-origin в роли
  «main артели»: тело гейта (`_cmd_approve_merge_gate`) зовётся напрямую,
  тем же приёмом, что `tests/test_fsm_merge_gate_done_snapshot.py`.

Приложения в PLAN.md и сам текст диффов — из `_parse.py` (там же
контракт разбора и защищённые пути от `config.PROTECTED_PATHS`).
"""
import subprocess
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import _parse  # noqa: E402

from orchestrator import (acceptance, artifact_branch, catalog,  # noqa: E402
                          ci, config, fsm, fsm_advance, fsm_merge_gate,
                          store, workspace)
from tests.sandbox import (RealGitSandbox, capture,  # noqa: E402
                           capture_new_task_id)

# --------------------------------------------------- именованные тексты SPEC

# Действие журнала отказа гейта применимости (требование 2/AC-5) —
# дословно из формулировки критерия.
INAPPLICABLE_REFUSAL_ACTION = "переход отклонён: приложение PLAN неприменимо"

# Причина возврата в `in_dev` с мержа (требование 4/AC-9) — дословный
# префикс, путь дописывает реализация.
AFTER_PULL_REASON_PREFIX = "приложение PLAN неприменимо после подтяжки:"

# Именованный отказ мержа по красному полному прогону (требование 5/AC-10).
BROKEN_TESTS_REFUSAL = "приложения ломают тесты:"

# Запись журнала успешного применения (требование 6/AC-12).
APPLIED_JOURNAL_MARK = "приложения применены:"

# Сообщение коммита приложений (требование 3/AC-8) — `{task}` и перечень
# путей подставляет реализация, сверяется опорная часть.
APPLIED_COMMIT_MARK = "приложения Оператора"

# Сообщение коммита снимка артефактов (`fsm_merge_gate.
# _overlay_artifact_snapshot`, сегодняшнее) — ориентир порядка для AC-8.
SNAPSHOT_COMMIT_MARK = "снимок артефактной ветки поверх merge"

ARTEL_TARGETS_YAML = """targets:
  artel:
    forge: github
    url: https://example.invalid/artel
    base: {base}
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

# Содержимое защищённого файла-фикстуры в базе сравнения: три строки,
# чтобы у диффа был и контекст, и заменяемая строка.
PROTECTED_BASE_TEXT = "первая строка базы\nвторая строка базы\nтретья строка базы\n"


def stale_diff_block(path: str, marker: str) -> str:
    """Блок ```diff, заведомо НЕ применимый ни к одному дереву: контекст и
    заменяемая строка хунка в файле отсутствуют — тот самый класс
    приложения из инцидента 11.09 («хунк без совпадающего диапазона»),
    на котором `git apply --check` отвечает отказом."""
    return ("```diff\n"
            f"diff --git a/{path} b/{path}\n"
            f"--- a/{path}\n"
            f"+++ b/{path}\n"
            "@@ -1,3 +1,3 @@\n"
            " строки, которой в файле нет\n"
            "-второй строки, которой в файле нет\n"
            f"+{marker}\n"
            " третьей строки, которой в файле нет\n"
            "```\n")


# Защищённые файлы-фикстуры, заводимые в main ДО origin: приложения
# правят именно их. Три штуки — по одному на каждый класс требования 5
# (вне `tests/`/`.github/`, под `tests/`, под `.github/`).
FIXTURE_PROTECTED_FILES = (_parse.PROTECTED_FILE, _parse.PROTECTED_TESTS_FILE,
                           _parse.PROTECTED_GITHUB_FILE)


class _AppendixSandboxBase(RealGitSandbox):
    """Общий корень: настоящий git-репозиторий пульта с bare-origin в роли
    главной копии артели, `targets.yaml` для `repo_context.resolve` и
    защищённые файлы-фикстуры в main (их и правят приложения).

    Фикстуры коммитятся ДО `add_synced_origin()`: main origin — база
    плотницкого merge (`_origin_main_sha`), и файл, появившийся в main
    ПОСЛЕ создания origin, в дерево scratch не попал бы вовсе."""

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(
            ARTEL_TARGETS_YAML.format(base=config.MAIN_BRANCH),
            encoding="utf-8")
        for rel in FIXTURE_PROTECTED_FILES:
            self.write_protected_fixture(rel)
            self.git("add", rel)
        self.git("commit", "-q", "-m", "защищённые файлы-фикстуры")
        self.origin = self.add_synced_origin()
        capture(catalog.cmd_init)

    # ------------------------------------------------------------- фикстуры

    def write_protected_fixture(self, rel: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(PROTECTED_BASE_TEXT, encoding="utf-8")

    def applicable_diff_block(self, rel: str, marker: str) -> str:
        """Блок ```diff, порождённый НАСТОЯЩИМ `git diff` по файлу `rel`
        базы сравнения: применимость такого приложения не предполагается
        на глаз, а обеспечена git'ом (хедер хунка считает он). Файл в
        рабочем дереве восстанавливается сразу после снятия диффа."""
        path = self.root / rel
        before = path.read_text(encoding="utf-8")
        path.write_text(before.replace("вторая строка базы", marker),
                        encoding="utf-8")
        diff = self.git("diff", "--", rel)
        path.write_text(before, encoding="utf-8")
        self.assertIn(f"diff --git a/{rel} b/{rel}", diff,
                      "фикстура диффа пуста — правка не изменила файл")
        return f"```diff\n{diff}```\n"

    def commit_plan(self, sections: list[str] | None = None) -> None:
        """PLAN.md в артефактную ветку задачи — единственный источник
        приложений и для гейта `in_dev`, и для мержа."""
        sha = artifact_branch.commit_files(
            self.TASK,
            {f"tasks/{self.TASK}/PLAN.md": _parse.plan_text(self.TASK,
                                                             sections)},
            f"{self.TASK}: PLAN.md")
        self.assertTrue(sha, "PLAN.md не закоммичен в артефактную ветку")

    # -------------------------------------------------------------- чтение

    def row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.row()["state"]

    def journal(self) -> list[tuple[str, str]]:
        return [(r["action"], r["detail"] or "")
                for r in store.task_steps(store.db(), self.TASK)]

    def journal_blob(self) -> str:
        return "\n".join(f"{a} | {d}" for a, d in self.journal())

    def worktree_paths(self, repo: Path) -> list[str]:
        res = subprocess.run(["git", "-C", str(repo), "worktree", "list",
                              "--porcelain"], capture_output=True, text=True)
        return [line.split(" ", 1)[1] for line in res.stdout.splitlines()
                if line.startswith("worktree ")]

    def patch(self, target, attr: str, replacement) -> None:
        patcher = mock.patch.object(target, attr, replacement)
        patcher.start()
        self.addCleanup(patcher.stop)


class InDevAppendixSandbox(_AppendixSandboxBase):
    """Задача в `in_dev`: настоящая кодовая ветка с коммитом, настоящая
    артефактная ветка, соседние гейты выхода `in_dev` подменены
    «пройдено»."""

    TASK_TITLE = "Приложения PLAN к защищённым путям"
    CODE_FILE = "feature.txt"

    def setUp(self):
        super().setUp()
        _, self.TASK = capture_new_task_id(catalog.cmd_new, self.TASK_TITLE)
        self.conn = store.db()
        self.artifacts_branch = artifact_branch.branch_name(self.TASK)
        self.code_branch = self.row()["branch"]
        self.commit_code_file()
        store.update_task(self.conn, self.TASK, zones=self.CODE_FILE,
                          state="in_dev")
        self.tdir = config.TASKS / self.TASK
        self.tdir.mkdir(parents=True, exist_ok=True)
        self.bypass_neighbour_gates()

    def commit_code_file(self) -> None:
        """Коммит кода в ветку ЗАДАЧИ (её настоящий worktree): без него у
        ветки нет ни одного своего коммита, и база сравнения
        (`gitcmd.diff_base`) совпала бы с её головой."""
        wt_path, error = workspace.ensure(self.TASK, self.code_branch)
        self.assertIsNone(error, f"worktree задачи не создан: {error}")
        self.wt_path = wt_path
        (wt_path / self.CODE_FILE).write_text("код задачи\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(wt_path), "add", self.CODE_FILE],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(wt_path), "commit", "-q", "-m",
                        f"{self.TASK}: {self.CODE_FILE}"],
                       check=True, capture_output=True)

    def bypass_neighbour_gates(self) -> None:
        """Соседние рубежи выхода `in_dev` (`orchestrator/fsm_advance.py::
        in_dev`) — «пройдено»: предмет AC-5/AC-7 ровно один, новый гейт
        применимости приложений, а исход перехода обязан зависеть только
        от него. Подменяются СУЩЕСТВУЮЩИЕ имена рубежей: задача их не
        переименовывает (её правка в `fsm_advance.py` — добавление гейта в
        список), а их собственные сценарии кроют их собственные тесты
        `tests/test_zones_gate.py`/`test_capacity_gate.py`/
        `test_branch_freshness_gate.py`."""
        self.patch(fsm, "_dirty_refuses", lambda *a, **k: False)
        self.patch(fsm, "_pull_main_or_escalate", lambda *a, **k: "fresh")
        self.patch(fsm_advance, "_acceptance_lock_refuses",
                   lambda *a, **k: False)
        self.patch(fsm_advance, "_capacity_gate_refuses", lambda *a, **k: False)
        self.patch(fsm_advance, "_zones_gate_refuses", lambda *a, **k: False)
        self.patch(fsm_advance, "_mutation_claim_gate", lambda *a, **k: None)
        self.patch(fsm_advance, "_review_rework_gate_refuses",
                   lambda *a, **k: False)
        self.patch(fsm_advance, "_origin_push_gate", lambda *a, **k: None)
        self.patch(fsm_advance, "_acceptance_run_refuses", lambda *a, **k: False)

    def advance(self) -> str:
        """Настоящий `fsm.cmd_advance` на выходе из `in_dev`."""
        return self.capture(fsm.cmd_advance, self.TASK)

    def refusals(self) -> list[tuple[str, str]]:
        """(action, detail) записей журнала «переход отклонён …» — тот же
        признак, которым их отбирает `store.refusal_history` для брифа."""
        return [(action, detail) for action, detail in self.journal()
                if action.startswith(store.REFUSAL_ACTION_PREFIX)]


class MergeAppendixSandbox(_AppendixSandboxBase):
    """Задача на `merge_gate`: кодовая ветка в самом пульте, bare-origin в
    роли главной копии артели, зелёный CI, полный прогон под наблюдением.
    """

    TASK = "01APPENDIXONMERGETASK00001"
    CODE_FILE = "feature.txt"

    def setUp(self):
        super().setUp()
        self.branch = f"task/{self.TASK.lower()}-x"
        self.make_task_branch(self.branch)
        store.insert_task(store.db(), self.TASK, f"Задача {self.TASK}",
                          "merge_gate", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.conn = store.db()
        self.full_suite_calls: list = []
        self.full_suite_result = (True, "42 passed (тест)")
        self.patch(acceptance, "run_full_suite", self.fake_full_suite)
        self.patch(ci, "branch_status", lambda branch: (True, "зелёный (тест)"))

    def make_task_branch(self, branch: str) -> None:
        """Кодовая ветка задачи прямо в `self.root` (код артели живёт в её
        собственной ветке пульта). `git add <файл>` — именно файл, не
        `-A`: слепой `-A` затянул бы `.artel/` БД в коммит."""
        self.checkout(branch, create=True)
        (self.root / self.CODE_FILE).write_text("код задачи\n",
                                                encoding="utf-8")
        self.git("add", self.CODE_FILE)
        self.git("commit", "-q", "-m", f"{self.TASK}: {self.CODE_FILE}")
        self.checkout(config.MAIN_BRANCH)

    def fake_full_suite(self, root):
        """Подмена `acceptance.run_full_suite` (SPEC называет её дословно в
        требовании 5): запоминает корень прогона, СНИМОК защищённых
        файлов этого корня на момент вызова и отвечает заготовленным
        исходом — настоящий pytest внутри приёмочного теста гонять
        незачем, а предмет AC-10/AC-11 — факт вызова и то, что прогон
        видит уже применённое приложение."""
        root = Path(root)
        texts = {}
        for rel in FIXTURE_PROTECTED_FILES:
            path = root / rel
            texts[rel] = path.read_text(encoding="utf-8") \
                if path.is_file() else ""
        self.full_suite_calls.append({"root": root, "texts": texts})
        return self.full_suite_result

    def approve(self):
        """Тело гейта merge напрямую, как `tests/
        test_fsm_merge_gate_done_snapshot.py`: `confirmed_ci_note` —
        статус, который подставил бы внешний цикл после зелёного
        ожидания CI (иначе путь «fresh» вернул бы ("wait", branch), не
        дойдя до merge)."""
        t = store.get_task(store.db(), self.TASK)
        return fsm_merge_gate._cmd_approve_merge_gate(
            store.db(), self.TASK, "merge_gate", t,
            confirmed_ci_note="зелёный (тест)")

    def approve_catching_exit(self) -> tuple:
        """(исход тела гейта либо `None`, текст отказа) — отказ узла
        merge_gate живёт в кодовой базе в двух формах (`sys.exit`
        именованной причиной у `_guard_task_root_or_refuse`/«merge
        FAILED» и мягкий возврат `("stopped",)` у гейта защищённых
        путей), а критерии называют НАБЛЮДАЕМЫЙ след отказа, не его
        форму: текст собирается и из `SystemExit`, и из возврата, а
        «прошло или нет» тесты определяют по состоянию задачи, main
        origin и журналу (тот же приём, что `tasks/
        01M2XJKQNFTWHYAY4KBBQ1NVY7/acceptance_tests/_util.py::
        run_command`)."""
        try:
            return self.approve(), ""
        except SystemExit as exc:  # noqa: PERF203 — сам предмет проверки
            return None, str(exc.code)

    # -------------------------------------------------------- чтение origin

    def origin_git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.origin), *args],
                              capture_output=True, text=True)

    def origin_main_sha(self) -> str:
        res = self.origin_git("rev-parse", "refs/heads/" + config.MAIN_BRANCH)
        return res.stdout.strip() if res.returncode == 0 else ""

    def origin_main_subjects(self) -> list[str]:
        """Сообщения коммитов main origin от старых к новым — по ним
        проверяется и наличие коммита приложений, и его место
        относительно коммита снимка артефактов (AC-8)."""
        res = self.origin_git("log", "--format=%s", "--reverse",
                              "refs/heads/" + config.MAIN_BRANCH)
        return [s for s in res.stdout.splitlines() if s] \
            if res.returncode == 0 else []

    def origin_file_text(self, rel: str) -> str:
        res = self.origin_git("show",
                              f"refs/heads/{config.MAIN_BRANCH}:{rel}")
        return res.stdout if res.returncode == 0 else ""

    def origin_files_changed_by(self, subject_mark: str) -> list[str]:
        """Файлы, изменённые коммитом main origin, чьё сообщение несёт
        `subject_mark` — пусто, такого коммита нет."""
        res = self.origin_git(
            "log", "--format=%H %s", "refs/heads/" + config.MAIN_BRANCH)
        for line in res.stdout.splitlines():
            sha, _, subject = line.partition(" ")
            if subject_mark in subject:
                show = self.origin_git("show", "--name-only", "--format=",
                                       sha)
                return [p for p in show.stdout.splitlines() if p]
        return []
