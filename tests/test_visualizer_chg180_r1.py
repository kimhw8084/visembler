from __future__ import annotations

import base64
import copy
import io
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image
from pptx import Presentation
from pptx.util import Inches

from company_ui.products.visualizer.domain import VisualizerContractError, canonical_model
from company_ui.products.visualizer.ppt_service import _kind, _validate_diagram_geometry, bound_export_items, export_pptx, import_visembler_pptx

ROOT = Path(__file__).resolve().parents[1]


def _wafer_model() -> dict:
    fields = [
        {'id': 'die_x', 'name': 'Die X', 'type': 'integer'},
        {'id': 'die_y', 'name': 'Die Y', 'type': 'integer'},
        {'id': 'yield', 'name': 'Yield', 'type': 'number'},
        {'id': 'reference', 'name': 'Reference', 'type': 'number'},
        {'id': 'affected', 'name': 'Affected', 'type': 'number'},
        {'id': 'wafer', 'name': 'Wafer', 'type': 'identifier'},
        {'id': 'lot', 'name': 'Lot', 'type': 'identifier'},
        {'id': 'tool', 'name': 'Tool', 'type': 'categorical'},
        {'id': 'chamber', 'name': 'Chamber', 'type': 'categorical'},
        {'id': 'recipe', 'name': 'Recipe', 'type': 'categorical'},
        {'id': 'process', 'name': 'Process', 'type': 'categorical'},
    ]
    rows = [
        [0, 0, 98.1, 100.0, 100.0, 'W07', 'L2407', 'ETCH-08', 'A', 'REC-17', 'Etch'],
        [1, 0, 96.0, 100.0, 95.0, 'W07', 'L2407', 'ETCH-08', 'A', 'REC-17', 'Etch'],
        [0, 1, 0, 100.0, 102.0, 'W07', 'L2407', 'ETCH-08', 'A', 'REC-17', 'Etch'],
        [1, 1, None, 102.0, None, 'W07', 'L2407', 'ETCH-08', 'A', 'REC-17', 'Etch'],
    ]
    return canonical_model({
        'mode': 'smart', 'canvas': {'width': 1600, 'height': 900}, 'nextId': 3,
        'datasets': [{'id': 'd-wafer', 'name': 'CHG-180 RCA wafer evidence', 'fields': fields, 'rows': rows}],
        'items': [
            {
                'id': 'c1', 'type': 'wafer', 'engine': 'WaferFabEngine', 'element': 'Wafer Map',
                'title': 'Affected Wafer Map', 'order': 0, 'dataset_id': 'd-wafer',
                'mapping': {'die_x': 'die_x', 'die_y': 'die_y', 'value': 'yield', 'wafer_id': 'wafer', 'lot_id': 'lot', 'tool': 'tool', 'chamber': 'chamber', 'recipe': 'recipe', 'process': 'process'},
            },
            {
                'id': 'c2', 'type': 'wafer', 'engine': 'WaferFabEngine', 'element': 'Wafer Difference Map',
                'title': 'Affected − Reference by Die', 'order': 1, 'dataset_id': 'd-wafer',
                'mapping': {'die_x': 'die_x', 'die_y': 'die_y', 'reference_value': 'reference', 'affected_value': 'affected', 'wafer_id': 'wafer', 'lot_id': 'lot', 'tool': 'tool', 'chamber': 'chamber', 'recipe': 'recipe', 'process': 'process'},
            },
        ],
    })


def _two_map_layout() -> dict:
    return {
        'canvas': {'width': 1600, 'height': 900},
        'items': [
            {'id': 'c1', 'x': 20, 'y': 20, 'w': 760, 'h': 860},
            {'id': 'c2', 'x': 820, 'y': 20, 'w': 760, 'h': 860},
        ],
    }


def _descr(shape) -> list[str]:
    return [node.get('descr') or '' for node in shape._element.xpath('.//p:cNvPr')]


