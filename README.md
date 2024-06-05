SOMEIP Adpater
===========
## Overview
Python module to leverage someip implementations developed from other programming languages.

## Setup
### Prerequisites

Download, Build, and Install vsomeip - [COVESA / vsomeip](https://github.com/COVESA/vsomeip)
* the same compiler (linux - gcc, windows - msvc) used for vsomip are used to build and package this module.
> [!IMPORTANT]
> for windows support: [COVESA / vsomeip (fork)](https://github.com/justinlhudson/vsomeip)

> [!TIP]
> ###### &nbsp;&nbsp;&nbsp;&nbsp; <ins>Windows</ins>
> * package.sh
>   * helper script to compile and install wheel 
> *  directory tree to place & find the vsomeip install created files:
>      ```
>      ├── <windows home drive> (e.g. 'c:\')
>      │   ├── vsomip
>      │   ├── bin
>      │   ├── include
>      │   ├── lib
>      │   ├── ...
>      ```
> 
> ###### &nbsp;&nbsp;&nbsp;&nbsp; <ins>Linux</ins>
> * package.sh
>   * helper script to compile and install wheel
> * 'error' loading configuration module
>   ```
>   sudo ldconfig
>   ```

## Usage

See 'examples' and 'tests'...

> [!NOTE]
> [COVESA / vsomeip](https://github.com/COVESA/vsomeip) uses configuration files, however those are automatically created as services and clients are launch within this module.  Be sure no other installation of vsomeip environment variables are set in the system.
