"""Контракт записки шага между автокоммитом и брифом (SPEC
01M4RZBPG6EXM74MTBPTEGW2D4, требования 5, 8): деталь записи «записка шага
сохранена» собирается и разбирается одним модулем, таблица допустимых
авторов чужой записки покрывает ровно роли записки.
"""
import hashlib
import random
import unittest

from orchestrator import brief, checkpoint
from scripts import guard


class SavedDetailTest(unittest.TestCase):

    def test_detail_round_trips_role_size_and_sha256(self):
        """Деталь, собранная `step_note_saved_detail`, разбирается
        `parse_step_note_saved` в ту же роль, размер в байтах и sha256.

        Ловит мутацию: сборка и разбор детали разошлись (размер в символах,
        другой разделитель, sha256 не от байтов) — бриф перестаёт находить
        сохранённые записки или сверяет текст не с тем sha256.
        """
        seed = random.randrange(1 << 30)
        rng = random.Random(seed)
        for role in guard.STEP_NOTE_ROLES:
            content = ("ёж " * rng.randrange(1, 50) + str(rng.random())).encode()
            with self.subTest(роль=role, зерно=seed):
                parsed = checkpoint.parse_step_note_saved(
                    checkpoint.step_note_saved_detail(role, content))
                self.assertEqual(parsed, {
                    "role": role, "size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest()})

    def test_detail_of_unknown_role_or_other_form_is_not_parsed(self):
        """Деталь с ролью вне `STEP_NOTE_ROLES`, пустая и произвольного
        вида.

        Ловит мутацию: разбор принимает любую роль — бриф положит записку
        «автора» `operator`, которого перечень записок не знает.
        """
        sha = "0" * 64
        for detail in (f"operator: 10 байт, sha256={sha}", "", None,
                       "developer: записка", f"developer: 10 байт sha256={sha}"):
            with self.subTest(деталь=detail):
                self.assertIsNone(checkpoint.parse_step_note_saved(detail))


class ForeignAuthorsTableTest(unittest.TestCase):

    def test_table_covers_note_roles_and_never_lists_own_role(self):
        """Таблица `brief.STEP_NOTE_FOREIGN_AUTHORS`.

        Наблюдение: ключи — ровно `guard.STEP_NOTE_ROLES`, авторы — из того
        же перечня, своя роль среди допустимых авторов чужой записки не
        стоит.

        Ловит мутацию: роль внесена в собственный список допустимых авторов
        — «чужой» становится её же записка, и чужая в бриф не попадает.
        """
        table = brief.STEP_NOTE_FOREIGN_AUTHORS
        self.assertEqual(set(table), set(guard.STEP_NOTE_ROLES))
        for role, authors in table.items():
            with self.subTest(роль=role):
                self.assertNotIn(role, authors)
                self.assertLessEqual(set(authors), set(guard.STEP_NOTE_ROLES))


if __name__ == "__main__":
    unittest.main()
