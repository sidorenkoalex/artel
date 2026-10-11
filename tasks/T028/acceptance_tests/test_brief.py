"""Приёмочные тесты T028 — бриф роли одним документом (developer, analyst).

Источник — только tasks/T028/SPEC.md, раздел «Критерии приёмки» (AC-1..AC-9).

Точка входа под тестом — `orchestrator.runner.cmd_run` (тот же приём, что
у tests/test_agent_prompt.py и tests/test_analyst_role.py): промпт роли
наблюдается через подменённый `subprocess.Popen`, песочница — БД/каталог
задач/логи во tmpdir, `config.ROOT` НЕ подменяется — SPEC.md/TZ.md здесь
синтетические (пишутся тестом в tmp-каталог задачи), а
`docs/codebase-map.md` и `CLAUDE.md` читаются как есть из настоящего
дерева пульта, тем же способом, каким test_agent_prompt.py уже читает
`skills/*.md` из настоящего `config.ROOT`.

Свежесть карты (AC-5..AC-7, требование 5 SPEC — «тем же способом, каким
уже пользуется CI-джоба codebase-map») сверяется тем же `git diff` по
`built_at_sha` из `docs/codebase-map.md`: `make_fake_git` ниже отвечает и
на булеву форму (`git diff --quiet a b -- paths`, применяет
`gitcmd.diff_paths`), и на перечисляющую (`git diff --name-only a b --
paths`, применяет CI-джоба и нужна для списка путей расхождения из AC-7) —
тесты не привязаны к тому, какую из двух выберет разработчик.

Регенерация карты (`scripts/codebase_map.py`) перехватывается подменой
`subprocess.run` целиком: реальный запуск переписал бы настоящий
`docs/codebase-map.md` пульта под тестом, а это файл рабочего дерева,
не фикстуры.

Формат хэшей компонентов (AC-8, AC-9) SPEC не называет — тесты проверяют
контракт алгоритмо-независимо: в журнале шага должны появиться
хэш-подобные токены, и они обязаны меняться вместе с содержимым
компонента (иначе это не хэш содержимого, а статическая метка).
"""
import io
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, gitcmd, roles, runner, store  # noqa: E402

HEX_TOKEN = re.compile(r"[0-9a-f]{8,64}")


def make_fake_git(stale_paths):
    """Заглушка `gitcmd.git`: «карта свежа» при stale_paths=[], иначе —
    расхождение по путям stale_paths. Понимает обе формы сверки диапазона
    `built_at_sha..HEAD`, которыми могла бы воспользоваться реализация."""
    def fake(*args) -> subprocess.CompletedProcess:
        if args and args[0] == "diff":
            if "--quiet" in args:
                rc = 1 if stale_paths else 0
                return subprocess.CompletedProcess(list(args), rc, "", "")
            stdout = ("\n".join(stale_paths) + "\n") if stale_paths else ""
            return subprocess.CompletedProcess(list(args), 0, stdout, "")
        return subprocess.CompletedProcess(list(args), 0, "", "")
    return fake


fake_git = make_fake_git([])


def real_text(rel: str) -> str:
    return (config.ROOT / rel).read_text(encoding="utf-8")


def real_built_at_sha() -> str:
    match = re.search(r"^built_at_sha:\s*(\S+)",
                      real_text("docs/codebase-map.md"), re.M)
    assert match, "во frontmatter docs/codebase-map.md нет built_at_sha"
    return match.group(1)


class FakeStream:
    def __init__(self, lines):
        self.lines = iter(lines)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.lines)

    def close(self):
        pass


class FakeProc:
    def __init__(self, lines, returncode: int = 0):
        self.stdout = FakeStream(lines)
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode


