"""AC-10 (часть): сверка фиксации и перечень сумм долгоживущих тестов
отказывают роли так же после выноса документов из рабочей копии кода.

Группа: разовый

Красен до реализации: автокоммит шага (`checkpoint._commit_step_artifacts_to_branch` -> `artifact_branch.commit_files(require_change=False)`) коммитит выложенный каталог документов поверх ТЕКУЩЕЙ головы ссылки — то есть поверх коммита, которым роль сама сдвинула `refs/artifacts/<id>`, — и тут же перефиксирует её (`store.record_fixation`): подмена ролью становится зафиксированным состоянием, следующий шаг стартует (test_ac10_role_moving_docs_ref_is_refused_by_fixation_check); метод перечня сумм зелёный с рождения — перечень читается из дерева коммита лока, вынос его сторожит, а не вводит (ANSWER-1, вопрос 1, как AC-6).

Сценарий сверки фиксации — вариант (а) ANSWER-1: роль во время шага
двигает ссылку мимо автокоммита, следующий старт шага обязан отказать
инцидентом целостности. Сегодня отказа нет на любом штатно завершённом
шаге, не только после выноса (наблюдение при написании планки 03.10).

Группа «разовый»: сценарий двигает ссылку документов настоящим git
(`commit-tree`/`update-ref`) и зовёт закрытый узел сверки перечня —
долгоживущему файлу то и другое запрещено. Сценарии — на настоящем git
(`_sandbox.DocsStepSandbox`/`LockedDocsSandbox`), имена и тексты
случайные, зерно печатается и входит в текст провала.
"""
import contextlib
import hashlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import artifact_branch, store  # noqa: E402
from orchestrator.advance_gates import acceptance as acceptance_gates  # noqa: E402
from scripts import guard  # noqa: E402

from _sandbox import DocsStepSandbox, LockedDocsSandbox, docs_dir  # noqa: E402


class RoleMovesRefPastAutocommitTest(DocsStepSandbox):

    def git_in(self, cwd: Path, *argv: str, env: dict = None,
               data: str = None) -> str:
        res = subprocess.run(["git", *argv], cwd=cwd, capture_output=True,
                             text=True, input=data,
                             env={**os.environ, **(env or {})})
        self.assertEqual(res.returncode, 0, self.note(
            f"git {' '.join(argv)}: {res.stderr}"))
        return res.stdout.strip()

    def test_ac10_role_moving_docs_ref_is_refused_by_fixation_check(self):
        """Роль сама сдвинула ссылку документов — следующий шаг не стартует.

        Сценарий (ANSWER-1, вариант а): задача артели в `tests_writing`,
        в ссылке уже есть SPEC и файл планки; «роль» во время шага из своей рабочей копии кода собирает коммит
        плумбингом git (`hash-object`/`update-index` во временном индексе,
        `commit-tree` поверх головы) и двигает `refs/artifacts/<id>`
        `update-ref` мимо автокоммита — случайно добавляет новый файл
        документов либо переписывает SPEC.md; каталог документов роль не
        трогает. Первый шаг агента запущен; следующий старт шага агента не
        запускает, задача уходит в `escalated`, печать и журнал называют
        инцидент целостности.

        Ловит мутацию: автокоммит шага после выноса перефиксирует ссылку
        (`store.record_fixation`) безусловно, даже когда переносить из
        каталога документов нечего, — подмена ролью становится
        зафиксированным состоянием, второй шаг стартует; сверка на старте
        шага сравнивает каталог документов с деревом ссылки, а не голову
        ссылки с `fixed_sha` — каталог и ссылка совпадают по файлам роли
        (новый файл не выложен, но и не ожидается), шаг стартует."""
        # Планка уже в ссылке: шаг test_author проходит проверку артефакта,
        # роли незачем писать в каталог документов (запись туда сама
        # двигает ссылку автокоммитом и перефиксирует её).
        self.commit_docs({f"acceptance_tests/test_{self.word()}.py":
                          "# планка прошлого шага\n"}, "планка песочницы")
        task_dir = f"tasks/{self.TASK}"
        add_new = self.rnd.random() < 0.5
        rel = (f"{task_dir}/{self.word()}.md" if add_new
               else f"{task_dir}/SPEC.md")
        text = f"подмена роли {self.word()}\n"
        print(f"вариант подмены: {'новый файл' if add_new else 'правка SPEC.md'}")
        ref =artifact_branch.branch_name(self.TASK)
        moved = {}

        def role(cmd, kwargs):
            cwd = Path(kwargs.get("cwd") or self.wt)
            head = self.git_in(cwd, "rev-parse", ref)
            index = Path(tempfile.mkdtemp()) / "index"
            env = {"GIT_INDEX_FILE": str(index)}
            self.git_in(cwd, "read-tree", head, env=env)
            blob = self.git_in(cwd, "hash-object", "-w", "--stdin", data=text)
            self.git_in(cwd, "update-index", "--add", "--cacheinfo",
                        f"100644,{blob},{rel}", env=env)
            tree = self.git_in(cwd, "write-tree", env=env)
            commit = self.git_in(
                cwd, "-c", "user.name=role", "-c", "user.email=role@x.invalid",
                "commit-tree", tree, "-p", head, "-m", "подмена роли")
            self.git_in(cwd, "update-ref", ref, commit, head)
            moved["sha"] = commit

        first = self.run_step(role)

        self.assertTrue(first["calls"], self.note(
            f"первый шаг: агент не запущен: {first['refusal']}\n"
            f"{first['output']}"))
        self.assertTrue(moved.get("sha"), self.note("роль не сдвинула ссылку"))
        second = self.run_step(lambda cmd, kwargs: None)
        state = store.get_task(store.db(), self.TASK)["state"]
        journal = "\n".join(
            f"{r['action']} {r['detail'] or ''}" for r in store.db().execute(
                "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
                (self.TASK,)).fetchall())
        self.assertEqual(second["calls"], [], self.note(
            f"второй шаг стартовал после подмены ссылки ролью "
            f"({'новый файл' if add_new else 'правка SPEC.md'})\n"
            f"{second['output']}"))
        self.assertEqual(state, "escalated", self.note(
            f"задача не остановлена: {state}\n{second['output']}"))
        self.assertIn("инцидент целостности", second["output"], self.note(
            second["output"]))
        self.assertIn("инцидент целостности", journal, self.note(journal))


