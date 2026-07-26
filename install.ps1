<#
.SYNOPSIS
Installs the Cinema 4D skills from this repository for Claude Code and Codex.

.DESCRIPTION
Copies every skill directory next to this script into the skills directory of
each assistant that is present on this machine. Existing skills are left alone
unless -Force is passed, and a skill that is a symlink or junction is never
overwritten, because that would write through the link into its source
repository.

.EXAMPLE
.\install.ps1

.EXAMPLE
.\install.ps1 -Force
#>
[CmdletBinding()]
param(
    [string]$ClaudeSkillsPath = (Join-Path $env:USERPROFILE ".claude\skills"),
    [string]$CodexSkillsPath = (Join-Path $env:USERPROFILE ".codex\skills"),
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$source = $PSScriptRoot

$skills = @(
    Get-ChildItem -LiteralPath $source -Directory |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "SKILL.md") -PathType Leaf } |
        Sort-Object Name
)
if ($skills.Count -eq 0) {
    throw "No skill directories found next to $source"
}

$targets = @()
foreach ($entry in @(
    @{ Name = "Claude Code"; Path = $ClaudeSkillsPath },
    @{ Name = "Codex"; Path = $CodexSkillsPath }
)) {
    # Install only where the assistant is actually set up.
    $parent = Split-Path -Parent $entry.Path
    if (Test-Path -LiteralPath $parent -PathType Container) {
        $targets += $entry
    }
}

if ($targets.Count -eq 0) {
    Write-Host "Neither ~\.claude nor ~\.codex was found. Install Claude Code or Codex first."
    exit 1
}

$installed = 0
$skipped = 0

foreach ($target in $targets) {
    if (-not (Test-Path -LiteralPath $target.Path -PathType Container)) {
        New-Item -ItemType Directory -Path $target.Path -Force | Out-Null
    }
    Write-Host ""
    Write-Host "$($target.Name): $($target.Path)"

    foreach ($skill in $skills) {
        $destination = Join-Path $target.Path $skill.Name

        if (Test-Path -LiteralPath $destination) {
            $existing = Get-Item -LiteralPath $destination -Force
            if ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                Write-Host "  skip  $($skill.Name) - linked to another location, leaving it untouched"
                $skipped++
                continue
            }
            if (-not $Force) {
                Write-Host "  skip  $($skill.Name) - already installed (use -Force to overwrite)"
                $skipped++
                continue
            }
            Remove-Item -LiteralPath $destination -Recurse -Force
        }

        Copy-Item -LiteralPath $skill.FullName -Destination $destination -Recurse
        Get-ChildItem -LiteralPath $destination -Recurse -Force -Directory -Filter "__pycache__" |
            ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
        Write-Host "  ok    $($skill.Name)"
        $installed++
    }
}

Write-Host ""
Write-Host "Installed $installed, skipped $skipped. Restart the assistant to pick up new skills."
