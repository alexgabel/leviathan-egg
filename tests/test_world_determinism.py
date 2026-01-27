from leviathan_egg.config import load_config
from leviathan_egg.world import World

def test_world_step_is_deterministic_given_seed():
    cfg = load_config("experiments/configs/phase1_reversal.yaml")

    w1 = World(cfg)
    w2 = World(cfg)

    for t in range(50):
        w1.step(t)
        w2.step(t)

    assert w1.snapshot() == w2.snapshot()