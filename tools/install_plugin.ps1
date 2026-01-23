param(
    [string]$PluginDir = $null
)

$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist"

if (-not $PluginDir) {
    $documents = [Environment]::GetFolderPath([Environment+SpecialFolder]::MyDocuments)
    if (-not $documents) {
        Write-Error "Could not resolve the Documents folder. Pass -PluginDir explicitly."
        exit 1
    }
    $PluginDir = Join-Path $documents "Adobe\Adobe Substance 3D Painter\python\plugins"
}

if (-not (Test-Path $dist)) {
    Write-Error "Bundle not found at $dist. Run tools\\build_plugin.py first."
    exit 1
}

New-Item -ItemType Directory -Path $PluginDir -Force | Out-Null
if (Test-Path (Join-Path $PluginDir "axe_usd")) {
    Remove-Item -Recurse -Force (Join-Path $PluginDir "axe_usd")
}
if (Test-Path (Join-Path $PluginDir "axe_usd_plugin.py")) {
    Remove-Item -Force (Join-Path $PluginDir "axe_usd_plugin.py")
}
if (Test-Path (Join-Path $PluginDir "AxeFX_usd_plugin.py")) {
    Remove-Item -Force (Join-Path $PluginDir "AxeFX_usd_plugin.py")
}
if (Test-Path (Join-Path $PluginDir "sp_usd_creator")) {
    Remove-Item -Recurse -Force (Join-Path $PluginDir "sp_usd_creator")
}
Copy-Item -Path (Join-Path $dist "axe_usd_plugin.py") -Destination $PluginDir -Force
Copy-Item -Path (Join-Path $dist "axe_usd") -Destination $PluginDir -Recurse -Force

Write-Host "Installed plugin to $PluginDir"
