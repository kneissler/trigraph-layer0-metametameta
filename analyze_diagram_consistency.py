#!/usr/bin/env python3
"""
Analyze complete-graph-with-grounding.drawio for consistency issues.
Checks all nodes for connectivity problems: orphaned, dangling, isolated.
"""

import xml.etree.ElementTree as ET
import sys
from collections import defaultdict

def parse_drawio(filepath):
    """Parse DrawIO XML and extract nodes and edges."""
    tree = ET.parse(filepath)
    root = tree.getroot()

    nodes = {}
    edges = []

    # Find all mxCell elements
    for cell in root.iter('mxCell'):
        cell_id = cell.get('id')
        if not cell_id:
            continue

        # Check if this is an edge (has source and target)
        source = cell.get('source')
        target = cell.get('target')

        if source and target:
            # This is an edge
            edges.append({
                'id': cell_id,
                'source': source,
                'target': target,
                'style': cell.get('style', '')
            })
        else:
            # This is a node
            value = cell.get('value', '')
            style = cell.get('style', '')

            # Extract ml attribute from value (e.g., value="text" ml="1")
            ml_attr = cell.get('ml')

            # Parse ml from style or attributes
            ml = None
            if 'ml=' in str(cell.attrib):
                for attr_name, attr_value in cell.attrib.items():
                    if attr_name == 'ml':
                        ml = attr_value

            nodes[cell_id] = {
                'id': cell_id,
                'label': value,
                'style': style,
                'ml': ml,
                'shape': 'ellipse' if 'ellipse' in style else
                        'hexagon' if 'hexagon' in style else
                        'rectangle' if 'whiteSpace=wrap' in style else 'unknown',
                'fill': extract_fill_color(style),
                'incoming': [],
                'outgoing': []
            }

    # Build incoming/outgoing edge lists
    for edge in edges:
        source_id = edge['source']
        target_id = edge['target']

        if source_id in nodes:
            nodes[source_id]['outgoing'].append(edge)

        if target_id in nodes:
            nodes[target_id]['incoming'].append(edge)

    return nodes, edges

def extract_fill_color(style):
    """Extract fill color from style string."""
    if 'fillColor=' in style:
        parts = style.split('fillColor=')
        if len(parts) > 1:
            color = parts[1].split(';')[0]
            return color
    return None

def classify_node(node):
    """Classify node by metalevel and type."""
    fill = node['fill']
    label = node['label']
    ml = node['ml']

    # Check for grounding nodes (fill=#eeeeee)
    if fill == '#eeeeee':
        return 'grounding', 1

    # Check for metalevel markers
    if label and any(x in label.lower() for x in ['meta-level', 'metalevel']):
        return 'metalevel-marker', None

    # Try to determine from label patterns
    # Layer 0 nodes (ml=3): mnt, mt, mlt, mr, mrs, type_rel, ml_rel, etc.
    layer0_patterns = ['mnt', 'metaNType', 'metaType', 'metaLevelType',
                       'metaRelation', 'metaRelationSignature', 'relationProperty',
                       'type_rel', 'ml_rel', 'sig_rel', 'st_rel', 'tt_rel',
                       'rpr', 'nml_rel', 'ml0', 'ml1', 'ml2', 'ml3', 'mlN',
                       'sig1', 'sig2', 'sig3', 'sig4', 'sig5', 'sig6', 'sig7']

    # Layer 1 nodes (ml=2): class, rel, rs, inh, supc, ith, pac, lay, sh
    layer1_patterns = ['class', 'relation', 'relationSignature',
                       'inh', 'supc', 'ith', 'pac', 'lay', 'sh', 'vn', 'dn']

    label_lower = label.lower() if label else ''

    for pattern in layer0_patterns:
        if pattern.lower() in label_lower:
            return 'layer0', 3

    for pattern in layer1_patterns:
        if pattern.lower() in label_lower:
            return 'layer1', 2

    # If no classification found but has label
    if label and label.strip():
        return 'unknown', None

    return 'container', None

def find_issues(nodes, edges):
    """Find consistency issues in the graph."""
    issues = {
        'orphaned': [],
        'dangling_edges': [],
        'isolated': [],
        'root_nodes': []
    }

    # Track all node IDs referenced in edges
    referenced_nodes = set()
    for edge in edges:
        referenced_nodes.add(edge['source'])
        referenced_nodes.add(edge['target'])

    # Check for dangling edges
    for edge in edges:
        if edge['source'] not in nodes:
            issues['dangling_edges'].append({
                'edge_id': edge['id'],
                'problem': f"Source node '{edge['source']}' does not exist",
                'target': edge['target']
            })
        if edge['target'] not in nodes:
            issues['dangling_edges'].append({
                'edge_id': edge['id'],
                'problem': f"Target node '{edge['target']}' does not exist",
                'source': edge['source']
            })

    # Check each node
    for node_id, node in nodes.items():
        label = node['label'].strip() if node['label'] else ''

        # Skip unlabeled nodes (containers, etc.)
        if not label or label == '':
            continue

        incoming_count = len(node['incoming'])
        outgoing_count = len(node['outgoing'])

        node_type, ml = classify_node(node)

        # Check for isolated nodes
        if incoming_count == 0 and outgoing_count == 0:
            issues['isolated'].append({
                'id': node_id,
                'label': label,
                'type': node_type,
                'ml': ml
            })
            continue

        # Check for orphaned nodes (0 incoming but has outgoing)
        # Exclude expected root nodes
        root_patterns = ['grounding root', 'meta^N type']
        is_root = any(pattern in label.lower() for pattern in root_patterns)

        if incoming_count == 0 and outgoing_count > 0:
            if is_root:
                issues['root_nodes'].append({
                    'id': node_id,
                    'label': label,
                    'type': node_type,
                    'ml': ml,
                    'outgoing': outgoing_count
                })
            else:
                issues['orphaned'].append({
                    'id': node_id,
                    'label': label,
                    'type': node_type,
                    'ml': ml,
                    'outgoing': outgoing_count
                })

    return issues

