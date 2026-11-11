"""Build the profile's activity SVGs from public GitHub data."""
import argparse
from collections import Counter
from datetime import date, timedelta
from heapq import heappop, heappush
from html import escape
from html.parser import HTMLParser
import json
from math import dist
from pathlib import Path
from random import Random
from urllib.request import Request, urlopen

OWNER = "c2451134117-cyber"
PROJECTS = ("physics-lab-preexam", "douyin-fire-helper")
ASSETS = Path(__file__).resolve().parents[1] / "assets"
API = "https://api.github.com"
FONT = "system-ui, -apple-system, sans-serif"
LANGUAGE_COLORS = {"JavaScript": "#e6b945", "HTML": "#e87151", "CSS": "#a18ce5", "Other": "#8392a3"}
TRAVEL_FRACTION = 0.92


def fetch(url):
    request = Request(url, headers={"User-Agent": f"{OWNER}-profile-assets"})
    with urlopen(request, timeout=25) as response:
        return response.read().decode()


class Calendar(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.days = {}
        self.feed(html)
        self.close()
        days = sorted(self.days)
        if not 364 <= len(days) <= 372 or (days[-1] - days[0]).days != len(days) - 1:
            raise ValueError("GitHub contribution calendar is incomplete")
        if abs((date.today() - days[-1]).days) > 2:
            raise ValueError("GitHub contribution calendar is out of date")

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "td" and {"data-date", "data-level"} <= attrs.keys():
            day = date.fromisoformat(attrs["data-date"])
            level = int(attrs["data-level"])
            if not 0 <= level <= 4 or day in self.days:
                raise ValueError("Unexpected contribution calendar cell")
            self.days[day] = level


def load_activity(snapshot):
    if snapshot:
        profile = json.loads((snapshot / "user.json").read_text())
        repos = {repo["name"]: repo for repo in json.loads((snapshot / "repos.json").read_text())}
        project_data = [(repos[name], json.loads((snapshot / f"{name}-languages").read_text())) for name in PROJECTS]
        calendar = (snapshot / "calendar").read_text()
    else:
        profile = json.loads(fetch(f"{API}/users/{OWNER}"))
        project_data = []
        for name in PROJECTS:
            url = f"{API}/repos/{OWNER}/{name}"
            project_data.append((json.loads(fetch(url)), json.loads(fetch(f"{url}/languages"))))
        calendar = fetch(f"https://github.com/users/{OWNER}/contributions")

    languages = Counter()
    stars = forks = 0
    for (repo, breakdown), name in zip(project_data, PROJECTS):
        if repo["private"] or repo["full_name"] != f"{OWNER}/{name}":
            raise ValueError(f"{name} is no longer a public project of {OWNER}")
        stars += repo["stargazers_count"]
        forks += repo["forks_count"]
        languages.update(breakdown)
    return (stars, forks, profile["followers"]), languages, Calendar(calendar).days


def svg(width, height, title, content, description=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">\n'
        f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description or title)}</desc>\n'
        f'{content}\n</svg>\n'
    )


def card(title, subtitle, content, description):
    return svg(348, 153, title, f"""
<style>
  svg {{ --bg: #f6f9fc; --line: #cfdae7; --ink: #152840; --muted: #465c75; --accent: #11695c }}
  @media (prefers-color-scheme: dark) {{
    svg {{ --bg: #101e2e; --line: #344b63; --ink: #edf4ff; --muted: #a4b9d1; --accent: #82e5d1 }}
  }}
</style>
<rect x=".5" y=".5" width="347" height="152" rx="13" fill="var(--bg)" stroke="var(--line)"/>
<g font-family="{FONT}">
  <path d="M20 23h12" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round"/>
  <text x="42" y="28" font-size="12" font-weight="700" letter-spacing="1" fill="var(--accent)">{title}</text>
  <text x="20" y="51" font-size="12" fill="var(--muted)">{subtitle}</text>
  {content}
</g>""", description)


def stats_card(totals):
    labels = ("Stars", "Forks", "Followers")
    items = []
    for x, value, label in zip((20, 126, 232), totals, labels):
        items.append(f'<text x="{x}" y="105" font-size="29" font-weight="700" fill="var(--ink)">{value:,}</text>')
        items.append(f'<text x="{x}" y="126" font-size="12" fill="var(--muted)">{label}</text>')
    divider = '<path d="M20 66h308M111 82v48M217 82v48" stroke="var(--line)"/>'
    description = ", ".join(f"{value} {label.lower()}" for label, value in zip(labels, totals))
    return card("GITHUB STATS", f"{len(PROJECTS)} featured repos · GitHub profile", divider + "\n".join(items), description)


