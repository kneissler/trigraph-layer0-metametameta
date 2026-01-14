#!/usr/bin/env python3
"""
Generate a consistency report comparing .sheet files, diagram nodes, and legend nodes.
"""

import xml.etree.ElementTree as ET
import re
from pathlib import Path
from collections import defaultdict
import subprocess

DIAGRAM_PATH = '/Users/jakneissler/git/github/trigraph/trigraph-layer0-metametameta/doc/complete-graph-with-grounding.drawio'
SHEETS_DIR = Path('/Users/jakneissler/git/github/trigraph/trigraph-layer0-metametameta/sheets')

# Define legend mappings (abbreviations to full names)
LEGEND_MAPPINGS = {
    # Types
    'mnt': 'metaNType',
    'mt': 'metaType',
    'mlt': 'metaLevelType',
    'mr': 'metaRelation',
    'mrs': 'metaRelationSignature',
    'rp': 'relationProperty',
    'class': 'class',
    'rel': 'relation',
    'rs': 'relationSignature',

    # Relations
    'type': 'type',
    'ml': 'metaLevel',
    'sig': 'signature',
    'st': 'sourceType',
    'tt': 'targetType',
    'nml': 'nextMetaLevel',
    'rpr': 'relationPropertyRelation',

    # Signatures
    'a2at': 'any-to-anyType',
    'a2mlt': 'any-to-metaLevelType',
    'mnt2mnt': 'metaNType-to-metaNType',
    'mr2mrs': 'metaRelation-to-metaRelationSignature',
    'mlt2mlt': 'metaLevelType-to-metaLevelType',
    'mrs2mt': 'metaRelationSignature-to-metaType',
    'rs2rp': 'relationSignature-to-relationProperty',
    'r2rs': 'relation-to-relationSignature',

    # MetaLevels
    'ml0': 'metaLevel-0',
    'ml1': 'metaLevel-1',
    'ml2': 'metaLevel-2',
    'ml3': 'metaLevel-3',
    'mlN': 'metaLevel-N',

    # Relation properties
    'man': 'mandatory',
    'uni': 'unique',
    'imp': 'implicit',
    'tra': 'transient',
}

def parse_sheet_file(filepath):
    """Parse a .sheet file and extract node names from public/public+1/private sections."""
    with open(filepath, 'r') as f:
        lines = f.readlines()

    nodes = []
    current_section = None

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        # Check for section headers
        if line.startswith('public:'):
            current_section = 'public'
            continue
        elif line.startswith('public+1:'):
            current_section = 'public+1'
            continue
        elif line.startswith('private:'):
            current_section = 'private'
            continue
        elif line.startswith('meta:') or line.startswith('references:') or line.startswith('relations:'):
            current_section = None
            continue

        # If we're in a visibility section, extract node names
        if current_section and line.startswith('  ') and not line.startswith('    '):
            # This is a node definition (2-space indent)
            # Format: "  node-name: description"
            match = re.match(r'  ([a-zA-Z0-9_-]+):', line)
            if match:
                nodes.append(match.group(1))

    return sorted(nodes)

def parse_all_sheet_files():
    """Parse all .sheet files and organize nodes by package."""
    sheet_files = list(SHEETS_DIR.glob('*.sheet'))
    package_nodes = {}

    for sheet_file in sheet_files:
        package_name = sheet_file.stem
        nodes = parse_sheet_file(sheet_file)
        package_nodes[package_name] = nodes

    return package_nodes

def clean_html(text):
    """Remove HTML tags from text."""
    if not text:
        return ''
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    return clean.strip()

