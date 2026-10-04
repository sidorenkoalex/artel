"""Юнит-тесты `orchestrator/checkpoint.py::_mandate_covered` (SPEC
01M446WN0V7JW4NSYQFKTBJ05C, требования 1-3) — углы, которые долгоживущий
файл задачи (`tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`)
не покрывает: защищённый путь мандатом коммита пульта не покрывается,
пустой список путей не читает ссылку документов вовсе, а покрытие считается
формулой гейта зон, не правилом вложенности фильтра зон.

Источник мандата подменён на уровне общего узла `zones._answer_zones_mandate`
— его происхождение и разбор проверяют `tests/test_zones_gate.py` и
`tests/test_answer_mandate.py`.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artifact_source, checkpoint, config  # noqa: E402
from orchestrator.advance_gates import zones  # noqa: E402

TASK = "01M0000000000000000000MNZZ"


class MandateCoveredTest(unittest.TestCase):

    def covered(self, mandate: set, paths: list) -> list:
        with mock.patch.object(zones, "_answer_zones_mandate",
                               return_value=set(mandate)) as node:
            result = checkpoint._mandate_covered(TASK, paths)
        self.node = node
        return result

    def test_protected_path_is_not_covered_by_mandate(self):
        """Мандат на каталог, в котором лежит защищённый путь, не делает
        этот путь своим для коммита пульта; соседний незащищённый путь под
        мандатом — свой.

        Ловит мутацию: проверка `config.is_protected_path` убрана —
        мандат Оператора «Расширение зон разрешено: skills/» протаскивает
        правку защищённого пути в коммит пульта, хотя гейт зон отклоняет
        её безусловно."""
        protected = "skills/developer.md"
        self.assertTrue(config.is_protected_path(protected))
        result = self.covered({"skills/", "docs/extra/"},
                              [protected, "docs/extra/note.md"])
        self.assertEqual(result, ["docs/extra/note.md"])

    def test_empty_paths_do_not_read_the_mandate(self):
        """Без путей вне зон общий узел мандата не вызывается — шаг без
        посторонних не платит чтением ссылки документов.

        Ловит мутацию: ранний возврат на пустом `paths` убран — каждый
        коммит пульта читает все ANSWER ссылки документов, а тесты с
        подменённым git получают лишние вызовы."""
        self.assertEqual(self.covered({"docs/extra/"}, []), [])
        self.node.assert_not_called()

    def test_coverage_uses_the_zones_gate_formula(self):
        """Элемент мандата без `/` на конце покрывает путь под ним так же,
        как у гейта зон (`zones._touches_zone`): что гейт признал бы
        покрытым, коммит пульта не снимает.

        Ловит мутацию: покрытие мандатом сверяется правилом вложенности
        фильтра зон `zone_lock._paths_overlap` (каталог — только с `/` на
        конце) — `docs/extra/note.md` под мандатом `docs/extra` снимается
        со стейджа, а гейт зон считает его покрытым."""
        mandate = {"docs/extra"}
        paths = ["docs/extra/note.md", "docs/other.md"]
        result = self.covered(mandate, paths)
        self.assertEqual(result, ["docs/extra/note.md"])
        self.assertEqual(
            result, [p for p in paths if zones._touches_zone(p, sorted(mandate))])

    def test_reads_mandate_from_the_task_docs_ref(self):
        """Общий узел зовётся на ссылке документов задачи — той же ветке,
        что гейт зон получает от `artifact_source.resolve`.

        Ловит мутацию: коммит пульта читает мандат с кодовой ветки задачи —
        ANSWER там нет, мандат всегда пуст."""
        self.covered({"docs/extra/"}, ["docs/extra/note.md"])
        gate_branch, _foreign = artifact_source.resolve(None, TASK)
        self.node.assert_called_once_with(gate_branch, TASK)


if __name__ == "__main__":
    unittest.main()