FLOW_LABELS = [
    'Define affected wafer scope and customer impact',
    'Contain material from the suspect process window',
    'Verify measurement method against qualified standards',
    'Compare affected and reference wafer populations',
    'Inspect etch tool and chamber process history',
    'Correlate recipe settings with die-level yield loss',
    'Confirm the physical defect signature by inspection',
    'Apply corrective action and verify effectiveness',
    'Release production after engineering approval',
]


def _process_flow(*, direction='down', canvas=(1600, 2305), bounds=(1080.158375508504, 776.9999999999999, 505.84162449149613, 1514)):
    nodes = FLOW_LABELS if direction == 'down' else ['Inspect incoming lot', 'Qualify process window']
    item = {
        'id': 'c6', 'type': 'diagram', 'engine': 'DiagramEngine', 'element': 'Process Flow',
        'title': 'Process Flow' if direction == 'down' else 'Inspection Flow',
        'direction': direction, 'nodes': nodes, 'edges': [[source, target] for source, target in zip(nodes, nodes[1:])],
        'order': 0,
    }
    width, height = canvas
    x, y, item_width, item_height = bounds
    model = canonical_model({'mode': 'smart', 'canvas': {'width': width, 'height': height}, 'nextId': 7, 'items': [item]})
    geometry = {'canvas': {'width': width, 'height': height}, 'items': [{'id': 'c6', 'x': x, 'y': y, 'w': item_width, 'h': item_height}]}
    return model, geometry


def _diagram_payload(shape, prefix):
    return json.loads(next(value.removeprefix(prefix) for value in _descr(shape) if value.startswith(prefix)))


def _node_payload(shape):
    descriptions = _descr(shape)
    if any(value.startswith('VisualizerDiagramNode:') for value in descriptions):
        return _diagram_payload(shape, 'VisualizerDiagramNode:')
    semantic = _diagram_payload(shape, 'VisualizerSemantic:')
    return {'item_id': semantic['id'], 'node_index': 0, 'label': semantic['nodes'][0], 'direction': semantic['direction']}


def _diagram_signature(path):
    deck = Presentation(str(path))
    return [
        (shape.name, shape.left, shape.top, shape.width, shape.height, getattr(shape, 'text', ''),
         bool(shape._element.xpath('.//a:tailEnd')), tuple(_descr(shape)))
        for slide in deck.slides for shape in slide.shapes
        if shape.name.startswith('VIZ::Process Flow::')
        or shape.name.startswith('VIZ::DiagramTitle::Process Flow::')
        or shape.name.startswith('VIZ::DiagramEdge::Process Flow::')
        or shape.name.startswith('VIZ::DiagramContinuation::Process Flow::')
    ]


def test_chg180_waferfab_map_variants_are_first_class_export_kinds():
    assert _kind({'engine': 'WaferFabEngine', 'element': 'Wafer Map'}) == 'wafer_map'
    assert _kind({'engine': 'WaferFabEngine', 'element': 'Wafer Difference Map'}) == 'wafer_difference'
    assert _kind({'engine': 'WaferFabEngine', 'element': 'Tool × Chamber Matrix'}) == 'fallback'


def test_chg180_bound_wafer_projection_preserves_die_values_identity_and_source_model():
    model = _wafer_model()
    source = copy.deepcopy(model)
    projected = bound_export_items(model)
    by_id = {entry['id']: entry for entry in projected}

    wafer = by_id['c1']
    assert wafer['observations'] == [
        {'x': 0, 'y': 0, 'value': 98.1},
        {'x': 1, 'y': 0, 'value': 96.0},
        {'x': 0, 'y': 1, 'value': 0},
        {'x': 1, 'y': 1, 'value': None},
    ]
    assert [wafer[key] for key in ('wafer_id', 'lot_id', 'tool', 'chamber', 'recipe', 'process')] == ['W07', 'L2407', 'ETCH-08', 'A', 'REC-17', 'Etch']

    difference = by_id['c2']['observations']
    assert [(row['x'], row['y'], row['reference_value'], row['affected_value'], row['delta']) for row in difference] == [
        (0, 0, 100.0, 100.0, 0.0),
        (1, 0, 100.0, 95.0, -5.0),
        (0, 1, 100.0, 102.0, 2.0),
        (1, 1, 102.0, None, None),
    ]
    assert model == source


