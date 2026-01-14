#!/usr/bin/env python3
"""
Generate complete-graph-with-grounding.md documentation from the DrawIO file.
"""

import xml.etree.ElementTree as ET
import re
from collections import defaultdict

DIAGRAM_PATH = '/Users/jakneissler/git/github/trigraph/trigraph-layer0-metametameta/doc/complete-graph-with-grounding.drawio'

def clean_html(text):
    """Remove HTML tags and decode HTML entities."""
    if not text:
        return ''
    import html
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    clean = html.unescape(clean)
    return clean.strip()

def extract_style_property(style, prop):
    """Extract a specific property from style string."""
    if not style:
        return None
    match = re.search(f'{prop}=([^;]+)', style)
    if match:
        return match.group(1)
    return None

def get_stroke_width(style):
    """Extract stroke width from style."""
    if not style:
        return '1'  # default
    width = extract_style_property(style, 'strokeWidth')
    return width if width else '1'

def get_shape_type(style):
    """Determine shape type from style."""
    if not style:
        return 'unknown'
    if 'ellipse' in style:
        return 'ellipse'
    elif 'hexagon' in style:
        return 'hexagon'
    elif 'whiteSpace=wrap' in style or 'rounded=0' in style:
        return 'rectangle'
    return 'other'

def get_text_style(value):
    """Determine text style from HTML value."""
    if not value:
        return 'normal'
    has_bold = '<b>' in value or '<b ' in value
    has_italic = '<i>' in value or '<i ' in value

    if has_bold and has_italic:
        return 'bold-italic'
    elif has_bold:
        return 'bold'
    elif has_italic:
        return 'italic'
    return 'normal'

def get_text_color(value):
    """Extract text color from HTML value."""
    if not value:
        return None
    # Look for light-dark() function first (handles nested rgb)
    # Match light-dark with nested parentheses
    match = re.search(r'color:\s*(light-dark\((?:[^()]*\([^()]*\)[^()]*)+\))', value)
    if match:
        return match.group(1)
    # Look for simple light-dark without nested parentheses
    match = re.search(r'color:\s*(light-dark\([^)]+\))', value)
    if match:
        return match.group(1)
    # Look for color in font tags
    match = re.search(r'color:\s*rgb\(([^)]+)\)', value)
    if match:
        return f'rgb({match.group(1)})'
    match = re.search(r'color:\s*([^;"\s]+)', value)
    if match:
        return match.group(1)
    match = re.search(r'color="([^"]+)"', value)
    if match:
        return match.group(1)
    return None

def color_to_markdown(color):
    """Convert color to HTML span with background color."""
    if not color or color == 'none':
        return 'none'
    # Clean up the color value
    clean_color = color.replace('light-dark(', '').replace(')', '')
    if ',' in clean_color:
        # Take the first color in light-dark
        clean_color = clean_color.split(',')[0].strip()

    # Determine text color (black or white) based on background brightness
    # Simple heuristic: if color starts with # and looks light, use black text
    text_color = '#000000'
    if clean_color.startswith('#') and len(clean_color) >= 7:
        # Extract RGB values
        try:
            r = int(clean_color[1:3], 16)
            g = int(clean_color[3:5], 16)
            b = int(clean_color[5:7], 16)
            # Calculate brightness
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            if brightness < 128:
                text_color = '#ffffff'
        except:
            pass

    return f'<span style="background-color: {clean_color}; color: {text_color}; padding: 2px 6px; border-radius: 3px;">{clean_color}</span>'

def normalize_color(color_str):
    """Normalize colors to hex format for consistent matching."""
    if not color_str:
        return ''
    color_str = color_str.lower().strip()
    # Handle light-dark() function - extract first color
    if 'light-dark(' in color_str:
        # Extract the content between light-dark( and )
        content = color_str.replace('light-dark(', '')
        # Find the first color (could be rgb(...) or #hex)
        if content.startswith('rgb('):
            # Extract complete rgb(...) function
            match = re.search(r'rgb\([^)]+\)', content)
            if match:
                color_str = match.group(0)
        else:
            # Extract first hex or named color (split at comma not inside parens)
            color_str = content.split(',')[0].strip()
    # Handle rgb() function - convert to hex
    if color_str.startswith('rgb('):
        # Extract RGB values
        rgb_values = color_str.replace('rgb(', '').replace(')', '').replace(' ', '')
        try:
            r, g, b = [int(v.strip()) for v in rgb_values.split(',')]
            color_str = f'#{r:02x}{g:02x}{b:02x}'
        except (ValueError, IndexError):
            # If parsing fails, keep as is
            pass
    # Remove any trailing parentheses
    color_str = color_str.replace(')', '')
    return color_str

def find_diagram_boundary():
    """Find the biggest yellowish circle to use as diagram boundary."""
    tree = ET.parse(DIAGRAM_PATH)
    root = tree.getroot()

    # Find all yellowish containers and pick the biggest
    yellowish_colors = ['#FEFFEF', '#fffef0', '#fffff0', '#fefef0']
    biggest_area = 0
    diagram_bounds = None

    for cell in root.iter('mxCell'):
        style = cell.get('style', '')
        if 'ellipse' in style:
            # Check if it has yellowish fill
            fill_color = extract_style_property(style, 'fillColor')
            if fill_color:
                clean_color = fill_color.replace('light-dark(', '').replace(')', '').split(',')[0].strip()
                if clean_color in yellowish_colors or clean_color.lower() in [c.lower() for c in yellowish_colors]:
                    # Get geometry
                    geom = cell.find('mxGeometry')
                    if geom is not None:
                        width = float(geom.get('width', 0))
                        height = float(geom.get('height', 0))
                        area = width * height
                        if area > biggest_area:
                            biggest_area = area
                            x = float(geom.get('x', 0))
                            y = float(geom.get('y', 0))
                            diagram_bounds = {
                                'x': x,
                                'y': y,
                                'width': width,
                                'height': height,
                                'cell_id': cell.get('id')
                            }

    return diagram_bounds

def is_in_diagram_area(x, y, diagram_bounds):
    """Check if a point is inside the diagram boundary."""
    if not diagram_bounds:
        return True  # If no boundary found, assume everything is diagram

    return (diagram_bounds['x'] <= x <= diagram_bounds['x'] + diagram_bounds['width'] and
            diagram_bounds['y'] <= y <= diagram_bounds['y'] + diagram_bounds['height'])

def is_outside_main_circle(x, y, main_circle_geom):
    """Check if a point is outside the main diagram circle."""
    if not main_circle_geom:
        return False
    center_x = main_circle_geom['x'] + main_circle_geom['width']/2
    center_y = main_circle_geom['y'] + main_circle_geom['height']/2
    radius_x = main_circle_geom['width']/2
    radius_y = main_circle_geom['height']/2
    normalized_dist = ((x - center_x)/radius_x)**2 + ((y - center_y)/radius_y)**2
    return normalized_dist > 1.0