def language_card(languages):
    total = sum(languages.values())
    if not total:
        message = "No language data"
        return card("LANGUAGES", "Featured repos · GitHub Linguist bytes",
                    f'<text x="20" y="99" font-size="15" fill="var(--ink)">{message}</text>', message)

    ranked = languages.most_common()
    if len(ranked) > 4:
        ranked = ranked[:3] + [("Other", sum(size for _, size in ranked[3:]))]
    items = ['<clipPath id="bar"><rect x="20" y="69" width="308" height="12" rx="6"/></clipPath>']
    labels = []
    x = 20
    for index, (language, size) in enumerate(ranked):
        color = LANGUAGE_COLORS.get(language, ("#4ac5b2", "#779ef2", "#e78fbc", "#8392a3")[index])
        width = 308 * size / total
        items.append(f'<rect clip-path="url(#bar)" x="{x:.4f}" y="69" width="{width:.4f}" height="12" fill="{color}"/>')
        x += width
        row, column = divmod(index, 2)
        label_x, label_y = 20 + 157 * column, 107 + 21 * row
        label = f"{language} {size / total:.1%}"
        labels.append(label)
        items.append(f'<circle cx="{label_x + 4}" cy="{label_y - 4}" r="4" fill="{color}"/>')
        items.append(f'<text x="{label_x + 14}" y="{label_y}" font-size="12" fill="var(--ink)">{escape(label)}</text>')
    return card("LANGUAGES", "Featured repos · GitHub Linguist bytes", "\n".join(items), ", ".join(labels))


def grid_distance(start, end):
    return abs(start[0] - end[0]) + abs(start[1] - end[1])


def find_path(grid, start, target, blocked, rng):
    queue = [(0, start)]
    costs = {start: 0}
    previous = {}
    while queue:
        cost, position = heappop(queue)
        if cost != costs[position]:
            continue
        if position == target:
            path = [target]
            while path[-1] != start:
                path.append(previous[path[-1]])
            return path[::-1]
        x, y = position
        for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if neighbor not in grid or neighbor in blocked:
                continue
            # Vary the cost of moving between adjacent cells to mix long runs and turns.
            next_cost = cost + rng.uniform(0.25, 1.75)
            if next_cost < costs.get(neighbor, float("inf")):
                costs[neighbor] = next_cost
                previous[neighbor] = position
                heappush(queue, (next_cost, neighbor))
    return None


def snake_route(grid, rng, first=None):
    food = {position for position, level in grid.items() if level}
    if not food:
        return []
    if first is None:
        first = rng.choice(sorted(food))
    starts = [position for position in sorted(grid) if not grid[position] and 2 <= grid_distance(position, first) <= 6]
    route = [rng.choice(starts) if starts else first]
    food.discard(route[0])
    target = first
    while food:
        if target not in food:
            closest = sorted(food, key=lambda position: (grid_distance(route[-1], position), position))[:2]
            target = rng.choice(closest)
        # Keep clear of the tail at turns. Allow it to clear a dead end if needed.
        recent = set(route[-3:-1])
        path = find_path(grid, route[-1], target, recent, rng)
        if path is None:
            path = find_path(grid, route[-1], target, set(), rng)
        route.extend(path[1:])
        food.difference_update(path)
    return route


def snake_round(route, food_boxes, center, duration, number, snake, eyes):
    points = [center(position) for position in route]
    elapsed = [0]
    for previous, current in zip(points, points[1:]):
        elapsed.append(elapsed[-1] + dist(previous, current))
    distance = elapsed[-1]
    first_visit = {}
    for position, offset in zip(route, elapsed):
        first_visit.setdefault(position, offset / distance * TRAVEL_FRACTION)

    path_id = f"snake-path-{number}"
    path = "M" + " L".join(f"{x:.4f},{y:.4f}" for x, y in points)
    pellets = []
    for position, box in food_boxes.items():
        hit = first_visit[position]
        if hit == 0:
            continue
        pellets.append(
            f'{box}><animate attributeName="opacity" calcMode="discrete" '
            f'values="1;0;0" keyTimes="0;{hit:.6f};1" dur="{duration}s" repeatCount="indefinite"/></rect>'
        )

    segments = []
    for index in range(8, -1, -1):
        spacing = min(2.9 * index, distance * 0.8)
        end = 1 - spacing / distance
        times = f"0;{TRAVEL_FRACTION};1"
        offsets = f"0;{end:.6f};{end:.6f}"
        if index:
            times = f"0;{spacing / distance * TRAVEL_FRACTION:.6f};{TRAVEL_FRACTION};1"
            offsets = "0;" + offsets
        if index:
            segment = f'<circle r="{4.4 - index * 0.26:.2f}" opacity="{1 - index * 0.055:.2f}"/>'
        else:
            segment = f'<circle r="4.9"/><path d="M2 -1.6h.01 M2 1.6h.01" stroke="{eyes}" stroke-width="1.5" stroke-linecap="round"/>'
        segments.append(
            f'<g>{segment}<animateMotion dur="{duration}s" repeatCount="indefinite" rotate="auto" '
            f'calcMode="linear" keyTimes="{times}" keyPoints="{offsets}"><mpath href="#{path_id}"/>'
            '</animateMotion></g>'
        )

    return f"""
<g class="snake-round round-{number}">
  <defs><path id="{path_id}" d="{path}"/></defs>
  {chr(10).join(pellets)}
  <g class="snake-body" fill="{snake}">{chr(10).join(segments)}</g>
</g>"""


