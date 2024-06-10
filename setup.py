"""
SPDX-FileCopyrightText: Copyright (c) 2023 Contributors to COVESA

See the NOTICE file(s) distributed with this work for additional
information regarding copyright ownership.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
SPDX-FileType: SOURCE
SPDX-License-Identifier: Apache-2.0
"""

from setuptools import Extension, setup, find_packages
import os, sys
import pathlib

project_name = 'someip_adapter'

script_directory = os.path.realpath(os.path.dirname(__file__))
is_windows = sys.platform.startswith('win')

# reference: https://setuptools.pypa.io/en/latest/userguide/ext_modules.html
extension_path = os.path.relpath(os.path.join(script_directory, project_name, 'vsomeip_extension'))
vsomeip_extension = Extension('vsomeip_ext',
                      include_dirs=['/usr/local/include/' if not is_windows else os.path.join(pathlib.Path.home().drive, os.sep, 'vsomeip', 'include')],
                      sources=[os.path.join(extension_path, 'vsomeip.cpp')],
                      libraries=['vsomeip3', 'vsomeip3-cfg'],
                      library_dirs=['/usr/local/lib/' if not is_windows else os.path.join(pathlib.Path.home().drive, os.sep, 'vsomeip', 'lib')],
                      extra_compile_args = ['-std=c++14'] if not is_windows else ['-DWIN32', '/std:c++14', '/MD', '/EHsc', '/wd4250'],
                      runtime_library_dirs=['/usr/local/lib/'] if not is_windows else [])

setup(
    name=project_name,
    version='0.9.3',
    python_requires='>=3.8',
    description='',
    author='',
    author_email='',
    data_files=[],
    packages=find_packages(exclude=['**/*.cpp']),
    include_package_data=True,  # see MANIFEST.in
    dependency_links=[],
    install_requires=['scapy'],
    cmdclass={},
    license='LICENSE.txt',
    long_description=open(os.path.join(script_directory, 'README.md')).read(),
    ext_modules=[vsomeip_extension],
)
