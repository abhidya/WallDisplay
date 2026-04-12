import ast
import re

with open("web/backend/routers/projection_router.py", "r") as f:
    content = f.read()

match1 = re.search(r"ANIMATION_LIBRARY = \[.*?\]\n", content, re.DOTALL)
list1_str = match1.group(0)

match2 = re.search(r"ANIMATION_LIBRARY\.extend\(\[.*?\]\)\n", content, re.DOTALL)
list2_str = match2.group(0)

list1_code = list1_str.replace("ANIMATION_LIBRARY = ", "").strip()
list1 = ast.literal_eval(list1_code)

list2_code = list2_str.replace("ANIMATION_LIBRARY.extend(", "")[:-2].strip()
list2 = ast.literal_eval(list2_code)

merged = {}
for item in list1:
    merged[item["id"]] = item

for item in list2:
    if item["id"] in merged:
        if "imported Shadertoy" in item["description"]:
            merged[item["id"]]["description"] = item["description"]
    else:
        merged[item["id"]] = item

new_list_str = "ANIMATION_LIBRARY = [\n"
for item in merged.values():
    new_list_str += "    {\n"
    for k, v in item.items():
        if isinstance(v, str):
            new_list_str += f'        "{k}": "{v}",\n'
        elif isinstance(v, list):
            new_list_str += f'        "{k}": {v},\n'
        else:
            new_list_str += f'        "{k}": {v},\n'
    new_list_str += "    },\n"
new_list_str += "]\n"

new_content = content.replace(list1_str, new_list_str).replace(list2_str, "")

with open("web/backend/routers/projection_router.py", "w") as f:
    f.write(new_content)
