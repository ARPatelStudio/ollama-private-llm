import os
import re
import sys
import time
import subprocess

import httpx
import gradio as gr

# ==========================================
# ⚡ AR PATEL STUDIO - PRIVATE GPU LLM (OLLAMA + GRADIO 6)
# ==========================================
# FIX 1: Gradio 6 me ChatInterface ka 'type' parameter remove ho gaya hai
#        (messages format ab DEFAULT hai) -> TypeError ka yahi reason tha.
# FIX 2: 'theme' ab Blocks() me nahi, launch() me pass hota hai.

# ---------------- CONFIG ----------------
MODEL_NAME  = os.environ.get("MODEL_NAME", "qwen2.5:3b")
OLLAMA_PORT = int(os.environ.get("OLLAMA_PORT", "11434"))
OLLAMA_BASE = f"http://127.0.0.1:{OLLAMA_PORT}"
OLLAMA_URL  = "https://ollama.com/download/ollama-linux-amd64.tar.zst"

HOME       = os.path.expanduser("~")
OLLAMA_DIR = os.path.join(HOME, ".ollama_bin")
OLLAMA_BIN = os.path.join(OLLAMA_DIR, "bin", "ollama")
LOG_PATH   = os.path.join(OLLAMA_DIR, "ollama.log")

# Paid persistent disk laga ho to model baar-baar download nahi hoga
if os.path.isdir("/data") and os.access("/data", os.W_OK):
    MODELS_DIR = "/data/ollama_models"
else:
    MODELS_DIR = os.path.join(HOME, ".ollama", "models")

API_KEY = os.environ.get("ARPATEL_API_KEY", "fallback_key_123")
if API_KEY == "fallback_key_123":
    print("⚠️ WARNING: 'ARPATEL_API_KEY' secret set nahi hai — fallback key use ho raha hai!")

DEFAULT_PERSONA = (
    "Tum Jarvis ho, Amit Patel ke personal AI assistant. "
    "Answers concise, direct aur professional rakho."
)

# ==========================================
# 1. 🚀 ENGINE SETUP (DOWNLOAD & START)
# ==========================================
def log_gpu_info():
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            print(f"🖥️ GPU detected: {r.stdout.strip()}")
        else:
            print("⚠️ GPU nahi mila — CPU mode chalega (slow). Hardware check karo.")
    except Exception:
        print("⚠️ nvidia-smi unavailable — CPU mode.")

def install_ollama():
    if os.path.exists(OLLAMA_BIN):
        print("✅ Ollama engine already installed — download skip.")
        return

    os.makedirs(OLLAMA_DIR, exist_ok=True)
    tarball = os.path.join(OLLAMA_DIR, "ollama.tar.zst")

    print("📥 Downloading official Ollama engine (.tar.zst)...")
    r = subprocess.run(["curl", "-L", "--retry", "3", "--retry-delay", "2",
                        "-o", tarball, OLLAMA_URL])
    if r.returncode != 0 or not os.path.isfile(tarball) or os.path.getsize(tarball) < 1_000_000:
        raise RuntimeError("❌ Ollama engine download fail hua!")

    try:
        import zstandard  # noqa: F401
    except ImportError:
        print("📦 Installing Python 'zstandard' package...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "zstandard"], check=True)

    import tarfile
    import zstandard as zstd

    size_mb = os.path.getsize(tarball) / 1e6
    print(f"📦 Unpacking Ollama engine ({size_mb:.1f} MB)...")
    with open(tarball, "rb") as f_in:
        with zstd.ZstdDecompressor().stream_reader(f_in) as reader:
            with tarfile.open(fileobj=reader, mode="r|") as tar:
                tar.extractall(OLLAMA_DIR)

    os.chmod(OLLAMA_BIN, 0o755)
    os.remove(tarball)
    print(f"✅ Ollama binary ready: {OLLAMA_BIN}")

def start_ollama():
    env = os.environ.copy()
    env.update({
        "OLLAMA_HOST":       f"127.0.0.1:{OLLAMA_PORT}",
        "OLLAMA_MODELS":     MODELS_DIR,
        "OLLAMA_KEEP_ALIVE": os.environ.get("OLLAMA_KEEP_ALIVE", "30m"),
        "OLLAMA_ORIGINS":    "*",
    })
    os.makedirs(MODELS_DIR, exist_ok=True)

    print("🟢 Starting Ollama background service (GPU mode)...")
    log_f = open(LOG_PATH, "ab")
    subprocess.Popen([OLLAMA_BIN, "serve"], stdout=log_f, stderr=log_f, env=env)

    print("⏳ Probing Ollama health...")
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            r = httpx.get(f"{OLLAMA_BASE}/api/version", timeout=2.0)
            if r.status_code == 200:
                print(f"✅ Engine ready (v{r.json().get('version')}) | log: {LOG_PATH}")
                return env
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError(f"❌ Ollama 120s me start nahi hua. Log dekho: {LOG_PATH}")

def pull_model(env):
    print(f"🧠 Pulling model '{MODEL_NAME}'... (first run me ~2GB download hota hai)")
    for attempt in range(1, 4):
        r = subprocess.run([OLLAMA_BIN, "pull", MODEL_NAME], env=env)
        if r.returncode == 0:
            print(f"✅ Model '{MODEL_NAME}' ready & loaded!")
            return
        print(f"⚠️ Pull attempt {attempt}/3 failed — retry...")
        time.sleep(3)
    raise RuntimeError(f"❌ Model '{MODEL_NAME}' pull fail hua.")

def warmup_model():
    try:
        t0 = time.time()
        httpx.post(
            f"{OLLAMA_BASE}/api/chat",
            json={"model": MODEL_NAME,
                  "messages": [{"role": "user", "content": "hi"}],
                  "stream": False, "options": {"num_predict": 4}},
            timeout=180.0,
        )
        print(f"🔥 Warmup done in {time.time() - t0:.1f}s — model VRAM me loaded.")
    except Exception as e:
        print(f"⚠️ Warmup skipped: {e}")

# Ignite the engine when Space starts
print("=" * 60)
print("⚡ AR PATEL STUDIO — booting private LLM engine...")
log_gpu_info()
install_ollama()
ENGINE_ENV = start_ollama()
pull_model(ENGINE_ENV)
warmup_model()
print("=" * 60)

# ==========================================
# 2. 🛡️ SECURITY GATEWAY + CHAT LOGIC
# ==========================================
THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
THINK_OPEN  = re.compile(r"<think>.*", re.DOTALL)

def clean_output(text: str) -> str:
    """<think>...</think> tags + unclosed <think> hata do"""
    text = THINK_BLOCK.sub("", text or "")
    text = THINK_OPEN.sub("", text)
    return text.strip()

def build_messages(system_prompt: str, history, user_message: str):
    msgs = [{"role": "system", "content": system_prompt or DEFAULT_PERSONA}]
    for m in (history or []):
        if isinstance(m, dict):
            role, content = m.get("role"), m.get("content")
            if isinstance(content, list):  # multimodal-style content
                content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
            if role in ("user", "assistant", "system") and content:
                msgs.append({"role": role, "content": str(content)})
        elif isinstance(m, (list, tuple)) and len(m) == 2:  # purana tuples format
            user_msg, bot_msg = m
            if user_msg:
                msgs.append({"role": "user", "content": str(user_msg)})
            if bot_msg:
                msgs.append({"role": "assistant", "content": str(bot_msg)})
    msgs.append({"role": "user", "content": user_message})
    return msgs

def call_ollama(messages):
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
        "keep_alive": "30m",
        "options": {"temperature": 0.7, "num_ctx": 4096, "num_predict": 1024},
    }
    resp = httpx.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=300.0)
    if resp.status_code == 200:
        content = resp.json().get("message", {}).get("content", "")
        return clean_output(content) or "⚠️ Empty response."
    return f"🚨 Engine Error (HTTP {resp.status_code}): {resp.text[:300]}"

