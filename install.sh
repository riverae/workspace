apt update
apt install nano -y
apt install xorg -y
pip install configparser
pip install dropbox
pip install pandas
bash /workspace/scripts/blender_install.sh
bash /workspace/scripts/addons_install.sh
cat /workspace/scripts/motionhive.txt
echo "Done installing. To download blend files use ./render_download.sh"
echo "Ready to render with ./render_easystates.sh, ./render_frame.sh or ./render_anim.sh"
