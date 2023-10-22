#!/usr/bin/env python
"""
   Copyright 2016 beardypig

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

import logging
from uuid import UUID

from construct import (
    Adapter,
    Array,
    BitsInteger,
    BitStruct,
    Bytes,
    Const,
    Container,
    CString,
    Default,
    Enum,
    Flag,
    GreedyBytes,
    GreedyRange,
    If,
    IfThenElse,
    Int8ub,
    Int16sb,
    Int16ub,
    Int24ub,
    Int32sb,
    Int32ub,
    Int64ub,
    LazyBound,
    NullTerminated,
    Padding,
    Peek,
    Prefixed,
    PrefixedArray,
    Rebuild,
    Select,
    Struct,
    Subconstruct,
    Switch,
    this,
)
from construct.lib import int2byte

log = logging.getLogger(__name__)

VERSIONS = {0: Int32ub, 1: Int64ub}
UNITY_MATRIX = [0x10000, 0, 0, 0, 0x10000, 0, 0, 0, 0x40000000]

STRING_ENCODING = "utf8"

# Header box

FileTypeBox = Struct(
    "type" / Const(b"ftyp"),
    "major_brand" / Bytes(4),
    "minor_version" / Int32ub,
    "compatible_brands" / GreedyRange(Bytes(4)),
)

SegmentTypeBox = Struct(
    "type" / Const(b"styp"),
    "major_brand" / Bytes(4),
    "minor_version" / Int32ub,
    "compatible_brands" / GreedyRange(Bytes(4)),
)

# Catch find boxes

RawBox = Struct("type" / Bytes(4), "data" / Default(GreedyBytes, b""))

FreeBox = Struct("type" / Const(b"free"), "data" / GreedyBytes)

SkipBox = Struct("type" / Const(b"skip"), "data" / GreedyBytes)

# Movie boxes, contained in a moov Box

MovieHeaderBox = Struct(
    "type" / Const(b"mvhd"),
    "version" / Default(Int8ub, 0),
    "flags" / Default(Int24ub, 0),
    "creation_time" / Switch(this.version, VERSIONS, 0),
    "modification_time" / Switch(this.version, VERSIONS, 0),
    "timescale" / Default(Int32ub, 10000000),
    "duration" / Switch(this.version, VERSIONS),
    "rate" / Default(Int32sb, 65536),
    "volume" / Default(Int16sb, 256),
    # below could be just Padding(10) but why not
    Const(0, Int16ub),
    Const(0, Int32ub),
    Const(0, Int32ub),
    "matrix" / Default(Int32sb[9], UNITY_MATRIX),
    "pre_defined" / Default(Int32ub[6], [0] * 6),
    "next_track_ID" / Default(Int32ub, 0xFFFFFFFF),
)

# Track boxes, contained in trak box

TrackHeaderBox = Struct(
    "type" / Const(b"tkhd"),
    "version" / Default(Int8ub, 0),
    "flags" / Default(Int24ub, 1),
    "creation_time" / Switch(this.version, VERSIONS, 0),
    "modification_time" / Switch(this.version, VERSIONS, 0),
    "track_ID" / Default(Int32ub, 1),
    Padding(4),
    "duration" / Switch(this.version, VERSIONS, 0),
    Padding(8),
    "layer" / Default(Int16sb, 0),
    "alternate_group" / Default(Int16sb, 0),
    "volume" / Default(Int16sb, 0),
    Padding(2),
    "matrix" / Default(Array(9, Int32sb), UNITY_MATRIX),
    "width" / Default(Int32ub, 0),
    "height" / Default(Int32ub, 0),
)

HDSSegmentBox = Struct(
    "type" / Const(b"abst"),
    "version" / Default(Int8ub, 0),
    "flags" / Default(Int24ub, 0),
    "info_version" / Int32ub,
    "attrs" / BitStruct(Padding(1), "profile" / Flag, "live" / Flag, "update" / Flag, Padding(4)),
    "time_scale" / Int32ub,
    "current_media_time" / Int64ub,
    "smpte_time_code_offset" / Int64ub,
    "movie_identifier" / NullTerminated(GreedyBytes),
    "server_entry_table" / PrefixedArray(Int8ub, NullTerminated(GreedyBytes)),
    "quality_entry_table" / PrefixedArray(Int8ub, NullTerminated(GreedyBytes)),
    "drm_data" / NullTerminated(GreedyBytes),
    "metadata" / NullTerminated(GreedyBytes),
    "segment_run_table" / PrefixedArray(Int8ub, LazyBound(lambda: Box)),
    "fragment_run_table" / PrefixedArray(Int8ub, LazyBound(lambda: Box)),
)

HDSSegmentRunBox = Struct(
    "type" / Const(b"asrt"),
    "version" / Default(Int8ub, 0),
    "flags" / Default(Int24ub, 0),
    "quality_entry_table" / PrefixedArray(Int8ub, NullTerminated(GreedyBytes)),
    "segment_run_enteries"
    / PrefixedArray(Int32ub, Struct("first_segment" / Int32ub, "fragments_per_segment" / Int32ub)),
)

HDSFragmentRunBox = Struct(
    "type" / Const(b"afrt"),
    "version" / Default(Int8ub, 0),
    "flags" / BitStruct(Padding(23), "update" / Flag),
    "time_scale" / Int32ub,
    "quality_entry_table" / PrefixedArray(Int8ub, NullTerminated(GreedyBytes)),
    "fragment_run_enteries"
    / PrefixedArray(
        Int32ub,
        Struct(
            "first_fragment" / Int32ub,
            "first_fragment_timestamp" / Int64ub,
            "fragment_duration" / Int32ub,
            "discontinuity" / If(this.fragment_duration == 0, Int8ub),
        ),
    ),
)


# Boxes contained by Media Box


class ISO6392TLanguageCode(Adapter):
    def _decode(self, obj, context, path):
        """
        Get the python representation of the obj
        """
        return b"".join(map(int2byte, [c + 0x60 for c in bytearray(obj)])).decode(STRING_ENCODING)

    def _encode(self, obj, context, path):
        """
        Get the bytes representation of the obj
        """
        return [c - 0x60 for c in bytearray(obj.encode(STRING_ENCODING))]


MediaHeaderBox = Struct(
    "type" / Const(b"mdhd"),
    "version" / Default(Int8ub, 0),
    "flags" / Const(0, Int24ub),
    "creation_time" / Switch(this.version, VERSIONS),
    "modification_time" / Switch(this.version, VERSIONS),
    "timescale" / Int32ub,
    "duration" / Switch(this.version, VERSIONS),
    "language"
    / BitStruct(
        Padding(1),
        "language" / ISO6392TLanguageCode(BitsInteger(5)[3]),
    ),
    Padding(2),
)

HandlerReferenceBox = Struct(
    "type" / Const(b"hdlr"),
    "version" / Const(0, Int8ub),
    "flags" / Const(0, Int24ub),
    Padding(4),
    "handler_type" / Bytes(4),
    Padding(12),  # Int32ub[3]
    "name" / CString(STRING_ENCODING),
)

# Boxes contained by Media Info Box

VideoMediaHeaderBox = Struct(
    "type" / Const(b"vmhd"),
    "version" / Int8ub,
    "flags" / Default(Int24ub, 1),
    "graphics_mode" / Default(Int16ub, 0),
    "opcolor"
    / Struct(
        "red" / Default(Int16ub, 0),
        "green" / Default(Int16ub, 0),
        "blue" / Default(Int16ub, 0),
    ),
)

DataEntryUrlBox = Prefixed(
    Int32ub,
    Struct(
        "type" / Const(b"url "),
        "version" / Const(0, Int8ub),
        "flags" / BitStruct(Padding(23), "self_contained" / Rebuild(Flag, ~this._.location)),
        "location" / If(~this.flags.self_contained, CString(STRING_ENCODING)),
    ),
    includelength=True,
)

DataEntryUrnBox = Prefixed(
    Int32ub,
    Struct(
        "type" / Const(b"urn "),
        "version" / Const(0, Int8ub),
        "flags"
        / BitStruct(
            Padding(23), "self_contained" / Rebuild(Flag, ~(this._.name & this._.location))
        ),
        "name" / If(this.flags == 0, CString(STRING_ENCODING)),
        "location" / If(this.flags == 0, CString(STRING_ENCODING)),
    ),
    includelength=True,
)

DataReferenceBox = Struct(
    "type" / Const(b"dref"),
    "version" / Const(0, Int8ub),
    "flags" / Default(Int24ub, 0),
    "data_entries" / PrefixedArray(Int32ub, Select(DataEntryUrnBox, DataEntryUrlBox)),
)

# Sample Table boxes (stbl)

MP4ASampleEntryBox = Struct(
    "version" / Default(Int16ub, 0),
    "revision" / Const(0, Int16ub),
    "vendor" / Const(0, Int32ub),
    "channels" / Default(Int16ub, 2),
    "bits_per_sample" / Default(Int16ub, 16),
    "compression_id" / Default(Int16sb, 0),
    "packet_size" / Default(Int16ub, 0),
    "sampling_rate" / Int16ub,
    Padding(2),
)

AC3SpecificBox = Struct(
    "type" / Const(b"dac3"),
    "flags" / BitStruct(
        "fscod" / BitsInteger(2),
        "bsid" / BitsInteger(5),
        "bsmod" / BitsInteger(3),
        "acmod" / BitsInteger(3),
        "lfeon" / BitsInteger(1),
        "bit_rate_code" / BitsInteger(5),
        "reserved" / BitsInteger(5),
    )
)


class MaskedInteger(Adapter):
    def _decode(self, obj, context, path):
        return obj & 0x1F

    def _encode(self, obj, context, path):
        return obj & 0x1F


AVCC = Struct(
    "version" / Const(1, Int8ub),
    "profile" / Int8ub,
    "compatibility" / Int8ub,
    "level" / Int8ub,
    "nal"
    / BitStruct(
        Padding(6, pattern=b"\x01"),
        "nal_unit_length_field" / Default(BitsInteger(2), 3),
    ),
    "sps" / Default(PrefixedArray(MaskedInteger(Int8ub), Prefixed(Int16ub, GreedyBytes)), []),
    "pps" / Default(PrefixedArray(Int8ub, Prefixed(Int16ub, GreedyBytes)), []),
)

HVCC = Struct(
    "attrs"
    / Struct(
        "version" / Const(1, Int8ub),
        "flags" / BitStruct(
            "profile_space" / BitsInteger(2),
            "general_tier_flag" / BitsInteger(1),
            "general_profile" / BitsInteger(5),
        ),
        "general_profile_compatibility_flags" / Int32ub,
        # 4 Bytes
        "general_constraint_indicator_flags" / Bytes(6),
        # 6 Bytes
        "general_level" / Int8ub,
        # 1 Byte
        "min_spatial_segmentation" / BitStruct(
            "reserved" / Bytes(4),
            # Padding(4, pattern=b"\xff"),
            "min_spatial_segmentation" / BitsInteger(12),
        ),
        # 2 Bytes
        "parallelism_type" / BitStruct(
            "reserved" / Bytes(6),
            # Padding(6, pattern=b"\xff"),
            "parallelism_type" / BitsInteger(2),
        ),
        # 1 Byte
        "chroma_format_idc" / BitStruct(
            "reserved" / Bytes(6),
            # Padding(6, pattern=b"\xff"),
            "chroma_format_idc" / BitsInteger(2),
        ),
        # 1 Byte
        "bit_depth_luma_minus8" / BitStruct(
            "reserved" / Bytes(5),
            # Padding(5, pattern=b"\xff"),
            "bit_depth_luma_minus8" / BitsInteger(3),
        ),
        # 1 Byte
        "bit_depth_chroma_minus8" / BitStruct(
            "reserved" / Bytes(5),
            # Padding(5, pattern=b"\xff"),
            "bit_depth_chroma_minus8" / BitsInteger(3),
        ),
        # 1 Byte
        "average_frame_rate" / Int16ub,
        # 2 Bytes
        "nalu_flags" / BitStruct(
            "constant_frame_rate" / BitsInteger(2),
            "num_temporal_layers" / BitsInteger(3),
            "temporal_id_nested" / BitsInteger(1),
            "nalu_length_size_minus1" / BitsInteger(2),
        ),
        # 1 Byte
        "num_of_arr_nalus" / Int8ub,
        # 1 Byte
        ###23 bytes
        "arr_nalus"
        / Array(
            this.num_of_arr_nalus,
            Struct(
                "nalu_flags" / BitStruct(
                    "array_completeness" / BitsInteger(1),
                    "reserved" / BitsInteger(1),
                    "nal_unit_type" / BitsInteger(6),
                ),
                "num_nalus" / Int16ub,
                "nalus"
                / Array(
                    this.num_nalus,
                    Struct(
                        "nal_unit_length" / Int16ub,
                        "nal_unit" / Bytes(this.nal_unit_length),
                    ),
                ),
            ),
        ),
    ),
)

PixelAspectRatioBox = Struct("hSpacing" / Int32ub, "vSpacing" / Int32ub)

AVC1SampleEntryBox = Struct(
    "version" / Default(Int16ub, 0),
    "revision" / Const(0, Int16ub),
    "vendor" / Default(Bytes(4), b"brdy"),
    "temporal_quality" / Default(Int32ub, 0),
    "spatial_quality" / Default(Int32ub, 0),
    "width" / Int16ub,
    "height" / Int16ub,
    "horizontal_resolution" / Default(Int16ub, 72),  # TODO: actually a fixed point decimal
    Padding(2),
    "vertical_resolution" / Default(Int16ub, 72),  # TODO: actually a fixed point decimal
    Padding(2),
    "data_size" / Const(0, Int32ub),
    "frame_count" / Default(Int16ub, 1),
    "compressor_name" / Default(Bytes(32), b""),
    "depth" / Default(Int16ub, 24),
    "color_table_id" / Default(Int16sb, -1),
    "avc_data"
    / Prefixed(
        Int32ub,
        Struct(
            "type" / Bytes(4),
            "box_body"
            / Switch(
                this.type,
                {
                    b"avcC": AVCC,
                    b"hvcC": HVCC,
                    b"pasp": PixelAspectRatioBox,
                },
            ),
        ),
        includelength=True,
    ),
)

SampleEntryBox = Prefixed(
    Int32ub,
    Struct(
        "type" / Bytes(4),
        Padding(6),
        "data_reference_index" / Default(Int16ub, 1),
        "sample_entry_box"
        / Switch(
            this.type,
            {   
                b"ec-3": MP4ASampleEntryBox,
                b"mp4a": MP4ASampleEntryBox,
                b"enca": MP4ASampleEntryBox,
                b"hvc1": AVC1SampleEntryBox,
                b"avc1": AVC1SampleEntryBox,
                b"encv": AVC1SampleEntryBox,
            },
            Struct("data" / GreedyBytes),
        ),
        "children" / LazyBound(lambda: GreedyRange(Box)),
    ),
    includelength=True,
)

BitRateBox = Struct(
    "type" / Const(b"btrt"),
    "bufferSizeDB" / Int32ub,
    "maxBitrate" / Int32ub,
    "avgBirate" / Int32ub,
)

SampleDescriptionBox = Struct(
    "type" / Const(b"stsd"),
    "version" / Default(Int8ub, 0),
    "flags" / Const(0, Int24ub),
    "children" / PrefixedArray(Int32ub, SampleEntryBox),  # entries
)

SampleSizeBox = Struct(
    "type" / Const(b"stsz"),
    "version" / Int8ub,
    "flags" / Const(0, Int24ub),
    "sample_size" / Int32ub,
    "sample_count" / Int32ub,
    "entry_sizes" / If(this.sample_size == 0, Array(this.sample_count, Int32ub)),
)

SampleSizeBox2 = Struct(
    "type" / Const(b"stz2"),
    "version" / Int8ub,
    "flags" / Const(0, Int24ub),
    Padding(3),
    "field_size" / Int8ub,
    "sample_count" / Int24ub,
    # "entries"
    # / Array(
    #     this.sample_count,
    #     Struct("entry_size" / LazyBound(lambda ctx: globals()["Int%dub" % ctx.field_size])),
    # ),
)

SampleDegradationPriorityBox = Struct(
    "type" / Const(b"stdp"),
    "version" / Const(0, Int8ub),
    "flags" / Const(0, Int24ub),
)

TimeToSampleBox = Struct(
    "type" / Const(b"stts"),
    "version" / Const(0, Int8ub),
    "flags" / Const(0, Int24ub),
    "entries"
    / Default(
        PrefixedArray(
            Int32ub,
            Struct(
                "sample_count" / Int32ub,
                "sample_delta" / Int32ub,
            ),
        ),
        [],
    ),
)

SyncSampleBox = Struct(
    "type" / Const(b"stss"),
    "version" / Const(0, Int8ub),
    "flags" / Const(0, Int24ub),
    "entries"
    / Default(
        PrefixedArray(
            Int32ub,
            Struct(
                "sample_number" / Int32ub,
            ),
        ),
        [],
    ),
)

SampleToChunkBox = Struct(
    "type" / Const(b"stsc"),
    "version" / Const(0, Int8ub),
    "flags" / Const(0, Int24ub),
    "entries"
    / Default(
        PrefixedArray(
            Int32ub,
            Struct(
                "first_chunk" / Int32ub,
                "samples_per_chunk" / Int32ub,
                "sample_description_index" / Int32ub,
            ),
        ),
        [],
    ),
)

ChunkOffsetBox = Struct(
    "type" / Const(b"stco"),
    "version" / Const(0, Int8ub),
    "flags" / Const(0, Int24ub),
    "entries"
    / Default(
        PrefixedArray(
            Int32ub,
            Struct(
                "chunk_offset" / Int32ub,
            ),
        ),
        [],
    ),
)

ChunkLargeOffsetBox = Struct(
    "type" / Const(b"co64"),
    "version" / Const(0, Int8ub),
    "flags" / Const(0, Int24ub),
    "entries"
    / PrefixedArray(
        Int32ub,
        Struct(
            "chunk_offset" / Int64ub,
        ),
    ),
)

# Movie Fragment boxes, contained in moof box

MovieFragmentHeaderBox = Struct(
    "type" / Const(b"mfhd"),
    "version" / Const(0, Int8ub),
    "flags" / Const(0, Int24ub),
    "sequence_number" / Int32ub,
)

TrackFragmentBaseMediaDecodeTimeBox = Struct(
    "type" / Const(b"tfdt"),
    "version" / Int8ub,
    "flags" / Const(0, Int24ub),
    "baseMediaDecodeTime" / Switch(this.version, VERSIONS),
)

TrackSampleFlags = BitStruct(
    Padding(4),
    "is_leading"
    / Default(Enum(BitsInteger(2), UNKNOWN=0, LEADINGDEP=1, NOTLEADING=2, LEADINGNODEP=3), 0),
    "sample_depends_on"
    / Default(Enum(BitsInteger(2), UNKNOWN=0, DEPENDS=1, NOTDEPENDS=2, RESERVED=3), 0),
    "sample_is_depended_on"
    / Default(Enum(BitsInteger(2), UNKNOWN=0, NOTDISPOSABLE=1, DISPOSABLE=2, RESERVED=3), 0),
    "sample_has_redundancy"
    / Default(Enum(BitsInteger(2), UNKNOWN=0, REDUNDANT=1, NOTREDUNDANT=2, RESERVED=3), 0),
    "sample_padding_value" / Default(BitsInteger(3), 0),
    "sample_is_non_sync_sample" / Default(Flag, False),
    "sample_degradation_priority" / Default(BitsInteger(16), 0),
)

TrackRunBox = Struct(
    "type" / Const(b"trun"),
    "version" / Int8ub,
    "flags"
    / BitStruct(
        Padding(12),
        "sample_composition_time_offsets_present" / Flag,
        "sample_flags_present" / Flag,
        "sample_size_present" / Flag,
        "sample_duration_present" / Flag,
        Padding(5),
        "first_sample_flags_present" / Flag,
        Padding(1),
        "data_offset_present" / Flag,
    ),
    "sample_count" / Int32ub,
    "data_offset" / If(this.flags.data_offset_present, Int32sb),
    "first_sample_flags" / If(this.flags.first_sample_flags_present, Int32ub),
    "sample_info"
    / Array(
        this.sample_count,
        Struct(
            "sample_duration" / If(this._.flags.sample_duration_present, Int32ub),
            "sample_size" / If(this._.flags.sample_size_present, Int32ub),
            "sample_flags" / If(this._.flags.sample_flags_present, TrackSampleFlags),
            "sample_composition_time_offsets"
            / If(
                this._.flags.sample_composition_time_offsets_present,
                Switch(this._.version, {0: Int32ub, 1: Int32sb}),
            ),
        ),
    ),
)

TrackFragmentHeaderBox = Struct(
    "type" / Const(b"tfhd"),
    "version" / Int8ub,
    "flags"
    / BitStruct(
        Padding(6),
        "default_base_is_moof" / Flag,
        "duration_is_empty" / Flag,
        Padding(10),
        "default_sample_flags_present" / Flag,
        "default_sample_size_present" / Flag,
        "default_sample_duration_present" / Flag,
        Padding(1),
        "sample_description_index_present" / Flag,
        "base_data_offset_present" / Flag,
    ),
    "track_ID" / Int32ub,
    "base_data_offset" / If(this.flags.base_data_offset_present, Int64ub),
    "sample_description_index" / If(this.flags.sample_description_index_present, Int32ub),
    "default_sample_duration" / If(this.flags.default_sample_duration_present, Int32ub),
    "default_sample_size" / If(this.flags.default_sample_size_present, Int32ub),
    "default_sample_flags" / If(this.flags.default_sample_flags_present, TrackSampleFlags),
)

MovieExtendsHeaderBox = Struct(
    "type" / Const(b"mehd"),
    "version" / Default(Int8ub, 0),
    "flags" / Const(0, Int24ub),
    "fragment_duration" / Switch(this.version, VERSIONS, 0),
)

TrackExtendsBox = Struct(
    "type" / Const(b"trex"),
    "version" / Const(0, Int8ub),
    "flags" / Const(0, Int24ub),
    "track_ID" / Int32ub,
    "default_sample_description_index" / Default(Int32ub, 1),
    "default_sample_duration" / Default(Int32ub, 0),
    "default_sample_size" / Default(Int32ub, 0),
    "default_sample_flags" / Default(TrackSampleFlags, Container()),
)

SegmentIndexBox = Struct(
    "type" / Const(b"sidx"),
    "version" / Int8ub,
    "flags" / Const(0, Int24ub),
    "reference_ID" / Int32ub,
    "timescale" / Int32ub,
    "earliest_presentation_time" / Switch(this.version, VERSIONS),
    "first_offset" / Switch(this.version, VERSIONS),
    Padding(2),
    "reference_count" / Int16ub,
    "references"
    / Array(
        this.reference_count,
        BitStruct(
            "reference_type" / Enum(BitsInteger(1), INDEX=1, MEDIA=0),
            "referenced_size" / BitsInteger(31),
            "segment_duration" / BitsInteger(32),
            "starts_with_SAP" / Flag,
            "SAP_type" / BitsInteger(3),
            "SAP_delta_time" / BitsInteger(28),
        ),
    ),
)

SampleAuxiliaryInformationSizesBox = Struct(
    "type" / Const(b"saiz"),
    "version" / Const(0, Int8ub),
    "flags"
    / BitStruct(
        Padding(23),
        "has_aux_info_type" / Flag,
    ),
    # Optional fields
    "aux_info_type" / If(this.flags.has_aux_info_type, Bytes(4)),
    "aux_info_type_parameter" / If(this.flags.has_aux_info_type, Int32ub),
    "default_sample_info_size" / Int8ub,
    "sample_count" / Int32ub,
    # only if sample default_sample_info_size is 0
    "sample_info_sizes" / If(this.default_sample_info_size == 0, Array(this.sample_count, Int8ub)),
)

SampleAuxiliaryInformationOffsetsBox = Struct(
    "type" / Const(b"saio"),
    "version" / Int8ub,
    "flags"
    / BitStruct(
        Padding(23),
        "has_aux_info_type" / Flag,
    ),
    # Optional fields
    "aux_info_type" / If(this.flags.has_aux_info_type, Bytes(4)),
    "aux_info_type_parameter" / If(this.flags.has_aux_info_type, Int32ub),
    # Short offsets in version 0, long in version 1
    "offsets" / PrefixedArray(Int32ub, Switch(this._.version, VERSIONS)),
)

# Movie data box

MovieDataBox = Struct(b"type" / Const(b"mdat"), "data" / GreedyBytes)

# Media Info Box

SoundMediaHeaderBox = Struct(
    "type" / Const(b"smhd"),
    "version" / Const(0, Int8ub),
    "flags" / Const(0, Int24ub),
    "balance" / Default(Int16sb, 0),
    "reserved" / Const(0, Int16ub),
)


# DASH Boxes


class UUIDBytes(Adapter):
    def _decode(self, obj, context, path):
        return UUID(bytes=obj)

    def _encode(self, obj, context, path):
        return obj.bytes


ProtectionSystemHeaderBox = Struct(
    "type" / If(this._.type != b"uuid", Const(b"pssh")),
    "version" / Rebuild(Int8ub, lambda ctx: 1 if (hasattr(ctx, "key_IDs") and ctx.key_IDs) else 0),
    "flags" / Const(0, Int24ub),
    "system_ID" / UUIDBytes(Bytes(16)),
    "key_IDs" / If(this.version == 1, PrefixedArray(Int32ub, UUIDBytes(Bytes(16)))),
    "init_data" / Prefixed(Int32ub, GreedyBytes),
)

TrackEncryptionBox = Struct(
    "type" / If(this._.type != b"uuid", Const(b"tenc")),
    "version" / Const(0, Int8ub),
    "flags" / Const(0, Int24ub),
    "is_encrypted" / Int24ub,
    "iv_size" / Int8ub,
    "key_ID" / UUIDBytes(Bytes(16)),
)

SampleEncryptionBox = Struct(
    "type" / If(this._.type != b"uuid", Const(b"senc")),
    "version" / Const(0, Int8ub),
    "flags" / BitStruct(Padding(22), "has_subsample_encryption_info" / Flag, Padding(1)),
    "sample_encryption_info"
    / PrefixedArray(
        Int32ub,
        Struct(
            "iv" / Bytes(8),
            # include the sub sample encryption information
            "subsample_encryption_info"
            / If(
                this._._.flags.has_subsample_encryption_info,
                PrefixedArray(Int16ub, Struct("clear_bytes" / Int16ub, "cipher_bytes" / Int32ub)),
            ),
        ),
    ),
)

SampleToGroupBox = Struct(
    "type" / Const(b"sbgp"),
    "version" / Int8ub,
    "flags" / Const(0, Int24ub),
    "grouping_type" / Bytes(4),
    "grouping_type_parameter" / If(this.version == 1, Int32ub),
    "entry_count" / Int32ub,
    "entries"
    / Array(
       this.entry_count,
       Struct(
           "sample_count" / Int32ub,
           "group_description_index" / Int32ub
       ),
    ),
)

SampleGroupDescriptionBox = Struct(
     "type" / Const(b"sgpd"),
     "version" / Int8ub,
     "flags" / Int24ub,
     "grouping_type" / Bytes(4),
     "default_length" / IfThenElse(this.version == 1, Int32ub, 0),
     "default_group_description_index" / If(this.version >= 2, Int32ub),
     "entry_count" / Int32ub,
     "entries"
    / Array(
       this.entry_count,
       Struct(
           "is_encrypted" / Int24ub,
           "iv_size" / Int8ub,
           "key_ID" / UUIDBytes(Bytes(16)),
       ),
    ),
)

OriginalFormatBox = Struct(
    "type" / Const(b"frma"),
    "original_format" / Default(Bytes(4), b"avc1"),
)

SchemeTypeBox = Struct(
    "type" / Const(b"schm"),
    "schema_uri" / Default(Bytes(4), b""),
    "scheme_type" / Default(Bytes(4), b"cenc"),
    "scheme_version" / Int32ub,
)

# PIFF boxes

UUIDBox = Struct(
    "type" / Const(b"uuid"),
    "extended_type" / UUIDBytes(Bytes(16)),
    "data"
    / Switch(
        this.extended_type,
        {
            UUID("A2394F52-5A9B-4F14-A244-6C427C648DF4"): SampleEncryptionBox,
            UUID("D08A4F18-10F3-4A82-B6C8-32D8ABA183D3"): ProtectionSystemHeaderBox,
            UUID("8974DBCE-7BE7-4C51-84F9-7148F9882554"): TrackEncryptionBox,
        },
        GreedyBytes,
    ),
)

ContainerBoxLazy = LazyBound(lambda: ContainerBox)


class TellPlusSizeOf(Subconstruct):
    def __init__(self, subcon):
        super().__init__(subcon)
        self.flagbuildnone = True

    def _parse(self, stream, context, path):
        return stream.tell() + self.subcon.sizeof(context=context)

    def _build(self, obj, stream, context, path):
        return b""

    def sizeof(self, context=None, **kw):
        return 0


Box = Prefixed(
    Int32ub,
    Struct(
        "type" / Peek(Bytes(4)),
        "box_body"
        / Switch(
            this.type,
            {
                b"ftyp": FileTypeBox,
                b"styp": SegmentTypeBox,
                b"mvhd": MovieHeaderBox,
                b"moov": ContainerBoxLazy,
                b"moof": ContainerBoxLazy,
                b"mfhd": MovieFragmentHeaderBox,
                b"tfdt": TrackFragmentBaseMediaDecodeTimeBox,
                b"trun": TrackRunBox,
                b"tfhd": TrackFragmentHeaderBox,
                b"traf": ContainerBoxLazy,
                b"mvex": ContainerBoxLazy,
                b"mehd": MovieExtendsHeaderBox,
                b"trex": TrackExtendsBox,
                b"trak": ContainerBoxLazy,
                b"mdia": ContainerBoxLazy,
                b"tkhd": TrackHeaderBox,
                b"mdat": MovieDataBox,
                b"free": FreeBox,
                b"skip": SkipBox,
                b"mdhd": MediaHeaderBox,
                b"hdlr": HandlerReferenceBox,
                b"minf": ContainerBoxLazy,
                b"vmhd": VideoMediaHeaderBox,
                b"dinf": ContainerBoxLazy,
                b"dref": DataReferenceBox,
                b"stbl": ContainerBoxLazy,
                b"stsd": SampleDescriptionBox,
                b"stsz": SampleSizeBox,
                # b"stz2": SampleSizeBox2,
                b"stts": TimeToSampleBox,
                b"stss": SyncSampleBox,
                b"stsc": SampleToChunkBox,
                b"stco": ChunkOffsetBox,
                b"co64": ChunkLargeOffsetBox,
                b"smhd": SoundMediaHeaderBox,
                b"sidx": SegmentIndexBox,
                b"saiz": SampleAuxiliaryInformationSizesBox,
                b"saio": SampleAuxiliaryInformationOffsetsBox,
                b"btrt": BitRateBox,
                b"dac3": AC3SpecificBox,
                # dash
                b"tenc": TrackEncryptionBox,
                b"pssh": ProtectionSystemHeaderBox,
                b"senc": SampleEncryptionBox,
                b"sinf": ContainerBoxLazy,
                b"frma": OriginalFormatBox,
                b"schm": SchemeTypeBox,
                b"schi": ContainerBoxLazy,
                b"sbgp": SampleToGroupBox,
                b"sgpd": SampleGroupDescriptionBox,
                # piff
                b"uuid": UUIDBox,
                # HDS boxes
                b"abst": HDSSegmentBox,
                b"asrt": HDSSegmentRunBox,
                b"afrt": HDSFragmentRunBox,
            },
            RawBox,
        ),
        "length" / TellPlusSizeOf(Int32ub),
    ),
    includelength=True,
)

ContainerBox = Struct("type" / Bytes(4), "children" / GreedyRange(Box))

MP4 = GreedyRange(Box)
