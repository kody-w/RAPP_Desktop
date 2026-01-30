#!/usr/bin/env python3
"""
RAPP Brain Stem - Unified Local Endpoint

Single endpoint that routes to any RAPP agent/implementation via GUID selection.
No need for multiple deployments - one brain stem orchestrates everything.

Architecture:
    User Request → GUID Router → Selected Agent(s) → Response

GUIDs:
    - User GUID: Identifies the user (memory isolation)
    - Session GUID: Identifies the conversation session
    - Agent GUID: Identifies which agent/implementation to use
    - Context GUID: Identifies the context/template being used
"""

import os
import sys
import json
import uuid
import logging
import importlib.util
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rapp_brain_stem")

# RAPP Home directory
RAPP_HOME = Path.home() / ".rapp"
AGENTS_DIR = RAPP_HOME / "agents"
SKILLS_DIR = RAPP_HOME / "skills"
PROJECTS_DIR = RAPP_HOME / "projects"
MEMORY_DIR = RAPP_HOME / "memory"
CONTEXTS_DIR = RAPP_HOME / "contexts"


@dataclass
class RappContext:
    """Represents a loaded RAPP context (agent configuration)."""
    guid: str
    name: str
    description: str
    agents: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    system_prompt: str = ""
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RappRequest:
    """Incoming request to the brain stem."""
    user_input: str
    user_guid: str = "default"
    session_guid: str = ""
    context_guid: str = "default"
    conversation_history: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RappResponse:
    """Response from the brain stem."""
    response: str
    voice_response: str = ""
    agent_logs: List[str] = field(default_factory=list)
    agents_used: List[str] = field(default_factory=list)
    session_guid: str = ""
    context_guid: str = ""


