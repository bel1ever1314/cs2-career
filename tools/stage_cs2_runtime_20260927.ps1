param([string]$Stage = 'D:\CS2CareerBuilds\v1.6.0\runtime-repair-20260927')
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
# Download only. No game files, user profiles, or source repositories are changed.
$pins = @(
    @('alliedmodders/metamod-source', '2.0.0.1472', 'mmsource-2.0.0-git1472-windows.zip'),
    @('roflmuffin/CounterStrikeSharp', 'v1.0.376', 'counterstrikesharp-with-runtime-windows-1.0.376.zip'),
    @('XBribo/CS2-Bot-Controller', 'v0.7.0', 'BotController-MM-windows-0.7.0.zip'),
    @('XBribo/CS2-Bot-Controller', 'v0.7.0', 'BotController-CSS-API-0.7.0.zip'),
    @('XBribo/CS2-Bot-Hider', 'v0.5.0', 'BotHider-Windows-0.5.0.zip'),
    @('XBribo/CS2-Bot-Vision', 'v0.3.0', 'BotVision-Windows-0.3.0.zip')
)
[void](New-Item -ItemType Directory -Path $Stage -Force)
$headers = @{'User-Agent'='CS2Career-local-compat-check'}
$records = @()
foreach ($pin in $pins) {
    $release = Invoke-RestMethod ('https://api.github.com/repos/' + $pin[0] + '/releases/tags/' + $pin[1]) -Headers $headers -TimeoutSec 30
    $asset = @($release.assets | Where-Object name -EQ $pin[2])
    if ($asset.Count -ne 1 -or $asset[0].digest -notmatch '^sha256:[a-f0-9]{64}$') { throw "Unverified asset $($pin[2])" }
    $asset = $asset[0]
    $zip = Join-Path $Stage $asset.name
    $expected = $asset.digest.Substring(7)
    if (!(Test-Path -LiteralPath $zip) -or (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne $expected) {
        Invoke-WebRequest $asset.browser_download_url -OutFile $zip -TimeoutSec 180
    }
    $actual = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw "SHA-256 mismatch: $zip" }
    $unpacked = Join-Path $Stage ([IO.Path]::GetFileNameWithoutExtension($asset.name))
    if (!(Test-Path -LiteralPath $unpacked)) { Expand-Archive -LiteralPath $zip -DestinationPath $unpacked }
    $records += [pscustomobject]@{repo=$pin[0]; tag=$pin[1]; url=$asset.browser_download_url; sha256=$actual; extracted=$unpacked}
    Write-Output "Verified $($asset.name)"
}
# Source-only updates are reviewed/compiled separately, never installed automatically.
foreach ($source in @(
    @('ed0ard/CS2-Bot-Randomizer','276f1ce6fd7f291be124d2023a2716ed720fb6d7'),
    @('ed0ard/CS2-Bullseye-Bot','c3d10f5f5e31302589032bb579dfc342c9ea5639')
)) {
    $url = 'https://api.github.com/repos/' + $source[0] + '/zipball/' + $source[1]
    $zip = Join-Path $Stage ($source[0].Split('/')[1] + '-source.zip')
    if (!(Test-Path -LiteralPath $zip)) { Invoke-WebRequest $url -Headers $headers -OutFile $zip -TimeoutSec 120 }
    $dest = Join-Path $Stage ($source[0].Split('/')[1] + '-source')
    if (!(Test-Path -LiteralPath $dest)) { Expand-Archive -LiteralPath $zip -DestinationPath $dest }
    $records += [pscustomobject]@{repo=$source[0]; commit=$source[1]; url=$url; sha256=(Get-FileHash -LiteralPath $zip).Hash.ToLowerInvariant(); extracted=$dest}
    Write-Output "Downloaded source $($source[0])@$($source[1])"
}
$records | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Stage 'sources.json') -Encoding utf8
