param(
    [string]$PluginDir = $null,
    [switch]$SkipDependencies
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

if (Test-Path $dist) {
    Remove-Item -Recurse -Force $dist
}

python (Join-Path $root "tools\\build_plugin.py")

if (-not (Test-Path $dist)) {
    Write-Error "Bundle not found at $dist after build."
    exit 1
}

$pluginRoot = Join-Path $PluginDir "axe_usd_plugin"

if ($SkipDependencies -and -not (Test-Path (Join-Path $pluginRoot "dependencies"))) {
    Write-Warning "Dependencies folder not found; performing full install."
    $SkipDependencies = $false
}

New-Item -ItemType Directory -Path $PluginDir -Force | Out-Null
if (Test-Path (Join-Path $PluginDir "axe_usd_plugin.py")) {
    Remove-Item -Force (Join-Path $PluginDir "axe_usd_plugin.py")
}
if (-not $SkipDependencies -and (Test-Path $pluginRoot)) {
    Remove-Item -Recurse -Force $pluginRoot
}
if (Test-Path (Join-Path $PluginDir "axe_usd")) {
    Remove-Item -Recurse -Force (Join-Path $PluginDir "axe_usd")
}
if (Test-Path (Join-Path $PluginDir "AxeFX_usd_plugin.py")) {
    Remove-Item -Force (Join-Path $PluginDir "AxeFX_usd_plugin.py")
}
if (Test-Path (Join-Path $PluginDir "sp_usd_creator")) {
    Remove-Item -Recurse -Force (Join-Path $PluginDir "sp_usd_creator")
}
if ($SkipDependencies) {
    $src = Join-Path $dist "axe_usd_plugin"
    $dst = $pluginRoot
    New-Item -ItemType Directory -Path $dst -Force | Out-Null
    robocopy $src $dst /MIR /XD dependencies /NFL /NDL /NJH /NJS /NP | Out-Null
} else {
    Copy-Item -Path (Join-Path $dist "axe_usd_plugin") -Destination $PluginDir -Recurse -Force
}

Write-Host "Installed plugin to $PluginDir"
if ($SkipDependencies) {
    Write-Host "Skipped copying dependencies (dev mode)."
}
