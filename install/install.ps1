#
# RAPP Desktop Installer - Windows
#
# One-line install (Run in PowerShell as Administrator):
#   irm https://raw.githubusercontent.com/kody-w/RAPP_Desktop/main/install/install.ps1 | iex
#

$ErrorActionPreference = "Stop"

# PowerShell 5.x compatible null coalescing
$RAPP_VERSION = if ($env:RAPP_VERSION) { $env:RAPP_VERSION } else { "latest" }
$RAPP_HOME = "$env:USERPROFILE\.rapp"
$RAPP_INSTALL_DIR = "$RAPP_HOME\app"

# Colors
function Log { param($msg) Write-Host "[RAPP] " -ForegroundColor Blue -NoNewline; Write-Host $msg }
function Success { param($msg) Write-Host "[RAPP] " -ForegroundColor Green -NoNewline; Write-Host $msg }
function Warn { param($msg) Write-Host "[RAPP] " -ForegroundColor Yellow -NoNewline; Write-Host $msg }
function Error { param($msg) Write-Host "[RAPP] " -ForegroundColor Red -NoNewline; Write-Host $msg; exit 1 }

# Banner
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Blue
Write-Host "║                                                          ║" -ForegroundColor Blue
Write-Host "║    " -ForegroundColor Blue -NoNewline
Write-Host "RAPP Desktop Installer" -ForegroundColor Green -NoNewline
Write-Host "                               ║" -ForegroundColor Blue
Write-Host "║    Rapid AI Agent Production Pipeline                    ║" -ForegroundColor Blue
Write-Host "║                                                          ║" -ForegroundColor Blue
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Blue
Write-Host ""

# Check if running as admin
function Test-Admin {
    $currentUser = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentUser.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Install Chocolatey if not present
function Install-Chocolatey {
    if (!(Get-Command choco -ErrorAction SilentlyContinue)) {
        Log "Installing Chocolatey package manager..."
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        Success "Chocolatey installed"
    } else {
        Success "Chocolatey already installed"
    }
}

# Install Rust
function Install-Rust {
    if (Get-Command cargo -ErrorAction SilentlyContinue) {
        Success "Rust already installed: $(rustc --version)"
    } else {
        Log "Installing Rust..."

        # Download rustup-init
        $rustupUrl = "https://win.rustup.rs/x86_64"
        $rustupPath = "$env:TEMP\rustup-init.exe"
        Invoke-WebRequest -Uri $rustupUrl -OutFile $rustupPath

        # Install Rust
        & $rustupPath -y --default-toolchain stable
        $env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"

        Success "Rust installed: $(rustc --version)"
    }
}

# Install Node.js
function Install-Node {
    if (Get-Command node -ErrorAction SilentlyContinue) {
        Success "Node.js already installed: $(node --version)"
    } else {
        Log "Installing Node.js..."
        choco install nodejs-lts -y
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        Success "Node.js installed: $(node --version)"
    }
}

# Install Python
function Install-Python {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        Success "Python already installed: $(python --version)"
    } else {
        Log "Installing Python..."
        choco install python311 -y
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        Success "Python installed: $(python --version)"
    }
}

# Install Git
function Install-Git {
    if (Get-Command git -ErrorAction SilentlyContinue) {
        Success "Git already installed: $(git --version)"
    } else {
        Log "Installing Git..."
        choco install git -y
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        Success "Git installed"
    }
}

# Install Visual Studio Build Tools
function Install-BuildTools {
    Log "Checking Visual Studio Build Tools..."

    # Check if already installed
    $vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vsWhere) {
        $vsPath = & $vsWhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($vsPath) {
            Success "Visual Studio Build Tools already installed"
            return
        }
    }

    Log "Installing Visual Studio Build Tools (this may take a while)..."
    choco install visualstudio2022buildtools --package-parameters "--add Microsoft.VisualStudio.Workload.VCTools --includeRecommended" -y

    Success "Visual Studio Build Tools installed"
}

# Install WebView2 Runtime
function Install-WebView2 {
    $webview2 = Get-ItemProperty -Path "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" -ErrorAction SilentlyContinue
    if ($webview2) {
        Success "WebView2 Runtime already installed"
    } else {
        Log "Installing WebView2 Runtime..."
        choco install webview2-runtime -y
        Success "WebView2 Runtime installed"
    }
}

