# smoke_walk.ps1 — end-to-end pipeline smoke test on the real machine.
#
# Runs DC -> Zoo build-kit -> Patina -> Zoo dress and GATES each stage: if a
# stage doesn't produce the file the next one needs, it stops with a clear
# message instead of cascading. Proves the whole flow is repeatable before you
# build levels on top of it.
#
# Set the paths for YOUR machine, then run:  .\smoke_walk.ps1
# (or override any path:  .\smoke_walk.ps1 -Spec specs\bank.json )

param(
  [string]$Lux     = "C:\Projects\lux",
  [string]$Patina  = "C:\Projects\patina",
  [string]$Zoo     = "C:\Projects\zoo",
  [string]$DC      = "C:\Projects\deli_counter",
  [string]$Spec    = "specs\corner_deli_heist_01.json",   # a garage-free spec
  [string]$BlenderRoot = "C:\blender",
  [string]$GodotRoot   = "C:\Godot\4.7",
  [switch]$NoGodot                                        # skip opening the editor
)

$ErrorActionPreference = "Stop"
function Ok($m)   { Write-Host "  [PASS] $m" -ForegroundColor Green }
function Bad($m)  { Write-Host "  [FAIL] $m" -ForegroundColor Red; exit 1 }
function Stage($m){ Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Need($p, $what) { if (Test-Path $p) { Ok "$what" } else { Bad "$what — missing: $p" } }

Stage "0. Resolve tools"
$Blender = (Get-ChildItem $BlenderRoot -Recurse -Filter "blender.exe" -ErrorAction SilentlyContinue |
            Select-Object -First 1).FullName
$Godot   = (Get-ChildItem $GodotRoot -Recurse -Filter "Godot*.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -notlike "*console*" } | Select-Object -First 1).FullName
if ($Blender) { Ok "Blender: $Blender" } else { Bad "Blender.exe not found under $BlenderRoot" }
if ($Godot)   { Ok "Godot: $Godot" }     elseif (-not $NoGodot) { Bad "Godot exe not found under $GodotRoot" }
$Walk = Join-Path $Lux "walk"
New-Item -ItemType Directory -Force -Path $Walk | Out-Null
$env:BLENDER = $Blender
# Clean prior run so stale files can't mask a failure.
Remove-Item "$Walk\gs*.*" -ErrorAction SilentlyContinue

Stage "1. Deli Counter — build the shell"
Push-Location $DC
python build.py $Spec --out "$Walk\gs.glb" --blender $Blender
Pop-Location
Need "$Walk\gs.glb"        "shell glb"
Need "$Walk\gs.slots.json" "slots manifest"

Stage "2. Zoo — build the module kit"
Push-Location $Zoo
& $Blender --background --python tools\zoo_cli.py -- --build-kit "$Walk\gs.slots.json" --theme delco --out $Walk
Pop-Location
# Zoo writes module glbs; at least one must appear (name pattern is <role>_<theme>_<style>).
$mods = Get-ChildItem $Walk -Filter "*.glb" | Where-Object { $_.Name -match "delco" }
if ($mods.Count -gt 0) { Ok "built $($mods.Count) delco module(s)" }
else { Bad "Zoo build-kit produced no delco modules (check for a missing species genome)" }

Stage "3. Patina — art-pass"
Push-Location $Patina
$pcmd = "patina"
if (-not (Get-Command patina -ErrorAction SilentlyContinue)) { $pcmd = "python -m patina.cli" }
Invoke-Expression "$pcmd `"$Walk\gs.glb`" --mode procedural --depth lux --slot-variation --anchors --dressing --preview --out `"$Walk\gs.patina.glb`""
Pop-Location
Need "$Walk\gs.patina.glb"           "styled glb"
Need "$Walk\gs.patina.preview.png"   "composite preview"
Need "$Walk\gs.patina.dressing.json" "dressing manifest"
Need "$Walk\gs.patina.instances.json" "per-slot instances"
Need "$Walk\gs.patina.json"          "patina manifest"

Stage "4. Headroom gate"
$man = Get-Content "$Walk\gs.patina.json" | ConvertFrom-Json
if ($man.depth) { Ok "manifest records depth = $($man.depth)" } else { Bad "manifest missing depth" }
# The dressing covers must all be non-collision.
$dr = Get-Content "$Walk\gs.patina.dressing.json" | ConvertFrom-Json
$bad = $dr.orders | Where-Object { $_.collision -ne "none" }
if (-not $bad) { Ok "$($dr.orders.Count) dressing orders, all collision:none" }
else { Bad "$($bad.Count) dressing order(s) not non-collision" }

Stage "5. Zoo — build the facade covers"
Push-Location $Zoo
& $Blender --background --python tools\zoo_cli.py -- --dress "$Walk\gs.patina.dressing.json" --theme delco --out $Walk
Pop-Location
$cover = Get-ChildItem $Walk -Filter "*dressing.glb" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($cover) { Ok "built covers: $($cover.Name)" } else { Bad "Zoo --dress produced no *_dressing.glb" }

Write-Host "`n====================================================" -ForegroundColor Cyan
Write-Host "SMOKE WALK PASSED — the full pipeline is repeatable." -ForegroundColor Green
Write-Host "Preview: $Walk\gs.patina.preview.png"
Write-Host "Building: $Walk\gs.patina.glb   Covers: $($cover.FullName)"

Invoke-Item "$Walk\gs.patina.preview.png"
if (-not $NoGodot) {
  Write-Host "`nOpening Lux in Godot — drop gs.patina.glb into a scene, add LuxRoot, apply delco_summer_afternoon." -ForegroundColor Yellow
  & $Godot --path $Lux
}
