param(
    [string]$Destination = 'E:\CS2CareerTools\Career3DRedesign'
)
$ErrorActionPreference = 'Stop'
$sourceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\work\career3d_redesign'))
$targetRoot = [IO.Path]::GetFullPath($Destination).TrimEnd('\')
$allowedRoot = [IO.Path]::GetFullPath('E:\CS2CareerTools').TrimEnd('\')
if (-not $targetRoot.StartsWith($allowedRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The deployment target must be a dedicated project below E:\CS2CareerTools.'
}
if (-not (Test-Path -LiteralPath (Join-Path $targetRoot 'project.godot'))) {
    throw 'Choose an existing 3D project with assets. This updater does not recreate or replace assets.'
}
# Verify both the unmodified font and its license before changing any files.
$fontRoot = 'E:\CS2CareerTools\Career3DMedia\fonts'
$fontManifest = Get-Content -LiteralPath (Join-Path $sourceRoot 'data\ui_style.json') -Raw | ConvertFrom-Json
foreach ($fontCheck in @(@('ChillRoundF.ttf', $fontManifest.font_sha256), @('OFL.txt', $fontManifest.license_sha256))) {
    $artifact = Join-Path $fontRoot $fontCheck[0]
    if (-not (Test-Path -LiteralPath $artifact) -or (Get-FileHash -LiteralPath $artifact).Hash.ToLowerInvariant() -ne $fontCheck[1]) {
        throw ('Missing or unverified font artifact: ' + $artifact)
    }
}
$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -like 'Godot*' -and $_.CommandLine -and $_.CommandLine.Contains($targetRoot)
}
if ($running) { throw 'Close the target 3D sample before updating its scripts.' }
$snapshotRoot = Join-Path $targetRoot 'source-snapshots'
New-Item -ItemType Directory -Path $snapshotRoot -Force | Out-Null
# Backups retain old scripts and UIDs; don't index them as live Godot resources.
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'godot_source_snapshots.gdignore') -Destination (Join-Path $snapshotRoot '.gdignore') -Force
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$snapshot = Join-Path $targetRoot ('source-snapshots\desktop-ladder-' + $stamp)
$files = [Collections.Generic.List[IO.FileInfo]]::new()
foreach ($folder in @('scripts', 'tests', 'data', 'source')) {
    Get-ChildItem -LiteralPath (Join-Path $sourceRoot $folder) -File -Recurse | Where-Object {
        $_.Extension -in @('.gd', '.uid', '.json', '.py', '.tscn', '.txt')
    } | ForEach-Object { $files.Add($_) }
}
# Shared RTS resources are generated from work/career_rts by sync_career_rts.ps1.
# Include only code and small map resources; never standalone runtime/reports.
$rtsRoot = Join-Path $sourceRoot 'rts'
if (Test-Path -LiteralPath $rtsRoot) {
    Get-ChildItem -LiteralPath $rtsRoot -File -Recurse | Where-Object {
        $_.Extension -in @('.gd','.json','.png','.txt') -and -not $_.FullName.Contains('\runtime\')
    } | ForEach-Object { $files.Add($_) }
}
Get-ChildItem -LiteralPath $sourceRoot -File | Where-Object {
    $_.Extension -in @('.gd', '.tscn', '.godot', '.cmd', '.txt')
} | ForEach-Object { $files.Add($_) }
$updated = 0
foreach ($file in $files) {
    $relative = $file.FullName.Substring($sourceRoot.Length).TrimStart('\')
    $target = Join-Path $targetRoot $relative
    if (Test-Path -LiteralPath $target) {
        if ((Get-FileHash -LiteralPath $target).Hash -eq (Get-FileHash -LiteralPath $file.FullName).Hash) { continue }
        $backup = Join-Path $snapshot $relative
        New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($backup)) -Force | Out-Null
        Copy-Item -LiteralPath $target -Destination $backup
    }
    New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($target)) -Force | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $target -Force
    $updated++
}
# Deliberately no deletion: runtime/career, assets, captures and extension data stay untouched.
# Licensed font artifacts live on E, never in the C-drive build workspace.
$fontFile = Join-Path $fontRoot 'ChillRoundF.ttf'
if (Test-Path -LiteralPath $fontFile) {
    $fontTarget = Join-Path $targetRoot 'fonts'
    New-Item -ItemType Directory -Path $fontTarget -Force | Out-Null
    foreach ($fontName in @('ChillRoundF.ttf', 'OFL.txt')) {
        $fontSource = Join-Path $fontRoot $fontName
        $fontDestination = Join-Path $fontTarget $fontName
        if (Test-Path -LiteralPath $fontDestination) {
            if ((Get-FileHash -LiteralPath $fontSource).Hash -eq (Get-FileHash -LiteralPath $fontDestination).Hash) { continue }
            $fontBackup = Join-Path $snapshot ('fonts\' + $fontName)
            New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($fontBackup)) -Force | Out-Null
            Copy-Item -LiteralPath $fontDestination -Destination $fontBackup
        }
        Copy-Item -LiteralPath $fontSource -Destination $fontDestination -Force
        $updated++
    }
}
[pscustomobject]@{ Destination = $targetRoot; Updated = $updated; Backup = $snapshot } | ConvertTo-Json -Compress
