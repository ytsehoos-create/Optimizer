# NinjaView payload test
#
# Sends ONE test message straight to the NinjaView add-on on this machine, the same way the
# Chrome extension forwards a TradingView alert. It takes TradingView and the extension out of
# the picture: if NinjaTrader acts on a message sent here, that JSON format works.
#
# Before you run it:
#   - NinjaTrader 8 running; TradeSync NinjaView window CONNECTED (Localhost mode, port 5001)
#   - Auto-Trade ticked; account Sim101
#   - Every test is 1 MNQ on Sim101. In tests 1, 3 and 5 the entry rests 400 points below the
#     price you give, the target 100 above it and the stop 500 below it, so nothing fills even
#     if the add-on sends the bracket legs straight away.
#   - Tests 6 and 7 are MARKET entries: they DO fill 1 MNQ long on Sim101 (needs a live market),
#     with the target 100 points above and the stop 100 below the price you give. Run test 8
#     (or 9) afterwards to close it. Note whether the target and stop orders are still working
#     after the close: if they are, cancel them by hand and tell Claude.
#   - Test 7 copies NinjaView's own example (github.com/NinjaView/Pinescript) exactly.
#
# Run it in PowerShell from the folder you saved it to:
#   powershell -ExecutionPolicy Bypass -File .\ninjaview_payload_test.ps1                  (lists the tests)
#   powershell -ExecutionPolicy Bypass -File .\ninjaview_payload_test.ps1 1 -Price 29900   (test 1 at MNQ 29900)
#   powershell -ExecutionPolicy Bypass -File .\ninjaview_payload_test.ps1 2 -Id NVT-103512 (cancel what test 1 placed)
#
# After each test, look at NinjaTrader's Orders tab and the add-on log, and note what happened.
# Cancel anything left over by hand in NinjaTrader when you are done.

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
    "1  bracketed limit entry, the script's format today ('oco limit buy', stop_loss_price)",
    "2  cancel by oco_id, the script's format today ('cancel oco')",
    "3  bracketed limit entry, payload-reference style ('OCO Limit Long', order_type, stop_price)",
    "4  cancel by oco_id, payload-reference style ('Cancel OCO')",
    "5  plain limit entry, no bracket ('Limit Long'): the baseline; cancel it by hand",
    "6  bracketed MARKET entry, setup-guide style ('oco market buy', stop_loss_price): fills 1 lot",
    "7  bracketed MARKET entry, NinjaView's GitHub example ('OCO Market Long', stop_price): fills 1 lot",
    "8  close the position ('Market Close')",
    "9  close everything ('Close All')"
)

if (@(1, 2, 3, 4, 5, 6, 7, 8, 9) -notcontains $Test) {
    Write-Host "Tests (send one at a time):"
    $tests | ForEach-Object { Write-Host "  $_" }
    Write-Host "Entry tests (1, 3, 5, 6, 7) need -Price <current MNQ price>; cancel tests (2, 4) need -Id <id the entry test printed>."
    exit 0
}
if ((@(1, 3, 5, 6, 7) -contains $Test) -and $Price -le 0) {
    Write-Host "Give the current MNQ price, for example: -Price 29900"
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
if (@(6, 7) -contains $Test) { $sl = Px ($Price - 100) }
$base = '"account":"' + $Account + '","ticker":"' + $Ticker + '"'

switch ($Test) {
    1 { $body = '{"alert":"oco limit buy",' + $base + ',"qty":"1","limit_price":"' + $e + '","take_profit_price":"' + $tp +
                '","stop_loss_price":"' + $sl + '","oco_id":"' + $Id + '","tif":"DAY"}' }
    2 { $body = '{"alert":"cancel oco",' + $base + ',"oco_id":"' + $Id + '"}' }
    3 { $body = '{"alert":"OCO Limit Long",' + $base + ',"qty":"1","order_type":"LIMIT","limit_price":"' + $e +
                '","take_profit_price":"' + $tp + '","stop_price":"' + $sl + '","oco_id":"' + $Id + '","tif":"DAY"}' }
    4 { $body = '{"alert":"Cancel OCO",' + $base + ',"oco_id":"' + $Id + '"}' }
    5 { $body = '{"alert":"Limit Long",' + $base + ',"qty":"1","order_type":"LIMIT","limit_price":"' + $e + '","tif":"DAY"}' }
    6 { $body = '{"alert":"oco market buy",' + $base + ',"qty":"1","take_profit_price":"' + $tp + '","stop_loss_price":"' + $sl +
                '","oco_id":"' + $Id + '"}' }
    7 { $body = '{"alert":"OCO Market Long",' + $base + ',"qty":"1","take_profit_price":"' + $tp + '","stop_price":"' + $sl +
                '","tif":"DAY","oco_id":"' + $Id + '"}' }
    8 { $body = '{"alert":"Market Close",' + $base + '}' }
    9 { $body = '{"alert":"Close All",' + $base + '}' }
}

Write-Host ("Test " + $tests[$Test - 1])
Write-Host "Sending: $body"
try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $url -Method Post -Body $body -ContentType "application/json"
    Write-Host ("Add-on replied " + $r.StatusCode + ": " + $r.Content)
} catch {
    Write-Host ("Could not reach the add-on at " + $url + ": " + $_.Exception.Message)
}
if (@(1, 3, 5) -contains $Test) { Write-Host "Id used: $Id  (entry $e, target $tp, stop $sl)" }
if (@(6, 7) -contains $Test) { Write-Host "Id used: $Id  (market entry, target $tp, stop $sl). Run test 8 or 9 to close it." }
Write-Host "Now check NinjaTrader's Orders tab and the add-on log."
