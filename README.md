<!-- retired-notice:start -->
> **Retired experiment, kept for reference.** The living project is [kody-w/RAPP](https://github.com/kody-w/RAPP).
<!-- retired-notice:end -->

# RAPP Desktop

<!-- rapp1:network-header:start -->
[![RAPP/1](https://kody-w.github.io/rapp-hive-public/portfolio/badges/RAPP_Desktop.svg)](https://github.com/kody-w/rapp-hive-public/blob/main/portfolio/repos/RAPP_Desktop.md) · **New to RAPP?** [Start here: get your Brainstem →](https://github.com/kody-w/rapp-installer#start-here)
<!-- rapp1:network-header:end -->

Native desktop application for the RAPP ecosystem. Browse agents, install skills, clone implementations, and manage your AI projects - all from a beautiful native UI.

## Install

**Via RAPP Installer (Recommended):**
```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/kody-w/rapp-installer/main/install.sh | bash

# Windows
irm https://raw.githubusercontent.com/kody-w/rapp-installer/main/install.ps1 | iex
```

**Build from Source:**
```bash
# Prerequisites: Node.js 18+, Rust, Cargo

git clone https://github.com/kody-w/RAPP_Desktop.git
cd RAPP_Desktop
npm install
npm run tauri build
```

## Features

- **RAPP Store** - Browse and install agents & skills
- **RAPP Hub** - Discover and clone complete implementations
- **Project Management** - Create and manage your RAPP projects
- **One-Click Install** - Install dependencies with a single click
- **Native Performance** - Built with Tauri + Rust

## Screenshots

```
┌─────────────────────────────────────────────────────────────┐
│  🤖 RAPP                                                    │
├──────────────┬──────────────────────────────────────────────┤
│              │                                              │
│  🏠 Home     │    Welcome to RAPP                          │
│  📦 Store    │                                              │
│  🌐 Hub      │    ┌──────┐  ┌──────┐  ┌──────┐            │
│  📁 Projects │    │ Store│  │  Hub │  │ New  │            │
│  ⚙️ Settings │    └──────┘  └──────┘  └──────┘            │
│              │                                              │
└──────────────┴──────────────────────────────────────────────┘
```

## Architecture

```
RAPP Desktop
    │
    ├── Tauri (Rust) ─── System Integration
    │                    └── File System, Process, HTTP
    │
    └── React (TypeScript) ─── User Interface
                               └── Store, Hub, Projects
```

## RAPP Ecosystem

| Component | Description |
|-----------|-------------|
| **[RAPP Desktop](https://github.com/kody-w/RAPP_Desktop)** | This app - native GUI |
| **[RAPP Installer](https://github.com/kody-w/rapp-installer)** | Bootstrapper & Azure deploy |
| **[RAPP Hub](https://github.com/kody-w/RAPP_Hub)** | Implementation registry |
| **[RAPP Store](https://github.com/kody-w/RAPP_Store)** | Agent & skill packages |

## Development

```bash
# Install dependencies
npm install

# Run in development mode
npm run tauri dev

# Build for production
npm run tauri build
```

## License

Apache 2.0
