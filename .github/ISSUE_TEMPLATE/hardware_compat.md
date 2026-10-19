---
name: Hardware Compatibility Report
about: Submit telemetry from a newly tested SBC or SoC board
title: "[HARDWARE] "
labels: ["hardware-compat"]
assignees: ""
---

### Board Information
- **Manufacturer / Board Name**: (e.g. Radxa Rock 5B, Orange Pi 5 Plus, BeagleBone AI-64)
- **SoC Model**: (e.g. Rockchip RK3588, TI TDA4VM, Allwinner H616)
- **RAM Capacity**: (e.g. 4GB, 8GB, 16GB)
- **Cooling Solution**: (Passive heatsink / Active fan / Open air)

### Output of `litrun inspect`
```json
// Paste the exact output of: litrun inspect --json
```

### Benchmark Results
Run `litrun benchmark qwen2.5-0.5b` and paste the output:
```text
Tokens/sec:
Peak RAM (MB):
Max Temperature (°C):
```

### Working / Non-Working Observations
- Any kernel warnings or dmesg logs?
- Did thermal throttling engage during generation?

