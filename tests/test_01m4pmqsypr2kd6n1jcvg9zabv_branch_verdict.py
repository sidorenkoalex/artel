"""Вердикт CI на `verifying` и гейте мержа строится по проверкам прогонов
ветки задачи: проверка, чей прогон найден в индексе `actions/runs` и чья
головная ветка (`head_branch`) — другая непустая ветка, из вердикта
исключается и называется в тексте; красная проверка ветки, красная и на
вершине main, получает фразу «красный унаследован от main <sha>».

Группа: долгоживущий

Красен до реализации: `verifying_status` и `branch_status` судят по всем check-run'ам коммита и `head_branch` прогона не читают — красная проверка прогона main на том же коммите красит задачу (AC-1, AC-5), коммит только с чужими проверками даёт красный/зелёный вместо «проверок нет / идут» (AC-3), исполненный близнец чужой ветки засчитывается полному набору (AC-4), фразы «унаследован от main» и подсказки pull-main нет (AC-6, расклад «унаследован» в AC-7); метод AC-2 и раскладки исключённой проверки в AC-7 зелены и до реализации — они держат то, что исключение не должно сломать.

Планка провалидирована временным стабом реализации (фильтр проверок по
`head_branch` прогона из индекса, фраза об исключённых проверках, фраза
«унаследован от main» через `ci.head_sha("main")` и
`ci.failed_check_names`); все методы зелёные, стаб удалён.

GitHub изображает подставной `ci.gh` (публичная точка выхода модуля в
`gh`, её же подменяют `tests/test_ci_status.py` и соседи), голову ветки —
подставной `ci.head_sha`. Подставной `gh` отвечает на:
- `api …/commits/<sha>/check-runs` — check-run'ы коммита, у каждого
  связанного — `check_suite.id` его прогона и ссылка
  `…/actions/runs/<id прогона>/job/<id>`;
- `api …/actions/runs?head_sha=<sha>` (с `branch=`/`event=` — отбор, как
  у GitHub) — прогоны коммита: `id`, `event`, `check_suite_id`,
  `head_sha` и головная ветка под ключом, который задаёт сценарий;
- `run list --branch <ветка>` — прогоны ветки в форме CLI.
Остальное отвечает ненулевым кодом.

Имена проверок, ветка задачи, чужая ветка, sha, id прогонов и
check-run'ов, события, заключения провала, порядок прогонов в ответе и вид
сбоя запроса прогонов выбираются случайно; зерно печатается и входит в
текст провала.
"""
import json
import random
import re
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from orchestrator import ci

CHECK_NAMES = (
    "Синтаксис и тесты оркестратора",
    "Инварианты на минимальной версии Python",
    "protected-paths",
    "id-format-greplint",
    "Свежесть карты кода",
    "Линтер шаблонов",
    "Сборка документации",
)
BAD_CONCLUSIONS = ("failure", "timed_out", "cancelled")
EVENTS = ("push", "pull_request")
OWNER_REPO = "artel-owner/artel"
# Подстроки, по которым разбирают текст статуса (требование 5).
PARSED = ("не зелёный:", "ещё идёт", "неизвестен", "check-run id")
INHERITED = "унаследован от main"
INHERITED_RE = re.compile(r"красный унаследован от main ([0-9a-fA-F]+)")
PULL_HINT = "подтянуть main в ветку задачи: artel.py pull-main <id задачи>"
# Ключ головной ветки «отсутствует» — прогон без поля ветки.
NO_KEY = None


