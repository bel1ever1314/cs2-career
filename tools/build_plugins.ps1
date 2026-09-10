$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
foreach ($pluginName in @('CareerMatch','BotBuy')) {
    $project = Join-Path $projectRoot "vendor/$pluginName/$pluginName.csproj"
    $output = Join-Path $projectRoot "build/public-plugins/$pluginName"
    & dotnet build $project --no-incremental --configuration Release --output $output "-p:PathMap=$projectRoot=/src/cs2career" -p:DebugType=None -p:DebugSymbols=false
    if ($LASTEXITCODE -ne 0) { throw "$pluginName build failed" }
    foreach ($suffix in @('.dll','.deps.json')) {
        Copy-Item -LiteralPath (Join-Path $output ($pluginName+$suffix)) -Destination (Join-Path $projectRoot "vendor/$pluginName/$pluginName$suffix") -Force
    }
}
