"""Углы команды `docs` (SPEC 01M41VTSE5N15P5P2WZF4GF2BQ), не покрытые
долгоживущими файлами задачи: недоступный `origin` при локальной ссылке,
уборка приватных ссылок подтягивания, отсутствующий файл документов.
Песочница — `DocsSandbox` долгоживущего файла задачи (настоящий git).
"""
import unittest

from orchestrator import artifact_branch
from tests.test_01m41vtse5n15p5p2wzf4gf2bq_docs_command import (
    REF_PREFIX, DocsSandbox)


class DocsEdgesTest(DocsSandbox):

    def test_unreachable_origin_reads_local_ref(self):
        """`origin` недоступен, локальная ссылка есть: файл печатается из неё
        с предупреждением, код 0.

        Ловит мутацию: исход `FETCH_FAILED` в `docs_fetch._docs` трактуется
        как отказ (`sys.exit`) при живой локальной ссылке — код ненулевой,
        файла в выводе нет.
        """
        tid = self.task_id()
        self.add_task(tid)
        body = self.text("локально")
        self.place_ref(self.root, tid, self.commit_docs(tid, {"SPEC.md": body}))
        self.git("remote", "set-url", "origin", str(self.scratch / "нет-такого"))

        code, out = self.run_cli("docs", tid, "SPEC.md")

        self.assertEqual(code, 0, self.why(f"код {code}: {out}"))
        self.assertIn(body.strip(), out, self.why("локальный файл не напечатан"))
        self.assertIn("не подтянута", out, self.why("нет предупреждения"))

    def test_fetch_leaves_no_private_refs(self):
        """После `docs <id>` и `docs --fetch-all` под `refs/artel/docs-fetch/`
        не остаётся ни одной ссылки.

        Ловит мутацию: убран вызов `artifact_branch._drop_fetch_refs` в
        `fetch_from_origin` или `fetch_all_from_origin` — приватные ссылки
        копятся в репозитории.
        """
        tid = self.task_id()
        self.add_task(tid)
        self.place_ref(self.bare, tid,
                       self.commit_docs(tid, {"SPEC.md": self.text("с")}))

        for argv in (("docs", tid), ("docs", "--fetch-all")):
            code, out = self.run_cli(*argv)
            self.assertEqual(code, 0, self.why(f"{argv}: код {code}: {out}"))
            left = self.git("for-each-ref", "--format=%(refname)",
                            artifact_branch._FETCH_NS + "/").strip()
            self.assertEqual(left, "", self.why(f"{argv}: остались {left}"))
        self.assertTrue(self.ref_sha(self.root, tid))

    def test_missing_file_named_refusal(self):
        """Файла нет в голове ссылки: ненулевой код, отказ называет файл.

        Ловит мутацию: `text is None` из `artifact_branch.show` печатается
        как пустой файл с кодом 0.
        """
        tid = self.task_id()
        self.add_task(tid)
        self.place_ref(self.bare, tid,
                       self.commit_docs(tid, {"SPEC.md": self.text("с")}))

        code, out = self.run_cli("docs", tid, "PLAN.md")

        self.assertNotEqual(code, 0, self.why(f"код 0: {out!r}"))
        self.assertIn("PLAN.md", out, self.why("отказ не называет файл"))
        self.assertEqual(self.ref_sha(self.root, tid),
                         self.git("ls-remote", str(self.bare),
                                  REF_PREFIX + tid).split()[0],
                         self.why("ссылка не подтянута"))


if __name__ == "__main__":
    unittest.main()
