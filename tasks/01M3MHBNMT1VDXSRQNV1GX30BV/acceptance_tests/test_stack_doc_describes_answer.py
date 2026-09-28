"""AC-9 — раздел docs/stack.md о канарейке описывает синтетический ответ
на эскалацию, а сторожевые тесты разделов документа остаются зелёными.

Источник — SPEC.md, «Критерии приёмки»:

AC-9. `docs/stack.md` в разделе «### Набор ролей канарейки: `canary_sets:`
и `canary --set`» несёт предложение о синтетическом ответе на эскалацию,
называющее оба смысловых якоря — решение за ролью и запись допущения;
сторожевые тесты разделов документа (`tests/test_stack_codex_section.py`,
`tests/test_stack_parity_table.py`, `tests/test_stack_zones_pull_section.py`)
остаются зелёными.

Красен до реализации: раздел о наборе ролей канарейки сегодня не говорит
об эскалации вовсе (единственные слова об эскалации в документе — в
разделе о подтяжке main), поэтому предложения с обоими якорями там нет.
Второй метод (сторожевые тесты разделов) зелен и до реализации — он
держит существующее свойство документа и обязан остаться зелёным после
правки.

Якоря сверяются по основам слов, а не по угаданной фразе: критерий
требует, чтобы предложение НАЗЫВАЛО решение за ролью и запись допущения,
а не чтобы оно было написано словами автора тестов.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _synthetic_answer  # noqa: E402

STACK_SENTINEL_TESTS = ("tests/test_stack_codex_section.py",
                        "tests/test_stack_parity_table.py",
                        "tests/test_stack_zones_pull_section.py")

# Основы слов якорей AC-9: «решение за ролью» и «запись допущения».
DECISION_STEMS = ("реша", "решен", "решить")
ROLE_STEM = "рол"
ASSUMPTION_STEM = "допущени"


def _sentences_about_escalation(body: str) -> list:
    """Предложения раздела, говорящие об эскалации (основа «эскалац»)."""
    flat = " ".join(body.split())
    sentences = [part.strip() for part in flat.replace("!", ".").split(".")]
    return [s for s in sentences if "эскалац" in s.lower()]


class StackCanarySectionTest(unittest.TestCase):

    def test_ac9_canary_section_describes_the_synthetic_escalation_answer(self):
        """Раздел о наборе ролей канарейки говорит об эскалации и называет
        оба якоря: решение остаётся за ролью, выбранное толкование
        записывается допущением.

        Ловит мутацию: правку кода сдали без предложения в документе (или
        предложение говорит лишь «эскалация закрывается автоматически», не
        называя ни решения за ролью, ни записи допущения) — раздел не
        содержит предложения с обоими якорями, и тест краснеет.
        """
        body = _synthetic_answer.stack_section(
            _synthetic_answer.STACK_CANARY_SET_HEADING)
        sentences = _sentences_about_escalation(body)
        self.assertTrue(sentences,
                        "раздел о наборе ролей канарейки не говорит об "
                        "эскалации вовсе")
        said = " ".join(sentences).lower()
        self.assertTrue(any(stem in said for stem in DECISION_STEMS),
                        f"предложение об эскалации не называет решение за "
                        f"ролью: {sentences}")
        self.assertIn(ROLE_STEM, said,
                      f"предложение об эскалации не называет роль: "
                      f"{sentences}")
        self.assertIn(ASSUMPTION_STEM, said,
                      f"предложение об эскалации не называет запись "
                      f"допущения: {sentences}")

    def test_ac9_stack_section_sentinel_tests_stay_green(self):
        """Сторожевые тесты разделов `docs/stack.md` проходят на документе
        ветки задачи.

        Ловит мутацию: предложение вписали, сломав структуру документа,
        которую сторожа держат (заголовок раздела, таблица паритета,
        порядок разделов) — сторожевые тесты краснеют, и красный код
        возврата прогона виден здесь.
        """
        code, tail = _synthetic_answer.run_pytest(*STACK_SENTINEL_TESTS)
        self.assertEqual(0, code,
                         f"сторожевые тесты разделов docs/stack.md красные:"
                         f"\n{tail}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
