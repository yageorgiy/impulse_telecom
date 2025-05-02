import copy
import json
import re
# import os
# import traceback
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any


@dataclass
class ConfigUpdate:
    key: str
    from_: str
    to: str


@dataclass
class ConfigAddition:
    key: str
    value: str


@dataclass
class MetaDescriptionParameter:
    name: str
    type: str


@dataclass
class MetaDescription:
    class_: str
    documentation: str
    isRoot: bool
    max: str
    min: str
    parameters: list[MetaDescriptionParameter]


class ConfigEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, ConfigUpdate):
            d = obj.__dict__
            ret: dict[str, Any] = dict()
            ret['key'] = d['key']
            ret['from'] = d['from_']
            ret['to'] = d['to']
            return ret
        if isinstance(obj, ConfigAddition):
            return obj.__dict__
        return json.JSONEncoder.default(self, obj)


class MetaDescriptionEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, MetaDescription):
            d = obj.__dict__
            ret: dict[str, Any] = dict()
            ret["class"] = d["class_"]
            ret["documentation"] = d["documentation"]
            ret["isRoot"] = d["isRoot"]
            if d["max"] != "-":
                ret["max"] = d["max"]
            if d["min"] != "-":
                ret["min"] = d["min"]
            ret["parameters"] = d["parameters"]
            return ret
        if isinstance(obj, MetaDescriptionParameter):
            return obj.__dict__
        return json.JSONEncoder.default(self, obj)


def build_child_attributes(
    current_child: ET.Element,
    root: ET.Element,
    json_meta_parameters: list[MetaDescriptionParameter]
) -> None:
    for child in current_child:
        tag: str = child.tag
        if tag != "Attribute":
            continue

        child_attrib: dict[str, str] = child.attrib
        attribute_name: str = child_attrib.get("name", "")
        attribute_type: str = child_attrib.get("type", "")

        if attribute_name == "":
            continue

        attribute = ET.SubElement(root, attribute_name)
        attribute.text = attribute_type

        json_meta_parameters.append(MetaDescriptionParameter(
            name=attribute_name,
            type=attribute_type
        ))


