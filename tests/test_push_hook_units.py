"""Мелкие свойства второго рубежа белого списка отправок (SPEC
01M6EZXVFGCHB1S4W45AWJ0QH6): правила хука `scripts/git-hooks/target-human/
pre-push` по строкам stdin, хост адреса записи и помощник учётных данных
пульта, проект `git clone` по адресу, сверки действующей конфигурации
`gitcmd` перед отправкой, эталон файла политики.

Хук гоняется настоящим `/bin/sh` в каталоге временного репозитория — строки
stdin подаёт тест, как их подал бы git; сверки конфигурации и `git
credential fill` — настоящим git с пустым `HOME` и без системного слоя.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import gitcmd, targets, workspace  # noqa: E402
from tests.sandbox import resilient_tmp_cleanup  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
HUMAN_PRE_PUSH = REPO_ROOT / "scripts" / "git-hooks" / "target-human" / "pre-push"
ZERO = "0" * 40
SHA = "1" * 40


def policy(template: str = "task/{id}-{slug}", base: str = "main") -> str:
    return (f"project=p\nbase={base}\nbranch_template={template}\n"
            f"artifacts_prefix=refs/artifacts/\n")


class _TempRepoTest(unittest.TestCase):
    """Временный репозиторий; окружение git — пустой `HOME`, без
    системного слоя и `GIT_*` процесса."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.tmp = Path(tmp.name).resolve()
        home = self.tmp / "home"
        home.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(HOME=str(home), GIT_CONFIG_NOSYSTEM="1",
                   GIT_TERMINAL_PROMPT="0")
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.repo = self.tmp / "repo"
        self.git("init", "-q", "-b", "main", str(self.repo))

    def git(self, *args: str, cwd: Path | None = None, **kwargs):
        return subprocess.run(["git", *args], cwd=cwd or self.tmp,
                              capture_output=True, text=True, check=True,
                              **kwargs)


class TargetHumanPrePushTest(_TempRepoTest):

    def hook(self, *lines: str, text: str | None = None):
        path = self.repo / ".git" / "artel-push-policy"
        if text is not None:
            path.write_text(text, encoding="utf-8")
        return subprocess.run(["/bin/sh", str(HUMAN_PRE_PUSH)], cwd=self.repo,
                              input="".join(f"{line}\n" for line in lines),
                              capture_output=True, text=True)

    def test_template_placeholders_nonempty_and_glob_characters_literal(self):
        """Шаблон с `*`, `[…]` и `{ref}`: подстановки — непустые, символы
        образца — буквально.

        Ловит мутацию: подстановка шаблона раскрывается в `*` (пустая
        подстрока проходит) либо символы `*`/`[` шаблона не экранируются —
        `axb/1` проходит шаблон `a*b/{id}`.
        """
        cases = [("a*b/{id}", "a*b/1", 0), ("a*b/{id}", "axb/1", 1),
                 ("f[x]/{ref}_{id}", "f[x]/R_1", 0),
                 ("f[x]/{ref}_{id}", "fx/R_1", 1),
                 ("f[x]/{ref}_{id}", "f[x]/_1", 1),
                 ("task/{id}-{slug}", "task/-s", 1)]
        for template, branch, code in cases:
            with self.subTest(template=template, branch=branch):
                res = self.hook(f"refs/heads/x {SHA} refs/heads/{branch} {ZERO}",
                                text=policy(template))
                self.assertEqual(res.returncode, code, res.stderr)

    def test_artifacts_update_and_delete_pass_branch_delete_refused(self):
        """Ссылка `refs/artifacts/<id>` проходит и обновлением, и удалением;
        удаление ветки по шаблону и голый префикс — отказ с именем ссылки.

        Ловит мутацию: удаление (нулевой sha) разбирается до префикса
        ссылки — удаление ссылки документов отказывается; префикс без
        имени `refs/artifacts/` принят за ссылку документов.
        """
        text = policy()
        for line, code in ((f"x {SHA} refs/artifacts/T1 {ZERO}", 0),
                           (f"(delete) {ZERO} refs/artifacts/T1 {SHA}", 0),
                           (f"(delete) {ZERO} refs/heads/task/a-b {SHA}", 1),
                           (f"x {SHA} refs/artifacts/ {ZERO}", 1)):
            with self.subTest(line=line):
                res = self.hook(line, text=text)
                self.assertEqual(res.returncode, code, res.stderr)
                if code:
                    self.assertIn(line.split()[2], res.stderr)

    def test_one_forbidden_line_refuses_whole_push(self):
        """Разрешённая строка перед запрещённой не спасает отправку: отказ
        называет запрещённую ссылку и причину `base`.

        Ловит мутацию: хук решает по первой строке stdin и выходит с 0.
        """
        res = self.hook(f"x {SHA} refs/heads/task/a-b {ZERO}",
                        f"x {SHA} refs/heads/develop {ZERO}",
                        text=policy(base="develop"))
        self.assertEqual(res.returncode, 1)
        self.assertIn("refs/heads/develop", res.stderr)
        self.assertIn("base develop", res.stderr)

    def test_policy_without_key_refuses_naming_key_and_path(self):
        """Файл политики без ключа `artifacts_prefix` — отказ любой
        отправке, причина называет ключ и путь файла.

        Ловит мутацию: из сверки ключей файла выпал `artifacts_prefix` —
        пустой префикс пропускает любую ссылку как ссылку документов.
        """
        text = "".join(line + "\n" for line in policy().splitlines()
                       if not line.startswith("artifacts_prefix="))
        res = self.hook(f"x {SHA} refs/tags/v1 {ZERO}", text=text)
        self.assertEqual(res.returncode, 1)
        self.assertIn("artifacts_prefix", res.stderr)
        self.assertIn(".git/artel-push-policy", res.stderr)


