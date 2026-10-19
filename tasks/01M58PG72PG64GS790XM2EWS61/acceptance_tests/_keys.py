"""Общая песочница планки ключа кэша итога полного набора (AC-12 — AC-15).

Дерево прогона — отдельный git worktree репозитория песочницы
`tests.sandbox.RealGitSandbox`; в нём закоммичен каталог `workdir` с
`.gitignore`, игнорирующим файл блокировки (имя — от зерна из пяти имён
требования 10), и сам игнорируемый файл лежит в рабочей копии. В
`targets.yaml` песочницы — артель (`pult-pytest`), учебная запись с
единственным компонентом `pytest-own` с `tools` и `workdir` и запись вида
sled (`test_profile`, `pytest-own`, `workdir`). Задачи каждого проекта
заведены в БД пульта песочницы.

Прогон набора подменён публичной точкой `acceptance.run_full_suite`
(зелёный итог с итоговой строкой pytest), ключ итога наблюдается так, как
им пользуются гейты: повторно ли `acceptance.full_suite` берёт итог (вызван
ли прогон) и под каким именем `gate-<ключ>.json`/`base-<ключ>.json` итог
лёг в `acceptance.suite_results_dir()`.
"""
import random
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, config, store
from tests.sandbox import RealGitSandbox, artel_target_entry

LETTERS = "abcdefghijkmnpqrstuvwxyz"
ULID = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LOCK_NAMES = ("uv.lock", "package-lock.json", "poetry.lock", "yarn.lock",
              "pnpm-lock.yaml")
GREEN = "========== 3 passed in 0.10s ==========\n"

HEAD = """  {name}:
    forge: github
    url: https://localhost/artel-tests/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

PROFILE_BODY = """{indent}command: [python3, -m, pytest]
{indent}long_lived_dir: tests
{indent}long_lived_name: test_<id>_<name>.py
{indent}weakening_scope: [tests/**/*.py]
{indent}mutation_claim_scope: [tests/test_*.py]
{indent}runner: pytest-own
{indent}workdir: {workdir}
"""


def tools_dict(tools) -> dict:
    """`Profile.tools` как отображение «инструмент → версия»: SPEC не
    задаёт форму поля, только смысл — объявленные инструменты компонента."""
    return dict(tools or {})


class KeySandbox(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used = set()
        self.project = f"p{self.word()}"
        self.sled = f"s{self.word()}"
        self.component = f"c{self.word(5)}"
        self.workdir = self.word(6)
        self.lock = self.rng.choice(LOCK_NAMES)
        self.tools = {f"t{self.word(5)}": str(self.rng.randrange(10, 30)),
                      f"t{self.word(5)}": f"{self.rng.randrange(1, 9)}."
                                          f"{self.rng.randrange(0, 20)}"}
        (self.root / self.workdir).mkdir()
        (self.root / self.workdir / ".gitignore").write_text(
            f"{self.lock}\n", encoding="utf-8")
        (self.root / self.workdir / "app.txt").write_text("x\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "workdir")
        holder = Path(tempfile.mkdtemp(prefix="artel-key-tree-")).resolve()
        self.addCleanup(shutil.rmtree, holder, True)
        self.tree = holder / "tree"
        self.git("worktree", "add", "-q", "--detach", str(self.tree),
                 config.MAIN_BRANCH)
        self.addCleanup(self.git, "worktree", "remove", "--force",
                        str(self.tree))
        self.set_lock(self.rng.randbytes(self.rng.randrange(1, 300)))
        self.write_targets(self.tools)
        self.tasks = {name: self.new_task(name) for name in
                      (config.DEFAULT_TARGET, self.project, self.sled)}

    def word(self, size: int = 7) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str = "") -> str:
        return f"{text}\nзерно: {self.seed}; файл блокировки {self.lock}"

    def new_task(self, target: str) -> str:
        task = "01M" + "".join(self.rng.choice(ULID) for _ in range(23))
        store.insert_task(store.db(), task, "Задача", "acceptance",
                          f"task/{task.lower()}-x", target, 25.0)
        return task

    def write_targets(self, tools: dict) -> str:
        """Запись артели, учебная запись с одним компонентом с `tools` и
        запись вида sled с `test_profile`."""
        single = (HEAD.format(name=self.project) + "    components:\n"
                  f"      {self.component}:\n"
                  + PROFILE_BODY.format(indent="        ", workdir=self.workdir)
                  + "        tools:\n"
                  + "".join(f'          {k}: "{v}"\n' for k, v in tools.items()))
        sled = (HEAD.format(name=self.sled) + "    test_profile:\n"
                + PROFILE_BODY.format(indent="      ", workdir=self.workdir))
        text = "targets:\n" + artel_target_entry() + single + sled
        config.TARGETS.write_text(text, encoding="utf-8")
        return text

    def set_lock(self, data: bytes) -> None:
        (self.tree / self.workdir / self.lock).write_bytes(data)

    def results(self) -> set:
        folder = acceptance.suite_results_dir()
        if not folder.is_dir():
            return set()
        return {p.name for p in folder.iterdir() if p.is_file()}

    def full(self, target: str, command) -> tuple[int, set]:
        """(сколько раз запущен набор, новые файлы итогов) — один вызов
        `acceptance.full_suite` дерева задачи проекта `target`."""
        before = self.results()
        with mock.patch.object(acceptance, "run_full_suite",
                               return_value=(True, GREEN)) as run:
            if command is None:
                acceptance.full_suite(self.tree, self.tasks[target])
            else:
                acceptance.full_suite(self.tree, self.tasks[target],
                                      command=command)
        return run.call_count, self.results() - before


def keys_of(names: set, kind: str) -> list:
    return sorted(n[len(kind) + 1:-len(".json")] for n in names
                  if n.startswith(f"{kind}-") and n.endswith(".json"))


_BASE_MODULE = None


def acceptance_at_base():
    """Модуль `orchestrator/acceptance.py` ревизии базы ветки задачи
    (`_pult.DIFF_BASE`) — код ключа «до правки». Загружается в пакет
    `orchestrator` отдельным именем: его относительные импорты берут
    текущие модули пакета (и подменённый песочницей `config`)."""
    global _BASE_MODULE
    if _BASE_MODULE is not None:
        return _BASE_MODULE
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _pult import CODE_ROOT, DIFF_BASE
    if not DIFF_BASE:
        raise AssertionError("пульт не назвал базу диффа задачи (DIFF_BASE) — "
                             "ключ до правки не с чем сверить")
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "show",
                          f"{DIFF_BASE}:orchestrator/acceptance.py"],
                         capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        raise AssertionError(f"acceptance.py базы {DIFF_BASE} не прочитан: "
                             f"{res.stderr.strip()}")
    name = "orchestrator._acceptance_at_diff_base"
    module = types.ModuleType(name)
    module.__package__ = "orchestrator"
    module.__file__ = f"{DIFF_BASE}:orchestrator/acceptance.py"
    sys.modules[name] = module
    exec(compile(res.stdout, module.__file__, "exec"), module.__dict__)
    _BASE_MODULE = module
    return module
