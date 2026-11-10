# Nirbhar AI — Start All Services
$python = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } elseif (Test-Path "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe") { "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" } elseif (Test-Path "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe") { "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe" } else { "python" }

Write-Host "Starting Nirbhar AI services..." -ForegroundColor Cyan

# 1. Core API (Port 8000)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\api'; & '$python' -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

# 2. Vendor Gateway (Port 8001)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\vendor-gateway'; & '$python' -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload"

# 3. Web UI (Port 3000)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\web'; npm run dev"

# 4. Open Browser
Start-Sleep -Seconds 3
Start-Process "http://localhost:3000"

Write-Host "All services started! UI is live at http://localhost:3000" -ForegroundColor Green

