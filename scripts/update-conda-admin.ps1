$ErrorActionPreference = "Stop"

$Conda = if ($env:CONDA_EXE) { $env:CONDA_EXE } else { "C:\ProgramData\Anaconda3\Scripts\conda.exe" }
if (-not (Test-Path $Conda)) {
    throw "Conda not found at $Conda"
}

& $Conda update -n base -c defaults conda -y
