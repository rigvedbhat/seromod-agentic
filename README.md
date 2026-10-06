# Seromod (Agentic)

> **Discord-Native AI Server Administrator** — An open-source, model-agnostic, event-driven agent architecture for Discord servers, inspired by the agent designs of Hermes and OpenClaw.

---

## 🌟 Product Vision

Seromod is not a chatbot or a collection of slash commands. It behaves like an **autonomous AI administrator** for your Discord server.

Administrators can give it natural goals:
- *"Make this server suitable for a Minecraft SMP."*
- *"Why did you create #clips-and-highlights?"*
- *"Move all community channels into their own category."*
- *"Be strict about harassment and spam, but relaxed about profanity."*

Seromod inspects the server, plans changes, calls structured tools through safe guardrails, records decisions, and enforces server-specific policies.

---

## 📐 Architecture Overview

```text
                  Discord Gateway Event
                           │
                           ▼
                      Event Router
                           │
                     Agent Runtime
            (Per-Guild Concurrency Lock)
                           │
                           ▼
                     ServerContext
         ┌─────────────────┴─────────────────┐
         ▼                                   ▼
Authoritative Live Discord            Local Workspace Memory
(Channels, Roles, State)             (DECISIONS.md, SERVER.md, POLICY.md)
         └─────────────────┬─────────────────┘
                           │
                           ▼
                    Brain Interface
            (Model-Agnostic / Structured JSON)
                           │
                           ▼
                 Policy & Safety Engine
            (Permissions + High-Impact Approval)
                           │
                           ▼
                     Tool Runtime
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   Server Structure    Moderation       Workspace Memory
   (Channels, Roles)  (Timeout, Kick)  (Read, Write, Search)
                           │
                           ▼
             Audit Record to DECISIONS.md
                           │
                           ▼
                  Verify / Continue / Done
```

---

## 🔑 Core Features & Design Principles

### 1. Live Discord State as Authoritative Truth
- Local memory is a derived context and history layer; it **never** overrides live Discord.
- If a channel was deleted directly on Discord, Seromod recognizes it as deleted even if previous decision records state that Seromod created it.

### 2. Local Agent Workspace Memory
Each server has a dedicated, self-hosted, human-readable Markdown workspace under `workspace/guilds/{guild_id}/`:
```text
workspace/
└── guilds/
    └── {guild_id}/
        ├── AGENTS.md        # Agent identity, persona & operational boundaries
        ├── SERVER.md        # Server purpose, theme & administrator preferences
        ├── MEMORY.md        # Curated long-term knowledge & facts
        ├── DECISIONS.md     # Chronological log of major decisions & rationale
        ├── POLICY.md        # Natural language server & moderation policies
        ├── memory/          # Daily notes/logs: YYYY-MM-DD.md
        ├── sessions/        # Session histories (JSON)
        └── tasks/           # Active/past task snapshots (JSON)
```
- No external database (PostgreSQL, Supabase, Redis, or Vector DB) required.
- Memory tools (`memory_read`, `memory_write`, `memory_search`, `memory_update`, `search_decisions`) allow the agent to inspect and update its workspace.

### 3. Explicit Approval State (`WAITING_FOR_APPROVAL`)
- High-impact operations (e.g. deleting channels, kicking or banning members) halt execution and transition the task to `WAITING_FOR_APPROVAL`.
- The task persists on disk, surfaces an approval request in Discord, and cleanly resumes via `approve_and_continue(...)`.

### 4. Non-Atomic Resilience (`PARTIALLY_COMPLETED`)
- Multi-step builds record `completed_actions`, `failed_actions`, and `remaining_plan`.
- If an operation fails midway, the task transitions to `PARTIALLY_COMPLETED` so it can be resumed or inspected rather than lost.

### 5. Multi-Stage Event-Driven Moderation
- **Cheap Heuristic Filter** → **Context Gathering** → **Moderation Brain** → **Policy Engine** → **Action**.
- Returns structured evaluation objects (`classification`, `confidence`, `severity`, `action`, `reason`, `evidence`).
- Actions are strictly checked against `POLICY.md`.

---

## 📁 Repository Structure

```text
seromod-agentic/
├── seromod/
│   ├── __init__.py
│   ├── __main__.py            # Application entrypoint
│   ├── bot.py                 # Discord gateway & event routing
│   ├── config.py              # Configuration & environment variables
│   ├── guild_handle.py        # GuildHandle protocol (Discord boundary)
│   │
│   ├── agent/
│   │   ├── brain.py           # Provider-independent Brain ABC
│   │   ├── gemini_brain.py    # Production Gemini Brain implementation
│   │   ├── context.py         # ServerContext builder
│   │   ├── decisions.py       # AgentDecision, ToolCallRequest, Moderation models
│   │   ├── runtime.py         # Central agent loop (observe-reason-act-verify)
│   │   └── task.py            # AgentTask lifecycle state machine
│   │
│   ├── memory/
│   │   ├── decisions.py       # DecisionRecord model
│   │   └── workspace.py       # WorkspaceMemoryStore (local Markdown workspace)
│   │
│   ├── policy/
│   │   └── engine.py          # Deterministic PolicyEngine
│   │
│   ├── skills/
│   │   ├── base.py            # Skill ABC
│   │   ├── conversation.py    # Server-aware Q&A skill
│   │   ├── server_builder.py  # Desired-state server building skill
│   │   └── moderation.py      # Event-driven moderation skill
│   │
│   └── tools/
│       ├── base.py            # Tool ABC, ToolResult, ToolSchema
│       ├── registry.py        # ToolRegistry
│       ├── channels.py        # Channel operations
│       ├── categories.py      # Category operations
│       ├── roles.py           # Role operations
│       ├── server.py          # Composite get_server_state
│       ├── messages.py        # Messaging operations
│       ├── members.py         # Timeout, kick, ban operations
│       ├── memory_tools.py    # Historical decision lookup
│       └── workspace_memory.py# memory_read, memory_write, memory_search, memory_update
│
├── tests/
│   ├── fake_discord.py        # In-memory GuildHandle implementation
│   ├── fake_brain.py          # Deterministic scripted Brain implementation
│   ├── test_suite.py          # Core runtime, build loop, and moderation tests
│   └── test_workspace_memory.py # 6-point workspace memory test suite
│
├── .gitignore
├── pyproject.toml
└── requirements.txt
```

---

## 🚀 Quickstart

### Prerequisites
- Python 3.10+
- A Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))
- A Gemini API Key ([Google AI Studio](https://aistudio.google.com/)) or compatible LLM provider key

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/rigvedbhat/seromod-agentic.git
   cd seromod-agentic
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   Create a `.env` file in the project root:
   ```env
   DISCORD_TOKEN=your_discord_bot_token_here
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-2.5-flash
   SEROMOD_WORKSPACE_DIR=workspace/guilds
   ```

4. **Run the agent:**
   ```bash
   python -m seromod
   ```

---

## 🧪 Testing

Seromod includes an in-memory testing harness (`FakeGuild` and `FakeBrain`) allowing comprehensive tests to execute in sub-second time without connecting to Discord or making live LLM calls:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

All 9 test suites cover:
- Multi-step server building loop
- Resilient recovery on partial build failure (`PARTIALLY_COMPLETED`)
- High-impact approval gates and resumption (`WAITING_FOR_APPROVAL`)
- Event-driven moderation pipeline
- Agent writing to workspace memory
- Memory survival across process restarts
- Authoritative live Discord state precedence over stale memory
- Historical question answering from `DECISIONS.md`

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
