import json
# import traceback
import xml.etree.ElementTree as ET


def build_xml_root_child_attributes(
    current_child: ET.Element, root: ET.Element
) -> None:
    for child in current_child:
        tag: str = child.tag
        if tag != "Attribute":
            continue

        child_attrib: dict[str, str] = child.attrib
        attribute_name: str = child_attrib.get("name") or ""
        attribute_type: str = child_attrib.get("type") or ""

        if attribute_name == "":
            continue

        attribute = ET.SubElement(root, attribute_name)
        attribute.text = attribute_type


def build_xml(root_tree: ET.Element) -> None:
    new_root: ET.Element | None = None
    new_classes_dict: dict[str, ET.Element] = dict()
    classes_list: list[ET.Element] = []
    aggregation_list: list[ET.Element] = []

    # Find all tags with Classes and Aggregations
    # Put items to lists again to avoid incorrect XML-order
    for child in root_tree:
        # print(child.tag, child.attrib)
        tag = child.tag
        if tag == "Class":
            classes_list.append(child)
            # classes_dict[child.attrib.get('name') or '_'] = child
        elif tag == "Aggregation":
            aggregation_list.append(child)

    # Process Classes
    # for key, class_child in classes_dict.items():
    for class_child in classes_list:
        attrib: dict[str, str] = class_child.attrib
        class_name: str = attrib.get("name") or "_"
        isRoot: bool = attrib.get("isRoot") == "true"

        if class_name not in new_classes_dict:
            e = ET.Element(class_name)
            new_classes_dict[class_name] = e

            if isRoot and new_root is None:
                new_root = e

            build_xml_root_child_attributes(class_child, e)
        else:
            print("Warning! Got duplication.", class_child)

    if new_root is None:
        print("No root found for XML.")
        return

    print("Built base.")
    # ET.dump(new_root)

    # Process Aggregations
    for aggregation_child in aggregation_list:
        source: str = aggregation_child.get("source") or ""
        target: str = aggregation_child.get("target") or ""

        if source == "" or target == "":
            continue

        if source not in new_classes_dict or target not in new_classes_dict:
            continue

        new_classes_dict[target].append(new_classes_dict[source])

    print("Built connections.")

    rough_xml_contents: bytes = ET.tostring(
        new_root,
        encoding="utf-8",
        # Example file elements are not shortened
        short_empty_elements=False,
    )
    # TODO: prettify and use short empty elements
    # parsed = minidom.parseString(rough_xml_contents)
    with open("out/config.xml", mode="b+w") as out_file:
        out_file.write(rough_xml_contents)
        # out_file.write(parsed.toprettyxml(indent="\t"))
        print("Written to out/config.xml.")


def process(
    patched_config: dict[str, int],
    config: dict[str, int],
    impulse_test_input_tree: ET.ElementTree,
) -> None:
    build_xml(impulse_test_input_tree.getroot())


def main() -> None:
    # try:
    with (
        open("in/config.json", "r", encoding="utf-8") as config,
        open("in/patched_config.json", "r", encoding="utf-8") as patched,
        open(
            "in/impulse_test_input.xml", "r", encoding="utf-8"
        ) as impulse_test_input_file,
    ):
        process(
            json.load(patched),
            json.load(config),
            ET.parse(impulse_test_input_file),
        )
    # except:
    #     print('Got exception.', traceback.format_exc())
    pass


if __name__ == "__main__":
    main()