def test_chg180_powerpoint_has_editable_spatial_cells_not_generic_fallback():
    model = _wafer_model()
    original = copy.deepcopy(model)
    deck = Presentation(io.BytesIO(export_pptx(None, model, layout_geometry=_two_map_layout())))
    slide = deck.slides[0]
    shapes = list(slide.shapes)

    assert len([shape for shape in shapes if shape.name.endswith('wafer-outline')]) == 2
    assert len([shape for shape in shapes if 'orientation-notch' in shape.name]) == 2
    wafer_cells = [shape for shape in shapes if shape.name.startswith('VIZ::Affected Wafer Map::die-')]
    delta_cells = [shape for shape in shapes if shape.name.startswith('VIZ::Affected − Reference by Die::die-')]
    assert len(wafer_cells) == len(delta_cells) == 4
    assert all(shape.left > 0 and shape.top > 0 and shape.width > 0 and shape.height > 0 for shape in wafer_cells + delta_cells)

    def die_map(cells):
        result = {}
        for shape in cells:
            payload = next(value.removeprefix('VisualizerSemanticDie:') for value in _descr(shape) if value.startswith('VisualizerSemanticDie:'))
            observation = json.loads(payload)
            result[(observation['x'], observation['y'])] = {'shape': shape, 'observation': observation}
        return result

    wafer_dies, delta_dies = die_map(wafer_cells), die_map(delta_cells)
    assert wafer_dies[(1, 0)]['shape'].left > wafer_dies[(0, 0)]['shape'].left
    assert wafer_dies[(0, 1)]['shape'].top < wafer_dies[(0, 0)]['shape'].top
    assert delta_dies[(1, 0)]['shape'].left > delta_dies[(0, 0)]['shape'].left
    assert delta_dies[(0, 1)]['shape'].top < delta_dies[(0, 0)]['shape'].top
    negative_color = tuple(delta_dies[(1, 0)]['shape'].fill.fore_color.rgb)
    positive_color = tuple(delta_dies[(0, 1)]['shape'].fill.fore_color.rgb)
    assert negative_color[2] > negative_color[0]
    assert positive_color[0] > positive_color[2]

    wafer_panel = next(shape for shape in shapes if shape.name == 'VIZ::Affected Wafer Map::spatial-panel')
    difference_panel = next(shape for shape in shapes if shape.name == 'VIZ::Affected − Reference by Die::spatial-panel')
    wafer_payload = json.loads(next(value.removeprefix('VisualizerSemantic:') for value in _descr(wafer_panel) if value.startswith('VisualizerSemantic:')))
    difference_payload = json.loads(next(value.removeprefix('VisualizerSemantic:') for value in _descr(difference_panel) if value.startswith('VisualizerSemantic:')))
    assert [row['value'] for row in wafer_payload['observations']] == [98.1, 96.0, 0, None]
    assert [wafer_payload[key] for key in ('wafer_id', 'lot_id', 'tool', 'chamber', 'recipe', 'process')] == ['W07', 'L2407', 'ETCH-08', 'A', 'REC-17', 'Etch']
    assert [row['delta'] for row in difference_payload['observations']] == [0.0, -5.0, 2.0, None]
    assert all(any(value.startswith('VisualizerSemanticDie:') for value in _descr(shape)) for shape in delta_cells)

    text = '\n'.join(shape.text for shape in shapes if getattr(shape, 'has_text_frame', False))
    for expected in ('W07', 'L2407', 'ETCH-08', 'Chamber A', 'REC-17', 'Process Etch', 'SIGNED DELTA · AFFECTED − REFERENCE', '-5', '+2'):
        assert expected in text
    assert not any('Controlled fallback' in shape.text for shape in shapes if getattr(shape, 'has_text_frame', False))
    assert model == original


