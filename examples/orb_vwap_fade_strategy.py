"""
ORB Breakout Fade — VWAP Reclaim Trigger parameter space.

Fades the first Opening Range Breakout of the session: waits for a 1-min
close back across session VWAP against the breakout direction, then enters
toward the opposite side of the ORB with a stop at the breakout extreme.
See examples/orb_vwap_fade_strategy.pine for the full strategy implementation.

Load examples/orb_vwap_fade_strategy.pine in the optimizer UI to auto-detect
all inputs, or use this file to optimize the two knobs that most directly
affect trade frequency/risk: ORB duration and stop buffer.
"""
from optimizer import IntParameter, FloatParameter, ParameterSpace

PARAMETER_SPACE = ParameterSpace([
    IntParameter(
        name="orb_duration_min",
        label="ORB Duration (minutes)",
        description="Length of the Opening Range window in minutes",
        start=5,
        stop=15,
        step=5,
    ),
    FloatParameter(
        name="stop_buffer_ticks",
        label="Stop Buffer (ticks beyond breakout extreme)",
        description="Extra ticks added beyond the breakout extreme for the stop",
        start=0,
        stop=8,
        step=1,
        decimals=0,
    ),
])
