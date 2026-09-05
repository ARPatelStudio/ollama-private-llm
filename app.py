import json
import os
import re
import stat
import subprocess
import sys
import time
from typing import Generator

import gradio as gr
import httpx

# ===========================================================================
# ⚡ AR PATEL STUDIO - CONFIGURATION & CONSTANTS
# ===========================================================================
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "127.0.0.1:11434")
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}"
OPENAI_COMPATIBLE_URL = f"{OLLAMA_BASE_URL}/v1/chat/completions"
TARGET_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

INSTALL_DIR = os.path.expanduser("~/.ollama_bin")
OLLAMA_BIN = os.path.join(INSTALL_DIR, "bin", "ollama")
# Ollama distributes the Linux executable directly, not as an archive.
DOWNLOAD_URL = "https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64"

# 🛡️ AR PATEL STUDIO MILITARY-GRADE SECURITY GATEWAY
API_KEY = os.environ.get("ARPATEL_API_KEY", "fallback_key_123")


# ===========================================================================
# 1. 🚀 DOWNLOAD & START OLLAMA ENGINE ON GPU
# ===========================================================================
def ensure_ollama_binary() -> None:
    """Downloads the official raw Ollama binary if not present."""
    if os.path.exists(OLLAMA_BIN):
        return

    print("⏳ Checking Ollama Engine...")
    print("📥 Downloading official Ollama Linux Binary...")
    
    # Ensure nested directories exist (e.g., ~/.ollama_bin/bin)
    os.makedirs(os.path.dirname(OLLAMA_BIN), exist_ok=True)

    # Use httpx to correctly follow GitHub's 302 redirects to the CDN
    try:
        with httpx.stream("GET", DOWNLOAD_URL, follow_redirects=True) as response:
            if response.status_code != 200:
                raise RuntimeError(f"Download failed: HTTP {response.status_code}")
            
            with open(OLLAMA_BIN, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
    except httpx.RequestError as e:
        raise RuntimeError(f"Network error during download: {str(e)}")

    # Verify we didn't just download a tiny error page
    file_size_mb = os.path.getsize(OLLAMA_BIN) / (1024 * 1024)
    if file_size_mb < 10:
        raise RuntimeError(
            f"Binary payload is too small ({file_size_mb:.2f} MB). Download corrupted."
        )

    print(f"📦 Download complete ({file_size_mb:.1f} MB). Applying permissions...")
    
    # Make executable (chmod +x)
    current_mode = os.stat(OLLAMA_BIN).st_mode
    os.chmod(OLLAMA_BIN, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print("✅ Ollama binary verified and ready.")


def start_ollama_daemon() -> subprocess.Popen:
    """Spawns Ollama daemon as a non-blocking background process."""
    ensure_ollama_binary()

    env = os.environ.copy()
    env["OLLAMA_HOST"] = OLLAMA_HOST

    print("🟢 Starting Ollama Background Service (GPU Mode)...")
    process = subprocess.Popen(
        [OLLAMA_BIN, "serve"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT
    )
    return process


def wait_for_ollama_ready(timeout_seconds: float = 30.0) -> None:
    """Actively polls the engine health endpoint until ready."""
    print("⏳ Probing Ollama service health...")
    start_time = time.time()
    endpoint = f"{OLLAMA_BASE_URL}/api/version"

    with httpx.Client(timeout=2.0) as client:
        while time.time() - start_time < timeout_seconds:
            try:
                response = client.get(endpoint)
                if response.status_code == 200:
                    version_info = response.json().get("version", "unknown")
                    print(f"✅ Engine Ready & Loaded on GPU (version {version_info}) in {time.time() - start_time:.1f}s!")
                    return
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            time.sleep(0.5)

    raise TimeoutError(f"Ollama server failed to start within {timeout_seconds} seconds.")


def is_model_cached(client: httpx.Client, model_name: str) -> bool:
    """Checks whether the requested model is already downloaded."""
    try:
        response = client.get(f"{OLLAMA_BASE_URL}/api/tags")
        if response.status_code == 200:
            models = response.json().get("models", [])
            for item in models:
                name = item.get("name", "")
                if name == model_name or name.startswith(f"{model_name}:"):
                    return True
    except Exception:
        return False
    return False


def pull_model_if_missing(model_name: str) -> None:
    """Pulls the model with real-time stream logs if missing from cache."""
    with httpx.Client(timeout=None) as client:
        if is_model_cached(client, model_name):
            print(f"⚡ Model '{model_name}' is already cached. Skipping pull.")
            return

        print(f"🧠 Pulling AI Model ({model_name})... Please wait.")
        payload = {"name": model_name, "stream": True}

        with client.stream("POST", f"{OLLAMA_BASE_URL}/api/pull", json=payload) as stream_response:
            if stream_response.status_code != 200:
                raise RuntimeError(f"Failed to initiate pull: HTTP {stream_response.status_code}")

            last_status = ""
            for line in stream_response.iter_lines():
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    status = event.get("status", "")
                    total = event.get("total", 0)
                    completed = event.get("completed", 0)

                    if total > 0:
                        percent = (completed / total) * 100
                        print(f"\r⏳ {status}: {percent:.1f}%", end="", flush=True)
                    elif status != last_status:
                        print(f"\n⚡ Status: {status}", flush=True)
                        last_status = status
                except json.JSONDecodeError:
                    continue

        print(f"\n✅ Model '{model_name}' Ready & Loaded on GPU!")


def setup_ollama() -> None:
    """Unified engine manager: extract, launch daemon, wait, and pull weights."""
    start_ollama_daemon()
    wait_for_ollama_ready(timeout_seconds=30.0)
    pull_model_if_missing(TARGET_MODEL)


# Ignite the Engine when Space starts
setup_ollama()


# ===========================================================================
# 2. 🛡️ MILITARY-GRADE SECURITY GATEWAY & JARVIS ROUTING
# ===========================================================================
def jarvis_chat_api(api_key: str, system_prompt: str, user_message: str) -> str:
    """Internal Jarvis API handler with authentication and <think> tag removal."""
    # Security Gate
    if api_key != API_KEY:
        return "🚨 ERROR: Unauthorized! Access Denied by AR Patel Security."

    # Payload for Ollama Engine
    payload = {
        "model": TARGET_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_ctx": 4096  # Large context window for history
        }
    }

    try:
        # Hit local Ollama engine hosted on HF
        response = httpx.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=120.0)
        if response.status_code == 200:
            result = response.json().get("message", {}).get("content", "")
            # Remove any <think> tags completely
            clean_result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()
            return clean_result
        else:
            return f"🚨 Engine Error: {response.text}"
    except Exception as e:
        return f"🚨 Exception: {str(e)}"


def stream_chat_interactive(
    message: str,
    history: list[dict[str, str]]
) -> Generator[str, None, None]:
    """Provides real-time token streaming for the UI test bench."""
    messages = [{"role": "system", "content": "Tum Jarvis ho, Amit Patel ke assistant."}]

    for entry in history:
        messages.append({"role": entry["role"], "content": entry["content"]})

    messages.append({"role": "user", "content": message})

    payload = {
        "model": TARGET_MODEL,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": 0.7,
            "num_ctx": 4096
        }
    }

    full_response = ""
    try:
        with httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            with client.stream("POST", f"{OLLAMA_BASE_URL}/api/chat", json=payload) as response:
                if response.status_code != 200:
                    yield f"⚠️ Engine Error (HTTP {response.status_code}): {response.read().decode('utf-8')}"
                    return

                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        full_response += token
                        # Filter out think tags from streaming output
                        display_text = re.sub(r"<think>.*?</think>", "", full_response, flags=re.DOTALL)
                        if "<think>" in display_text:
                            display_text = display_text.split("<think>")[0]
                        yield display_text.strip()
                    except json.JSONDecodeError:
                        continue
    except Exception as exc:
        yield f"🚨 Stream Error: {str(exc)}"


