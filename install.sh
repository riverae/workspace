apt update
apt install xorg -y
curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | bash
apt install -y git-lfs
bash /workspace/scripts/blender_install.sh
echo "Done installing. Ready to render with ./render_frame.sh or ./render_anim.sh"
