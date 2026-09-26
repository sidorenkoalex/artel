"""AC-1, AC-2 задачи 01M3FQ3JVC3DGGM33XCX8TC7ME — узел разбора вывода
pytest в `orchestrator/acceptance.py`.

Узел ищется поведением, а не по имени (имени ни один критерий не
называет) — см. докстринг `_fixtures.find_parse_node`.

Красен до реализации: узла разбора вывода pytest в
orchestrator/acceptance.py ещё нет — ни одна функция модуля не отдаёт по
тексту прогона итоговую строку вместе с именами упавших тестов, поиск
кандидата возвращает None.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import (FAILED_NODEIDS, HEAD_MARKER, NO_PARSE_NODE_HINT,  # noqa: E402
                       SUMMARY_LINE, TAIL_MARKER, call_with_output,
                       digest_text, find_parse_node, huge_red_output,
                       output_without_summary_and_failed, red_output)
from orchestrator import config  # noqa: E402


class ParseNodeTest(unittest.TestCase):

    def node(self):
        node, digest = find_parse_node()
        self.assertIsNotNone(node, NO_PARSE_NODE_HINT)
        return node, digest

    def test_ac1_parse_node_names_summary_line_and_failed_tests(self):
        """Вывод красного прогона полного набора (строки `FAILED
        <nodeid>` блока «short test summary info» и итоговая строка
        pytest) отдаётся узлом разбора так, что выжимка несёт И итоговую
        строку, И оба имени упавших тестов — не только признак красноты.

        Ловит мутацию: узел разбирает только итоговую строку (регулярка
        `amend._RUN_SUMMARY` вынесена как есть, без сбора строк `FAILED`)
        — выжимка назовёт «2 failed, 305 passed …», но ни одного имени
        упавшего теста, и поиск кандидата не найдёт узел вовсе.
        """
        node, digest = self.node()

        self.assertIn(SUMMARY_LINE, digest,
                      f"{node.__name__} потерял итоговую строку pytest")
        for nodeid in FAILED_NODEIDS:
            self.assertIn(nodeid, digest,
                          f"{node.__name__} не назвал упавший тест {nodeid}")

    def test_ac1_parse_node_falls_back_to_output_tail(self):
        """Вывод, в котором НЕТ ни итоговой строки pytest, ни строк
        `FAILED <nodeid>` (сбор оборвался на conftest), разбирается тем же
        узлом в хвост вывода — диагностика не теряется совсем.

        Ловит мутацию: ветка «ни итога, ни упавших» возвращает пустую
        строку/None вместо хвоста — маркер последней строки вывода в
        выжимке не появится.
        """
        node, _digest = self.node()
        text = output_without_summary_and_failed()

        digest = digest_text(call_with_output(node, text))

        self.assertIn(TAIL_MARKER, digest,
                      f"{node.__name__} на выводе без итоговой строки и без "
                      f"FAILED обязан отдать хвост вывода, отдал {digest!r}")

    def test_ac2_digest_is_bounded_by_log_tail_config(self):
        """Выжимка узла разбора на выводе с 200 строками `FAILED` и
        длинными именами тестов ограничена теми же константами, что
        выжимка логов ролей: `config.LOG_TAIL_LINES` строк и
        `config.LOG_TAIL_CHARS` символов (предпосылки читаются от config,
        не литералами — потолки поворачивает Оператор).

        Ловит мутацию: ограничение применено только по символам (срез
        `[-LOG_TAIL_CHARS:]` без обрезки по строкам) либо только по
        строкам — выжимка из двухсот имён упавших тестов пролезет в
        журнал целиком и утопит в себе причину.
        """
        node, _digest = self.node()

        digest = digest_text(call_with_output(node, huge_red_output()))

        self.assertLessEqual(
            len(digest.splitlines()), config.LOG_TAIL_LINES,
            f"выжимка {node.__name__} длиннее config.LOG_TAIL_LINES="
            f"{config.LOG_TAIL_LINES} строк")
        self.assertLessEqual(
            len(digest), config.LOG_TAIL_CHARS,
            f"выжимка {node.__name__} длиннее config.LOG_TAIL_CHARS="
            f"{config.LOG_TAIL_CHARS} символов")

    def test_ac2_digest_of_short_red_output_is_bounded_too(self):
        """Та же граница объёма — на обычном красном прогоне с двумя
        упавшими тестами: выжимка не имеет права тащить в журнал тело
        вывода (заголовок сессии, шестьдесят строк прогресса, traceback).

        Ловит мутацию: узел отдаёт срез всего вывода (`tail[-2000:]`,
        как сегодня делает `run_full_suite`) вместо выжимки — маркер
        начала вывода окажется в выжимке, а её объём превысит
        `config.LOG_TAIL_LINES`.
        """
        node, digest = self.node()

        self.assertNotIn(
            HEAD_MARKER, digest,
            f"выжимка {node.__name__} тащит заголовок сессии pytest — это "
            f"весь вывод, не выжимка")
        self.assertLessEqual(len(digest.splitlines()), config.LOG_TAIL_LINES)
        self.assertLessEqual(len(digest), config.LOG_TAIL_CHARS)


class ParseNodeIsSingleTest(unittest.TestCase):

    def test_ac1_the_same_node_serves_both_shapes_of_output(self):
        """Оба исхода разбора (есть итоговая строка и имена упавших /
        нет ни того, ни другого) обслуживает ОДИН узел: тот самый, что
        нашёлся на красном выводе, отвечает и на вывод без итога.

        Ловит мутацию: разбор разъехался на две независимые функции —
        одна знает итоговую строку, другая хвост, — и узел, нашедшийся
        по красному выводу, на выводе без итога отдаёт пустоту.
        """
        node, _ = find_parse_node()
        self.assertIsNotNone(node, NO_PARSE_NODE_HINT)

        red_digest = digest_text(call_with_output(node, red_output()))
        fallback_digest = digest_text(
            call_with_output(node, output_without_summary_and_failed()))

        self.assertIn(SUMMARY_LINE, red_digest)
        self.assertIn(TAIL_MARKER, fallback_digest)


if __name__ == "__main__":
    unittest.main()
