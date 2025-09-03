apt update
apt install nano -y
apt install xorg -y
#curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | bash
pip install dropbox
pip install pandas
bash /workspace/scripts/blender_install.sh
echo ""
echo "Done installing. To download blend files use ./render_download.sh"
echo "Ready to render with ./render_frame.sh or ./render_anim.sh"
