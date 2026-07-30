$ErrorActionPreference = "Stop"

$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$outputRoot = Join-Path $projectRoot "dist"
$workRoot = Join-Path $projectRoot ".build\pyinstaller"
$appName = "Santri Exporta$([char]0x00E7)$([char]0x00F5)es"
$iconPath = Join-Path $projectRoot "src\santri_automation\resources\ui\assets\sh-app-icon.ico"

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name $appName `
  --icon $iconPath `
  --paths (Join-Path $projectRoot "src") `
  --add-data "$projectRoot\src\santri_automation\resources;santri_automation\resources" `
  --collect-all "webview" `
  --hidden-import "webview.platforms.edgechromium" `
  --distpath $outputRoot `
  --workpath $workRoot `
  --specpath $workRoot `
  (Join-Path $projectRoot "run_local_app.py")

$exePath = Join-Path $outputRoot "$appName.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
  throw "O executável não foi gerado."
}

$shell = New-Object -ComObject WScript.Shell
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "$appName.lnk"
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $projectRoot
$shortcut.IconLocation = "$exePath,0"
$shortcut.Description = "Automação local de exportações do Santri"
$shortcut.Save()

$legacyAppNames = @(
  "Santri Export",
  "Santri Exporta$([char]0x00C3)$([char]0x00A7)$([char]0x00C3)$([char]0x00B5)es"
)
foreach ($legacyAppName in $legacyAppNames) {
  $oldShortcutPath = Join-Path $desktopPath "$legacyAppName.lnk"
  if (Test-Path -LiteralPath $oldShortcutPath) {
    Remove-Item -LiteralPath $oldShortcutPath -Force
  }

  $oldExePath = Join-Path $outputRoot "$legacyAppName.exe"
  if (Test-Path -LiteralPath $oldExePath) {
    Remove-Item -LiteralPath $oldExePath -Force
  }
}

Write-Host "Executável: $exePath"
Write-Host "Atalho: $shortcutPath"