class RoleRewritesManifestInDocsDirTest(LockedDocsSandbox):

    def test_ac10_manifest_rewritten_in_docs_dir_does_not_pass_check(self):
        """Перечень сумм, переписанный ролью в каталоге документов, не спасает.

        Сценарий: задача после лока в `in_dev`; шаг developer: «роль»
        правит свой долгоживущий файл в рабочей копии кода (пульт
        коммитит его в кодовую ветку) и в каталоге документов
        переписывает `acceptance_tests/long_lived.sha256.txt` суммой
        правленого файла. Контроль: до шага сверка перечня проходит.
        После шага сверка перечня (`_long_lived_manifest_refuses`)
        отказывает и называет путь файла, а переход `in_dev -> verifying`
        задачу не двигает.

        Ловит мутацию: после выноса сверка перечня читает перечень из
        каталога документов или из головы ссылки (куда автокоммит перенёс
        правку роли), а не из дерева коммита лока, — сумма совпадает с
        правленым файлом, отказа нет."""
        wt = self.wt
        conn = store.db()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            refused_before = acceptance_gates._long_lived_manifest_refuses(
                conn, self.TASK)
        self.assertFalse(refused_before, self.note(
            f"фикстура: сверка перечня отказывает до правки\n{buf.getvalue()}"))
        edited = ((wt / self.own).read_text(encoding="utf-8")
                  + f"# правка роли после лока {self.word()}\n")
        digest = hashlib.sha256(edited.encode("utf-8")).hexdigest()

        def role(cmd, kwargs):
            (wt / self.own).write_text(edited, encoding="utf-8")
            manifest = (docs_dir(self.TASK) / "acceptance_tests"
                        / guard.LONG_LIVED_MANIFEST_NAME)
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(f"{digest}  {self.own}\n", encoding="utf-8")

        step = self.run_step(role)

        self.assertTrue(step["calls"], self.note(
            f"агент не запущен: {step['refusal']}\n{step['output']}"))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            refused = acceptance_gates._long_lived_manifest_refuses(
                store.db(), self.TASK)
        self.assertTrue(refused, self.note(
            f"сверка перечня пропустила правку долгоживущего файла при "
            f"перечне, переписанном в каталоге документов\n{step['output']}"))
        self.assertIn(self.own, buf.getvalue(), self.note(buf.getvalue()))
        out = self.advance()
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "in_dev", self.note(out))


if __name__ == "__main__":
    unittest.main()
