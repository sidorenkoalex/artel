"""Юниты внешних ссылок и вида `board --md` (SPEC
01M5TBFH5VZ7GSRXX7VNKHFCCQ): проверка полей записи проекта
`ref_required`/`ref_systems`, экранирование ячеек таблицы `--md`."""
import unittest

from orchestrator import board, targets


def _entry(**extra) -> dict:
    """Плоская запись проекта с обязательными полями `targets.FIELDS`."""
    entry = {"forge": "github", "url": "https://localhost/team/p",
             "base": "main", "token_slot": "p-token", "no_paths": [],
             "project_skills": [], "merge_gate": "operator"}
    entry.update(extra)
    return entry


class RefPolicyFieldsTest(unittest.TestCase):

    def test_valid_policy_fields_accepted(self):
        """Ловит мутацию: проверка `ref_systems` требует, чтобы
        `ref_required` был в списке, или отвергает непустой список строк —
        годная запись отказывает `TargetsError`."""
        targets.check("p", _entry(ref_required="kaiten",
                                  ref_systems=["kaiten", "gitlab-issue"]))

    def test_empty_ref_required_refused_naming_field(self):
        """Ловит мутацию: `ref_required` не проверяется — пустая система
        принимается, и `new` потом требует ссылку системы ''."""
        for value in ("", "  ", ["kaiten"]):
            with self.assertRaises(targets.TargetsError) as caught:
                targets.check("p", _entry(ref_required=value))
            self.assertIn("ref_required", str(caught.exception))

    def test_ref_systems_with_empty_item_refused_naming_field(self):
        """Ловит мутацию: `ref_systems` проверяется как «список строк» без
        непустоты (или не проверяется) — элемент '' делает пустую систему
        допустимой."""
        for value in (["kaiten", ""], "kaiten", [1]):
            with self.assertRaises(targets.TargetsError) as caught:
                targets.check("p", _entry(ref_systems=value))
            self.assertIn("ref_systems", str(caught.exception))


class BoardMdTest(unittest.TestCase):

    def _model(self, title: str) -> dict:
        return {"project": "p", "generated_at": "2026-01-02 03:04:05Z",
                "pin": None, "columns": ["in_dev"], "epics": [],
                "cards": [{"task": "T1", "title": title, "epic": None,
                           "state": "in_dev", "waiting_on": "role",
                           "budget_usd": 25.0, "spent_usd": 0.0,
                           "refs": [{"system": "kaiten", "key": "7",
                                     "url": None, "by": "operator",
                                     "at": "2026-01-01 00:00:00Z"}]}]}

    def test_pipe_and_newline_in_title_do_not_break_table_row(self):
        """Ловит мутацию: ячейка `--md` пишется как есть — «|» в названии
        добавляет столбец, перевод строки рвёт строку таблицы."""
        text = board.render_md(self._model("а|б\nв"))
        rows = [line for line in text.splitlines() if line.startswith("| T1 ")]
        self.assertEqual(len(rows), 1, text)
        self.assertIn("а\\|б в", rows[0])
        self.assertIn("kaiten:7", rows[0])

    def test_empty_board_says_no_tasks(self):
        """Ловит мутацию: без карточек печатается пустая шапка таблицы
        вместо «Задач нет.»."""
        model = self._model("x")
        model["cards"] = []
        self.assertIn("Задач нет.", board.render_md(model))


if __name__ == "__main__":
    unittest.main()
