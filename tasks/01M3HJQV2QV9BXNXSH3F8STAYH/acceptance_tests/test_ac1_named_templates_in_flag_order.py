"""AC-1 — 01M3HJQV2QV9BXNXSH3F8STAYH: `--template` берёт из пула названные
шаблоны в порядке флага, без случайной выборки.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. `canary --k <N> --template <имя-1>,…,<имя-N>` с именами шаблонов
пула прогоняет ровно эти шаблоны в порядке их перечисления во флаге,
без случайной выборки; имя даётся без расширения `.md`.

Наблюдение снимается на границе «выбор шаблонов -> полный цикл задачи»:
`canary._run_one_task` подменён записью своего первого аргумента
(`_util.PoolSandbox.run_templates`), поэтому виден и состав, и ПОРЯДОК
выбранного, а ни одного эфемерного клона и ни одного шага роли не
возникает. Флаг разбирается настоящим CLI (`artel._cmd_canary`) — имя
параметра, которым выбор доезжает до `canary.cmd_canary`, планка не
угадывает.

«Без случайной выборки» проверяется запретом: `random.sample` на время
прогона заменён функцией, падающей при любом вызове.

Красен до реализации: флага `--template` команда не знает и лишние
аргументы не разбирает — флаг молча игнорируется, и прогон берёт случайные
шаблоны пула (`canary._sample_pool_templates`, `random.sample`), то есть
запрет случайной выборки срабатывает на первом же вызове.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import canary  # noqa: E402


def _forbidden_sample(population, k):
    raise AssertionError(
        "случайная выборка пула вызвана при явном --template")


class NamedTemplatesTest(_util.PoolSandbox):

    def test_ac1_named_templates_run_in_flag_order_without_random_sampling(self):
        """Прогон `--k 2 --template plank-gamma,plank-alpha` ведёт ровно два
        названных шаблона и именно в этом порядке; `random.sample` при этом
        не зовётся ни разу.

        Ловит мутацию: имена разобраны, но выбор всё равно идёт через
        `random.sample` по отфильтрованному списку (или список приводится к
        `sorted`/`set` «для порядка») — прогон шёл бы алфавитным порядком
        пула вместо порядка флага, и воспроизвести сценарий пула командой
        по-прежнему было бы нельзя.
        """
        with mock.patch.object(canary.random, "sample", _forbidden_sample):
            titles = self.run_titles(
                ["--k", "2", "--template", "plank-gamma,plank-alpha",
                 "--sha", self.head])

        self.assertEqual(["plank-gamma", "plank-alpha"], titles)

    def test_ac1_name_without_extension_resolves_to_the_pool_md_file(self):
        """Имя во флаге даётся без расширения: прогон получает файл
        `<имя>.md` именно того каталога пула.

        Ловит мутацию: имя склеивается с каталогом как есть (`pool_dir /
        имя`) — `_run_one_task` получил бы несуществующий путь без
        расширения, и первое же чтение шаблона упало бы внутри эфемерного
        клона, где причина умирает вместе с клоном.
        """
        paths, _out = self.run_templates(
            ["--k", "1", "--template", "plank-beta", "--sha", self.head])

        self.assertEqual([self.pool_dir / "plank-beta.md"], paths)

    def test_ac1_all_pool_names_are_selectable_by_the_flag(self):
        """Каждое из трёх стабильных имён пула выбирается флагом, и при
        `--k 3` прогон ведёт все три в перечисленном порядке.

        Ловит мутацию: разбирается только первое имя списка (`split(",")[0]`
        либо `--template` трактуется как одно значение) — `--k 3` с тремя
        именами повёл бы одну задачу вместо трёх, а число имён по требованию
        обязано равняться `--k`.
        """
        order = ["plank-gamma", "plank-beta", "plank-alpha"]

        titles = self.run_titles(
            ["--k", "3", "--template", ",".join(order), "--sha", self.head])

        self.assertEqual(order, titles)


if __name__ == "__main__":
    unittest.main()
