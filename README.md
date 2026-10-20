# ⚡ litrun

[![CI Matrix](https://github.com/assassinaj602/litrun/actions/workflows/ci.yml/badge.svg)](https://github.com/assassinaj602/litrun/actions)
[![Release & Distribution](https://github.com/assassinaj602/litrun/actions/workflows/release.yml/badge.svg)](https://github.com/assassinaj602/litrun/releases)
[![PyPI version](https://img.shields.io/pypi/v/litrun.svg?color=blue)](https://pypi.org/project/litrun/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Supported SoCs](https://img.shields.io/badge/SoCs-BCM2711%20%7C%20BCM2712%20%7C%20RK3588%20%7C%20x86__64-green.svg)](#hardware-support-matrix)
[![GitHub release](https://img.shields.io/github/v/release/assassinaj602/litrun?color=orange)](https://github.com/assassinaj602/litrun/releases/tag/v0.1.0)

> **Deploy any LLM to any embedded Linux device in one command.**  
> A lightweight, universal open-source runtime that eliminates hardware fragmentation for on-device AI across Raspberry Pi, Orange Pi, industrial SoCs, and ARM64 / RISC-V edge boards.

---

## 🚀 Quickstart: The One Working Moment

### 1. Instant POSIX Bootstrap (No toolchains, no cmake)
```bash
curl -sSL https://litrun.dev/install | sh
```
*Or via pip:*
```bash
pip install litrun
```

### 2. Inspect Hardware Vector Capabilities (<5ms)
```bash
litrun inspect
```

### 3. Run Your First Model With Zero Guesswork
```bash
litrun run qwen2.5-0.5b
```

```text
→ Detected: Raspberry Pi 5 Model B (BCM2712 Cortex-A76, 8192 MB RAM)
→ Selected: qwen2.5-0.5b-Q4_K_M (optimal RAM envelope: 900MB required / 6800MB free)
→ Binary:   pulling precompiled ARM64 a76+dotprod build... done [cached]
→ Model:    streaming weights from HuggingFace (397MB)... done
→ Warmup complete. Running at 14.2 tokens/sec on 4 threads. Type to interact.

> Hello litrun! How do you prevent out-of-memory crashes on embedded devices?
litrun: I integrate a dedicated C resource governor that inspects Linux memory
cgroups and /proc/meminfo before model allocation, preventing kernel OOM-killer panics.
```

---

## 🧠 Why Litrun Exists

| The Amateur Edge AI Struggle | The Litrun Way |
| :--- | :--- |
| **45-minute on-device compilation** on Pi 4 that thermal throttles and crashes during linking. | **Instant prebuilt binaries** cross-compiled per microarchitecture (Cortex-A72 NEON, Cortex-A76 DotProd). |
| **Quantization guesswork**: Devs guess between Q4_K_M, Q5_K_S, IQ3_XS without knowing if RAM + KV cache fits. | **Hardware-aware envelope**: Evaluates free RAM + KV cache before launch, picking optimal accuracy safely. |
| **Silent kernel panics**: Linux OOM-killer randomly terminates services or hangs the board. | **Active Resource Governor**: Hard memory ceilings and dynamic thermal throttling. |
| **Disjoint vendor APIs**: llama.cpp, ONNX Runtime, and RKNN share zero API commonality. | **Unified Interface**: One CLI, Python SDK (`from litrun import Model`), and drop-in OpenAI REST API. |

---

## 🏛️ System Architecture

Litrun is architected in 5 decoupled layers:

```
┌────────────────────────────────────────────────────────┐
│  LAYER 1: User Surface (CLI, Python SDK, REST Server)  │
│  litrun run/pull/list/inspect/serve • from litrun import Model  │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│  LAYER 2: Orchestration & Active Resource Governor     │
│  RAM Safety Ceiling (85%) • Cgroup v1/v2 • Thermal Monitor│
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│  LAYER 3: Hardware Abstraction Native Engine (Pure C99) │
│  Devicetree • Aux Vector (NEON, DotProd, i8mm) • <5ms  │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│  LAYER 4: Pluggable Inference Backends                 │
│  llama.cpp (ARM DotProd) • RKNN NPU • ONNX Runtime     │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│  LAYER 5: Distributed Metadata Registries (Flat YAML)   │
│  models.yaml • hardware.yaml • binaries.yaml (GitHub CDN) │
└────────────────────────────────────────────────────────┘
```

---

## 💻 Python SDK Usage

```python
from litrun import Model, probe_hardware, poll_governor

# 1. Inspect hardware and active memory governor
hw = probe_hardware()
print(f"Board: {hw.board_name} | Profile: {hw.profile_id}")
print(f"Vector Acceleration: NEON={hw.has_neon}, DotProd={hw.has_dotprod}")

# 2. Automatically resolves hardware, checks RAM envelope, pulls weights
model = Model.load("qwen2.5-0.5b")

# 3. Stream tokens in real time
for chunk in model.stream("Summarize industrial sensor telemetry:"):
    print(chunk, end="", flush=True)

# 4. Or launch the local OpenAI-compatible REST server
# model.serve(host="0.0.0.0", port=8080)
```

---

## 🌐 OpenAI-Compatible REST Server

Drop Litrun directly into LangChain, LlamaIndex, AutoGen, or web frontends:

```bash
litrun serve --port 8080 qwen2.5-0.5b
```

Send standard OpenAI completions:

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-0.5b",
    "messages": [{"role": "user", "content": "Explain edge computing in one sentence."}],
    "stream": true
  }'
```

Query live hardware and thermal telemetry via REST:
```bash
curl http://localhost:8080/v1/hardware
```

---

## 📊 Hardware Support Matrix

| Board / SBC | SoC Architecture | Vector Extensions / NPU | Default Speed | Phase |
| :--- | :--- | :--- | :--- | :--- |
| **Raspberry Pi 5** | BCM2712 (Cortex-A76) | ARM NEON + DotProd (ASIMDDP) | 14.2 tok/s | Phase 1 (GA) |
| **Raspberry Pi 4 Model B** | BCM2711 (Cortex-A72) | ARM NEON (ASIMD) | 8.2 tok/s | Phase 1 (GA) |
| **Raspberry Pi 3 / Zero 2 W**| BCM2837 (Cortex-A53) | ARM NEON Baseline | 14.5 tok/s (135M) | Phase 1 (GA) |
| **Orange Pi 5 / 5 Plus** | Rockchip RK3588 | 6 TOPS NPU (RKNN) + A76/A55 | 18.5 tok/s | Phase 2 |
| **NVIDIA Jetson Orin Nano** | Tegra Orin (Cortex-A78AE)| Ampere GPU + NVDLA | 28.0 tok/s | Phase 2 |
| **Generic x86_64 Edge Host**| Intel Core / AMD Ryzen | AVX2 + FMA | 32.0 tok/s | Phase 1 (GA) |

---

## 🛠️ Building & Testing from Source

```bash
# Clone the repository
git clone https://github.com/litrun/litrun.git
cd litrun

# Build C Native Core and Shared Library
make all

# Run complete test suite (C99 unit tests + Python test suite)
make test

# Install locally in editable development mode
make install-dev
```

---

## 📄 License

Litrun is 100% open-source software licensed under the [MIT License](LICENSE).
Built with ❤️ for the embedded Linux and robotics community.

