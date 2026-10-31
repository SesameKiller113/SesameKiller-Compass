from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RobotsRule:
    allow: bool
    path: str


@dataclass(frozen=True)
class RobotsGroup:
    agents: list[str]
    rules: list[RobotsRule]


def parse_robots_txt(text: str) -> list[RobotsGroup]:
    groups: list[RobotsGroup] = []
    agents: list[str] = []
    rules: list[RobotsRule] = []
    has_rules = False

    def flush() -> None:
        nonlocal agents, rules, has_rules
        if agents:
            groups.append(RobotsGroup(agents=agents, rules=rules))
        agents = []
        rules = []
        has_rules = False

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue

        directive, value = line.split(":", 1)
        directive = directive.strip().lower()
        value = value.strip()

        if directive == "user-agent":
            if agents and has_rules:
                flush()
            agents.append(value.lower())
            continue

        if directive in {"allow", "disallow"} and agents:
            rules.append(RobotsRule(allow=directive == "allow", path=value))
            has_rules = True

    flush()
    return groups


def is_path_allowed_by_robots(path_with_search: str, robots_text: str, user_agent: str) -> bool:
    groups = parse_robots_txt(robots_text)
    matching_groups = [
        group for group in groups if any(agent_matches(agent, user_agent) for agent in group.agents)
    ]
    if not matching_groups:
        return True

    winning_rule: RobotsRule | None = None
    for group in matching_groups:
        for rule in group.rules:
            if not rule.path:
                continue
            if not path_with_search.startswith(rule.path):
                continue
            if winning_rule is None or len(rule.path) > len(winning_rule.path):
                winning_rule = rule
            elif len(rule.path) == len(winning_rule.path) and rule.allow:
                winning_rule = rule

    return winning_rule.allow if winning_rule else True


def agent_matches(agent: str, user_agent: str) -> bool:
    return agent == "*" or agent in user_agent.lower()
