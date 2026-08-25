#!/usr/bin/env python3
"""
claude_ui_poc.py — drive a Claude Code session from your own UI.

Proof of concept for the pattern you want:

    Your text box  ──►  Claude Code session
    Chat bubbles   ◄──  a custom tool Claude calls to talk to your UI
    Side log       ◄──  Claude's ordinary assistant text and tool activity

The important idea: the chat pane is NOT fed by Claude's assistant text. It is
fed by an in-process MCP tool (`say_to_user`) that we define here in Python.
When Claude calls it, our function runs inside this process and pushes a bubble
into the UI. Assistant prose goes to the side log instead.

That means the UI gets structured, intentional messages instead of whatever
prose the model happened to emit — and because the tool is a normal Python
function, it can return a value that Claude then reads and reasons about.

Setup
-----
    npm install -g @anthropic-ai/claude-code
    pip install claude-agent-sdk          # Python 3.10+
    claude                                # log in once, then quit
    python claude_ui_poc.py [project_dir]

Swapping in NiceGUI (or any framework): see NICEGUI NOTES at the bottom. All
the Claude wiring is in ClaudeUIBridge, which knows nothing about Tkinter.

API reference: https://docs.claude.com/en/api/agent-sdk/python
"""

from __future__ import annotations

import asyncio
import os
import queue
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any

# ---------------------------------------------------------------------------
# 1. The UI-facing event stream
# ---------------------------------------------------------------------------


@dataclass
class UIEvent:
    """Anything the bridge wants the UI to render."""

    kind: str  # bubble | ask | prose | tool | status | result | error | ready
    text: str = ""
    data: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 2. The bridge: a Claude Code session plus the tools it can use to talk back
# ---------------------------------------------------------------------------


