"""
Tests for backend/core/simulation/org_graph.py

Critical audit bug covered:
- _cached_agents_count was the sole cache key, meaning two different datasets
  with the same headcount would share the same cached graph.
- Fix: dataset_id is now part of the cache key.
"""

import pytest
from unittest.mock import MagicMock, patch


# ── Helper ─────────────────────────────────────────────────────────────────────

def _make_agent(employee_id, department="Engineering", job_level=2, manager_id=None):
    """Build a minimal MagicMock that satisfies OrgGraph._build_graph()."""
    emp = MagicMock()
    emp.employee_id              = employee_id
    emp.department               = department
    emp.job_level                = job_level
    emp.manager_id               = manager_id
    emp.years_with_curr_manager  = 2
    emp.job_satisfaction         = 3.0
    emp.work_life_balance        = 3.0
    emp.total_working_years      = 5
    emp.years_at_company         = 3
    emp.monthly_income           = 5000
    emp.attrition                = "No"
    emp.job_role                 = "Engineer"
    emp.performance_rating       = 3
    emp.stock_option_level       = 1
    emp.age                      = 30
    emp.distance_from_home       = 10
    emp.percent_salary_hike      = 10
    emp.years_since_last_promotion = 1
    emp.job_involvement          = 3
    emp.environment_satisfaction = 3
    emp.num_companies_worked     = 2
    emp.marital_status           = "Single"
    emp.overtime                 = 0
    return emp


def _make_agents(n, department="Engineering"):
    return [_make_agent(i, department=department) for i in range(1, n + 1)]


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_cache():
    """Always start each test with a clean graph cache."""
    from backend.core.simulation.org_graph import clear_graph_cache
    clear_graph_cache()
    yield
    clear_graph_cache()


# ── Cache isolation tests ──────────────────────────────────────────────────────

class TestCacheIsolation:
    """
    Audit: cache was keyed only by agent count.
    Two datasets with 50 agents each would return the SAME cached graph.
    Fix: cache key now includes dataset_id.
    """

    def test_same_count_different_dataset_id_builds_separate_graphs(self):
        """Core audit regression test."""
        from backend.core.simulation.org_graph import build_org_graph

        agents_a = _make_agents(20, department="Engineering")
        agents_b = _make_agents(20, department="Sales")  # same count, different data

        graph_a = build_org_graph(agents_a, dataset_id="dataset_A")
        graph_b = build_org_graph(agents_b, dataset_id="dataset_B")

        # They must be distinct objects — not the same cached template
        assert id(graph_a.G) != id(graph_b.G), (
            "Two different datasets with same agent count share the same graph object. "
            "Cache is keyed only on agent count, not dataset_id. This is the audit bug."
        )

    def test_same_dataset_id_reuses_template(self):
        """Caching must still work for repeated calls with same dataset_id."""
        from backend.core.simulation.org_graph import build_org_graph, _cached_template_graph
        import backend.core.simulation.org_graph as og_module

        agents = _make_agents(15)

        # First call — builds from scratch
        build_org_graph(agents, dataset_id="same_id")
        template_after_first = og_module._cached_template_graph

        # Second call — should reuse cached template
        build_org_graph(agents, dataset_id="same_id")
        template_after_second = og_module._cached_template_graph

        assert template_after_first is template_after_second

    def test_cache_invalidated_on_different_dataset_id(self):
        """Switching dataset_id must rebuild and update the cache."""
        from backend.core.simulation.org_graph import build_org_graph
        import backend.core.simulation.org_graph as og_module

        agents = _make_agents(10)

        build_org_graph(agents, dataset_id="id_1")
        template_1 = og_module._cached_template_graph

        build_org_graph(agents, dataset_id="id_2")
        template_2 = og_module._cached_template_graph

        # Cache must have been replaced
        assert template_1 is not template_2

    def test_clear_graph_cache_resets_all_state(self):
        """clear_graph_cache() must zero out all three module-level globals."""
        from backend.core.simulation.org_graph import build_org_graph, clear_graph_cache
        import backend.core.simulation.org_graph as og_module

        build_org_graph(_make_agents(10), dataset_id="test")
        assert og_module._cached_template_graph is not None

        clear_graph_cache()

        assert og_module._cached_template_graph is None
        assert og_module._cached_agents_count   == 0
        assert og_module._cached_dataset_id     is None