def parse_drawio_diagram():
    """Parse DrawIO file and extract diagram nodes (abbreviated) and legend nodes."""
    tree = ET.parse(DIAGRAM_PATH)
    root = tree.getroot()

    diagram_abbrev_nodes = defaultdict(list)  # Abbreviated names as they appear in diagram
    legend_abbrev_nodes = defaultdict(list)   # Abbreviated names from legend

    # Legend node IDs to skip when counting diagram nodes
    legend_ids = set()

    for cell in root.iter('mxCell'):
        cell_id = cell.get('id')
        value = cell.get('value', '')

        if not value or not cell_id:
            continue

        # Skip edges
        if cell.get('source') or cell.get('target'):
            continue

        # Clean HTML from value
        clean_value = clean_html(value)

        # Identify legend nodes
        if cell_id.startswith('legend_'):
            legend_ids.add(cell_id)

            # Extract legend abbreviation mappings
            # Format: <b><i>abbr</i></b> = full name
            match = re.search(r'([a-z0-9]+)\s*=\s*([a-zA-Z0-9_-]+)', clean_value, re.IGNORECASE)
            if match:
                abbr = match.group(1).strip()
                full_name = match.group(2).strip()
                # Determine package for legend entry
                package = categorize_node_by_fullname(full_name)
                if package:
                    legend_abbrev_nodes[package].append(abbr)
            continue

        # Skip container/decorative nodes
        is_container = (
            cell_id in ['0', '1', 'visibility_container'] or
            'container' in cell_id or
            clean_value.startswith('Layer') or
            clean_value.startswith('Meta') or
            clean_value.startswith('Types') or
            clean_value.startswith('Relations') or
            clean_value.startswith('Relation Signatures') or
            clean_value.startswith('Relation properties') or
            clean_value.startswith('Signature nodes') or
            clean_value.startswith('MetaLevel nodes') or
            clean_value.startswith('Grounding Nodes') or
            'grounding nodes' in clean_value or
            clean_value.startswith('Visibility') or
            clean_value == 'z' or
            clean_value == 'N' or
            clean_value == 'meta' or
            clean_value == 'layer 0' or
            clean_value.startswith('ml =') or
            clean_value.startswith('meta level') or
            clean_value.startswith('level') or
            'visible to' in clean_value.lower() or
            '55 grounding' in clean_value or
            clean_value.startswith('public') or
            clean_value.startswith('private')
        )

        if is_container:
            continue

        # Extract actual diagram node names
        node_name = None
        style = cell.get('style', '')

        # Check specific ID patterns
        if cell_id == 'mnt':
            node_name = 'mnt'
        elif cell_id == 'mt':
            node_name = 'mt'
        elif cell_id == 'mlt':
            node_name = 'mlt'
        elif cell_id == 'mr':
            node_name = 'mr'
        elif cell_id == 'mrs':
            node_name = 'mrs'
        elif cell_id == 'type_rel':
            node_name = 'type'
        elif cell_id == 'ml_rel':
            node_name = 'ml'
        elif cell_id == 'sig_rel':
            node_name = 'sig'
        elif cell_id == 'st_rel':
            node_name = 'st'
        elif cell_id == 'tt_rel':
            node_name = 'tt'
        elif cell_id == 'nml_rel':
            node_name = 'nml'
        elif cell_id == 'rpr':
            node_name = 'rpr'
        elif cell_id.startswith('sig') and cell_id[3:].isdigit():
            # Signature node - value contains the actual name
            node_name = clean_value
        elif cell_id.startswith('ml') and cell_id[2:] in ['0', '1', '2', '3', 'N']:
            node_name = cell_id
        elif clean_value in ['class', 'relation', 'relationSignature', 'mandatory', 'unique', 'implicit', 'transient']:
            node_name = clean_value
        # Catch any other layer 0 nodes with the characteristic blue fill color
        elif '#E6F0FF' in style or '#E6FFE6' in style:
            # These are layer 0 nodes, use the clean_value as node name
            if clean_value and len(clean_value) < 20:  # Reasonable node name length
                node_name = clean_value

        if node_name:
            package = categorize_node_by_abbrev(node_name)
            if package:
                diagram_abbrev_nodes[package].append(node_name)

    # Sort and deduplicate
    for package in diagram_abbrev_nodes:
        diagram_abbrev_nodes[package] = sorted(set(diagram_abbrev_nodes[package]))
    for package in legend_abbrev_nodes:
        legend_abbrev_nodes[package] = sorted(set(legend_abbrev_nodes[package]))

    return diagram_abbrev_nodes, legend_abbrev_nodes

