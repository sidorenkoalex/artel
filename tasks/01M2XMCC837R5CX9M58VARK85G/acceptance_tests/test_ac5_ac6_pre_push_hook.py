"""AC-5, AC-6: `pre-push` во временном репозитории с включёнными хуками —
отказ push'у в `refs/heads/main` без маркера, проход с маркером, и полная
прозрачность хука для `task/*`, `artifact/*` и `refs/artifacts/*`.

Красен до реализации: файла `scripts/git-hooks/pre-push` ещё нет — песочница падает на его копировании.
"""
import unittest

from _hooks import REFUSAL_CORE, HookedRepoTest, output, squeeze


class PrePushHookTest(HookedRepoTest):

    def setUp(self):
        super().setUp()
        self.origin = self.add_origin()

    def remote_ref(self, ref: str) -> str:
        """sha `ref` в bare-`origin`; пустая строка — такого ref там нет."""
        out = self.git_ok("ls-remote", "origin", ref, marker=True)
        return out.split()[0] if out.strip() else ""

    def test_ac5_push_to_refs_heads_main_is_refused_without_the_marker(self):
        """`git push origin <sha>:refs/heads/main` без маркера отказывает
        ненулевым кодом с именованным текстом требования 2 и ничего не
        публикует; тот же push с `ARTEL_PULT_GIT=1` проходит и создаёт
        main в origin.

        Ловит мутацию: хук читает не целевой (удалённый) ref из пары на
        stdin, а локальный — при push вида `<sha>:refs/heads/main`
        локальная сторона это голый sha, имени `refs/heads/main` в ней
        нет, и отказ бы не сработал: первая проверка ниже (ненулевой код)
        покраснела бы.
        """
        sha = self.head()

        refused = self.push(f"{sha}:refs/heads/main", marker=False)

        self.assertNotEqual(refused.returncode, 0,
                            "push в main без маркера прошёл")
        self.assertIn(squeeze(REFUSAL_CORE), output(refused))
        self.assertEqual(self.remote_ref("refs/heads/main"), "",
                         "отказанный push всё-таки опубликовал main")

        allowed = self.push(f"{sha}:refs/heads/main", marker=True)

        self.assertEqual(allowed.returncode, 0, output(allowed))
        self.assertEqual(self.remote_ref("refs/heads/main"), sha)

    def test_ac6_task_artifact_and_artifact_refs_pushes_pass_without_marker(self):
        """Push ветки `task/x`, ветки `artifact/x` и ссылки
        `refs/artifacts/<id>` без маркера проходит: хук сторожит только
        main главной копии, обычный трафик веток задач и артефактов ему
        не подведомственен.

        Ловит мутацию: хук отказывает по подстроке `main` в любом ref
        (например `case "$remote_ref" in *main*`) или вовсе любому push
        без маркера — тогда публикация ветки задачи и артефактной ветки
        (`artifact_branch.push`, draft-MR разработчика) перестала бы
        работать и проверки ниже покраснели бы.
        """
        sha = self.head()
        self.git_ok("branch", "task/x")
        self.git_ok("branch", "artifact/x")

        for refspec, published in (("task/x", "refs/heads/task/x"),
                                   ("artifact/x", "refs/heads/artifact/x"),
                                   (f"{sha}:refs/artifacts/01ABC",
                                    "refs/artifacts/01ABC")):
            with self.subTest(refspec=refspec):
                res = self.push(refspec, marker=False)
                self.assertEqual(res.returncode, 0, output(res))
                self.assertEqual(self.remote_ref(published), sha)


if __name__ == "__main__":
    unittest.main()
