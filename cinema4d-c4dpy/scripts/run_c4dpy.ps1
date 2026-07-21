<#
Safe headless run of a Cinema 4D Python script via c4dpy (no GUI).
- adds the license argument (without it c4dpy hangs on licensing);
- redirects stdout/stderr to files;
- waits for the __C4DPY_SCRIPT_DONE__ marker (or process exit) with a timeout;
- force-kills the whole c4dpy process tree afterwards.

Example:
  powershell -NoProfile -ExecutionPolicy Bypass -File run_c4dpy.ps1 `
    -Script C:\path\probe.py -StdoutPath C:\path\out.txt -TimeoutSec 300
#>
param(
    [Parameter(Mandatory = $true)][string]$Script,
    [string[]]$ScriptArgs = @(),
    [Parameter(Mandatory = $true)][string]$C4dpyExe,
    [string]$LicenseArg = "g_licenseModel=LICENSEMODEL::MAXONAPP",
    [string]$SuccessPattern = "__C4DPY_SCRIPT_DONE__",
    [int]$TimeoutSec = 600,
    [string]$StdoutPath = "",
    [string]$StderrPath = ""
)
$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $C4dpyExe)) { throw "c4dpy.exe not found: $C4dpyExe" }
if (-not (Test-Path -LiteralPath $Script))   { throw "script not found: $Script" }
$Script = (Resolve-Path -LiteralPath $Script).Path
$C4dpyExe = (Resolve-Path -LiteralPath $C4dpyExe).Path
$dir = Split-Path -Parent $Script
if (-not $StdoutPath) { $StdoutPath = Join-Path $dir "c4dpy_stdout.txt" }
if (-not $StderrPath) { $StderrPath = Join-Path $dir "c4dpy_stderr.txt" }
$stdoutDir = Split-Path -Parent $StdoutPath
$stderrDir = Split-Path -Parent $StderrPath
if ($stdoutDir) { New-Item -ItemType Directory -Force -Path $stdoutDir | Out-Null }
if ($stderrDir) { New-Item -ItemType Directory -Force -Path $stderrDir | Out-Null }

function Quote([string]$v) {
    if ($null -eq $v) { return '""' }
    $e = $v.Replace('\', '\\').Replace('"', '\"')
    if ($e -match '\s|["]') { return '"' + $e + '"' } else { return $e }
}
function Stop-OwnedTree([int]$procId) {
    foreach ($c in @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $procId" -ErrorAction SilentlyContinue)) {
        Stop-OwnedTree ([int]$c.ProcessId)
    }
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}

$argLine = (@($LicenseArg, $Script) + $ScriptArgs | ForEach-Object { Quote $_ }) -join " "
Write-Host "c4dpy: $Script"
$proc = Start-Process -FilePath $C4dpyExe -ArgumentList $argLine `
    -RedirectStandardOutput $StdoutPath -RedirectStandardError $StderrPath `
    -WindowStyle Hidden -PassThru
Write-Host "PID: $($proc.Id)  stdout: $StdoutPath"

$deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSec)
$done = $false
try {
    while ($true) {
        if ($SuccessPattern -and (Test-Path -LiteralPath $StdoutPath)) {
            if (Select-String -LiteralPath $StdoutPath -SimpleMatch -Pattern $SuccessPattern -Quiet) {
                $done = $true; Write-Host "done (marker found)"; break
            }
        }
        if ($proc.WaitForExit(300)) { break }
        if ([DateTime]::UtcNow -ge $deadline) { Write-Warning "timeout ${TimeoutSec}s"; break }
    }
} finally {
    Stop-OwnedTree $proc.Id
}
if (-not $done) {
    throw "c4dpy success marker not found; inspect stdout/stderr: $StdoutPath | $StderrPath"
}
