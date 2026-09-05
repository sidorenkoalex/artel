"""AC-8 (tasks/01M1SAA2AZX3ERQ779QJ5TS9J4/SPEC.md): бриф developer
после `reject` из `verifying` с причиной, называющей упавшие тесты,
несёт имена этих тестов дословно в разделе «Причина возврата» (раздел
передаёт текст `detail` как есть, без произвольного изменения).

Красен до реализации: раздел не собирается — имена тестов из `detail`
нигде не появляются в брифе, `assertIn` падает.
"""
import unittest

from _sandbox import BriefSandbox, DETAIL_REJECT_VERIFYING  # noqa: E402


class Ac8FailedTestNamesVerbatimTest(BriefSandbox):
    """Ловит мутацию: реализация обрезает/пересказывает длинный `detail`
    (например берёт только первое предложение до двоеточия, отбрасывая
    сам список упавших тестов) — конкретные имена
    `test_ac3_foo`/`test_ac9_bar` из фикстуры перестали бы встречаться
    буквально."""

    def test_ac8_developer_brief_carries_failed_test_names_verbatim_from_verifying_reject(self):
        self.seed_state("in_dev", "fsm", "приёмочные тесты готовы")
        self.seed_state("review", "operator", "готово к ревью")
        self.seed_state("verifying", "fsm", "ревью пройдено")
        self.seed_state("in_dev", "operator", DETAIL_REJECT_VERIFYING)

        text = self.build_developer_brief()

        self.assertIn(DETAIL_REJECT_VERIFYING, text)
        self.assertIn("test_ac3_foo", text)
        self.assertIn("test_ac9_bar", text)


if __name__ == "__main__":
    unittest.main()