def check_key(api_key):
    if not api_key or str(api_key).strip() != API_KEY:
        return "🚨 ERROR: Unauthorized! Access Denied by AR Patel Security."
    return None

def jarvis_chat(msg_or_hist, hist_or_msg, api_key, system_prompt):
    # Gradio 6 ChatInterface: fn(message, history, *additional_inputs)
    # Order alag ho to bhi dono handle ho jaye — defensive signature:
    if isinstance(msg_or_hist, list) and isinstance(hist_or_msg, str):
        history, message = msg_or_hist, hist_or_msg
    else:
        message, history = msg_or_hist, hist_or_msg
    history = history or []

    err = check_key(api_key)
    if err:
        return err
    if not (message and str(message).strip()):
        return "⚠️ Message khali hai."

    try:
        return call_ollama(build_messages(system_prompt, history, str(message)))
    except httpx.TimeoutException:
        return "🚨 Timeout — engine busy hai, thodi der baad try karo."
    except Exception as e:
        return f"🚨 Exception: {e}"

def jarvis_single_shot(api_key, system_prompt, user_message):
    """External Jarvis routing ke liye simple single-shot endpoint"""
    return jarvis_chat(user_message, [], api_key, system_prompt)

# ==========================================
# 3. 🎨 GRADIO UI (GRADIO 6 COMPATIBLE)
# ==========================================
with gr.Blocks(title="AR PATEL STUDIO — GPU Private LLM") as demo:  # FIX: theme yahan nahi
    gr.Markdown("# ⚡ AR PATEL STUDIO — GPU Private LLM")
    gr.Markdown("⚠️ *Strictly for internal Jarvis routing. Unauthorized access will be blocked.*")

    # Main chat — FIX: 'type' parameter REMOVE kiya (Gradio 6 default = messages)
    gr.ChatInterface(
        fn=jarvis_chat,
        additional_inputs=[
            gr.Textbox(label="🔐 Security Key", type="password",
                       placeholder="ARPATEL_API_KEY enter karo"),
            gr.Textbox(label="🧠 System Persona", lines=2, value=DEFAULT_PERSONA),
        ],
        retry_btn="🔄 Retry",
        undo_btn="↩️ Undo",
        clear_btn="🗑️ New Chat",
    )

    gr.Markdown("---\n### 🔌 Raw Single-Shot API (external routing ke liye)")
    with gr.Accordion("Direct API Call", open=False):
        raw_key = gr.Textbox(label="Security Key", type="password")
        with gr.Row():
            raw_sys  = gr.Textbox(label="System Persona", lines=2, value=DEFAULT_PERSONA)
            raw_user = gr.Textbox(label="User Message", lines=2, placeholder="Command here...")
        raw_out = gr.Textbox(label="Jarvis Response", lines=5)
        raw_btn = gr.Button("🧠 Process Command", variant="primary")
        raw_btn.click(
            fn=jarvis_single_shot,
            inputs=[raw_key, raw_sys, raw_user],
            outputs=raw_out,
            api_name="jarvis",  # stable endpoint name for external router
        )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", "7860")),
        show_error=True,
        theme=gr.themes.Monochrome(),  # FIX 2: theme ab launch() me
    )
