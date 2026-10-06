"""Decision rules: which rung to start on. Pure functions; no I/O.

Every rule returns an index into the ladder. None of them can refuse a task:
escalation and the coordinator's own last rung handle failure.
"""
from __future__ import annotations


def cheapest_first(**_):
    return 0


def jev_noul(passes, cutoff=0.5, **_):
    """The product rule: the cheapest rung Jev says can do the job.

    If no rung clears the cutoff, start where Jev is most confident, not at the top.
    """
    for i, p in enumerate(passes):
        if p >= cutoff:
            return i
    return max(range(len(passes)), key=lambda i: (passes[i], -i))


def jev_choice(start, **_):
    return start


def expected_cost(passes, costs, coordinator_cost, start):
    """Expected spend escalating from `start`, treating rung outcomes as independent."""
    reach, total = 1.0, 0.0
    for p, c in zip(passes[start:], costs[start:]):
        total += reach * c
        reach *= 1 - p
    return total + reach * coordinator_cost


def jev_ev(passes, costs, coordinator_cost, **_):
    """No tuned parameter: minimise expected cost using Jev's pass answers and measured rung cost."""
    return min(range(len(passes)), key=lambda s: (expected_cost(passes, costs, coordinator_cost, s), s))


RULES = {'cheapest_first': cheapest_first, 'jev_noul': jev_noul, 'jev_choice': jev_choice, 'jev_ev': jev_ev}


def pick(rule, routing, cutoff=0.5, costs=None, coordinator_cost=None):
    """Apply a rule to a routing result; any missing Jev answer degrades to cheapest_first."""
    if rule == 'cheapest_first' or not routing or routing.get('route') != 'jev':
        return 0
    if rule == 'jev_choice':
        return jev_choice(routing['start'])
    if rule == 'jev_ev':
        if not costs or coordinator_cost is None:
            return jev_noul(routing['passes'], cutoff)
        return jev_ev(routing['passes'], costs, coordinator_cost)
    return jev_noul(routing['passes'], cutoff)
