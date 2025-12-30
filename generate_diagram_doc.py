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
    """Parse the legend structure from the diagram (7 boxes with their entries)."""
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
        geom = cell.find('mxGeometry')

        x, y = 0, 0
        if geom is not None:
            x = float(geom.get('x', 0))
            y = float(geom.get('y', 0))

        if cell_id:
            cell_map[cell_id] = {
                'element': cell,
                'parent_id': parent_id,
                'value': value,
                'x': x,
                'y': y,
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

    # For each box, extract all text entries
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

        # Get text entries with their Y positions (for sorting)
        entries = []
        for desc_id, desc_info in all_descendants:
            value = desc_info['value']
            clean_val = clean_html(value)
            # Filter out corrupted entries with URL-encoded content
            if clean_val and '%3C' not in clean_val:
                entries.append({
                    'text': clean_val,
                    'y': desc_info['y']
                })

        # Sort by Y position
        entries.sort(key=lambda e: e['y'])
        box['entries'] = [e['text'] for e in entries]

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

    # Legend Section - Parse the 7 boxes from the diagram
    md.append("## Legend")
    md.append("")

    legend_boxes = parse_legend_structure()

    # Helper function to parse entries and create tables
    def format_legend_entries(entries):
        """Format legend entries into appropriate table structure."""
        # Detect entry types
        abbrev_entries = []  # format: "abbr = description"
        arrow_entries = []   # format: "→   abbr = description"
        desc_entries = []    # format: "Description text (ml=N)"

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
                # Description entry
                desc_entries.append(entry)

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
            # Create table for abbreviations
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

                    lines.append(f"| {abbr} | {desc} | {ml} |")

            lines.append("")

        # Add arrow entries (if any)
        if arrow_entries:
            lines.append("**Relation Properties:**")
            lines.append("")
            lines.append("| Abbreviation | Description |")
            lines.append("|--------------|-------------|")

            for entry in arrow_entries:
                # Remove arrow and parse
                entry_clean = entry.replace('→', '').strip()
                parts = entry_clean.split('=', 1)
                if len(parts) == 2:
                    abbr = parts[0].strip()
                    desc = parts[1].strip()
                    lines.append(f"| {abbr} | {desc} |")

            lines.append("")

        return lines

    # Generate subsections for each box
    for i, box in enumerate(legend_boxes, 1):
        md.append(f"### {box['title']}")
        md.append("")

        # Format the entries for this box
        formatted = format_legend_entries(box['entries'])
        md.extend(formatted)

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
