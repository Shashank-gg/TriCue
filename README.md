# TriCue — Final Local Snooker Scoreboard

A simple local Flask scoreboard for 2–6 players.

## Rules implemented
- One active player at a time.
- RED -> COLOUR -> RED -> COLOUR while reds remain.
- After the last red, the colours clear in order: Yellow, Green, Brown, Blue, Pink, Black.
- Potting a legal ball keeps the same player's turn.
- MISS / END VISIT passes the turn to the next player while keeping the correct ball on.
- Foul ends the visit and passes the turn.
- Custom house rule: foul penalty is deducted from the player who committed the foul.
- Undo restores the previous action.
- Scores can go negative under the requested foul rule.

## Windows
Double-click `start.bat`. It installs Flask if needed and opens the browser.

## Android / Termux
Run:
```bash
bash start.sh
```
Then open Chrome and go to `http://127.0.0.1:5000`.

Keep Termux running while using the app.
