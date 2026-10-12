"""Выбор базы сравнения джоба `protected-paths`: первый родитель
merge-коммита PR против `BASE_SHA` события (`scripts/ci_protected_paths.py`).

Группа: долгоживущий
Красен до реализации: скрипт сегодня всегда сравнивает от `BASE_SHA` и не печатает источник базы — случай 11.10 даёт код 1 вместо 0, перечень `HEAD^1` не читается, строк «первый родитель merge-коммита PR»/«BASE_SHA события» и названного невыполненного условия в выводе нет.

Держит связку «скрипт — настоящий git»: форма HEAD (число родителей,
предок, второй родитель) видна только в живом репозитории, поэтому каждый
сценарий строит временный репозиторий песочницы (`RealGitSandbox`) и
запускает скрипт отдельным процессом с явным окружением без переменных
`GITHUB_*` раннера; файл события — временный. Имена защищённых и обычных
путей порождаются заново при каждом запуске модулем `random`; зерно
печатается и входит в текст каждого провала.
"""
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.sandbox import RealGitSandbox

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "ci_protected_paths.py"
CONFIG_REL = "orchestrator/config.py"

SOURCE_MERGE = "первый родитель merge-коммита PR"
SOURCE_EVENT = "BASE_SHA события"

# Слова, которыми вывод называет невыполненное условие требования 1 SPEC.
# Формулировку SPEC не фиксирует — принимается любое из естественных
# названий условия; различие условий между собой проверяется отдельно.
COND_PARENTS = ("два родителя", "двух родител", "ровно два", "2 родител",
                "число родител", "родителей", "parents")
COND_ANCESTOR = ("предок", "предка", "is-ancestor", "merge-base")
COND_SECOND = ("head^2", "второй родитель", "второго родителя", "head.sha")
COND_EVENT = ("github_event_path", "файл события", "файла события",
              "файле события", "pull_request.head.sha", "json")


