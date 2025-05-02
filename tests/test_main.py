import json
# import os
import xml.etree.ElementTree as ET

from main import process

# print(os.path.dirname(os.path.realpath(__file__)))
# print(os.getcwd())


def compare_xml_elements_builtin(
        xml1: ET.Element,
        xml2: ET.Element
) -> bool:
    """
    Compare two XML elements recursively (using the
    built-in xml.etree.ElementTree)
    """
    if xml1.tag != xml2.tag:
        return False
    text1: str = xml1.text or ''
    text2: str = xml2.text or ''
    # Ignore cases of "\n   " and None, for example
    if text1.strip() != text2.strip():
        return False
    if xml1.attrib != xml2.attrib:
        return False
    children1 = list(xml1)
    children2 = list(xml2)
    if len(children1) != len(children2):
        return False
    for child1, child2 in zip(children1, children2):
        if not compare_xml_elements_builtin(child1, child2):
            return False
    return True


def test_validate_from_example() -> None:
    p: str = 'tests/payloads/example'
    with (
        # ACTUAL payloads
        open("{}/config.json".format(p), "r", encoding="utf-8") as config,
        open(
            "{}/patched_config.json".format(p),
            "r",
            encoding="utf-8"
        ) as patched,
        open(
            "{}/impulse_test_input.xml".format(p), "r", encoding="utf-8"
        ) as impulse_test_input_file,

        # OUT payloads
        open(
            "{}/config.xml".format(p),
            "r",
            encoding="utf-8"
        ) as expected_config,
        open(
            "{}/meta.json".format(p),
            "r",
            encoding="utf-8"
        ) as expected_meta,
    ):
        (actual_config_contents, actual_meta_contents) = process(
            json.load(patched),
            json.load(config),
            ET.parse(impulse_test_input_file),
        )

        expected_config_xml_contents: str = expected_config.read()
        expected_meta_contents: str = expected_meta.read()

        # Compare config.xml
        actual_config_tree = ET.fromstring(actual_config_contents)
        expected_config_tree = ET.fromstring(expected_config_xml_contents)

        assert compare_xml_elements_builtin(
            expected_config_tree,
            actual_config_tree
        )

        # Compare meta.json
        expected_meta_json = json.loads(expected_meta_contents)
        actual_meta_json = json.loads(actual_meta_contents)

        # Don't check order
        expected_meta_json.sort(key=lambda j: j["class"], reverse=True)
        actual_meta_json.sort(key=lambda j: j["class"], reverse=True)

        assert expected_meta_json == actual_meta_json
