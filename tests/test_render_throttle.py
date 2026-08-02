from __future__ import annotations

import unittest

import conftest  # noqa: F401  (adds src/ to sys.path)

from lego_db.presentation.gui.render_throttle import RenderThrottle


class RenderThrottleTests(unittest.TestCase):
    def test_first_call_always_renders(self) -> None:
        throttle = RenderThrottle(min_interval_seconds=1.0)
        self.assertTrue(throttle.should_render(now=0.0, is_final=False))

    def test_final_call_always_renders_even_if_too_soon(self) -> None:
        throttle = RenderThrottle(min_interval_seconds=1.0)
        throttle.mark_rendered(now=0.0)
        self.assertTrue(throttle.should_render(now=0.001, is_final=True))

    def test_skips_renders_that_are_too_soon(self) -> None:
        throttle = RenderThrottle(min_interval_seconds=0.05)
        throttle.mark_rendered(now=10.0)
        self.assertFalse(throttle.should_render(now=10.01, is_final=False))

    def test_renders_again_once_the_interval_has_passed(self) -> None:
        throttle = RenderThrottle(min_interval_seconds=0.05)
        throttle.mark_rendered(now=10.0)
        self.assertTrue(throttle.should_render(now=10.06, is_final=False))

    def test_simulated_large_import_only_renders_a_handful_of_times(self) -> None:
        # 27,000 "rows" arriving over ~0.5 simulated seconds -- this is
        # the whole point of the throttle: render a handful of times,
        # not 27,000 times.
        throttle = RenderThrottle(min_interval_seconds=0.05)
        total = 27_000
        render_count = 0
        for current in range(1, total + 1):
            now = (current / total) * 0.5
            is_final = current >= total
            if throttle.should_render(now=now, is_final=is_final):
                throttle.mark_rendered(now)
                render_count += 1
        # ~0.5s / 0.05s interval -> about 10, plus the guaranteed first
        # and final renders. Comfortably under 50 regardless of rounding.
        self.assertLess(render_count, 50)
        self.assertGreater(render_count, 1)


if __name__ == "__main__":
    unittest.main()
