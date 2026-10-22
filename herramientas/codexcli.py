"""Cómo el bot llama a Codex (la app de la tienda de Windows, con tu plan de ChatGPT)."""
import json
import os
import pathlib
import subprocess
import tempfile


def codex_exe() -> str:
    if os.environ.get("CODEX_EXE"):
        return os.environ["CODEX_EXE"]
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-AppxPackage OpenAI.Codex).InstallLocation"],
                       capture_output=True, text=True)
    exe = pathlib.Path(r.stdout.strip()) / "app" / "resources" / "codex.exe"
    if not exe.exists():
        raise RuntimeError("No encuentro la app de Codex instalada (o definí CODEX_EXE)")
    return str(exe)


def correr_codex(args: list, prompt: str, timeout=900) -> str:
    """La instrucción va por la entrada estándar: -i acepta varias imágenes y se "comería" el texto."""
    cmd = [codex_exe(), "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only", *args]
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"Codex terminó con error {r.returncode}: {(r.stderr or r.stdout)[-400:]}")
    return r.stdout


def imagenes(rutas) -> list:
    args = []
    for r in rutas:
        if not pathlib.Path(r).is_file():           # sin la imagen, Codex contestaría igual (inventando)
            raise FileNotFoundError(f"No encuentro la imagen {r}")
        args += ["-i", str(r)]
    return args


def correr_json(prompt: str, esquema: dict, fotos=(), buscar=False, timeout=600) -> dict:
    """Respuesta de Codex con forma fija (JSON Schema). buscar=True le habilita la búsqueda en internet."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta_esquema = pathlib.Path(tmp) / "esquema.json"
        ruta_esquema.write_text(json.dumps(esquema), encoding="utf-8")
        respuesta = pathlib.Path(tmp) / "respuesta.json"
        args = ["-C", tmp, "--output-schema", str(ruta_esquema), "-o", str(respuesta), *imagenes(fotos)]
        if buscar:
            args += ["-c", 'web_search="live"']
        correr_codex(args, prompt, timeout=timeout)
        return json.loads(respuesta.read_text(encoding="utf-8"))


def objeto(props: dict) -> dict:
    """Objeto JSON Schema estricto: todas las claves obligatorias y ninguna extra (lo exige --output-schema)."""
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}
