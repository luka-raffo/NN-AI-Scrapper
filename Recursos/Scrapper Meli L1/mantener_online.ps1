# ============================================================
#  Guardian: mantiene la app SIEMPRE online.
#  - Levanta el backend (uvicorn) si no esta corriendo.
#  - Levanta el tunel Cloudflare y reinicia todo si se cae.
#  - Escribe el link publico actual en el Escritorio: "LINK DE LA APP.txt"
#  No necesita permisos de administrador.
# ============================================================
$ErrorActionPreference = 'SilentlyContinue'
$dir      = Split-Path -Parent $MyInvocation.MyCommand.Path
$linkFile = Join-Path ([Environment]::GetFolderPath('Desktop')) 'LINK DE LA APP.txt'
$cfLog    = Join-Path $env:TEMP 'cf_tunnel.log'
Set-Location $dir

function Test-Port($p) {
  try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', $p); $c.Close(); return $true }
  catch { return $false }
}

# Evita dos guardianes a la vez
$mutex = New-Object System.Threading.Mutex($false, 'Global\MeliKeeperGuardian')
if (-not $mutex.WaitOne(0)) { exit }

while ($true) {
  # 1) Backend
  if (-not (Test-Port 8000)) {
    Start-Process -WindowStyle Hidden -FilePath 'py' `
      -ArgumentList '-m','uvicorn','api:app','--host','0.0.0.0','--port','8000'
    for ($i=0; $i -lt 20 -and -not (Test-Port 8000); $i++) { Start-Sleep -Seconds 1 }
  }

  # 2) Tunel Cloudflare (captura su salida para leer la URL)
  if (Test-Path $cfLog) { Remove-Item $cfLog -Force }
  $proc = Start-Process -PassThru -WindowStyle Hidden -FilePath (Join-Path $dir 'cloudflared.exe') `
    -ArgumentList 'tunnel','--url','http://localhost:8000','--no-autoupdate' `
    -RedirectStandardError $cfLog

  # Esperar a que imprima la URL publica y guardarla en el Escritorio
  $url = $null
  for ($i=0; $i -lt 40 -and -not $url; $i++) {
    Start-Sleep -Seconds 1
    $m = Select-String -Path $cfLog -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($m) { $url = $m.Matches[0].Value }
  }
  if ($url) {
    Set-Content -Path $linkFile -Encoding UTF8 -Value @(
      'LINK PARA ABRIR Y COMPARTIR LA APP:',
      '',
      $url,
      '',
      ('(actualizado ' + (Get-Date -Format 'yyyy-MM-dd HH:mm') + ')'),
      'Si el link no abre, esperá 1 minuto: el guardián lo reabre solo y actualiza este archivo.'
    )
  }

  # Esperar a que el tunel muera; cuando muere, el while reinicia todo
  if ($proc) { Wait-Process -Id $proc.Id }
  Start-Sleep -Seconds 3
}
