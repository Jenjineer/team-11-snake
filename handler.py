"""
Battlesnake for AWS Lambda. Logic ported from Replit main.py.
"""

import base64
import json
import random


def info():
    return {
        "apiversion": "1",
        "author": "Alligator",
        "color": "#800088",
        "head": "default",
        "tail": "default",
        "version": "1.0.0",
    }


def choose_move(state):
    """Return one of: 'up', 'down', 'left', 'right'."""
    try:
        return _move_logic(state)["move"]
    except Exception as e:
        print(f"MOVE ERROR turn {state.get('turn', '?')}: {e}")
        try:
            you = state["you"]
            head = you["body"][0]
            body = {(p["x"], p["y"]) for p in you["body"]}
            w = state["board"]["width"]
            h = state["board"]["height"]
            for m, (x, y) in {
                "up": (head["x"], head["y"] + 1),
                "down": (head["x"], head["y"] - 1),
                "left": (head["x"] - 1, head["y"]),
                "right": (head["x"] + 1, head["y"]),
            }.items():
                if 0 <= x < w and 0 <= y < h and (x, y) not in body:
                    return m
        except Exception:
            pass
        return "down"


def _move_logic(game_state):
    board_width = game_state["board"]["width"]
    board_height = game_state["board"]["height"]
    you = game_state["you"]
    my_head = you["body"][0]
    my_len = len(you["body"])
    my_health = you["health"]
    my_tail = (you["body"][-1]["x"], you["body"][-1]["y"])
    my_head_coord = (my_head["x"], my_head["y"])

    blocked = set()
    for snake in game_state["board"]["snakes"]:
        body = snake["body"]
        ate = snake["health"] == 100
        for i, part in enumerate(body):
            if i == len(body) - 1 and not ate and len(body) > 1:
                continue
            blocked.add((part["x"], part["y"]))

    danger = {}
    for snake in game_state["board"]["snakes"]:
        if snake["id"] == you["id"]:
            continue
        h = snake["body"][0]
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            c = (h["x"] + dx, h["y"] + dy)
            danger[c] = max(danger.get(c, 0), len(snake["body"]))

    def in_bounds(c):
        return 0 <= c[0] < board_width and 0 <= c[1] < board_height

    def flood(start, obstacles):
        seen = {start}
        stack = [start]
        while stack and len(seen) < 121:
            x, y = stack.pop()
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                n = (x + dx, y + dy)
                if in_bounds(n) and n not in obstacles and n not in seen:
                    seen.add(n)
                    stack.append(n)
        return len(seen)

    def can_reach_tail(start, obstacles, tail):
        if start == tail:
            return True
        seen = {start}
        stack = [start]
        while stack:
            x, y = stack.pop()
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                n = (x + dx, y + dy)
                if n == tail:
                    return True
                if in_bounds(n) and n not in obstacles and n not in seen:
                    seen.add(n)
                    stack.append(n)
        return False

    moves = {
        "up": (my_head["x"], my_head["y"] + 1),
        "down": (my_head["x"], my_head["y"] - 1),
        "left": (my_head["x"] - 1, my_head["y"]),
        "right": (my_head["x"] + 1, my_head["y"]),
    }

    biggest = None
    for snake in game_state["board"]["snakes"]:
        if snake["id"] == you["id"]:
            continue
        if biggest is None or len(snake["body"]) > len(biggest["body"]):
            biggest = snake

    contested = set(blocked)
    for coord in danger:
        contested.add(coord)

    food_set = {(f["x"], f["y"]) for f in game_state["board"]["food"]}
    biggest_len = len(biggest["body"]) if biggest else 0
    if my_health < 40 or my_len <= biggest_len:
        food_weight = 3.0
    else:
        food_weight = 1.0

    scored = []
    for m, c in moves.items():
        if not in_bounds(c) or c in blocked:
            continue
        if c in danger and danger[c] >= my_len:
            continue
        space = flood(c, contested)
        if space < my_len * 2:
            space -= 40
        if space <= my_len:
            space -= 60
        score = space
        if c in danger:
            if danger[c] < my_len:
                margin = my_len - danger[c]
                score += 20 + min(margin, 5) * 6
        if biggest is not None and len(biggest["body"]) >= my_len:
            bh = biggest["body"][0]
            dist_to_big = abs(bh["x"] - c[0]) + abs(bh["y"] - c[1])
            if dist_to_big <= 4:
                score -= 30
            elif dist_to_big <= 6:
                score -= 12
        center = (board_width - 1) / 2
        center_y = (board_height - 1) / 2
        dist_center = abs(c[0] - center) + abs(c[1] - center_y)
        score -= dist_center * 1.5
        on_edge = c[0] == 0 or c[0] == board_width - 1 or c[1] == 0 or c[1] == board_height - 1
        big_near = (biggest is not None and len(biggest["body"]) >= my_len
                    and abs(biggest["body"][0]["x"] - c[0]) + abs(biggest["body"][0]["y"] - c[1]) <= 5)
        if food_set and space >= my_len * 2 and not (on_edge and big_near):
            fd = min(abs(fx - c[0]) + abs(fy - c[1]) for (fx, fy) in food_set)
            score -= fd * food_weight
            if (c[0], c[1]) in food_set:
                score += 12
        eating = (c[0], c[1]) in food_set
        if eating:
            if space >= my_len + 2:
                score += 15
            else:
                score -= 50
        else:
            tail_obstacles = blocked | {my_head_coord}
            if can_reach_tail(c, tail_obstacles, my_tail):
                score += 25
            else:
                score -= 50
        scored.append((score, m, c))

    if not scored:
        backups = []
        for m, c in moves.items():
            if in_bounds(c) and c not in blocked:
                risk = danger.get(c, 0)
                backups.append((risk, m))
        if backups:
            backups.sort()
            return {"move": backups[0][1]}
        return {"move": "down"}

    scored.sort(reverse=True)
    best = scored[0][1]
    return {"move": best}


def _response(body, status=200):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "/")

    raw_body = event.get("body") or ""
    if event.get("isBase64Encoded") and raw_body:
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    if method == "GET" and path in ("/", ""):
        return _response(info())
    if method == "POST" and path == "/start":
        return _response({})
    if method == "POST" and path == "/move":
        state = json.loads(raw_body or "{}")
        return _response({"move": choose_move(state)})
    if method == "POST" and path == "/end":
        return _response({})

    return _response({"message": "Not Found"}, 404)
