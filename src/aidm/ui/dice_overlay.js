// Dice thrown across the page: real polyhedra built from their corners, spun down onto the rolled face.
const PHI = (1 + Math.sqrt(5)) / 2;
// The rim height that makes a d10's kites flat when its points sit at z = ±1.
const D10_RIM = (1 - Math.cos(Math.PI / 5)) / (1 + Math.cos(Math.PI / 5));
const EPS = 1e-4;
const FLIGHT_MS = 1600;
const REST_MS = 1300;
const FADE_MS = 500;
const STAGGER_MS = 90;

const SOLIDS = {
  4: [[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]],
  6: signed([1, 1, 1]),
  8: cyclic([1, 0, 0]).flatMap(signed),
  10: trapezohedron(),
  12: [...signed([1, 1, 1]), ...cyclic([0, 1 / PHI, PHI]).flatMap(signed)],
  20: cyclic([0, 1, PHI]).flatMap(signed),
};

export default {
  template: "<div></div>",
  methods: {
    toss(dice) {
      if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      const layer = document.createElement("div");
      layer.className = "game-dice-layer";
      this.$el.appendChild(layer);
      const radius = Math.max(36, Math.min(64, Math.min(innerWidth, innerHeight) * 0.055));
      const start = offscreen(radius);
      const spots = [];
      const landings = dice.map((die, index) => {
        const element = buildDie(die, radius);
        layer.appendChild(element);
        const spot = clearSpot(spots, radius);
        spots.push(spot);
        return fly(element, start, spot, radius, index * STAGGER_MS).then(() => {
          element.classList.add("game-dice-landed");
        });
      });
      const fade = { duration: FADE_MS, delay: REST_MS, fill: "forwards" };
      Promise.all(landings)
        .then(() => layer.animate([{ opacity: 1 }, { opacity: 0 }], fade).finished)
        .then(() => layer.remove());
    },
  },
};

function buildDie(die, radius) {
  const points = SOLIDS[die.faces] ?? SOLIDS[6];
  const reach = Math.max(...points.map(length));
  const faces = hullFaces(points.map((point) => scale(point, 1 / reach)));
  const numbers = numbered(faces);
  const size = radius * 2;
  const element = tag("game-dice-die" + (die.kept ? " game-dice-kept" : ""));
  element.style.width = element.style.height = `${size}px`;
  const spin = element.appendChild(tag("game-dice-spin"));
  const body = spin.appendChild(tag("game-dice-body"));
  body.style.transform = facing(faces[numbers.indexOf(die.value)] ?? faces[0]);
  faces.forEach((face, index) => {
    const panel = body.appendChild(tag("game-dice-face"));
    panel.textContent = numbers[index];
    panel.style.transform = `matrix3d(${face.u},0,${face.v},0,${face.normal},0,${scale(face.centroid, radius)},1)`;
    const corners = face.corners.map(([x, y]) => `${radius + x * radius}px ${radius + y * radius}px`);
    panel.style.clipPath = `polygon(${corners})`;
    panel.style.fontSize = `${inradius(face.corners) * radius * 1.1}px`;
  });
  return element;
}

// A point just past the left, right or bottom edge of the page: the handful comes from one hand.
function offscreen(radius) {
  const away = radius * 2;
  const along = Math.random();
  const edges = [
    [-away, innerHeight * along],
    [innerWidth + away, innerHeight * along],
    [innerWidth * along, innerHeight + away],
  ];
  return edges[Math.floor(Math.random() * edges.length)];
}

// A random spot around the middle of the page, away from the dice already down.
function clearSpot(taken, radius) {
  let spot = [];
  for (let tries = 0; tries < 20; tries++) {
    spot = [innerWidth * (0.25 + Math.random() * 0.5) - radius, innerHeight * (0.25 + Math.random() * 0.35) - radius];
    if (taken.every((other) => Math.hypot(other[0] - spot[0], other[1] - spot[1]) > radius * 2.4)) break;
  }
  return spot;
}

function fly(element, start, [x, y], radius, delay) {
  const apex = [(start[0] + x) / 2, (start[1] + y) / 2 - innerHeight * 0.2];
  const turns = () => (Math.random() < 0.5 ? -1 : 1) * (540 + Math.random() * 540);
  const timing = { duration: FLIGHT_MS, delay, fill: "both" };
  element.querySelector(".game-dice-spin").animate(
    [
      { transform: `rotateX(${turns()}deg) rotateY(${turns()}deg) rotateZ(${turns()}deg)` },
      { transform: "rotateX(-12deg) rotateY(12deg) rotateZ(0deg)" },
    ],
    { ...timing, easing: "cubic-bezier(.15,.75,.25,1)" },
  );
  return element.animate(
    [
      { transform: `translate(${start[0]}px, ${start[1]}px) scale(.5)`, opacity: 0, easing: "ease-out" },
      { opacity: 1, offset: 0.15 },
      { transform: `translate(${apex[0]}px, ${apex[1]}px) scale(1.15)`, offset: 0.5, easing: "ease-in" },
      { transform: `translate(${x}px, ${y}px) scale(1)`, offset: 0.8, easing: "ease-out" },
      { transform: `translate(${x}px, ${y - radius * 0.35}px) scale(1)`, offset: 0.9, easing: "ease-in" },
      { transform: `translate(${x}px, ${y}px) scale(1)` },
    ],
    timing,
  ).finished;
}

