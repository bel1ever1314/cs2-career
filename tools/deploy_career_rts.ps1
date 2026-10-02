param([string]$Destination = 'E:\CS2CareerTools\CS2Tactical2D')
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\work\career_rts')).TrimEnd('\')
$target = [IO.Path]::GetFullPath($Destination).TrimEnd('\')
if ($target -ne 'E:\CS2CareerTools\CS2Tactical2D') { throw 'Choose only the dedicated CS2Tactical2D sample.' }
$running = Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'Godot*' -and $_.CommandLine -and $_.CommandLine.Contains($target) }
if ($running) { throw 'Close the 2D sample before updating.' }
$backups = Join-Path $target 'source-snapshots'
New-Item -ItemType Directory -Path $backups -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'godot_source_snapshots.gdignore') -Destination (Join-Path $backups '.gdignore') -Force
$snapshot = Join-Path $backups (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$updated = 0
foreach ($file in Get-ChildItem -LiteralPath $source -File -Recurse) {
    if ($file.FullName.Contains('\.godot\') -or $file.Extension -notin @('.gd','.tscn','.godot','.json','.png','.txt','.cmd','.ps1','.py')) { continue }
    $relative = $file.FullName.Substring($source.Length).TrimStart('\')
    $out = Join-Path $target $relative
    if (Test-Path -LiteralPath $out) {
        if ((Get-FileHash -LiteralPath $out).Hash -eq (Get-FileHash -LiteralPath $file.FullName).Hash) { continue }
        $backup = Join-Path $snapshot $relative
        New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($backup)) -Force | Out-Null
        Copy-Item -LiteralPath $out -Destination $backup
    }
    New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($out)) -Force | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $out -Force
    $updated++
}
[pscustomobject]@{Destination=$target;Updated=$updated;Backup=$snapshot} | ConvertTo-Json -Compress