class BriefSandboxTest(unittest.TestCase):
    """Общая песочница шага: БД/каталог задач/логи во tmpdir."""

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks", lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Бриф роли")
        self.tdir = config.TASKS / self.TASK

    # ------------------------------------------------------------ утилиты

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def write(self, name: str, text: str) -> str:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / name).write_text(text, encoding="utf-8")
        return text

    def actor_steps(self, actor: str, since: int = 0) -> list:
        return [s for s in store.task_steps(store.db(), self.TASK)[since:]
                if s["actor"] == actor]

    def step_count(self) -> int:
        return len(store.task_steps(store.db(), self.TASK))

    def run_step(self, state: str, git_fn=fake_git,
                regen: subprocess.CompletedProcess | None = None):
        """Прогон шага: (промпт роли, мок subprocess.run регенерации карты)."""
        self.set_state(state)
        with mock.patch.object(gitcmd, "git", git_fn):
            with mock.patch("subprocess.run") as run_mock:
                if regen is not None:
                    run_mock.return_value = regen
                with mock.patch.object(runner.subprocess, "Popen") as popen:
                    popen.return_value = FakeProc(["готово\n"])
                    self.capture(runner.cmd_run, self.TASK)
        prompt = Path(popen.call_args.kwargs["stdin"].name).read_text(
            encoding="utf-8")
        return prompt, run_mock

    def regen_invoked(self, run_mock: mock.Mock) -> bool:
        for call in run_mock.call_args_list:
            cmd = call.args[0] if call.args else call.kwargs.get("args", [])
            if any("codebase_map.py" in str(part) for part in cmd):
                return True
        return False


# --------------------------------------------------------------------------
# Роль developer: AC-1..AC-8.

class DeveloperBriefTest(BriefSandboxTest):

    def developer_skills_text(self) -> str:
        names = roles.skills("developer")
        return "\n\n".join(real_text(f"skills/{n}.md") for n in names)

    def run_developer(self, **kw):
        prompt, run_mock = self.run_step("in_dev", **kw)
        self.last_run_mock = run_mock
        return prompt

    def test_ac1_prompt_contains_full_spec_text(self):
        spec_text = self.write(
            "SPEC.md", "# SPEC: AC-1\n\nМаркер-АС1-уникальный-текст-критерия.\n")

        prompt = self.run_developer()

        self.assertIn(spec_text, prompt)

    def test_ac2_prompt_contains_full_codebase_map_text(self):
        self.write("SPEC.md", "# SPEC: AC-2\n")
        map_text = real_text("docs/codebase-map.md")

        prompt = self.run_developer()

        self.assertIn(map_text, prompt)

    def test_ac3_conventions_component_is_separate_from_skills_block(self):
        self.write("SPEC.md", "# SPEC: AC-3\n")
        claude_text = real_text("CLAUDE.md")
        skills_text = self.developer_skills_text()

        prompt = self.run_developer()

        self.assertIn(claude_text, prompt)
        self.assertIn(skills_text, prompt)
        s_start = prompt.index(skills_text)
        s_end = s_start + len(skills_text)
        c_start = prompt.index(claude_text)
        c_end = c_start + len(claude_text)
        overlaps = c_start < s_end and s_start < c_end
        self.assertFalse(
            overlaps,
            "CLAUDE.md слился с текстом блока «--- СКИЛЫ РОЛИ ---» — "
            "конвенции обязаны быть отдельным компонентом (требование 3)")

    def test_ac4_skill_text_appears_only_once_in_the_prompt(self):
        self.write("SPEC.md", "# SPEC: AC-4\n")
        skill_text = real_text("skills/coding-standards.md")

        prompt = self.run_developer()

        self.assertEqual(
            prompt.count(skill_text), 1,
            "текст skills/coding-standards.md продублирован сверх "
            "блока «--- СКИЛЫ РОЛИ ---»")

    def test_ac5_stale_map_triggers_regeneration_before_the_brief(self):
        self.write("SPEC.md", "# SPEC: AC-5\n")

        prompt, run_mock = self.run_step(
            "in_dev", git_fn=make_fake_git(["orchestrator/runner.py"]),
            regen=subprocess.CompletedProcess(
                ["python3", "scripts/codebase_map.py"], 0, "", ""))

        self.assertTrue(
            self.regen_invoked(run_mock),
            "scripts/codebase_map.py не был запущен при обнаруженном "
            "расхождении built_at_sha..HEAD по orchestrator/*.py")

    def test_ac6_fresh_map_is_not_regenerated_and_gets_no_stale_note(self):
        self.write("SPEC.md", "# SPEC: AC-6\n")
        map_text = real_text("docs/codebase-map.md")

        prompt, run_mock = self.run_step("in_dev", git_fn=make_fake_git([]))

        run_mock.assert_not_called()
        self.assertIn(
            map_text, prompt,
            "при отсутствии расхождений карта должна попасть в бриф "
            "как есть, без пометки о неактуальности")

    def test_ac7_failed_regeneration_is_alerted_and_marked_in_the_brief(self):
        self.write("SPEC.md", "# SPEC: AC-7\n")
        stale_paths = ["orchestrator/runner.py", "scripts/codebase_map.py"]
        before_alerts = len(
            store.db().execute("SELECT id FROM alerts").fetchall())

        prompt, run_mock = self.run_step(
            "in_dev", git_fn=make_fake_git(stale_paths),
            regen=subprocess.CompletedProcess(
                ["python3", "scripts/codebase_map.py"], 1, "",
                "AC-7-стенд: генератор упал"))

        self.assertTrue(self.regen_invoked(run_mock),
                        "регенерация не была запущена при расхождении")

        base_sha = real_built_at_sha()
        self.assertIn(
            base_sha, prompt,
            "пометка о неактуальности карты не называет использованный "
            "built_at_sha")
        for path in stale_paths:
            self.assertIn(
                path, prompt,
                f"путь расхождения {path} не назван в пометке брифа")

        alerts = store.db().execute(
            "SELECT message, source FROM alerts ORDER BY id DESC").fetchall()
        self.assertGreater(len(alerts), before_alerts,
                           "алерт о неудачной регенерации карты не записан")
        self.assertTrue(
            any("AC-7-стенд" in (a["message"] or "") + (a["source"] or "")
                for a in alerts),
            "записанный алерт не ссылается на причину сбоя регенерации")

    def test_ac8_component_hashes_are_journaled_and_track_content(self):
        self.write("SPEC.md", "# SPEC: AC-8, версия раз.\n")
        before_1 = self.step_count()
        self.run_developer()
        detail_1 = "\n".join(
            s["detail"] for s in self.actor_steps("developer", before_1))
        tokens_1 = set(HEX_TOKEN.findall(detail_1))
        self.assertGreaterEqual(
            len(tokens_1), 3,
            "в журнале шага меньше трёх хэш-подобных токенов — ожидались "
            "хэши компонентов SPEC, карты и конвенций (требование 8)")

        before_2 = self.step_count()
        self.write("SPEC.md", "# SPEC: AC-8, версия два — другое содержимое.\n")
        self.run_developer()
        detail_2 = "\n".join(
            s["detail"] for s in self.actor_steps("developer", before_2))
        tokens_2 = set(HEX_TOKEN.findall(detail_2))
        self.assertGreaterEqual(len(tokens_2), 3)
        self.assertNotEqual(
            tokens_1, tokens_2,
            "хэши в журнале не изменились при изменении содержимого "
            "SPEC.md — запись не отражает реальное содержимое компонента")


