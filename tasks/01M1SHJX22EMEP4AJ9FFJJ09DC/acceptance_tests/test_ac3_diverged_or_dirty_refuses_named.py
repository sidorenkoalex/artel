"""AC-3 (tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md): «Живой sha расходится
с зафиксированным, либо копия грязная — approve без sha отклоняется
именованным отказом, называющим оба sha (живой и зафиксированный) и
подсказку перепроверить артефакты; состояние задачи не меняется.»

Настоящий git self/артели (`ApproveSandbox`). Отказ не обязан быть
`sys.exit` конкретно (SPEC не предписывает механизм) — `approve_output_
or_exit_message` в `_sandbox.py` перехватывает оба варианта и сравнивает
наблюдаемый текст, как того требует критерий.

Красен до реализации: сегодня approve без sha на расхождении/грязной
копии печатает «approve требует sha — зафиксирован <fixed>» — там есть
ТОЛЬКО зафиксированный sha, живого (текущего, после подмены) в тексте
нет вовсе, и никакого сравнения не происходит (`if sha is None` — самая
первая ветка, раньше «current != sha»). `test_ac3_diverged_...` падает на
`assertIn(live_sha, out)`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import store  # noqa: E402

from _sandbox import ApproveSandbox  # noqa: E402


class ApproveWithoutShaOnDivergedOrDirtyFixationRefusesTest(ApproveSandbox):

    def test_ac3_diverged_live_sha_is_named_refused_and_state_unchanged(self):
        """Кто-то закоммитил правку `task_dir()` мимо гейта (посторонний
        коммит поверх зафиксированного sha) — approve без sha обязан
        отказать, назвав ОБА значения (живое и зафиксированное), и не
        трогать состояние задачи.

        Ловит мутацию: если реализация после чтения живого значения
        сравнивает его только для решения «пройти/не пройти», но не
        подставляет оба значения в текст отказа (например, использует
        общую фразу без конкретных sha), `assertIn(fixed_sha, out)` или
        `assertIn(live_sha, out)` не найдёт нужную подстроку.
        """
        fixed_sha = self.enter_spec_gate()
        (self.task_dir() / "SPEC.md").write_text(
            "подмена мимо гейта\n", encoding="utf-8")
        self.commit_task_dir("посторонняя правка мимо approve")
        live_sha = self.head()
        self.assertNotEqual(fixed_sha, live_sha,
                            "тест ничего не докажет без реального расхождения")

        out = self.approve_output_or_exit_message()

        self.assertIn(fixed_sha, out, "зафиксированный sha не назван в отказе")
        self.assertIn(live_sha, out, "живой sha не назван в отказе")
        row = store.get_task(store.db(), self.TASK)
        self.assertEqual(row["state"], "spec_gate",
                         "отклонённый approve не двигает состояние")

    def test_ac3_dirty_copy_with_matching_sha_is_named_refused_and_state_unchanged(self):
        """Живой sha (HEAD) совпадает с зафиксированным, но рабочая копия
        грязная (правка есть, коммита нет) — approve без sha обязан
        отказать по грязноте, а не молча пройти, раз sha формально
        совпал.

        Ловит мутацию: сверка, которая проверяет только `current ==
        fixed` и игнорирует `clean`, пропустила бы approve дальше —
        `assertEqual(row["state"], "spec_gate")` поймает случившийся
        переход.
        """
        fixed_sha = self.enter_spec_gate()
        (self.task_dir() / "SPEC.md").write_text(
            "правка без коммита\n", encoding="utf-8")
        # Коммита нет — рабочая копия репозитория фиксации грязная,
        # HEAD (и, значит, «живой» sha из fixation.read) не меняется.
        self.assertEqual(self.head(), fixed_sha,
                         "sha не должен был сдвинуться без коммита")

        out = self.approve_output_or_exit_message()

        self.assertIn("грязн", out, "отказ обязан называть грязную копию")
        row = store.get_task(store.db(), self.TASK)
        self.assertEqual(row["state"], "spec_gate",
                         "отклонённый approve не двигает состояние")


if __name__ == "__main__":
    unittest.main()
