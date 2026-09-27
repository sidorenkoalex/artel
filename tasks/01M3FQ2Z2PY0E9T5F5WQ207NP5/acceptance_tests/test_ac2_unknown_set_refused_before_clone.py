"""AC-2 — 01M3FQ2Z2PY0E9T5F5WQ207NP5: имя набора, которого нет в
локальном слое, — отказ до эфемерного клона.

Источник — SPEC.md, «Критерии приёмки»:

AC-2. `--set` с именем, которого нет в `canary_sets:` локального слоя, —
отказ с названной причиной и перечнем известных имён, до создания
эфемерного клона (ни одного `git clone`, ни одной строки в `tasks`).

Оба факта «до клона» снимает `_util.CanarySetSandbox.refuse_before_clone`:
`canary.subprocess.run` обёрнут наблюдателем (`git clone` не должен
случиться ни разу), а `tasks` БД пульта обязана остаться пустой.

Красен до реализации: `canary.cmd_canary` не знает ни параметра набора,
ни раздела `canary_sets:` — вызов падает на отсутствующем параметре
подписи, а не на названном отказе по имени набора.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402


class UnknownSetRefusedTest(_util.CanarySetSandbox):

    def test_ac2_unknown_set_name_is_refused_before_any_clone(self):
        """Прогон с именем набора, которого в `canary_sets:` нет: отказ
        называет и само имя, и известные имена наборов, эфемерный клон не
        создаётся, строка задачи не заводится.

        Ловит мутацию: проверка имени набора стоит ПОСЛЕ входа в
        `_ephemeral_clone` (естественный порядок «сначала клон, потом
        собираем его слой») — `git clone` и заведение задачи уже
        случились бы, и Оператор платил бы клоном за опечатку в имени.
        """
        message = self.refuse_before_clone("net-takogo-nabora")

        self.assertIn("net-takogo-nabora", message)
        for known in (_util.SET_NAME, _util.OTHER_SET_NAME):
            self.assertIn(known, message,
                          "отказ не перечислил известные имена наборов")

    def test_ac2_named_refusal_when_the_layer_has_no_sets_section_at_all(self):
        """Локальный слой пульта без раздела `canary_sets:` вовсе: `--set`
        по любому имени — тот же отказ до клона, а не трейсбек разбора.

        Ловит мутацию: наборы читаются как `document["canary_sets"][имя]`
        без ветки «раздела нет» — на слое сегодняшнего пульта (шаблон
        `LOCAL_TEMPLATE` раздела наборов не несёт) Оператор получил бы
        `KeyError`/`TypeError` вместо причины.
        """
        self.write_local_layer(None, self.OVERRIDES)

        message = self.refuse_before_clone(_util.SET_NAME)

        self.assertIn(_util.SET_NAME, message)


if __name__ == "__main__":
    unittest.main()
