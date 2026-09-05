import os
import re
import time
import subprocess
import httpx
import gradio as gr

# ==========================================
# ⚡ AR PATEL STUDIO - PRIVATE GPU LLM (OLLAMA)
# ==========================================

OLLAMA_HOST = "http://127.0.0.1:11434"
MODEL_NAME = "qwen2.5:3b"
API_KEY = os.environ.get("ARPATEL_API_KEY", "fallback_key_123")


def setup_ollama():
    print("⏳ Checking Ollama Engine...")
    if not os.path.exists("./ollama"):
        print("📥 Downloading Ollama Linux Binary...")
        os.system("curl -L https://ollama.com/download/ollama-linux-amd64 -o ollama")
        os.system("chmod +x ollama")

    print("🟢 Starting Ollama Background Service (GPU Mode)...")
    subprocess.Popen(["./ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Wait until the local API is actually up
    for i in range(30):
        try:
            r = httpx.get(f"{OLLAMA_HOST}/api/version", timeout=2.0)
            if r.status_code == 200:
                print(f"✅ Engine Ready (version {r.json().get('version', '?')})")
                break
        except Exception:
            time.sleep(1)
    else:
        print("⚠️ Ollama did not respond in time — continuing anyway")

    print(f"🧠 Pulling AI Model ({MODEL_NAME})... Please wait.")
    os.system(f"./ollama pull {MODEL_NAME}")
    print("✅ Engine Ready & Loaded on GPU!")


setup_ollama()


def jarvis_chat_api(api_key, system_prompt, user_message):
    if api_key != API_KEY:
        return "🚨 ERROR: Unauthorized! Access Denied by AR Patel Security."

    if not (user_message or "").strip():
        return "⚠️ Empty message."

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt or "You are a helpful assistant."},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_ctx": 4096,
        },
    }

    try:
        response = httpx.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=120.0)
        if response.status_code == 200:
            result = response.json().get("message", {}).get("content", "")
            return re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()
        return f"🚨 Engine Error: {response.text}"
    except Exception as e:
        return f"🚨 Exception: {str(e)}"


with gr.Blocks() as demo:
    gr.Markdown("# ⚡ AR PATEL STUDIO - GPU Private LLM")
    gr.Markdown("⚠️ *Strictly for internal Jarvis routing. Unauthorized access will be blocked.*")

    key_input = gr.Textbox(
        label="Security Key",
        type="password",
        placeholder="Enter ARPATEL_API_KEY",
    )
    sys_input = gr.Textbox(
        label="System Persona",
        lines=3,
        value="Tum Jarvis ho, Amit Patel ke assistant.",
    )
    user_input = gr.Textbox(
        label="User Message",
        lines=3,
        placeholder="Command here...",
    )
    output_box = gr.Textbox(label="Jarvis Response", lines=5)
    btn = gr.Button("🧠 Process Command", variant="primary")

    btn.click(
        fn=jarvis_chat_api,
        inputs=[key_input, sys_input, user_input],
        outputs=output_box,
        api_name="chat",
    )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        theme=gr.themes.Monochrome(),
    )
