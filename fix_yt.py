import json

with open('Untitled0.ipynb', 'r') as f:
    nb = json.load(f)

lines = nb['cells'][0]['source']

for i, line in enumerate(lines):
    if line.strip() == 'def _parse(self, item: dict, vid: str, brand: str) -> List[DiscourseRecord]:':
        lines[i] = '    def _parse(self, item: dict, vid: str) -> List[DiscourseRecord]:\n'
    elif line.strip() == 'raw_text=top.get("textDisplay",""),':
        lines.insert(i, '                brand_target=self._bd.detect(top.get("textDisplay","")),\n')
        # Also, I need to remove the previous brand_target=brand
    elif 'platform_source="youtube", brand_target=brand,' in line:
        lines[i] = '                platform_source="youtube",\n'
    elif line.strip() == 'brand = self._bd.detect(vid)':
        lines[i] = ''
    elif 'recs.extend(self._parse(item, vid, brand))' in line:
        lines[i] = '                    recs.extend(self._parse(item, vid))\n'
    elif 'recs.extend(self._parse(rep, vid, brand))' in line:
        lines[i] = '                            recs.extend(self._parse(rep, vid))\n'

with open('Untitled0.ipynb', 'w') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("YT Fixed!")
