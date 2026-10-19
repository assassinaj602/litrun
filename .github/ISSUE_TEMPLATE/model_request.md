---
name: Model Registry Request
about: Propose adding a new curated model or quantization to models.yaml
title: "[MODEL] "
labels: ["model-registry"]
assignees: ""
---

### Model Details
- **Model ID**: (e.g. `smollm2-1.7b`)
- **Full Model Name**: (e.g. SmolLM2 1.7B Instruct)
- **HuggingFace Repository URL**:
- **GGUF File Direct Download URL**:
- **Context Length**: (e.g. 8192)

### Quantization Variants & Sizes
| Quantization | Size (MB) | Required RAM (MB) | Recommended Target SoCs |
| :--- | :--- | :--- | :--- |
| Q4_K_M | | | |
| Q8_0 | | | |

### Verification
- [ ] Verified SHA-256 checksum matches HuggingFace source
- [ ] Successfully run inference with `litrun run <model>`
- [ ] Tested on physical board or QEMU