class ClaudeUIBridge:
    """Owns a persistent Claude Code session on a background asyncio loop.

    GUI-agnostic. It calls `emit(UIEvent)` from a worker thread, so whatever
    UI you attach must marshal those onto its own thread (Tkinter: a Queue
    polled by `after`; NiceGUI: see the notes at the bottom).
    """

    def __init__(
        self,
        cwd: str,
        emit: Callable[[UIEvent], None],
        *,
        model: str | None = None,
    ) -> None:
        self.cwd = cwd
        self.emit = emit
        self.model = model

        self.loop = asyncio.new_event_loop()
        self.prompts: asyncio.Queue[str | None] | None = None
        self.client: Any = None
        self.busy = False

        # Answers to `ask_user`, keyed by question. The UI fills these in.
        self._answers: dict[str, str] = {}
        self._answer_ready: dict[str, threading.Event] = {}

        self._thread = threading.Thread(target=self._run, daemon=True)

    # -- public, called from the UI thread ----------------------------------

    def start(self) -> None:
        self._thread.start()

    def send(self, prompt: str) -> None:
        if self.prompts is None:
            self.emit(UIEvent("error", "Session is still starting."))
            return
        self.loop.call_soon_threadsafe(self.prompts.put_nowait, prompt)

    def interrupt(self) -> None:
        if self.client is not None and self.busy:
            asyncio.run_coroutine_threadsafe(self.client.interrupt(), self.loop)

    def answer(self, question: str, reply: str) -> None:
        """Hand a reply back to a blocked `ask_user` tool call."""
        self._answers[question] = reply
        event = self._answer_ready.get(question)
        if event:
            event.set()

    def shutdown(self) -> None:
        if self.prompts is not None:
            self.loop.call_soon_threadsafe(self.prompts.put_nowait, None)

    # -- the tools Claude can call to reach the UI -------------------------

    def _build_ui_server(self):
        """An in-process MCP server. These run in OUR process, not a subprocess."""
        from claude_agent_sdk import create_sdk_mcp_server, tool

        @tool(
            "say_to_user",
            "Show a chat message to the user in the app's chat panel. Use this "
            "for anything the user should read as conversation: findings, "
            "summaries, progress, results. Prefer one clear message over many.",
            {
                "message": Annotated[str, "The chat message to display"],
                "tone": Annotated[str, "One of: info, success, warning. Defaults to info."],
            },
        )
        async def say_to_user(args: dict[str, Any]) -> dict[str, Any]:
            # Runs inside this Python process — so it can touch app state
            # directly. Here it just pushes a bubble into the UI.
            self.emit(
                UIEvent(
                    "bubble",
                    args["message"],
                    {"tone": args.get("tone", "info")},
                )
            )
            # Whatever we return, Claude reads. Confirming delivery keeps it
            # from re-sending the same message.
            return {"content": [{"type": "text", "text": "Displayed in the chat panel."}]}

        @tool(
            "ask_user",
            "Ask the user a question in the chat panel and wait for their typed "
            "answer. Only use when you genuinely cannot proceed without it.",
            {"question": Annotated[str, "The question to ask"]},
        )
        async def ask_user(args: dict[str, Any]) -> dict[str, Any]:
            question = args["question"]
            ready = threading.Event()
            self._answer_ready[question] = ready
            self.emit(UIEvent("ask", question))

            # Block this tool call, not the event loop, until the UI replies.
            await asyncio.get_running_loop().run_in_executor(None, ready.wait)

            reply = self._answers.pop(question, "")
            self._answer_ready.pop(question, None)
            return {"content": [{"type": "text", "text": reply or "(no answer)"}]}

        return create_sdk_mcp_server(name="ui", version="1.0.0", tools=[say_to_user, ask_user])

    # -- the session -------------------------------------------------------

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._session())
        except Exception as exc:
            self.emit(UIEvent("error", f"{type(exc).__name__}: {exc}"))
        finally:
            self.loop.close()

    async def _session(self) -> None:
        try:
            from claude_agent_sdk import (
                AssistantMessage,
                ClaudeAgentOptions,
                ClaudeSDKClient,
                CLINotFoundError,
                PermissionResultAllow,
                PermissionResultDeny,
                ResultMessage,
                TextBlock,
                ToolUseBlock,
            )
        except ImportError:
            self.emit(
                UIEvent(
                    "error",
                    "Missing dependencies:\n"
                    "    pip install claude-agent-sdk\n"
                    "    npm install -g @anthropic-ai/claude-code",
                )
            )
            return

        self.prompts = asyncio.Queue()

        # Tools from an SDK MCP server are namespaced mcp__<server>__<tool>.
        ui_tools = ["mcp__ui__say_to_user", "mcp__ui__ask_user"]

        async def gate(tool_name: str, tool_input: dict, context) -> Any:
            """Auto-allow our own UI tools; auto-allow reads; block writes.

            A real app would surface anything else to the user for approval.
            Keeping the PoC read-only means it can't damage the project.
            """
            if tool_name in ui_tools:
                return PermissionResultAllow()
            if tool_name in ("Read", "Glob", "Grep", "TodoWrite", "Task"):
                return PermissionResultAllow()
            return PermissionResultDeny(
                message=(
                    f"{tool_name} is disabled in this proof of concept. "
                    "Report findings with say_to_user instead."
                )
            )

        options = ClaudeAgentOptions(
            cwd=self.cwd,
            model=self.model,
            # Without these two presets the SDK starts as a bare agent with no
            # system prompt and no Claude Code tools.
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": (
                    "You are running inside a desktop app, not a terminal. The "
                    "user cannot see your normal replies. To communicate, call "
                    "the say_to_user tool — that is the only thing they read. "
                    "Call it at least once per turn, and call ask_user if you "
                    "need information you cannot obtain yourself."
                ),
            },
            tools={"type": "preset", "preset": "claude_code"},
            mcp_servers={"ui": self._build_ui_server()},
            allowed_tools=ui_tools,
            permission_mode="default",  # keeps `gate` in play
            can_use_tool=gate,
        )

        self.emit(UIEvent("status", f"Starting Claude Code in {self.cwd} …"))

        try:
            async with ClaudeSDKClient(options=options) as client:
                self.client = client
                self.emit(UIEvent("ready", "Session ready."))

                while True:
                    prompt = await self.prompts.get()
                    if prompt is None:
                        break

                    self.busy = True
                    self.emit(UIEvent("status", "Claude is working …"))
                    try:
                        await client.query(prompt)
                        async for msg in client.receive_response():
                            if isinstance(msg, AssistantMessage):
                                for block in msg.content:
                                    if isinstance(block, TextBlock):
                                        # Prose the user isn't meant to read as
                                        # chat — goes to the side log.
                                        if block.text.strip():
                                            self.emit(UIEvent("prose", block.text))
                                    elif isinstance(block, ToolUseBlock):
                                        if block.name not in ui_tools:
                                            self.emit(
                                                UIEvent(
                                                    "tool",
                                                    describe(block.name, block.input),
                                                )
                                            )
                            elif isinstance(msg, ResultMessage):
                                self.emit(UIEvent("result", summarize(msg)))
                    except Exception as exc:
                        self.emit(UIEvent("error", f"{type(exc).__name__}: {exc}"))
                    finally:
                        self.busy = False
        except CLINotFoundError:
            self.emit(
                UIEvent(
                    "error",
                    "The `claude` CLI is not on PATH.\n"
                    "    npm install -g @anthropic-ai/claude-code",
                )
            )


