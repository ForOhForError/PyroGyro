import logging
import typing

import pyrogyro.io_types


class ControlNode:
    def __init__(
        self,
        root_graph: "ControlGraph",
        on: pyrogyro.io_types.MapSource = None,
        do: pyrogyro.io_types.MapTarget = None,
        always_active=False,
    ):
        self.root_graph = root_graph
        self.children: typing.List[ControlNode] = []
        self.on = on
        self.do = do
        self.always_active = always_active
        self.active = False

    def get_children(self):
        return self.children

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
                if isinstance(entry, pyrogyro.io_types.DetailedMapping):
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

    def pre_process(self, event_list: typing.List[pyrogyro.io_types.InputEvent]):
        if not self.always_active:
            for event in event_list:
                if event.source == self.on:
                    if event.event_type == pyrogyro.io_types.EventType.PRESS:
                        self.active = True
                    elif event.event_type == pyrogyro.io_types.EventType.RELEASE:
                        self.active = False
                    elif event.event_type == pyrogyro.io_types.EventType.UPDATE:
                        self.active = True
        if self.active or self.always_active:
            for child in self.get_children():
                child.pre_process(event_list)

    def process(self, event_list: typing.List[pyrogyro.io_types.InputEvent], pad, delta_time: float = 0.0):
        if self.active or self.always_active:
            for event in event_list:
                if event.source == self.on and event.is_processable:
                    if self.do:
                        self.do.handle_input(event, graph=self.root_graph, pad=pad)
            if self.do:
                self.do.handle_tick(delta_time=delta_time, graph=self.root_graph, pad=pad)
            for child in self.get_children():
                child.process(event_list, pad, delta_time=delta_time)


class ControlGraph:
    def __init__(self, main_layer: ControlNode | None = None):
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

    def set_main_layer(self, main_layer: ControlNode):
        self.main_layer = main_layer

    def process(self, event_list: typing.List[pyrogyro.io_types.InputEvent], pad, delta_time: float = 0.0):
        self.main_layer.pre_process(event_list)
        for layer in self.layers.values():
            layer.pre_process(event_list)
        self.main_layer.process(event_list, pad, delta_time=delta_time)
        for layer in self.layers.values():
            layer.process(event_list, pad, delta_time=delta_time)


def to_node(
    entry, root_graph: ControlGraph, on: pyrogyro.io_types.MapSource | None = None
):
    root = ControlNode(root_graph, on=on)
    if isinstance(entry, typing.Sequence):
        for sub_entry in entry:
            node = to_node(sub_entry, root_graph, on=on)
            root.add_child(node)
    elif isinstance(entry, dict):
        for sub_entry_key, sub_entry in entry.items():
            root.add_child(to_node(sub_entry, root_graph, on=sub_entry_key))
    elif isinstance(entry, GraphComponent):
        root.add_child(entry.to_node(root_graph, on=on))
    else:
        root.do = entry
    return root


class GraphComponent:
    def to_node(
        self, root_graph: ControlGraph, on: pyrogyro.io_types.MapSource | None = None
    ) -> ControlNode:
        raise NotImplementedError()
