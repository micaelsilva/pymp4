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

import sys
from pathlib import Path

from setuptools import find_packages, setup

sys.path.insert(0, str(Path(__file__).parent / "src"))

deps = ["construct~=2.10.67"]

setup(
    name="pymp4",
    version="1.4.5",
    description="A Python parser for MP4 boxes",
    url="https://github.com/beardypig/pymp4",
    author="beardypig",
    author_email="git@beardypig.com",
    license="Apache 2.0",
    packages=find_packages("src"),
    package_dir={"": "src"},
    python_requires=">=3.6",
    entry_points={"console_scripts": ["mp4dump=pymp4.cli:dump"]},
    install_requires=deps,
    test_suite="tests",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Multimedia :: Video",
        "Topic :: Utilities",
    ],
)