def snake_card(days, dark):
    surface, border, ink, muted, snake = (
        ("#101e2e", "#344b63", "#edf4ff", "#a4b9d1", "#a7b9fc") if dark
        else ("#f6f9fc", "#cfdae7", "#152840", "#465c75", "#5949bc")
    )
    colors = (
        ("#24364a", "#254d51", "#246e69", "#2c9b89", "#6be4c9") if dark
        else ("#e2eaf2", "#b6e7db", "#76cbb8", "#35a892", "#137869")
    )
    first, last = min(days), max(days)
    sunday = first - timedelta(days=(first.weekday() + 1) % 7)
    grid = {divmod((day - sunday).days, 7): level for day, level in days.items()}
    columns = (last - sunday).days // 7 + 1
    size, step = 10, min(13, 700 / columns)
    left, top = 35, 63

    def center(position):
        column, row = position
        return left + column * step + size / 2, top + row * 13 + size / 2

    cells = []
    food_boxes = {}
    for (column, row), level in sorted(grid.items()):
        x, y = left + column * step, top + row * 13
        box = f'<rect x="{x:.2f}" y="{y}" width="{size}" height="{size}" rx="2"'
        cells.append(f'{box} fill="{colors[0]}"/>')
        if level:
            food_boxes[(column, row)] = f'{box} fill="{colors[level]}"'

    labels = []
    month = None
    previous_label = -10
    for column in range(columns):
        week = sunday + timedelta(weeks=column)
        if month != week.month and column >= previous_label + 5 and column <= columns - 3:
            labels.append(f'<text x="{left + column * step:.2f}" y="54">{week:%b}</text>')
            month = week.month
            previous_label = column

    # Seed by date so both themes use the same routes and the next calendar day gets new routes.
    rng = Random(last.toordinal())
    rounds = []
    if food_boxes:
        first_route = snake_route(grid, rng)
        first_hit = next(position for position in first_route if position in food_boxes)
        next_start = max(food_boxes, key=lambda position: grid_distance(first_hit, position))
        rounds = [first_route, snake_route(grid, rng, first=next_start)]
    longest = max((len(route) - 1 for route in rounds), default=0) * 13
    duration = round(max(7, min(40, longest / 90)), 2)
    animations = [
        snake_round(route, food_boxes, center, duration, number, snake, surface)
        for number, route in enumerate(rounds, 1)
    ]
    still_food = "".join(f"{box}/>" for box in food_boxes.values())
    active = len(food_boxes)
    return svg(760, 172, "Contribution Snake", f"""
<style>
  .snake-round {{ animation: show-round {2 * duration:.2f}s step-end infinite }}
  .round-2 {{ opacity: 0; animation-delay: -{duration}s }}
  .still-food {{ display: none }}
  @keyframes show-round {{ 0% {{ opacity: 1 }} 50%, 100% {{ opacity: 0 }} }}
  @media (prefers-reduced-motion: reduce) {{ .snake-round {{ display: none }} .still-food {{ display: inline }} }}
</style>
<rect x=".5" y=".5" width="759" height="171" rx="13" fill="{surface}" stroke="{border}"/>
<g font-family="{FONT}">
  <path d="M21 22h12" stroke="{snake}" stroke-width="2.5" stroke-linecap="round"/>
  <text x="43" y="27" font-size="15" font-weight="700" fill="{ink}">Contribution Snake</text>
  <text x="739" y="27" font-size="13" text-anchor="end" fill="{muted}">Last year · {active} active {"day" if active == 1 else "days"}</text>
  <g font-size="11" fill="{muted}">{chr(10).join(labels)}</g>
</g>
{chr(10).join(cells)}
<g class="still-food">{still_food}</g>
{chr(10).join(animations)}""",
        f"Snake animation on the GitHub profile contribution calendar, {first} through {last}, {active} active days.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, help="Use saved public API responses and calendar HTML")
    args = parser.parse_args()
    totals, languages, days = load_activity(args.snapshot)
    generated = {
        "stats.svg": stats_card(totals),
        "languages.svg": language_card(languages),
        "snake-light.svg": snake_card(days, dark=False),
        "snake-dark.svg": snake_card(days, dark=True),
    }
    for name, content in generated.items():
        (ASSETS / name).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
