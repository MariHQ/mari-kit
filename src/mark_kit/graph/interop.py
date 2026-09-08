"""Transient graph projections and loss-visible interchange encoders."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any
from urllib.parse import quote


def _attributes(values: Mapping[str, Any]) -> MappingProxyType:
    return MappingProxyType(dict(values))


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectionEdge:
    source: str
    target: str
    relation: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source or not self.target or not self.relation:
            raise ValueError("edge source, target, and relation are required")
        object.__setattr__(self, "attributes", _attributes(self.attributes))


@dataclass(frozen=True, slots=True, kw_only=True)
class GraphProjection:
    nodes: tuple[tuple[str, Mapping[str, Any]], ...]
    edges: tuple[ProjectionEdge, ...]
    directed: bool = True

    def __post_init__(self) -> None:
        normalized = tuple(
            (node_id, _attributes(attributes)) for node_id, attributes in self.nodes
        )
        ids = [node_id for node_id, _ in normalized]
        if len(ids) != len(set(ids)):
            raise ValueError("projection node IDs must be unique")
        object.__setattr__(self, "nodes", normalized)
        object.__setattr__(self, "edges", tuple(self.edges))


@dataclass(frozen=True, slots=True, kw_only=True)
class InterchangeReport:
    losses: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class EncodedGraph:
    data: bytes
    report: InterchangeReport


def _scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _graphml_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "long"
    if isinstance(value, float):
        return "double"
    return "string"


def _graphml_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def to_graphml(projection: GraphProjection) -> EncodedGraph:
    namespace = "http://graphml.graphdrawing.org/xmlns"
    ET.register_namespace("", namespace)
    root = ET.Element(f"{{{namespace}}}graphml")
    node_attributes: dict[str, set[str]] = {}
    edge_attributes: dict[str, set[str]] = {"relation": {"string"}}
    for _, attributes in projection.nodes:
        for key, value in attributes.items():
            if _scalar(value):
                node_attributes.setdefault(key, set()).add(_graphml_type(value))
    for edge in projection.edges:
        for key, value in edge.attributes.items():
            if _scalar(value):
                edge_attributes.setdefault(key, set()).add(_graphml_type(value))
    node_keys = {key: f"n{index}" for index, key in enumerate(sorted(node_attributes))}
    edge_keys = {key: f"e{index}" for index, key in enumerate(sorted(edge_attributes))}
    losses: list[str] = []
    for key in sorted(node_attributes):
        value_type = (
            next(iter(node_attributes[key]))
            if len(node_attributes[key]) == 1
            else "string"
        )
        if len(node_attributes[key]) > 1:
            losses.append(f"node:{key}:mixed_types_coerced_to_string")
        ET.SubElement(
            root,
            f"{{{namespace}}}key",
            {
                "id": node_keys[key],
                "for": "node",
                "attr.name": key,
                "attr.type": value_type,
            },
        )
    for key in sorted(edge_attributes):
        value_type = (
            next(iter(edge_attributes[key]))
            if len(edge_attributes[key]) == 1
            else "string"
        )
        if len(edge_attributes[key]) > 1:
            losses.append(f"edge:{key}:mixed_types_coerced_to_string")
        ET.SubElement(
            root,
            f"{{{namespace}}}key",
            {
                "id": edge_keys[key],
                "for": "edge",
                "attr.name": key,
                "attr.type": value_type,
            },
        )
    graph = ET.SubElement(
        root,
        f"{{{namespace}}}graph",
        edgedefault="directed" if projection.directed else "undirected",
    )
    for node_id, attributes in sorted(projection.nodes, key=lambda item: item[0]):
        node = ET.SubElement(graph, f"{{{namespace}}}node", id=node_id)
        for key, value in sorted(attributes.items()):
            if not _scalar(value):
                losses.append(f"node:{node_id}:{key}:nested_value")
                continue
            ET.SubElement(
                node, f"{{{namespace}}}data", key=node_keys[key]
            ).text = _graphml_text(value)
    for index, edge in enumerate(
        sorted(
            projection.edges, key=lambda item: (item.source, item.target, item.relation)
        )
    ):
        element = ET.SubElement(
            graph,
            f"{{{namespace}}}edge",
            id=f"e{index}",
            source=edge.source,
            target=edge.target,
        )
        ET.SubElement(
            element, f"{{{namespace}}}data", key=edge_keys["relation"]
        ).text = edge.relation
        for key, value in sorted(edge.attributes.items()):
            if not _scalar(value):
                losses.append(f"edge:{index}:{key}:nested_value")
                continue
            ET.SubElement(
                element, f"{{{namespace}}}data", key=edge_keys[key]
            ).text = _graphml_text(value)
    return EncodedGraph(
        data=ET.tostring(root, encoding="utf-8", xml_declaration=True),
        report=InterchangeReport(losses=tuple(losses)),
    )


def to_json_ld(projection: GraphProjection) -> EncodedGraph:
    node_values: dict[str, dict[str, Any]] = {
        node_id: {"@id": node_id, **dict(attributes)}
        for node_id, attributes in projection.nodes
    }
    losses: list[str] = []
    for edge in projection.edges:
        source = node_values.get(edge.source)
        if source is None:
            losses.append(f"edge:{edge.source}:{edge.target}:missing_source")
            continue
        value: dict[str, Any] = {"@id": edge.target}
        if edge.attributes:
            value.update(edge.attributes)
            losses.append(
                f"edge:{edge.source}:{edge.target}:attributes_reified_as_value"
            )
        current = source.setdefault(edge.relation, [])
        if isinstance(current, list):
            current.append(value)
    payload = {"@graph": [node_values[key] for key in sorted(node_values)]}
    data = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return EncodedGraph(data=data, report=InterchangeReport(losses=tuple(losses)))


def to_networkx(projection: GraphProjection) -> tuple[Any, InterchangeReport]:
    """Convert when NetworkX is installed without making it a dependency."""

    try:
        import networkx as nx  # pyright: ignore[reportMissingModuleSource]
    except ImportError as error:
        raise ImportError(
            "NetworkX conversion requires the 'networkx' package"
        ) from error
    graph = nx.DiGraph() if projection.directed else nx.Graph()
    graph.add_nodes_from(
        (node_id, dict(attributes)) for node_id, attributes in projection.nodes
    )
    graph.add_edges_from(
        (edge.source, edge.target, {"relation": edge.relation, **dict(edge.attributes)})
        for edge in projection.edges
    )
    duplicate_endpoints = len(
        {(edge.source, edge.target) for edge in projection.edges}
    ) != len(projection.edges)
    losses = ("parallel_edges_collapsed",) if duplicate_endpoints else ()
    return graph, InterchangeReport(losses=losses)


def from_networkx(graph: Any) -> tuple[GraphProjection, InterchangeReport]:
    directed = bool(graph.is_directed())
    nodes = tuple(
        (str(node), dict(attributes)) for node, attributes in graph.nodes(data=True)
    )
    edges: list[ProjectionEdge] = []
    losses: list[str] = []
    for left, right, attributes in graph.edges(data=True):
        values = dict(attributes)
        relation = str(values.pop("relation", "related_to"))
        edges.append(
            ProjectionEdge(
                source=str(left),
                target=str(right),
                relation=relation,
                attributes=values,
            )
        )
    if bool(graph.is_multigraph()):
        losses.append("parallel_edge_keys_not_preserved")
    return GraphProjection(
        nodes=nodes, edges=tuple(edges), directed=directed
    ), InterchangeReport(losses=tuple(losses))


def to_rdflib(
    projection: GraphProjection, *, base_iri: str = "urn:mari:"
) -> tuple[Any, InterchangeReport]:
    try:
        from rdflib import (  # pyright: ignore[reportMissingImports]
            Graph,
            Literal,
            URIRef,
        )
    except ImportError as error:
        raise ImportError("RDF conversion requires the 'rdflib' package") from error
    graph = Graph()
    losses: list[str] = []

    def iri(value: str) -> Any:
        return URIRef(base_iri + quote(value, safe=""))

    for edge in projection.edges:
        graph.add((iri(edge.source), iri(edge.relation), iri(edge.target)))
        if edge.attributes:
            losses.append(f"edge:{edge.source}:{edge.target}:attributes_not_reified")
    for node_id, attributes in projection.nodes:
        subject = iri(node_id)
        for key, value in attributes.items():
            if _scalar(value):
                graph.add((subject, iri(key), Literal(value)))
            else:
                losses.append(f"node:{node_id}:{key}:nested_value")
    return graph, InterchangeReport(losses=tuple(losses))


def to_pyg_data(projection: GraphProjection) -> tuple[Any, InterchangeReport]:
    try:
        import torch  # pyright: ignore[reportMissingImports]
        from torch_geometric.data import Data  # pyright: ignore[reportMissingImports]
    except ImportError as error:
        raise ImportError(
            "PyG conversion requires 'torch' and 'torch-geometric'"
        ) from error
    node_ids = tuple(node_id for node_id, _ in projection.nodes)
    positions = {node_id: index for index, node_id in enumerate(node_ids)}
    endpoints = [
        (positions[edge.source], positions[edge.target])
        for edge in projection.edges
        if edge.source in positions and edge.target in positions
    ]
    missing = [
        edge
        for edge in projection.edges
        if edge.source not in positions or edge.target not in positions
    ]
    edge_index = (
        torch.tensor(endpoints, dtype=torch.long).t().contiguous()
        if endpoints
        else torch.empty((2, 0), dtype=torch.long)
    )
    data = Data(edge_index=edge_index, num_nodes=len(node_ids))
    data.node_ids = node_ids
    data.edge_relations = tuple(
        edge.relation
        for edge in projection.edges
        if edge.source in positions and edge.target in positions
    )
    losses = tuple(
        f"edge:{edge.source}:{edge.target}:missing_endpoint" for edge in missing
    )
    losses += (
        ("node_and_edge_attributes_not_tensorized",)
        if any(attributes for _, attributes in projection.nodes)
        or any(edge.attributes for edge in projection.edges)
        else ()
    )
    return data, InterchangeReport(losses=losses)