# Clone or update RAPP Desktop
function Get-RappDesktop {
    Log "Setting up RAPP Desktop..."

    New-Item -ItemType Directory -Force -Path $RAPP_HOME | Out-Null

    if (Test-Path $RAPP_INSTALL_DIR) {
        Log "Updating existing installation..."
        Set-Location $RAPP_INSTALL_DIR
        git pull origin main
    } else {
        Log "Cloning RAPP Desktop..."
        git clone https://github.com/kody-w/RAPP_Desktop.git $RAPP_INSTALL_DIR
        Set-Location $RAPP_INSTALL_DIR
    }

    Success "RAPP Desktop source ready"
}

# Build RAPP Desktop
function Build-RappDesktop {
    Log "Building RAPP Desktop (this may take several minutes)..."
    Set-Location $RAPP_INSTALL_DIR

    # Refresh PATH for new installations
    $env:Path = "$env:USERPROFILE\.cargo\bin;" + [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

    # Install npm dependencies
    npm install

    # Build release
    npm run tauri build

    Success "RAPP Desktop built successfully"
}

# Install RAPP OS Python dependencies
function Install-RappOS {
    Log "Setting up RAPP OS..."

    Set-Location "$RAPP_INSTALL_DIR\rapp_os"

    # Create virtual environment
    python -m venv "$RAPP_HOME\venv"
    & "$RAPP_HOME\venv\Scripts\Activate.ps1"

    # Install dependencies
    pip install --upgrade pip
    pip install -r requirements.txt

    Success "RAPP OS dependencies installed"
}

# Setup directory structure
function Setup-Directories {
    Log "Creating RAPP directories..."

    $dirs = @(
        "$RAPP_HOME\agents",
        "$RAPP_HOME\skills",
        "$RAPP_HOME\projects",
        "$RAPP_HOME\contexts",
        "$RAPP_HOME\memory"
    )

    foreach ($dir in $dirs) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }

    Success "RAPP directories created"
}

# Create shortcuts and launcher
function Create-Launcher {
    Log "Creating launchers..."

    # Find the built executable
    $exePath = "$RAPP_INSTALL_DIR\src-tauri\target\release\rapp-desktop.exe"

    if (Test-Path $exePath) {
        # Create Start Menu shortcut
        $startMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
        $shortcutPath = "$startMenu\RAPP Desktop.lnk"

        $WshShell = New-Object -comObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut($shortcutPath)
        $Shortcut.TargetPath = $exePath
        $Shortcut.WorkingDirectory = $RAPP_INSTALL_DIR
        $Shortcut.Description = "RAPP Desktop - AI Agent Production Pipeline"
        $Shortcut.Save()

        # Create Desktop shortcut
        $desktopPath = "$env:USERPROFILE\Desktop\RAPP Desktop.lnk"
        $Shortcut = $WshShell.CreateShortcut($desktopPath)
        $Shortcut.TargetPath = $exePath
        $Shortcut.WorkingDirectory = $RAPP_INSTALL_DIR
        $Shortcut.Description = "RAPP Desktop - AI Agent Production Pipeline"
        $Shortcut.Save()

        Success "Shortcuts created"
    }

    # Create CLI launcher for RAPP OS
    $launcherContent = @"
@echo off
call "$RAPP_HOME\venv\Scripts\activate.bat"
python "$RAPP_INSTALL_DIR\rapp_os\rapp_os.py" %*
"@
    Set-Content -Path "$RAPP_HOME\rapp.bat" -Value $launcherContent

    # Add to PATH
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$RAPP_HOME*") {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$RAPP_HOME", "User")
        Log "Added RAPP to PATH"
    }
}

# Main installation
function Main {
    if (!(Test-Admin)) {
        Warn "Some features require Administrator privileges."
        Warn "Consider running this script as Administrator for full installation."
        Write-Host ""
    }

    Install-Chocolatey
    Install-Git
    Install-Rust
    Install-Node
    Install-Python
    Install-BuildTools
    Install-WebView2

    Get-RappDesktop
    Build-RappDesktop
    Install-RappOS
    Setup-Directories
    Create-Launcher

    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║                                                          ║" -ForegroundColor Green
    Write-Host "║    " -ForegroundColor Green -NoNewline
    Write-Host "RAPP Desktop Installed Successfully!" -ForegroundColor Green -NoNewline
    Write-Host "                 ║" -ForegroundColor Green
    Write-Host "║                                                          ║" -ForegroundColor Green
    Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""

    Log "Launch RAPP Desktop from the Start Menu or Desktop shortcut"
    Log "Or run RAPP OS from terminal: rapp"
    Write-Host ""
}

Main
