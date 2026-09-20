"""AC-5 — 01M2ZZDJ5ECR4ZYV23BKFCNFXM: база инкрементального diff берётся
по якорю вердикта, а не «предпоследней записью журнала».

Источник — SPEC.md, «Критерии приёмки»:

AC-5. Между вердиктом итерации 1 и входом в `review` итерации 2 журнал
задачи несёт лишние записи «sha зафиксирован» (автокоммит артефактов,
чекпоинт, подтяжка main) — базой инкрементального diff выбран `код=`
записи фиксации, следующей за переходом `state -> in_dev` с detail
«замечания ревью, итерация 1», а не предпоследняя запись журнала.

Красен до реализации: `orchestrator/review.py::previous_verdict_sha`
берёт `код=` ПРЕДПОСЛЕДНЕЙ записи «sha зафиксирован» (`entries[-2]`) и
про переход `state -> in_dev` не знает вовсе — при лишних записях
фиксации между итерациями она возвращает sha автокоммита/чекпоинта, а
не sha вердикта.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402
from orchestrator import review  # noqa: E402


class VerdictAnchorIsTheBaseTest(_sandbox.ReviewPackagePlankSandbox):

    def seed_iteration_two_journal(self) -> tuple:
        """Журнал задачи между вердиктом итерации 1 и входом в review
        итерации 2: якорь вердикта + три лишние записи фиксации
        (автокоммит артефактов, чекпоинт, подтяжка main). Возвращает
        (sha вердикта, sha предпоследней записи журнала)."""
        verdict_sha = self.developer_commit(f"{_sandbox.DEV_MARK}-вердикт\n")
        autocommit_sha = self.developer_commit(f"{_sandbox.DEV_MARK}-1\n")
        checkpoint_sha = self.developer_commit(f"{_sandbox.DEV_MARK}-2\n")
        pull_sha = self.developer_commit(f"{_sandbox.DEV_MARK}-3\n")
        self.journal_verdict_anchor(verdict_sha, iteration=1)
        self.journal_noise_fixations(autocommit_sha, checkpoint_sha, pull_sha)
        return verdict_sha, checkpoint_sha

    def test_ac5_base_is_the_fixation_following_the_verdict_transition(self):
        """Якорь — переход `state -> in_dev` с detail «замечания ревью,
        итерация 1»; сразу за ним идёт запись фиксации с `код=<sha
        вердикта>`, дальше — три лишние записи фиксации. База обязана
        быть sha вердикта.

        Ловит мутацию: поиск якоря ведётся по ПЕРВОЙ записи фиксации
        журнала или по записи, предшествующей переходу, а не по
        ближайшей следующей за ним — вернётся чужой sha, и assertEqual
        покраснеет.
        """
        verdict_sha, _ = self.seed_iteration_two_journal()

        base = review.previous_verdict_sha(self.conn, self.TASK)

        self.assertEqual(base, verdict_sha,
                         "база инкремента — `код=` записи фиксации, следующей "
                         "за переходом по вердикту")

    def test_ac5_penultimate_journal_entry_is_not_the_base_anymore(self):
        """Предпоследняя запись «sha зафиксирован» (чекпоинт) базой быть
        перестаёт — именно она возвращалась до задачи.

        Ловит мутацию: `entries[-2]` оставлен как запасной путь (якорь
        ищется, но при любой неудаче поиска код молча падает на прежнюю
        предпоследнюю запись) — база совпадёт с sha чекпоинта, и
        assertNotEqual покраснеет.
        """
        _, penultimate_sha = self.seed_iteration_two_journal()

        base = review.previous_verdict_sha(self.conn, self.TASK)

        self.assertNotEqual(base, penultimate_sha,
                            "«предпоследняя запись журнала» базой быть "
                            "перестаёт")

    def test_ac5_package_of_iteration_two_diffs_from_the_verdict_sha(self):
        """Тот же журнал, но предмет проверки — собранный пакет шага
        ревью итерации 2: диапазон diff обязан начинаться с sha вердикта,
        sha лишних записей фиксации в пакете не появляется.

        Ловит мутацию: правка сделана только в `previous_verdict_sha`, а
        шаг сборки промпта по-прежнему подставляет в пакет другую базу
        (например, считает её сам) — в тексте пакета окажется sha
        чекпоинта, и assertNotIn покраснеет.
        """
        verdict_sha, penultimate_sha = self.seed_iteration_two_journal()

        text = self.build_prompt(reviewed_iter=1)

        self.assertIn(verdict_sha, text,
                      "пакет итерации 2 обязан называть базой sha вердикта")
        self.assertNotIn(penultimate_sha, text,
                         "sha предпоследней записи журнала базой не является")


if __name__ == "__main__":
    unittest.main()
