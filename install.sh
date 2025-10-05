apt update
apt install nano -y
apt install xorg -y
apt install zip -y
apt install p7zip-full -y
apt install ffmpeg -y
apt install exiftool -y
curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | bash
apt install speedtest -y
pip install asyncio
pip install aiohttp
pip install configparser
pip install dropbox
pip install pandas
pip install tqdm
bash /workspace/scripts/blender_install.sh
bash /workspace/scripts/addons_install.sh
cat /workspace/scripts/motionhive.txt
echo "Done installing. To download blend files use ./render_download.sh"
echo "Ready to render with ./render_easystates.sh, ./render_frame.sh or ./render_anim.sh"
