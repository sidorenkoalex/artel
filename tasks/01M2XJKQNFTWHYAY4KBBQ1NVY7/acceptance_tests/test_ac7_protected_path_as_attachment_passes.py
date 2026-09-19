"""AC-7: защищённый путь, названный «Приложением:» и не названный в
«Зоны:», отказа `new` не вызывает.

Зелёный с рождения: сегодня `catalog.cmd_new` не сверяет пути ТЗ вовсе и заводит задачу при любом тексте — сценарий проверяет ОТСУТСТВИЕ отказа и покраснеет ровно тогда, когда новая сверка защищённых путей начнёт смотреть не в тот раздел.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from _new_sandbox import NewWithTzSandbox  # noqa: E402


class ProtectedPathAsAttachmentTest(NewWithTzSandbox):

    def test_ac7_protected_path_named_only_as_attachment_passes(self):
        """Тот же защищённый путь, что в AC-6 отказывает из «Зоны:»,
        назван в разделе «Приложением:» и в «Зоны:» отсутствует —
        `new --tz` проходит и заводит задачу.

        Ловит мутацию: проверка `PROTECTED_PATHS` применяется ко ВСЕМ
        собранным путям ТЗ, а не только к содержимому раздела «Зоны:»
        (требование 4) — приложение-диф стало бы невозможно объявить, и
        `new` отказал бы здесь.
        """
        text = self.run_new(_util.tz_text(
            requires="Поправить формат разделов.",
            zones=_util.ZONE_PATH,
            attachment=f"{_util.PROTECTED_FILE} — unified-диф к PLAN.md."))

        self.assertNotIn(_util.PROTECTED_REFUSAL_TEXT, text,
                         f"new отказал на приложении:\n{text}")
        _util.assert_no_unclassified_refusal(self, text)
        self.assert_task_created(text)


if __name__ == "__main__":
    unittest.main()
