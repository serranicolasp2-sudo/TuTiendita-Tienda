"""Claude como segunda IA del bot, con tu suscripción (Claude Code en modo no interactivo, `claude -p`).

No usa la API paga: se le saca ANTHROPIC_API_KEY del entorno a propósito, así que si no hay sesión iniciada falla en
lugar de cobrar. Gasta del mismo cupo que usás en la app de Claude. Para iniciar sesión, una sola vez, en una terminal:
    claude          y adentro:  /login   (elegí tu cuenta de Claude, no "API key")
"""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

MODELO = os.environ.get("CLAUDE_MODELO", "sonnet")


class SinClaude(RuntimeError):
    """No hay Claude disponible (sin instalar, sin sesión o sin cupo): el bot sigue con Codex."""


def claude_exe() -> str:
    if os.environ.get("CLAUDE_EXE"):
        return os.environ["CLAUDE_EXE"]
    local = pathlib.Path.home() / ".local" / "bin" / "claude.exe"
    return str(local) if local.exists() else (shutil.which("claude") or "")


def correr_json(prompt: str, esquema: dict, timeout=600) -> dict:
    """Respuesta de Claude con forma fija (JSON Schema). Sin herramientas: solo lee el texto y contesta."""
    exe = claude_exe()
    if not exe:
        raise SinClaude("Claude Code no está instalado")
    entorno = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    with tempfile.TemporaryDirectory() as tmp:            # carpeta vacía: no lee instrucciones de ningún proyecto
        try:
            r = subprocess.run([exe, "-p", "--output-format", "json", "--json-schema", json.dumps(esquema),
                                "--tools", "", "--no-session-persistence", "--strict-mcp-config", "--model", MODELO],
                               input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=timeout, cwd=tmp, env=entorno)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise SinClaude(f"Claude no respondió: {e}") from e
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise SinClaude(f"Claude no respondió: {(r.stderr or r.stdout)[-300:]}") from None
    if d.get("is_error") or not isinstance(d.get("structured_output"), dict):
        raise SinClaude(str(d.get("result") or "respuesta vacía")[:300])
    return d["structured_output"]