# --------------------------------------------------------------------------
# Роль analyst: AC-9 (та же сверка/регенерация/хэш, что у developer, поверх
# существующего входа TZ.md).

TZ_RAW = "Каждой роли — собранный бриф одним документом.\n"


class AnalystBriefTest(BriefSandboxTest):

    def write_tz(self, raw: str = TZ_RAW) -> Path:
        self.tdir.mkdir(parents=True, exist_ok=True)
        tz_path = self.tdir / "TZ.md"
        tz_path.write_text(catalog._tz_document(self.TASK, "Бриф роли", raw),
                           encoding="utf-8")
        return tz_path

    def run_analyst(self, **kw):
        prompt, run_mock = self.run_step("spec_writing", **kw)
        self.last_run_mock = run_mock
        return prompt

    def test_ac9_prompt_adds_full_codebase_map_to_the_tz_input(self):
        self.write_tz()
        map_text = real_text("docs/codebase-map.md")

        prompt = self.run_analyst()

        self.assertIn("TZ.md", prompt)
        self.assertIn(map_text, prompt)

    def test_ac9_stale_map_triggers_regeneration_for_analyst_too(self):
        self.write_tz()

        prompt, run_mock = self.run_step(
            "spec_writing", git_fn=make_fake_git(["scripts/codebase_map.py"]),
            regen=subprocess.CompletedProcess(
                ["python3", "scripts/codebase_map.py"], 0, "", ""))

        self.assertTrue(
            self.regen_invoked(run_mock),
            "у роли analyst сверка свежести карты не совпадает с developer "
            "— регенерация не была запущена при расхождении")

    def test_ac9_map_hash_is_journaled_for_the_analyst_step(self):
        self.write_tz()
        before = self.step_count()

        self.run_analyst()

        detail = "\n".join(s["detail"] for s in self.actor_steps("analyst", before))
        tokens = set(HEX_TOKEN.findall(detail))
        self.assertGreaterEqual(
            len(tokens), 1,
            "хэш компонента «карта» не найден в журнале шага analyst")


if __name__ == "__main__":
    unittest.main()
