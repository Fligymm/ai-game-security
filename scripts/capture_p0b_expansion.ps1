#requires -Version 5.1
<#
.SYNOPSIS
Capture one P0-B first-person POV expansion session with the old default model.

.DESCRIPTION
This only records the screen. It does NOT start CS2, start a CV agent, or send
mouse/keyboard input. Start CS2 (and for game_bot, the observer/Bot setup)
manually before running.

The script calls tools/capture_fps_pilot.py with explicit POV attestations and
then validates the new session with tools/check_fps_pilot.py --verify-hash.

.EXAMPLE
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType human -CaptureSource player_pov -OperatorId anon_h04

.EXAMPLE
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType game_bot -CaptureSource observer_followed_bot -OperatorId anon_b04
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet("human", "game_bot")]
    [string]$AgentType,

    [Parameter(Mandatory)]
    [ValidateSet("player_pov", "observer_followed_bot")]
    [string]$CaptureSource,

    [Parameter(Mandatory)]
    [ValidatePattern("^anon_[a-zA-Z0-9_]+$")]
    [string]$OperatorId,

    [ValidateRange(10, 300)]
    [int]$Duration = 60,

    [ValidateRange(10, 60)]
    [int]$Fps = 30,

    [string]$Scene = "static_target",
    [string]$MapName = "aim_botz",
    [string]$Weapon = "ak47",
    [double]$Sensitivity = 0.8,
    [int]$Fov = 90,
    [string]$OutputDir = "runs\captures\p0b_pilot",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Python environment not found: $python"
}

if ($AgentType -eq "human" -and $CaptureSource -ne "player_pov") {
    throw "human requires -CaptureSource player_pov"
}
if ($AgentType -eq "game_bot" -and $CaptureSource -ne "observer_followed_bot") {
    throw "game_bot requires -CaptureSource observer_followed_bot"
}

$captureArgs = @(
    "tools\capture_fps_pilot.py",
    "--agent-type", $AgentType,
    "--capture-source", $CaptureSource,
    "--view-mode", "first_person",
    "--scene", $Scene,
    "--map-name", $MapName,
    "--weapon", $Weapon,
    "--sensitivity", $Sensitivity,
    "--fov", $Fov,
    "--duration", $Duration,
    "--fps", $Fps,
    "--operator-id", $OperatorId,
    "--output-dir", $OutputDir,
    "--attest-pov",
    "--attest-experiment",
    "--confirm-offline"
)
if ($DryRun) { $captureArgs += "--dry-run" }

Push-Location $repo
try {
    Write-Host "[INFO] agent=$AgentType source=$CaptureSource operator=$OperatorId duration=${Duration}s fps=$Fps"
    & $python @captureArgs
    if ($LASTEXITCODE -ne 0) {
        throw "capture_fps_pilot failed with exit code $LASTEXITCODE"
    }
    if ($DryRun) {
        Write-Host "[INFO] dry-run complete; no session was created."
        return
    }

    $session = Get-ChildItem $OutputDir -Directory |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $session) {
        throw "no session directory found under $OutputDir"
    }
    Write-Host "[INFO] validating: $($session.FullName)"
    & $python "tools\check_fps_pilot.py" $session.FullName --verify-hash
    if ($LASTEXITCODE -ne 0) {
        throw "check_fps_pilot failed; inspect errors before using this session"
    }
    Write-Host "[OK] session validated: $($session.FullName)"
}
finally {
    Pop-Location
}