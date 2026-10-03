"""Ссылка документов задачи живёт в репозитории её проекта (ADR-0021 п.3),
репозитория фиксации области проекта нет (ADR-0021 п.2, инвариант 25).

Группа: долгоживущий

Красен до реализации: ссылка документов внешней задачи пока пишется в git пульта и уходит в его origin (сверки мержа, kill и doctor читают пульт), а target-init заводит репозиторий фиксации — методы AC-1, AC-4–AC-8 о внешней задаче красные; методы AC-2 и AC-9 (и половина AC-4/AC-5 об артели) держат уже существующее поведение и зелёные.

Сценарий на настоящем git: пульт (`self.root`) с bare-`origin` (`self.bare`),
внешний проект — клон по адресу `repo_context.resolve(<проект>).path` со
своим bare-`origin` (`self.project_bare`); задача артели и задача внешнего
проекта заведены в БД. Ссылку документов внешней задачи пишет сам пульт
(строка паспорта на каждом переходе `store.set_state`, коммит закрытия);
ссылку задачи артели — фикстура (коммит без родителя в git пульта, как
после неотправленного коммита) и затем пульт (`snapshot.commit_closing`).

Имя внешнего проекта и число переходов — из `random`, зерно печатается и
входит в текст провала.
"""
import random
import shutil
import tempfile
import unittest
from pathlib import Path

from orchestrator import (cleanup, config, doctor, fixation, fsm,
                          fsm_merge_gate, projects, repo_context, snapshot,
                          store)
from tests.sandbox import AutoOriginSandbox, capture

REF_PREFIX = "refs/artifacts/"
PROJECT_NAMES = ("sled", "sani", "drovni", "rozvalni")
CYCLE = ("verifying", "review", "in_dev")


def _targets_yaml(external: str) -> str:
    entry = ("    forge: github\n    url: file:///nonexistent/{name}\n"
             "    base: {base}\n    token_slot: {name}-token\n"
             "    no_paths: []\n    project_skills: []\n"
             "    merge_gate: operator\n")
    return ("targets:\n"
            f"  {config.DEFAULT_TARGET}:\n"
            + entry.format(name=config.DEFAULT_TARGET, base=config.MAIN_BRANCH)
            + f"  {external}:\n"
            + entry.format(name=external, base=config.MAIN_BRANCH))


