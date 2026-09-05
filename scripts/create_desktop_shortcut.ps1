$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$desktopDirectory = [Environment]::GetFolderPath('DesktopDirectory')
$shortcutPath = Join-Path $desktopDirectory 'Texas Investors.lnk'
$pythonWindowless = Join-Path $projectRoot '.venv/Scripts/pythonw.exe'
$launcher = Join-Path $projectRoot 'launch_app.py'
if (-not (Test-Path -LiteralPath $pythonWindowless)) { throw 'The project Python environment is missing.' }
$shortcutShell = New-Object -ComObject WScript.Shell
$shortcut = $shortcutShell.CreateShortcut($shortcutPath)
if ((Test-Path -LiteralPath $shortcutPath) -and $shortcut.TargetPath -ne $pythonWindowless) {
    throw 'An unrelated Texas Investors shortcut already exists. It was preserved.'
}
$shortcut.TargetPath = $pythonWindowless
$shortcut.Arguments = '"' + $launcher + '"'
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = 'Open the Texas Investors local property research app'
$shortcut.WindowStyle = 7
$shortcut.Save()
if (-not (Test-Path -LiteralPath $shortcutPath)) { throw 'Shortcut was not created.' }
Write-Output $shortcutPath
