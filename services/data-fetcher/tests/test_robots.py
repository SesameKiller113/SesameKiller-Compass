from __future__ import annotations

import unittest

from data_fetcher.robots import is_path_allowed_by_robots, parse_robots_txt


class RobotsTest(unittest.TestCase):
    def test_parse_user_agent_groups(self) -> None:
        groups = parse_robots_txt("User-agent: *\nDisallow: /private\nAllow: /private/public\n")

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].agents, ["*"])
        self.assertEqual(len(groups[0].rules), 2)

    def test_longest_matching_rule_wins(self) -> None:
        robots = "User-agent: *\nDisallow: /private\nAllow: /private/public\n"

        self.assertFalse(is_path_allowed_by_robots("/private", robots, "SesameKiller-CompassBot/0.1"))
        self.assertTrue(is_path_allowed_by_robots("/private/public/menu", robots, "SesameKiller-CompassBot/0.1"))
        self.assertTrue(is_path_allowed_by_robots("/public", robots, "SesameKiller-CompassBot/0.1"))


if __name__ == "__main__":
    unittest.main()
