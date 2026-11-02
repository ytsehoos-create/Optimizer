# NinjaView payload test
#
# Sends ONE test message straight to the NinjaView add-on on this machine, the same way the
# Chrome extension forwards a TradingView alert (and the same as the extension's
# Payload tab -> "Send to NT8"). It takes TradingView out of the picture: if NinjaTrader acts on a
# message sent here, that message works and the add-on is listening.
#
# The messages are exactly what NinjaView Bridge v5.2's Payload generator builds, and what
# T2_combined_v3.pine sends:
#   1  oco limit buy            resting limit entry with take-profit / stop-loss ("Resting limit")
#   2  cancel oco               withdraw that order by its oco_id
#   3  oco market buy           market entry with take-profit / stop-loss ("Market at the level")
#   4  cancel oco and flatten   cancel that trade's bracket and close it (15:55)
#   5  market close             close the position (backstop after 4; also 9:30 safety net)
#   6  close then oco market buy  handoff: close any position, then market entry with bracket
#   7  cancel orders            cancel every working order (clean-up)
#
# Before you run it:
#   - NinjaTrader 8 running; TradeSync NinjaView window CONNECTED (Localhost mode, port 5001)
#   - Auto-Trade ticked; account Sim101. Every test is 1 MNQ on Sim101.
#   - Test 1: the entry rests 400 points below the price you give, the target 100 above it and
#     the stop 500 below it, so nothing fills even if the target and stop are placed at once.
#     Note whether they appear before the entry fills: that decides whether resting limits are safe.
#   - Tests 3 and 6 FILL 1 MNQ long at market (needs a live market): target 100 above, stop 100
#     below the price you give. Close with test 4 (same id) or 5, then check nothing is left working.
#
# Run it in PowerShell from the folder you saved it to:
#   powershell -ExecutionPolicy Bypass -File .\ninjaview_payload_test.ps1                  (lists the tests)
#   powershell -ExecutionPolicy Bypass -File .\ninjaview_payload_test.ps1 1 -Price 28600   (test 1 at MNQ 28600)
#   powershell -ExecutionPolicy Bypass -File .\ninjaview_payload_test.ps1 2 -Id NVT-103512 (cancel what test 1 placed)
#
# After each test, look at NinjaTrader's Orders and Positions tabs and the add-on log.

param(
    [int]$Test = 0,
    [double]$Price = 0,
    [string]$Id = "",
    [string]$Account = "Sim101",
    [string]$Ticker = "MNQ 12-26",
    [int]$Port = 5001
)

$url = "http://localhost:$Port/"
$inv = [Globalization.CultureInfo]::InvariantCulture
function Px([double]$x) { return $x.ToString("0.00", $inv) }

$tests = @(
    "1  oco limit buy: resting limit entry with bracket (does not fill)",
    "2  cancel oco: withdraw the order from test 1 (needs -Id)",
    "3  oco market buy: market entry with bracket (FILLS 1 lot)",
    "4  cancel oco and flatten: cancel the bracket and close the trade from test 3 or 6 (needs -Id)",
    "5  market close: close the position",
    "6  close then oco market buy: close any position, then market entry with bracket (FILLS 1 lot)",
    "7  cancel orders: cancel every working order"
)

if (@(1, 2, 3, 4, 5, 6, 7) -notcontains $Test) {
    Write-Host "Tests (send one at a time):"
    $tests | ForEach-Object { Write-Host "  $_" }
    Write-Host "Entry tests (1, 3, 6) need -Price <current MNQ price>; tests 2 and 4 need -Id <id the entry test printed>."
    exit 0
}
if ((@(1, 3, 6) -contains $Test) -and $Price -le 0) {
    Write-Host "Give the current MNQ price, for example: -Price 28600"
    exit 1
}
if ((@(2, 4) -contains $Test) -and $Id -eq "") {
    Write-Host "Give the id the entry test printed, for example: -Id NVT-103512"
    exit 1
}
if ($Id -eq "") { $Id = "NVT-" + (Get-Date -Format "HHmmss") }

$e  = Px ($Price - 400)
$tp = Px ($Price + 100)
$sl = Px ($Price - 500)
if (@(3, 6) -contains $Test) { $sl = Px ($Price - 100) }
$base = '"account":"' + $Account + '","ticker":"' + $Ticker + '"'
$bracket = ',"qty":"1","take_profit_price":"' + $tp + '","stop_loss_price":"' + $sl + '","oco_id":"' + $Id + '"}'

switch ($Test) {
    1 { $body = '{"alert":"oco limit buy",' + $base + ',"qty":"1","limit_price":"' + $e + '","take_profit_price":"' + $tp +
                '","stop_loss_price":"' + $sl + '","oco_id":"' + $Id + '"}' }
    2 { $body = '{"alert":"cancel oco",' + $base + ',"oco_id":"' + $Id + '"}' }
    3 { $body = '{"alert":"oco market buy",' + $base + $bracket }
    4 { $body = '{"alert":"cancel oco and flatten",' + $base + ',"oco_id":"' + $Id + '"}' }
    5 { $body = '{"alert":"market close",' + $base + '}' }
    6 { $body = '{"alert":"close then oco market buy",' + $base + $bracket }
    7 { $body = '{"alert":"cancel orders",' + $base + '}' }
}

Write-Host ("Test " + $tests[$Test - 1])
Write-Host "Sending: $body"
try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $url -Method Post -Body $body -ContentType "application/json"
    Write-Host ("Add-on replied " + $r.StatusCode + ": " + $r.Content)
} catch {
    Write-Host ("Could not reach the add-on at " + $url + ": " + $_.Exception.Message)
}
if ($Test -eq 1) { Write-Host "Id used: $Id  (entry $e, target $tp, stop $sl)" }
if (@(3, 6) -contains $Test) { Write-Host "Id used: $Id  (market entry, target $tp, stop $sl). Close it with test 4 -Id $Id" }
Write-Host "Now check NinjaTrader's Orders and Positions tabs and the add-on log."
