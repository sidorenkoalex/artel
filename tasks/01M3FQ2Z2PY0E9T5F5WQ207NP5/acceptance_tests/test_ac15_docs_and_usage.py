"""AC-15 — 01M3FQ2Z2PY0E9T5F5WQ207NP5: документация и текст usage.

Источник — SPEC.md, «Критерии приёмки»:

AC-15. Документация: `docs/stack.md` описывает формат `canary_sets:` и флаг
`--set`; `docs/operator-session.md` несёт правило «канарейка на наборе,
отличном от набора по умолчанию, — по требованию и не считается зелёной
канарейкой для сдвига пина»;
`docs/reference/models-local.example.yaml` несёт образец `canary_sets:` и
по-прежнему совпадает с шаблоном локального слоя по своей сверке; usage
`orchestrator/artel.py` называет `--set`.

Текст usage — модульный докстринг `orchestrator/artel.py` (его и печатает
команда без аргументов), поэтому флаг ищется в строке этого докстринга,
где живёт сама команда `canary --k`, а не где-нибудь в файле.

Правило в `docs/operator-session.md` критерий требует «рядом с пунктом
про пин» — отсюда окно вокруг пункта «Обновление пина после починки», а не
поиск по всему файлу: то же правило, запрятанное в другой раздел, Оператор
в аварийном режиме не прочитает.

Красен до реализации: ни `docs/stack.md`, ни `docs/operator-session.md`,
ни образец локального слоя, ни usage о наборах не говорят.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import artel, models  # noqa: E402

STACK_MD = _util.REPO_ROOT / "docs" / "stack.md"
OPERATOR_SESSION_MD = _util.REPO_ROOT / "docs" / "operator-session.md"
EXAMPLE_YAML = (_util.REPO_ROOT / "docs" / "reference"
                / "models-local.example.yaml")

#: Пункт аварийного раздела, рядом с которым критерий требует правило
#: про набор.
PIN_ITEM = "Обновление пина после починки"

#: Окно строк вокруг пункта про пин, которое считается «рядом».
WINDOW = 8


class DocsAndUsageTest(unittest.TestCase):

    def test_ac15_stack_md_describes_the_sets_format_and_the_flag(self):
        """`docs/stack.md` называет и ключ `canary_sets:`, и флаг `--set`.

        Ловит мутацию: формат набора описан только в SPEC задачи — Оператор,
        заводя набор руками в файле вне git, не имел бы в документации
        пульта ни имени ключа, ни флага, которым набор выбирается.
        """
        text = STACK_MD.read_text(encoding="utf-8")

        self.assertIn("canary_sets", text)
        self.assertIn("--set", text)

    def test_ac15_operator_session_carries_the_rule_next_to_the_pin_item(self):
        """`docs/operator-session.md` рядом с пунктом про пин несёт правило
        о канарейке на наборе, отличном от набора по умолчанию.

        Ловит мутацию: правило дописано в другой раздел (или не дописано
        вовсе) — прогон на Codex-наборе зачлись бы зелёной канарейкой для
        сдвига пина, то есть пин двигался бы по прогону, которым пульт не
        работает.
        """
        lines = OPERATOR_SESSION_MD.read_text(encoding="utf-8").splitlines()
        anchors = [index for index, line in enumerate(lines)
                   if PIN_ITEM in line]
        self.assertTrue(anchors, f"в файле нет пункта «{PIN_ITEM}»")

        window = "\n".join(
            lines[max(0, anchors[0] - WINDOW):anchors[0] + WINDOW + 1]).lower()

        self.assertIn("набор", window)
        self.assertIn("зелён", window)

    def test_ac15_example_local_layer_shows_the_sets_and_still_equals_template(self):
        """Образец локального слоя несёт `canary_sets:` и по-прежнему
        совпадает с текстом шаблона, который кладёт `init`.

        Ловит мутацию: образец дополнен наборами, а шаблон
        `models.LOCAL_TEMPLATE` — нет (или наоборот) — сверка образца с
        шаблоном разошлась бы, и Оператор правил бы по документации файл,
        которого пульт не кладёт.
        """
        example = EXAMPLE_YAML.read_text(encoding="utf-8")

        self.assertIn("canary_sets", example)
        self.assertEqual(models.local_template_text(), example)

    def test_ac15_usage_of_the_canary_command_names_the_set_flag(self):
        """Строка usage команды `canary --k` называет `--set`.

        Ловит мутацию: флаг реализован, но в usage не назван — единственный
        текст, который печатает команда без аргументов, о наборе молчал бы,
        и флаг существовал бы только в SPEC задачи.
        """
        usage_lines = [line for line in (artel.__doc__ or "").splitlines()
                       if "canary --k" in line]
        self.assertTrue(usage_lines, "в usage нет строки команды canary --k")

        self.assertTrue(
            any("--set" in line for line in usage_lines),
            f"строка usage команды canary не называет --set: {usage_lines}")


if __name__ == "__main__":
    unittest.main()
