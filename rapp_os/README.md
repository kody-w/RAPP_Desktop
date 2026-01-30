# RAPP OS

Local operating system layer for RAPP Desktop. Provides a unified endpoint with GUID-based routing to all RAPP agents and system integrations.

## Architecture

```
User Request → Brain Stem → GUID Router → Selected Agent(s) → Response
```

### GUIDs

- **User GUID**: Identifies the user (memory isolation)
- **Session GUID**: Identifies the conversation session
- **Context GUID**: Identifies the agent configuration being used

## Components

### Brain Stem (`core/brain_stem.py`)
The unified RAPP endpoint. Routes requests to appropriate agents based on GUID selection. No need for multiple deployments - one brain stem orchestrates everything.

### Local Server (`core/local_server.py`)
HTTP REST API for RAPP Desktop integration. Runs on port 7071 by default.

**Endpoints:**
- `POST /api/rapp` - Main chat endpoint
- `GET /health` - Health check
- `GET /agents` - List available agents
- `GET /contexts` - List available contexts
- `GET /reload` - Reload agents and contexts

### iMessage Bridge (`bridges/imessage_bridge.py`)
Remote control via text messages. Monitors iMessage database for incoming messages and routes commands to brain stem.

**Requirements:**
- macOS only
- Full Disk Access permission for Terminal/Python

**Configuration:**
Edit `~/.rapp/imessage_bridge.json`:
```json
{
  "allowed_numbers": ["+15551234567"],
  "prefix": "/rapp"
}
```

### System Agent (`agents/system_agent.py`)
Local system integration:
- Open applications
- Send notifications
- Read/write clipboard
- Send iMessages
- Run Shortcuts
- Get system info

### File Agent (`agents/system_agent.py`)
Secure file operations within home directory:
- Read files
- Write files
- List directories
- Delete files

## Usage

### Standalone
```bash
cd rapp_os
pip install -r requirements.txt
python rapp_os.py
```

### With Options
```bash
python rapp_os.py --port 8080           # Custom port
python rapp_os.py --imessage            # Enable iMessage bridge
python rapp_os.py --no-server           # Disable HTTP server
```

### With RAPP Desktop
The Tauri desktop application automatically manages RAPP OS. Use the "Start RAPP OS" button in the Chat page or Settings.

## Environment Variables

For AI capabilities, set these in your environment or `~/.rapp/config.env`:

```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o

# Or OpenAI
OPENAI_API_KEY=your-key
```

## Adding Custom Agents

1. Create a Python file in `~/.rapp/agents/` with `_agent.py` suffix
2. Define a class that inherits pattern:
   ```python
   class MyAgent:
       def __init__(self):
           self.name = 'MyAgent'
           self.metadata = {
               "name": self.name,
               "description": "What this agent does",
               "parameters": {...}
           }

       def get_function_definition(self):
           return self.metadata

       def perform(self, **kwargs):
           return "result"
   ```
3. Restart RAPP OS or call `/reload` endpoint

## File Locations

- **Agents**: `~/.rapp/agents/`
- **Skills**: `~/.rapp/skills/`
- **Contexts**: `~/.rapp/contexts/`
- **Memory**: `~/.rapp/memory/`
- **Config**: `~/.rapp/rapp_os.json`