# ── Graph structure correctness ────────────────────────────────────────────────

class TestGraphStructure:

    def test_all_agents_become_nodes(self):
        from backend.core.simulation.org_graph import build_org_graph

        agents = _make_agents(10)
        graph  = build_org_graph(agents, dataset_id="test")

        for agent in agents:
            assert graph.has_node(agent.employee_id), (
                f"Agent {agent.employee_id} missing from graph nodes"
            )

    def test_manager_edges_created(self):
        """Employees with manager_id set must have a manager-type edge."""
        from backend.core.simulation.org_graph import build_org_graph

        manager = _make_agent(1)
        report  = _make_agent(2, manager_id=1)
        graph   = build_org_graph([manager, report], dataset_id="test")

        assert graph.has_edge(1, 2) or graph.has_edge(2, 1)
        # Confirm edge type
        edge_data = graph.G.get_edge_data(1, 2) or graph.G.get_edge_data(2, 1)
        assert edge_data["edge_type"] == "manager"

    def test_no_self_loops(self):
        """No agent should have an edge to itself."""
        from backend.core.simulation.org_graph import build_org_graph

        agents = _make_agents(10)
        graph  = build_org_graph(agents, dataset_id="test")

        for agent in agents:
            assert not graph.has_edge(agent.employee_id, agent.employee_id)

    def test_copy_does_not_mutate_template(self):
        """OrgGraph copies must not mutate the cached template."""
        from backend.core.simulation.org_graph import build_org_graph
        import backend.core.simulation.org_graph as og_module

        agents = _make_agents(10)
        build_org_graph(agents, dataset_id="test")

        # Snapshot node count before second call
        node_count_before = og_module._cached_template_graph.number_of_nodes()

        # Second call returns a copy — we then manipulate it
        graph2 = build_org_graph(agents, dataset_id="test")
        graph2.add_node(9999)  # mutate the copy

        # Template must be unchanged
        assert og_module._cached_template_graph.number_of_nodes() == node_count_before


# ── OrgGraph traversal methods ─────────────────────────────────────────────────

class TestOrgGraphTraversal:

    def test_get_direct_reports_returns_correct_agents(self):
        from backend.core.simulation.org_graph import OrgGraph, build_org_graph

        manager = _make_agent(1)
        r1      = _make_agent(2, manager_id=1)
        r2      = _make_agent(3, manager_id=1)
        graph   = build_org_graph([manager, r1, r2], dataset_id="test")

        # Must import EmployeeAgent since build_org_graph wraps mock agents
        reports = graph.get_direct_reports(1)
        report_ids = [a.employee_id for a in reports]

        assert 2 in report_ids
        assert 3 in report_ids

    def test_get_direct_reports_missing_node_returns_empty(self):
        from backend.core.simulation.org_graph import build_org_graph

        graph = build_org_graph(_make_agents(5), dataset_id="test")

        result = graph.get_direct_reports(99999)  # non-existent

        assert result == []

    def test_chain_of_command_no_infinite_loop(self):
        """Cycle in manager_id data must not cause infinite loop."""
        # emp A reports to B, B reports to A — cycle
        a = _make_agent(1, manager_id=2)
        b = _make_agent(2, manager_id=1)

        from backend.core.simulation.org_graph import build_org_graph
        graph = build_org_graph([a, b], dataset_id="test")

        # Must terminate — visited set prevents infinite loop
        chain = graph.get_chain_of_command(1)
        assert len(chain) <= 2
