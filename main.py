# Welcome to
# __________         __    __  .__                               __
# \______   \_____ _/  |__/  |_|  |   ____   ______ ____ _____  |  | __ ____
#  |    |  _/\__  \\   __\   __\  | _/ __ \ /  ___//    \\__  \ |  |/ // __ \
#  |    |   \ / __ \|  |  |  | |  |_\  ___/ \___ \|   |  \/ __ \|    <\  ___/
#  |________/(______/__|  |__| |____/\_____>______>___|__(______/__|__\\_____>
#
# This file can be a nice home for your Battlesnake logic and helper functions.
#
# To get you started we've included code to prevent your Battlesnake from moving backwards.
# For more info see docs.battlesnake.com

import random
import typing


# info is called when you create your Battlesnake on play.battlesnake.com
# and controls your Battlesnake's appearance
# TIP: If you open your Battlesnake URL in a browser you should see this data
def info() -> typing.Dict:
    print("INFO")

    return {
        "apiversion": "1",
        "author": "Alligator",  # TODO: Your Battlesnake Username
        "color": "#800088",  # TODO: Choose color
        "head": "default",  # TODO: Choose head
        "tail": "default",  # TODO: Choose tail
    }


# start is called when your Battlesnake begins a game
def start(game_state: typing.Dict):
    print("GAME START")


# end is called when your Battlesnake finishes a game
def end(game_state: typing.Dict):
    print("GAME OVER\n")


# move is called on every turn and returns your next move
# Valid moves are "up", "down", "left", or "right"
# See https://docs.battlesnake.com/api/example-move for available data
def move(game_state: typing.Dict) -> typing.Dict:
    try:
        return _move_logic(game_state)
    except Exception as e:
        print(f"MOVE ERROR turn {game_state.get('turn', '?')}: {e}")
        try:
            you = game_state["you"]
            head = you["body"][0]
            body = {(p["x"], p["y"]) for p in you["body"]}
            w = game_state["board"]["width"]
            h = game_state["board"]["height"]
            for m, (x, y) in {
                "up": (head["x"], head["y"] + 1),
                "down": (head["x"], head["y"] - 1),
                "left": (head["x"] - 1, head["y"]),
                "right": (head["x"] + 1, head["y"]),
            }.items():
                if 0 <= x < w and 0 <= y < h and (x, y) not in body:
                    return {"move": m}
        except Exception:
            pass
        return {"move": "down"}


def _move_logic(game_state: typing.Dict) -> typing.Dict:
    board_width = game_state["board"]["width"]
    board_height = game_state["board"]["height"]
    you = game_state["you"]
    my_head = you["body"][0]
    my_len = len(you["body"])
    my_health = you["health"]
    my_tail = (you["body"][-1]["x"], you["body"][-1]["y"])
    my_head_coord = (my_head["x"], my_head["y"])

    # --- Build the obstacle set: all snake bodies, minus tails that will move.
    blocked = set()
    for snake in game_state["board"]["snakes"]:
        body = snake["body"]
        ate = snake["health"] == 100  # just ate -> tail stays this turn
        for i, part in enumerate(body):
            if i == len(body) - 1 and not ate and len(body) > 1:
                continue  # tail will vacate
            blocked.add((part["x"], part["y"]))

    # --- Squares enemy heads could enter next turn (head-to-head danger).
    danger = {}  # coord -> max enemy length that can reach it
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
        # Count reachable squares from start (bounded to avoid huge cost).
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

    # Find the biggest enemy (for avoidance).
    biggest = None
    for snake in game_state["board"]["snakes"]:
        if snake["id"] == you["id"]:
            continue
        if biggest is None or len(snake["body"]) > len(biggest["body"]):
            biggest = snake

    # Squares enemies will likely occupy next turn (their head-adjacent cells).
    contested = set(blocked)
    for coord in danger:
        contested.add(coord)

    # Set of food coords for quick lookup.
    food_set = {(f["x"], f["y"]) for f in game_state["board"]["food"]}
    # How strongly to chase food this turn.
    biggest_len = len(biggest["body"]) if biggest else 0
    am_biggest = my_len > biggest_len
    if my_health < 40 or my_len <= biggest_len:
        food_weight = 3.0  # want to grow / not starve
    else:
        food_weight = 1.0  # topped up and biggest; eat only if convenient

    scored = []
    for m, c in moves.items():
        if not in_bounds(c) or c in blocked:
            continue
        if c in danger and danger[c] >= my_len:
            continue
        space = flood(c, contested)  # <-- use contested, not blocked
        if space < my_len * 2:
            space -= 40
        if space <= my_len:
            space -= 60
        score = space
        # Aggression: moving into a square a SHORTER enemy head can reach
        # is a kill we win. Reward it, scaled by how clear the win is.
        if c in danger:
            if danger[c] < my_len:
                margin = my_len - danger[c]
                score += 20 + min(margin, 5) * 6  # up to +50 for a clear win

        if biggest is not None and len(biggest["body"]) >= my_len:
            bh = biggest["body"][0]
            dist_to_big = abs(bh["x"] - c[0]) + abs(bh["y"] - c[1])
            if dist_to_big <= 4:
                score -= 30
            elif dist_to_big <= 6:
                score -= 12
        # Gentle pull toward center; walls are traps.
        center = (board_width - 1) / 2
        center_y = (board_height - 1) / 2
        dist_center = abs(c[0] - center) + abs(c[1] - center_y)
        score -= dist_center * 1.5

        # Food attraction: only when this move leads into healthy space,
        # so food can never lure us into a trap.
        on_edge = c[0] == 0 or c[0] == board_width - 1 or c[1] == 0 or c[1] == board_height - 1
        big_near = (biggest is not None and len(biggest["body"]) >= my_len
                    and abs(biggest["body"][0]["x"] - c[0]) + abs(biggest["body"][0]["y"] - c[1]) <= 5)
        if food_set and space >= my_len * 2 and not (on_edge and big_near):
            fd = min(abs(fx - c[0]) + abs(fy - c[1]) for (fx, fy) in food_set)
            score -= fd * food_weight
            if (c[0], c[1]) in food_set:
                score += 12

        # Tail safety: keep a path to our tail so we don't self-trap.
        # BUT if this move eats food, we grow and our tail does NOT vacate,
        # so don't count on that space opening up.
        eating = (c[0], c[1]) in food_set
        if eating:
            # After eating, tail stays; require real open space instead.
            if space >= my_len + 2:
                score += 15
            else:
                score -= 50  # eating here likely traps us
        else:
            tail_obstacles = blocked | {my_head_coord}
            if can_reach_tail(c, tail_obstacles, my_tail):
                score += 25
            else:
                score -= 50
        scored.append((score, m, c))

    if not scored:
        # Everything is dangerous; pick the least-bad in-bounds, non-body move.
        # Prefer squares an enemy head is NOT guaranteed to take.
        backups = []
        for m, c in moves.items():
            if in_bounds(c) and c not in blocked:
                risk = danger.get(c, 0)  # 0 = no enemy head can reach it
                backups.append((risk, m))
        if backups:
            backups.sort()  # lowest risk first
            return {"move": backups[0][1]}
        return {"move": "down"}

    # --- Food logic: eat only when the math demands it.
    scored.sort(reverse=True)
    best = scored[0][1]
    print(f"MOVE {game_state['turn']}: {best}")
    return {"move": best}


# Start server when `python main.py` is run
if __name__ == "__main__":
    from server import run_server

    run_server({"info": info, "start": start, "move": move, "end": end})