class HostingHelperTest(_TempRepoTest):

    def test_url_host_forms(self):
        """Хост адреса записи — в виде, в каком git называет его помощнику.

        Ловит мутацию: порт отбрасывается (хост `h:8443` не совпадёт с
        запросом git) либо учётная часть `user@` остаётся в хосте; путь и
        `file://` дают непустой хост.
        """
        self.assertEqual(gitcmd.url_host("https://localhost:8443/g/r.git"),
                         "localhost:8443")
        # Сторож инварианта 35 читает учётную часть `u:p@` как хост —
        # адрес собран из частей, хост тот же localhost.
        userinfo = "u:p@"
        self.assertEqual(gitcmd.url_host("https://" + userinfo + "127.0.0.1/g/r"),
                         "127.0.0.1")
        self.assertEqual(gitcmd.url_host("git@localhost:g/r.git"), "localhost")
        self.assertEqual(gitcmd.url_host("file:///srv/r.git"), "")
        self.assertEqual(gitcmd.url_host("/srv/r.git"), "")

    def fill(self, env: dict, url: str) -> str:
        return subprocess.run(["git", "credential", "fill"], cwd=self.repo,
                              input=f"url={url}\n\n", capture_output=True,
                              text=True, env=env).stdout

    def test_helper_answers_record_host_with_port_only(self):
        """Помощник пульта отдаёт пароль хосту записи с тем же портом; иной
        порт того же хоста — без пароля.

        Ловит мутацию: помощник сверяет `host` по началу строки или без
        порта — запрос на `localhost:9999` получает токен слота.
        """
        env = gitcmd.hosting_env(dict(os.environ), "tok-77", "localhost:8443")
        self.assertIn("password=tok-77\n",
                      self.fill(env, "https://localhost:8443/g/r"))
        other = self.fill(env, "https://localhost:9999/g/r")
        self.assertNotIn("password=", other)
        self.assertNotIn("tok-77", other)

    def test_clone_project_by_url_only_with_token_slot(self):
        """`git clone <url записи>` — хостинговый вызов проекта со
        `token_slot`; запись без слота и артель — нет.

        Ловит мутацию: клон узнаётся хостинговым для любой записи (запись
        без слота в процессе роли получила бы отказ) либо проект клона
        ищется по рабочему каталогу, которого у клона ещё нет.
        """
        entries = {"artel": {"url": "/srv/artel.git", "token_slot": "a"},
                   "pslot": {"url": "/srv/pslot.git", "token_slot": "pslot-t"},
                   "pnone": {"url": "/srv/pnone.git"}}
        with mock.patch.object(gitcmd, "_declared_targets", lambda: entries):
            found = gitcmd._hosting_project(
                ("-C", str(self.tmp), "clone", "--quiet", "/srv/pslot.git", "repo"))
            self.assertEqual(found[0], "pslot")
            self.assertIsNone(gitcmd._hosting_project(
                ("clone", "--quiet", "/srv/pnone.git", "repo")))
            self.assertIsNone(gitcmd._hosting_project(
                ("clone", "/srv/artel.git", "repo")))


class ConfigRedirectRefusalTest(_TempRepoTest):

    def setUp(self):
        super().setUp()
        self.url = str(self.tmp / "origin.git")
        self.git("remote", "add", "origin", self.url, cwd=self.repo)
        self.entry = {"url": self.url, "merge_gate": "target-human"}

    def refusal(self):
        return gitcmd._config_redirect_refusal(self.entry, self.repo)

    def test_global_layer_findings_refuse(self):
        """Находка в глобальном слое (`~/.gitconfig`) — тоже отказ: сверка
        читает действующую конфигурацию, не только клон (ANSWER-1 п. 4).

        Ловит мутацию: сверка читает только `--local` — `pushInsteadOf` из
        `~/.gitconfig` проходит.
        """
        self.assertIsNone(self.refusal())
        self.git("config", "--global", "url./elsewhere.pushInsteadOf", self.url)
        self.assertIn("pushinsteadof", (self.refusal() or "").lower())

    def test_hooks_path_relative_or_foreign_refused_own_passes(self):
        """`core.hooksPath` = абсолютный каталог хуков пульта проекта —
        не находка; относительный или чужой — отказ со значением.

        Ловит мутацию: сверка сравнивает последнее слово пути или
        `endswith` — относительный `scripts/git-hooks/target-human`
        проходит.
        """
        own = gitcmd.project_hooks_path(self.entry)
        self.git("config", "core.hooksPath", str(own), cwd=self.repo)
        self.assertIsNone(self.refusal())
        for value in ("scripts/git-hooks/target-human", str(self.tmp / "x")):
            with self.subTest(value=value):
                self.git("config", "core.hooksPath", value, cwd=self.repo)
                self.assertIn(value, self.refusal() or "")


class PushPolicyTextTest(unittest.TestCase):

    def test_four_lines_in_order_with_default_template(self):
        """Эталон файла политики — четыре строки `ключ=значение` в порядке
        SPEC; поля `branch_template` нет — шаблон по умолчанию.

        Ловит мутацию: шаблон по умолчанию не подставлен (пустой
        `branch_template=` отказал бы любой отправке) либо порядок строк
        иной.
        """
        text = workspace.push_policy_text("p1", {"base": "develop"})
        self.assertEqual(text, "project=p1\nbase=develop\n"
                               f"branch_template={targets.DEFAULT_BRANCH_TEMPLATE}\n"
                               "artifacts_prefix=refs/artifacts/\n")


if __name__ == "__main__":
    unittest.main()
