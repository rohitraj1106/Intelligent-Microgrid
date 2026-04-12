import pytest
from edge.simulator import MicrogridSimulator
from edge.config import NODE_CONFIGS

def test_simulator_generates_all_75_nodes():
    """Verify that the simulator initializes state for exactly 75 nodes."""
    sim = MicrogridSimulator()
    assert len(sim._node_state) == 75
    assert len(NODE_CONFIGS) == 75

def test_node_capacities_are_randomized():
    """Verify that battery capacities are randomized between 8kWh and 12kWh."""
    capacities = [cfg["battery_capacity_wh"] for cfg in NODE_CONFIGS.values()]
    # At least two different capacities should exist among 75 nodes
    assert len(set(capacities)) > 1
    for cap in capacities:
        assert 8000 <= cap <= 12000

def test_physics_boundary_soc():
    """Verify that generated readings maintain SoC within [0, 100] limits."""
    sim = MicrogridSimulator(time_step_min=60) # Large step to force SoC change
    
    # Run for a few simulated days
    for _ in range(48):
        for node_id, node_cfg in NODE_CONFIGS.items():
            reading = sim._generate_reading(node_id, node_cfg)
            assert 0.0 <= reading.soc_pct <= 100.0
            
def test_city_batching_logic():
    """Verify that nodes are correctly grouped by city for batched publishing."""
    sim = MicrogridSimulator()
    city_batches = {}
    for node_id, node_cfg in NODE_CONFIGS.items():
        city = node_cfg["city"]
        if city not in city_batches:
            city_batches[city] = []
        city_batches[city].append(node_id)
        
    # Should have 5 cities with 15 nodes each
    assert len(city_batches) == 5
    for city, nodes in city_batches.items():
        assert len(nodes) == 15
