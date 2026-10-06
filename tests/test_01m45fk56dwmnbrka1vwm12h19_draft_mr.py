"""Подсветка защищённых путей в черновике MR задачи внешнего проекта — по
`no_paths` её записи.

Группа: долгоживущий
Красен до реализации: подсветка черновика MR берёт перечень пульта `config.PROTECTED_PATHS` для любого проекта — пути диффа под `no_paths` внешнего проекта в комментарии не названы, а путь, защищённый только у артели, назван.

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`); внешний проект —
клон с bare `origin` (`tests.sandbox.make_project_repo`), запись
`targets.yaml` песочницы с `forge: github` и полем `no_paths` из случайных
каталогов `zn…/` и файлов `zn….cfg`. Ветка задачи заведена рабочей копией
(`workspace.ensure`), код закоммичен в неё. Черновик заводит
`github_adapter.ensure_draft_mr`; `push` ветки идёт в настоящий bare
`origin`, фордж (`gh`) подменён шпионом — он отвечает успехом и запоминает
аргументы каждого вызова. Наблюдается текст комментария `gh pr comment`.

Провалидировано временным стабом реализации (удалён, не закоммичен):
подсветка по перечню проекта задачи — метод зелёный.

Зерно печатается и входит в текст каждого провала.
"""
import random
import re
import subprocess
import unittest
from unittest import mock

from orchestrator import config, github_adapter, idgen, store, workspace
from tests.sandbox import RealGitSandbox, make_project_repo

ARTEL = config.DEFAULT_TARGET
EXT = "vnesh"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
# Перечень путей в тексте подсветки `github_adapter.ensure_draft_mr`:
# «… затрагивает защищённые пути: a, b (<источник перечня>).»
HIGHLIGHT_PATHS = re.compile(r"затрагивает защищённые пути: (.+) \(")

TARGET_ENTRY = """  {name}:
    forge: github
    url: {url}
    base: {base}
    token_slot: {name}-token
    no_paths: [{no_paths}]
    project_skills: []
    merge_gate: operator
"""

# Профиль тестов артели — как в `targets.yaml` пульта: без него пульт
# проекту артели отказывает (fail-closed). Внешнему проекту не пишется.
ARTEL_PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
"""


class DraftMrSandbox(RealGitSandbox):
    """Клон внешнего проекта и шпион форджа."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        make_project_repo(EXT)
        self.no_paths = []
        while len(self.no_paths) < 3:
            name = f"zn{self.word()}" + self.rng.choice(("/", ".cfg"))
            if name not in self.no_paths:
                self.no_paths.append(name)
        config.TARGETS.write_text(
            "targets:\n"
            + TARGET_ENTRY.format(name=ARTEL, url="http://localhost/artel",
                                  base=config.MAIN_BRANCH,
                                  no_paths=", ".join(config.PROTECTED_PATHS))
            + ARTEL_PROFILE
            + TARGET_ENTRY.format(name=EXT, url="http://localhost/vnesh",
                                  base=config.MAIN_BRANCH,
                                  no_paths=", ".join(self.no_paths)),
            encoding="utf-8")
        self.gh_calls: list = []
        patcher = mock.patch.object(github_adapter.ci, "gh", self.spy_gh)
        patcher.start()
        self.addCleanup(patcher.stop)

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def explain(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def spy_gh(self, *args, **kwargs):
        self.gh_calls.append((list(args), dict(kwargs)))
        return subprocess.CompletedProcess(list(args), 0,
                                           "http://localhost/vnesh/pull/1\n", "")

    def under(self, entry: str) -> str:
        if entry.startswith("**/"):
            return f"zd{self.word()}/{entry[3:]}"
        if entry.endswith("/"):
            return f"{entry}{self.word()}.md"
        return entry

    def artel_only_path(self) -> str:
        return self.under(self.rng.choice(config.PROTECTED_PATHS))

    def draft_for(self, files: list[str]) -> list[str]:
        """Задача внешнего проекта с кодом `files` в ветке; `ensure_draft_mr`;
        возврат — тексты комментариев `gh pr comment`."""
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-mr"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}",
                          "in_dev", branch, EXT, config.DEFAULT_BUDGET_USD)
        wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.explain(f"рабочая копия не заведена: {error}"))
        for rel in files:
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{rel} {self.seed}\n", encoding="utf-8")
        self.git("-C", str(wt), "add", "-A")
        self.git("-C", str(wt), "commit", "-q", "-m", f"{task_id}: код задачи")
        self.gh_calls.clear()
        github_adapter.ensure_draft_mr(self.conn, task_id,
                                       store.get_task(self.conn, task_id))
        creates = [a for a, _kw in self.gh_calls if a[:2] == ["pr", "create"]]
        self.assertTrue(creates, self.explain(
            f"черновик не заведён: {self.gh_calls}; журнал: "
            f"{[dict(r) for r in store.task_steps(self.conn, task_id)]}"))
        return [" ".join(a) for a, _kw in self.gh_calls if a[:2] == ["pr", "comment"]]