def describe(name: str, params: dict) -> str:
    for key in ("file_path", "path", "pattern", "command", "query", "url"):
        val = params.get(key)
        if isinstance(val, str) and val.strip():
            snippet = " ".join(val.split())
            return f"{name}({snippet[:70] + '…' if len(snippet) > 73 else snippet})"
    return f"{name}()"


def summarize(msg) -> str:
    bits = [f"{msg.duration_ms / 1000:.1f}s", f"{msg.num_turns} turn(s)"]
    if msg.total_cost_usd:
        bits.append(f"${msg.total_cost_usd:.4f}")
    return " · ".join(bits)


# ---------------------------------------------------------------------------
# 3. A minimal Tkinter UI, to prove the loop closes
# ---------------------------------------------------------------------------


def run_tk_ui(cwd: str) -> None:
    import tkinter as tk
    from tkinter import scrolledtext, ttk

    events: queue.Queue[UIEvent] = queue.Queue()
    bridge = ClaudeUIBridge(cwd, events.put, model=os.environ.get("CLAUDE_MODEL"))

    root = tk.Tk()
    root.title(f"Claude Code · {os.path.basename(cwd)}")
    root.geometry("1040x680")

    split = ttk.Panedwindow(root, orient="horizontal")
    split.pack(fill="both", expand=True)

    # left: the chat, driven only by tool calls
    left = ttk.Frame(split, padding=8)
    ttk.Label(left, text="CHAT — written by Claude via say_to_user").pack(anchor="w")
    chat = scrolledtext.ScrolledText(
        left,
        wrap="word",
        state="disabled",
        width=52,
        background="#12161b",
        foreground="#e6e0d4",
        borderwidth=0,
        padx=10,
        pady=10,
    )
    chat.pack(fill="both", expand=True, pady=(4, 0))
    for tag, colour in (
        ("you", "#6fbfd0"),
        ("info", "#e6e0d4"),
        ("success", "#8fbf6f"),
        ("warning", "#d99b3d"),
        ("ask", "#c48fd0"),
    ):
        chat.tag_configure(tag, foreground=colour, spacing1=6, spacing3=4)

    # right: everything else, so you can see what's really happening
    right = ttk.Frame(split, padding=8)
    ttk.Label(right, text="SESSION LOG — prose, tools, cost").pack(anchor="w")
    log = scrolledtext.ScrolledText(
        right,
        wrap="word",
        state="disabled",
        width=48,
        background="#0e1114",
        foreground="#8b96a3",
        borderwidth=0,
        padx=10,
        pady=10,
    )
    log.pack(fill="both", expand=True, pady=(4, 0))
    log.tag_configure("prose", foreground="#b9b2a4")
    log.tag_configure("tool", foreground="#d99b3d")
    log.tag_configure("error", foreground="#c4574f")

    split.add(left, weight=3)
    split.add(right, weight=2)

    bar = ttk.Frame(root, padding=(8, 6))
    bar.pack(fill="x")
    entry = tk.Text(bar, height=3, wrap="word")
    entry.pack(fill="x")
    controls = ttk.Frame(bar)
    controls.pack(fill="x", pady=(6, 0))
    status = ttk.Label(controls, text="Starting…")
    status.pack(side="left")

    pending_question: list[str] = []

    def write(widget, text: str, tag: str, prefix: str = "") -> None:
        widget.configure(state="normal")
        widget.insert("end", f"{prefix}{text.rstrip()}\n", tag)
        widget.see("end")
        widget.configure(state="disabled")

    def send() -> None:
        text = entry.get("1.0", "end").strip()
        if not text:
            return
        entry.delete("1.0", "end")
        write(chat, text, "you", prefix="You · ")
        if pending_question:
            bridge.answer(pending_question.pop(0), text)
            status.configure(text="Answer sent")
        else:
            bridge.send(text)
            status.configure(text="Claude is working …")

    send_btn = ttk.Button(controls, text="Send", command=send, state="disabled")
    send_btn.pack(side="right")
    ttk.Button(controls, text="Interrupt", command=bridge.interrupt).pack(side="right", padx=(0, 6))

    def on_return(event):
        if event.state & 0x0001:
            return None
        send()
        return "break"

    entry.bind("<Return>", on_return)

    def drain() -> None:
        try:
            while True:
                ev = events.get_nowait()
                if ev.kind == "bubble":
                    write(chat, ev.text, ev.data.get("tone", "info"), prefix="Claude · ")
                elif ev.kind == "ask":
                    pending_question.append(ev.text)
                    write(chat, ev.text, "ask", prefix="Claude asks · ")
                    status.configure(text="Waiting for your answer")
                elif ev.kind == "prose":
                    write(log, ev.text, "prose")
                elif ev.kind == "tool":
                    write(log, f"⚙ {ev.text}", "tool")
                elif ev.kind == "error":
                    write(log, ev.text, "error")
                    status.configure(text="Error — see the log")
                elif ev.kind == "ready":
                    send_btn.configure(state="normal")
                    status.configure(text="Ready")
                elif ev.kind == "result":
                    write(log, f"— {ev.text}", "prose")
                    status.configure(text="Ready")
                elif ev.kind == "status":
                    status.configure(text=ev.text)
        except queue.Empty:
            pass
        root.after(40, drain)

    def on_close() -> None:
        bridge.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    bridge.start()
    root.after(40, drain)
    entry.focus_set()
    root.mainloop()


