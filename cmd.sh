#!/bin/sh

: ${BIN:=$HOME/.local/bin/lot}
: ${LM:=$HOME/lot}
: ${PY:=$LM/.venv/bin/python}

mkdir -p $(dirname $BIN)
cat <<EOF > $BIN
#!/bin/sh
$PY $LM/main.py "\$@"
EOF

chmod +x $BIN
