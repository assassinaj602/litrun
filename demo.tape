# VHS Tape Configuration for litrun Terminal Demo
# Output: demo.gif
Output demo.gif

Set FontSize 18
Set Width 1200
Set Height 720
Set Theme "Charm"
Set Padding 20

# 1. Inspect Hardware
Type "litrun inspect"
Enter
Sleep 3s

# 2. List Models & Registries
Type "litrun list"
Enter
Sleep 3s

# 3. One-Command LLM Run on Embedded Linux
Type "litrun run qwen2.5-0.5b --prompt 'Explain how litrun avoids kernel OOM crashes on Raspberry Pi.'"
Enter
Sleep 5s

