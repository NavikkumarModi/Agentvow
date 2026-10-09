"""Agent-agnostic input: hook payloads and transcripts from different agents.

Verified against: Claude Code session files (used in this project). Everything else is built from vendor documentation or
tolerant format sniffing and is NOT yet verified against real Copilot/Codex/Cursor/Gemini transcripts: when a transcript
cannot be understood the caller gets None and reports "nothing was verified" (never a guess).
"""
import json
from pathlib import Path

_TEXT_KEYS = ("text", "output_text", "content", "message", "last_assistant_message", "response")
_ASSIST = {"assistant", "model", "agent", "ai", "bot", "copilot"}
_ASSIST_TYPES = {"assistant", "assistant_message", "agent_message", "model", "model_response", "response", "agent_response"}


def parse_hook_payload(payload: dict) -> dict:
    """Normalise camelCase (Copilot CLI/cloud agent), snake_case (VS Code, Claude Code, Codex) and Cursor-style hook inputs."""
    g = lambda *ks: next((payload[k] for k in ks if payload.get(k)), None)
    return {
        "cwd": g("cwd", "workingDirectory", "workspace_root", "workspaceRoot") or (g("workspace_roots") or [None])[0]
        if isinstance(g("workspace_roots"), list) or g("cwd", "workingDirectory", "workspace_root", "workspaceRoot") else None,
        "transcript": g("transcript_path", "transcriptPath"),
        "message": g("last_assistant_message", "lastAssistantMessage", "final_message", "text"),
        "session": g("session_id", "sessionId", "conversation_id"),
        "loop": bool(g("stop_hook_active", "stopHookActive")),
    }


def _is_assistant(node: dict) -> bool:
    role = str(node.get("role", "")).lower()
    typ = str(node.get("type", "")).lower()
    return role in _ASSIST or typ in _ASSIST_TYPES


MAX_DEPTH = 40


def _texts(node, assistant: bool, out: list, depth: int = 0):
    """Collect text strings under assistant nodes (recursive; tolerant of unknown nesting; depth-bounded)."""
    if depth > MAX_DEPTH:
        return
    if isinstance(node, dict):
        a = assistant or _is_assistant(node)
        for k, v in node.items():
            if isinstance(v, str) and a and k in _TEXT_KEYS and v.strip() and not v.lstrip().startswith(("{", "[")):
                if str(node.get("type", "")).lower() not in ("tool_use", "tool_result", "function_call", "tool_call", "thinking", "reasoning"):
                    out.append(v.strip())
            elif isinstance(v, (dict, list)):
                _texts(v, a, out, depth + 1)
    elif isinstance(node, list):
        for v in node:
            _texts(v, assistant, out, depth + 1)


def _copilot_event_text(obj):
    """GitHub Copilot CLI session events (~/.copilot/session-state/<id>/events.jsonl): {"type": "assistant.message", "data": {"content": "...",
    "phase": "final_answer"|"commentary"|None, "toolRequests": [...]}}. Only data.content is the message; tool arguments (which can hold whole
    files under a `content` key) must never be mistaken for it. -> (text, is_final) or None when this record is not an assistant message."""
    if isinstance(obj, dict) and obj.get("type") == "assistant.message" and isinstance(obj.get("data"), dict):
        d = obj["data"]
        text = d.get("content")
        return (text.strip() if isinstance(text, str) else ""), d.get("phase") == "final_answer"
    return None


def final_message_info(raw: str):
    """-> (text or None, is_final, is_copilot). Copilot CLI transcripts are scoped to the CURRENT turn (everything after the latest
    user.message): when the final answer has not been flushed to the file yet this returns no text, never the previous turn's answer."""
    last, last_final, parsed_any, copilot = None, None, False, False
    for line in raw.splitlines():
        line = line.strip()
        if not line or line[0] not in "{[" or len(line) > 2_000_000:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, RecursionError):
            continue
        parsed_any = True
        if isinstance(obj, dict) and obj.get("type") == "user.message":
            last = last_final = None   # a new turn starts: nothing before this belongs to the answer we are looking for
            copilot = True
            continue
        cop = _copilot_event_text(obj)
        if cop is not None:
            copilot = True
            if cop[0]:
                last = cop[0]
                if cop[1]:
                    last_final = cop[0]
            continue
        found: list = []
        _texts(obj, False, found)
        if found:
            last = "\n".join(found).strip() or last
    if last_final:
        return last_final, True, copilot
    if not parsed_any:
        try:  # a single pretty-printed JSON document
            obj = json.loads(raw[:5_000_000])
            found = []
            _texts(obj, False, found)
            return (found[-1] if found else None), False, False
        except (ValueError, RecursionError):
            return (raw.strip()[-6000:] or None), False, False  # plain text transcript (bounded)
    return last, False, copilot


def final_message_from_text(raw: str):
    return final_message_info(raw)[0]


MAX_TRANSCRIPT_BYTES = 8_000_000   # transcripts can be hundreds of MB; the final answer is at the end, so only the tail is read


def read_tail(path: Path, limit: int = MAX_TRANSCRIPT_BYTES) -> str:
    """The last `limit` bytes of a regular file as text (first partial line dropped). Non-regular files (fifos, devices) are refused."""
    import os, stat
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise OSError("not a regular file")
        cut = st.st_size > limit
        if cut:
            os.lseek(fd, st.st_size - limit, os.SEEK_SET)
        data = b""
        while len(data) < limit:
            chunk = os.read(fd, min(1_000_000, limit - len(data)))
            if not chunk:
                break
            data += chunk
    finally:
        os.close(fd)
    text = data.decode("utf-8", errors="replace")
    return text.split("\n", 1)[1] if cut and "\n" in text else text


def final_message_info_file(path: Path):
    try:
        return final_message_info(read_tail(path))
    except OSError:
        return None, False, False


def final_message(path: Path):
    try:
        return final_message_from_text(read_tail(path))
    except OSError:
        return None


def shape_of(node, depth: int = 0):
    """The STRUCTURE of a JSON value (key names, types, string lengths), never its content: safe to share when debugging an unknown format."""
    if depth > 6:
        return "..."
    if isinstance(node, dict):
        return {str(k): shape_of(v, depth + 1) for k, v in list(node.items())[:40]}
    if isinstance(node, list):
        return [shape_of(node[0], depth + 1), f"... {len(node)} items"] if node else []
    if isinstance(node, str):
        return f"str[{len(node)}]"
    return type(node).__name__


def transcript_shapes(path: Path, n: int = 4) -> dict:
    """Structure of the first and last few records of a JSONL transcript (no content)."""
    from collections import deque
    head, tail = [], deque(maxlen=n)
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                line = line[:200_000]
                if i < n:
                    head.append(line)
                else:
                    tail.append(line)
    except OSError as e:
        return {"error": type(e).__name__}
    shapes = []
    for line in [*head, *tail]:
        try:
            shapes.append(shape_of(json.loads(line)))
        except (ValueError, RecursionError):
            shapes.append(f"non-json line, {len(line)} chars")
    return {"records_sampled": len(shapes), "shapes": shapes}