class MergeBaseChoiceTest(RealGitSandbox):
    """Сценарии выбора базы на временном репозитории."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        rng = random.Random(self.seed)
        n = rng.randrange(10 ** 6)
        self.prot_dir = f"guard{n}/"
        self.prot_file = f"lock{n}.yaml"
        self.prot_path = rng.choice(
            [f"{self.prot_dir}item{rng.randrange(1000)}.md", self.prot_file])
        self.plain = f"doc{rng.randrange(10 ** 6)}.txt"
        self.protected = [self.prot_dir, self.prot_file]
        self.event_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.event_dir, ignore_errors=True)
        self.git_dir = os.path.dirname(shutil.which("git"))

    # --- построение репозитория -------------------------------------------

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.git("add", "--", rel)

    def write_config(self, paths) -> None:
        self.write(CONFIG_REL, f"PROTECTED_PATHS = {tuple(paths)!r}\n")

    def commit(self, message: str) -> str:
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.sha("HEAD")

    def sha(self, rev: str) -> str:
        return self.git("rev-parse", rev).strip()

    def base_commit(self, paths=None) -> str:
        """Коммит `BASE_SHA` на main: перечень защищённых путей фикстуры."""
        self.write_config(self.protected if paths is None else paths)
        return self.commit("база")

    def pr_branch(self, base: str, files=(), config=None, branch="pr") -> str:
        """Ветка PR от `base`: правит `files` (и перечень, если задан)."""
        self.git("checkout", "-q", "-b", branch, base)
        self.write(f"pr-{branch}.txt", "ветка\n")
        for rel in files:
            self.write(rel, f"правка ветки {rel}\n")
        if config is not None:
            self.write_config(config)
        head = self.commit("ветка PR")
        self.git("checkout", "-q", "main")
        return head

    def main_moves(self, files=(), config=None, remove_config=False,
                   raw_config=None) -> str:
        """Коммит Оператора в main после `BASE_SHA` — будущий `HEAD^1`."""
        self.git("checkout", "-q", "main")
        self.moves = getattr(self, "moves", 0) + 1
        self.write(f"main-{self.moves}.txt", "main\n")
        for rel in files:
            self.write(rel, f"правка main {rel}\n")
        if config is not None:
            self.write_config(config)
        if raw_config is not None:
            self.write(CONFIG_REL, raw_config)
        if remove_config:
            self.git("rm", "-q", "--", CONFIG_REL)
        return self.commit("main после базы")

    def merge_head(self, first: str, *others: str) -> str:
        """HEAD — merge-коммит `first` с `others` (как `refs/pull/N/merge`)."""
        self.git("checkout", "-q", "--detach", first)
        self.git("merge", "-q", "--no-ff", "-m", "merge", *others)
        return self.sha("HEAD")

    def detach(self, rev: str) -> None:
        self.git("checkout", "-q", "--detach", rev)

    def event(self, head_sha: str) -> Path:
        path = self.event_dir / f"event-{random.randrange(10 ** 9)}.json"
        path.write_text(json.dumps(
            {"pull_request": {"head": {"sha": head_sha},
                              "base": {"sha": "0" * 40}}}), encoding="utf-8")
        return path

    def raw_event(self, text: str) -> Path:
        path = self.event_dir / f"raw-{random.randrange(10 ** 9)}.json"
        path.write_text(text, encoding="utf-8")
        return path

    # --- запуск скрипта ---------------------------------------------------

    def run_script(self, base_sha: str, event_path=None,
                   path_prefix: str = "") -> subprocess.CompletedProcess:
        env = {"PATH": f"{path_prefix}{self.git_dir}:/usr/bin:/bin",
               "HOME": str(self.event_dir),
               "PYTHONIOENCODING": "utf-8",
               "BASE_SHA": base_sha}
        if event_path is not None:
            env["GITHUB_EVENT_PATH"] = str(event_path)
        return subprocess.run([sys.executable, str(SCRIPT)], cwd=self.root,
                              env=env, capture_output=True, text=True,
                              encoding="utf-8", timeout=60)

    def why(self, res) -> str:
        return (f"зерно: {self.seed}; код {res.returncode}\n"
                f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}")

    def output(self, res) -> str:
        return res.stdout + res.stderr

    def assert_names(self, res, markers, what: str) -> None:
        text = self.output(res).lower()
        self.assertTrue(any(m.lower() in text for m in markers),
                        f"вывод не называет условие «{what}»; " + self.why(res))

    def assert_source(self, res, source: str, sha: str) -> None:
        out = self.output(res)
        self.assertIn(source, out, self.why(res))
        self.assertIn(sha[:7], out, self.why(res))

    def scenario_1110(self):
        """Случай 11.10: main правит защищённый путь после `BASE_SHA`, ветка
        PR его не трогает, HEAD — merge-коммит PR. -> (base, head1, pr)."""
        base = self.base_commit()
        pr = self.pr_branch(base, files=[self.plain])
        head1 = self.main_moves(files=[self.prot_path])
        self.merge_head(head1, pr)
        return base, head1, pr

    # --- критерии ---------------------------------------------------------

    def test_ac1_main_moved_protected_path_after_base_is_green(self):
        """Случай 11.10: Оператор правит защищённый путь в main после
        `BASE_SHA`, ветка PR этот путь не трогает, HEAD — merge-коммит PR
        с корректным файлом события — код 0.

        Ловит мутацию: при доказанном merge-коммите PR база всё равно
        берётся от `BASE_SHA` (или от второго родителя `HEAD^2`) — дифф
        несёт правку main, и джоб красный с кодом 1 вместо 0.
        """
        base, head1, pr = self.scenario_1110()

        res = self.run_script(base, self.event(pr))

        self.assertEqual(res.returncode, 0, self.why(res))

    def test_ac2_list_and_diff_come_from_first_parent(self):
        """Путь, внесённый в перечень только коммитом main после `BASE_SHA`
        (`HEAD^1`) и изменённый веткой PR, — код 1.

        Ловит мутацию: перечень берётся от `BASE_SHA` или от `HEAD^2`
        вместо `HEAD^1` — нового пути в нём нет, и PR, правящий его,
        проходит с кодом 0 вместо 1.
        """
        fresh = f"fresh{random.Random(self.seed).randrange(10 ** 6)}/"
        base = self.base_commit()
        pr = self.pr_branch(base, files=[f"{fresh}x.md"])
        head1 = self.main_moves(config=self.protected + [fresh])
        self.merge_head(head1, pr)

        res = self.run_script(base, self.event(pr))

        self.assertEqual(res.returncode, 1, self.why(res))

    def test_ac3_pr_changing_protected_path_is_red_in_both_forms(self):
        """Ветка PR правит защищённый путь: код 1 и при merge-коммите PR,
        и при HEAD с одним родителем (голова ветки, база `BASE_SHA`).

        Ловит мутацию: дифф от `HEAD^1` считается с переставленными
        концами (`HEAD...HEAD^1`) — он пуст, и PR, правящий защищённый
        путь, проходит с кодом 0 вместо 1.
        """
        base = self.base_commit()
        pr = self.pr_branch(base, files=[self.prot_path])
        head1 = self.main_moves(files=[self.plain])
        self.merge_head(head1, pr)
        event = self.event(pr)

        with self.subTest(form="merge-коммит PR"):
            res = self.run_script(base, event)
            self.assertEqual(res.returncode, 1, self.why(res))
        with self.subTest(form="один родитель"):
            self.detach(pr)
            res = self.run_script(base, event)
            self.assertEqual(res.returncode, 1, self.why(res))

    def test_ac4_main_merged_into_task_branch_keeps_base_sha(self):
        """HEAD — слияние main в ветку задачи: два родителя, `HEAD^2` (вершина
        main) не голова PR из файла события, защищённый путь изменён более
        ранним коммитом ветки — код 1, база `BASE_SHA`, вывод называет
        условие «второй родитель не голова PR».

        Ловит мутацию: сверка `HEAD^2` с `pull_request.head.sha` удалена —
        слияние main в ветку принято за merge-коммит PR, база `HEAD^1`
        (вершина ветки) прячет ранний коммит ветки, и код 0 вместо 1.
        """
        base = self.base_commit()
        self.pr_branch(base, files=[self.prot_path], branch="task")
        self.git("checkout", "-q", "task")
        self.write(f"later-{self.plain}", "поздний коммит ветки\n")
        task_tip = self.commit("поздний коммит ветки")
        main_tip = self.main_moves(files=[self.plain])
        head = self.merge_head(task_tip, main_tip)

        res = self.run_script(base, self.event(head))

        self.assertEqual(res.returncode, 1, self.why(res))
        self.assert_source(res, SOURCE_EVENT, base)
        self.assert_names(res, COND_SECOND, "второй родитель не голова PR")

    def test_ac5_each_failed_condition_falls_back_and_is_named(self):
        """Каждое невыполненное условие по отдельности — не ровно два
        родителя (один, три), `BASE_SHA` не предок `HEAD^1`, `HEAD^2` не
        голова PR — база `BASE_SHA`, и вывод называет именно это условие.

        Ловит мутацию: проверка одного из условий выброшена (например,
        «`BASE_SHA` — предок `HEAD^1`» или «ровно два родителя» при
        осьминожьем слиянии) — сценарий с этим условием берёт базу
        `HEAD^1`, и вывод называет источник «первый родитель merge-коммита
        PR» вместо «BASE_SHA события».
        """
        base = self.base_commit()
        pr = self.pr_branch(base, files=[self.plain])
        other = self.pr_branch(base, files=[f"o-{self.plain}"], branch="other")
        side = self.pr_branch(base, files=[f"s-{self.plain}"], branch="side")
        head1 = self.main_moves(files=[f"m-{self.plain}"])

        cases = []
        self.detach(pr)
        cases.append(("один родитель", base, COND_PARENTS,
                      self.run_script(base, self.event(pr))))
        self.merge_head(head1, pr, other)
        cases.append(("три родителя", base, COND_PARENTS,
                      self.run_script(base, self.event(pr))))
        self.merge_head(head1, pr)
        cases.append(("BASE_SHA не предок HEAD^1", side, COND_ANCESTOR,
                      self.run_script(side, self.event(pr))))
        cases.append(("HEAD^2 не голова PR", base, COND_SECOND,
                      self.run_script(base, self.event(other))))

        for what, used_base, markers, res in cases:
            with self.subTest(case=what):
                self.assertIn(res.returncode, (0, 1), self.why(res))
                self.assert_source(res, SOURCE_EVENT, used_base)
                self.assertNotIn(SOURCE_MERGE, self.output(res), self.why(res))
                self.assert_names(res, markers, what)

    def test_ac5_git_error_on_ancestor_check_is_failed_condition(self):
        """HEAD — merge-коммит PR с корректным файлом события, а `BASE_SHA` —
        несуществующий sha (`git merge-base --is-ancestor` отвечает 128):
        откат на `BASE_SHA` с названной причиной, итог — код 2.

        Ловит мутацию: ошибка git 128 при проверке предка трактуется как
        выполненное условие — скрипт берёт базу `HEAD^1`, ветка PR чистая,
        и код 0 вместо 2.
        """
        base = self.base_commit()
        pr = self.pr_branch(base, files=[self.plain])
        head1 = self.main_moves(files=[f"m-{self.plain}"])
        self.merge_head(head1, pr)
        rng = random.Random(self.seed)
        ghost = "".join(rng.choice("0123456789abcdef") for _ in range(40))

        res = self.run_script(ghost, self.event(pr))

        self.assertEqual(res.returncode, 2, self.why(res))
        self.assert_names(res, COND_ANCESTOR, "BASE_SHA не предок HEAD^1")
        self.assertNotIn(SOURCE_MERGE, self.output(res), self.why(res))

    def test_ac6_unreadable_event_file_falls_back_to_base_sha(self):
        """Файла события нет, он не JSON, в нём нет `pull_request.head.sha`,
        `GITHUB_EVENT_PATH` не задан — откат на `BASE_SHA` с названной
        причиной; вердикт прежний: защищённый путь в диффе от `BASE_SHA` —
        код 1, без него — код 0.

        Ловит мутацию: нечитаемый файл события проглочен как выполненное
        условие (`except: True`) — случай 11.10 берёт базу `HEAD^1` и даёт
        код 0 вместо 1.
        """
        def events():
            return [("файла нет", self.event_dir / "missing.json"),
                    ("не JSON", self.raw_event("{не json")),
                    ("нет head.sha", self.raw_event(
                        json.dumps({"pull_request": {"head": {}}}))),
                    ("GITHUB_EVENT_PATH не задан", None)]

        base, _head1, _pr = self.scenario_1110()
        for what, event in events():
            with self.subTest(case=what, verdict=1):
                res = self.run_script(base, event)
                self.assertEqual(res.returncode, 1, self.why(res))
                self.assert_source(res, SOURCE_EVENT, base)
                self.assert_names(res, COND_EVENT, what)

        self.git("checkout", "-q", "-B", "main", base)
        clean_pr = self.pr_branch(base, files=[self.plain], branch="clean")
        clean_head1 = self.main_moves(files=[f"m-{self.plain}"])
        self.merge_head(clean_head1, clean_pr)
        for what, event in events():
            with self.subTest(case=what, verdict=0):
                res = self.run_script(base, event)
                self.assertEqual(res.returncode, 0, self.why(res))
                self.assert_source(res, SOURCE_EVENT, base)
                self.assert_names(res, COND_EVENT, what)

    def test_ac7_empty_base_sha_is_code_2_in_any_head_form(self):
        """Пустой `BASE_SHA` (пустая строка и пробелы) — код 2 и при HEAD с
        одним родителем, и при merge-коммите PR с корректным файлом события.

        Ловит мутацию: при пустом `BASE_SHA` и доказуемом по остальным
        признакам merge-коммите скрипт берёт базу `HEAD^1` — чистая ветка
        проходит с кодом 0 вместо 2.
        """
        base = self.base_commit()
        pr = self.pr_branch(base, files=[self.plain])
        head1 = self.main_moves(files=[f"m-{self.plain}"])
        for empty in ("", "   "):
            with self.subTest(form="один родитель", base_sha=repr(empty)):
                self.detach(pr)
                res = self.run_script(empty, self.event(pr))
                self.assertEqual(res.returncode, 2, self.why(res))
            with self.subTest(form="merge-коммит PR", base_sha=repr(empty)):
                self.merge_head(head1, pr)
                res = self.run_script(empty, self.event(pr))
                self.assertEqual(res.returncode, 2, self.why(res))
                self.assertIn("BASE_SHA", self.output(res), self.why(res))

    def test_ac8_output_names_base_and_source_on_codes_0_and_1(self):
        """Вывод называет sha использованной базы и её источник — «первый
        родитель merge-коммита PR» либо «BASE_SHA события» — и при коде 0,
        и при коде 1.

        Ловит мутацию: строка базы печатается только вместе с нарушениями
        — зелёный прогон (код 0) молчит о том, от чего сравнивал.
        """
        base, head1, pr = self.scenario_1110()
        with self.subTest(source=SOURCE_MERGE, code=0):
            res = self.run_script(base, self.event(pr))
            self.assertEqual(res.returncode, 0, self.why(res))
            self.assert_source(res, SOURCE_MERGE, head1)
        with self.subTest(source=SOURCE_EVENT, code=1):
            res = self.run_script(base, None)
            self.assertEqual(res.returncode, 1, self.why(res))
            self.assert_source(res, SOURCE_EVENT, base)

        self.git("checkout", "-q", "-B", "main", base)
        dirty = self.pr_branch(base, files=[self.prot_path], branch="dirty")
        self.merge_head(self.main_moves(files=[self.plain]), dirty)
        dirty_head1 = self.sha("HEAD^1")
        with self.subTest(source=SOURCE_MERGE, code=1):
            res = self.run_script(base, self.event(dirty))
            self.assertEqual(res.returncode, 1, self.why(res))
            self.assert_source(res, SOURCE_MERGE, dirty_head1)
        with self.subTest(source=SOURCE_EVENT, code=0):
            self.git("checkout", "-q", "-B", "main", base)
            clean = self.pr_branch(base, files=[self.plain], branch="clean")
            self.detach(clean)
            res = self.run_script(base, self.event(clean))
            self.assertEqual(res.returncode, 0, self.why(res))
            self.assert_source(res, SOURCE_EVENT, base)

    def test_ac9_unreadable_list_at_first_parent_is_code_2(self):
        """Все три условия выполнены, а перечень `HEAD^1` не прочитан (файла
        `orchestrator/config.py` нет; значение не разбирается) — код 2 с
        названной причиной, хотя откат на чистый `BASE_SHA` дал бы 0.

        Ловит мутацию: нечитаемый перечень `HEAD^1` ведёт к откату на
        `BASE_SHA` — перечень и дифф базы читаются, нарушений нет, и код 0
        вместо 2.
        """
        root_commit = self.sha("HEAD")
        variants = (("файла нет", "gone", {"remove_config": True}),
                    ("значение не разбирается", "bad",
                     {"raw_config": "PROTECTED_PATHS = tuple(sorted(x))\n"}))
        for what, branch, broken in variants:
            with self.subTest(case=what):
                self.git("checkout", "-q", "-B", "main", root_commit)
                base = self.base_commit()
                pr = self.pr_branch(base, files=[self.plain], branch=branch)
                head1 = self.main_moves(**broken)
                self.merge_head(head1, pr)

                res = self.run_script(base, self.event(pr))

                self.assertEqual(res.returncode, 2, self.why(res))
                self.assert_names(res, (CONFIG_REL, "PROTECTED_PATHS"),
                                  "перечень HEAD^1 не прочитан")

    def test_ac9_diff_failure_from_first_parent_is_code_2(self):
        """Все три условия выполнены, а `git diff` от `HEAD^1` отказывает
        (обёртка `git` в `PATH` отказывает только на `diff` от sha `HEAD^1`
        и его символьных форм, остальное передаёт настоящему git) — код 2 с
        названной причиной, без отката на `BASE_SHA`.

        Ловит мутацию: сбой диффа от `HEAD^1` ведёт к откату на `BASE_SHA` —
        дифф базы читается, и код 0 или 1 вместо 2.
        """
        base, head1, pr = self.scenario_1110()
        wrapper_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, wrapper_dir, ignore_errors=True)
        wrapper = wrapper_dir / "git"
        wrapper.write_text(
            "#!/bin/sh\n"
            "is_diff=0\nhit=0\n"
            'for a in "$@"; do\n'
            '  case "$a" in diff) is_diff=1;; esac\n'
            f'  case "$a" in *{head1}*|*"HEAD^"*|*"HEAD~"*) hit=1;; esac\n'
            "done\n"
            'if [ "$is_diff" = 1 ] && [ "$hit" = 1 ]; then\n'
            '  echo "fatal: подстроенный отказ диффа" >&2\n'
            "  exit 128\n"
            "fi\n"
            f'exec "{shutil.which("git")}" "$@"\n', encoding="utf-8")
        wrapper.chmod(0o755)

        res = self.run_script(base, self.event(pr),
                              path_prefix=f"{wrapper_dir}:")

        self.assertEqual(res.returncode, 2, self.why(res))
        self.assert_names(res, ("дифф", "diff"), "дифф от HEAD^1 не собран")

    def test_ac9_unreadable_list_at_base_sha_on_fallback_is_code_2(self):
        """Условие требования 1 не выполнено (HEAD с одним родителем; файла
        события нет), а в `BASE_SHA` нет `orchestrator/config.py` — код 2 с
        названной причиной.

        Ловит мутацию: нечитаемый перечень `BASE_SHA` при откате сведён к
        пустому списку — нарушений нет, и код 0 вместо 2.
        """
        root_commit = self.sha("HEAD")
        pr = self.pr_branch(root_commit, files=[self.plain])
        head1 = self.main_moves(config=self.protected)
        for what, merge, event in (("один родитель", False, True),
                                   ("файла события нет", True, False)):
            with self.subTest(case=what):
                if merge:
                    self.merge_head(head1, pr)
                else:
                    self.detach(pr)
                res = self.run_script(root_commit,
                                      self.event(pr) if event else None)
                self.assertEqual(res.returncode, 2, self.why(res))
                self.assert_names(res, (CONFIG_REL, "PROTECTED_PATHS"),
                                  "перечень BASE_SHA не прочитан")

    def test_ac10_branch_adding_its_own_file_to_list_stays_green(self):
        """Ветка создаёт файл и тем же коммитом вносит его в
        `PROTECTED_PATHS` — код 0 при merge-коммите PR и при прежней базе
        `BASE_SHA` (HEAD с одним родителем).

        Ловит мутацию: перечень берётся из дерева HEAD (или `HEAD^2`), а не
        из базы сравнения — новый путь ветки в нём есть, и PR красит сам
        себя кодом 1 вместо 0.
        """
        own = f"own{random.Random(self.seed).randrange(10 ** 6)}.yaml"
        base = self.base_commit()
        pr = self.pr_branch(base, files=[own], config=self.protected + [own])
        head1 = self.main_moves(files=[self.plain])
        with self.subTest(form="merge-коммит PR"):
            self.merge_head(head1, pr)
            res = self.run_script(base, self.event(pr))
            self.assertEqual(res.returncode, 0, self.why(res))
        with self.subTest(form="база BASE_SHA"):
            self.detach(pr)
            res = self.run_script(base, self.event(pr))
            self.assertEqual(res.returncode, 0, self.why(res))
