# 🚀 J.A.R.V.I.S. Monolithic Omni-Core Deployment Dockerfile (Hugging Face Edition)
# Developed By: AR PATEL STUDIO
FROM python:3.10-slim

# Working directory set kar rahe hain
WORKDIR /app

# Audio processing aur system level tools install kar rahe hain
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Requirements file copy karke install karna
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Aapka poora main.py aur baaki files copy karna
COPY . .

# Hugging Face default port 7860 use karta hai
ENV PORT=7860
EXPOSE 7860

# JARVIS Backend Boot Command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
