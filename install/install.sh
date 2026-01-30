#!/bin/bash
#
# RAPP Desktop Installer - macOS/Linux
#
# One-line install:
#   curl -fsSL https://raw.githubusercontent.com/kody-w/RAPP_Desktop/main/install/install.sh | bash
#

set -e

RAPP_VERSION="${RAPP_VERSION:-latest}"
RAPP_HOME="$HOME/.rapp"
RAPP_INSTALL_DIR="$HOME/.rapp/app"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[RAPP]${NC} $1"; }
success() { echo -e "${GREEN}[RAPP]${NC} $1"; }
warn() { echo -e "${YELLOW}[RAPP]${NC} $1"; }
error() { echo -e "${RED}[RAPP]${NC} $1"; exit 1; }

# Banner
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                          ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}    ${GREEN}RAPP Desktop Installer${NC}                               ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}    Rapid AI Agent Production Pipeline                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                          ${BLUE}║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*) OS="macos" ;;
        Linux*)  OS="linux" ;;
        *)       error "Unsupported operating system" ;;
    esac
    log "Detected OS: $OS"
}

# Check and install Rust
install_rust() {
    if command -v cargo &> /dev/null; then
        success "Rust already installed: $(rustc --version)"
    else
        log "Installing Rust..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source "$HOME/.cargo/env"
        success "Rust installed: $(rustc --version)"
    fi
}

# Check and install Node.js
install_node() {
    if command -v node &> /dev/null; then
        success "Node.js already installed: $(node --version)"
    else
        log "Installing Node.js..."
        if [ "$OS" = "macos" ]; then
            if command -v brew &> /dev/null; then
                brew install node
            else
                # Install nvm
                curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
                export NVM_DIR="$HOME/.nvm"
                [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
                nvm install --lts
            fi
        else
            # Linux - use nvm
            curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
            export NVM_DIR="$HOME/.nvm"
            [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
            nvm install --lts
        fi
        success "Node.js installed: $(node --version)"
    fi
}

# Check and install Python
install_python() {
    if command -v python3 &> /dev/null; then
        success "Python already installed: $(python3 --version)"
    else
        log "Installing Python..."
        if [ "$OS" = "macos" ]; then
            if command -v brew &> /dev/null; then
                brew install python@3.11
            else
                error "Please install Homebrew first: https://brew.sh"
            fi
        else
            sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv
        fi
        success "Python installed: $(python3 --version)"
    fi
}

# Install system dependencies
install_dependencies() {
    log "Installing system dependencies..."

    if [ "$OS" = "macos" ]; then
        # macOS dependencies for Tauri
        if ! command -v brew &> /dev/null; then
            warn "Homebrew not found. Installing..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        # Tauri needs these on macOS
        xcode-select --install 2>/dev/null || true
    else
        # Linux dependencies for Tauri
        sudo apt-get update
        sudo apt-get install -y \
            libwebkit2gtk-4.0-dev \
            libgtk-3-dev \
            libayatana-appindicator3-dev \
            librsvg2-dev \
            build-essential \
            curl \
            wget \
            file \
            libssl-dev
    fi

    success "System dependencies installed"
}

# Clone or update RAPP Desktop
clone_rapp() {
    log "Setting up RAPP Desktop..."

    mkdir -p "$RAPP_HOME"

    if [ -d "$RAPP_INSTALL_DIR" ]; then
        log "Updating existing installation..."
        cd "$RAPP_INSTALL_DIR"
        git pull origin main
    else
        log "Cloning RAPP Desktop..."
        git clone https://github.com/kody-w/RAPP_Desktop.git "$RAPP_INSTALL_DIR"
        cd "$RAPP_INSTALL_DIR"
    fi

    success "RAPP Desktop source ready"
}

# Build RAPP Desktop
build_rapp() {
    log "Building RAPP Desktop (this may take a few minutes)..."
    cd "$RAPP_INSTALL_DIR"

    # Install npm dependencies
    npm install

    # Source cargo if needed
    [ -f "$HOME/.cargo/env" ] && source "$HOME/.cargo/env"

    # Build release
    npm run tauri build

    success "RAPP Desktop built successfully"
}

# Install RAPP OS Python dependencies
install_rapp_os() {
    log "Setting up RAPP OS..."

    cd "$RAPP_INSTALL_DIR/rapp_os"

    # Create virtual environment
    python3 -m venv "$RAPP_HOME/venv"
    source "$RAPP_HOME/venv/bin/activate"

    # Install dependencies
    pip install --upgrade pip
    pip install -r requirements.txt

    success "RAPP OS dependencies installed"
}

# Create launch script
create_launcher() {
    log "Creating launcher..."

    # Find the built app
    if [ "$OS" = "macos" ]; then
        APP_PATH="$RAPP_INSTALL_DIR/src-tauri/target/release/bundle/macos/RAPP Desktop.app"
        if [ -d "$APP_PATH" ]; then
            # Copy to Applications
            cp -r "$APP_PATH" /Applications/ 2>/dev/null || true
            success "RAPP Desktop installed to /Applications"
        fi
    else
        BINARY_PATH="$RAPP_INSTALL_DIR/src-tauri/target/release/rapp-desktop"
        if [ -f "$BINARY_PATH" ]; then
            # Create desktop entry
            mkdir -p "$HOME/.local/share/applications"
            cat > "$HOME/.local/share/applications/rapp-desktop.desktop" << EOF
[Desktop Entry]
Name=RAPP Desktop
Comment=Rapid AI Agent Production Pipeline
Exec=$BINARY_PATH
Icon=$RAPP_INSTALL_DIR/src-tauri/icons/icon.png
Terminal=false
Type=Application
Categories=Development;
EOF
            success "RAPP Desktop launcher created"
        fi
    fi

    # Create CLI launcher for RAPP OS
    cat > "$RAPP_HOME/rapp" << EOF
#!/bin/bash
source "$RAPP_HOME/venv/bin/activate"
python "$RAPP_INSTALL_DIR/rapp_os/rapp_os.py" "\$@"
EOF
    chmod +x "$RAPP_HOME/rapp"

    # Add to PATH suggestion
    echo ""
    log "Add RAPP to your PATH by adding this to your shell profile:"
    echo -e "  ${YELLOW}export PATH=\"\$PATH:$RAPP_HOME\"${NC}"
}

# Setup directory structure
setup_directories() {
    log "Creating RAPP directories..."
    mkdir -p "$RAPP_HOME/agents"
    mkdir -p "$RAPP_HOME/skills"
    mkdir -p "$RAPP_HOME/projects"
    mkdir -p "$RAPP_HOME/contexts"
    mkdir -p "$RAPP_HOME/memory"
    success "RAPP directories created"
}

# Main installation
main() {
    detect_os
    install_dependencies
    install_rust
    install_node
    install_python
    clone_rapp
    build_rapp
    install_rapp_os
    setup_directories
    create_launcher

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}                                                          ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}    ${GREEN}RAPP Desktop Installed Successfully!${NC}                 ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}                                                          ${GREEN}║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    if [ "$OS" = "macos" ]; then
        log "Launch RAPP Desktop from /Applications"
    else
        log "Launch RAPP Desktop from your application menu"
    fi

    log "Or run RAPP OS from terminal: $RAPP_HOME/rapp"
    echo ""
}

main "$@"
