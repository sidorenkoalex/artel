"""Заголовок MR по `policy.mr_title_template` без `{ref}`: ссылки задачи не
читаются (SPEC 01M6RJDRR027G50D81W8T3T8AK, требование 3)."""
import unittest
from unittest import mock

from orchestrator import github_adapter, store


class MrTitleWithoutRefTest(unittest.TestCase):

    def title(self, entry: dict, task_title: str) -> tuple:
        with mock.patch.object(store, "external_refs",
                               side_effect=AssertionError("ссылки прочитаны")) as refs, \
                mock.patch.object(store, "journal") as journal:
            title = github_adapter._mr_title(
                None, "01ABC", {"title": task_title}, entry)
        return title, refs.call_count, journal.call_count

    def test_default_template_does_not_read_refs(self):
        """Запись без шаблона (и с `ref_required`) — заголовок `<id>: <название>`, к ссылкам задачи обращения нет, журнал не пишется.

        Ловит мутацию: ссылки читаются безусловно (до проверки `{ref}` в
        шаблоне) — подменённый `store.external_refs` бросает исключение.
        """
        title, refs, journal = self.title({"ref_required": "tracker"}, "Правка")
        self.assertEqual(title, "01ABC: Правка")
        self.assertEqual((refs, journal), (0, 0))

    def test_template_without_ref_does_not_read_refs(self):
        """Шаблон `[{id}] {title}` без `{ref}` — заголовок по шаблону, ссылки не читаются, `{ref}` в названии остаётся буквальным.

        Ловит мутацию: ссылки читаются при шаблоне без `{ref}`; `{title}`
        подставлен раньше `{ref}`/`{id}` — `{id}` из названия раскрылся.
        """
        title, refs, journal = self.title(
            {"ref_required": "tracker", "mr_title_template": "[{id}] {title}"},
            "Про {id} и {ref}")
        self.assertEqual(title, "[01ABC] Про {id} и {ref}")
        self.assertEqual((refs, journal), (0, 0))


if __name__ == "__main__":
    unittest.main()