def process(
    config: dict[str, str],
    patched_config: dict[str, str],
    impulse_test_input_tree: ET.ElementTree,
) -> tuple[bytes, str, str, str]:
    #
    # config / patched_config processing
    #
    final_json: dict[str, str] = copy.deepcopy(config)
    updates: list[ConfigUpdate] = []
    deletions: list[str] = []
    additions: list[ConfigAddition] = []

    for key, value in patched_config.items():
        # New item
        if key not in config:
            additions.append(ConfigAddition(
                key=key,
                value=value
            ))
            final_json[key] = value
        else:
            # Updated item
            if config[key] != value:
                updates.append(ConfigUpdate(
                    key=key,
                    from_=config[key],
                    to=value
                ))
                final_json[key] = value
            del config[key]

    # Find for removed items
    for key, value in config.items():
        deletions.append(key)
        del final_json[key]

    return_delta: str = json.dumps(
        {
            "additions": additions,
            "deletions": deletions,
            "updates": updates
        },
        # Allow utf-8 characters
        ensure_ascii=False,
        # Pretty print
        indent=4,
        # Custom encoder for dataclasses
        cls=ConfigEncoder
    )

    return_res_config: str = json.dumps(
        # From dict to list
        final_json,
        # Allow utf-8 characters
        ensure_ascii=False,
        # Pretty print
        indent=4
    )

    #
    # config.xml and meta.json processing
    #

    xml_root_tree: ET.Element = impulse_test_input_tree.getroot()
    xml_new_root: ET.Element | None = None
    xml_new_classes_dict: dict[str, ET.Element] = dict()
    xml_classes_list: list[ET.Element] = []
    xml_aggregation_list: list[ET.Element] = []

    json_meta: dict[str, MetaDescription] = dict()

    # Find all tags with Classes and Aggregations
    # Put items to lists again to avoid incorrect XML-order
    for child in xml_root_tree:
        # print(child.tag, child.attrib)
        tag = child.tag
        if tag == "Class":
            xml_classes_list.append(child)
            # classes_dict[child.attrib.get('name', '_')] = child
        elif tag == "Aggregation":
            xml_aggregation_list.append(child)

    # Process Classes
    # for key, class_child in classes_dict.items():
    for class_child in xml_classes_list:
        attrib: dict[str, str] = class_child.attrib
        class_name: str = attrib.get("name", "_")
        isRoot: bool = attrib.get("isRoot") == "true"

        if class_name in xml_new_classes_dict:
            print("Warning! Got duplication.", class_child)
            continue

        e = ET.Element(class_name)
        xml_new_classes_dict[class_name] = e

        if isRoot and xml_new_root is None:
            xml_new_root = e

        # Building basic MetaDescription for meta.json
        json_meta_parameters: list[MetaDescriptionParameter] = []
        build_child_attributes(class_child, e, json_meta_parameters)

        json_meta[class_name] = MetaDescription(
            class_=class_name,
            parameters=json_meta_parameters,
            isRoot=isRoot,
            documentation=attrib.get("documentation", ""),
            # placeholder, calculated later, should be ignored if "-"
            max="-",
            # placeholder, calculated later, should be ignored if "-"
            min="-"
        )

    if xml_new_root is None:
        print("No root found.")
        return b"", "", return_delta, return_res_config

    print("Built base.")

    # Process Aggregations
    for aggregation_child in xml_aggregation_list:
        source: str = aggregation_child.get("source", "")
        target: str = aggregation_child.get("target", "")

        if source == "" or target == "":
            continue

        if (source not in xml_new_classes_dict or
                target not in xml_new_classes_dict):
            continue

        xml_new_classes_dict[target].append(xml_new_classes_dict[source])

        json_meta[target].parameters.append(MetaDescriptionParameter(
            name=source,
            type="class"
        ))

        source_multiplicity: str = (
            aggregation_child.get("sourceMultiplicity", "1"))
        # Trying to find "number..number" in attribute
        match: list[tuple[str, str]] = (
            re.findall(r'([0-9]+)\.\.([0-9]+)', source_multiplicity))

        # should be ignored if 0
        _min: str = "0"
        _max: str = "0"

        if match and match[0]:
            data: tuple[str, str] = match[0]
            _min = data[0]
            _max = data[1]
        # elif isinstance(source_multiplicity, int):
        else:
            _min = source_multiplicity
            _max = source_multiplicity

        json_meta[source].max = _max
        json_meta[source].min = _min

    print("Built connections.")

    # XML export
    return_config_xml: bytes = ET.tostring(
        xml_new_root,
        encoding="utf-8",
        # Example file elements are not shortened
        short_empty_elements=False,
    )
    # TODO: prettify and use short empty elements
    # parsed = minidom.parseString(rough_xml_contents)
    # out_file.write(parsed.toprettyxml(indent="\t"))

    return_meta_json = json.dumps(
        # From dict to list
        list(json_meta.values()),
        # Allow utf-8 characters
        ensure_ascii=False,
        # Pretty print
        indent=4,
        # Custom encoder for dataclasses
        cls=MetaDescriptionEncoder
    )

    return (return_config_xml, return_meta_json,
            return_delta, return_res_config)


def main() -> None:
    # try:
    # print(os.path.dirname(os.path.realpath(__file__)))
    # print(os.getcwd())
    with (
        open("in/config.json", "r", encoding="utf-8") as config,
        open("in/patched_config.json", "r", encoding="utf-8") as patched,
        open(
            "in/impulse_test_input.xml", "r", encoding="utf-8"
        ) as impulse_test_input_file,
    ):
        (
            config_xml,
            meta_json,
            delta_json,
            res_config_json
        ) = process(
            json.load(config),
            json.load(patched),
            ET.parse(impulse_test_input_file),
        )

        with open("out/config.xml", mode="b+w") as out_file:
            out_file.write(config_xml)
            print("Written to out/config.xml.")

        with open("out/meta.json", mode="w") as out_file:
            out_file.write(meta_json)
            print("Written to out/meta.json.")

        with open("out/delta.json", mode="w") as out_file:
            out_file.write(delta_json)
            print("Written to out/delta.json.")

        with open("out/res_patched_config.json", mode="w") as out_file:
            out_file.write(res_config_json)
            print("Written to out/res_patched_config.json.")

    # except:
    #     print('Got exception.', traceback.format_exc())
    pass


if __name__ == "__main__":
    main()
