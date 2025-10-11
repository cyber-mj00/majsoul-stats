# Dayaya Majsoul Stats
Majsoul Contest Stats Generator

## Setup
This script is written using Python (Tested working on 3.12).
We recommend that you set up a virtual environment.

To use the script, you need to set up configuration file by changing its name from `config.env.example` to `config.env`, then update the parameters accordingly.

```bash
mv config.env.example config.env
vim config.env
```

You then need to install Python dependencies then run the script.
```bash
pip install -r requirements.txt
py stats.py
```

## Majsoul Tourney Team Adaptation

Please ensure that "Season Type" is set to "**Team**" and "Note" is set to RGB color code for each team, or the script would not work.

## Thanks

https://github.com/oscarfzs/pymjsoul

https://github.com/Longhorn-Riichi/Ronhorn


