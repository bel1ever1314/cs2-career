param([string]$OutputRoot = 'D:\CS2CareerBuilds\plugins')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$artifactsRoot = [System.IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Path $artifactsRoot -Force | Out-Null
foreach ($pluginName in @('CareerMatch','BotBuy')) {
    $project = Join-Path $projectRoot "vendor/$pluginName/$pluginName.csproj"
    $output = Join-Path $artifactsRoot "bin/$pluginName"
    $intermediate = (Join-Path $artifactsRoot "obj/$pluginName") + [System.IO.Path]::DirectorySeparatorChar
    & dotnet build $project --no-incremental --configuration Release --output $output "-p:BaseIntermediateOutputPath=$intermediate" "-p:MSBuildProjectExtensionsPath=$intermediate" "-p:PathMap=$projectRoot=/src/cs2career" -p:DebugType=None -p:DebugSymbols=false
    if ($LASTEXITCODE -ne 0) { throw "$pluginName build failed" }
    foreach ($suffix in @('.dll','.deps.json')) {
        Copy-Item -LiteralPath (Join-Path $output ($pluginName+$suffix)) -Destination (Join-Path $projectRoot "vendor/$pluginName/$pluginName$suffix") -Force
    }
}
