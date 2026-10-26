# Programa herramientas/actualizar_desde_pc.py en Windows: 07:00 y 19:00.
# Si la PC está apagada a esa hora, corre apenas se encienda.
# Uso (PowerShell, sin permisos de administrador):
#   powershell -ExecutionPolicy Bypass -File herramientas\instalar_tarea.ps1
# Para quitarla: Unregister-ScheduledTask -TaskName "Chamba al Toque - actualizar" -Confirm:$false

$repo = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $repo ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) { throw "No encuentro $pythonw (crea el .venv primero)" }

$accion = New-ScheduledTaskAction -Execute $pythonw `
  -Argument "herramientas\actualizar_desde_pc.py --log" -WorkingDirectory $repo
$disparadores = @(
  New-ScheduledTaskTrigger -Daily -At "07:00"
  New-ScheduledTaskTrigger -Daily -At "19:00"
)
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
  -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "Chamba al Toque - actualizar" -Action $accion `
  -Trigger $disparadores -Settings $ajustes -Force `
  -Description "Descarga ofertas de Talento Perú desde esta PC y publica chambearhoy.toca.pe. Log: out\pc\actualizar.log" | Out-Null

Write-Host "Tarea instalada: 07:00 y 19:00. Log en $repo\out\pc\actualizar.log"
