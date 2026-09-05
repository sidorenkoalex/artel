"""AC-1 (tasks/01M1P9RJVYHTAC087J4B2CAR44/SPEC.md): `review.
previous_verdict_sha` возвращает sha КОДОВОЙ ВЕТКИ задачи (поле `код=`
записи «sha зафиксирован»), не фиксационный sha артефактного репозитория
target'а (поле `sha=` той же записи), когда в журнале есть ≥2 такие
записи с распознанным sha кодовой ветки.

Красен до реализации: `previous_verdict_sha` (orchestrator/review.py)
сегодня разбирает запись регулярным выражением `sha=([0-9a-f]{4,40})` —
оно находит ПЕРВОЕ вхождение литерала `sha=` в строке `detail`, то есть
поле `sha=` (фиксационный sha артефактного репозитория, требование 1
SPEC его явно называет НЕПРАВИЛЬНОЙ базой), а не `код=` дальше по той же
строке. Тест ниже подставляет заведомо РАЗНЫЕ значения в оба поля —
функция обязана вернуть значение `код=`, а не `sha=`.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import review, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

TASK = "T001"

# Три РАЗЛИЧНЫХ пары (sha=, код=) — по одной на каждый из трёх переходов
# FSM журнала (T021, докстринг `previous_verdict_sha`). Оба поля —
# синтаксически валидный 40-символьный hex, каждое значение уникально,
# чтобы результат функции однозначно указывал, ИЗ КАКОГО поля он взят.
FIXATION_REPO_SHAS = ["1" * 40, "2" * 40, "3" * 40]  # `sha=` — фиксационный
CODE_BRANCH_SHAS = ["a" * 40, "b" * 40, "c" * 40]    # `код=` — кодовой ветки


class PreviousVerdictShaUsesCodeBranchShaTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()

    def fixate(self, fixation_sha: str, code_sha: str) -> None:
        store.journal(
            self.conn, TASK, "fsm", "sha зафиксирован",
            f"target=sled, sha={fixation_sha}, чисто=True, "
            f"код={code_sha}, артефакты={'e' * 40}")

    def test_ac1_returns_code_branch_sha_not_fixation_repo_sha(self):
        """Три перехода FSM (T021, докстринг `previous_verdict_sha`):
        entry[-2] («review -> in_dev», вердикт итерации 1) — искомая
        база инкрементального diff итерации 2.

        Ловит мутацию: `previous_verdict_sha` продолжает искать поле
        `sha=` (текущий регресс) вместо `код=` — вернёт второй элемент
        FIXATION_REPO_SHAS вместо второго элемента CODE_BRANCH_SHAS.
        """
        self.fixate(FIXATION_REPO_SHAS[0], CODE_BRANCH_SHAS[0])  # in_dev->review, итерация 1
        self.fixate(FIXATION_REPO_SHAS[1], CODE_BRANCH_SHAS[1])  # review->in_dev, вердикт итерации 1
        self.fixate(FIXATION_REPO_SHAS[2], CODE_BRANCH_SHAS[2])  # in_dev->review, итерация 2 (текущий)

        result = review.previous_verdict_sha(self.conn, TASK)

        self.assertEqual(result, CODE_BRANCH_SHAS[1])
        self.assertNotEqual(result, FIXATION_REPO_SHAS[1],
                            "вернулся фиксационный sha артефактного "
                            "репозитория target'а вместо sha кодовой ветки")


if __name__ == "__main__":
    unittest.main()
