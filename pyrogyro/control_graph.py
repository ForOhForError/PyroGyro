import logging
import typing

from pyrogyro.io_types import (
    DetailedMapping,
    EventType,
    InputEvent,
    MapSource,
    MapTarget,
)


class ControlNode:
    def __init__(
        self,
        root_graph: "ControlGraph",
        on: MapSource = None,
        do: MapTarget = None,
        always_active=False,
    ):
        self.root_graph = root_graph
        self.children: typing.List[ControlNode] = []
        self.on = on
        self.do = do
        self.always_active = always_active
        self.active = always_active

    def print_structure(self, space_level=0, log_level=logging.DEBUG):
        if self.always_active:
            logging.log(log_level, f"{' '*space_level}(Always Active)")
        else:
            logging.log(log_level, f"{' '*space_level}{self.on} -> {self.do}")
        for child in self.children:
            child.print_structure(space_level=space_level + 1, log_level=log_level)

    def add_child(self, child: "ControlNode"):
        self.children.append(child)

    def add_from_layer(self, layer):
        root_map = layer.mapping
        if isinstance(root_map, typing.Sequence):
            for entry in root_map:
                if isinstance(entry, DetailedMapping):
                    node = ControlNode(self.root_graph, entry.input, entry.output)
                    self.children.append(node)
                else:
                    for subentry_key, subentry_value in entry.items():
                        if isinstance(subentry_value, typing.Sequence):
                            for final_value in subentry_value:
                                node = ControlNode(
                                    self.root_graph, subentry_key, final_value
                                )
                                self.children.append(node)
                        else:
                            node = ControlNode(
                                self.root_graph, subentry_key, subentry_value
                            )
                            self.children.append(node)
        else:
            for entry_key, entry_value in root_map.items():
                if isinstance(entry_value, typing.Sequence):
                    for final_value in entry_value:
                        node = ControlNode(self.root_graph, entry_key, final_value)
                        self.children.append(node)
                else:
                    node = ControlNode(self.root_graph, entry_key, entry_value)
                    self.children.append(node)

    def pre_process(self, event_list: typing.List[InputEvent]):
        if not self.always_active:
            for event in event_list:
                if event.source == self.on:
                    if event.event_type == EventType.PRESS:
                        self.active = True
                    elif event.event_type == EventType.RELEASE:
                        self.active = False
                    elif event.event_type == EventType.UPDATE:
                        self.active = True
        if self.active:
            for child in self.children:
                child.pre_process(event_list)

    def process(self, event_list: typing.List[InputEvent], pad):
        if self.active:
            for event in event_list:
                if event.source == self.on and event.is_processable:
                    if self.do:
                        self.do.process(event, graph=self.root_graph, pad=pad)
            for child in self.children:
                child.process(event_list, pad)


class ControlGraph:
    def __init__(self, main_layer: ControlNode|None = None):
        if not main_layer:
            self.main_layer = ControlNode(self, always_active=True)
        else:
            self.main_layer = main_layer
        self.layers: typing.Dict[str, ControlNode] = {}

    def print_structure(self, log_level=logging.DEBUG):
        self.main_layer.print_structure(log_level=log_level)
        for layer_name, layer in self.layers.items():
            logging.info(f"Layer {layer_name}")
            layer.print_structure(space_level=1, log_level=log_level)

    def add_to_main(self, node: ControlNode):
        self.main_layer.add_child(node)

    def set_layer(self, name: str, root: ControlNode):
        self.layers[name] = root

    def process(self, event_list: typing.List[InputEvent], pad):
        self.main_layer.pre_process(event_list)
        for layer in self.layers.values():
            layer.pre_process(event_list)
        self.main_layer.process(event_list, pad)
        for layer in self.layers.values():
            layer.process(event_list, pad)

    @classmethod
    def from_mapping(cls, mapping: "Mapping") -> "ControlGraph":
        graph = cls()
        graph.main_layer.add_from_layer(mapping)
        for layer_name, layer in mapping.layers.items():
            node = ControlNode(graph, always_active=True)
            node.add_from_layer(layer)
            graph.layers[layer_name] = node
        return graph


def to_node(entry, root_graph: ControlGraph, on: MapSource | None = None):
    root = ControlNode(root_graph, on=on)
    if isinstance(entry, typing.Sequence):
        pass
    elif isinstance(entry, dict):
        pass
    elif isinstance(entry, GraphComponent):
        return entry.to_node(root_graph, on=on)
    return root


class GraphComponent:
    def to_node(
        self, root_graph: ControlGraph, on: MapSource | None = None
    ) -> ControlNode:
        raise NotImplementedError()