class AgentRegistry:
    """Registry of all available agents."""

    def __init__(self):
        self.agents: Dict[str, Any] = {}
        self.agent_metadata: Dict[str, Dict] = {}

    def load_agents(self):
        """Load all agents from the agents directory."""
        self.agents.clear()
        self.agent_metadata.clear()

        if not AGENTS_DIR.exists():
            AGENTS_DIR.mkdir(parents=True, exist_ok=True)
            return

        for agent_file in AGENTS_DIR.glob("*_agent.py"):
            if agent_file.name.startswith("_") or agent_file.name == "basic_agent.py":
                continue
            try:
                self._load_agent_file(agent_file)
            except Exception as e:
                logger.warning(f"Failed to load {agent_file.name}: {e}")

    def _load_agent_file(self, agent_file: Path):
        """Load a single agent file."""
        spec = importlib.util.spec_from_file_location(agent_file.stem, agent_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for name, obj in module.__dict__.items():
            if (isinstance(obj, type) and
                name.endswith("Agent") and
                name != "BasicAgent" and
                hasattr(obj, "perform")):
                instance = obj()
                agent_id = getattr(instance, 'name', name)
                self.agents[agent_id] = instance
                self.agent_metadata[agent_id] = getattr(instance, 'metadata', {})
                logger.info(f"Loaded agent: {agent_id}")

    def get_agent(self, agent_id: str):
        """Get an agent by ID."""
        return self.agents.get(agent_id)

    def list_agents(self) -> List[Dict]:
        """List all available agents."""
        return [
            {"id": aid, "metadata": meta}
            for aid, meta in self.agent_metadata.items()
        ]


class ContextManager:
    """Manages RAPP contexts (agent configurations)."""

    def __init__(self):
        self.contexts: Dict[str, RappContext] = {}
        self._ensure_default_context()

    def _ensure_default_context(self):
        """Ensure default context exists."""
        CONTEXTS_DIR.mkdir(parents=True, exist_ok=True)

        default_path = CONTEXTS_DIR / "default.json"
        if not default_path.exists():
            default_context = {
                "guid": "default",
                "name": "Default Context",
                "description": "Default RAPP context with all agents enabled",
                "agents": ["*"],  # All agents
                "skills": ["*"],  # All skills
                "system_prompt": "You are a helpful AI assistant powered by RAPP.",
                "config": {}
            }
            default_path.write_text(json.dumps(default_context, indent=2))

    def load_contexts(self):
        """Load all contexts from disk."""
        self.contexts.clear()

        for ctx_file in CONTEXTS_DIR.glob("*.json"):
            try:
                data = json.loads(ctx_file.read_text())
                ctx = RappContext(
                    guid=data.get("guid", ctx_file.stem),
                    name=data.get("name", ctx_file.stem),
                    description=data.get("description", ""),
                    agents=data.get("agents", ["*"]),
                    skills=data.get("skills", ["*"]),
                    system_prompt=data.get("system_prompt", ""),
                    config=data.get("config", {})
                )
                self.contexts[ctx.guid] = ctx
            except Exception as e:
                logger.warning(f"Failed to load context {ctx_file}: {e}")

    def get_context(self, guid: str) -> Optional[RappContext]:
        """Get a context by GUID."""
        return self.contexts.get(guid, self.contexts.get("default"))

    def create_context(self, name: str, agents: List[str], **kwargs) -> RappContext:
        """Create a new context."""
        guid = str(uuid.uuid4())[:8]
        ctx = RappContext(
            guid=guid,
            name=name,
            agents=agents,
            **kwargs
        )

        # Save to disk
        ctx_file = CONTEXTS_DIR / f"{guid}.json"
        ctx_file.write_text(json.dumps({
            "guid": ctx.guid,
            "name": ctx.name,
            "description": ctx.description,
            "agents": ctx.agents,
            "skills": ctx.skills,
            "system_prompt": ctx.system_prompt,
            "config": ctx.config
        }, indent=2))

        self.contexts[guid] = ctx
        return ctx

    def list_contexts(self) -> List[Dict]:
        """List all contexts."""
        return [
            {"guid": c.guid, "name": c.name, "description": c.description}
            for c in self.contexts.values()
        ]


class MemoryManager:
    """Manages user and session memory."""

    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def get_user_memory(self, user_guid: str) -> str:
        """Get memory for a user."""
        mem_file = MEMORY_DIR / f"user_{user_guid}.txt"
        if mem_file.exists():
            return mem_file.read_text()
        return ""

    def append_user_memory(self, user_guid: str, content: str):
        """Append to user memory."""
        mem_file = MEMORY_DIR / f"user_{user_guid}.txt"
        with open(mem_file, "a") as f:
            f.write(f"\n[{datetime.now().isoformat()}] {content}")

    def get_session_memory(self, session_guid: str) -> List[Dict]:
        """Get conversation history for a session."""
        mem_file = MEMORY_DIR / f"session_{session_guid}.json"
        if mem_file.exists():
            return json.loads(mem_file.read_text())
        return []

    def save_session_memory(self, session_guid: str, history: List[Dict]):
        """Save conversation history for a session."""
        mem_file = MEMORY_DIR / f"session_{session_guid}.json"
        mem_file.write_text(json.dumps(history, indent=2))


class RappBrainStem:
    """
    The unified RAPP endpoint - routes requests to appropriate agents
    based on GUID selection.
    """

    def __init__(self):
        self.agent_registry = AgentRegistry()
        self.context_manager = ContextManager()
        self.memory_manager = MemoryManager()

        # Load everything
        self.agent_registry.load_agents()
        self.context_manager.load_contexts()

        # AI client (configure based on available provider)
        self.ai_client = None
        self._init_ai_client()

    def _init_ai_client(self):
        """Initialize AI client based on available credentials."""
        # Try Azure OpenAI first
        if os.getenv("AZURE_OPENAI_ENDPOINT"):
            try:
                from openai import AzureOpenAI
                self.ai_client = AzureOpenAI(
                    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
                )
                self.model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
                logger.info("Using Azure OpenAI")
                return
            except Exception as e:
                logger.warning(f"Azure OpenAI init failed: {e}")

        # Fall back to OpenAI
        if os.getenv("OPENAI_API_KEY"):
            try:
                from openai import OpenAI
                self.ai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                self.model = os.getenv("OPENAI_MODEL", "gpt-4o")
                logger.info("Using OpenAI")
                return
            except Exception as e:
                logger.warning(f"OpenAI init failed: {e}")

        logger.warning("No AI client configured - agent-only mode")

    def reload(self):
        """Reload agents and contexts."""
        self.agent_registry.load_agents()
        self.context_manager.load_contexts()

    def process(self, request: RappRequest) -> RappResponse:
        """
        Process a request through the brain stem.

        Routes to appropriate agents based on context GUID.
        """
        # Ensure session GUID
        if not request.session_guid:
            request.session_guid = str(uuid.uuid4())

        # Get context
        context = self.context_manager.get_context(request.context_guid)
        if not context:
            context = self.context_manager.get_context("default")

        # Get applicable agents
        available_agents = self._get_agents_for_context(context)

        # Get user memory
        user_memory = self.memory_manager.get_user_memory(request.user_guid)

        # Build messages
        messages = self._build_messages(
            request, context, user_memory, available_agents
        )

        # Get agent function definitions
        functions = [
            agent.get_function_definition()
            for agent in available_agents.values()
            if hasattr(agent, 'get_function_definition')
        ]

        # Call AI
        response_text = ""
        agents_used = []
        agent_logs = []

        if self.ai_client and functions:
            try:
                response = self.ai_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    functions=functions if functions else None,
                    function_call="auto" if functions else None,
                    max_tokens=4096
                )

                msg = response.choices[0].message

                # Handle function calls
                if msg.function_call:
                    func_name = msg.function_call.name
                    func_args = json.loads(msg.function_call.arguments or "{}")

                    if func_name in available_agents:
                        agent = available_agents[func_name]
                        try:
                            result = agent.perform(**func_args)
                            agents_used.append(func_name)
                            agent_logs.append(f"{func_name}: {result[:200]}...")

                            # Get final response with agent result
                            messages.append({"role": "assistant", "content": None, "function_call": msg.function_call})
                            messages.append({"role": "function", "name": func_name, "content": str(result)})

                            final_response = self.ai_client.chat.completions.create(
                                model=self.model,
                                messages=messages,
                                max_tokens=4096
                            )
                            response_text = final_response.choices[0].message.content or ""
                        except Exception as e:
                            agent_logs.append(f"{func_name} error: {e}")
                            response_text = f"Agent error: {e}"
                    else:
                        response_text = msg.content or ""
                else:
                    response_text = msg.content or ""

            except Exception as e:
                logger.error(f"AI call failed: {e}")
                response_text = f"AI error: {e}"
        else:
            # No AI client - try direct agent routing
            response_text = self._direct_agent_route(request, available_agents)

        # Parse voice response if present
        voice_response = ""
        if "|||VOICE|||" in response_text:
            parts = response_text.split("|||VOICE|||")
            response_text = parts[0].strip()
            voice_response = parts[1].strip() if len(parts) > 1 else ""

        # Save session memory
        history = request.conversation_history + [
            {"role": "user", "content": request.user_input},
            {"role": "assistant", "content": response_text}
        ]
        self.memory_manager.save_session_memory(request.session_guid, history[-20:])

        return RappResponse(
            response=response_text,
            voice_response=voice_response,
            agent_logs=agent_logs,
            agents_used=agents_used,
            session_guid=request.session_guid,
            context_guid=context.guid
        )

    def _get_agents_for_context(self, context: RappContext) -> Dict[str, Any]:
        """Get agents enabled for a context."""
        if "*" in context.agents:
            return self.agent_registry.agents.copy()

        return {
            aid: agent
            for aid, agent in self.agent_registry.agents.items()
            if aid in context.agents
        }

    def _build_messages(self, request: RappRequest, context: RappContext,
                        user_memory: str, agents: Dict) -> List[Dict]:
        """Build messages for AI call."""
        system_content = context.system_prompt or "You are a helpful AI assistant."

        if user_memory:
            system_content += f"\n\nUser Memory:\n{user_memory[-2000:]}"

        if agents:
            agent_list = ", ".join(agents.keys())
            system_content += f"\n\nAvailable agents: {agent_list}"

        messages = [{"role": "system", "content": system_content}]

        # Add conversation history
        for msg in request.conversation_history[-10:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })

        # Add current message
        messages.append({"role": "user", "content": request.user_input})

        return messages

    def _direct_agent_route(self, request: RappRequest, agents: Dict) -> str:
        """Route directly to agent without AI (fallback)."""
        user_lower = request.user_input.lower()

        for agent_name, agent in agents.items():
            if agent_name.lower() in user_lower:
                try:
                    return agent.perform(action="help", request=request.user_input)
                except:
                    pass

        return f"Available agents: {', '.join(agents.keys())}"


