import json

with open("generate_notebook.py", "r") as f:
    code = f.read()

# I will replace the generation blocks inside generate_notebook.py to apply the same patches 
# that were done in _fix_pipeline.py
