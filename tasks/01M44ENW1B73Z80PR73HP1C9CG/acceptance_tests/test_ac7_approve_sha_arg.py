"""AC-7, разбор sha: `orchestrator/artel.py::_approve_sha_arg` не берёт
`--no-answer` за sha.

Группа: разовый

Красен до реализации: `_approve_sha_arg` пропускает только `--accept-red`/`--fixes-main` и их основания — для `[<id>, "--no-answer"]` возвращает «--no-answer» вместо `None`.

Критерий называет закрытую функцию диспетчера прямо, а снаружи её исход
не наблюдаем: в `escalated` sha сверяется с живой фиксацией, которой в
песочнице нет, а вне `escalated` флаг отказывает раньше сверки. Закрытое
имя долгоживущий файл `tests/` трогать не может, поэтому этот угол AC-7
живёт в планке; поведение флага через `artel.main` (отказ вне
`escalated`) держит долгоживущий файл задачи в `tests/`.
"""
import random
import unittest

from orchestrator import artel

FLAG = "--no-answer"


class ApproveShaArgTest(unittest.TestCase):

    def test_ac7_no_answer_flag_is_not_taken_for_sha(self):
        """`approve <id> --no-answer` — sha нет; `approve <id> <sha> --no-answer` — sha равен `<sha>`.

        Id задачи и sha (40 или 7–12 шестнадцатеричных знаков) случайны;
        зерно печатается. Для `[<id>, "--no-answer"]` функция возвращает
        `None`, для `[<id>, <sha>, "--no-answer"]` — `<sha>`.

        Ловит мутацию: флаг не добавлен в пропускаемые — первый случай
        вернёт «--no-answer» как sha; флаг пропускается вместе с соседним
        аргументом слева (перепутан сдвиг индекса) — во втором случае sha
        потеряется и вернётся `None`.
        """
        seed = random.randrange(1 << 32)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        for _ in range(5):
            task = "".join(rng.choice("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
                           for _ in range(26))
            sha = "".join(rng.choice("0123456789abcdef")
                          for _ in range(rng.choice((40, rng.randint(7, 12)))))
            with self.subTest(task=task, sha=sha, зерно=seed):
                self.assertIsNone(artel._approve_sha_arg([task, FLAG]),
                                  f"«{FLAG}» принят за sha (зерно: {seed})")
                self.assertEqual(sha, artel._approve_sha_arg([task, sha, FLAG]),
                                 f"sha потерян при флаге (зерно: {seed})")


if __name__ == "__main__":
    unittest.main()
