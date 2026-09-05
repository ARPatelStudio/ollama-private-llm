import os
import subprocess
import time
import httpx
import gradio as gr
import re

# ==========================================
# ⚡ AR PATEL STUDIO - PRIVATE GPU LLM (OLLAMA)
# ==========================================

# 1. 🚀 DOWNLOAD & START OLLAMA ENGINE ON GPU
def setup_ollama():
    print("⏳ Checking Ollama Engine...")
    if not os.path.exists("./ollama"):
        print("📥 Downloading Ollama Linux Binary from Official GitHub...")
        # 🚀 CRITICAL FIX: GitHub se direct binary download kar rahe hain (Fail-Proof)
        os.system("curl -L https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64 -o ollama")
        os.system("chmod +x ollama")
    
    print("🟢 Starting Ollama Background Service (GPU Mode)...")
    # Run Ollama in background
    subprocess.Popen(["./ollama", "serve"])
    
    # Wait for the engine to boot
    time.sleep(5)
    
    # Pulling Model (GPU par 3B model bohot fast chalega)
    print("🧠 Pulling AI Model (qwen2.5:3b)... Please wait.")
    os.system("./ollama pull qwen2.5:3b")
    print("✅ Engine Ready & Loaded on GPU!")

# Ignite the Engine when Space starts
setup_ollama()

# 2. 🛡️ MILITARY-GRADE SECURITY GATEWAY
API_KEY = os.environ.get("ARPATEL_API_KEY", "fallback_key_123")

def jarvis_chat_api(api_key, system_prompt, user_message):
    # Security Gate
    if api_key != API_KEY:
        return "🚨 ERROR: Unauthorized! Access Denied by AR Patel Security."
    
    # Payload for Ollama
    payload = {
        "model": "qwen2.5:3b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_ctx": 4096 # Large context window for history
        }
    }
    
    try:
        # Hit local Ollama engine hosted on HF
        response = httpx.post("http://127.0.0.1:11434/api/chat", json=payload, timeout=120.0)
        if response.status_code == 200:
            result = response.json().get("message", {}).get("content", "")
            # Remove any <think> tags completely
            clean_result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()
            return clean_result
        else:
            return f"🚨 Engine Error: {response.text}"
    except Exception as e:
        return f"🚨 Exception: {str(e)}"

# 3. 🎨 GRADIO UI & API EXPOSURE
with gr.Blocks(theme=gr.themes.Monochrome()) as demo:
    gr.Markdown("# ⚡ AR PATEL STUDIO - GPU Private LLM")
    gr.Markdown("⚠️ *Strictly for internal Jarvis routing. Unauthorized access will be blocked.*")
    
    with gr.Row():
        key_input = gr.Textbox(label="Security Key", type="password", placeholder="Enter ARPATEL_API_KEY")
    
    with gr.Row():
        sys_input = gr.Textbox(label="System Persona", lines=3, value="Tum Jarvis ho, Amit Patel ke assistant.")
        user_input = gr.Textbox(label="User Message", lines=3, placeholder="Command here...")
        
    output_box = gr.Textbox(label="Jarvis Response", lines=5)
    btn = gr.Button("🧠 Process Command", variant="primary")
    
    # Creates the /api/chat endpoint
    btn.click(
        fn=jarvis_chat_api, 
        inputs=[key_input, sys_input, user_input], 
        outputs=output_box,
        api_name="chat" 
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
