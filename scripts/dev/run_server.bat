@echo off
echo Starting the CODESYS API HTTP server...
echo This server WILL connect to CODESYS
echo.
echo Use another command window to test with:
echo python scripts\manual\example_client.py
echo.
echo Press Ctrl+C to stop the server.
python "%~dp0..\\..\\HTTP_SERVER.py"
