"""AC-2 — 01M3HJQV2QV9BXNXSH3F8STAYH: четыре случая битого `--template` —
именованный отказ до клона, до origin и до заведения задачи.

Источник — SPEC.md, «Критерии приёмки»:

AC-2. Каждый из случаев — неизвестное имя шаблона, число имён не равно
`--k`, повтор имени в списке, `--template` без значения — даёт именованный
отказ команды с ненулевым кодом возврата, при котором не создан эфемерный
клон, не заведена задача и не было обращения к origin; в отказе по
неизвестному имени перечислены доступные имена шаблонов пула. Отсутствие
`--k` по-прежнему отказ.

Три факта «до прогона» снимает `_util.PoolSandbox.refuse`:
`canary.subprocess.run` обёрнут наблюдателем (`git clone` не должен
случиться ни разу), `canary.gitcmd.fetch_ref_sha` — наблюдателем обращений
к origin (флаг `--sha` в этих вызовах сознательно не передаётся, иначе
origin не спрашивался бы и без отказа), а `tasks` БД пульта обязана
остаться пустой.

Красен до реализации: флага `--template` команда не знает вовсе и лишние
аргументы не разбирает — он молча игнорируется, ни одной из четырёх проверок
не существует, и вместо отказа прогон идёт дальше и заводит задачу (на этом
и падает наблюдатель `catalog.cmd_new`). Отказ на отсутствующем `--k`
существует сегодня и обязан сохраниться.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402


class TemplateRefusalsTest(_util.PoolSandbox):

    def test_ac2_unknown_template_name_is_refused_and_lists_the_pool(self):
        """Имя, которого в пуле нет: отказ называет само имя и перечисляет
        все доступные имена шаблонов пула, клона и задачи не возникает.

        Ловит мутацию: неизвестное имя просто пропускается (или проверка
        стоит после входа в эфемерный клон) — Оператор платил бы за опечатку
        клоном и заведённой задачей, а из отказа не узнал бы, какие имена
        вообще есть в пуле.
        """
        message = self.refuse(["--k", "1", "--template", "net-takogo-shablona"])

        self.assertIn("net-takogo-shablona", message)
        for title in _util.POOL_TITLES:
            self.assertIn(title, message,
                          "отказ не перечислил доступные имена шаблонов пула")

    def test_ac2_count_of_names_not_equal_to_k_is_refused(self):
        """Число имён, не равное `--k`, — отказ, называющий флаг; и когда
        имён меньше `--k`, и когда больше.

        Ловит мутацию: список имён молча обрезается до `k` (или `k`
        переопределяется длиной списка) — команда вела бы не то число задач,
        которое Оператор назвал `--k`, и существующий смысл «сколько задач
        ведёт прогон» раздвоился бы.
        """
        fewer = self.refuse(["--k", "2", "--template", "plank-alpha"])
        more = self.refuse(
            ["--k", "1", "--template", "plank-alpha,plank-beta"])

        for message in (fewer, more):
            self.assertIn("--template", message)

    def test_ac2_repeated_name_in_the_list_is_refused(self):
        """Повтор имени в списке — отказ, называющий повторённое имя.

        Ловит мутацию: повтор разрешён (список не проверяется на
        уникальность) — прогон вёл бы один и тот же шаблон дважды, обе задачи
        писали бы бейзлайн одного шаблона в одном прогоне, и вторая строка
        перезаписывала бы первую.
        """
        message = self.refuse(
            ["--k", "2", "--template", "plank-alpha,plank-alpha"])

        self.assertIn("plank-alpha", message)

    def test_ac2_template_flag_without_a_value_is_refused(self):
        """`--template` последним аргументом, без значения, — именованный
        отказ, а не трейсбек разбора.

        Ловит мутацию: значение берётся `rest[idx + 1]` без проверки границы
        — Оператор получил бы `IndexError` вместо причины, а команда уже
        числилась бы запущенной.
        """
        message = self.refuse(["--k", "1", "--template"])

        self.assertIn("--template", message)

    def test_ac2_missing_k_is_still_refused(self):
        """`--template` без `--k` — прежний отказ «нужен параметр --k».

        Ловит мутацию: `--k` выведен из числа имён `--template` и потому
        перестал быть обязательным — прежний отказ ослаблен, а требование 2
        прямо его сохраняет.
        """
        message = self.refuse(["--template", "plank-alpha"])

        self.assertIn("--k", message)


if __name__ == "__main__":
    unittest.main()