# Global brain stem instance
_brain_stem: Optional[RappBrainStem] = None

def get_brain_stem() -> RappBrainStem:
    """Get or create the global brain stem instance."""
    global _brain_stem
    if _brain_stem is None:
        _brain_stem = RappBrainStem()
    return _brain_stem


def process_request(
    user_input: str,
    user_guid: str = "default",
    session_guid: str = "",
    context_guid: str = "default",
    conversation_history: List[Dict] = None
) -> Dict:
    """
    Process a request through the brain stem.

    This is the main entry point for all RAPP requests.
    """
    brain = get_brain_stem()

    request = RappRequest(
        user_input=user_input,
        user_guid=user_guid,
        session_guid=session_guid,
        context_guid=context_guid,
        conversation_history=conversation_history or []
    )

    response = brain.process(request)

    return {
        "response": response.response,
        "voice_response": response.voice_response,
        "agent_logs": response.agent_logs,
        "agents_used": response.agents_used,
        "session_guid": response.session_guid,
        "context_guid": response.context_guid
    }


if __name__ == "__main__":
    # Test the brain stem
    brain = get_brain_stem()
    print(f"Loaded {len(brain.agent_registry.agents)} agents")
    print(f"Loaded {len(brain.context_manager.contexts)} contexts")

    # Test request
    result = process_request("Hello, what can you do?")
    print(f"Response: {result['response'][:200]}...")