def categorize_node_by_abbrev(abbrev_name):
    """Categorize a node by its abbreviated name."""
    # Expand to full name if possible
    full_name = LEGEND_MAPPINGS.get(abbrev_name, abbrev_name)
    return categorize_node_by_fullname(full_name)

def categorize_node_by_fullname(full_name):
    """Categorize a node into its package based on full name."""
    # metaLevels package
    if full_name.startswith('metaLevel-'):
        return 'metaLevels'

    # metaRelations package
    meta_relations = ['type', 'metaLevel', 'signature', 'relationPropertyRelation',
                     'sourceType', 'targetType', 'nextMetaLevel']
    if full_name in meta_relations:
        return 'metaRelations'

    # metaRelationSignatures package
    signatures = ['any-to-anyType', 'any-to-metaLevelType', 'metaNType-to-metaNType',
                 'metaRelation-to-metaRelationSignature', 'metaLevelType-to-metaLevelType',
                 'metaRelationSignature-to-metaType', 'relationSignature-to-relationProperty',
                 'relation-to-relationSignature']
    if full_name in signatures:
        return 'metaRelationSignatures'

    # types package
    types_nodes = ['class', 'relation', 'relationSignature', 'metaRelation',
                  'metaRelationSignature', 'metaType', 'metaLevelType',
                  'relationProperty', 'metaNType']
    if full_name in types_nodes:
        return 'types'

    # relationProperties package
    rel_props = ['mandatory', 'unique', 'implicit', 'transient']
    if full_name in rel_props:
        return 'relationProperties'

    return None

def expand_abbreviations(abbrev_list):
    """Expand abbreviated node names using legend mappings."""
    expanded = []
    for abbrev in abbrev_list:
        if abbrev in LEGEND_MAPPINGS:
            expanded.append(LEGEND_MAPPINGS[abbrev])
        else:
            expanded.append(abbrev)
    return sorted(expanded)

def check_consistency(sheet_nodes, diagram_abbrev, legend_abbrev):
    """
    Check if nodes are consistent across sheet, diagram, and legend.
    Returns: (is_consistent, message)
    """
    # Expand diagram and legend abbreviations
    expanded_diagram = expand_abbreviations(diagram_abbrev)
    expanded_legend = expand_abbreviations(legend_abbrev)

    # Check if diagram nodes (abbrev) match legend nodes (abbrev)
    diagram_legend_match = sorted(diagram_abbrev) == sorted(legend_abbrev)

    # Check if expanded diagram nodes match sheet nodes
    sheet_match = sorted(expanded_diagram) == sorted(sheet_nodes)

    is_consistent = diagram_legend_match and sheet_match

    if is_consistent:
        return True, "✓"
    else:
        issues = []
        if not diagram_legend_match:
            issues.append("diagram≠legend")
        if not sheet_match:
            # More detail
            if len(expanded_diagram) != len(sheet_nodes):
                issues.append(f"count:{len(expanded_diagram)}≠{len(sheet_nodes)}")
            else:
                issues.append("names differ")
        return False, "✗ (" + ", ".join(issues) + ")"