if __name__ == "__main__":
    target = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    run_tk_ui(target)


# ---------------------------------------------------------------------------
# NICEGUI NOTES
# ---------------------------------------------------------------------------
#
# ClaudeUIBridge is UI-agnostic; only the `emit` callback and the input
# handler change. NiceGUI already runs an asyncio loop, so the marshalling is
# simpler than Tkinter's — no polling required.
#
#     from nicegui import ui, app
#
#     messages = []           # (role, text) pairs
#     chat_box = None
#
#     def emit(ev: UIEvent):
#         # Called from the bridge's worker thread. Hop onto NiceGUI's loop:
#         if ev.kind in ("bubble", "ask"):
#             messages.append(("claude", ev.text))
#             chat_box.refresh()          # @ui.refreshable render function
#         elif ev.kind == "prose":
#             print("[prose]", ev.text)   # or a ui.log() element
#
#     bridge = ClaudeUIBridge("/path/to/project", emit)
#     bridge.start()
#
#     @ui.refreshable
#     def chat_box_view():
#         for role, text in messages:
#             ui.chat_message(text, name="Claude" if role == "claude" else "You",
#                             sent=(role == "you"))
#
#     def on_submit(e):
#         messages.append(("you", e.value))
#         bridge.send(e.value)
#         chat_box.refresh()
#
#     ui.input(placeholder="Ask Claude…", on_change=None).on("keydown.enter", on_submit)
#     ui.run()
#
# Two gotchas:
#   * `emit` fires on a non-UI thread. Wrap UI mutations so they land on
#     NiceGUI's loop — the cleanest way is a client-bound
#     `ui.timer(0.1, drain_queue)` reading a queue.Queue, exactly like the
#     Tkinter version, or `app.loop.call_soon_threadsafe(...)`.
#   * Call `bridge.shutdown()` from `app.on_shutdown` so the CLI subprocess
#     doesn't outlive the web server.
