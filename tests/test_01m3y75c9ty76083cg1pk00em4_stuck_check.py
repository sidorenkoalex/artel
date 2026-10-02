"""Проверка CI, которую GitHub отдаёт «идущей» при известном исходе, и
проверка, зависшая без исхода дольше порога.

Check-run с `status` не `completed`, но с непустыми `conclusion` и
`completed_at`, читается завершённым с этим `conclusion` — одинаково в
`ci.verifying_status` и `ci.branch_status`. Check-run в `in_progress`/
`queued` без `conclusion` старше `config.CI_STUCK_CHECK_MINUTES` (возраст от
`started_at`, без него — от `created_at`) даёт в `verifying` отдельное
именованное состояние «проверка зависла»: не зелёное и не красное; запись
журнала статуса CI называет имя, id и возраст такой проверки, а `ci-rerun`
в этом состоянии не отказывает и перезапускает прогон workflow, которому
проверка принадлежит.

`gh` подменён целиком (`ci.gh`), голова ветки — `ci.head_sha`: сети и git
нет ни в одном тесте. Время check-run'ов считается от настоящих текущих
часов: код задачи вправе брать «сейчас» как угодно, а фикстура отстоит от
порога на минуты, не на секунды. Имена, id и возрасты проверок порождаются
`random` при каждом запуске, зерно печатается и входит в текст провала.

Группа: долгоживущий
Красен до реализации: `ci.verifying_status`/`ci.branch_status` считают проверку идущей по одному `status != "completed"` (AC-1, AC-2, AC-8 видят «ещё идёт»), константы `config.CI_STUCK_CHECK_MINUTES` и состояния «проверка зависла» нет (AC-5, AC-6 падают на AttributeError/исходе running), `ci-rerun` отказывает «не завершённо-красный» (AC-7).
"""
import io
import json
import random
import re
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from unittest import mock

from orchestrator import ci, ci_rerun, config, fsm, store
from tests.sandbox import LightTransitionSandbox

KNOWN_OUTCOMES = ("VERIFYING_GREEN", "VERIFYING_NONE", "VERIFYING_RUNNING",
                  "VERIFYING_RED")

CHECK_NAMES = ("Валидация артефактов", "python", "guard", "Свежесть карты",
               "protected-paths", "lint")


def new_rng(testcase) -> tuple[random.Random, int]:
    """Генератор входов теста и его зерно (печатается — провал
    воспроизводим)."""
    seed = random.randrange(2 ** 32)
    print(f"зерно: {seed}")
    return random.Random(seed), seed


def iso_ago(minutes: float) -> str:
    """Отметка времени GitHub API (`2026-10-02T08:31:44Z`) `minutes` назад."""
    moment = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def green_check(name: str, check_id: int) -> dict:
    return {"id": check_id, "name": name, "status": "completed",
            "conclusion": "success", "started_at": iso_ago(30),
            "completed_at": iso_ago(25), "created_at": iso_ago(31)}


def random_sha(rng: random.Random) -> str:
    return "".join(rng.choice("abcdef0123456789") for _ in range(40))


def pick_names(rng: random.Random, count: int) -> list[str]:
    return rng.sample(CHECK_NAMES, count)


