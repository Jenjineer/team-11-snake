# Team 11 Battlesnake

A survival-focused Battlesnake written in Python for the 2026 tech summit
competition. Reached the finals (top 4 of 16 teams).

The snake picks each move by scoring all four possible directions and choosing the
highest. Scoring blends space evaluation, self-trap avoidance, head-to-head logic,
food seeking, and positional bias. A safety wrapper guarantees the snake always
returns a legal move even if the main logic hits an unexpected error.

## Files

There are two versions of the same logic:

- **`main.py`** — Replit / local server version. Entry point is `move(game_state)`,
  returns `{"move": "up"}` (a dict). Runs via `run_server` for local play and
  testing.
- **`handler.py`** — AWS Lambda version. Entry point is `handler(event, context)`,
  which routes the Battlesnake API endpoints and calls `choose_move(state)`,
  returning a bare string like `"up"`. This is the version registered for scored
  competition play.

Both share the identical decision logic in `_move_logic`. The only differences are
the surrounding plumbing (server vs. Lambda handler) and how the result is returned
(dict vs. string).

**Keep the two files in sync.** `_move_logic` is duplicated across `main.py` and
`handler.py`. Any change to the decision logic (scoring, thresholds, new behavior)
must be made in BOTH files, or the snake you test on Replit will not match the one
that competes on Lambda.

## How a move is chosen

On each turn the snake evaluates its four neighbor squares. Any square that is
off-board, on a snake body, or reachable by a longer-or-equal enemy head is
discarded outright. Every surviving square gets a numeric score, and the highest
score wins. If every square is discarded (fully boxed in), a fallback picks the
in-bounds, non-body square with the fewest enemy heads able to reach it.

## Scoring components

Each candidate square's score is built from these pieces:

- **Reachable space (flood fill)** — counts open squares reachable from the
  candidate, up to the full board (121 on an 11x11). More space is better. Squares
  leading into cramped pockets are heavily penalized (a pocket smaller than twice
  the snake's length loses points; one at or below the snake's length loses more),
  because tight space is where snakes trap themselves.
- **Head-to-head avoidance** — squares an enemy head could enter next turn are
  tracked. If that enemy is the same length or longer, the square is discarded (we
  lose or tie-and-both-die). We never voluntarily enter a collision we can't win.
- **Aggression** — if the enemy that could reach the square is strictly shorter, the
  collision is a win for us, so the square gets a bonus scaled by how much longer we
  are (a clear length advantage is rewarded more).
- **Big-snake buffer** — when an enemy at least our length is nearby, squares close
  to its head are penalized (more within 4 squares, less within 6), so we keep our
  distance and avoid being pinned.
- **Center bias** — a gentle pull toward the middle of the board, since edges and
  corners have fewer escape routes and are easier to get trapped against.
- **Food attraction** — pulls the snake toward the nearest food, weighted by need.
  The pull is stronger when health is low or when we are not the biggest snake
  (so we grow enough to win future head-to-heads), and weaker once we are topped up
  and largest. Food attraction is switched off for a square when it leads into
  cramped space, or when the square is on an edge and a bigger snake is near, so
  food never lures the snake into a trap.
- **Tail safety** — the single most important self-trap guard. For a normal move,
  the snake checks it can still trace a path from the candidate square to its own
  tail; if it can, that region stays survivable (the tail keeps vacating ahead of
  it), so the move is rewarded, and if it can't, the move is heavily penalized.
  Because eating grows the snake and its tail does NOT vacate that turn, moves that
  land on food are instead judged on whether they lead into genuinely open space.

## Food logic

Food is handled through the food-attraction and tail-safety scoring above, rather
than a separate "seek food now" mode. The snake eats when it needs to grow or when
food is conveniently on the way through safe space, and it declines food that would
pull it onto an edge near a larger snake or into a pocket it can't escape.

## Safety wrapper

The competition entry point wraps the main logic in a try/except. If anything in the
decision logic raises an error, the wrapper logs it and falls back to the first
in-bounds, non-self square (or `"down"` as a last resort). This means a stray edge
case can never forfeit a game by returning no move or crashing.

## Known weaknesses and future improvements

- **Equal-length head-to-heads** — when two snakes of the same length move into the
  same square, both die, and neither had a winning option. This cost us the final
  match. The snake avoids these when it can, but they are sometimes unavoidable.
- **Being pinned against a wall by a longer snake** — the hardest scenario in the
  game. The center bias and big-snake buffer reduce how often it happens, but do not
  eliminate it.
- **Bad spawn positions** — starting in a corner or next to a stronger snake is
  luck-of-the-draw and hard to code around beyond heading for open space early.

Ideas worth exploring next time:

- **Stronger, deliberate hunting** of snakes we are much larger than, where the
  smaller snake has no realistic chance of catching up in length. The current
  aggression bonus is a step in this direction but could be pushed to actively
  corner and eliminate weaker snakes rather than just accept favorable collisions.
- **Looking more than one move ahead** (a shallow search / minimax) so the snake can
  anticipate an opponent forcing it into an equal-length collision, instead of only
  reacting to the current board.
- **Predicting enemy intent** rather than treating every enemy-head neighbor as
  equally likely, which would tighten both the avoidance and the hunting logic.
