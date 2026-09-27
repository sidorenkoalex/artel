"""AC-8, AC-9 — 01M3GKJFN90ATK2KECNDZXPPP6: нерезолвимый явный `--sha`
останавливает канарейку до клона; резолвимый короткий доезжает до
`canary_runs.main_sha` полным.

Источник — раздел «Критерии приёмки»:

AC-8. Явный `--sha`, который локально не разрешается, даёт именованный
отказ `canary` — до первого `git clone` и до заведения задачи (ни клона,
ни строки задачи в БД после отказа не появилось).

AC-9. `canary_runs.main_sha` прогона, запущенного с коротким явным
`--sha`, — полный 40-символьный sha.

Оба факта «до клона» AC-8 сняты запретами в самих подменах
(`_util.CanaryShaSandbox.refuse_explicit_sha`): точка эфемерного клона
(`canary._ephemeral_clone`, внутри неё и живёт `git clone`), сам
подпроцесс `git clone` и заведение задачи (`catalog.cmd_new`) поднимают
`AssertionError` — сработавший запрет называет, что именно случилось
раньше отказа. Прогон AC-9 идёт без клона и без живого CLI: фаза 1
(`canary._run_task_in_ephemeral_clone`) подменена фикстурой штатного
исхода, а фазы записи прогона и сверки с бейзлайном — настоящие, ведь
именно они пишут строку `canary_runs`.

Голова главной копии в прогоне AC-9 намеренно ОТЛИЧАЕТСЯ от sha, в
который резолвится короткий `--sha`: иначе «разрешил короткий sha» и
«свалился на `gitcmd.head_sha()`» давали бы в колонке одно и то же
значение и были бы неразличимы.

Красен до реализации: явный `--sha` возвращается как напечатан —
нерезолвимая строка отказа не вызывает (прогон идёт в клон), а короткая
доезжает до `canary_runs.main_sha` короткой.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402


class CanaryExplicitShaRunTest(_util.CanaryShaSandbox):

    def test_ac8_unresolvable_explicit_sha_is_refused_before_any_clone(self):
        """Прогон с `--sha`, которого в локальной базе нет: команда
        останавливается именованным отказом, назвавшим сам sha, — ни
        эфемерного клона, ни `git clone`, ни строки задачи в БД.

        Ловит мутацию: резолв явного sha добавлен, а его неудача
        проглочена (`or explicit_sha` — «не разрешился, возьмём как
        напечатан»): за опечатку в `--sha` Оператор платил бы клоном и
        заведённой канареечной задачей, а причина умирала бы вместе с
        уничтоженным клоном.
        """
        message = self.refuse_explicit_sha(_util.UNKNOWN_SHA)

        self.assertIn(_util.UNKNOWN_SHA, message,
                      "отказ не назвал сам нерезолвимый sha")

    def test_ac9_recorded_main_sha_of_a_short_sha_run_is_the_full_sha(self):
        """Прогон запущен с коротким явным `--sha`: строка `canary_runs`
        несёт в `main_sha` полный 40-символьный sha, а не короткую запись
        и не голову главной копии.

        Ловит мутацию: приведение сделано только для печати отчёта
        (`sha_label`/строка вывода), а в `canary_runs.main_sha` уходит
        по-прежнему исходный аргумент `--sha` — в БД продолжали бы
        появляться короткие строки, слепые к строковому сравнению, ровно
        тот дефект, который ревизия и назвала.
        """
        self.run_canary(_util.SHORT_SHA, head=_util.OTHER_HEAD_SHA)

        rows = self.canary_run_rows()
        self.assertEqual(1, len(rows), "прогон не записал ровно одну строку")
        main_sha = rows[0]["main_sha"]
        self.assertEqual(_util.FULL_SHA, main_sha)
        self.assertEqual(40, len(main_sha))


if __name__ == "__main__":
    unittest.main()