class ProjectDocsRefSandbox(AutoOriginSandbox):
    """Пульт с `origin`, внешний проект со своим `origin`, две задачи в
    `in_dev`: `ART` (артель) и `EXT` (внешний проект `self.target`)."""

    ART = "01UNITPROJDOCSART001"
    EXT = "01UNITPROJDOCSEXT001"

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.target = (self.rng.choice(PROJECT_NAMES)
                       + str(self.rng.randrange(10, 100)))
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        config.TARGETS.write_text(_targets_yaml(self.target), encoding="utf-8")

        ctx = repo_context.resolve(self.target)
        self.assertIsNotNone(ctx, self.why("предусловие: контекст проекта"))
        self.project = Path(ctx.path)
        self.project.mkdir(parents=True, exist_ok=True)
        self.pgit("init", "-q", "-b", config.MAIN_BRANCH)
        self.pgit("config", "user.email", "project@example.invalid")
        self.pgit("config", "user.name", "project tests")
        (self.project / "README.md").write_text("проект\n", encoding="utf-8")
        self.pgit("add", "README.md")
        self.pgit("commit", "-q", "-m", "init")
        self.project_bare = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.project_bare, ignore_errors=True)
        self.git("init", "-q", "--bare", self.project_bare)
        self.pgit("remote", "add", "origin", self.project_bare)
        self.pgit("push", "-q", "origin",
                  f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

        store.insert_task(store.db(), self.ART, "Задача артели", "in_dev",
                          f"task/{self.ART.lower()}-x", config.DEFAULT_TARGET,
                          25.0)
        store.insert_task(store.db(), self.EXT, "Задача проекта", "in_dev",
                          f"task/{self.EXT.lower()}-x", self.target, 25.0)

    # --- git-наблюдения -------------------------------------------------

    def why(self, text: str) -> str:
        return f"{text} (зерно {self.seed}, проект {self.target})"

    def pgit(self, *args: str) -> str:
        return self.git("-C", str(self.project), *args)

    def ref(self, task_id: str) -> str:
        return REF_PREFIX + task_id

    def pult_ref(self, task_id: str) -> str:
        return self.git("for-each-ref", "--format=%(objectname)",
                        self.ref(task_id)).strip()

    def project_ref(self, task_id: str) -> str:
        return self.pgit("for-each-ref", "--format=%(objectname)",
                         self.ref(task_id)).strip()

    def remote_ref(self, bare: str, task_id: str) -> str:
        out = self.git("ls-remote", bare, self.ref(task_id)).split()
        return out[0] if out else ""

    def reject_ref_pushes(self, bare: str) -> None:
        """`bare` отвергает запись в `refs/artifacts/*` — расхождение с ним
        не «лечится» попутной отправкой пульта."""
        hook = Path(bare) / "hooks" / "pre-receive"
        hook.write_text(
            "#!/bin/sh\n"
            "while read old new ref; do\n"
            "  case \"$ref\" in refs/artifacts/*) exit 1;; esac\n"
            "done\n"
            "exit 0\n", encoding="utf-8")
        hook.chmod(0o755)

    def seed_pult_ref(self, task_id: str) -> str:
        """Коммит без родителя под ссылкой задачи в git пульта, в `origin`
        не отправленный."""
        tree = self.git("rev-parse", f"{config.MAIN_BRANCH}^{{tree}}").strip()
        sha = self.git("commit-tree", tree, "-m",
                       f"{task_id}: документы").strip()
        self.git("update-ref", self.ref(task_id), sha)
        return sha

    def seed_fixation_repo(self, target: str) -> str:
        """Репозиторий фиксации прежнего устройства в области проекта: коммит
        и грязная копия. Возвращает его HEAD."""
        repo = config.PROJECTS / target
        repo.mkdir(parents=True, exist_ok=True)
        self.git("-C", str(repo), "init", "-q", "-b", config.MAIN_BRANCH)
        (repo / "old.md").write_text("старая фиксация\n", encoding="utf-8")
        self.git("-C", str(repo), "add", "old.md")
        self.git("-C", str(repo), "-c", "user.name=t",
                 "-c", "user.email=t@t.invalid", "commit", "-q", "-m", "фиксация")
        (repo / "wip.md").write_text("незакоммичено\n", encoding="utf-8")
        return self.git("-C", str(repo), "rev-parse", "HEAD").strip()

    # --- пульт ----------------------------------------------------------

    def state(self, task_id: str) -> str:
        return store.get_task(store.db(), task_id)["state"]

    def journal_actions(self, task_id: str) -> list:
        return [r["action"] for r in store.task_steps(store.db(), task_id)]

    def move(self, task_id: str, to: str) -> None:
        frm = self.state(task_id)
        capture(lambda: store.set_state(store.db(), task_id, to, "fsm",
                                        expected_state=frm,
                                        detail="переход теста"))

    def random_transitions(self, task_id: str) -> int:
        """1–3 перехода по кругу `in_dev -> verifying -> review -> in_dev`;
        задача остаётся в последнем из них."""
        count = self.rng.randint(1, 3)
        for step in range(count):
            self.move(task_id, CYCLE[step % len(CYCLE)])
        return count

    def run_cmd(self, fn, *args) -> str:
        def body():
            try:
                fn(*args)
            except SystemExit as exc:
                print(f"\nSystemExit: {exc}")
        return capture(body)

    def problems_about(self, task_id: str) -> list:
        return [c for c in doctor.check_artifact_ref_sync(store.db())
                if c.status != "ok" and task_id in (c.detail or "")]


class NoFixationRepoTest(ProjectDocsRefSandbox):

    def test_ac1_no_path_creates_fixation_repo_of_project(self):
        """Заведение проекта, переходы, чтение фиксации и `approve` без sha не заводят `.git` в области проекта.

        Сценарий: `target-init` внешнего проекта, 1–3 перехода его задачи
        (фиксация на каждом), чтение зафиксированного состояния
        (`fixation.read`, `fixation.check_integrity`), переход на гейт
        мержа и `approve` без явного sha. После каждого пути каталог
        `config.PROJECTS/<проект>` не является git-репозиторием (`.git`
        в нём нет).

        Ловит мутацию: `cmd_target_init` по-прежнему зовёт заведение
        репозитория фиксации (`git init` области проекта) либо фиксация
        перехода/чтение лениво заводят его, как прежний `_fix_external`, —
        в `config.PROJECTS/<проект>` появляется `.git`.
        """
        fixation_git = config.PROJECTS / self.target / ".git"

        capture(projects.cmd_target_init, self.target)
        self.assertFalse(fixation_git.exists(),
                         self.why("target-init завёл репозиторий фиксации"))

        self.random_transitions(self.EXT)
        self.assertFalse(fixation_git.exists(),
                         self.why("фиксация перехода завела репозиторий фиксации"))

        fixation.read(self.EXT, self.target)
        fixation.check_integrity(store.db(), self.EXT)
        self.assertFalse(fixation_git.exists(),
                         self.why("чтение фиксации завело репозиторий фиксации"))

        self.move(self.EXT, "merge_gate")
        self.run_cmd(fsm.cmd_approve, self.EXT)
        self.assertFalse(fixation_git.exists(),
                         self.why("approve без sha завёл репозиторий фиксации"))


class FixedStateIsRefHeadTest(ProjectDocsRefSandbox):

    def test_ac2_fixed_sha_is_ref_head_not_fixation_repo(self):
        """Зафиксированное состояние обеих задач — голова их ссылки документов, не репозиторий фиксации.

        Сценарий: в области проекта артели и внешнего проекта лежит
        репозиторий фиксации прежнего устройства (коммит плюс
        незакоммиченный файл). У задачи артели есть ссылка документов в
        git пульта, внешняя получает свою на переходах. После 1–3
        переходов каждой задачи `tasks.fixed_sha` — голова её ссылки
        `refs/artifacts/<id>` (там, где ссылка живёт), не HEAD
        репозитория фиксации; `fixation.read` отдаёт тот же sha и «чисто»,
        `check_integrity` не видит инцидента, хотя копия репозитория
        фиксации грязная.

        Ловит мутацию: фиксация или чтение внешнего (или любого) target
        возвращается к репозиторию фиксации (`_fix_external`/
        `_read_external`) — `fixed_sha` равен HEAD репозитория фиксации, а
        `check_integrity` докладывает грязную копию.
        """
        old_heads = {
            self.ART: self.seed_fixation_repo(config.DEFAULT_TARGET),
            self.EXT: self.seed_fixation_repo(self.target),
        }
        self.seed_pult_ref(self.ART)
        targets = {self.ART: config.DEFAULT_TARGET, self.EXT: self.target}

        for task_id, target in targets.items():
            self.random_transitions(task_id)
            fixed = store.get_task(store.db(), task_id)["fixed_sha"]
            heads = {self.pult_ref(task_id), self.project_ref(task_id)} - {""}
            self.assertIn(fixed, heads, self.why(
                f"{task_id}: fixed_sha {fixed} — не голова ссылки {heads}"))
            self.assertNotEqual(fixed, old_heads[task_id], self.why(
                f"{task_id}: зафиксирован HEAD репозитория фиксации"))
            self.assertEqual(fixation.read(task_id, target), (fixed, True),
                             self.why(f"{task_id}: чтение фиксации"))
            self.assertIsNone(fixation.check_integrity(store.db(), task_id),
                              self.why(f"{task_id}: ложный инцидент целостности"))


class RefLivesInProjectRepoTest(ProjectDocsRefSandbox):

    def test_ac4_external_ref_in_project_repo_artel_ref_in_pult(self):
        """Ссылка внешней задачи пишется в git проекта, ссылка задачи артели — в git пульта.

        Сценарий: 1–3 перехода внешней задачи (каждый пишет строку паспорта
        в её ссылку документов) — ссылка `refs/artifacts/<id>` есть в
        репозитории проекта, её голова — зафиксированное состояние, в git
        пульта такой ссылки нет. Коммит закрытия задачи артели
        (`snapshot.commit_closing`) двигает её ссылку в git пульта; в
        репозитории проекта ссылки артели нет.

        Ловит мутацию: узел записи документов пишет ссылку в `config.ROOT`
        для любого target (как до задачи) — у внешней задачи ссылка
        появляется в git пульта, в репозитории проекта её нет; либо
        репозиторий задачи выбирается для артели как область проекта —
        ссылка артели не двигается в git пульта.
        """
        self.random_transitions(self.EXT)

        ext_head = self.project_ref(self.EXT)
        self.assertTrue(ext_head, self.why("ссылки внешней задачи нет в git проекта"))
        self.assertEqual(fixation.read(self.EXT, self.target)[0], ext_head,
                         self.why("зафиксировано не то, что в git проекта"))
        self.assertEqual(self.pult_ref(self.EXT), "",
                         self.why("ссылка внешней задачи записана в git пульта"))

        art_before = self.seed_pult_ref(self.ART)
        store.update_task(store.db(), self.ART, state="killed")
        capture(snapshot.commit_closing, store.db(), self.ART, "killed")

        art_after = self.pult_ref(self.ART)
        self.assertTrue(art_after)
        self.assertNotEqual(art_after, art_before,
                            self.why("коммит закрытия артели не сдвинул ссылку в пульте"))
        self.assertEqual(self.project_ref(self.ART), "",
                         self.why("ссылка задачи артели записана в git проекта"))


class SendToProjectOriginTest(ProjectDocsRefSandbox):

    def test_ac5_external_ref_sent_to_project_origin_not_pult(self):
        """Ссылка внешней задачи уходит в `origin` проекта — после коммита и повтором на переходе; в `origin` пульта — нет.

        Сценарий: переходы внешней задачи — голова её ссылки в `origin`
        проекта равна локальной, в `origin` пульта ссылки нет (он
        принимает любые пуши, так что ошибочная отправка была бы видна).
        Затем `origin` проекта недоступен: переход пишет коммит, отправка
        отказывает — в `origin` проекта прежняя голова; `origin` вернули —
        следующий переход досылает ссылку.

        Ловит мутацию: отправка (`push`/досылка) идёт в `origin` пульта
        для любой задачи — ссылка внешней задачи появляется в
        `origin` пульта, а в `origin` проекта её нет; либо досылка на
        переходе пропущена для внешней задачи — после возврата `origin`
        проекта он остаётся на прежней голове.
        """
        self.random_transitions(self.EXT)
        head = self.project_ref(self.EXT)
        self.assertTrue(head, self.why("ссылки внешней задачи нет в git проекта"))
        self.assertEqual(self.remote_ref(self.project_bare, self.EXT), head,
                         self.why("ссылка не отправлена в origin проекта"))
        self.assertEqual(self.remote_ref(self.bare, self.EXT), "",
                         self.why("ссылка внешней задачи ушла в origin пульта"))

        self.pgit("remote", "set-url", "origin",
                  str(self.root / ".artel" / "нет-такого-origin.git"))
        self.move(self.EXT, "verifying" if self.state(self.EXT) != "verifying"
                  else "review")
        unsent = self.project_ref(self.EXT)
        self.assertNotEqual(unsent, head)
        self.assertEqual(self.remote_ref(self.project_bare, self.EXT), head,
                         self.why("предусловие: origin проекта недоступен"))
        self.pgit("remote", "set-url", "origin", self.project_bare)

        self.move(self.EXT, "in_dev" if self.state(self.EXT) != "in_dev"
                  else "verifying")

        final = self.project_ref(self.EXT)
        self.assertEqual(self.remote_ref(self.project_bare, self.EXT), final,
                         self.why("переход не дослал ссылку в origin проекта"))
        self.assertEqual(self.remote_ref(self.bare, self.EXT), "",
                         self.why("ссылка внешней задачи ушла в origin пульта"))

    def test_ac5_artel_ref_sent_to_pult_origin(self):
        """Ссылка задачи артели досылается переходом и отправляется после коммита в `origin` пульта, не в `origin` проекта.

        Сценарий: у задачи артели неотправленная ссылка в git пульта;
        переход (`set_state`) досылает её в `origin` пульта; коммит
        закрытия отправляется туда же сразу. В `origin` внешнего проекта
        ссылки артели нет.

        Ловит мутацию: репозиторий отправки выбирается для артели как
        область проекта `config.PROJECTS/artel` (по образцу `docs_root`) —
        ссылка артели не доходит до `origin` пульта.
        """
        self.seed_pult_ref(self.ART)
        self.move(self.ART, "verifying")
        self.assertEqual(self.remote_ref(self.bare, self.ART),
                         self.pult_ref(self.ART),
                         self.why("переход не дослал ссылку артели в origin пульта"))

        store.update_task(store.db(), self.ART, state="killed")
        capture(snapshot.commit_closing, store.db(), self.ART, "killed")
        self.assertEqual(self.remote_ref(self.bare, self.ART),
                         self.pult_ref(self.ART),
                         self.why("коммит закрытия артели не отправлен в origin пульта"))
        self.assertEqual(self.remote_ref(self.project_bare, self.ART), "",
                         self.why("ссылка артели ушла в origin проекта"))


class MergeGateReadsProjectTest(ProjectDocsRefSandbox):

    def approve(self) -> tuple:
        before = len(self.journal_actions(self.EXT))
        out = self.run_cmd(fsm.cmd_approve, self.EXT)
        return out, self.journal_actions(self.EXT)[before:]

    def test_ac6_project_ref_unsynced_refuses_merge_gate(self):
        """Ссылка внешней задачи расходится с `origin` проекта — гейт мержа отказывает.

        Сценарий: `origin` проекта отвергает запись ссылок документов,
        `origin` пульта принимает всё. Переходы внешней задачи доводят её
        до гейта мержа (локальная ссылка в git проекта впереди его
        `origin`), `approve` без sha: в журнале отказ гейта мержа о
        документах, вывод называет ссылку, задача осталась на гейте.

        Ловит мутацию: сверка гейта мержа (`origin_sync_refusal`) читает
        репозиторий пульта и его `origin` — там ссылки внешней задачи нет
        ни локально, ни в `origin`, «совпадение» пропускает гейт дальше.
        """
        self.reject_ref_pushes(self.project_bare)
        self.random_transitions(self.EXT)
        self.move(self.EXT, "merge_gate")
        self.assertNotEqual(self.project_ref(self.EXT),
                            self.remote_ref(self.project_bare, self.EXT),
                            self.why("предусловие: ссылка расходится с origin проекта"))

        out, new_actions = self.approve()

        self.assertIn(fsm_merge_gate.MERGE_UNSYNCED_JOURNAL_ACTION, new_actions,
                      self.why(f"гейт мержа не отказал; вывод:\n{out}"))
        self.assertIn(self.ref(self.EXT), out, self.why("отказ не называет ссылку"))
        self.assertEqual(self.state(self.EXT), "merge_gate")

    def test_ac6_pult_ref_state_does_not_decide_merge_gate(self):
        """Ссылка внешней задачи совпадает с `origin` проекта — расхождение одноимённой ссылки в пульте гейт не останавливает.

        Сценарий: `origin` пульта отвергает запись ссылок документов, и в
        git пульта лежит посторонняя ссылка `refs/artifacts/<id внешней
        задачи>`, которой в `origin` пульта нет; `origin` проекта
        принимает всё, ссылка проекта с ним совпадает. `approve` без sha
        на гейте мержа: отказа о документах в журнале нет, гейт идёт к
        следующим шагам (журнал пополнился), задача осталась на гейте
        (ветки кода у неё нет — мерж дальше не идёт).

        Ловит мутацию: сверка гейта мержа читает репозиторий пульта —
        расхождение посторонней ссылки пульта с его `origin` даёт отказ
        гейта мержа внешней задаче.
        """
        self.reject_ref_pushes(self.bare)
        self.seed_pult_ref(self.EXT)
        self.random_transitions(self.EXT)
        self.move(self.EXT, "merge_gate")
        self.assertEqual(self.project_ref(self.EXT),
                         self.remote_ref(self.project_bare, self.EXT),
                         self.why("предусловие: ссылка совпадает с origin проекта"))

        out, new_actions = self.approve()

        self.assertTrue(new_actions, self.why(f"approve не дошёл до гейта:\n{out}"))
        self.assertNotIn(fsm_merge_gate.MERGE_UNSYNCED_JOURNAL_ACTION, new_actions,
                         self.why(f"отказ по ссылке пульта; вывод:\n{out}"))
        self.assertEqual(self.state(self.EXT), "merge_gate")


class KillReadsProjectTest(ProjectDocsRefSandbox):

    def test_ac7_project_ref_unsynced_refuses_kill(self):
        """Ссылка внешней задачи расходится с `origin` проекта — `kill` отказывает, задача и ссылка не тронуты.

        Сценарий: `origin` проекта отвергает запись ссылок документов,
        `origin` пульта принимает всё; после переходов внешней задачи
        `kill`: процесс завершён отказом, называющим ссылку, в журнале
        отказ `kill` о документах, состояние прежнее, голова ссылки в git
        проекта прежняя (коммита закрытия нет).

        Ловит мутацию: сверка `kill` (`origin_sync_refusal`) читает
        репозиторий пульта — ссылки внешней задачи там нет ни локально,
        ни в `origin`, задача закрывается с документами, которых нет в
        `origin` проекта.
        """
        self.reject_ref_pushes(self.project_bare)
        self.random_transitions(self.EXT)
        state = self.state(self.EXT)
        head = self.project_ref(self.EXT)

        out = self.run_cmd(cleanup.cmd_kill, self.EXT)

        self.assertIn("SystemExit", out, self.why(f"kill не отказал:\n{out}"))
        self.assertIn(self.ref(self.EXT), out)
        self.assertIn(cleanup.KILL_UNSYNCED_JOURNAL_ACTION,
                      self.journal_actions(self.EXT))
        self.assertEqual(self.state(self.EXT), state)
        self.assertEqual(self.project_ref(self.EXT), head)

    def test_ac7_pult_ref_state_does_not_decide_kill(self):
        """Ссылка внешней задачи совпадает с `origin` проекта — посторонняя ссылка пульта `kill` не останавливает.

        Сценарий: `origin` пульта отвергает запись ссылок документов, в
        git пульта лежит посторонняя ссылка с id внешней задачи, которой
        нет в `origin` пульта; ссылка проекта совпадает с `origin`
        проекта. `kill` закрывает задачу без отказа о документах.

        Ловит мутацию: сверка `kill` читает репозиторий пульта —
        расхождение посторонней ссылки пульта с его `origin` отказывает
        `kill` внешней задачи.
        """
        self.reject_ref_pushes(self.bare)
        self.seed_pult_ref(self.EXT)
        self.random_transitions(self.EXT)

        out = self.run_cmd(cleanup.cmd_kill, self.EXT)

        self.assertNotIn(cleanup.KILL_UNSYNCED_JOURNAL_ACTION,
                         self.journal_actions(self.EXT),
                         self.why(f"kill отказал по ссылке пульта:\n{out}"))
        self.assertEqual(self.state(self.EXT), "killed", self.why(out))


class DoctorReadsProjectTest(ProjectDocsRefSandbox):

    def test_ac8_doctor_warns_on_project_ref_unsynced(self):
        """Ссылка внешней задачи впереди `origin` проекта — `doctor` предупреждает об этой задаче.

        Сценарий: `origin` проекта отвергает запись ссылок документов,
        `origin` пульта принимает всё; после переходов внешней задачи
        сверка `doctor` синхронности ссылок несёт не-`ok` запись с id этой
        задачи.

        Ловит мутацию: `check_artifact_ref_sync` берёт голову ссылки и
        `ls-remote` из репозитория пульта для любой задачи — внешней
        задачи там нет, расхождение в репозитории проекта молча
        пропускается.
        """
        self.reject_ref_pushes(self.project_bare)
        self.random_transitions(self.EXT)
        self.assertNotEqual(self.project_ref(self.EXT),
                            self.remote_ref(self.project_bare, self.EXT))

        self.assertTrue(self.problems_about(self.EXT), self.why(
            f"doctor молчит о расхождении: "
            f"{doctor.check_artifact_ref_sync(store.db())}"))

    def test_ac8_doctor_ignores_pult_ref_of_external_task(self):
        """Ссылка внешней задачи совпадает с `origin` проекта — посторонняя ссылка пульта не даёт предупреждения.

        Сценарий: `origin` пульта отвергает запись ссылок документов, в
        git пульта лежит посторонняя ссылка с id внешней задачи, которой
        нет в `origin` пульта; ссылка проекта совпадает с `origin`
        проекта. Сверка `doctor` не несёт не-`ok` записей об этой задаче.

        Ловит мутацию: сверка `doctor` читает репозиторий пульта для
        внешней задачи — посторонняя ссылка пульта «не отправлена» и даёт
        предупреждение.
        """
        self.reject_ref_pushes(self.bare)
        self.seed_pult_ref(self.EXT)
        self.random_transitions(self.EXT)
        self.assertEqual(self.project_ref(self.EXT),
                         self.remote_ref(self.project_bare, self.EXT))

        self.assertEqual(self.problems_about(self.EXT), [], self.why(
            "doctor предупреждает по ссылке пульта"))


class ArtelOutcomesKeptTest(ProjectDocsRefSandbox):

    def test_ac9_artel_unsynced_ref_refused_by_merge_gate_kill_and_doctor(self):
        """Неотправленная ссылка задачи артели: отказ гейта мержа, отказ `kill`, предупреждение `doctor` — как до задачи.

        Сценарий: `origin` пульта отвергает запись ссылок документов, у
        задачи артели ссылка в git пульта, которой нет в `origin` пульта
        (переходы её не досылают). `doctor` несёт не-`ok` запись о задаче;
        `approve` на гейте мержа пишет отказ о документах, задача остаётся
        на гейте; `kill` отказывает и не меняет состояние.

        Ловит мутацию: репозиторий задачи для артели выбирается как
        область проекта `config.PROJECTS/artel` (по образцу `docs_root`) —
        ссылки там нет, сверки гейта мержа, `kill` и `doctor` считают её
        «нечего сверять» и пропускают.
        """
        self.reject_ref_pushes(self.bare)
        self.seed_pult_ref(self.ART)
        self.move(self.ART, "merge_gate")

        self.assertTrue(self.problems_about(self.ART),
                        self.why("doctor молчит о неотправленной ссылке артели"))

        out = self.run_cmd(fsm.cmd_approve, self.ART)
        self.assertIn(fsm_merge_gate.MERGE_UNSYNCED_JOURNAL_ACTION,
                      self.journal_actions(self.ART), self.why(out))
        self.assertEqual(self.state(self.ART), "merge_gate")

        out = self.run_cmd(cleanup.cmd_kill, self.ART)
        self.assertIn("SystemExit", out, self.why(out))
        self.assertIn(cleanup.KILL_UNSYNCED_JOURNAL_ACTION,
                      self.journal_actions(self.ART))
        self.assertEqual(self.state(self.ART), "merge_gate")

    def test_ac9_artel_synced_ref_passes_doctor_and_kill(self):
        """Отправленная ссылка задачи артели: `doctor` молчит, `kill` закрывает задачу коммитом закрытия в `origin` пульта.

        Сценарий: у задачи артели неотправленная ссылка в git пульта;
        переход досылает её в `origin` пульта. `doctor` не несёт не-`ok`
        записей о задаче; `kill` закрывает её, голова ссылки в git пульта
        — новый коммит закрытия, и она же в `origin` пульта.

        Ловит мутацию: досылка на переходе (`send_pending`) для артели
        отправляет в `origin` области проекта, а не пульта — ссылка
        остаётся неотправленной, `doctor` предупреждает, `kill` отказывает.
        """
        before = self.seed_pult_ref(self.ART)
        self.move(self.ART, "verifying")

        self.assertEqual(self.problems_about(self.ART), [],
                         self.why("doctor предупреждает о досланной ссылке"))

        out = self.run_cmd(cleanup.cmd_kill, self.ART)
        self.assertEqual(self.state(self.ART), "killed", self.why(out))
        head = self.pult_ref(self.ART)
        self.assertNotEqual(head, before, self.why("коммита закрытия нет"))
        self.assertEqual(self.remote_ref(self.bare, self.ART), head,
                         self.why("коммит закрытия не в origin пульта"))


if __name__ == "__main__":
    unittest.main()
