"""
MACD Strategy parameter space definition.

This file defines which inputs to optimize for a MACD-based PineScript strategy.
The 'label' field must match EXACTLY the input label shown in TradingView's
Strategy Settings > Inputs dialog.

PineScript strategy template (paste into TradingView Pine Editor):

    //@version=5
    strategy("MACD Optimizer Strategy", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=100)

    fastLength   = input.int(12,  "Fast Length",   minval=2, maxval=100)
    slowLength   = input.int(26,  "Slow Length",   minval=5, maxval=200)
    signalLength = input.int(9,   "Signal Length", minval=1, maxval=50)
    atrMult      = input.float(1.5, "ATR Multiplier", minval=0.5, maxval=5.0, step=0.1)
    atrPeriod    = input.int(14,  "ATR Period",    minval=5,  maxval=50)

    [macdLine, signalLine, histLine] = ta.macd(close, fastLength, slowLength, signalLength)
    atr = ta.atr(atrPeriod)

    longCond  = ta.crossover(macdLine, signalLine)
    shortCond = ta.crossunder(macdLine, signalLine)

    if longCond
        strategy.entry("Long", strategy.long)
        strategy.exit("Long Exit", "Long",  loss=atr * atrMult * 10, profit=atr * atrMult * 20)
    if shortCond
        strategy.entry("Short", strategy.short)
        strategy.exit("Short Exit", "Short", loss=atr * atrMult * 10, profit=atr * atrMult * 20)
"""
from optimizer import IntParameter, FloatParameter, ParameterSpace

PARAMETER_SPACE = ParameterSpace([
    IntParameter(
        name="fast_length",
        label="Fast Length",
        description="MACD fast EMA period",
        start=6,
        stop=30,
        step=2,
    ),
    IntParameter(
        name="slow_length",
        label="Slow Length",
        description="MACD slow EMA period",
        start=20,
        stop=60,
        step=5,
    ),
    IntParameter(
        name="signal_length",
        label="Signal Length",
        description="MACD signal smoothing period",
        start=5,
        stop=20,
        step=1,
    ),
    FloatParameter(
        name="atr_mult",
        label="ATR Multiplier",
        description="Stop/target distance multiplier",
        start=1.0,
        stop=3.0,
        step=0.5,
        decimals=1,
    ),
    IntParameter(
        name="atr_period",
        label="ATR Period",
        description="ATR lookback period",
        start=10,
        stop=20,
        step=5,
    ),
])
