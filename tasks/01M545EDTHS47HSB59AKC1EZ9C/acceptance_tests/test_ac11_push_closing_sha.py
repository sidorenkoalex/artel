"""AC-11: досылка коммита закрытия `doctor` в `origin` внешнего проекта.

Группа: разовый
Красен до реализации: push `_push_closing_sha` по URL `origin` клона идёт без помощника учётных данных пульта — в его окружении `git credential fill` по URL проекта отдаёт пароль чужого помощника, а пустой слот `token_slot` не даёт отказа с именем слота.

Разовый, а не долгоживущий, потому что SPEC (требование 8, AC-11) прямо
требует вызова закрытой `orchestrator/doctor/artifact_branches.py::
_push_closing_sha`: для внешнего проекта случай «источник вне
`.artel/projects/<проект>/`» публичным путём `doctor --fix` недостижим, а
долгоживущий файл закрытых имён не касается. Окружение — та же песочница,
что у долгоживущего файла задачи (`ProjectSandbox`: второй настоящий
git-репозиторий `origin`, подставной `gh`, подмена `keychain.token`,
конкурирующие помощники глобальный и с областью URL проекта).
"""
import contextlib
import io
import string
import unittest

from orchestrator import config, doctor
from orchestrator.doctor import artifact_branches
from tests.test_01m545edths47hsb59akc1ez9c_project_token import ProjectSandbox


class PushClosingShaTest(ProjectSandbox):
    """`_push_closing_sha(source, repo, …)`: `repo` — клон проекта, `source`
    — репозиторий вне области проекта."""

    def new_task_id(self) -> str:
        return "".join(self.rng.choice(string.ascii_uppercase + string.digits)
                       for _ in range(26))

    def outside_repo(self):
        outside = self.aux / f"source-{self.rng.randrange(10**6)}"
        self.git("init", "-q", "-b", config.MAIN_BRANCH, str(outside))
        self.git("-C", str(outside), "commit", "-q", "--allow-empty", "-m",
                 f"закрытие {self.rng.random()}")
        return outside

    def push_closing(self, source):
        task_id = self.new_task_id()
        closing = self.git("-C", str(source), "rev-parse", "HEAD").strip()
        ref = doctor.artifact_branch.branch_name(task_id)
        out = io.StringIO()
        with self.recording() as rec, contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            artifact_branches._push_closing_sha(source, self.clone, task_id,
                                                closing)
        return closing, ref, out.getvalue(), rec

    def test_ac11_push_closing_sha_uses_project_token(self):
        """Досылка из репозитория вне области проекта — с токеном слота.

        Источник — главная копия пульта (`config.ROOT`) либо посторонний
        репозиторий вне корня. Push проходит: `refs/artifacts/<id>` в
        `origin` — коммит закрытия; в окружении этого git-вызова `git
        credential fill` по URL проекта отдаёт только токен слота при каждом
        наборе конкурирующих помощников. Значения токена нет в argv вызовов
        и в выводе `doctor`. Пустой слот — коммит не дослан, вывод называет
        слот.

        Ловит мутацию: признак проекта берётся только по пути `-C`
        (источник вне `.artel/projects/<проект>/` признака не даёт) — push
        идёт без помощника пульта и `credential fill` отдаёт чужой пароль,
        а пустой слот не останавливает push.
        """
        for source in (config.ROOT, self.outside_repo()):
            with self.subTest(источник=str(source)):
                closing, ref, out, rec = self.push_closing(source)
                self.assertEqual(self.origin_has(ref), closing,
                                 self.msg(f"коммит закрытия не дослан: {out}"))
                pushes = rec.git_calls("push")
                self.assertEqual(len(pushes), 1, self.msg(str(rec.calls)))
                self.assert_slot_credential(pushes[0].env,
                                            f"досылка из {source}")
                for call in rec.calls:
                    self.assertNotIn(self.token, " ".join(call.argv),
                                     self.msg("токен в argv вызова"))
                self.assertNotIn(self.token, out, self.msg("токен в выводе"))
        with self.subTest(слот="пуст"):
            self.slots[self.slot] = None
            closing, ref, out, rec = self.push_closing(self.outside_repo())
            self.assertEqual(self.origin_has(ref), "",
                             self.msg("дослано при пустом слоте"))
            self.assertIn(self.slot, out,
                          self.msg(f"вывод без имени слота: {out}"))


if __name__ == "__main__":
    unittest.main()
