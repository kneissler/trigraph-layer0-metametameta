import xml.etree.ElementTree as ET
import html
import re

def clean_html(text):
    if not text:
        return ''
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    return text.strip()

def normalize_color(color_str):
    if not color_str:
        return ''
    color_str = color_str.lower().strip()
    if 'light-dark(' in color_str:
        content = color_str.replace('light-dark(', '')
        if content.startswith('rgb('):
            match = re.search(r'rgb\([^)]+\)', content)
            if match:
                color_str = match.group(0)
        else:
            color_str = content.split(',')[0].strip()
    if color_str.startswith('rgb('):
        rgb_values = color_str.replace('rgb(', '').replace(')', '').replace(' ', '')
        try:
            r, g, b = [int(v.strip()) for v in rgb_values.split(',')]
            color_str = f'#{r:02x}{g:02x}{b:02x}'
        except:
            pass
    color_str = color_str.replace(')', '')
    return color_str

def extract_style_property(style, prop):
    if not style:
        return None
    match = re.search(f'{prop}=([^;]+)', style)
    return match.group(1) if match else None

tree = ET.parse('/Users/jakneissler/git/github/trigraph/trigraph-layer0-metametameta/doc/complete-graph-with-grounding.drawio')
root = tree.getroot()

# All area IDs with their names
area_mapping = {
    'y8TMbiYartTCWvdmmpqS-7': 'layer0-mlN-metaN',
    'y8TMbiYartTCWvdmmpqS-10': 'layer0-ml3-metaMetaMeta',
    '4rcjDRaJ5Oi-6SsU8W6B-1': 'layer0-ml2-metalevels',
    '4rcjDRaJ5Oi-6SsU8W6B-4': 'layer0-ml2-types',
    'y8TMbiYartTCWvdmmpqS-112': 'layer0-ml2-relationProperties',
    'y8TMbiYartTCWvdmmpqS-117': 'layer1-ml2-classInheritance-relations',
    'y8TMbiYartTCWvdmmpqS-116': 'layer1-ml2-classInheritance-signatures',
    'y8TMbiYartTCWvdmmpqS-296': 'layer1-ml2-persistance-types',
    'y8TMbiYartTCWvdmmpqS-297': 'layer1-ml2-persistance-signatures',
    'y8TMbiYartTCWvdmmpqS-298': 'layer1-ml2-persistance-relations',
    'y8TMbiYartTCWvdmmpqS-309': 'layer2-ml2-grounding',
    'y8TMbiYartTCWvdmmpqS-231': 'layer2-ml1-grounding',
}

# Build node name mapping
node_names = {}
for cell in root.iter('mxCell'):
    value = cell.get('value', '')
    clean_val = clean_html(value)
    cell_id = cell.get('id')
    if clean_val and cell_id and not cell.get('source'):
        node_names[cell_id] = clean_val

# Collect all area edges with their colors
area_edges = {}
for cell in root.iter('mxCell'):
    source_id = cell.get('source')
    target_id = cell.get('target')

    if source_id in area_mapping and target_id:
        style = cell.get('style', '')
        text_color = extract_style_property(style, 'fontColor')
        if not text_color:
            text_color = extract_style_property(style, 'strokeColor')

        normalized = normalize_color(text_color) if text_color else ''
        target_name = node_names.get(target_id, target_id)

        color_type = 'cyan/ml' if normalized in ['#00cccc', '#00b0b0'] else 'red/type' if normalized == '#ff0000' else 'other'

        area_edges[source_id] = {
            'area_name': area_mapping[source_id],
            'target': target_name,
            'color': normalized,
            'color_type': color_type
        }

print("=" * 80)
print("DIAGRAM CONSISTENCY ANALYSIS")
print("=" * 80)
print()

print("CURRENT STATE:")
print("-" * 80)
print()

# Group by layer and category
layer0_ml2 = []
layer0_ml3 = []
layer0_mlN = []
layer1_classInheritance = []
layer1_persistance = []
layer2_grounding = []