def stamp(minutes_ago: float) -> str:
    moment = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def completed(args, stdout: str = "", returncode: int = 0,
              stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(list(args), returncode, stdout, stderr)


class FakeGitHub:
    """Подставной `ci.gh`: check-run'ы коммитов и их workflow-прогоны."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.runs: list[dict] = []
        self.checks: dict[str, list[dict]] = {}
        # "" — исправен; "code"/"garbage" — запрос прогонов отвечает
        # ненулевым кодом либо неразборным текстом.
        self.runs_broken = ""
        self.used: set[int] = set()

    def new_id(self, low: int, high: int) -> int:
        while True:
            value = self.rng.randint(low, high)
            if value not in self.used:
                self.used.add(value)
                return value

    def check(self, sha: str, name: str, state: str) -> dict:
        """Check-run без связки с прогоном: состояние — заключение
        завершённой проверки либо "running" (идёт минуту)."""
        check_id = self.new_id(10 ** 8, 10 ** 9 - 1)
        if state == "running":
            status, conclusion = "in_progress", None
        else:
            status, conclusion = "completed", state
        return {"id": check_id, "name": name, "status": status,
                "conclusion": conclusion, "head_sha": sha,
                "started_at": stamp(3),
                "completed_at": stamp(1) if status == "completed" else None,
                "app": {"slug": "github-actions"}}

    def add_unlinked(self, sha: str, name: str, state: str) -> dict:
        created = self.check(sha, name, state)
        self.checks.setdefault(sha, []).append(created)
        return created

    def add_run(self, sha: str, event: str, branch: str | None,
                checks: list[tuple[str, str]], branch_key: str | None =
                "head_branch", listed: bool = True) -> tuple[dict, list[dict]]:
        """Прогон `event` ветки `branch` на `sha` с проверками [(имя,
        состояние)]. `branch_key` — ключ, под которым ответ несёт ветку
        (`NO_KEY` — поля ветки нет); `listed=False` — прогона нет в ответе
        `actions/runs`, хотя проверки ссылаются на него."""
        run_id = self.new_id(10 ** 10, 10 ** 11 - 1)
        suite = self.new_id(10 ** 9, 10 ** 10 - 1)
        created = []
        for name, state in checks:
            check = self.check(sha, name, state)
            url = (f"http://127.0.0.1/{OWNER_REPO}/actions/runs/{run_id}"
                   f"/job/{check['id']}")
            check.update({"check_suite": {"id": suite},
                          "details_url": url, "html_url": url})
            created.append(check)
        run = {"id": run_id, "name": "CI", "event": event, "head_sha": sha,
               "check_suite_id": suite, "status": "completed",
               "run_number": self.rng.randint(1, 9999),
               "html_url": f"http://127.0.0.1/{OWNER_REPO}/actions/runs/"
                           f"{run_id}",
               "_branch": branch, "_listed": listed}
        if branch_key is not NO_KEY:
            run[branch_key] = branch
        self.runs.append(run)
        self.checks.setdefault(sha, []).extend(created)
        return run, created

    @staticmethod
    def public(record: dict) -> dict:
        return {k: v for k, v in record.items() if not k.startswith("_")}

    def __call__(self, *args, **_kwargs) -> subprocess.CompletedProcess:
        args = [str(a) for a in args]
        joined = " ".join(args)
        page = re.search(r"[?&]page=(\d+)", joined)
        first_page = page is None or page.group(1) == "1"
        found = re.search(r"commits/([0-9a-fA-F]{7,40})/check-runs", joined)
        if args[:1] == ["api"] and found:
            checks = self.checks.get(found.group(1), [])
            return completed(args, json.dumps(
                {"total_count": len(checks),
                 "check_runs": checks if first_page else []}))
        if args[:1] == ["api"] and re.search(r"actions/runs(?![\w/])", joined):
            if self.runs_broken == "code":
                return completed(args, returncode=1,
                                 stderr="gh: HTTP 502 Bad Gateway (песочница)")
            if self.runs_broken == "garbage":
                return completed(args, "<html>502 — не JSON</html>")
            sha = re.search(r"head_sha=([0-9a-fA-F]+)", joined)
            runs = [r for r in self.runs if r["_listed"] and (
                sha is None or r["head_sha"].startswith(sha.group(1)))]
            for key, field in (("event", "event"), ("branch", "_branch")):
                value = re.search(rf"[?&]{key}=([^&\s]+)", joined)
                if value:
                    runs = [r for r in runs if r[field] == value.group(1)]
            return completed(args, json.dumps(
                {"total_count": len(runs),
                 "workflow_runs": ([self.public(r) for r in runs]
                                   if first_page else [])}))
        if args[:2] == ["run", "list"]:
            branch = (args[args.index("--branch") + 1]
                      if "--branch" in args else None)
            runs = [r for r in self.runs
                    if branch is None or r["_branch"] == branch]
            return completed(args, json.dumps(
                [{"databaseId": r["id"], "event": r["event"],
                  "headSha": r["head_sha"], "headBranch": r["_branch"] or "",
                  "status": r["status"], "conclusion": "success"}
                 for r in runs]))
        return completed(args, returncode=1,
                         stderr=f"gh песочницы: вызов не поддержан: {joined}")


class BranchVerdictTest(unittest.TestCase):
    """Вердикт CI ветки задачи — по проверкам прогонов этой ветки."""

    def setUp(self):
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.branch = f"task/{self.hex(10)}-x"
        self.sha = self.hex(40)
        self.main_sha = self.hex(40)
        # Головы веток для подставного `ci.head_sha`; ветки нет — git не
        # определил голову.
        self.heads = {self.branch: self.sha}
        self.fake = FakeGitHub(random.Random(self.rng.randrange(2 ** 32)))
        for target, value in (
                ("gh", lambda *a, **k: self.fake(*a, **k)),
                ("head_sha", lambda branch, **_k: self.head(branch))):
            patcher = mock.patch.object(ci, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    # Помощники сценария ----------------------------------------------

    def hex(self, length: int) -> str:
        return "".join(self.rng.choice("0123456789abcdef")
                       for _ in range(length))

    def head(self, branch: str) -> tuple[str, str]:
        sha = self.heads.get(branch, "")
        if not sha:
            return "", (f"головной коммит ветки {branch} не определён: "
                        f"fatal: ветки нет (песочница)")
        return sha, ""

    def reset(self, seed: int) -> None:
        self.fake = FakeGitHub(random.Random(seed))
        self.heads = {self.branch: self.sha}

    def other_branch(self) -> str:
        return self.rng.choice(("main", f"task/{self.hex(10)}-y"))

    def event(self) -> str:
        return self.rng.choice(EVENTS)

    def bad(self) -> str:
        return self.rng.choice(BAD_CONCLUSIONS)

    def shuffle_runs(self) -> None:
        self.rng.shuffle(self.fake.runs)

    def msg(self, note: str, extra: str = "") -> str:
        return f"зерно: {self.seed}\n{extra}\nтекст статуса:\n{note}"

    def read_both(self) -> tuple[tuple[str, str], tuple[bool, str]]:
        return ci.verifying_status(self.branch), ci.branch_status(self.branch)

    # Критерии ---------------------------------------------------------

    def test_ac1_red_check_of_main_run_is_excluded_and_named(self):
        """Красная проверка прогона main на том же коммите не красит задачу.

        Коммит несёт зелёные проверки прогона ветки задачи (в одном
        раскладе — push и pull_request, в другом — только push) и красную
        проверку прогона с `head_branch` = `main`, найденного в индексе.
        Имя красной проверки — отдельное либо совпадает с зелёной
        проверкой ветки (одноимённое задание чужого прогона). Исход —
        `VERIFYING_GREEN` и `True`, текст обоих читателей называет
        исключённую проверку. Отдельно: зелёные проверки только push-прогона
        ветки задачи без всякого pull_request — зелёный вердикт обоих.

        Ловит мутацию: вердикт по всем проверкам коммита (красный прогон
        main даёт `VERIFYING_RED`/`False`); исключение без упоминания в
        тексте (имени исключённой проверки в зелёном тексте нет); требование
        прогонов обоих событий (только push даёт «идёт»/не зелёный).
        """
        for layout in ("отдельное имя", "одноимённая с зелёной"):
            with self.subTest(layout=layout):
                self.reset(self.rng.randrange(2 ** 32))
                names = self.rng.sample(CHECK_NAMES, 4)
                green_names, foreign = names[:3], names[3]
                if layout == "одноимённая с зелёной":
                    foreign = self.rng.choice(green_names)
                for event in EVENTS:
                    self.fake.add_run(self.sha, event, self.branch,
                                      [(n, "success") for n in green_names])
                self.fake.add_run(self.sha, self.event(), "main",
                                  [(foreign, self.bad())])
                self.shuffle_runs()

                (outcome, note), (green, bnote) = self.read_both()

                self.assertEqual(outcome, ci.VERIFYING_GREEN, self.msg(note))
                self.assertIs(green, True, self.msg(bnote))
                for text in (note, bnote):
                    self.assertIn(foreign, text, self.msg(
                        text, "исключённая проверка не названа"))

        with self.subTest(layout="только push ветки задачи"):
            self.reset(self.rng.randrange(2 ** 32))
            names = self.rng.sample(CHECK_NAMES, 3)
            self.fake.add_run(self.sha, "push", self.branch,
                              [(n, "success") for n in names])
            (outcome, note), (green, bnote) = self.read_both()
            self.assertEqual(outcome, ci.VERIFYING_GREEN, self.msg(note))
            self.assertIs(green, True, self.msg(bnote))

    def test_ac2_red_check_without_proven_other_branch_stays_in_verdict(self):
        """Красная проверка без доказанной чужой ветки прогона красит задачу.

        Зелёные проверки прогона ветки задачи и красная проверка, у которой
        чужая ветка не доказана: (1) индекс прогонов не получен (ненулевой
        код либо неразборный ответ); (2) её прогона нет в ответе
        `actions/runs`; (3) у неё нет ни `check_suite.id`, ни ссылки на
        прогон; (4) у её прогона `head_branch` пустой; (5) поля
        `head_branch` нет; (6) чужая ветка записана только под ключом
        `headBranch`. Во всех — `VERIFYING_RED` и `False`.

        Ловит мутацию: проверка без найденного прогона отбрасывается
        (зелёный вместо красного в (1)-(3)); пустая или отсутствующая ветка
        прогона читается как «другая ветка» (зелёный в (4)-(5)); ветка
        читается из `headBranch` (зелёный в (6)).
        """
        layouts = ("индекс не получен", "прогона нет на странице",
                   "проверка без связи с прогоном", "head_branch пустой",
                   "head_branch отсутствует", "ветка только в headBranch")
        for layout in layouts:
            with self.subTest(layout=layout):
                self.reset(self.rng.randrange(2 ** 32))
                names = self.rng.sample(CHECK_NAMES, 4)
                green_names, red = names[:3], names[3]
                self.fake.add_run(self.sha, self.event(), self.branch,
                                  [(n, "success") for n in green_names])
                other = self.other_branch()
                checks = [(red, self.bad())]
                if layout == "индекс не получен":
                    self.fake.runs_broken = self.rng.choice(("code",
                                                             "garbage"))
                    self.fake.add_run(self.sha, self.event(), other, checks)
                elif layout == "прогона нет на странице":
                    self.fake.add_run(self.sha, self.event(), other, checks,
                                      listed=False)
                elif layout == "проверка без связи с прогоном":
                    self.fake.add_unlinked(self.sha, red, checks[0][1])
                elif layout == "head_branch пустой":
                    self.fake.add_run(self.sha, self.event(), "", checks)
                elif layout == "head_branch отсутствует":
                    self.fake.add_run(self.sha, self.event(), other, checks,
                                      branch_key=NO_KEY)
                else:
                    self.fake.add_run(self.sha, self.event(), other, checks,
                                      branch_key="headBranch")
                self.shuffle_runs()

                (outcome, note), (green, bnote) = self.read_both()

                self.assertEqual(outcome, ci.VERIFYING_RED,
                                 self.msg(note, layout))
                self.assertIs(green, False, self.msg(bnote, layout))

    def test_ac3_only_foreign_checks_mean_no_checks_not_green(self):
        """Коммит только с проверками прогонов других веток — «проверок нет /
        идут».

        Все прогоны коммита — других веток (случайные события, заключения,
        часть проверок ещё идёт). `verifying_status` — `VERIFYING_NONE` либо
        `VERIFYING_RUNNING`; `branch_status` — `False`, и `ci.status_kind`
        его текста — "running" либо "unknown", не "red".

        Ловит мутацию: пусто после исключения → зелёный (`VERIFYING_GREEN`/
        `True` по пустому списку проверок) либо иной вид статуса — текст
        `branch_status` без «ещё идёт»/«неизвестен», `status_kind` даёт
        "red" и гейт мержа отказывает вместо ожидания.
        """
        for layout in ("все чужие зелёные", "чужие красные и идущие"):
            with self.subTest(layout=layout):
                self.reset(self.rng.randrange(2 ** 32))
                for _ in range(self.rng.randint(1, 3)):
                    names = self.rng.sample(CHECK_NAMES,
                                            self.rng.randint(1, 3))
                    states = ["success" if layout == "все чужие зелёные"
                              else self.rng.choice((self.bad(), "running",
                                                    "success"))
                              for _ in names]
                    if layout != "все чужие зелёные":
                        states[0] = self.bad()
                    self.fake.add_run(self.sha, self.event(),
                                      self.other_branch(),
                                      list(zip(names, states)))
                self.shuffle_runs()

                (outcome, note), (green, bnote) = self.read_both()

                self.assertIn(outcome, (ci.VERIFYING_NONE,
                                        ci.VERIFYING_RUNNING),
                              self.msg(note, layout))
                self.assertIs(green, False, self.msg(bnote, layout))
                self.assertIn(ci.status_kind(bnote), ("running", "unknown"),
                              self.msg(bnote, layout))

    def test_ac4_full_suite_twin_of_other_branch_does_not_count(self):
        """Пропущенный полный набор ветки не закрывается близнецом чужой
        ветки.

        Прогон ветки задачи: задание полного набора `skipped`, прочие
        проверки зелёные. Исполненный зелёный близнец того же задания (push
        либо pull_request) есть только в прогоне другой ветки. Исход
        `verifying_status` — не `VERIFYING_GREEN`, `branch_status` — `False`.

        Ловит мутацию: правило неисполненного полного набора считается по
        всем проверкам коммита, а исключение — только для вердикта красноты:
        близнец чужой ветки засчитан, исход зелёный.
        """
        suite_name = self.rng.choice(sorted(ci.FULL_SUITE_CHECKS))
        others = self.rng.sample(
            [n for n in CHECK_NAMES if n not in ci.FULL_SUITE_CHECKS], 2)
        self.fake.add_run(self.sha, self.event(), self.branch,
                          [(suite_name, "skipped")]
                          + [(n, "success") for n in others])
        self.fake.add_run(self.sha, self.event(), self.other_branch(),
                          [(suite_name, "success")]
                          + [(n, "success") for n in others])
        self.shuffle_runs()

        (outcome, note), (green, bnote) = self.read_both()

        self.assertNotEqual(outcome, ci.VERIFYING_GREEN, self.msg(note))
        self.assertIs(green, False, self.msg(bnote))

    def test_ac5_exclusion_phrase_does_not_change_parsed_kind(self):
        """Зелёный текст с исключённой красной проверкой разбирается как
        зелёный без неё.

        Один и тот же расклад зелёных проверок ветки задачи читается дважды:
        без прогона другой ветки и с ним (красная проверка, прогон найден в
        индексе). Со вторым `ci.verifying_is_red` текста `verifying_status`
        ложен, а `ci.status_kind` текстов обоих читателей равен
        `status_kind` текстов первого чтения (без фразы об исключённых).

        Ловит мутацию: фраза об исключённой проверке несёт «не зелёный:»
        (`verifying_is_red` истинен на зелёном исходе) либо «ещё идёт»/
        «неизвестен» (`status_kind` меняется с "red" на "running"/
        "unknown").
        """
        seed = self.rng.randrange(2 ** 32)
        names = self.rng.sample(CHECK_NAMES, 4)
        green_names, foreign = names[:3], names[3]
        other, conclusion = self.other_branch(), self.bad()

        def build(with_foreign: bool):
            self.reset(seed)
            self.fake.add_run(self.sha, self.event(), self.branch,
                              [(n, "success") for n in green_names])
            if with_foreign:
                self.fake.add_run(self.sha, self.event(), other,
                                  [(foreign, conclusion)])
            return self.read_both()

        (_o, base_note), (_g, base_bnote) = build(False)
        (outcome, note), (green, bnote) = build(True)

        self.assertEqual(outcome, ci.VERIFYING_GREEN, self.msg(note))
        self.assertIs(green, True, self.msg(bnote))
        self.assertFalse(ci.verifying_is_red(note), self.msg(note))
        self.assertEqual(ci.status_kind(note), ci.status_kind(base_note),
                         self.msg(note, f"без фразы:\n{base_note}"))
        self.assertEqual(ci.status_kind(bnote), ci.status_kind(base_bnote),
                         self.msg(bnote, f"без фразы:\n{base_bnote}"))

    def test_ac6_failure_red_on_main_tip_is_named_inherited(self):
        """Упавшая проверка ветки, красная и на вершине main, — «красный
        унаследован от main <sha>».

        Ветка задачи: проверка X упала, прочие зелёные. Раскладки вершины
        main (`ci.head_sha("main")`, её проверки — через
        `ci.failed_check_names`): (1) X упала и там — оба текста несут
        «красный унаследован от main <sha вершины>», текст
        `verifying_status` — подсказку «подтянуть main в ветку задачи:
        artel.py pull-main <id задачи>», текст `branch_status` — нет;
        (2) на main упала другая проверка, X зелёная — фразы нет;
        (3) голова main не определена; (4) у вершины main нет проверок
        (`failed_check_names` → `None`); (5) запрос её проверок не
        ответил — в (3)-(5) ни фразы, ни подсказки. Исход везде —
        `VERIFYING_RED` и `False`.

        Ловит мутацию: фраза ставится по любой красной проверке main, а не
        по совпадению имени (фраза в (2)); sha вершины не тот (в фразе sha
        головы ветки задачи); подсказка pull-main и в `branch_status`;
        неизвестная вершина main читается как «унаследован» (фраза в
        (3)-(5)); фраза заменяет красный исход зелёным или «идёт».
        """
        names = self.rng.sample(CHECK_NAMES, 4)
        x, others = names[0], names[1:]
        layouts = ("X красна и на main", "на main упала другая",
                   "голова main не определена", "у вершины main нет проверок",
                   "проверки вершины main не ответили")
        for layout in layouts:
            with self.subTest(layout=layout):
                self.reset(self.rng.randrange(2 ** 32))
                self.fake.add_run(self.sha, self.event(), self.branch,
                                  [(x, self.bad())]
                                  + [(n, "success") for n in others])
                if layout != "голова main не определена":
                    self.heads["main"] = self.main_sha
                main_failed = {"X красна и на main": x,
                               "на main упала другая": others[0]}
                if layout in main_failed:
                    for name in [x, *others]:
                        self.fake.add_unlinked(
                            self.main_sha, name,
                            self.bad() if name == main_failed[layout]
                            else "success")
                elif layout == "проверки вершины main не ответили":
                    real = self.fake

                    def broken_main(*args, **kwargs):
                        if self.main_sha in " ".join(map(str, args)):
                            return completed(args, returncode=1,
                                             stderr="gh: HTTP 502 (песочница)")
                        return real(*args, **kwargs)
                    self.fake = broken_main

                (outcome, note), (green, bnote) = self.read_both()

                self.assertEqual(outcome, ci.VERIFYING_RED,
                                 self.msg(note, layout))
                self.assertIs(green, False, self.msg(bnote, layout))
                if layout == "X красна и на main":
                    for text in (note, bnote):
                        match = INHERITED_RE.search(text)
                        self.assertIsNotNone(match, self.msg(text, layout))
                        self.assertGreaterEqual(len(match.group(1)), 7,
                                                self.msg(text, layout))
                        self.assertTrue(
                            self.main_sha.startswith(match.group(1).lower()),
                            self.msg(text, f"sha вершины main: "
                                           f"{self.main_sha}"))
                    self.assertIn(PULL_HINT, note, self.msg(note, layout))
                    self.assertNotIn("pull-main", bnote,
                                     self.msg(bnote, layout))
                else:
                    for text in (note, bnote):
                        self.assertNotIn(INHERITED, text,
                                         self.msg(text, layout))
                        self.assertNotIn("pull-main", text,
                                         self.msg(text, layout))

    def test_ac7_new_phrases_carry_no_parsed_substrings(self):
        """Фразы об исключённых проверках и «унаследован от main» не несут
        разбираемых подстрок.

        Каждый расклад читается парой: без новой фразы и с ней (тот же
        прогон ветки задачи плюс красная проверка прогона другой ветки;
        либо та же упавшая проверка при вершине main, где она зелёная, и
        при вершине, где она упала). Число вхождений каждой из подстрок
        «не зелёный:», «ещё идёт», «неизвестен», «check-run id» в тексте с
        фразой равно числу в тексте без неё — для обоих читателей; в
        зелёном тексте с исключённой проверкой их нет вовсе.

        Ловит мутацию: фраза названа «…проверки других веток: не зелёный:
        …», «…статус ветки неизвестен…», «…ещё идёт в main…» или несёт id
        check-run'а в форме «check-run id N» — число вхождений растёт, и
        разборщики `verifying_is_red`/`status_kind`/`stuck_check_ids`
        меняют исход.
        """
        names = self.rng.sample(CHECK_NAMES, 4)
        x, others, foreign = names[0], names[1:3], names[3]
        other = self.other_branch()

        def build(seed: int, branch_x: str, foreign_state: str | None,
                  main_x: str | None) -> list[str]:
            self.reset(seed)
            self.fake.add_run(self.sha, "push", self.branch,
                              [(x, branch_x)]
                              + [(n, "success") for n in others])
            if foreign_state is not None:
                self.fake.add_run(self.sha, self.event(), other,
                                  [(foreign, foreign_state)])
            if main_x is not None:
                self.heads["main"] = self.main_sha
                for name in [x, *others]:
                    self.fake.add_unlinked(
                        self.main_sha, name,
                        main_x if name == x else "success")
            (_o, note), (_g, bnote) = self.read_both()
            return [note, bnote]

        bad = self.bad()
        pairs = {
            "исключённая при зелёном": ("success", None, bad, None),
            "исключённая при красном": (bad, None, bad, None),
            "исключённая при идущем": ("running", None, bad, None),
            "унаследован от main": (bad, "success", None, bad),
        }
        for layout, (branch_x, main_without, foreign_with, main_with) in \
                pairs.items():
            with self.subTest(layout=layout):
                seed = self.rng.randrange(2 ** 32)
                if layout == "унаследован от main":
                    without = build(seed, branch_x, None, main_without)
                    with_phrase = build(seed, branch_x, None, main_with)
                    self.assertIn(INHERITED, with_phrase[0],
                                  self.msg(with_phrase[0], layout))
                else:
                    without = build(seed, branch_x, None, None)
                    with_phrase = build(seed, branch_x, foreign_with, None)
                for base, text in zip(without, with_phrase):
                    for part in PARSED:
                        self.assertEqual(
                            text.count(part), base.count(part),
                            self.msg(text, f"{layout}: «{part}» — без "
                                           f"фразы:\n{base}"))
                if layout == "исключённая при зелёном":
                    for text in with_phrase:
                        for part in PARSED:
                            self.assertNotIn(part, text,
                                             self.msg(text, layout))


if __name__ == "__main__":
    unittest.main()
