@echo off
echo Run this as Administrator (right-click - Run as administrator)
netsh advfirewall firewall add rule name="CryptoApp Backend 8000" dir=in action=allow protocol=TCP localport=8000
echo Done. Try phone browser: http://192.168.0.2:8000/health
pause
