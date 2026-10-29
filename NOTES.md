# Baseline, 2026-10-18
- Model: qwen3.8:27b (Ollama, llamacpp runner), 17 GB, 100% GPU
- Context applied: 32768
- VRAM in use with model loaded: about 21.3 GB of 24.6 GB (desktop uses about 1.5 GB)
- Generation: about 79 tokens/sec (219-token sample)
- Thinking: on by default. Shows in `ollama run` as "Thinking..." and used about 200 tokens on a trivial prompt
- Idle unload: about 5 minutes, then the next request pays a cold load
- smoke.py: returns a correct tool call for add(1234, 5678)
