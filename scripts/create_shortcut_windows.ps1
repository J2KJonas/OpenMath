$WshShell = New-Object -ComObject WScript.Shell
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoDir = Split-Path -Parent $scriptDir
$desktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$startMenuPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Programs)

$targetPath = Join-Path $repoDir "run.bat"
$iconPath = Join-Path $repoDir "resources\AppIcon.ico"

# Desktop Shortcut
$desktopShortcut = $WshShell.CreateShortcut((Join-Path $desktopPath "OpenMath.lnk"))
$desktopShortcut.TargetPath = $targetPath
$desktopShortcut.WorkingDirectory = $repoDir
$desktopShortcut.IconLocation = "$iconPath,0"
$desktopShortcut.Description = "OpenMath CAS Calculator"
$desktopShortcut.Save()
Write-Host "Created Desktop shortcut: $(Join-Path $desktopPath 'OpenMath.lnk')"

# Start Menu Shortcut
$startMenuShortcut = $WshShell.CreateShortcut((Join-Path $startMenuPath "OpenMath.lnk"))
$startMenuShortcut.TargetPath = $targetPath
$startMenuShortcut.WorkingDirectory = $repoDir
$startMenuShortcut.IconLocation = "$iconPath,0"
$startMenuShortcut.Description = "OpenMath CAS Calculator"
$startMenuShortcut.Save()
Write-Host "Created Start Menu shortcut: $(Join-Path $startMenuPath 'OpenMath.lnk')"
Write-Host "Done!"