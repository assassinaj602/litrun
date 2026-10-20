# VHS Tape Configuration for litrun Terminal Demo
# Output: assets/demo.gif
Output assets/demo.gif

Set FontSize 16
Set Width 960
Set Height 580
Set Theme "Dracula"
Set Padding 15

# 1. Inspect Hardware & Vector Extensions
Type "litrun inspect"
Enter
Sleep 3s

# 2. List Curated Model Registry
Type "litrun list"
Enter
Sleep 2.5s

# 3. One-Command LLM Inference with Active Governor
Type "litrun run smollm2-135m --prompt 'What is edge AI?'"
Enter
Sleep 4.5s
