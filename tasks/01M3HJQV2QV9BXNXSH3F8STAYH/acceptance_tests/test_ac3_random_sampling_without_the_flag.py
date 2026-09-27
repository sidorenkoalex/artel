"""AC-3 — 01M3HJQV2QV9BXNXSH3F8STAYH: без `--template` выбор шаблонов
прежний, прежние отказы `--k` сохранены.

Источник — SPEC.md, «Критерии приёмки»:

AC-3. Без флага `--template` прогон выбирает `k` шаблонов пула прежней
случайной выборкой (проверяется подменой случайного выбора), а прежние
отказы `--k` (неположительное значение, `--k` больше числа шаблонов пула)
сохранены.

Случайный выбор подменён (`random.sample`): планка сверяет, что он
по-прежнему зовётся, с каким населением и каким `k`, и что прогон ведёт
именно то, что он вернул. Порядок населения не фиксируется — критерий
говорит о случайной выборке, а не о порядке перечисления пула.

Зелёный с рождения: и случайная выборка, и оба отказа `--k` существуют на
сегодняшнем коде — это тест сохранения поведения. Он краснеет ровно тогда,
когда флаг выбора шаблона подменит прежнюю ветку выбора («всегда
разбираем список, пустой список = весь пул») или ослабит существующие
отказы `--k`.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import canary  # noqa: E402


class RandomSamplingWithoutFlagTest(_util.PoolSandbox):

    def test_ac3_without_the_flag_the_pool_is_sampled_randomly(self):
        """Прогон без `--template` зовёт случайную выборку по всем `*.md`
        пула с `k` из флага и ведёт ровно то, что выборка вернула.

        Ловит мутацию: ветка выбора переписана «под флаг» так, что без флага
        берутся первые `k` шаблонов по алфавиту — прогон канарейки перестал
        бы перебирать пул, и один и тот же шаблон проверялся бы прогон за
        прогоном.
        """
        seen = {}

        def fake_sample(population, k):
            seen["titles"] = sorted(Path(p).stem for p in population)
            seen["k"] = k
            return [population[1]]

        with mock.patch.object(canary.random, "sample", fake_sample):
            titles = self.run_titles(["--k", "1", "--sha", self.head])

        self.assertEqual(sorted(_util.POOL_TITLES), seen.get("titles"),
                         "случайная выборка не зовётся или получила не пул")
        self.assertEqual(1, seen.get("k"))
        self.assertEqual(1, len(titles))
        self.assertIn(titles[0], _util.POOL_TITLES)

    def test_ac3_nonpositive_k_is_still_refused(self):
        """`--k 0` — прежний отказ до клона и до origin.

        Ловит мутацию: проверка `k <= 0` снята (или переехала под ветку
        `--template`, где её при пустом флаге никто не исполняет) — прогон с
        нулевым `k` печатал бы «0 задач» и завершался успешно, то есть
        молчаливо ничего не проверял.
        """
        message = self.refuse(["--k", "0"])

        self.assertIn("--k", message)

    def test_ac3_k_greater_than_the_pool_is_still_refused(self):
        """`--k` больше числа шаблонов пула — прежний отказ, называющий
        число доступных шаблонов.

        Ловит мутацию: сверка `k` с размером пула снята вместе с переходом на
        разбор имён — выборка падала бы `ValueError` внутри `random.sample`
        вместо названной причины.
        """
        too_many = len(_util.POOL_TITLES) + 1

        message = self.refuse(["--k", str(too_many)])

        self.assertTrue(_util.mentions_amount(message, len(_util.POOL_TITLES)),
                        f"отказ не назвал число шаблонов пула: {message}")


if __name__ == "__main__":
    unittest.main()
