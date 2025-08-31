apt update
apt install xorg -y
bash /workspace/scripts/blender_install.sh
echo "Done installing. Ready to render with ./render_frame.sh or ./render_anim.sh"