def test_chg180_geometry_payload_is_rejected_when_incomplete_overlapping_or_out_of_hull():
    model = _wafer_model()
    layout = _two_map_layout()
    layout['items'] = layout['items'][:1]
    with pytest.raises(VisualizerContractError, match='do not match'):
        export_pptx(None, model, layout_geometry=layout)
    layout = _two_map_layout()
    layout['items'][1]['x'] = 700
    with pytest.raises(VisualizerContractError, match='overlapping'):
        export_pptx(None, model, layout_geometry=layout)
    layout = _two_map_layout()
    layout['items'][1]['y'] = 890
    with pytest.raises(VisualizerContractError, match='exceeds'):
        export_pptx(None, model, layout_geometry=layout)


def test_chg180_keeps_existing_chart_table_diagram_image_and_metric_export_kinds():
    expected = {
        'CoreChartEngine': 'chart', 'EngineeringChartEngine': 'chart',
        'TableEngine': 'table', 'MatrixEngine': 'table', 'DiagramEngine': 'diagram',
        'ImageMediaEngine': 'image', 'MetricEngine': 'kpi', 'ComparisonEngine': 'kpi',
    }
    for engine, kind in expected.items():
        assert _kind({'engine': engine}) == kind

    image = io.BytesIO(); Image.new('RGB', (8, 8), (30, 80, 160)).save(image, format='PNG')
    encoded = 'data:image/png;base64,' + base64.b64encode(image.getvalue()).decode('ascii')
    entries = [
        {'id': 'm', 'type': 'metric', 'engine': 'MetricEngine', 'element': 'Hero KPI', 'title': 'Yield', 'value': 0, 'order': 0},
        {'id': 'c', 'type': 'chart', 'engine': 'CoreChartEngine', 'element': 'Line Chart', 'title': 'Trend', 'data': [['W1', 0], ['W2', 5]], 'order': 1},
        {'id': 't', 'type': 'table', 'engine': 'TableEngine', 'element': 'Clean Table', 'title': 'Actions', 'customTable': {'headers': ['Action', 'Status'], 'rows': [['Verify', 'Open']]}, 'order': 2},
        {'id': 'd', 'type': 'diagram', 'engine': 'DiagramEngine', 'element': 'Process Flow', 'title': 'Flow', 'nodes': ['Inspect', 'Release'], 'edges': [['Inspect', 'Release']], 'order': 3},
        {'id': 'i', 'type': 'image', 'engine': 'ImageMediaEngine', 'element': 'Image', 'title': 'Evidence image', 'src': encoded, 'order': 4},
    ]
    geometry = {'canvas': {'width': 1600, 'height': 900}, 'items': [
        {'id': entry['id'], 'x': 20 + index * 310, 'y': 20, 'w': 290, 'h': 300} for index, entry in enumerate(entries)
    ]}
    deck = Presentation(io.BytesIO(export_pptx(None, canonical_model({'items': entries, 'nextId': 6}), layout_geometry=geometry)))
    shapes = list(deck.slides[0].shapes)
    assert any(getattr(shape, 'has_chart', False) for shape in shapes)
    assert any(getattr(shape, 'has_table', False) for shape in shapes)
    assert any(getattr(shape, 'shape_type', None) == 13 for shape in shapes)
    assert any(shape.name.startswith('VIZ::Flow::Inspect') for shape in shapes)
    assert any(getattr(shape, 'has_text_frame', False) and '0' in shape.text for shape in shapes)


