"""
RSI + Bollinger Bands Strategy parameter space.

PineScript strategy template:

    //@version=5
    strategy("RSI+BB Optimizer Strategy", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=100)

    rsiLength  = input.int(14,   "RSI Length",      minval=2,   maxval=50)
    rsiOB      = input.int(70,   "RSI Overbought",  minval=60,  maxval=90)
    rsiOS      = input.int(30,   "RSI Oversold",    minval=10,  maxval=40)
    bbLength   = input.int(20,   "BB Length",       minval=5,   maxval=100)
    bbMult     = input.float(2.0, "BB Multiplier",  minval=0.5, maxval=4.0, step=0.1)
    useFilter  = input.bool(true, "Use Trend Filter")
    trendMA    = input.int(200,  "Trend MA Length", minval=50,  maxval=400)

    rsi  = ta.rsi(close, rsiLength)
    [bb_mid, bb_up, bb_dn] = ta.bb(close, bbLength, bbMult)
    trend_ok = not useFilter or close > ta.sma(close, trendMA)

    longCond  = rsi < rsiOS and close <= bb_dn and trend_ok
    shortCond = rsi > rsiOB and close >= bb_up and not trend_ok

    if longCond
        strategy.entry("Long",  strategy.long)
    if shortCond
        strategy.entry("Short", strategy.short)

    // Exit when RSI returns to midpoint
    if strategy.position_size > 0 and rsi > 50
        strategy.close("Long")
    if strategy.position_size < 0 and rsi < 50
        strategy.close("Short")
"""
from optimizer import IntParameter, FloatParameter, CategoricalParameter, ParameterSpace

PARAMETER_SPACE = ParameterSpace([
    IntParameter(
        name="rsi_length",
        label="RSI Length",
        description="RSI calculation period",
        start=8,
        stop=21,
        step=1,
    ),
    IntParameter(
        name="rsi_ob",
        label="RSI Overbought",
        description="RSI overbought threshold",
        start=65,
        stop=80,
        step=5,
    ),
    IntParameter(
        name="rsi_os",
        label="RSI Oversold",
        description="RSI oversold threshold",
        start=20,
        stop=35,
        step=5,
    ),
    IntParameter(
        name="bb_length",
        label="BB Length",
        description="Bollinger Bands period",
        start=10,
        stop=30,
        step=5,
    ),
    FloatParameter(
        name="bb_mult",
        label="BB Multiplier",
        description="Bollinger Bands std-dev multiplier",
        start=1.5,
        stop=3.0,
        step=0.5,
        decimals=1,
    ),
    IntParameter(
        name="trend_ma",
        label="Trend MA Length",
        description="SMA length for trend filter",
        start=100,
        stop=300,
        step=50,
    ),
])