def parse_legend_structure():
    """Parse the legend structure from the diagram (7 boxes with their entries and visual nodes)."""
    tree = ET.parse(DIAGRAM_PATH)
    root = tree.getroot()

    # Main circle geometry
    main_circle_geom = {'x': 49.0, 'y': -730.0, 'width': 1391.0, 'height': 1349.0}

    # Build parent-child map
    cell_map = {}
    for cell in root.iter('mxCell'):
        cell_id = cell.get('id')
        parent_id = cell.get('parent')
        value = cell.get('value', '')
        style = cell.get('style', '')
        geom = cell.find('mxGeometry')

        x, y, width, height = 0, 0, 0, 0
        if geom is not None:
            x = float(geom.get('x', 0))
            y = float(geom.get('y', 0))
            width = float(geom.get('width', 0))
            height = float(geom.get('height', 0))

        if cell_id:
            cell_map[cell_id] = {
                'element': cell,
                'parent_id': parent_id,
                'value': value,
                'style': style,
                'x': x,
                'y': y,
                'width': width,
                'height': height,
                'children': []
            }

    # Populate children
    for cell_id, info in cell_map.items():
        parent_id = info['parent_id']
        if parent_id and parent_id in cell_map:
            cell_map[parent_id]['children'].append(cell_id)

    # Find legend boxes (large shapes outside main circle)
    legend_boxes = []
    for cell_id, info in cell_map.items():
        cell = info['element']
        style = cell.get('style', '')
        value = cell.get('value', '')
        geom = cell.find('mxGeometry')

        if geom is not None:
            x = float(geom.get('x', 0))
            y = float(geom.get('y', 0))
            w = float(geom.get('width', 0))
            h = float(geom.get('height', 0))
            center_x = x + w/2
            center_y = y + h/2

            if is_outside_main_circle(center_x, center_y, main_circle_geom):
                clean_val = clean_html(value)
                if clean_val and h > 150 and w > 200:
                    legend_boxes.append({
                        'title': clean_val,
                        'cell_id': cell_id,
                        'x': x,
                        'y': y,
                        'width': w,
                        'height': h,
                    })

    legend_boxes.sort(key=lambda b: (b['y'], b['x']))

    # For each box, extract all text entries and visual nodes
    for box in legend_boxes:
        # Get all descendants recursively
        def get_all_descendants(cid):
            descendants = []
            if cid in cell_map:
                for child_id in cell_map[cid]['children']:
                    descendants.append((child_id, cell_map[child_id]))
                    descendants.extend(get_all_descendants(child_id))
            return descendants

        all_descendants = get_all_descendants(box['cell_id'])

        # Get text entries and visual nodes with their Y positions (for sorting)
        entries = []
        visual_nodes = {}  # Map node name to visual properties

        # First pass: collect all text entries
        text_entries = []  # entries with positions
        for desc_id, desc_info in all_descendants:
            value = desc_info['value']
            clean_val = clean_html(value)

            # Filter out corrupted entries with URL-encoded content
            if clean_val and '%3C' not in clean_val:
                entries.append({
                    'text': clean_val,
                    'y': desc_info['y']
                })

                # For text entries with '=', record position for matching
                if '=' in clean_val:
                    abbrev = clean_val.split('=')[0].strip()
                    # Remove arrow prefix if present
                    abbrev = abbrev.replace('→', '').strip()

                    # Skip long text (these are likely descriptions, not abbreviations)
                    if len(abbrev) <= 10:
                        text_entries.append({
                            'abbrev': abbrev,
                            'x': desc_info['x'],
                            'y': desc_info['y'],
                            'width': desc_info['width'],
                            'height': desc_info['height']
                        })

        # Second pass: find visual shapes and match them to nearby text
        for desc_id, desc_info in all_descendants:
            value = desc_info['value']
            clean_val = clean_html(value)
            style = desc_info['style']

            # Look for visual shapes (no text, has shape)
            if not clean_val:
                fill_color = extract_style_property(style, 'fillColor')
                stroke_color = extract_style_property(style, 'strokeColor')
                shape = get_shape_type(style)

                # Only process if it has a shape
                if shape and shape in ['ellipse', 'hexagon', 'rectangle', 'arrow']:
                    shape_x = desc_info['x']
                    shape_y = desc_info['y']

                    # Find the closest text entry
                    min_dist = float('inf')
                    closest_abbrev = None

                    for text_entry in text_entries:
                        # Calculate distance between shape and text
                        # Text is typically to the right of or below the shape
                        dx = shape_x - text_entry['x']
                        dy = shape_y - text_entry['y']
                        dist = (dx**2 + dy**2) ** 0.5

                        # Prefer shapes that are to the left of or above the text (within 50 units)
                        if dist < min_dist and dist < 50:
                            min_dist = dist
                            closest_abbrev = text_entry['abbrev']

                    # Store the visual properties for the closest text
                    # Prefer non-rectangle shapes (hexagon/ellipse) over rectangles
                    # because rectangles are often just background boxes
                    if closest_abbrev:
                        should_update = False
                        if closest_abbrev not in visual_nodes:
                            should_update = True
                        else:
                            # Update if new shape is better (non-rectangle over rectangle, or closer)
                            existing = visual_nodes[closest_abbrev]
                            if shape in ['hexagon', 'ellipse'] and existing['shape'] == 'rectangle':
                                should_update = True  # Prefer specific shapes
                            elif shape == existing['shape'] and min_dist < 30:
                                should_update = True  # Same shape type but closer

                        if should_update:
                            visual_nodes[closest_abbrev] = {
                                'shape': shape,
                                'fill_color': normalize_color(fill_color) if fill_color else None,
                                'stroke_color': normalize_color(stroke_color) if stroke_color else None,
                            }

        # Sort by Y position
        entries.sort(key=lambda e: e['y'])
        box['entries'] = [e['text'] for e in entries]
        box['visual_nodes'] = visual_nodes

    return legend_boxes

