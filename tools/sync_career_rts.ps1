param([string]$Destination = '')
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$source = Join-Path $repo 'work\career_rts'
if (-not $Destination) { $Destination = Join-Path $repo 'work\career3d_redesign\rts' }
$target = [IO.Path]::GetFullPath($Destination)
if ([IO.Path]::GetFileName($target) -ne 'rts') { throw 'Shared resource destination must be a dedicated rts folder.' }
# Mechanical resource namespace rewrite. The standalone project is canonical;
# its shared copy has no main scene, autoload, network connection or save writer.
foreach ($folder in @('scripts','data','assets')) {
    foreach ($file in Get-ChildItem -LiteralPath (Join-Path $source $folder) -Recurse -File) {
        if ($file.Extension -notin @('.gd','.json','.png','.txt')) { continue }
        $relative = $file.FullName.Substring($source.Length).TrimStart('\')
        $out = Join-Path $target $relative
        New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($out)) -Force | Out-Null
        if ($file.Extension -in @('.gd','.json')) {
            $text = [IO.File]::ReadAllText($file.FullName)
            foreach ($prefix in @('scripts','data','assets','runtime')) {
                $text = $text.Replace('res://' + $prefix + '/', 'res://rts/' + $prefix + '/')
            }
            [IO.File]::WriteAllText($out,$text,[Text.UTF8Encoding]::new($false))
        } else { Copy-Item -LiteralPath $file.FullName -Destination $out -Force }
    }
}
[pscustomobject]@{Shared=$target;Source=$source} | ConvertTo-Json -Compress