for area_id, area_name in area_mapping.items():
    edge_info = area_edges.get(area_id)

    entry = {
        'area_name': area_name,
        'has_edge': edge_info is not None,
        'target': edge_info['target'] if edge_info else 'MISSING',
        'color_type': edge_info['color_type'] if edge_info else 'MISSING'
    }

    if 'layer0-ml2' in area_name:
        layer0_ml2.append(entry)
    elif 'layer0-ml3' in area_name:
        layer0_ml3.append(entry)
    elif 'layer0-mlN' in area_name:
        layer0_mlN.append(entry)
    elif 'layer1-ml2-classInheritance' in area_name:
        layer1_classInheritance.append(entry)
    elif 'layer1-ml2-persistance' in area_name:
        layer1_persistance.append(entry)
    elif 'layer2' in area_name:
        layer2_grounding.append(entry)

def print_group(title, entries):
    print(f"{title}:")
    for entry in sorted(entries, key=lambda x: x['area_name']):
        status = "✓" if entry['has_edge'] else "✗"
        print(f"  {status} {entry['area_name']:45} -> {entry['target']:10} ({entry['color_type']})")
    print()

print_group("Layer0 ML2 Areas", layer0_ml2)
print_group("Layer0 ML3 Areas", layer0_ml3)
print_group("Layer0 MLN Areas", layer0_mlN)
print_group("Layer1 ClassInheritance Areas", layer1_classInheritance)
print_group("Layer1 Persistance Areas", layer1_persistance)
print_group("Layer2 Grounding Areas", layer2_grounding)

print("=" * 80)
print("ANALYSIS & RECOMMENDATIONS:")
print("=" * 80)
print()

cyan_count = sum(1 for e in area_edges.values() if e['color_type'] == 'cyan/ml')
red_count = sum(1 for e in area_edges.values() if e['color_type'] == 'red/type')
missing_count = len(area_mapping) - len(area_edges)

print(f"Current area-to-node edges: {len(area_edges)}")
print(f"  - Cyan (ml):   {cyan_count}")
print(f"  - Red (type):  {red_count}")
print(f"  - Missing:     {missing_count}")
print()
print(f"Expected (per user): 6 cyan, 4 red")
print(f"Gap: {6 - cyan_count} more cyan edges needed")
print()

print("LIKELY MISSING EDGES (based on naming patterns):")
print("-" * 80)
print()

# Identify likely missing edges
suggestions = []

# layer0-ml2 areas should target ml2 with cyan
if '4rcjDRaJ5Oi-6SsU8W6B-1' not in area_edges:  # layer0-ml2-metalevels
    suggestions.append(("layer0-ml2-metalevels", "ml2", "cyan", "Pattern: other layer0-ml2 areas -> ml2 (cyan)"))

# layer1-ml2-classInheritance areas should target ml2 with cyan (matching -relations)
if 'y8TMbiYartTCWvdmmpqS-116' not in area_edges:  # layer1-ml2-classInheritance-signatures
    suggestions.append(("layer1-ml2-classInheritance-signatures", "ml2", "cyan", "Pattern: classInheritance-relations -> ml2 (cyan)"))

# layer2 grounding areas - need to determine pattern
if 'y8TMbiYartTCWvdmmpqS-231' not in area_edges:  # layer2-ml1-grounding
    suggestions.append(("layer2-ml1-grounding", "ml1", "cyan?", "Pattern: likely targets ml1 based on name"))

if 'y8TMbiYartTCWvdmmpqS-309' not in area_edges:  # layer2-ml2-grounding
    suggestions.append(("layer2-ml2-grounding", "ml2", "cyan?", "Pattern: likely targets ml2 based on name"))

for i, (area, target, color, reason) in enumerate(suggestions, 1):
    print(f"{i}. {area}")
    print(f"   Should target: {target} with {color} edge")
    print(f"   Reasoning: {reason}")
    print()

print("=" * 80)
print("RECOMMENDATION:")
print("=" * 80)
print()
print("To achieve the expected '6 cyan, 4 red' configuration, add these 2 edges:")
print("  1. layer0-ml2-metalevels -> ml2 (cyan)")
print("  2. layer1-ml2-classInheritance-signatures -> ml2 (cyan)")
print()
print("These follow the clear pattern where layer0-ml2 and layer1-ml2-classInheritance")
print("areas all target ml2 with cyan edges.")