def parse_diagram():
    """Parse the DrawIO diagram and extract all information."""
    tree = ET.parse(DIAGRAM_PATH)
    root = tree.getroot()

    # Find the diagram boundary (biggest yellowish circle)
    diagram_bounds = find_diagram_boundary()

    # Data structures
    containers = []  # Areas/containers
    nodes = []       # Actual nodes
    legend_entries = []

    # Map cell IDs to their info for parent lookup and position
    cell_info = {}

    # First pass: collect all cells with their positions
    for cell in root.iter('mxCell'):
        cell_id = cell.get('id')
        parent_id = cell.get('parent')
        value = cell.get('value', '')
        style = cell.get('style', '')

        if not cell_id:
            continue

        # Skip edges
        if cell.get('source') or cell.get('target'):
            continue

        # Get position for diagram/legend determination
        geom = cell.find('mxGeometry')
        x, y = 0, 0
        if geom is not None:
            x = float(geom.get('x', 0))
            y = float(geom.get('y', 0))
            width = float(geom.get('width', 0))
            height = float(geom.get('height', 0))
            # Use center point
            x = x + width / 2
            y = y + height / 2

        cell_info[cell_id] = {
            'id': cell_id,
            'parent': parent_id,
            'value': value,
            'style': style,
            'clean_value': clean_html(value),
            'x': x,
            'y': y,
            'is_in_diagram': is_in_diagram_area(x, y, diagram_bounds)
        }

    # Second pass: categorize
    for cell_id, info in cell_info.items():
        value = info['value']
        clean_value = info['clean_value']
        style = info['style']
        parent_id = info['parent']

        # Skip root cells
        if cell_id in ['0', '1']:
            continue

        # Check if item is outside diagram area
        # Items outside the diagram are legend entries
        if not info['is_in_diagram']:
            # If it has '=' and is outside, it's a legend abbreviation entry
            if '=' in clean_value and len(clean_value) < 100:
                legend_entries.append({
                    'text': clean_value
                })
            # Skip items outside diagram area
            continue

        # Get fill color and stroke properties
        fill_color = extract_style_property(style, 'fillColor')
        stroke_color = extract_style_property(style, 'strokeColor')
        is_dashed = 'dashed=1' in style

        # Check if this is a red dashed boundary (exception case for containers)
        has_red_dashed_border = False
        if stroke_color and is_dashed:
            clean_stroke = stroke_color.replace('light-dark(', '').replace(')', '').split(',')[0].strip()
            has_red_dashed_border = clean_stroke.lower() in ['#ff0000', 'red', '#f00']

        # Determine if this should be processed
        has_fill = fill_color and fill_color not in ['none', 'default']

        # Skip if no fill color AND not red dashed boundary
        if not has_fill and not has_red_dashed_border:
            continue

        # Shapes with fill color and text are nodes
        # Shapes with fill color and no text are containers
        # Exception: Shapes with no fill but red dashed boundary are containers (even if they have text)
        if clean_value and has_fill and not has_red_dashed_border:
            # This is a NODE (has text and fill color, and not red dashed exception)
            shape = get_shape_type(style)
            text_style = get_text_style(value)
            text_color = get_text_color(value) or extract_style_property(style, 'fontColor')
            # Normalize text color to hex format for consistent matching
            text_color = normalize_color(text_color) if text_color else text_color
            stroke_width = get_stroke_width(style)

            nodes.append({
                'name': clean_value,
                'shape': shape,
                'text_style': text_style,
                'text_color': text_color,
                'fill_color': fill_color,
                'stroke_color': stroke_color,
                'stroke_width': stroke_width,
                'cell_id': cell_id,
                'x': info['x'],
                'y': info['y']
            })
        else:
            # This is a CONTAINER
            # Either: no text, or has red dashed boundary (exception)

            # Only include areas with fill color OR red border (solid or dashed)
            has_red_border = False
            if stroke_color:
                clean_stroke = stroke_color.replace('light-dark(', '').replace(')', '').split(',')[0].strip()
                has_red_border = clean_stroke.lower() in ['#ff0000', 'red', '#f00']

            if not (has_fill or has_red_border):
                continue

            # Find parent container
            parent_name = None
            if parent_id and parent_id != '1':
                parent_info = cell_info.get(parent_id)
                if parent_info:
                    parent_name = parent_info['clean_value'] or parent_id

            containers.append({
                'name': cell_id,
                'fill_color': fill_color,
                'stroke_color': stroke_color,
                'parent': parent_name
            })

    return containers, nodes, legend_entries

def point_in_rotated_ellipse(px, py, cx, cy, rx, ry, rotation_deg):
    """
    Check if point (px, py) is inside a rotated ellipse.

    Args:
        px, py: Point coordinates
        cx, cy: Ellipse center coordinates
        rx, ry: Ellipse semi-axes (half width, half height)
        rotation_deg: Rotation angle in degrees (counterclockwise)

    Returns:
        True if point is inside the ellipse
    """
    import math

    # Convert rotation to radians
    rotation_rad = math.radians(rotation_deg)

    # Translate point to ellipse's coordinate system
    tx = px - cx
    ty = py - cy

    # Rotate point by -rotation to align with ellipse axes
    cos_r = math.cos(-rotation_rad)
    sin_r = math.sin(-rotation_rad)
    rx_point = tx * cos_r - ty * sin_r
    ry_point = tx * sin_r + ty * cos_r

    # Check if point is inside the unrotated ellipse
    # (x/a)^2 + (y/b)^2 <= 1
    if rx == 0 or ry == 0:
        return False

    return (rx_point / rx) ** 2 + (ry_point / ry) ** 2 <= 1

def point_in_container(px, py, container_geom):
    """
    Check if point (px, py) is inside a container, accounting for rotation and shape.

    Args:
        px, py: Point coordinates
        container_geom: Container geometry dict with x, y, width, height, rotation, is_ellipse

    Returns:
        True if point is inside the container
    """
    x = container_geom['x']
    y = container_geom['y']
    width = container_geom['width']
    height = container_geom['height']
    rotation = container_geom.get('rotation', 0)
    is_ellipse = container_geom.get('is_ellipse', False)

    # Calculate center and semi-axes
    cx = x + width / 2
    cy = y + height / 2

    if is_ellipse and rotation != 0:
        # Use rotated ellipse check
        rx = width / 2
        ry = height / 2
        return point_in_rotated_ellipse(px, py, cx, cy, rx, ry, rotation)
    elif is_ellipse:
        # Unrotated ellipse
        rx = width / 2
        ry = height / 2
        dx = (px - cx) / rx
        dy = (py - cy) / ry
        return dx * dx + dy * dy <= 1
    else:
        # Rectangle (axis-aligned bounding box)
        return x <= px <= x + width and y <= py <= y + height

def read_existing_names(output_path):
    """Read existing Name column values from the Areas table if file exists."""
    try:
        with open(output_path, 'r') as f:
            content = f.read()

        # Find the Areas table
        in_areas_table = False
        area_names = {}

        for line in content.split('\n'):
            if '### Areas (Containers)' in line:
                in_areas_table = True
                continue
            if in_areas_table and line.startswith('###'):
                break
            if in_areas_table and line.startswith('|') and not line.startswith('|---'):
                # Parse table row
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 3 and parts[1] and parts[1] != 'ID' and parts[1] != '**TOTAL**':
                    area_id = parts[1]
                    area_name = parts[2] if len(parts) > 2 else ''
                    area_names[area_id] = area_name

        return area_names
    except FileNotFoundError:
        return {}

