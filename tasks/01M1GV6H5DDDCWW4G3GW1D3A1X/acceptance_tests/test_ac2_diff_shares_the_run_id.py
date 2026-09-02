"""AC-2 (tasks/01M1GV6H5DDDCWW4G3GW1D3A1X/SPEC.md): дифф ревью-пакета
обёрнут собственной парой граничных маркеров с ТЕМ ЖЕ идентификатором
запуска, что и остальные компоненты ревью-пакета этого же запуска.

Красен до реализации: сегодня diff вообще не обёрнут маркерами —
`marker_id_for` бросает `AssertionError` вокруг тела diff'а.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (FakeGitDiff, marker_id_for, standard_files,  # noqa: E402
                      build_review_package)


class Ac2DiffSharesRunIdTest(unittest.TestCase):

    def test_ac2_diff_marker_id_matches_spec_marker_id_of_the_same_package(self):
        """Diff и SPEC одного и того же вызова `review_package` несут
        общий идентификатор границы — та же пара маркеров по природе, что
        обвязывает SPEC/PLAN (AC-1), но применённая отдельно к diff'у
        (SPEC требование 1: «Дифф ревью-пакета получает собственную пару
        границ с тем же идентификатором запуска»).

        Ловит мутацию: diff обвязан своей ОТДЕЛЬНОЙ, отличной от
        остальных компонентов пары идентификации — например если diff
        оборачивается на более раннем этапе сборки, чем остальные части,
        и получает собственный nonce вместо общего.
        """
        diff_body = "diff --git a/x b/x\n+строка-диффа-AC2"
        files = standard_files()
        git = FakeGitDiff(files=files, diff=diff_body)

        package = build_review_package(git)
        text = package["text"]

        self.assertIn(diff_body, text)
        diff_id = marker_id_for(text, diff_body)
        spec_id = marker_id_for(text, "Маркер-тела-SPEC-ревью-пакета.")

        self.assertEqual(
            diff_id, spec_id,
            "diff обязан нести тот же идентификатор запуска, что и "
            "остальные компоненты ревью-пакета этого же вызова")

    def test_ac2_diff_marker_id_is_shared_on_incremental_diff_too(self):
        """Тот же общий идентификатор — и для инкрементального diff'а
        (iteration > 1, prev_sha задан): AC-2 не оговаривает тип diff'а,
        значит требование распространяется на оба (полный и
        инкрементальный).

        `branch`/`prev_sha` — намеренно короче 8 символов: в
        инкрементальном режиме оба легитимно упоминаются ДВАЖДЫ вокруг
        diff'а (заголовок «git diff --stat base...branch» перед ним и
        инструкция «diff выше — инкрементальный... (prev_sha)» после) —
        при длине 8+ они сами становятся ложным «общим кандидатом» для
        `marker_id_for`, независимо от настоящего маркера границы.

        Ловит мутацию: инкрементальный diff обёрнут ОТДЕЛЬНЫМ id, не
        общим с остальными компонентами (например если код границ
        применяется к diff'у до того, как остальной пакет получил тот
        же nonce запуска).
        """
        diff_body = "diff --git a/y b/y\n+строка-инкрементального-диффа"
        files = standard_files(with_prev_review=True)
        git = FakeGitDiff(files=files, diff=diff_body)

        package = build_review_package(git, branch="t/x", iteration=2,
                                       prev_sha="cafe12")
        text = package["text"]

        diff_id = marker_id_for(text, diff_body)
        plan_id = marker_id_for(text, "Маркер-тела-PLAN-ревью-пакета.")

        self.assertEqual(diff_id, plan_id)


if __name__ == "__main__":
    unittest.main()