class DraftMrHighlightTest(DraftMrSandbox):

    def highlighted(self, comments: list[str]) -> list[str]:
        """Пути, которые назвали комментарии подсветки: перечень между
        «защищённые пути: » и « (<источник перечня>)» — не весь текст, в
        котором источник «no_paths проекта … в targets.yaml» назван всегда."""
        named: list[str] = []
        for comment in comments:
            match = HIGHLIGHT_PATHS.search(comment)
            self.assertIsNotNone(match, self.explain(
                f"комментарий без перечня путей: {comment}"))
            named.extend(match.group(1).split(", "))
        return named

    def test_ac6_highlight_lists_no_paths_and_omits_artel_only_paths(self):
        """Комментарий черновика MR внешнего проекта называет пути диффа под его `no_paths` и не называет пути, защищённые только у артели.

        Сценарий: дифф задачи внешнего проекта — файл кода, один-два пути под
        записями `no_paths` проекта и по пути под КАЖДОЙ записью
        `config.PROTECTED_PATHS` (их нет в `no_paths`). После
        `ensure_draft_mr` перечень путей, названных комментариями
        `gh pr comment`, содержит каждый путь `no_paths` и — подтестом на
        каждую запись перечня пульта — не содержит её путь. Вторая задача —
        файл кода и только пути под каждой записью перечня пульта: перечень
        не содержит ни одного (подтест на запись).

        Ловит мутацию: подсветка сверяет дифф с `config.PROTECTED_PATHS` для
        любого проекта — пути `no_paths` выпадают из комментария (или
        комментария нет вовсе), а путь пульта в нём назван; перечень берётся
        из записи артели, а не проекта задачи.
        """
        ext_paths = [self.under(e) for e in
                     self.rng.sample(self.no_paths, self.rng.randint(1, 2))]
        artel_paths = {e: self.under(e) for e in config.PROTECTED_PATHS}
        code = f"kod{self.word()}/{self.word()}.py"
        comments = self.draft_for([code, *artel_paths.values(), *ext_paths])
        named = self.highlighted(comments)
        for rel in ext_paths:
            self.assertIn(rel, named, self.explain(
                f"путь no_paths {rel} не подсвечен: {comments}"))
        for entry, artel_path in artel_paths.items():
            with self.subTest(scenario="no_paths и пути пульта", entry=entry):
                self.assertNotIn(artel_path, named, self.explain(
                    f"путь пульта {artel_path} подсвечен: {comments}"))

        artel_paths = {e: self.under(e) for e in config.PROTECTED_PATHS}
        comments = self.draft_for([f"kod{self.word()}/{self.word()}.py",
                                   *artel_paths.values()])
        named = self.highlighted(comments)
        for entry, artel_path in artel_paths.items():
            with self.subTest(scenario="только пути пульта", entry=entry):
                self.assertNotIn(artel_path, named, self.explain(
                    f"путь пульта {artel_path} подсвечен: {comments}"))


if __name__ == "__main__":
    unittest.main()
