from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from copy import deepcopy

app = Flask(__name__)
app.secret_key = "tricue-local-snooker-v2"
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,
)

BALLS = [
    ("RED", 1, "#d92f2f"),
    ("YELLOW", 2, "#d9b62f"),
    ("GREEN", 3, "#26934b"),
    ("BROWN", 4, "#8a522c"),
    ("BLUE", 5, "#3478d8"),
    ("PINK", 6, "#e56b9b"),
    ("BLACK", 7, "#151515"),
]
COLOUR_ORDER = ["YELLOW", "GREEN", "BROWN", "BLUE", "PINK", "BLACK"]
VALUES = {name: value for name, value, _ in BALLS}
STATE_KEYS = ["current_player", "phase", "red_count", "reds_remaining", "reds_potted", "last_red_needs_colour", "colour_index", "break", "best_break"]


def get_game():
    return session.get("game")


def save_game(game):
    session["game"] = game
    session.modified = True


def next_player(game):
    game["current_player"] = (game["current_player"] + 1) % len(game["players"])


def snapshot(game):
    return deepcopy({key: game[key] for key in STATE_KEYS})


def record(game, action, player, before_scores, before):
    game["history"].append({
        "type": action,
        "player": player,
        "before_scores": before_scores,
        "before": before,
    })


@app.route("/", methods=["GET", "POST"])
def setup():
    if request.method == "POST":
        try:
            count = int(request.form.get("player_count", 3))
        except (TypeError, ValueError):
            count = 3
        count = max(2, min(6, count))
        names = []
        for i in range(count):
            name = request.form.get(f"player_{i}", "").strip()
            names.append(name[:24] or f"Player {i + 1}")

        try:
            red_count = int(request.form.get("red_count", 15))
        except (TypeError, ValueError):
            red_count = 15
        red_count = max(1, min(15, red_count))

        game = {
            "players": [{"name": name, "score": 0} for name in names],
            "current_player": 0,
            "phase": "RED",
            "red_count": red_count,
            "reds_remaining": red_count,
            "reds_potted": 0,
            "last_red_needs_colour": False,
            "colour_index": 0,
            "history": [],
            "break": 0,
            "best_break": [0] * count,
            "finished": False,
        }
        save_game(game)
        return redirect(url_for("match"))
    return render_template("setup.html")


@app.route("/match")
def match():
    game = get_game()
    if not game:
        return redirect(url_for("setup"))
    return render_template("match.html", game=game, balls=BALLS)


@app.post("/shot")
def shot():
    game = get_game()
    if not game:
        return jsonify(ok=False, error="No match is running."), 400
    if game.get("finished"):
        return jsonify(ok=False, error="Frame is finished. Start a new match."), 400

    player = game["current_player"]
    kind = request.form.get("kind", "").upper()
    before = snapshot(game)
    before_scores = [p["score"] for p in game["players"]]

    if game["phase"] == "RED":
        if kind != "RED":
            return jsonify(ok=False, error="RED is on. Pot a RED, miss, or record a foul."), 400
        game["players"][player]["score"] += 1
        game["break"] += 1
        game["reds_remaining"] = max(0, game["reds_remaining"] - 1)
        game["reds_potted"] = game.get("red_count", 15) - game["reds_remaining"]
        game["last_red_needs_colour"] = True
        # After a RED, the colour is immediately on. If the player misses it,
        # the next player must inherit this COLOUR state (not RED).
        game["phase"] = "COLOUR"

    elif game["phase"] == "COLOUR":
        if kind not in COLOUR_ORDER:
            return jsonify(ok=False, error="A colour is on after a RED."), 400
        value = VALUES[kind]
        game["players"][player]["score"] += value
        game["break"] += value
        game["last_red_needs_colour"] = False
        if game["reds_remaining"] > 0:
            game["phase"] = "RED"
        else:
            game["phase"] = "CLEARING"
            game["colour_index"] = 0

    elif game["phase"] == "CLEARING":
        expected = COLOUR_ORDER[game["colour_index"]]
        if kind != expected:
            return jsonify(ok=False, error=f"{expected} is on now."), 400
        value = VALUES[kind]
        game["players"][player]["score"] += value
        game["break"] += value
        if game["colour_index"] < len(COLOUR_ORDER) - 1:
            game["colour_index"] += 1
        else:
            game["finished"] = True

    game["best_break"][player] = max(game["best_break"][player], game["break"])
    record(game, "pot", player, before_scores, before)
    save_game(game)
    return jsonify(ok=True, game=game)


@app.post("/turn-end")
def turn_end():
    game = get_game()
    if not game:
        return jsonify(ok=False, error="No match is running."), 400
    if game.get("finished"):
        return jsonify(ok=False, error="Frame is finished."), 400

    player = game["current_player"]
    before = snapshot(game)
    before_scores = [p["score"] for p in game["players"]]
    game["best_break"][player] = max(game["best_break"][player], game["break"])
    game["break"] = 0

    # A MISS ends the current player's visit.
    #
    # IMPORTANT SNOOKER TURN RULE USED BY THIS APP:
    # If a player pots a RED and then misses the following COLOUR, that
    # colour opportunity is lost. The next player starts a fresh visit and
    # RED is on again (while reds remain).
    #
    # If the reds are already finished, the final-red colour remains on;
    # there is no RED to return to. During colour clearing, the current
    # colour remains on after a miss.
    next_player(game)
    if game["phase"] == "COLOUR" and game["reds_remaining"] > 0:
        game["phase"] = "RED"
        game["last_red_needs_colour"] = False
    # Otherwise keep COLOUR/CLEARING as-is.
    record(game, "miss", player, before_scores, before)
    save_game(game)
    return jsonify(ok=True, game=game)


@app.post("/foul")
def foul():
    game = get_game()
    if not game:
        return jsonify(ok=False, error="No match is running."), 400
    if game.get("finished"):
        return jsonify(ok=False, error="Frame is finished."), 400

    offender = game["current_player"]
    try:
        penalty = int(request.form.get("ball", "4"))
    except (TypeError, ValueError):
        penalty = 4
    penalty = max(4, min(7, penalty))

    before = snapshot(game)
    before_scores = [p["score"] for p in game["players"]]

    # User-requested house rule: subtract the foul from the offender.
    game["players"][offender]["score"] -= penalty
    game["best_break"][offender] = max(game["best_break"][offender], game["break"])
    game["break"] = 0

    # User-requested turn rule: ANY foul ends the visit and the next
    # player starts a fresh visit. While reds remain, RED is always on
    # for the next player, even if the foul happened while a colour was on.
    # This means a foul never passes the previous player's colour chance
    # to the next player.
    next_player(game)
    if game["reds_remaining"] > 0:
        game["phase"] = "RED"
        game["last_red_needs_colour"] = False
    # Once all reds are gone, keep the current colour/clearing state.
    record(game, "foul", offender, before_scores, before)
    game["history"][-1]["penalty"] = penalty
    save_game(game)
    return jsonify(ok=True, game=game)


@app.post("/undo")
def undo():
    game = get_game()
    if not game or not game.get("history"):
        return jsonify(ok=False, error="Nothing to undo."), 400

    action = game["history"].pop()
    for i, score in enumerate(action["before_scores"]):
        game["players"][i]["score"] = score
    for key, value in action["before"].items():
        game[key] = value
    game["finished"] = False
    save_game(game)
    return jsonify(ok=True, game=game)


@app.post("/reset")
def reset():
    session.pop("game", None)
    return jsonify(ok=True)


@app.get("/health")
def health():
    return jsonify(ok=True, app="TriCue")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