// The rotation that turns a face toward the viewer with its number upright.
function facing(face) {
  const [nx, ny, nz] = face.normal;
  const axis = [ny, -nx, 0];
  const turn =
    length(axis) < EPS ? (nz > 0 ? "" : "rotate3d(1,0,0,180deg)") : `rotate3d(${axis},${Math.acos(nz)}rad)`;
  const down = new DOMMatrix(turn).transformPoint(new DOMPoint(...face.v, 0));
  return `rotateZ(${Math.PI / 2 - Math.atan2(down.y, down.x)}rad) ${turn}`;
}

// Every plane through three corners that keeps all other corners on one side is a face.
function hullFaces(points) {
  const faces = new Map();
  for (let i = 0; i < points.length; i++) {
    for (let j = i + 1; j < points.length; j++) {
      for (let k = j + 1; k < points.length; k++) {
        let normal = cross(sub(points[j], points[i]), sub(points[k], points[i]));
        if (length(normal) < EPS) continue;
        normal = scale(normal, 1 / length(normal));
        const heights = points.map((point) => dot(sub(point, points[i]), normal));
        if (heights.some((h) => h > EPS)) {
          if (heights.some((h) => h < -EPS)) continue;
          normal = scale(normal, -1);
        }
        const key = normal.map((x) => Math.round(x * 1000) + 0).join();
        if (faces.has(key)) continue;
        faces.set(key, face(points.filter((_, index) => Math.abs(heights[index]) < EPS), normal));
      }
    }
  }
  return [...faces.keys()].sort().map((key) => faces.get(key));
}

function face(corners, normal) {
  const centroid = scale(corners.reduce(add), 1 / corners.length);
  const first = sub(corners[0], centroid);
  let u = scale(first, 1 / length(first));
  let v = cross(normal, u);
  const flatten = () =>
    corners
      .map((corner) => [dot(sub(corner, centroid), u), dot(sub(corner, centroid), v)])
      .sort(([x1, y1], [x2, y2]) => Math.atan2(y1, x1) - Math.atan2(y2, x2));
  // Turn the frame so the number stands on an edge: local down points at the first edge's midpoint.
  const [mx, my] = scale(add(...flatten().slice(0, 2)), 0.5);
  const spin = Math.atan2(my, mx) - Math.PI / 2;
  [u, v] = [
    add(scale(u, Math.cos(spin)), scale(v, Math.sin(spin))),
    add(scale(u, -Math.sin(spin)), scale(v, Math.cos(spin))),
  ];
  return { normal, centroid, u, v, corners: flatten() };
}

// Opposite faces sum to one more than the count, as on a real die.
function numbered(faces) {
  const numbers = new Array(faces.length);
  let next = 1;
  faces.forEach((face, index) => {
    if (numbers[index]) return;
    numbers[index] = next;
    const opposite = faces.findIndex((other) => dot(other.normal, face.normal) < -0.999);
    if (opposite >= 0) numbers[opposite] = faces.length + 1 - next;
    next += 1;
  });
  return numbers;
}

function inradius(corners) {
  return Math.min(
    ...corners.map((p, index) => {
      const q = corners[(index + 1) % corners.length];
      const edge = [q[0] - p[0], q[1] - p[1]];
      return Math.abs(p[0] * edge[1] - p[1] * edge[0]) / Math.hypot(...edge);
    }),
  );
}

function trapezohedron() {
  const rim = [...Array(10).keys()].map((i) => {
    const angle = (i * Math.PI) / 5;
    return [Math.cos(angle), Math.sin(angle), i % 2 ? -D10_RIM : D10_RIM];
  });
  return [[0, 0, 1], [0, 0, -1], ...rim];
}

function signed(point) {
  return point.reduce((points, x) => points.flatMap((p) => (x ? [[...p, x], [...p, -x]] : [[...p, 0]])), [[]]);
}

function cyclic([x, y, z]) {
  return [[x, y, z], [z, x, y], [y, z, x]];
}

function tag(className) {
  const element = document.createElement("div");
  element.className = className;
  return element;
}

const add = (a, b) => a.map((x, i) => x + b[i]);
const sub = (a, b) => a.map((x, i) => x - b[i]);
const scale = (a, k) => a.map((x) => x * k);
const dot = (a, b) => a.reduce((sum, x, i) => sum + x * b[i], 0);
const length = (a) => Math.sqrt(dot(a, a));
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