def answer(returncode: int, stdout: str = "",
           stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(["gh"], returncode, stdout, stderr)


def check_runs_json(runs: list) -> str:
    return json.dumps({"total_count": len(runs), "check_runs": runs})


def numbers_in(text: str) -> list[int]:
    return [int(n) for n in re.findall(r"\d+", text)]


def names_age(note: str, age_minutes: int, *, drop: tuple = ()) -> bool:
    """`note` называет возраст проверки: целым числом минут (±1 на
    округление), секунд (±90) либо формой «Ч ч М мин». Имя, id и sha,
    тоже несущие цифры, вырезаются до сверки."""
    text = note
    for fragment in drop:
        text = text.replace(str(fragment), " ")
    for number in numbers_in(text):
        if abs(number - age_minutes) <= 1 or abs(number - age_minutes * 60) <= 90:
            return True
    for hours, mins in re.findall(r"(\d+)\s*ч\D{0,4}?(\d+)\s*мин", text):
        if abs(int(hours) * 60 + int(mins) - age_minutes) <= 1:
            return True
    return False


class CiStandMixin:
    """Подменённые `ci.gh` и `ci.head_sha`: ответ check-runs — `self.runs`."""

    def start_ci_stand(self, head: str, runs: list) -> None:
        self.head = head
        self.runs = runs
        self.gh_calls: list[tuple] = []
        for target, value in (("gh", self.fake_gh),
                              ("head_sha", self.fake_head_sha)):
            patcher = mock.patch.object(ci, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def fake_head_sha(self, branch: str, repo=None) -> tuple:
        return self.head, ""

    def fake_gh(self, *args: str, **kwargs) -> subprocess.CompletedProcess:
        self.gh_calls.append(args)
        joined = " ".join(args)
        if "check-runs" in joined:
            return answer(0, check_runs_json(self.runs))
        if args[:2] == ("run", "list"):
            return answer(0, "[]")
        return answer(0, "")


class FinishedButReportedRunningTest(CiStandMixin, unittest.TestCase):
    """AC-1, AC-2: исход известен, хотя `status` ещё `in_progress`."""

    def fixture(self, conclusion: str) -> tuple[dict, int]:
        rng, seed = new_rng(self)
        names = pick_names(rng, rng.randint(2, 4))
        check = {"id": rng.randrange(10 ** 10, 10 ** 12), "name": names[0],
                 "status": "in_progress", "conclusion": conclusion,
                 # Начата давно — старше порога зависания: исход известен,
                 # и правило «зависла» к ней применяться не должно.
                 "started_at": iso_ago(rng.randint(120, 600)),
                 "created_at": iso_ago(rng.randint(601, 700)),
                 "completed_at": iso_ago(rng.randint(60, 119))}
        others = [green_check(n, rng.randrange(10 ** 6)) for n in names[1:]]
        runs = others + [check]
        rng.shuffle(runs)
        self.start_ci_stand(random_sha(rng), runs)
        return check, seed

    def test_ac1_success_conclusion_counts_as_green_in_both_readers(self):
        """`in_progress` + `conclusion=success` + `completed_at` — зелёный.

        Остальные проверки коммита завершены зелёными; одна проверка отдана
        GitHub с `status=in_progress`, но с исходом `success` и временем
        завершения. `ci.verifying_status` обязана дать `VERIFYING_GREEN`, а
        `ci.branch_status` — `True` (зелёный на гейте мержа).

        Ловит мутацию: новое правило подключено только в `verifying_status`,
        а `branch_status` по-прежнему сверяет `status != "completed"` — гейт
        мержа отдаст `(False, "… ещё идёт: …")`, и тест покраснеет на
        `branch_status`; либо правило требует `status == "completed"` и
        `completed_at` разом — `verifying_status` отдаст `running`.
        """
        check, seed = self.fixture("success")

        outcome, note = ci.verifying_status("task/x")
        green, gate_note = ci.branch_status("task/x")

        self.assertEqual(outcome, ci.VERIFYING_GREEN,
                         f"зерно {seed}: verifying_status: {note!r}")
        self.assertTrue(green, f"зерно {seed}: branch_status: {gate_note!r}")

    def test_ac2_failure_conclusion_counts_as_red_in_both_readers(self):
        """`in_progress` + `conclusion=failure` + `completed_at` — красный.

        Тот же check-run, что в AC-1, но с исходом `failure`.
        `ci.verifying_status` обязана дать `VERIFYING_RED`, `ci.branch_status`
        — `False` с красным `note` (`ci.status_kind(note) == "red"`), а не
        «ещё идёт».

        Ловит мутацию: проверка с `completed_at` считается зелёной без
        оглядки на `conclusion` (правило «есть completed_at — значит
        прошла») — `verifying_status` отдаст `green`; либо `branch_status`
        оставлен со старым сравнением `status` — его `note` будет «ещё
        идёт», `status_kind` вернёт `running`, и тест покраснеет.
        """
        check, seed = self.fixture("failure")

        outcome, note = ci.verifying_status("task/x")
        green, gate_note = ci.branch_status("task/x")

        self.assertEqual(outcome, ci.VERIFYING_RED,
                         f"зерно {seed}: verifying_status: {note!r}")
        self.assertFalse(green, f"зерно {seed}: branch_status: {gate_note!r}")
        self.assertEqual(ci.status_kind(gate_note), "red",
                         f"зерно {seed}: note гейта мержа: {gate_note!r}")


def stuck_outcome_constants(outcome: str) -> list[str]:
    """Имена `ci.VERIFYING_*`, кроме четырёх прежних, равные `outcome`."""
    return [name for name in dir(ci)
            if name.startswith("VERIFYING_") and name not in KNOWN_OUTCOMES
            and getattr(ci, name) == outcome]


class StuckCheckTest(CiStandMixin, unittest.TestCase):
    """AC-5, AC-6: проверка без исхода — «идёт» до порога, «зависла» после."""

    def stand_with(self, rng: random.Random, check: dict) -> None:
        names = [n for n in CHECK_NAMES if n != check["name"]]
        others = [green_check(n, rng.randrange(10 ** 6))
                  for n in rng.sample(names, rng.randint(1, 3))]
        runs = others + [check]
        rng.shuffle(runs)
        self.start_ci_stand(random_sha(rng), runs)

    def test_ac5_young_check_without_conclusion_is_running(self):
        """Проверка моложе порога — исход «идёт», не «зависла».

        Четыре входа: статус `in_progress` и `queued`, каждый — с
        `started_at` моложе порога при `created_at` СТАРШЕ порога (возраст
        отсчитывается от `started_at`) и без `started_at` вовсе при
        `created_at` моложе порога. Порог — `config.CI_STUCK_CHECK_MINUTES`.

        Ловит мутацию: возраст считается от `created_at` даже при
        заданном `started_at` — давно созданная, но недавно начатая
        проверка станет «зависшей», и тест покраснеет на первом входе;
        либо сравнение с порогом перевёрнуто (`<` вместо `>`) — молодая
        проверка станет «зависшей» на всех входах.
        """
        threshold = config.CI_STUCK_CHECK_MINUTES
        rng, seed = new_rng(self)
        for status in ("in_progress", "queued"):
            for with_started in (True, False):
                young = rng.randint(0, max(0, threshold - 3))
                check = {"id": rng.randrange(10 ** 10, 10 ** 12),
                         "name": rng.choice(CHECK_NAMES), "status": status,
                         "conclusion": None, "completed_at": None}
                if with_started:
                    check["started_at"] = iso_ago(young)
                    check["created_at"] = iso_ago(threshold + rng.randint(10, 300))
                else:
                    check["created_at"] = iso_ago(young)
                with self.subTest(status=status, with_started=with_started):
                    self.stand_with(rng, check)
                    outcome, note = ci.verifying_status("task/x")
                    self.assertEqual(
                        outcome, ci.VERIFYING_RUNNING,
                        f"зерно {seed}: {check!r} -> {outcome!r}: {note!r}")

    def test_ac6_old_check_without_conclusion_is_named_stuck_state(self):
        """Проверка старше порога — именованное состояние «проверка зависла».

        Четыре входа: `in_progress`/`queued`, каждый — со `started_at`
        старше порога и без `started_at` при `created_at` старше порога.
        Исход — не один из четырёх прежних и равен значению некоторой
        именованной константы `ci.VERIFYING_*`; `note` называет имя
        проверки, её id и возраст; `ci.verifying_is_red(note)` ложно.

        Ловит мутацию: проверка без `started_at` не считается зависшей
        (возраст берётся только от `started_at`, а его отсутствие — «ещё
        идёт») — второй вход отдаст `running`; либо зависшая проверка
        журналируется как красная («… не зелёный: …») — `verifying_is_red`
        станет истинным, и `auto` остановил бы цикл как на красном CI;
        либо `note` не несёт id — Оператор не найдёт check-run.
        """
        threshold = config.CI_STUCK_CHECK_MINUTES
        rng, seed = new_rng(self)
        for status in ("in_progress", "queued"):
            for with_started in (True, False):
                age = threshold + rng.randint(5, 400)
                check = {"id": rng.randrange(10 ** 10, 10 ** 12),
                         "name": rng.choice(CHECK_NAMES), "status": status,
                         "conclusion": None, "completed_at": None}
                if with_started:
                    check["started_at"] = iso_ago(age)
                    check["created_at"] = iso_ago(age + rng.randint(0, 5))
                else:
                    check["created_at"] = iso_ago(age)
                with self.subTest(status=status, with_started=with_started):
                    self.stand_with(rng, check)
                    outcome, note = ci.verifying_status("task/x")
                    where = f"зерно {seed}: {check!r} -> {outcome!r}: {note!r}"
                    self.assertNotIn(
                        outcome, [getattr(ci, n) for n in KNOWN_OUTCOMES], where)
                    self.assertTrue(stuck_outcome_constants(outcome),
                                    f"исход не назван константой ci.VERIFYING_*; "
                                    f"{where}")
                    self.assertFalse(ci.verifying_is_red(note), where)
                    self.assertIn(check["name"], note, where)
                    self.assertIn(str(check["id"]), note, where)
                    self.assertTrue(
                        names_age(note, age, drop=(check["id"], check["name"],
                                                   self.head[:8])),
                        f"note не называет возраст ≈{age} мин; {where}")


class VerifyingJournalTest(CiStandMixin, LightTransitionSandbox):
    """AC-8: запись журнала `fsm.VERIFYING_STATUS_ACTION` после опроса CI
    в `verifying` настоящим `fsm.cmd_advance`."""

    TASK_TITLE = "Проверка CI, зависшая в состоянии идёт"

    def status_records(self, since: int) -> list[str]:
        return [r["detail"] or "" for r in store.task_steps(store.db(), self.TASK)
                if r["id"] > since and r["action"] == fsm.VERIFYING_STATUS_ACTION]

    def last_step_id(self) -> int:
        rows = store.task_steps(store.db(), self.TASK)
        return rows[-1]["id"] if rows else 0

    def advance_verifying(self) -> list[str]:
        self.set_state("verifying")
        before = self.last_step_id()
        self.capture(fsm.cmd_advance, self.TASK)
        return self.status_records(before)

    def test_ac8_journal_names_reinterpreted_check_on_its_own_line(self):
        """Запись статуса CI называет «идущую» проверку с исходом дословно.

        Опрос CI в `verifying`: одна проверка отдана с
        `status=in_progress`, `conclusion=success`, `completed_at=<t>`,
        остальные завершены зелёными. Запись `fsm.VERIFYING_STATUS_ACTION`
        обязана содержать строку «<имя>: GitHub отдаёт status=in_progress
        при conclusion=success, completed_at=<t> — считаю завершённой».

        Ловит мутацию: проверка молча переклассифицирована завершённой, а
        в `note` попадает только итог «CI коммита … зелёный (N проверок)»
        — Оператор не узнал бы из журнала, что пульт поверил `conclusion`
        вопреки `status`, и запись не найдёт строки.
        """
        rng, seed = new_rng(self)
        names = pick_names(rng, rng.randint(2, 4))
        completed_at = iso_ago(rng.randint(60, 119))
        check = {"id": rng.randrange(10 ** 10, 10 ** 12), "name": names[0],
                 "status": "in_progress", "conclusion": "success",
                 "started_at": iso_ago(rng.randint(120, 600)),
                 "created_at": iso_ago(rng.randint(601, 700)),
                 "completed_at": completed_at}
        runs = [green_check(n, rng.randrange(10 ** 6)) for n in names[1:]]
        runs.append(check)
        rng.shuffle(runs)
        self.start_ci_stand(random_sha(rng), runs)

        records = self.advance_verifying()

        line = (f"{check['name']}: GitHub отдаёт status=in_progress при "
                f"conclusion=success, completed_at={completed_at} — считаю "
                f"завершённой")
        self.assertTrue(any(line in record for record in records),
                        f"зерно {seed}: нет строки {line!r} в записях {records!r}")

    def test_ac8_journal_names_stuck_check_id_and_age(self):
        """Запись статуса CI зависшей проверки называет имя, id и возраст.

        Опрос CI в `verifying`: одна проверка `in_progress` без
        `conclusion`, начата раньше порога `config.CI_STUCK_CHECK_MINUTES`.
        Запись `fsm.VERIFYING_STATUS_ACTION` несёт имя проверки, её id и
        возраст.

        Ловит мутацию: состояние «зависла» распознано, но запись журнала
        собрана общим текстом «CI коммита … ещё идёт: <имя>» без id и
        возраста — Оператор не отличил бы зависшую проверку от идущей и не
        нашёл бы check-run для перезапуска.
        """
        threshold = config.CI_STUCK_CHECK_MINUTES
        rng, seed = new_rng(self)
        names = pick_names(rng, rng.randint(2, 4))
        age = threshold + rng.randint(5, 400)
        check = {"id": rng.randrange(10 ** 10, 10 ** 12), "name": names[0],
                 "status": "in_progress", "conclusion": None,
                 "completed_at": None, "started_at": iso_ago(age),
                 "created_at": iso_ago(age + 1)}
        runs = [green_check(n, rng.randrange(10 ** 6)) for n in names[1:]]
        runs.append(check)
        rng.shuffle(runs)
        self.start_ci_stand(random_sha(rng), runs)

        records = self.advance_verifying()

        where = f"зерно {seed}: записи {records!r}"
        self.assertTrue(records, where)
        self.assertTrue(
            any(check["name"] in r and str(check["id"]) in r
                and names_age(r, age, drop=(check["id"], check["name"],
                                            self.head[:8]))
                for r in records), where)


class StuckCheckRerunTest(CiStandMixin, LightTransitionSandbox):
    """AC-7: `ci-rerun` в состоянии «проверка зависла»."""

    TASK_TITLE = "Повтор зависшей проверки CI"

    def setUp(self):
        super().setUp()
        rng, self.seed = new_rng(self)
        threshold = config.CI_STUCK_CHECK_MINUTES
        names = pick_names(rng, rng.randint(2, 4))
        self.run_id = rng.randrange(10 ** 10, 10 ** 11)
        self.other_run_id = self.run_id + rng.randint(1, 1000)
        self.suite_id = rng.randrange(10 ** 10, 10 ** 11)
        self.check_id = rng.randrange(10 ** 11, 10 ** 12)
        self.stuck = {
            "id": self.check_id, "name": names[0], "status": "in_progress",
            "conclusion": None, "completed_at": None,
            "started_at": iso_ago(threshold + rng.randint(5, 400)),
            "created_at": iso_ago(threshold + 401),
            "check_suite": {"id": self.suite_id},
            "details_url": (f"http://127.0.0.1/o/r/actions/runs/"
                            f"{self.run_id}/job/{self.check_id}"),
            "html_url": (f"http://127.0.0.1/o/r/actions/runs/"
                         f"{self.run_id}/job/{self.check_id}")}
        self.green_runs = [green_check(n, rng.randrange(10 ** 6))
                           for n in names[1:]]
        self.start_ci_stand(random_sha(rng), self.green_runs + [self.stuck])
        # Два прогона одного коммита (push и pull_request), оба завершены
        # зелёными, как в инциденте; зависшая проверка — во ВТОРОМ из них.
        self.workflow_runs = [
            {"id": self.other_run_id, "databaseId": self.other_run_id,
             "status": "completed", "conclusion": "success", "event": "push",
             "check_suite_id": self.suite_id + 1,
             "head_sha": self.head},
            {"id": self.run_id, "databaseId": self.run_id,
             "status": "completed", "conclusion": "success",
             "event": "pull_request", "check_suite_id": self.suite_id,
             "head_sha": self.head}]

    def fake_gh(self, *args: str, **kwargs) -> subprocess.CompletedProcess:
        joined = " ".join(args)
        if args[:2] == ("run", "rerun"):
            self.gh_calls.append(args)
            # Перезапуск состоялся — проверка завершается зелёной.
            self.runs = self.green_runs + [dict(
                self.stuck, status="completed", conclusion="success",
                completed_at=iso_ago(0))]
            return answer(0)
        if args[:2] == ("run", "watch"):
            self.gh_calls.append(args)
            return answer(0, "прогон завершён")
        if re.search(rf"actions/jobs/{self.check_id}\b", joined):
            self.gh_calls.append(args)
            return answer(0, json.dumps({"id": self.check_id,
                                         "run_id": self.run_id}))
        if re.search(r"actions/runs/(\d+)(?:\b|$)", joined) and \
                "head_sha=" not in joined and "check_suite_id=" not in joined:
            self.gh_calls.append(args)
            wanted = int(re.search(r"actions/runs/(\d+)", joined).group(1))
            for run in self.workflow_runs:
                if run["id"] == wanted:
                    return answer(0, json.dumps(run))
            return answer(1, "", "HTTP 404")
        if "check_suite_id=" in joined:
            self.gh_calls.append(args)
            return answer(0, json.dumps({"total_count": 1, "workflow_runs": [
                r for r in self.workflow_runs
                if f"check_suite_id={r['check_suite_id']}" in joined]}))
        if "actions/runs" in joined:
            self.gh_calls.append(args)
            return answer(0, json.dumps({"total_count": 2,
                                         "workflow_runs": self.workflow_runs}))
        if re.search(rf"check-runs/{self.check_id}\b", joined):
            self.gh_calls.append(args)
            return answer(0, json.dumps(self.stuck))
        return super().fake_gh(*args, **kwargs)

    def run_ci_rerun(self, reason: str) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            try:
                ci_rerun.cmd_ci_rerun(self.TASK, reason)
            except SystemExit as exc:
                buf.write(f"\n{exc}\n")
        return buf.getvalue()

    def test_ac7_rerun_of_stuck_check_restarts_its_workflow_run(self):
        """`ci-rerun` при зависшей проверке перезапускает её прогон.

        Задача в `verifying`, опрос CI записал в журнал состояние
        «проверка зависла» (настоящий `fsm.cmd_advance`). У коммита два
        прогона workflow, оба `completed/success`; зависшая проверка
        принадлежит второму (ссылки `details_url`/`html_url`, `check_suite`
        check-run'а и задание `actions/jobs/<id>` указывают на него).
        `ci-rerun <id> --reason <новое основание>` не отказывает:
        отказа «не завершённо-красный … повторять нечего» нет, записи
        `ci_rerun.CI_RERUN_REFUSED_ACTION` нет, `gh run rerun` вызван с id
        прогона зависшей проверки.

        Ловит мутацию: `ci-rerun` по-прежнему пускает только
        `VERIFYING_RED` — команда откажет «не завершённо-красный», `gh run
        rerun` не будет; либо перезапуск нацелен «самым свежим прогоном
        коммита» без связи с зависшей проверкой — `gh run rerun` получит id
        первого (push) прогона, и тест покраснеет на id; либо команда
        отказывает из-за отсутствия в журнале записи о красном CI.
        """
        self.set_state("verifying")
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "verifying",
                         f"зерно {self.seed}: зависшая проверка не двигает "
                         f"задачу — фикстура сломана")
        before = max([r["id"] for r in store.task_steps(store.db(), self.TASK)]
                     or [0])
        reason = f"проверка {self.check_id} висит in_progress, прогон перезапустить"

        text = self.run_ci_rerun(reason)

        rows = [r for r in store.task_steps(store.db(), self.TASK)
                if r["id"] > before]
        where = (f"зерно {self.seed}: вывод {text!r}; gh {self.gh_calls!r}; "
                 f"журнал {[(r['action'], r['detail']) for r in rows]!r}")
        self.assertNotIn("не завершённо-красный", text, where)
        self.assertNotIn("повторять нечего", text, where)
        self.assertFalse(
            [r for r in rows if r["action"] == ci_rerun.CI_RERUN_REFUSED_ACTION],
            where)
        reruns = [argv for argv in self.gh_calls if argv[:2] == ("run", "rerun")]
        self.assertTrue(reruns, f"gh run rerun не вызван; {where}")
        self.assertTrue(all(str(self.run_id) in argv for argv in reruns),
                        f"перезапущен не прогон зависшей проверки "
                        f"{self.run_id}; {where}")
        self.assertFalse(any(str(self.other_run_id) in argv for argv in reruns),
                         where)


if __name__ == "__main__":
    unittest.main()
