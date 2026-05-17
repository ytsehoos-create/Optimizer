"""
EMA Crossover Strategy parameter space.

PineScript strategy template:

    //@version=5
    strategy("EMA Cross Optimizer", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=100)

    fastEMA   = input.int(9,   "Fast EMA",     minval=2,  maxval=50)
    slowEMA   = input.int(21,  "Slow EMA",     minval=10, maxval=200)
    stopPct   = input.float(2.0, "Stop Loss %", minval=0.5, maxval=10.0, step=0.5)
    tpRatio   = input.float(2.0, "TP Ratio",   minval=0.5, maxval=5.0,  step=0.5)
    trailStop = input.bool(false, "Use Trail Stop")
    volFilter = input.bool(true,  "Volume Filter")
    volMult   = input.float(1.5, "Volume Multiplier", minval=1.0, maxval=3.0, step=0.25)

    fast = ta.ema(close, fastEMA)
    slow = ta.ema(close, slowEMA)

    vol_ok = not volFilter or volume > ta.sma(volume, 20) * volMult

    longCond  = ta.crossover(fast, slow) and vol_ok
    shortCond = ta.crossunder(fast, slow) and vol_ok

    stopDist = close * stopPct / 100

    if longCond
        strategy.entry("Long", strategy.long)
        if trailStop
            strategy.exit("Long TS", "Long", trail_points=stopDist/syminfo.mintick,
                          trail_offset=stopDist/syminfo.mintick * 0.5)
        else
            strategy.exit("Long Exit", "Long", loss=stopDist/syminfo.mintick,
                          profit=(stopDist * tpRatio)/syminfo.mintick)

    if shortCond
        strategy.entry("Short", strategy.short)
        if trailStop
            strategy.exit("Short TS", "Short", trail_points=stopDist/syminfo.mintick,
                          trail_offset=stopDist/syminfo.mintick * 0.5)
        else
            strategy.exit("Short Exit", "Short", loss=stopDist/syminfo.mintick,
                          profit=(stopDist * tpRatio)/syminfo.mintick)
"""
from optimizer import IntParameter, FloatParameter, CategoricalParameter, ParameterSpace

PARAMETER_SPACE = ParameterSpace([
    IntParameter(
        name="fast_ema",
        label="Fast EMA",
        description="Fast EMA period",
        start=5,
        stop=25,
        step=2,
    ),
    IntParameter(
        name="slow_ema",
        label="Slow EMA",
        description="Slow EMA period",
        start=15,
        stop=100,
        step=5,
    ),
    FloatParameter(
        name="stop_pct",
        label="Stop Loss %",
        description="Stop loss percentage",
        start=1.0,
        stop=5.0,
        step=0.5,
        decimals=1,
    ),
    FloatParameter(
        name="tp_ratio",
        label="TP Ratio",
        description="Risk-reward ratio for take profit",
        start=1.0,
        stop=4.0,
        step=0.5,
        decimals=1,
    ),
    FloatParameter(
        name="vol_mult",
        label="Volume Multiplier",
        description="Volume filter threshold multiplier",
        start=1.0,
        stop=2.5,
        step=0.25,
        decimals=2,
    ),
])