def print_report(nodes, edges, issues):
    """Print comprehensive consistency report."""
    print("="*80)
    print("COMPLETE DIAGRAM CONSISTENCY ANALYSIS")
    print("="*80)
    print()

    # Summary statistics
    labeled_nodes = [n for n in nodes.values() if n['label'].strip()]
    grounding_nodes = [n for n in labeled_nodes if classify_node(n)[0] == 'grounding']
    layer0_nodes = [n for n in labeled_nodes if classify_node(n)[0] == 'layer0']
    layer1_nodes = [n for n in labeled_nodes if classify_node(n)[0] == 'layer1']

    print(f"Total nodes in diagram: {len(nodes)}")
    print(f"Labeled nodes: {len(labeled_nodes)}")
    print(f"  - Layer 0 (ml=3): {len(layer0_nodes)}")
    print(f"  - Layer 1 (ml=2): {len(layer1_nodes)}")
    print(f"  - Grounding (ml=1): {len(grounding_nodes)}")
    print(f"Total edges: {len(edges)}")
    print()

    # Issues summary
    print("="*80)
    print("ISSUES SUMMARY")
    print("="*80)
    print(f"Orphaned nodes (0 in, >0 out): {len(issues['orphaned'])}")
    print(f"Isolated nodes (0 in, 0 out): {len(issues['isolated'])}")
    print(f"Dangling edges (invalid refs): {len(issues['dangling_edges'])}")
    print(f"Root nodes (expected 0 in): {len(issues['root_nodes'])}")
    print()

    # Detailed reports
    if issues['orphaned']:
        print("="*80)
        print("ORPHANED NODES (0 incoming edges, but have outgoing)")
        print("="*80)
        for node in issues['orphaned']:
            print(f"\nNode: {node['label']}")
            print(f"  ID: {node['id']}")
            print(f"  Type: {node['type']}, ML={node['ml']}")
            print(f"  Outgoing edges: {node['outgoing']}")

    if issues['isolated']:
        print("\n" + "="*80)
        print("ISOLATED NODES (0 incoming, 0 outgoing)")
        print("="*80)
        for node in issues['isolated']:
            print(f"\nNode: {node['label']}")
            print(f"  ID: {node['id']}")
            print(f"  Type: {node['type']}, ML={node['ml']}")

    if issues['dangling_edges']:
        print("\n" + "="*80)
        print("DANGLING EDGES (pointing to non-existent nodes)")
        print("="*80)
        for edge in issues['dangling_edges']:
            print(f"\nEdge: {edge['edge_id']}")
            print(f"  Problem: {edge['problem']}")

    if issues['root_nodes']:
        print("\n" + "="*80)
        print("ROOT NODES (expected to have 0 incoming edges)")
        print("="*80)
        for node in issues['root_nodes']:
            print(f"\nNode: {node['label']}")
            print(f"  ID: {node['id']}")
            print(f"  Type: {node['type']}, ML={node['ml']}")
            print(f"  Outgoing edges: {node['outgoing']}")

    # Final verdict
    print("\n" + "="*80)
    print("OVERALL ASSESSMENT")
    print("="*80)
    total_issues = len(issues['orphaned']) + len(issues['isolated']) + len(issues['dangling_edges'])
    if total_issues == 0:
        print("✓ NO CONSISTENCY ISSUES FOUND")
        print("✓ All labeled nodes are properly connected")
        print("✓ No dangling edge references")
        print("✓ Graph structure is complete and valid")
    else:
        print(f"✗ FOUND {total_issues} CONSISTENCY ISSUES")
        print(f"  - {len(issues['orphaned'])} orphaned nodes need incoming edges")
        print(f"  - {len(issues['isolated'])} isolated nodes need connections")
        print(f"  - {len(issues['dangling_edges'])} dangling edges need fixing")
    print()

if __name__ == '__main__':
    filepath = '/Users/jakneissler/git/github/trigraph/trigraph-layer0-metametameta/doc/complete-graph-with-grounding.drawio'

    print("Parsing DrawIO file...")
    nodes, edges = parse_drawio(filepath)

    print("Analyzing consistency...")
    issues = find_issues(nodes, edges)

    print_report(nodes, edges, issues)
