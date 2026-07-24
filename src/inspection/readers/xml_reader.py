"""
XML reader.

Profiles XML files and returns a DataProfile.
"""

from pathlib import Path
import xml.etree.ElementTree as ET

from src.common.models.data_profile import DataProfile
from src.inspection.readers.base_reader import BaseReader


class XmlReader(BaseReader):
    """
    Reader responsible for profiling XML files.
    """

    @property
    def supported_extensions(
        self,
    ) -> tuple[str, ...]:

        return (
            ".xml",
        )

    def _build_profile(
        self,
        file_path: Path,
    ) -> DataProfile:
        """
        Build a profile describing one XML file.
        """

        tree = ET.parse(file_path)

        root = tree.getroot()

        element_count = sum(
            1
            for _ in root.iter()
        )

        namespace_count = len(
            {
                element.tag.split("}")[0]
                for element in root.iter()
                if "}" in element.tag
            }
        )

        return DataProfile(
            file_path=file_path,
            file_name=file_path.name,
            extension=file_path.suffix.lower(),
            file_size_bytes=file_path.stat().st_size,
            profile_type="XML",
            inspection_status="Success",
            inspection_message="XML profile created successfully.",
            root_element=root.tag,
            namespace_count=namespace_count,
            additional_metadata={
                "element_count": element_count,
            },
        )