def test_chg180_process_flow_geometry_is_rebuilt_from_saved_diagram_content():
    if not shutil.which('node'):
        pytest.skip('Node.js is required for the maintained Visembler renderer checks.')
    script = """
      import {diagramRenderBounds, renderDiagramSvg} from './company_ui/products/visualizer/assets/authoring_diagram_studio.mjs';
      const labels=['Problem definition and scope','Method qualification','Machine chamber verification','Material traceability review','Measurement system confirmation','Environment excursion analysis','Containment effectiveness review','Corrective action verification','Production release approval'];
      const entry={engine:'DiagramEngine',element:'Process Flow',direction:'down',nodes:labels,edges:labels.slice(0,-1).map((label,index)=>[label,labels[index+1]])};
      const bounds=diagramRenderBounds(entry),again=diagramRenderBounds(structuredClone(entry)),svg=renderDiagramSvg(entry);
      console.log(JSON.stringify({bounds,again,svg}));
    """
    result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT, text=True, capture_output=True, check=True)
    projection = json.loads(result.stdout)
    assert projection['bounds'] == projection['again']
    assert projection['bounds']['height'] > 1400
    view_box = projection['svg'].split('viewBox="', 1)[1].split('"', 1)[0]
    assert float(view_box.split()[3]) == projection['bounds']['height']
    for label in ('Problem definition and scope', 'Machine chamber verification', 'Production release approval'):
        assert label in projection['svg']


