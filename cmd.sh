#!/bin/sh

mkdir -p $HOME/.local/bin

cat > $HOME/.local/bin/lot <<EOF
#!/bin/sh

python $(pwd -P)/main.py "\$@"

EOF

chmod +x $HOME/.local/bin/lot
