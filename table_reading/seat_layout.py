"""9-max PPPoker seat geometry as fractions of the table crop (experimental).

Derived from real blue-felt table gabaritos (750x1334). Fractions, so they
transfer across crop sizes of the same layout; other table sizes or skins are
NOT yet validated. A nameplate holds a name line and a stack line (XXX,X BB).

The hero is the bottom-centre seat (its cards are face-up); CLOCKWISE lists the
seats in poker action order starting at the hero, for deriving positions from
the dealer button once that is read.
"""

# Nameplate centre as (fx, fy) fractions of the crop, per physical seat.
SEAT_ANCHORS = {
    'hero':      (0.50, 0.90),
    'bot_right': (0.89, 0.765),
    'right_low': (0.90, 0.58),
    'right_up':  (0.89, 0.355),
    'top_right': (0.69, 0.19),
    'top_left':  (0.31, 0.19),
    'left_up':   (0.11, 0.355),
    'left_low':  (0.10, 0.58),
    'bot_left':  (0.11, 0.765),
}

# Clockwise table order starting at the hero (the next seat is to the hero's left).
CLOCKWISE = ['hero', 'bot_right', 'right_low', 'right_up', 'top_right',
             'top_left', 'left_up', 'left_low', 'bot_left']

NAMEPLATE_W = 0.22  # fraction of crop width
NAMEPLATE_H = 0.06  # fraction of crop height

# The avatar sits just above the nameplate; this circular photo is what tells an
# occupied seat from empty blue felt.
AVATAR_DY = 0.075   # how far above the nameplate centre the avatar centre is
AVATAR_W = 0.055    # half-width fraction
AVATAR_H = 0.045    # half-height fraction


def nameplate_box(width, height, seat):
    """Pixel box (x0, y0, x1, y1) of a seat's nameplate within a width x height crop."""
    fx, fy = SEAT_ANCHORS[seat]
    cx, cy = int(fx * width), int(fy * height)
    w2, h2 = int(NAMEPLATE_W * width / 2), int(NAMEPLATE_H * height / 2)
    return max(0, cx - w2), max(0, cy - h2), min(width, cx + w2), min(height, cy + h2)


def avatar_box(width, height, seat):
    """Pixel box (x0, y0, x1, y1) of a seat's avatar within a width x height crop."""
    fx, fy = SEAT_ANCHORS[seat]
    cx, cy = int(fx * width), int((fy - AVATAR_DY) * height)
    w2, h2 = int(AVATAR_W * width), int(AVATAR_H * height)
    return max(0, cx - w2), max(0, cy - h2), min(width, cx + w2), min(height, cy + h2)