def test_chg180_process_flow_powerpoint_projection_preserves_validated_geometry_and_direction(tmp_path):
    model, geometry = _process_flow()
    assert geometry['canvas'] == {'width': 1600, 'height': 2305}
    assert geometry['items'][0] == {
        'id': 'c6', 'x': 1080.158375508504, 'y': 776.9999999999999,
        'w': 505.84162449149613, 'h': 1514,
    }
    output = tmp_path / 'dense-operations.pptx'
    output.write_bytes(export_pptx(None, model, layout_geometry=geometry))
    first_signature = _diagram_signature(output)
    again = tmp_path / 'dense-operations-again.pptx'
    again.write_bytes(export_pptx(None, model, layout_geometry=geometry))
    assert first_signature == _diagram_signature(again)

    deck = Presentation(str(output))
    slide = deck.slides[0]
    diagram_container = next(shape for shape in slide.shapes if shape.name == 'VIZ::Process Flow')
    assert diagram_container.text == ''
    node_shapes = [shape for shape in slide.shapes if shape.name.startswith('VIZ::Process Flow::') and '::node-' in shape.name]
    assert len(node_shapes) == 9
    node_shapes.sort(key=lambda shape: _node_payload(shape)['node_index'])
    for index, (shape, expected) in enumerate(zip(node_shapes, FLOW_LABELS)):
        assert ''.join(shape.text.split()) == ''.join(expected.split())
        assert all(paragraph.font.size.pt == 10 for paragraph in shape.text_frame.paragraphs)
        node = _node_payload(shape)
        assert node['node_index'] == index and node['direction'] == 'down'
        if index:
            assert node_shapes[index - 1].top < shape.top

    scale = deck.slide_height / geometry['canvas']['height']
    x, y, width, height = (round(geometry['items'][0][key] * scale) for key in ('x', 'y', 'w', 'h'))
    rect = (x, y, width, height)
    primitives = [
        shape for shape in slide.shapes
        if shape.name.startswith('VIZ::Process Flow::')
        or shape.name.startswith('VIZ::DiagramTitle::Process Flow::')
        or shape.name.startswith('VIZ::DiagramEdge::Process Flow::')
    ]
    _validate_diagram_geometry(slide, rect, primitives)
    for shape in primitives:
        assert shape.left >= x and shape.top >= y
        assert shape.left + shape.width <= x + width
        assert shape.top + shape.height <= y + height
        assert shape.left >= 0 and shape.top >= 0
        assert shape.left + shape.width <= deck.slide_width
        assert shape.top + shape.height <= deck.slide_height

    for first, second in zip(node_shapes, node_shapes[1:]):
        overlap_w = min(first.left + first.width, second.left + second.width) - max(first.left, second.left)
        overlap_h = min(first.top + first.height, second.top + second.height) - max(first.top, second.top)
        assert not (overlap_w > 1 and overlap_h > 1)
        assert abs((first.left + first.width // 2) - (second.left + second.width // 2)) <= 1
    edges = [shape for shape in slide.shapes if shape.name.startswith('VIZ::DiagramEdge::Process Flow::')]
    assert len(edges) == 8
    semantic_edges = [_diagram_payload(shape, 'VisualizerSemanticEdge:') for shape in edges]
    assert [(edge['source'], edge['target']) for edge in semantic_edges] == list(zip(FLOW_LABELS, FLOW_LABELS[1:]))
    assert all(shape._element.xpath('.//a:tailEnd') for shape in edges)
    imported = import_visembler_pptx(output.read_bytes())
    flow = imported['items'][0]
    assert flow['id'] == 'c6' and flow['direction'] == 'down'
    assert flow['nodes'] == FLOW_LABELS and flow['edges'] == [list(edge) for edge in zip(FLOW_LABELS, FLOW_LABELS[1:])]


def test_chg180_rightward_process_flow_stays_horizontal_when_it_fits(tmp_path):
    model, geometry = _process_flow(direction='right', canvas=(1600, 900), bounds=(80, 80, 1440, 700))
    deck = Presentation(io.BytesIO(export_pptx(None, model, layout_geometry=geometry)))
    slide = deck.slides[0]
    nodes = [shape for shape in slide.shapes if shape.name.startswith('VIZ::Inspection Flow::') and '::node-' in shape.name]
    nodes.sort(key=lambda shape: _node_payload(shape)['node_index'])
    assert [shape.text.replace('\n', ' ') for shape in nodes] == ['Inspect incoming lot', 'Qualify process window']
    assert nodes[0].left < nodes[1].left
    assert abs((nodes[0].top + nodes[0].height // 2) - (nodes[1].top + nodes[1].height // 2)) <= 1
    connector = next(shape for shape in slide.shapes if shape.name.startswith('VIZ::DiagramEdge::Inspection Flow::'))
    assert connector._element.xpath('.//a:tailEnd')
    assert _diagram_payload(connector, 'VisualizerSemanticEdge:') == {
        'item_id': 'c6', 'edge_index': 0, 'source': 'Inspect incoming lot',
        'target': 'Qualify process window', 'continuation': False,
    }


def test_chg180_data_flow_honors_down_direction(tmp_path):
    model, geometry = _process_flow()
    model['items'][0].update({'element': 'Data Flow', 'title': 'Data Flow', 'direction': 'down', 'nodes': ['Source population', 'Qualified observations', 'Engineering conclusion'], 'edges': [['Source population', 'Qualified observations'], ['Qualified observations', 'Engineering conclusion']]})
    geometry['items'][0].update({'x': 50, 'y': 50, 'w': 1500, 'h': 2200})
    deck = Presentation(io.BytesIO(export_pptx(None, model, layout_geometry=geometry)))
    nodes = [shape for shape in deck.slides[0].shapes if shape.name.startswith('VIZ::Data Flow::') and '::node-' in shape.name]
    nodes.sort(key=lambda shape: _node_payload(shape)['node_index'])
    assert len(nodes) == 3
    assert nodes[0].top < nodes[1].top < nodes[2].top
    assert all(_node_payload(shape)['direction'] == 'down' for shape in nodes[1:])
    edges = [shape for shape in deck.slides[0].shapes if shape.name.startswith('VIZ::DiagramEdge::Data Flow::')]
    assert [_diagram_payload(shape, 'VisualizerSemanticEdge:')['source'] for shape in edges] == ['Source population', 'Qualified observations']


def test_chg180_structural_diagram_validator_rejects_primitive_outside_assigned_region(tmp_path):
    model, geometry = _process_flow(direction='right', canvas=(1600, 900), bounds=(80, 80, 1440, 700))
    deck = Presentation(io.BytesIO(export_pptx(None, model, layout_geometry=geometry)))
    slide = deck.slides[0]
    scale = deck.slide_width / geometry['canvas']['width']
    rect = tuple(round(geometry['items'][0][key] * scale) for key in ('x', 'y', 'w', 'h'))
    primitives = [
        shape for shape in slide.shapes
        if shape.name.startswith('VIZ::Inspection Flow::')
        or shape.name.startswith('VIZ::DiagramTitle::Inspection Flow::')
        or shape.name.startswith('VIZ::DiagramEdge::Inspection Flow::')
    ]
    _validate_diagram_geometry(slide, rect, primitives)
    escaped = next(shape for shape in primitives if shape.name.startswith('VIZ::DiagramTitle::'))
    escaped.left = rect[0] - 1
    with pytest.raises(VisualizerContractError, match='assigned element region'):
        _validate_diagram_geometry(slide, rect, primitives)


def test_chg180_process_flow_continuations_are_ordered_complete_and_round_trip(tmp_path):
    model, geometry = _process_flow(canvas=(1600, 900), bounds=(40, 40, 1520, 820))
    template = Presentation()
    template.slide_width = Inches(4)
    template.slide_height = Inches(3)
    template.slides.add_slide(template.slide_layouts[6])
    template_bytes = io.BytesIO()
    template.save(template_bytes)
    output = export_pptx(template_bytes.getvalue(), model, layout_geometry=geometry)
    deck = Presentation(io.BytesIO(output))
    assert len(deck.slides) == 6
    headings = [
        shape.text for slide in deck.slides for shape in slide.shapes
        if shape.name.startswith('VIZ::DiagramTitle::Process Flow::')
    ]
    assert [' '.join(value.split()) for value in headings] == [f'Process Flow · Continued {index}/5' for index in range(1, 6)]
    nodes = [
        shape for slide in deck.slides for shape in slide.shapes
        if shape.name.startswith('VIZ::Process Flow::') and '::node-' in shape.name
    ]
    assert len(nodes) == len(FLOW_LABELS)
    nodes.sort(key=lambda shape: _node_payload(shape)['node_index'])
    assert [_node_payload(shape)['label'] for shape in nodes] == FLOW_LABELS
    edges = [
        shape for slide in deck.slides for shape in slide.shapes
        if shape.name.startswith('VIZ::DiagramEdge::Process Flow::')
    ]
    assert len(edges) == 8
    semantic_edges = sorted((_diagram_payload(shape, 'VisualizerSemanticEdge:') for shape in edges), key=lambda edge: edge['edge_index'])
    assert [(edge['source'], edge['target']) for edge in semantic_edges] == list(zip(FLOW_LABELS, FLOW_LABELS[1:]))
    assert sum(edge['continuation'] for edge in semantic_edges) == 4
    for slide in list(deck.slides)[1:]:
        slide_nodes = [
            shape for shape in slide.shapes
            if shape.name.startswith('VIZ::Process Flow::') and '::node-' in shape.name
        ]
        assert slide_nodes
        rect = (Inches(.5), Inches(.4), deck.slide_width-Inches(1), deck.slide_height-Inches(.8))
        diagram_shapes = [
            shape for shape in slide.shapes
            if shape.name.startswith('VIZ::Process Flow::')
            or shape.name.startswith('VIZ::DiagramTitle::Process Flow::')
            or shape.name.startswith('VIZ::DiagramEdge::Process Flow::')
            or shape.name.startswith('VIZ::DiagramContinuation::Process Flow::')
        ]
        _validate_diagram_geometry(slide, rect, diagram_shapes)
    imported = import_visembler_pptx(output)
    assert len(imported['items']) == 1
    assert imported['items'][0]['id'] == 'c6'
    assert imported['items'][0]['nodes'] == FLOW_LABELS
    assert imported['items'][0]['edges'] == [list(edge) for edge in zip(FLOW_LABELS, FLOW_LABELS[1:])]
    assert _diagram_signature_from_bytes(output) == _diagram_signature_from_bytes(export_pptx(template_bytes.getvalue(), model, layout_geometry=geometry))


def _diagram_signature_from_bytes(payload):
    deck = Presentation(io.BytesIO(payload))
    return [
        (shape.name, shape.left, shape.top, shape.width, shape.height, getattr(shape, 'text', ''),
         bool(shape._element.xpath('.//a:tailEnd')), tuple(_descr(shape)))
        for slide in deck.slides for shape in slide.shapes
    ]
