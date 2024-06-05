@ECHO OFF

rmdir /s /q .\build
rmdir /s /q .\dist
for /d %%i in (*.egg-info) do rd /s /q %%i

python .\setup.py build
python .\setup.py uninstall
python .\setup.py install --force
python .\setup.py bdist_wheel --python-tag=py3

cd .\dist
::for /r %%i in (*.egg) do wheel convert %%i
