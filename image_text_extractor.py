import os
from dataclasses import dataclass
from typing import Optional, Union, IO


@dataclass
class FileInfo:
    spec_version: str
    image_width: int
    image_height: int
    global_color_table_flag: bool
    color_resolution: int
    sort_flag: bool
    global_color_table_size: int
    background_color_index: int


@dataclass
class GraphicControlExtension:
    data: bytearray


@dataclass
class ImageBlockDescriptor:
    graphic_control: Optional[GraphicControlExtension]
    image_left: int
    image_top: int
    image_width: int
    image_height: int
    local_color_table_flag: bool
    interlace_flag: bool
    sort_flag: bool
    color_table_size: int


class PageFileParser:

    def __init__(self, page_path: str):
        self._page_path: str = page_path
        self._page_file: Optional[IO] = None

        self.file_info: Optional[FileInfo] = None
        self.app_extensions = list()
        self.image_descriptors = list()
        self.station_entry = None
        self._extract_data_from_page()

    @staticmethod
    def _get_bits(bitfield: int, shift: int, bits_amount: int = 1) -> int:
        bitfield = bitfield >> shift
        bitfield = bitfield & ((1 << bits_amount) - 1)
        return bitfield

    @staticmethod
    def _read_uint16(number: bytearray):
        return number[0] + 256 * number[1]

    def _read_next_bytes(self, read_len: int = 1) -> Union[int, bytearray]:
        assert read_len > 0
        assert self._page_file
        data = self._page_file.read(read_len)
        if read_len == 1:
            data = data[0]
        return data

    def _extract_data_from_page(self) -> None:
        with open(self._page_path, "rb") as self._page_file:
            self._parse_intro()

            if self.file_info.global_color_table_flag:
                self._skip_color_table(self.file_info.global_color_table_size)

            block_type = self._read_next_bytes()
            while block_type != 0x3B:
                if block_type == 0x21:
                    self._parse_extension()
                else:
                    assert block_type == 0x2C
                    self._parse_image_block()
                block_type = self._read_next_bytes()

            self._parse_station_entry()
        self._page_file = None

    def _parse_intro(self) -> None:
        page_format = self._read_next_bytes(3)
        assert page_format == b'GIF'

        spec_version_bytes = self._read_next_bytes(3)
        # Why tf is it 87a? 87a is not supposed to support animation?
        assert spec_version_bytes == b'87a' or spec_version_bytes == b'89a'

        width_bytes = self._read_next_bytes(2)
        height_bytes = self._read_next_bytes(2)
        packed_info = self._read_next_bytes()
        background_color_index = self._read_next_bytes()
        pixel_aspect_ratio = self._read_next_bytes()
        # not sure what does it mean
        assert pixel_aspect_ratio == 0

        self.file_info = FileInfo(
            spec_version=spec_version_bytes.decode('ascii'),
            image_width=self._read_uint16(width_bytes),
            image_height=self._read_uint16(height_bytes),
            global_color_table_flag=bool(self._get_bits(packed_info, 7)),
            color_resolution=self._get_bits(packed_info, 4, 3),
            sort_flag=bool(self._get_bits(packed_info, 3)),
            global_color_table_size=2 ** (self._get_bits(packed_info, 0, 3) + 1),
            background_color_index=background_color_index
        )

    def _skip_color_table(self, size: int):
        self._page_file.read(3 * size)

    def _skip_image_data(self):
        code_size = self._read_next_bytes()
        _ = self._read_data_blocks()

    def _parse_extension(self):
        extension_type = self._read_next_bytes()
        if extension_type == 0xF9:
            # Graphics Control Extension
            header_size = self._read_next_bytes()
            extension_data = self._read_next_bytes(header_size)
            terminator = self._read_next_bytes()
            assert terminator == 0
            image_start = self._read_next_bytes()
            assert image_start == 0x2C
            self._parse_image_block(GraphicControlExtension(data=extension_data))
        elif extension_type == 0x01:
            # Plain Text Extension
            raise NotImplemented()
        elif extension_type == 0xFF:
            # Application Extension
            header_size = self._read_next_bytes()
            assert header_size == 0x0B
            app_id = self._read_next_bytes(8).decode('ascii')
            app_code = self._read_next_bytes(3).decode('ascii')
            self.app_extensions.append((app_id, app_code))
            _ = self._read_data_blocks()
        else:
            assert extension_type == 0xFE
            raise NotImplemented()
            # Comment Extension

    def _parse_image_block(self, graphic_control: Optional[GraphicControlExtension] = None):
        image_left_bytes = self._read_next_bytes(2)
        image_top_bytes = self._read_next_bytes(2)
        image_width_bytes = self._read_next_bytes(2)
        image_height_bytes = self._read_next_bytes(2)
        packed_flags = self._read_next_bytes()
        descriptor = ImageBlockDescriptor(
            graphic_control=graphic_control,
            image_left=image_left_bytes[0] + 256 * image_left_bytes[1],
            image_top=image_top_bytes[0] + 256 * image_top_bytes[1],
            image_width=image_width_bytes[0] + 256 * image_width_bytes[1],
            image_height=image_height_bytes[0] + 256 * image_height_bytes[1],
            local_color_table_flag=bool(self._get_bits(packed_flags, 7)),
            interlace_flag=bool(self._get_bits(packed_flags, 6)),
            sort_flag=bool(self._get_bits(packed_flags, 5)),
            color_table_size=2 ** (self._get_bits(packed_flags, 0, 3) + 1)
        )
        self.image_descriptors.append(descriptor)
        if descriptor.local_color_table_flag:
            self._skip_color_table(descriptor.color_table_size)
        self._skip_image_data()

    def _parse_station_entry(self):
        # read the rest of the file
        entry = self._page_file.read()
        if entry:
            self.station_entry = entry.decode('ascii')
        else:
            self.station_entry = "--- NO STATION ENTRY ---"

    def _read_data_blocks(self):
        block_size = self._read_next_bytes()
        data = bytearray()
        while block_size > 0:
            block_data = self._page_file.read(block_size)
            data = data + block_data
            block_size = self._read_next_bytes()
        return data


if __name__ == "__main__":
    for page in os.listdir("pages"):
        print(page)
        parser = PageFileParser(f"pages/{page}")
        print(parser.station_entry)
    print("Done")