def generate_markdown_report():
    """Generate the consistency report in markdown format."""
    # Run analysis script
    result = subprocess.run(
        ['python3', 'analyze_diagram_consistency.py'],
        capture_output=True, text=True,
        cwd='/Users/jakneissler/git/github/trigraph/trigraph-layer0-metametameta'
    )

    # Parse data
    sheet_nodes = parse_all_sheet_files()
    diagram_abbrev, legend_abbrev = parse_drawio_diagram()

    # Generate report
    report = []
    report.append("# Diagram Consistency Report")
    report.append("")
    report.append("## Analysis Summary")
    report.append("")
    report.append("**Script:** `analyze_diagram_consistency.py`")
    report.append("")

    # Extract key findings from script output
    lines = result.stdout.split('\n')
    for i, line in enumerate(lines):
        if 'Total nodes in diagram:' in line:
            report.append(f"- {line.strip()}")
        elif 'Labeled nodes:' in line:
            report.append(f"- {line.strip()}")
        elif 'Total edges:' in line:
            report.append(f"- {line.strip()}")
        elif 'ISSUES SUMMARY' in line:
            for j in range(i+2, min(i+6, len(lines))):
                if lines[j].strip() and not lines[j].startswith('='):
                    report.append(f"- {lines[j].strip()}")

    report.append("")
    report.append("**Overall Assessment:**")
    for i, line in enumerate(lines):
        if 'OVERALL ASSESSMENT' in line:
            for j in range(i+2, len(lines)):
                if lines[j].strip() and not lines[j].startswith('='):
                    report.append(f"- {lines[j].strip()}")
            break

    report.append("")
    report.append("## Package Node Comparison")
    report.append("")
    report.append("This table shows node counts per package. The Consistency column indicates whether:")
    report.append("- The diagram nodes match the legend nodes (by abbreviation)")
    report.append("- When expanding abbreviations using the legend, the diagram nodes match the sheet file nodes")
    report.append("")
    report.append("| Package | Sheet Files | Diagram | Legend | Consistency |")
    report.append("|---------|-------------|---------|--------|-------------|")

    # Get all packages
    all_packages = sorted(set(list(sheet_nodes.keys()) + list(diagram_abbrev.keys()) + list(legend_abbrev.keys())))

    for package in all_packages:
        sheet_count = len(sheet_nodes.get(package, []))
        diagram_count = len(diagram_abbrev.get(package, []))
        legend_count = len(legend_abbrev.get(package, []))

        # Check consistency
        is_consistent, consistency_msg = check_consistency(
            sheet_nodes.get(package, []),
            diagram_abbrev.get(package, []),
            legend_abbrev.get(package, [])
        )

        report.append(f"| {package} | {sheet_count} | {diagram_count} | {legend_count} | {consistency_msg} |")

    report.append("")
    report.append("## Detailed Node Lists by Package")
    report.append("")

    for package in all_packages:
        report.append(f"### {package}")
        report.append("")

        sheet_list = sheet_nodes.get(package, [])
        diagram_list = diagram_abbrev.get(package, [])
        legend_list = legend_abbrev.get(package, [])

        report.append(f"**Sheet ({len(sheet_list)}):** {', '.join(sheet_list) if sheet_list else '(none)'}")
        report.append("")
        report.append(f"**Diagram ({len(diagram_list)}):** {', '.join(diagram_list) if diagram_list else '(none)'}")
        report.append("")
        report.append(f"**Legend ({len(legend_list)}):** {', '.join(legend_list) if legend_list else '(none)'}")
        report.append("")

        # Show expanded versions
        if diagram_list:
            expanded_diagram = expand_abbreviations(diagram_list)
            report.append(f"**Diagram (expanded):** {', '.join(expanded_diagram)}")
            report.append("")

    report.append("---")
    report.append("")
    report.append("*Report generated by `generate_consistency_report.py`*")

    return '\n'.join(report)

if __name__ == '__main__':
    report = generate_markdown_report()

    # Write to file
    output_path = '/Users/jakneissler/git/github/trigraph/trigraph-layer0-metametameta/CONSISTENCY_REPORT.md'
    with open(output_path, 'w') as f:
        f.write(report)

    print(f"Report generated: {output_path}")
    print()
    print(report)
