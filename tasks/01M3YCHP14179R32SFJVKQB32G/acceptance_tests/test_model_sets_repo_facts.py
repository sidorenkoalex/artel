"""Факты кодовой ветки задачи: файл `model_sets.yaml` в корне и раздел
`docs/stack.md` о нём.

Группа: разовый

Красен до реализации: файла `model_sets.yaml` в корне репозитория нет (git ls-files отказывает, чтение падает), в `docs/stack.md` нет раздела о нём и о команде `admit`.

Критерии AC-2…AC-13 покрывает долгоживущий файл
`tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py` (тот же прогон).
Планка провалидирована временным стабом (файл с тремя пустыми разделами
и раздел документа) — оба метода зелёные, стаб удалён.

Корень — каталог кода, из которого импортирован пакет `orchestrator`
(рабочая копия ветки задачи и при прогоне гейта): файлы читаются оттуда,
артефакты задачи не читаются вовсе.
"""
import re
import subprocess
import unittest
from pathlib import Path

from orchestrator import config, yamlmini

CODE_ROOT = Path(config.__file__).resolve().parent.parent
MODEL_SETS_REL = "model_sets.yaml"
SECTIONS = ("sets", "pairs", "canary_templates")

#: Признаки поля счётчика пробных задач в имени ключа (рус./англ.).
COUNTER_KEY = re.compile(r"сч[её]т|count|trial|проб", re.IGNORECASE)


def all_keys(node) -> list:
    if not isinstance(node, dict):
        return []
    keys = []
    for key, value in node.items():
        keys.append(str(key))
        keys += all_keys(value)
    return keys


class ModelSetsFileTest(unittest.TestCase):

    def test_ac1_tracked_file_with_three_sections_without_counter(self):
        """Файл решений Оператора — в git, разбирается `yamlmini`, без счётчика.

        Сценарий: `git ls-files --error-unmatch model_sets.yaml` в корне
        кода; текст файла разбирается `yamlmini.mapping` без ошибки;
        разделы `sets`, `pairs`, `canary_templates` — среди ключей
        верхнего уровня; ни один ключ на любой глубине не похож на поле
        счётчика пробных задач.

        Ловит мутацию: файл заведён, но в `.gitignore`/не добавлен в git
        (ls-files отказывает); раздел назван иначе (`templates:` вместо
        `canary_templates:`) или формат вне подмножества `yamlmini`
        (списки `- …`) — разбор падает или ключа нет; в файл положено
        поле `trial_count:` — ключ найден."""
        res = subprocess.run(
            ["git", "ls-files", "--error-unmatch", MODEL_SETS_REL],
            cwd=CODE_ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        text = (CODE_ROOT / MODEL_SETS_REL).read_text(encoding="utf-8")
        document = yamlmini.mapping(text)
        for section in SECTIONS:
            self.assertIn(section, document, text)
        counters = [k for k in all_keys(document) if COUNTER_KEY.search(k)]
        self.assertEqual(counters, [], text)


class StackDocTest(unittest.TestCase):

    def test_ac14_stack_doc_has_section_on_model_sets_and_admit(self):
        """В `docs/stack.md` есть раздел о файле наборов, допуске и `admit`.

        Сценарий: документ режется на разделы по заголовкам `#`…; раздел
        (вместе с вложенными подразделами до следующего заголовка того же
        или более высокого уровня) обязан назвать `model_sets.yaml`,
        команду `admit`, допуск пары и допуск набора.

        Ловит мутацию: документ не тронут либо упоминает файл одной
        строкой в чужом разделе без команды `admit` и допуска набора —
        ни один раздел не несёт всех признаков."""
        lines = (CODE_ROOT / "docs" / "stack.md").read_text(
            encoding="utf-8").splitlines()
        heads = [(i, len(m.group(1))) for i, line in enumerate(lines)
                 for m in [re.match(r"^(#{1,6})\s", line)] if m]
        found = False
        for pos, (start, level) in enumerate(heads):
            end = next((i for i, lvl in heads[pos + 1:] if lvl <= level),
                       len(lines))
            body = "\n".join(lines[start:end]).lower()
            if ("model_sets.yaml" in body and "admit" in body
                    and "допуск" in body and "пар" in body
                    and "набор" in body):
                found = True
                break
        self.assertTrue(found, "нет раздела о model_sets.yaml, допуске "
                               "пары и набора и команде admit")


if __name__ == "__main__":
    unittest.main()
