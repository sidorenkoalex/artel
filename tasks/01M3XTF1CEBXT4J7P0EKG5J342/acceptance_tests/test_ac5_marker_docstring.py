"""AC-5: докстринг `fsm_advance._mark_artifact_escalation` перечисляет все
пять точек записи признака эскалации по артефакту роли.

Группа: разовый

Красен до реализации: докстринг сегодня называет три точки («Точек вызова
три») и не упоминает `_in_dev_plan_escalate` — правку докстринга вносит
разработчик этой задачи.

Файл разовый: формулировка докстринга закрытой функции — поставка этой
задачи, а не поведение кода; долгоживущий файл не вправе читать закрытые
имена `orchestrator`.
"""
import re
import unittest

from orchestrator import fsm_advance


class MarkerDocstringTest(unittest.TestCase):

    def setUp(self):
        self.doc = fsm_advance._mark_artifact_escalation.__doc__ or ""
        self.flat = re.sub(r"\s+", " ", self.doc)

    def test_ac5_docstring_names_all_five_marker_points(self):
        """Докстринг называет пять точек записи признака и не говорит «три».

        В тексте докстринга — `spec_writing` с батчем `QUESTIONS.md` на
        обоих путях (ветка-источник и диск), `tests_writing` с пометкой
        `AC-n: escalate`, `_review_escalate` и новая точка
        `_in_dev_plan_escalate`; прежней фразы «Точек вызова три» нет.

        Ловит мутацию: в докстринг дописан `_in_dev_plan_escalate`, но
        оставлена фраза «Точек вызова три» — тест найдёт её; либо вызов
        добавлен в код, а докстринг не тронут — нет имени
        `_in_dev_plan_escalate`; либо при переписывании выпала одна из
        прежних точек (дисковый путь `spec_writing`, `_review_escalate`).
        """
        for name in ("spec_writing", "QUESTIONS.md", "tests_writing", "AC-n",
                     "_review_escalate", "_in_dev_plan_escalate"):
            self.assertIn(name, self.flat,
                          f"докстринг не называет точку «{name}»:\n{self.doc}")
        for stem in ("ветк", "диск"):
            self.assertIn(stem, self.flat.lower(),
                          f"докстринг не называет оба пути spec_writing "
                          f"(нет «{stem}»):\n{self.doc}")
        self.assertNotIn("Точек вызова три", self.flat,
                         f"в докстринге осталась прежняя фраза:\n{self.doc}")


if __name__ == "__main__":
    unittest.main()
