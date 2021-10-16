#!/usr/bin/env python
import argparse
import io
import logging

from construct import setglobalfullprinting

from pymp4.parser import Box

log = logging.getLogger(__name__)
setglobalfullprinting(True)


def dump():
    parser = argparse.ArgumentParser(description="Dump all the boxes from an MP4 file")
    parser.add_argument(
        "input_file",
        type=argparse.FileType("rb"),
        metavar="FILE",
        help="Path to the MP4 file to open",
    )

    args = parser.parse_args()

    fd = args.input_file
    fd.seek(0, io.SEEK_END)
    eof = fd.tell()
    fd.seek(0)

    while fd.tell() < eof:
        box = Box.parse_stream(fd)
        print(box)