# ===========================================================================
# 3. 🎨 GRADIO UI & API EXPOSURE
# ===========================================================================
with gr.Blocks(theme=gr.themes.Monochrome(), title="AR PATEL STUDIO - GPU Private LLM") as demo:
    gr.Markdown("# ⚡ AR PATEL STUDIO - GPU Private LLM")
    gr.Markdown("⚠️ *Strictly for internal Jarvis routing. Unauthorized access will be blocked.*")

    with gr.Tabs():
        # Tab 1: Direct Jarvis Security Gateway (Maintains API Name 'chat')
        with gr.Tab("🛡️ Jarvis Command Console (API)"):
            with gr.Row():
                key_input = gr.Textbox(label="Security Key", type="password", placeholder="Enter ARPATEL_API_KEY")

            with gr.Row():
                sys_input = gr.Textbox(label="System Persona", lines=3, value="Tum Jarvis ho, Amit Patel ke assistant.")
                user_input = gr.Textbox(label="User Message", lines=3, placeholder="Command here...")

            output_box = gr.Textbox(label="Jarvis Response", lines=5)
            btn = gr.Button("🧠 Process Command", variant="primary")

            # Preserves the exact /api/chat endpoint for external Jarvis automation
            btn.click(
                fn=jarvis_chat_api,
                inputs=[key_input, sys_input, user_input],
                outputs=output_box,
                api_name="chat"
            )

        # Tab 2: Real-Time Streaming Interactive Chat
        with gr.Tab("💬 Interactive Chat Interface"):
            gr.ChatInterface(
                fn=stream_chat_interactive,
                type="messages",
                title=f"Jarvis Interactive Interface ({TARGET_MODEL})",
                description="Direct GPU-accelerated chat test bench with streaming token generation.",
                autofocus=False,
            )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_api=True
    )