def generate_markdown():
    """Generate the markdown documentation."""
    output_path = '/Users/jakneissler/git/github/trigraph/trigraph-layer0-metametameta/doc/complete-graph-with-grounding.md'

    # Read existing names before regenerating
    existing_names = read_existing_names(output_path)

    containers, nodes, legend_entries = parse_diagram()

    # Filter out legend items from diagram section
    diagram_containers = [c for c in containers if not c['name'].startswith('legend_')]
    diagram_nodes = nodes  # All parsed nodes are diagram nodes (legend filtering already done in parse_diagram)

    # Count nodes per area based on geometric visibility
    # Parse geometry information for containers and nodes
    tree = ET.parse(DIAGRAM_PATH)
    root = tree.getroot()

    # Build container geometry map
    container_geometries = {}
    for cell in root.iter('mxCell'):
        cell_id = cell.get('id')
        value = cell.get('value', '')
        clean_val = clean_html(value)
        style = cell.get('style', '')

        # Check if this is one of our diagram containers
        for container in diagram_containers:
            if cell_id == container['name'] or clean_val == container['name']:
                # Get geometry
                geom = cell.find('mxGeometry')
                if geom is not None:
                    x = float(geom.get('x', 0))
                    y = float(geom.get('y', 0))
                    width = float(geom.get('width', 0))
                    height = float(geom.get('height', 0))

                    # Check for rotation (in degrees)
                    rotation = 0
                    rot_match = re.search(r'rotation=([^;]+)', style)
                    if rot_match:
                        rotation = float(rot_match.group(1))

                    # Check if it's an ellipse
                    is_ellipse = 'ellipse' in style

                    container_geometries[container['name']] = {
                        'x': x,
                        'y': y,
                        'width': width,
                        'height': height,
                        'rotation': rotation,
                        'is_ellipse': is_ellipse,
                        'cell_id': cell_id
                    }
                break

    # Get node positions - only for nodes that will appear in the Nodes section
    # Build set of node names that are in diagram_nodes
    diagram_node_names = {n['name'] for n in diagram_nodes}

    node_positions = {}
    for cell in root.iter('mxCell'):
        cell_id = cell.get('id')
        value = cell.get('value', '')
        clean_val = clean_html(value)

        # Skip edges
        if cell.get('source') or cell.get('target'):
            continue

        # Check if this node will appear in the Nodes section
        if clean_val in diagram_node_names:
            geom = cell.find('mxGeometry')
            if geom is not None:
                x = float(geom.get('x', 0))
                y = float(geom.get('y', 0))
                # Store center point of node
                width = float(geom.get('width', 0))
                height = float(geom.get('height', 0))
                node_positions[clean_val] = {
                    'x': x + width / 2,
                    'y': y + height / 2
                }

    # Assign nodes to visible areas
    # For each node, find which containers it's in, then determine which is topmost
    # IMPORTANT: Only assign to NAMED areas (skip unnamed background areas)
    node_counts = {}
    for node_name, pos in node_positions.items():
        # Find all containers that contain this node
        containing_containers = []
        for container_name, geom in container_geometries.items():
            # Use proper containment check (accounts for rotation and ellipse shape)
            if point_in_container(pos['x'], pos['y'], geom):
                containing_containers.append(container_name)

        # Filter to only NAMED containers (skip unnamed background areas)
        named_containers = [c for c in containing_containers if existing_names.get(c, '').strip() != '']

        # If node is in multiple named containers, assign to the topmost (last in DOM order / highest z-index)
        if named_containers:
            # Get the cell order for these containers
            container_order = {}
            cell_index = 0
            for cell in root.iter('mxCell'):
                cell_id = cell.get('id')
                for cont_name, geom in container_geometries.items():
                    if cell_id == geom['cell_id'] and cont_name in named_containers:
                        container_order[cont_name] = cell_index
                cell_index += 1

            # Assign to the container with highest index (rendered last, so on top)
            if container_order:
                topmost_container = max(container_order.keys(), key=lambda k: container_order[k])
                node_counts[topmost_container] = node_counts.get(topmost_container, 0) + 1

    # Filter out containers with no nodes and add node count
    diagram_containers_with_nodes = []
    for container in diagram_containers:
        count = node_counts.get(container['name'], 0)
        if count > 0:
            container['node_count'] = count
            diagram_containers_with_nodes.append(container)

    # Helper function to extract layer number from area name
    def extract_layer(area_name):
        """Extract layer number from area name like 'layer0-ml2-metalevels' -> 0"""
        name = existing_names.get(area_name, '')
        if not name:
            return 999  # Put unnamed areas at the end
        match = re.match(r'layer(-?\d+|N)', name)
        if match:
            layer_str = match.group(1)
            if layer_str == 'N':
                return 999  # Put layerN at the end
            return int(layer_str)
        return 999

    def extract_ml_level(area_name):
        """Extract ml level from area name like 'layer0-ml2-metalevels' -> 2, 'layer0-mlN-metaN' -> 999"""
        name = existing_names.get(area_name, '')
        if not name:
            return 0
        match = re.search(r'-ml(\d+|N)-', name)
        if match:
            ml_str = match.group(1)
            if ml_str == 'N':
                return 999  # mlN should come first
            return int(ml_str)
        return 0

    # Sort areas by layer, then by ml level (descending - higher ml first), then by fill color
    diagram_containers_with_nodes.sort(key=lambda x: (extract_layer(x['name']), -extract_ml_level(x['name']), x['fill_color'] or ''))

    # Don't sort nodes yet - we'll do it after assigning areas

    md = []
    md.append("# Complete Graph with Grounding - Diagram Documentation")
    md.append("")
    md.append("Auto-generated documentation for `complete-graph-with-grounding.drawio`")
    md.append("")

    # Diagram Section
    md.append("## Diagram")
    md.append("")

    # Overview subsection - to be populated after we parse relations
    overview_placeholder_idx = len(md)

    # Areas table
    md.append("### Areas (Containers)")
    md.append("")
    md.append("| ID | Name | Fill Color | Stroke Color | Nodes |")
    md.append("|----|------|------------|--------------|-------|")

    total_nodes = 0
    for container in diagram_containers_with_nodes:
        container_id = container['name']
        # Preserve existing name if available, otherwise leave empty
        container_name = existing_names.get(container_id, '')
        fill = color_to_markdown(container['fill_color'])
        stroke = color_to_markdown(container['stroke_color'])
        node_count = container.get('node_count', 0)
        total_nodes += node_count
        md.append(f"| {container_id} | {container_name} | {fill} | {stroke} | {node_count} |")

    # Add sum row
    md.append(f"| **TOTAL** | | | | **{total_nodes}** |")

    md.append("")

    # Assign areas to nodes
    # Create a mapping of node names to their areas
    # IMPORTANT: Only assign to NAMED areas (skip unnamed background areas)
    node_to_area = {}
    for node_name, pos in node_positions.items():
        # Find all containers that contain this node
        containing_containers = []
        for container_name, geom in container_geometries.items():
            # Use proper containment check (accounts for rotation and ellipse shape)
            if point_in_container(pos['x'], pos['y'], geom):
                containing_containers.append(container_name)

        # Filter to only NAMED containers (skip unnamed background areas)
        named_containers = [c for c in containing_containers if existing_names.get(c, '').strip() != '']

        # If node is in multiple named containers, assign to the topmost (last in DOM order)
        if named_containers:
            container_order = {}
            cell_index = 0
            for cell in root.iter('mxCell'):
                cell_id = cell.get('id')
                for cont_name, geom in container_geometries.items():
                    if cell_id == geom['cell_id'] and cont_name in named_containers:
                        container_order[cont_name] = cell_index
                cell_index += 1

            if container_order:
                topmost_container = max(container_order.keys(), key=lambda k: container_order[k])
                # Get the area name (not ID)
                area_name = existing_names.get(topmost_container, '')
                node_to_area[node_name] = area_name if area_name else topmost_container

    # Add area assignments to nodes for sorting
    for node in diagram_nodes:
        node['area'] = node_to_area.get(node['name'], '')

    # Create area order mapping based on the sorted areas table
    area_order = {}
    for idx, container in enumerate(diagram_containers_with_nodes):
        container_id = container['name']
        container_name = existing_names.get(container_id, '')
        if container_name:
            area_order[container_name] = idx

    # Sort nodes by area order (following areas table sequence), then alphabetically by name
    diagram_nodes.sort(key=lambda x: (area_order.get(x['area'], 999), x['name']))

    # Nodes table
    md.append(f"### Nodes ({len(diagram_nodes)} total)")
    md.append("")
    md.append("| # | Name | Shape | Text Style | Text Color | Fill Color | Border Color | Stroke Width | Area |")
    md.append("|---|------|-------|------------|------------|------------|--------------|--------------|------|")

    for idx, node in enumerate(diagram_nodes, 1):
        name = node['name']
        shape = node['shape']
        text_style = node['text_style']
        text_color = color_to_markdown(node['text_color'])
        fill = color_to_markdown(node['fill_color'])
        stroke = color_to_markdown(node['stroke_color'])
        stroke_width = node.get('stroke_width', '1')
        area = node['area']
        md.append(f"| {idx} | {name} | {shape} | {text_style} | {text_color} | {fill} | {stroke} | {stroke_width} | {area} |")

    md.append("")

    # Relations Section
    md.append("### Relations")
    md.append("")

    # Parse edges/relations from the diagram
    # Build a mapping of cell IDs to names (both nodes and areas)
    cell_id_to_name = {}
    cell_id_to_type = {}  # 'node' or 'area'

    # Add nodes
    for node in diagram_nodes:
        # Find the cell ID for this node
        for cell in root.iter('mxCell'):
            value = cell.get('value', '')
            clean_val = clean_html(value)
            if clean_val == node['name']:
                cell_id = cell.get('id')
                if cell_id:
                    cell_id_to_name[cell_id] = node['name']
                    cell_id_to_type[cell_id] = 'node'
                break

    # Build area_cell_ids from ALL cells that could be containers (not just visible ones)
    # This ensures we detect edges from containers that might not be in the Areas table
    area_cell_ids = set()
    for cell in root.iter('mxCell'):
        cell_id = cell.get('id')
        value = cell.get('value', '')
        clean_val = clean_html(value)

        # Skip if this is an edge
        if cell.get('source') or cell.get('target'):
            continue

        # Skip root cells
        if cell_id in ['0', '1']:
            continue

        # Check if this cell is already a known node
        if cell_id in cell_id_to_name and cell_id_to_type.get(cell_id) == 'node':
            continue

        # If this cell has geometry and is not a node, treat it as a potential area
        geom = cell.find('mxGeometry')
        if geom is not None:
            area_cell_ids.add(cell_id)
            # Always add to cell_id_to_name for edge detection
            # Try to find the name from existing_names first
            container_name = existing_names.get(cell_id, '')
            if container_name:
                cell_id_to_name[cell_id] = container_name
            else:
                # Use the cell ID as the name
                cell_id_to_name[cell_id] = cell_id
            cell_id_to_type[cell_id] = 'area'

    # Build a comprehensive mapping of colors to relation node names
    # Relation type nodes are identified by bold or bold-italic text style
    color_to_relation = {}
    for node in diagram_nodes:
        text_style = node.get('text_style', '')

        # Relation type nodes have bold or bold-italic text style
        if 'bold' in text_style:
            node_name = node['name']

            # Map all color properties from this node
            # 1. Text color
            text_color = node.get('text_color', '')
            if text_color and text_color not in ['none', 'default']:
                clean_color = normalize_color(text_color)
                if clean_color and clean_color not in color_to_relation:
                    color_to_relation[clean_color] = node_name

            # 2. Border/stroke color (often used for relation type identification)
            stroke_color = node.get('stroke_color', '')
            if stroke_color and stroke_color not in ['none', 'default']:
                clean_color = normalize_color(stroke_color)
                if clean_color and clean_color not in color_to_relation:
                    color_to_relation[clean_color] = node_name

            # 3. For black text, map to node_name with priority for bold-italic
            if text_color and normalize_color(text_color) == '#000000':
                # Only set if not already set, or if this is bold-italic (higher priority)
                if '#000000' not in color_to_relation or 'italic' in text_style:
                    color_to_relation['#000000'] = node_name

    # Add common color variations that might appear in edges
    # Map teal/cyan variants to 'ml' if it exists
    if any(n['name'] == 'ml' for n in diagram_nodes):
        for color in ['#00cccc', '#00b0b0', '#0cc', 'rgb(0,204,204)', 'rgb(0,176,176)']:
            clean_color = normalize_color(color)
            if clean_color not in color_to_relation:
                color_to_relation[clean_color] = 'ml'

    # Parse edges
    area_to_node_relations = []
    node_to_node_relations = []

    for cell in root.iter('mxCell'):
        source_id = cell.get('source')
        target_id = cell.get('target')

        if source_id and target_id:
            # This is an edge
            source_name = cell_id_to_name.get(source_id, source_id)
            target_name = cell_id_to_name.get(target_id, target_id)

            # Determine if source is an area and target is a node
            source_is_area = source_id in area_cell_ids
            target_is_node = target_id in cell_id_to_name and cell_id_to_type.get(target_id) == 'node'

            # Get edge colors (check multiple properties)
            style = cell.get('style', '')
            value = cell.get('value', '')

            # Collect all possible colors from the edge
            edge_colors = []

            # 1. Font/text color from style
            font_color = extract_style_property(style, 'fontColor')
            if font_color:
                edge_colors.append(font_color)

            # 2. Text color from HTML in value
            if value:
                color_match = re.search(r'color:\s*([^;"]+)', value)
                if color_match:
                    edge_colors.append(color_match.group(1).strip())

            # 3. Stroke color (often the main edge color)
            stroke_color = extract_style_property(style, 'strokeColor')
            if stroke_color:
                edge_colors.append(stroke_color)

            # 4. Fill color (sometimes used)
            fill_color = extract_style_property(style, 'fillColor')
            if fill_color:
                edge_colors.append(fill_color)

            # Try to find relation type by matching any of the edge colors
            relation_type = ''
            matched_color = None
            for color in edge_colors:
                clean_color = normalize_color(color)
                if clean_color in color_to_relation:
                    relation_type = color_to_relation[clean_color]
                    matched_color = color
                    break

            # Use the first color for display (prefer font color, then stroke color)
            display_color = edge_colors[0] if edge_colors else 'none'

            # Skip if source or target not found as named entities
            # Check if they're in the mapping, not if name == id (since some nodes have IDs that match their names)
            if source_id not in cell_id_to_name or target_id not in cell_id_to_name:
                continue

            relation_data = {
                'source': source_name,
                'target': target_name,
                'color': display_color,
                'type': relation_type
            }

            # Categorize by source type
            if source_is_area and target_is_node:
                area_to_node_relations.append(relation_data)
            elif not source_is_area and target_is_node:
                node_to_node_relations.append(relation_data)

    # Table 1: Area to Node relations
    md.append("#### Relations from Area to Node")
    md.append("")
    md.append("| Source Area | Target Node | Arrow Color | Relation Type |")
    md.append("|-------------|-------------|-------------|---------------|")

    # Sort by relation type first, then by source and target
    for rel in sorted(area_to_node_relations, key=lambda x: (x['type'] or 'zzz', x['source'], x['target'])):
        color_display = color_to_markdown(rel['color'])
        md.append(f"| {rel['source']} | {rel['target']} | {color_display} | {rel['type']} |")

    if not area_to_node_relations:
        md.append("| | | | *No area-to-node relations found* |")

    md.append("")

    # Table 2: Node to Node relations
    md.append("#### Relations from Node to Node")
    md.append("")
    md.append("| Source Node | Target Node | Arrow Color | Relation Type |")
    md.append("|-------------|-------------|-------------|---------------|")

    # Sort by relation type first, then by source and target
    for rel in sorted(node_to_node_relations, key=lambda x: (x['type'] or 'zzz', x['source'], x['target'])):
        color_display = color_to_markdown(rel['color'])
        md.append(f"| {rel['source']} | {rel['target']} | {color_display} | {rel['type']} |")

    if not node_to_node_relations:
        md.append("| | | | *No node-to-node relations found* |")

    md.append("")

    # Generate overview section - insert at the placeholder
    overview_lines = []
    overview_lines.append("### Overview")
    overview_lines.append("")

    # 1. Area counts by color
    overview_lines.append("#### Area Counts by Color")
    overview_lines.append("")

    # Group areas by fill color
    areas_by_color = defaultdict(list)
    for container in diagram_containers_with_nodes:
        fill_color = container['fill_color'] or 'none'
        container_name = existing_names.get(container['name'], container['name'])
        areas_by_color[fill_color].append(container_name)

    overview_lines.append("| Fill Color | Count | Areas |")
    overview_lines.append("|------------|-------|-------|")

    # Sort by count descending
    for fill_color in sorted(areas_by_color.keys(), key=lambda c: len(areas_by_color[c]), reverse=True):
        count = len(areas_by_color[fill_color])
        areas_list = ', '.join(areas_by_color[fill_color])
        color_display = color_to_markdown(fill_color)
        overview_lines.append(f"| {color_display} | {count} | {areas_list} |")

    overview_lines.append("")

    # 2. Node counts by area
    overview_lines.append("#### Node Counts by Area")
    overview_lines.append("")
    overview_lines.append("| Area | Node Count |")
    overview_lines.append("|------|------------|")

    # Sort by node count descending
    for container in sorted(diagram_containers_with_nodes, key=lambda c: c.get('node_count', 0), reverse=True):
        container_name = existing_names.get(container['name'], container['name'])
        node_count = container.get('node_count', 0)
        overview_lines.append(f"| {container_name} | {node_count} |")

    overview_lines.append(f"| **TOTAL** | **{total_nodes}** |")
    overview_lines.append("")

    # 3. Relation counts by type
    overview_lines.append("#### Relation Counts by Type")
    overview_lines.append("")

    # Count relations by type
    relation_type_counts = defaultdict(int)
    for rel in area_to_node_relations + node_to_node_relations:
        rel_type = rel['type'] if rel['type'] else '(untyped)'
        relation_type_counts[rel_type] += 1

    overview_lines.append("| Relation Type | Count |")
    overview_lines.append("|---------------|-------|")

    # Sort by count descending
    for rel_type in sorted(relation_type_counts.keys(), key=lambda t: relation_type_counts[t], reverse=True):
        count = relation_type_counts[rel_type]
        overview_lines.append(f"| {rel_type} | {count} |")

    total_relations = sum(relation_type_counts.values())
    overview_lines.append(f"| **TOTAL** | **{total_relations}** |")
    overview_lines.append("")

    # Insert overview at the placeholder position
    for i, line in enumerate(overview_lines):
        md.insert(overview_placeholder_idx + i, line)

    # Legend Section - Parse the 7 boxes from the diagram
    md.append("## Legend")
    md.append("")

    legend_boxes = parse_legend_structure()

    # Build a map of node names to their text colors (for arrow color display)
    node_text_colors = {}
    for node in diagram_nodes:
        if node.get('text_color'):
            node_text_colors[node['name']] = node['text_color']

    # Helper function to parse entries and create tables
    def format_legend_entries(entries, visual_nodes=None):
        """Format legend entries into appropriate table structure with visual properties.

        Args:
            entries: List of text entries
            visual_nodes: Dict mapping abbreviation to visual properties {shape, fill_color, stroke_color}
        """
        if visual_nodes is None:
            visual_nodes = {}
        # Detect entry types
        abbrev_entries = []  # format: "abbr = description"
        arrow_entries = []   # format: "→   abbr = description"
        desc_entries = []    # format: "Description text (ml=N)"
        plain_entries = []   # format: "plain text without ="

        for entry in entries:
            if entry.startswith('→'):
                # Arrow entry - relation property
                arrow_entries.append(entry)
            elif '=' in entry:
                # Check if "=" is only inside parentheses (description) or outside (abbreviation)
                # Remove parenthesized content and check if "=" still exists
                without_parens = re.sub(r'\([^)]*\)', '', entry)
                if '=' in without_parens:
                    # Abbreviation entry (has = outside parentheses)
                    abbrev_entries.append(entry)
                else:
                    # Description entry (= only appears inside parentheses)
                    desc_entries.append(entry)
            else:
                # Plain text entry (no '=')
                plain_entries.append(entry)

        lines = []

        # Add description entries first (if any)
        if desc_entries:
            for entry in desc_entries:
                # Parse entries like "Types (ml=2)" or "Grounding Nodes (ml=1)"
                # Extract ML if present
                if '(ml=' in entry or '(all ml=' in entry:
                    match = re.search(r'(.*?)\s*\((.*?ml\s*=\s*(\d+|N).*?)\)', entry)
                    if match:
                        lines.append(f"**{match.group(1).strip()}** ({match.group(2)})")
                    else:
                        lines.append(f"**{entry}**")
                else:
                    lines.append(f"**{entry}**")
            lines.append("")

        # Add abbreviation entries (if any)
        if abbrev_entries:
            # Check if we have any visual properties
            has_visuals = any(abbr.split('=')[0].strip() in visual_nodes for abbr in abbrev_entries if '=' in abbr)

            # Create table for abbreviations
            if has_visuals:
                lines.append("| Abbreviation | Description | ML | Shape | Fill Color | Border Color |")
                lines.append("|--------------|-------------|-----|-------|------------|--------------|")
            else:
                lines.append("| Abbreviation | Description | ML |")
                lines.append("|--------------|-------------|-----|")

            for entry in abbrev_entries:
                # Parse formats like:
                # "gt = groundingType"
                # "mlt = metaLevelType (ml=2)"
                # "ml = 1 (classes and relations)"
                parts = entry.split('=', 1)
                if len(parts) == 2:
                    abbr = parts[0].strip()
                    rest = parts[1].strip()

                    # Extract ML number if present in parentheses
                    ml = ''
                    desc = rest

                    # Match (ml=N) pattern
                    match = re.search(r'\(ml\s*=\s*(\d+|N)\)', rest)
                    if match:
                        ml = match.group(1)
                        # Remove the (ml=N) part from description
                        desc = re.sub(r'\s*\(ml\s*=\s*(\d+|N)\)', '', rest).strip()

                    # For entries like "ml = 1 (classes and relations)", the ML is the first part
                    if abbr == 'ml':
                        # Split the description
                        desc_parts = desc.split('(', 1)
                        if len(desc_parts) == 2:
                            ml = desc_parts[0].strip()
                            desc = '(' + desc_parts[1]

                    # Add visual properties if available
                    if has_visuals:
                        visual = visual_nodes.get(abbr, {})
                        shape = visual.get('shape', '')
                        fill_color = visual.get('fill_color', '')
                        stroke_color = visual.get('stroke_color', '')

                        # Format colors
                        fill_display = color_to_markdown(fill_color) if fill_color else ''
                        stroke_display = color_to_markdown(stroke_color) if stroke_color else ''

                        lines.append(f"| {abbr} | {desc} | {ml} | {shape} | {fill_display} | {stroke_display} |")
                    else:
                        lines.append(f"| {abbr} | {desc} | {ml} |")

            lines.append("")

        # Add arrow entries (if any)
        if arrow_entries:
            # Check if we have text colors from diagram nodes
            has_arrow_colors = any(entry.replace('→', '').strip().split('=')[0].strip() in node_text_colors for entry in arrow_entries if '=' in entry)

            lines.append("**Relation Properties:**")
            lines.append("")

            if has_arrow_colors:
                lines.append("| Abbreviation | Description | Arrow Color |")
                lines.append("|--------------|-------------|-------------|")
            else:
                lines.append("| Abbreviation | Description |")
                lines.append("|--------------|-------------|")

            for entry in arrow_entries:
                # Remove arrow and parse
                entry_clean = entry.replace('→', '').strip()
                parts = entry_clean.split('=', 1)
                if len(parts) == 2:
                    abbr = parts[0].strip()
                    desc = parts[1].strip()

                    # Add arrow color from diagram node text color
                    if has_arrow_colors:
                        # Use the text color from the actual diagram node
                        arrow_color = node_text_colors.get(abbr, '')
                        arrow_display = color_to_markdown(arrow_color) if arrow_color else ''
                        lines.append(f"| {abbr} | {desc} | {arrow_display} |")
                    else:
                        lines.append(f"| {abbr} | {desc} |")

            lines.append("")

        # Add plain text entries (if any)
        if plain_entries:
            for entry in plain_entries:
                lines.append(f"**{entry}**")
                lines.append("")

        return lines

    # Helper function to split entries into sections
    def split_into_sections(entries):
        """Split entries into sections based on section headers (text without '=')."""
        sections = []
        current_section = {'title': None, 'entries': []}

        for entry in entries:
            # Check if this is a section header (no '=' or only '=' inside parens)
            without_parens = re.sub(r'\([^)]*\)', '', entry)

            # Section headers are text without '=' that look like proper headers
            # Not short entries like "ml0, ml1, ml2, ml3, mlN" or "55 grounding nodes"
            is_section_header = False
            if '=' not in without_parens and entry.strip():
                # Check if this looks like a section header
                # Section headers typically:
                # - Start with capital letter or contain "("
                # - Are not just a list of items (no commas unless in parens)
                # - Don't start with numbers like "55 grounding nodes"
                entry_no_parens = re.sub(r'\([^)]*\)', '', entry).strip()
                if (entry[0].isupper() or '(' in entry) and \
                   (',' not in entry_no_parens or entry_no_parens.count(',') <= 1) and \
                   not entry[0].isdigit():
                    is_section_header = True

            if is_section_header:
                # This is a section header
                if current_section['entries'] or current_section['title']:
                    sections.append(current_section)
                current_section = {'title': entry, 'entries': []}
            else:
                # This is a regular entry
                if entry.strip():
                    current_section['entries'].append(entry)

        # Add the last section
        if current_section['entries'] or current_section['title']:
            sections.append(current_section)

        return sections

    # Generate subsections for each box with custom formatting
    for i, box in enumerate(legend_boxes, 1):
        box_title = box['title']

        # Special handling for different boxes
        if box_title == "Meta - Levels":
            md.append(f"### {box_title}")
            md.append("")
            formatted = format_legend_entries(box['entries'], box.get('visual_nodes', {}))
            md.extend(formatted)

        elif box_title == "Layers - Packages":
            md.append(f"### Layers")
            md.append("")
            md.append("| Layer | Description |")
            md.append("|-------|-------------|")
            for entry in box['entries']:
                md.append(f"| {entry} | |")
            md.append("")

        elif box_title == "Visibility":
            md.append(f"### {box_title}")
            md.append("")
            md.append("| Visibility | Description |")
            md.append("|------------|-------------|")
            for entry in box['entries']:
                # Split "public (visible to all following layers)" into parts
                match = re.match(r'([^\(]+)\s*\(([^)]+)\)', entry)
                if match:
                    vis = match.group(1).strip()
                    desc = match.group(2).strip()
                    md.append(f"| {vis} | {desc} |")
                else:
                    md.append(f"| {entry} | |")
            md.append("")

        elif box_title == "Layer 0 - MetaMetaMeta":
            md.append(f"### {box_title}")
            md.append("")

            # Split into 6 subsections
            sections = split_into_sections(box['entries'])
            visual_nodes = box.get('visual_nodes', {})
            for section in sections:
                if section['title']:
                    md.append(f"#### {section['title']}")
                    md.append("")
                if section['entries']:
                    formatted = format_legend_entries(section['entries'], visual_nodes)
                    md.extend(formatted)

        elif box_title == "Layer 2 - Grounding":
            md.append(f"### {box_title}")
            md.append("")

            # Split into 4 subsections
            sections = split_into_sections(box['entries'])
            visual_nodes = box.get('visual_nodes', {})
            for section in sections:
                if section['title']:
                    md.append(f"#### {section['title']}")
                    md.append("")
                if section['entries']:
                    formatted = format_legend_entries(section['entries'], visual_nodes)
                    md.extend(formatted)

        elif "Class-Inheritance" in box_title or "Class Inheritance" in box_title:
            md.append(f"### Layer 1 - Class Inheritance")
            md.append("")

            # Split into subsections (Relations and Relation Signatures)
            sections = split_into_sections(box['entries'])
            visual_nodes = box.get('visual_nodes', {})
            for section in sections:
                if section['title']:
                    md.append(f"#### {section['title']}")
                    md.append("")
                if section['entries']:
                    formatted = format_legend_entries(section['entries'], visual_nodes)
                    md.extend(formatted)

        elif "Persistence-Structure" in box_title or "Persistence Structure" in box_title:
            md.append(f"### Layer 1 - Persistence Structure")
            md.append("")

            # Split into 3 subsections (Types, Relations, Relation Signatures)
            sections = split_into_sections(box['entries'])
            visual_nodes = box.get('visual_nodes', {})
            for section in sections:
                if section['title']:
                    md.append(f"#### {section['title']}")
                    md.append("")
                if section['entries']:
                    formatted = format_legend_entries(section['entries'], visual_nodes)
                    md.extend(formatted)
        else:
            # Default formatting
            md.append(f"### {box_title}")
            md.append("")
            formatted = format_legend_entries(box['entries'], box.get('visual_nodes', {}))
            md.extend(formatted)

    md.append("")
    md.append("---")
    md.append("")
    md.append("## Diagram Consistency Constraints")
    md.append("")
    md.append("The diagram follows these structural and semantic constraints:")
    md.append("")

    md.append("### Naming Conventions")
    md.append("")
    md.append("- **Relation signatures**: Follow `source2target` pattern (e.g., `c2c`, `pa2sh`, `gt2gt`)")
    md.append("- **Node abbreviations**: 2-4 letter systematic codes (e.g., `mt`, `mr`, `mrs`, `rp`)")
    md.append("- **Meta levels**: Numeric suffix pattern (`ml0`, `ml1`, `ml2`, `ml3`, `mlN`)")
    md.append("- **Relation properties**: 3-letter codes (`imp`, `man`, `tra`, `uni`)")
    md.append("")

    md.append("### Shape-to-Concept Mappings")
    md.append("")
    md.append("- **Ellipses**: MetaType nodes, relation signatures, meta-level instances, grounding nodes (ml=1)")
    md.append("- **Hexagons**: MetaRelation types, MetaRelationSignature types, RelationProperty types, special relations")
    md.append("- **Rectangles**: Class types, concrete relation instances, persistence types, relation properties (ml=2)")
    md.append("")

    md.append("### Text Style Semantics")
    md.append("")
    md.append("- **Bold-Italic**: Meta-meta level constructs (ml=3 or ml=N types and signatures)")
    md.append("- **Bold**: Relation type nodes, relation instances, type-defining constructs")
    md.append("- **Normal**: Instances, concrete types, non-meta constructs, grounding nodes (ml=1)")
    md.append("")

    md.append("### Color Coding Rules")
    md.append("")
    md.append("**Text colors encode relation types:**")
    md.append("")
    md.append("| Color | Purpose | Example |")
    md.append("|-------|---------|---------|")
    md.append("| Black (#000000) | Type relations, meta-types | `type`, `mnt`, `mlt` |")
    md.append("| Teal (#00CCCC) | Meta-level relations | `ml` |")
    md.append("| Green (#00AA00) | Next-meta-level | `nml` |")
    md.append("| Yellow (#FFFF00) | Relation properties | `rpr` |")
    md.append("| Orange (#FF8800) | Signatures | `sig` |")
    md.append("| Blue (#0000FF) | Source type | `st` |")
    md.append("| Purple (#AA00FF) | Target type | `tt` |")
    md.append("| Magenta (#FF00FF) | Inverse transitive hull | `ith` |")
    md.append("| Red (#FF0000) | Type assignment | `type` |")
    md.append("| Gray (#97A0AB) | Grounding references | `grr` |")
    md.append("")
    md.append("**Fill colors encode metalevels:**")
    md.append("")
    md.append("| Fill Color | Metalevel | Usage |")
    md.append("|------------|-----------|-------|")
    md.append("| Light blue (#E6F0FF) | ml=3 | Meta-meta-meta level nodes |")
    md.append("| Light green (#E6FFE6) | ml=2 | Meta-level instances |")
    md.append("| Light purple (#e1d5e7) | ml=2 | Class/relation types |")
    md.append("| Light yellow (#fff2cc) | ml=2 | Relation properties |")
    md.append("| Light teal (#b0e3e6) | ml=2 | Concrete relations |")
    md.append("| Light peach (#ffcc99) | ml=2 | Relation signatures |")
    md.append("| Light gray (#eeeeee) | ml=1 | Grounding nodes |")
    md.append("")

    md.append("### Metalevel Organization")
    md.append("")
    md.append("- **ml=N**: Collapsed representation of all higher meta levels (1 node: `mnt`)")
    md.append("- **ml=3**: Meta-meta-meta level defining meta-types (20 nodes in layer0-ml3)")
    md.append("- **ml=2**: Meta-meta level with types and relations for modeling (across 11 areas)")
    md.append("- **ml=1**: Instance level with grounding nodes (57 nodes in layer2-ml1)")
    md.append("- **Containment rule**: Nodes at ml=X are in areas with `-mlX-` in their name")
    md.append("")

    md.append("### Area Naming and Organization")
    md.append("")
    md.append("- **Pattern**: `layer{N}-ml{M}-{description}`")
    md.append("- **Layer 0**: MetaMetaMeta foundation (4 areas)")
    md.append("- **Layer 1**: ClassInheritance & PersistenceStructure (5 areas)")
    md.append("- **Layer 2**: Grounding instances (2 areas)")
    md.append("- **Visibility**: Only areas with fill color OR red border (#ff0000) are shown")
    md.append("")

    md.append("### Relation Type Constraints")
    md.append("")
    md.append("**Area-to-Node relations (13 total):**")
    md.append("")
    md.append("- `ml` relations: Areas → their metalevel nodes (8 relations, teal arrows)")
    md.append("- `type` relations: Areas → type nodes (5 relations, red arrows)")
    md.append("")
    md.append("**Node-to-Node relations (218 total):**")
    md.append("")
    md.append("| Relation | Count | Purpose | Arrow Color |")
    md.append("|----------|-------|---------|-------------|")
    md.append("| gdr | 69 | Grounding detail (taxonomy) | Black |")
    md.append("| grr | 39 | Grounding reference | Gray |")
    md.append("| type | 30 | Type assignment | Red |")
    md.append("| sig | 28 | Signature definition | Orange |")
    md.append("| tt | 22 | Target type specification | Purple |")
    md.append("| st | 19 | Source type specification | Blue |")
    md.append("| ml | 9 | Metalevel connection | Teal |")
    md.append("| rpr | 9 | Property assignment | Yellow |")
    md.append("| nml | 5 | Next metalevel (hierarchy) | Green |")
    md.append("| ith | 1 | Inverse transitive hull | Magenta |")
    md.append("")
    md.append("**Signature semantic rule**: Each relation signature has exactly 3 defining relations:")
    md.append("")
    md.append("1. `sig`: Points to signature definition")
    md.append("2. `st`: Points to source type")
    md.append("3. `tt`: Points to target type")
    md.append("")

    md.append("### Stroke Width Semantics")
    md.append("")
    md.append("- **Width 1** (default): Standard nodes, relations, instances (117 nodes)")
    md.append("- **Width 2**: Special emphasis (`mnt`)")
    md.append("- **Width 3**: Type-defining nodes at ml=2 (`class`)")
    md.append("- **Width 4**: Fundamental type-defining constructs (`mlt`, `mr`, `mrs`, `rp`, `gt`)")
    md.append("")

    md.append("### Validation Rules")
    md.append("")
    md.append("1. All abbreviations must be defined in legend")
    md.append("2. Node counts in diagram should match source definitions")
    md.append("3. Each relation must have a valid type from the defined set")
    md.append("4. Nodes must be contained in appropriately labeled areas")
    md.append("5. Metalevel containment must be consistent with area naming")
    md.append("6. Grounding nodes (ml=1) must use ellipse shape and normal text style")
    md.append("")

    md.append("---")
    md.append("")
    md.append("## How to Regenerate This File")
    md.append("")
    md.append("This file is auto-generated from `complete-graph-with-grounding.drawio`. To update it after modifying the diagram:")
    md.append("")
    md.append("```bash")
    md.append("python3 generate_diagram_doc.py")
    md.append("```")
    md.append("")
    md.append("### Generation Rules")
    md.append("")
    md.append("1. **Diagram vs Legend**: Everything inside the biggest yellowish circle (#FEFFEF) is considered diagram content; everything outside is legend")
    md.append("2. **Container/Node detection**:")
    md.append("   - Shapes with fill color AND text → Nodes")
    md.append("   - Shapes with fill color and NO text → Containers/Areas")
    md.append("   - Shapes with no fill color → Ignored")
    md.append("   - **Exception**: Shapes with red dashed boundary (no fill required) → Containers (even if they have text)")
    md.append("3. **Area filtering**: Only areas with a fill color OR red border color (#ff0000) are included")
    md.append("4. **Area node counts**: Only nodes from the Nodes section are counted; nodes are counted based on geometric position within visible areas")
    md.append("5. **Node assignment to areas**: Nodes are only assigned to NAMED areas (areas with a manual name in the Name column); unnamed areas are ignored")
    md.append("6. **Overlapping areas**: When named areas overlap, nodes are assigned to the topmost (last rendered) named area")
    md.append("7. **Empty areas**: Areas with zero nodes are not shown")
    md.append("8. **Area table columns**: The 'ID' column contains technical identifiers; the 'Name' column is preserved from previous versions if it exists (manual annotations are not overwritten)")
    md.append("9. **Colors**: All colors are displayed with their hex code on a colored background for easy visual reference")
    md.append("")
    md.append("---")
    md.append("")
    md.append("*Generated by `generate_diagram_doc.py`*")

    return '\n'.join(md)

if __name__ == '__main__':
    markdown = generate_markdown()

    output_path = '/Users/jakneissler/git/github/trigraph/trigraph-layer0-metametameta/doc/complete-graph-with-grounding.md'
    with open(output_path, 'w') as f:
        f.write(markdown)

    print(f"Documentation generated: {output_path}")
    print()
    print(markdown)
