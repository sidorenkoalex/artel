"""AC-2: исход метода предела `suite-run` одинаков при обоих порядках «старт пробника / первое чтение часов».

Группа: разовый
Зелёный с рождения: метод сегодня ждёт предел по реальным часам — его исход не зависит от того, стартовал ли пробник до первого чтения часов в `Popen.wait` или после, и обрыв делает настоящий `Popen._wait` из `_run_full_suite_to_log`; красной эту планку делает подмена часов, сломанная в одном из порядков (однократный перевод при старте пробника), а независимость от реального времени держат AC-3 и AC-5.

Метод гоняется вложенным pytest; порядок навязывается снаружи прослойкой
под подменой часов теста (`_meta.py`): «до» — настоящий `Popen.wait`
вызывается лишь после старта всех тестов прогона ветки; «после» — тесты
прогона стартуют лишь после первого чтения часов в `Popen.wait`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _meta import run_limit_test  # noqa: E402


class ClockOrderTest(unittest.TestCase):

    def assert_green_cut_by_real_wait(self, run) -> list:
        self.assertEqual(run.outcome, "passed", run.context())
        cuts = run.of("cut_by_real_wait")
        self.assertTrue(cuts, "обрыв прогона ветки сделал не настоящий "
                        "Popen._wait из _run_full_suite_to_log\n"
                        + run.context())
        return cuts

    def test_ac2_probe_started_before_first_clock_read_keeps_outcome(self):
        """Пробник стартовал до первого чтения часов в `Popen.wait` — метод зелёный, обрыв настоящий.

        Сценарий: прослойка под подменой часов теста задерживает вызов
        настоящего `Popen.wait` прогона ветки из `_run_full_suite_to_log`,
        пока не стартуют все тесты прогона (и ещё 0,5 с) — ровно гонка 07.10.
        Метод предела зелёный; `TimeoutExpired` прогона ветки бросил
        настоящий `Popen._wait` (событие `cut_by_real_wait`), и навязанный
        порядок действительно наступил (событие `order` с `forced` для того
        же процесса).

        Ловит мутацию: часы подмены переводятся однократно при старте
        пробника (исходная гонка 07.10) — перевод попадает в само чтение
        `endtime` в `Popen.wait`, срок сдвигается, обрыва нет, метод красен;
        либо обёртка сама бросает `TimeoutExpired`, не вызвав настоящий
        `Popen.wait`, — события `cut_by_real_wait` нет.
        """
        run = run_limit_test("before")
        cuts = self.assert_green_cut_by_real_wait(run)
        forced = {e["pgid"] for e in run.of("order") if e.get("forced")}
        self.assertTrue(forced & {e["pgid"] for e in cuts},
                        "порядок «пробник до первого чтения часов» не "
                        "навязан оборванному прогону\n" + run.context())

    def test_ac2_probe_started_after_first_clock_read_keeps_outcome(self):
        """Пробник стартовал после первого чтения часов в `Popen.wait` — метод зелёный, обрыв настоящий.

        Сценарий: плагин прогона ветки держит старт каждого теста, пока
        настоящий `Popen.wait` прогона из `_run_full_suite_to_log` не прочитал
        часы (вошёл во внутренний `_wait`; потолок 3 с). Метод предела
        зелёный, `TimeoutExpired` прогона ветки бросил настоящий
        `Popen._wait`.

        Ловит мутацию: подмена переводит часы только тогда, когда пробник
        уже стартовал к моменту входа в обёртку (перевод решён один раз на
        входе), — при позднем старте пробника часы стоят, обрыва нет, метод
        красен; либо исход решает обёртка, а не настоящий `Popen.wait`, —
        события `cut_by_real_wait` нет.
        """
        run = run_limit_test("after")
        self.assert_green_cut_by_real_wait(run)

    def test_ac2_unforced_run_is_green_and_cut_by_real_wait(self):
        """Без навязанного порядка метод зелёный, обрыв делает настоящий `Popen.wait`.

        Сценарий: прослойка только записывает события. Метод предела
        зелёный; `TimeoutExpired` прогона ветки бросил настоящий
        `Popen._wait`, вызванный из `proc.wait(timeout=…)` в
        `_run_full_suite_to_log` копии пульта.

        Ловит мутацию: обрыв вынесен из настоящего кода — обёртка над
        `Popen.wait` сама бросает `TimeoutExpired` по своему счёту либо
        подменён `Popen._wait` целиком — события `cut_by_real_wait` нет.
        """
        run = run_limit_test("natural")
        self.assert_green_cut_by_real_wait(run)


if __name__ == "__main__":
    unittest.main()
