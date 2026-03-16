import * as THREE from "https://unpkg.com/three@0.161.0/build/three.module.js";
import { realVoxelBusinesses } from "./businesses.js";

const STREET_LNG = {
  alton: -80.1411,
  washington: -80.1329,
  collins: -80.1317,
  ocean: -80.13045,
  park: -80.1298,
  beach: -80.12915,
};

const CROSS_STREETS = [
  { name: "8th", lat: 25.7780 },
  { name: "10th", lat: 25.78015 },
  { name: "11th", lat: 25.7818 },
  { name: "12th", lat: 25.7827 },
  { name: "14th", lat: 25.78545 },
];

const CATEGORY_META = {
  restaurant: { label: "Restaurant", baseHeight: 5.4, width: 4.2, depth: 4.2, accent: 0xffb177 },
  cafe: { label: "Cafe", baseHeight: 4.4, width: 3.6, depth: 3.8, accent: 0x7deeff },
  gym: { label: "Gym", baseHeight: 6.6, width: 4.8, depth: 4.8, accent: 0x93ffcf },
};

const BOUNDS = computeBounds(realVoxelBusinesses);
const WORLD = {
  minX: -38,
  maxX: 38,
  minZ: -54,
  maxZ: 42,
};

const canvas = document.getElementById("viewport");
const streetLabel = document.getElementById("street-label");
const visitedCountEl = document.getElementById("visited-count");
const factsCountEl = document.getElementById("facts-count");
const modeLabel = document.getElementById("mode-label");
const queueList = document.getElementById("queue-list");
const businessPanel = document.getElementById("business-panel");
const businessNameEl = document.getElementById("business-name");
const businessCategoryEl = document.getElementById("business-category");
const businessStreetEl = document.getElementById("business-street");
const businessDistanceEl = document.getElementById("business-distance");
const businessAddressEl = document.getElementById("business-address");
const businessCompletenessEl = document.getElementById("business-completeness");
const knownPhoneEl = document.getElementById("known-phone");
const knownWebsiteEl = document.getElementById("known-website");
const knownHoursEl = document.getElementById("known-hours");
const businessSourceEl = document.getElementById("business-source");
const businessLicenseEl = document.getElementById("business-license");
const factsList = document.getElementById("facts-list");
const feedList = document.getElementById("feed-list");
const minimap = document.getElementById("minimap");
const zonePill = document.getElementById("zone-pill");
const prompt = document.getElementById("prompt");
const promptTitle = document.getElementById("prompt-title");
const visitButton = document.getElementById("visit-button");
const closePanel = document.getElementById("close-panel");
const intro = document.getElementById("intro");
const startButton = document.getElementById("start-button");
const toast = document.getElementById("toast");

const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: true,
  alpha: false,
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
renderer.setSize(window.innerWidth, window.innerHeight);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf5ab76);
scene.fog = new THREE.Fog(0xf0a36f, 64, 170);

const camera = new THREE.PerspectiveCamera(52, window.innerWidth / window.innerHeight, 0.1, 280);

const ambient = new THREE.HemisphereLight(0xffdfba, 0x17405d, 1.5);
scene.add(ambient);

const sun = new THREE.DirectionalLight(0xffe6bc, 1.95);
sun.position.set(44, 66, 18);
scene.add(sun);

const fill = new THREE.DirectionalLight(0x82f2ff, 0.7);
fill.position.set(-28, 22, -20);
scene.add(fill);

const world = new THREE.Group();
scene.add(world);

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const clock = new THREE.Clock();
const tempVector = new THREE.Vector3();

const pickables = [];
const businessEntries = [];
const obstacleRects = [];
const waveBands = [];
const movingLabels = [];
const clouds = [];
const neonMaterials = [];

const state = {
  started: false,
  cameraYaw: Math.PI * 0.88,
  cameraPitch: 0.54,
  cameraDistance: 19,
  mouseDrag: null,
  selectedId: null,
  activeId: null,
  discovered: new Set(),
  keys: {
    forward: false,
    backward: false,
    left: false,
    right: false,
    fast: false,
  },
  feed: [
    { text: "Jules confirmed outdoor seating at News Cafe.", time: "2m ago" },
    { text: "Mia flagged missing hours at Yoga Lab.", time: "5m ago" },
    { text: "Andre verified day pass info for Crunch Fitness.", time: "8m ago" },
  ],
  toastTimer: null,
};

const MATERIALS = createMaterials();
buildSliceWorld();
const player = createPlayer();
scene.add(player);
buildBusinessWorld();
renderQueue();
renderFeed();
updateStats();
drawMinimap();

const cameraTarget = new THREE.Vector3();
const desiredCamera = new THREE.Vector3();
const currentCamera = new THREE.Vector3();
const lookOffset = new THREE.Vector3();
const moveDirection = new THREE.Vector3();
const rightDirection = new THREE.Vector3();
const nextPosition = new THREE.Vector3();

function computeBounds(data) {
  let lngMin = Infinity;
  let lngMax = -Infinity;
  let latMin = Infinity;
  let latMax = -Infinity;

  data.forEach((business) => {
    lngMin = Math.min(lngMin, business.coords[0]);
    lngMax = Math.max(lngMax, business.coords[0]);
    latMin = Math.min(latMin, business.coords[1]);
    latMax = Math.max(latMax, business.coords[1]);
  });

  return {
    lngMin: lngMin - 0.0016,
    lngMax: lngMax + 0.0018,
    latMin: latMin - 0.0013,
    latMax: latMax + 0.0013,
  };
}

function createMaterials() {
  const mat = (color, extra = {}) =>
    new THREE.MeshStandardMaterial({
      color,
      flatShading: true,
      roughness: 0.9,
      metalness: 0.04,
      ...extra,
    });

  const neon = (color, intensity = 0.75, extra = {}) => {
    const material = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: intensity,
      flatShading: true,
      roughness: 0.38,
      metalness: 0.08,
      ...extra,
    });
    neonMaterials.push(material);
    return material;
  };

  return {
    bay: mat(0x216d97),
    ocean: mat(0x28b1ef),
    foam: neon(0xb8faff, 0.9),
    asphalt: mat(0x34485a),
    sidewalk: mat(0xf0d2bd),
    park: mat(0x76c377),
    darkerPark: mat(0x4b925c),
    sand: mat(0xf0cd88),
    boardwalk: mat(0xc38a55),
    palmTrunk: mat(0x8a5a34),
    palmLeaf: mat(0x2fa45d),
    roof: mat(0xfff3dd),
    dark: mat(0x243244),
    glass: neon(0xc7f7ff, 0.25, { transparent: true, opacity: 0.92 }),
    lane: neon(0xfff2c2, 0.35),
    avatarSkin: mat(0xf0b48a),
    avatarShirt: neon(0xff6ad6, 0.85),
    avatarShorts: mat(0x39bdd9),
    avatarShoe: mat(0x1f2735),
    board: neon(0x92fbff, 0.55),
    sculpture: neon(0xa6ffd7, 0.6),
    skyline: mat(0x21314a),
    white: mat(0xfdfefe),
    amber: neon(0xffcf7c, 0.9),
    cyan: neon(0x7deeff, 1.05),
    magenta: neon(0xff78da, 1.05),
  };
}

function projectLng(lng) {
  return THREE.MathUtils.mapLinear(lng, BOUNDS.lngMin, BOUNDS.lngMax, WORLD.minX, WORLD.maxX);
}

function projectLat(lat) {
  return THREE.MathUtils.mapLinear(lat, BOUNDS.latMin, BOUNDS.latMax, WORLD.maxZ, WORLD.minZ);
}

function projectCoords([lng, lat]) {
  return new THREE.Vector3(projectLng(lng), 0, projectLat(lat));
}

function unprojectX(x) {
  return THREE.MathUtils.mapLinear(x, WORLD.minX, WORLD.maxX, BOUNDS.lngMin, BOUNDS.lngMax);
}

function unprojectZ(z) {
  return THREE.MathUtils.mapLinear(z, WORLD.maxZ, WORLD.minZ, BOUNDS.latMin, BOUNDS.latMax);
}

function worldToCoords(x, z) {
  return [unprojectX(x), unprojectZ(z)];
}

function haversineMeters([lng1, lat1], [lng2, lat2]) {
  const toRad = (value) => (value * Math.PI) / 180;
  const earthRadius = 6371000;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return earthRadius * c;
}

function addBox(group, x, y, z, width, height, depth, material) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material);
  mesh.position.set(x, y + height / 2, z);
  group.add(mesh);
  return mesh;
}

function addObstacle(x, z, width, depth, padding = 0.8) {
  obstacleRects.push({
    minX: x - width / 2 - padding,
    maxX: x + width / 2 + padding,
    minZ: z - depth / 2 - padding,
    maxZ: z + depth / 2 + padding,
  });
}

function shortLabel(name) {
  const parts = name.split(" ");
  return parts.length > 2 ? `${parts[0]} ${parts[1]}` : name;
}

function createLabelSprite(text, borderColor) {
  const spriteCanvas = document.createElement("canvas");
  spriteCanvas.width = 420;
  spriteCanvas.height = 120;
  const ctx = spriteCanvas.getContext("2d");
  roundRect(ctx, 10, 14, 400, 92, 24);
  ctx.fillStyle = "rgba(8, 12, 24, 0.82)";
  ctx.fill();
  ctx.lineWidth = 5;
  ctx.strokeStyle = borderColor;
  ctx.stroke();
  ctx.font = '700 46px "Space Grotesk"';
  ctx.fillStyle = "#f7fbff";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 210, 60);
  const texture = new THREE.CanvasTexture(spriteCanvas);
  texture.needsUpdate = true;
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(9.4, 2.7, 1);
  return sprite;
}

function roundRect(ctx, x, y, width, height, radius) {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + width - radius, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
  ctx.lineTo(x + width, y + height - radius);
  ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  ctx.lineTo(x + radius, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}

function addPalm(group, x, z, height = 5.4) {
  addBox(group, x, 0.7, z, 0.56, height, 0.56, MATERIALS.palmTrunk);
  const crownY = height + 1.1;
  addBox(group, x, crownY, z, 2.8, 0.34, 0.9, MATERIALS.palmLeaf);
  addBox(group, x, crownY, z, 0.9, 0.34, 2.8, MATERIALS.palmLeaf);
  addBox(group, x + 0.82, crownY - 0.25, z + 0.2, 1.8, 0.24, 0.55, MATERIALS.palmLeaf);
  addBox(group, x - 0.82, crownY - 0.25, z - 0.2, 1.8, 0.24, 0.55, MATERIALS.palmLeaf);
}

function addUmbrella(group, x, z, material) {
  addBox(group, x, 0.3, z, 0.14, 1.1, 0.14, MATERIALS.dark);
  addBox(group, x, 1.38, z, 1.6, 0.18, 1.6, material);
}

function addLifeguardTower(group, x, z) {
  addBox(group, x, 0.18, z, 2.4, 0.36, 2.4, MATERIALS.white);
  addBox(group, x, 0.56, z, 1.6, 0.72, 1.6, MATERIALS.cyan);
  addBox(group, x, 1.3, z, 2.1, 0.24, 2.1, MATERIALS.amber);
  addBox(group, x, 1.62, z, 2.2, 0.16, 2.2, MATERIALS.roof);
}

function addCloud(x, y, z, scale = 1) {
  const cloud = new THREE.Group();
  addBox(cloud, 0, 0, 0, 7 * scale, 1.7 * scale, 3 * scale, MATERIALS.white);
  addBox(cloud, -2.2 * scale, 0.6 * scale, 0.2 * scale, 3.4 * scale, 1.5 * scale, 2.4 * scale, MATERIALS.white);
  addBox(cloud, 2.4 * scale, 0.5 * scale, 0.2 * scale, 4.1 * scale, 1.6 * scale, 2.6 * scale, MATERIALS.white);
  cloud.position.set(x, y, z);
  cloud.userData.speed = 1.4 + scale * 0.4;
  clouds.push(cloud);
  scene.add(cloud);
}

function buildSliceWorld() {
  const zCenter = (WORLD.minZ + WORLD.maxZ) / 2;
  const depth = WORLD.maxZ - WORLD.minZ;
  const xAlton = projectLng(STREET_LNG.alton);
  const xWashington = projectLng(STREET_LNG.washington);
  const xCollins = projectLng(STREET_LNG.collins);
  const xOcean = projectLng(STREET_LNG.ocean);
  const xPark = projectLng(STREET_LNG.park);
  const xBeach = projectLng(STREET_LNG.beach);
  const bayWidth = xAlton - WORLD.minX - 5;
  const oceanWidth = WORLD.maxX - xBeach + 8;

  addBox(world, WORLD.minX + bayWidth / 2 - 4, -0.35, zCenter, bayWidth, 0.7, depth + 22, MATERIALS.bay);
  addBox(world, WORLD.maxX - oceanWidth / 2 + 4, -0.32, zCenter, oceanWidth, 0.64, depth + 20, MATERIALS.ocean);
  addBox(world, xAlton - 4.8, -0.04, zCenter, 5.2, 0.48, depth, MATERIALS.sidewalk);
  addBox(world, xAlton, -0.05, zCenter, 3.4, 0.52, depth, MATERIALS.asphalt);
  addBox(world, xWashington, -0.05, zCenter, 3.2, 0.52, depth, MATERIALS.asphalt);
  addBox(world, xCollins, -0.05, zCenter, 2.9, 0.5, depth, MATERIALS.asphalt);
  addBox(world, xOcean, -0.05, zCenter, 2.6, 0.5, depth, MATERIALS.asphalt);
  addBox(world, (xWashington + xCollins) / 2, -0.04, zCenter, xCollins - xWashington - 3.8, 0.46, depth, MATERIALS.sidewalk);
  addBox(world, (xOcean + xPark) / 2, -0.04, zCenter, xPark - xOcean - 0.6, 0.46, depth, MATERIALS.park);
  addBox(world, (xPark + xBeach) / 2, -0.04, zCenter, xBeach - xPark + 2.2, 0.46, depth, MATERIALS.sand);
  addBox(world, xCollins + 2.1, -0.03, zCenter, 2.1, 0.45, depth, MATERIALS.sidewalk);
  addBox(world, xOcean + 1.8, -0.03, zCenter, 1.6, 0.45, depth, MATERIALS.sidewalk);
  addBox(world, xPark + 2.8, -0.03, zCenter, 1.4, 0.45, depth, MATERIALS.boardwalk);

  for (let z = WORLD.minZ + 4; z < WORLD.maxZ; z += 10) {
    addBox(world, xAlton, 0.42, z, 0.35, 0.08, 4.2, MATERIALS.lane);
    addBox(world, xWashington, 0.42, z, 0.35, 0.08, 4.2, MATERIALS.lane);
    addBox(world, xCollins, 0.42, z, 0.3, 0.08, 3.8, MATERIALS.lane);
    addBox(world, xOcean, 0.42, z, 0.3, 0.08, 3.8, MATERIALS.lane);
  }

  CROSS_STREETS.forEach((street) => {
    const z = projectLat(street.lat);
    addBox(world, (xWashington + xPark) / 2, -0.04, z, xPark - xWashington + 3.8, 0.46, 2.5, MATERIALS.asphalt);
    addBox(world, (xAlton + xWashington) / 2 - 1.5, -0.04, z, xWashington - xAlton + 0.8, 0.44, 2.1, MATERIALS.asphalt);
    addBox(world, (xOcean + xPark) / 2, 0.38, z, xPark - xOcean, 0.06, 0.28, MATERIALS.lane);
  });

  for (let z = WORLD.minZ + 2; z <= WORLD.maxZ; z += 8) {
    addPalm(world, xPark - 0.4, z, 5.3);
    addPalm(world, xPark + 3.6, z + 2.4, 5.1);
    addUmbrella(world, xBeach + 1.8, z + 1.2, z % 16 === 0 ? MATERIALS.magenta : MATERIALS.amber);
  }

  addLifeguardTower(world, xBeach + 0.8, projectLat(25.779));
  addLifeguardTower(world, xBeach + 0.8, projectLat(25.7832));

  for (let z = WORLD.minZ - 6; z <= WORLD.maxZ + 6; z += 6) {
    const band = addBox(world, WORLD.maxX - 3.6, -0.18, z, 12, 0.18, 2.1, MATERIALS.foam);
    waveBands.push({ mesh: band, baseY: band.position.y, phase: z * 0.14 });
  }

  buildStreetLabels(xAlton, xWashington, xCollins, xOcean, xPark);
  buildBackdrop();
  buildSky();
}

function buildStreetLabels(xAlton, xWashington, xCollins, xOcean, xPark) {
  const labels = [
    { text: "Alton Road", x: xAlton - 1.8, z: WORLD.maxZ - 6, color: "#7deeff" },
    { text: "Washington", x: xWashington, z: WORLD.maxZ - 6, color: "#ff78da" },
    { text: "Collins", x: xCollins, z: WORLD.maxZ - 6, color: "#ffd189" },
    { text: "Ocean Drive", x: xOcean + 0.4, z: WORLD.maxZ - 8, color: "#ff78da" },
    { text: "Lummus Park", x: xPark + 1.2, z: WORLD.maxZ - 10, color: "#7deeff" },
  ];

  labels.forEach((label) => {
    const sprite = createLabelSprite(label.text, label.color);
    sprite.position.set(label.x, 7.5, label.z);
    world.add(sprite);
    movingLabels.push({ target: sprite, baseY: sprite.position.y, drift: Math.random() * Math.PI * 2 });
  });
}

function buildBackdrop() {
  const skyline = new THREE.Group();
  for (let index = 0; index < 6; index += 1) {
    const x = WORLD.minX + 2 + index * 4.2;
    const h = 14 + (index % 3) * 6;
    const z = WORLD.minZ + 14 + index * 8;
    addBox(skyline, x, 0, z, 3.2, h, 6 + (index % 2) * 2, MATERIALS.skyline);
  }

  addBox(skyline, projectLng(STREET_LNG.alton) - 5.8, -0.02, (WORLD.minZ + WORLD.maxZ) / 2, 2.4, 0.42, WORLD.maxZ - WORLD.minZ, MATERIALS.darkerPark);
  addBox(skyline, projectLng(STREET_LNG.ocean) + 3.2, -0.01, (WORLD.minZ + WORLD.maxZ) / 2, 0.7, 0.44, WORLD.maxZ - WORLD.minZ, MATERIALS.boardwalk);
  world.add(skyline);
}

function buildSky() {
  addCloud(4, 30, -8, 1.4);
  addCloud(26, 34, -28, 1.1);
  addCloud(-8, 29, 12, 1.25);
  addCloud(18, 33, 28, 1.35);

  const sunMesh = new THREE.Mesh(
    new THREE.SphereGeometry(6, 16, 16),
    new THREE.MeshBasicMaterial({ color: 0xffdd8a })
  );
  sunMesh.position.set(58, 46, -34);
  scene.add(sunMesh);
}

function streetPalette(street, category) {
  if (street === "Ocean Drive") {
    return { body: 0xffa2b7, accent: 0xff78da };
  }
  if (street === "Washington Avenue") {
    return { body: category === "gym" ? 0x8fead5 : 0xffc491, accent: 0x7deeff };
  }
  if (street === "Alton Road") {
    return { body: 0xaad7ff, accent: 0xffd189 };
  }
  return { body: 0xcab5ff, accent: 0x7deeff };
}

function buildBusinessWorld() {
  realVoxelBusinesses.forEach((business) => {
    const pos = projectCoords(business.coords);
    const group = new THREE.Group();
    const meta = CATEGORY_META[business.category];
    const palette = streetPalette(business.street, business.category);
    const bodyMaterial = new THREE.MeshStandardMaterial({
      color: palette.body,
      flatShading: true,
      roughness: 0.85,
      metalness: 0.04,
    });
    const accentMaterial = new THREE.MeshStandardMaterial({
      color: palette.accent,
      emissive: palette.accent,
      emissiveIntensity: 0.78,
      flatShading: true,
      roughness: 0.36,
      metalness: 0.08,
    });
    neonMaterials.push(accentMaterial);

    const height = meta.baseHeight + (business.completeness - 30) / 18;
    const width = meta.width;
    const depth = meta.depth;

    addBox(group, 0, 0, 0, width, height, depth, bodyMaterial);
    addBox(group, 0, height, 0, width - 0.7, 0.8, depth - 0.8, bodyMaterial);
    addBox(group, 0, height + 0.7, 0, width - 1.4, 0.4, depth - 1.4, MATERIALS.roof);

    if (business.street === "Ocean Drive") {
      addBox(group, width / 2 - 0.24, 0.5, 0, 0.24, height + 1.2, depth + 0.5, accentMaterial);
      addBox(group, width / 2 - 0.88, 0.8, 0, 0.14, height + 0.8, depth, accentMaterial);
      addBox(group, 0, 0.3, depth / 2 - 0.25, width + 0.3, 0.22, 0.24, accentMaterial);
      addBox(group, 0, 1.2, depth / 2 - 0.18, width - 1.1, 1.2, 0.16, MATERIALS.glass);
    } else if (business.street === "Washington Avenue") {
      addBox(group, 0, 0.3, depth / 2 - 0.22, width + 0.3, 0.26, 0.24, accentMaterial);
      addBox(group, 0, 1.1, depth / 2 - 0.16, width - 0.8, 1.2, 0.16, MATERIALS.glass);
      addBox(group, -width / 2 + 0.35, 0.5, 0, 0.16, height + 1, depth, accentMaterial);
    } else {
      addBox(group, 0, 0.28, depth / 2 - 0.18, width + 0.3, 0.22, 0.22, accentMaterial);
      addBox(group, 0, 1.2, depth / 2 - 0.14, width - 1.1, 1.1, 0.14, MATERIALS.glass);
      addBox(group, 0, height + 0.3, 0, width - 1.8, 0.4, depth - 1.8, accentMaterial);
    }

    if (business.category === "gym") {
      addBox(group, 0, height + 1.1, 0, width - 1.2, 0.35, depth - 1.5, MATERIALS.dark);
      addBox(group, -0.9, 0, -depth / 2 - 0.8, 0.45, 1, 0.45, MATERIALS.dark);
      addBox(group, 0.9, 0, -depth / 2 - 0.8, 0.45, 1, 0.45, MATERIALS.dark);
    } else {
      addBox(group, -1.1, 0, -depth / 2 - 0.8, 0.6, 0.7, 0.6, MATERIALS.dark);
      addBox(group, 1.1, 0, -depth / 2 - 0.8, 0.6, 0.7, 0.6, MATERIALS.dark);
    }

    const beacon = addBox(group, 0, height + 1.4, 0, 0.34, 2.1, 0.34, accentMaterial);
    const top = addBox(group, 0, height + 3.55, 0, 0.9, 0.3, 0.9, accentMaterial);
    const label = createLabelSprite(shortLabel(business.name), `#${palette.accent.toString(16).padStart(6, "0")}`);
    label.position.set(0, height + 6, 0);
    group.add(label);
    const light = new THREE.PointLight(palette.accent, 1.4, 16);
    light.position.set(0, height + 3.2, 0);
    group.add(light);

    group.position.copy(pos);
    world.add(group);
    addObstacle(pos.x, pos.z, width + 0.4, depth + 0.4);

    group.traverse((child) => {
      if (child.isMesh) {
        child.userData.businessId = business.id;
        pickables.push(child);
      }
    });

    businessEntries.push({
      ...business,
      group,
      label,
      beacon,
      top,
      light,
      beaconBaseY: beacon.position.y,
      labelBaseY: label.position.y,
      distance: Infinity,
      worldPosition: pos.clone(),
      discovered: false,
    });
  });
}

function createPlayer() {
  const avatar = new THREE.Group();
  addBox(avatar, 0, 0, 0, 1.2, 0.34, 2.4, MATERIALS.board);
  addBox(avatar, 0, 0.32, 0.4, 1.2, 0.6, 0.65, MATERIALS.avatarShorts);
  addBox(avatar, 0, 0.98, 0.5, 1.2, 1.28, 0.75, MATERIALS.avatarShirt);
  addBox(avatar, 0, 2.02, 0.5, 1.02, 1.02, 1.02, MATERIALS.avatarSkin);
  addBox(avatar, -0.32, 0.04, 0.94, 0.36, 0.28, 0.7, MATERIALS.avatarShoe);
  addBox(avatar, 0.32, 0.04, 0.94, 0.36, 0.28, 0.7, MATERIALS.avatarShoe);
  avatar.position.set(projectLng(STREET_LNG.ocean) + 2.6, 0, projectLat(25.7806));
  return avatar;
}

function findEntry(id) {
  return businessEntries.find((entry) => entry.id === id) ?? null;
}

function totalVerifiedFacts() {
  return businessEntries.reduce(
    (count, entry) => count + entry.facts.filter((fact) => fact.confirmations >= fact.target).length,
    0
  );
}

function updateStats() {
  visitedCountEl.textContent = String(state.discovered.size);
  factsCountEl.textContent = String(totalVerifiedFacts());
  modeLabel.textContent = state.started ? "Real Slice" : "Paused";
}

function currentCorridor() {
  const x = player.position.x;
  const oceanX = projectLng(STREET_LNG.ocean);
  const collinsX = projectLng(STREET_LNG.collins);
  const washingtonX = projectLng(STREET_LNG.washington);
  const altonX = projectLng(STREET_LNG.alton);
  const parkX = projectLng(STREET_LNG.park);
  const beachX = projectLng(STREET_LNG.beach);

  if (x > beachX + 0.6) {
    return { label: "Atlantic Edge", zone: "Beach and Atlantic" };
  }
  if (x > parkX) {
    return { label: "Lummus Park", zone: "Lummus Park and beachwalk" };
  }
  if (x > oceanX - 1.4) {
    return { label: "Ocean Drive", zone: "Ocean Drive frontage" };
  }
  if (x > collinsX - 1.2) {
    return { label: "Collins Avenue", zone: "Collins corridor" };
  }
  if (x > washingtonX - 1.6) {
    return { label: "Washington Avenue", zone: "Washington Avenue strip" };
  }
  if (x > altonX - 1.8) {
    return { label: "Alton Road", zone: "Alton Road edge" };
  }
  return { label: "Bay Side", zone: "Bay approach" };
}

function renderQueue() {
  queueList.innerHTML = "";
  const sorted = [...businessEntries].sort((a, b) => a.distance - b.distance).slice(0, 6);
  sorted.forEach((entry) => {
    const item = document.createElement("button");
    item.className = `queue-item${entry.id === state.selectedId ? " active" : ""}`;
    item.innerHTML = `
      <div class="queue-top">
        <span class="queue-title">${entry.name}</span>
        <span class="queue-distance">${Math.round(entry.distance)}m</span>
      </div>
      <div class="queue-bottom">
        <span class="queue-pending">${missingFactCount(entry)} open facts</span>
        <span class="queue-badges">
          <span class="meta-chip">${entry.street}</span>
          <span class="meta-chip emphasis">${entry.completeness}%</span>
        </span>
      </div>
    `;
    item.addEventListener("click", () => selectBusiness(entry.id));
    queueList.appendChild(item);
  });
}

function missingFactCount(entry) {
  return entry.facts.filter((fact) => fact.confirmations < fact.target).length;
}

function renderBusiness(entry) {
  if (!entry) {
    businessPanel.classList.add("hidden");
    return;
  }

  businessPanel.classList.remove("hidden");
  businessNameEl.textContent = entry.name;
  businessCategoryEl.textContent = CATEGORY_META[entry.category].label;
  businessStreetEl.textContent = entry.street;
  businessDistanceEl.textContent = `${Math.round(entry.distance)}m away`;
  businessAddressEl.textContent = entry.address || "Address still needs cleanup from source.";
  businessCompletenessEl.textContent = `${entry.completeness}% complete`;
  knownPhoneEl.textContent = entry.fields.phone ? "Known" : "Missing";
  knownWebsiteEl.textContent = entry.fields.website ? "Known" : "Missing";
  knownHoursEl.textContent = entry.fields.hours ? "Known" : "Missing";
  businessSourceEl.textContent = `Source: ${entry.source.toUpperCase()}`;
  businessLicenseEl.textContent = `License: ${entry.sourceLicense}`;

  factsList.innerHTML = "";
  entry.facts.forEach((fact) => {
    const verified = fact.confirmations >= fact.target;
    const progress = Math.min(100, (fact.confirmations / fact.target) * 100);
    const card = document.createElement("div");
    card.className = "fact-card";
    const options = fact.options
      .map(
        (option) =>
          `<button class="fact-option" data-business="${entry.id}" data-fact="${fact.key}" data-value="${option}" ${verified ? "disabled" : ""}>${option}</button>`
      )
      .join("");

    card.innerHTML = `
      <div class="fact-top">
        <div>
          <div class="fact-title">${fact.label}</div>
          <div class="fact-copy">${fact.prompt}</div>
        </div>
        <span class="meta-chip ${verified ? "emphasis" : ""}">${verified ? "verified" : "pending"}</span>
      </div>
      <div class="fact-progress">
        <span>${fact.confirmations}/${fact.target} confirmations</span>
        <span>${verified ? "Consensus reached" : "Still needs players"}</span>
      </div>
      <div class="progress-track"><div class="progress-fill" style="width:${progress}%"></div></div>
      <div class="fact-options">${options}</div>
    `;
    factsList.appendChild(card);
  });

  factsList.querySelectorAll(".fact-option").forEach((button) => {
    button.addEventListener("click", () => {
      submitFact(
        button.getAttribute("data-business"),
        button.getAttribute("data-fact"),
        button.getAttribute("data-value")
      );
    });
  });
}

function renderFeed() {
  feedList.innerHTML = "";
  state.feed.slice(0, 6).forEach((entry) => {
    const card = document.createElement("div");
    card.className = "feed-item";
    card.innerHTML = `
      <div class="feed-top">
        <span class="feed-title">${entry.text}</span>
        <span class="feed-time">${entry.time}</span>
      </div>
    `;
    feedList.appendChild(card);
  });
}

function submitFact(businessId, factKey, value) {
  const entry = findEntry(businessId);
  if (!entry) {
    return;
  }

  const fact = entry.facts.find((item) => item.key === factKey);
  if (!fact || fact.confirmations >= fact.target) {
    return;
  }

  fact.confirmations += 1;
  const justVerified = fact.confirmations >= fact.target;
  entry.completeness = Math.min(100, entry.completeness + (justVerified ? 8 : 3));

  if (fact.key === "phone") {
    entry.fields.phone = value !== "Unavailable";
  }
  if (fact.key === "website") {
    entry.fields.website = value !== "No" && value !== "Unavailable";
  }
  if (fact.key === "hours") {
    entry.fields.hours = value !== "Unsure" && value !== "Update needed" && value !== "Changed";
  }

  state.feed.unshift({
    text: `You answered "${value}" for ${fact.label} at ${entry.name}.`,
    time: "now",
  });
  state.feed = state.feed.slice(0, 8);

  renderBusiness(entry);
  renderQueue();
  renderFeed();
  updateStats();
  showToast(justVerified ? `${fact.label} verified for ${entry.name}` : `Answer saved for ${entry.name}`);
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => {
    toast.classList.remove("visible");
  }, 2200);
}

function selectBusiness(id) {
  state.selectedId = id;
  const entry = findEntry(id);
  if (!entry) {
    return;
  }

  if (!entry.discovered) {
    entry.discovered = true;
    state.discovered.add(entry.id);
    updateStats();
  }

  renderBusiness(entry);
  renderQueue();
}

function isWalkable(x, z) {
  const xPark = projectLng(STREET_LNG.park);
  const xBeach = projectLng(STREET_LNG.beach);
  if (z < WORLD.minZ || z > WORLD.maxZ) {
    return false;
  }
  if (x < WORLD.minX + 4 || x > WORLD.maxX - 5.2) {
    return false;
  }
  if (x < projectLng(STREET_LNG.alton) - 5.8) {
    return false;
  }
  if (x > xBeach + 3.8) {
    return false;
  }
  for (const rect of obstacleRects) {
    if (x > rect.minX && x < rect.maxX && z > rect.minZ && z < rect.maxZ) {
      return false;
    }
  }
  if (x > xPark + 0.6 && x < xBeach - 0.8) {
    return true;
  }
  return true;
}

function updateProximity() {
  if (!state.started) {
    prompt.classList.add("hidden");
    visitButton.classList.add("hidden");
  }

  const playerCoords = worldToCoords(player.position.x, player.position.z);
  let nearest = null;
  let minDistance = Infinity;

  businessEntries.forEach((entry) => {
    entry.distance = haversineMeters(playerCoords, entry.coords);
    const highlight = entry.id === state.selectedId || entry.distance < 34;
    entry.label.visible = highlight;
    if (entry.distance < minDistance) {
      minDistance = entry.distance;
      nearest = entry;
    }
  });

  state.activeId = nearest && nearest.distance < 28 ? nearest.id : null;

  if (state.activeId && state.started) {
    const active = findEntry(state.activeId);
    prompt.classList.remove("hidden");
    visitButton.classList.remove("hidden");
    promptTitle.textContent = active.discovered ? `Revisit ${active.name}` : `Inspect ${active.name}`;
  } else {
    prompt.classList.add("hidden");
    visitButton.classList.add("hidden");
  }

  if (state.selectedId) {
    renderBusiness(findEntry(state.selectedId));
  }

  renderQueue();
  updateStats();
}

function updateHud() {
  const corridor = currentCorridor();
  streetLabel.textContent = corridor.label;
  zonePill.textContent = corridor.zone;
}

function updateCamera(delta) {
  cameraTarget.set(player.position.x, 4.8, player.position.z);
  const pitchCos = Math.cos(state.cameraPitch);
  lookOffset.set(
    Math.sin(state.cameraYaw) * pitchCos * state.cameraDistance,
    Math.sin(state.cameraPitch) * state.cameraDistance + 3.4,
    Math.cos(state.cameraYaw) * pitchCos * state.cameraDistance
  );

  desiredCamera.copy(cameraTarget).add(lookOffset);
  currentCamera.lerp(desiredCamera, 1 - Math.exp(-delta * 7));
  camera.position.copy(currentCamera);
  camera.lookAt(cameraTarget);
}

function applyMovement(delta) {
  let inputX = 0;
  let inputZ = 0;
  if (state.keys.left) inputX -= 1;
  if (state.keys.right) inputX += 1;
  if (state.keys.forward) inputZ += 1;
  if (state.keys.backward) inputZ -= 1;

  if (inputX === 0 && inputZ === 0) {
    player.position.y = THREE.MathUtils.lerp(player.position.y, 0, 0.12);
    return;
  }

  const inputVector = new THREE.Vector2(inputX, inputZ);
  if (inputVector.lengthSq() > 1) {
    inputVector.normalize();
  }

  const forwardYaw = state.cameraYaw + Math.PI;
  moveDirection.set(Math.sin(forwardYaw), 0, Math.cos(forwardYaw));
  rightDirection.set(Math.sin(forwardYaw - Math.PI / 2), 0, Math.cos(forwardYaw - Math.PI / 2));

  tempVector.copy(moveDirection).multiplyScalar(inputVector.y);
  tempVector.addScaledVector(rightDirection, inputVector.x);

  const speed = state.keys.fast ? 10.2 : 6.4;
  nextPosition.copy(player.position).addScaledVector(tempVector, speed * delta);

  if (isWalkable(nextPosition.x, player.position.z)) {
    player.position.x = nextPosition.x;
  }
  if (isWalkable(player.position.x, nextPosition.z)) {
    player.position.z = nextPosition.z;
  }

  player.rotation.y = Math.atan2(tempVector.x, tempVector.z);
  const sway = Math.sin(clock.elapsedTime * 10) * 0.07;
  player.position.y = Math.abs(sway) * 0.18;
}

function updateWorldEffects(elapsed) {
  const pulse = (Math.sin(elapsed * 1.6) + 1) * 0.5;
  neonMaterials.forEach((material, index) => {
    material.emissiveIntensity = 0.42 + pulse * 0.7 + (index % 4) * 0.03;
  });

  waveBands.forEach((entry, index) => {
    entry.mesh.position.y = entry.baseY + Math.sin(elapsed * 1.8 + entry.phase + index * 0.2) * 0.08;
  });

  movingLabels.forEach((entry, index) => {
    entry.target.position.y = entry.baseY + Math.sin(elapsed * 1.4 + entry.drift + index * 0.15) * 0.18;
  });

  businessEntries.forEach((entry, index) => {
    entry.beacon.position.y = entry.beaconBaseY + Math.sin(elapsed * 2 + index * 0.6) * 0.22;
    entry.label.position.y = entry.labelBaseY + Math.sin(elapsed * 1.8 + index * 0.5) * 0.22;
    entry.light.intensity = 0.8 + Math.sin(elapsed * 2.2 + index) * 0.28;
    entry.top.rotation.y += 0.01;
  });

  clouds.forEach((cloud) => {
    cloud.position.x += cloud.userData.speed * 0.01;
    if (cloud.position.x > 64) {
      cloud.position.x = -56;
    }
  });
}

function drawMinimap() {
  const ctx = minimap.getContext("2d");
  const width = minimap.width;
  const height = minimap.height;
  const mapX = (x) => ((x - WORLD.minX) / (WORLD.maxX - WORLD.minX)) * (width - 20) + 10;
  const mapZ = (z) => ((z - WORLD.minZ) / (WORLD.maxZ - WORLD.minZ)) * (height - 20) + 10;

  const xAlton = projectLng(STREET_LNG.alton);
  const xWashington = projectLng(STREET_LNG.washington);
  const xCollins = projectLng(STREET_LNG.collins);
  const xOcean = projectLng(STREET_LNG.ocean);
  const xPark = projectLng(STREET_LNG.park);
  const xBeach = projectLng(STREET_LNG.beach);

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#071321";
  ctx.fillRect(0, 0, width, height);

  ctx.fillStyle = "#134363";
  ctx.fillRect(6, 6, mapX(xAlton - 5.5) - 6, height - 12);
  ctx.fillStyle = "#2d4154";
  ctx.fillRect(mapX(xAlton - 1.8), 8, mapX(xOcean + 1.5) - mapX(xAlton - 1.8), height - 16);
  ctx.fillStyle = "#6dbe72";
  ctx.fillRect(mapX(xOcean + 0.9), 8, mapX(xPark + 2.8) - mapX(xOcean + 0.9), height - 16);
  ctx.fillStyle = "#f0cd88";
  ctx.fillRect(mapX(xPark + 2.8), 8, mapX(xBeach + 3.6) - mapX(xPark + 2.8), height - 16);
  ctx.fillStyle = "#21a6df";
  ctx.fillRect(mapX(xBeach + 3.6), 8, width - mapX(xBeach + 3.6) - 8, height - 16);

  ctx.strokeStyle = "rgba(255,255,255,0.15)";
  ctx.lineWidth = 1;
  [xAlton, xWashington, xCollins, xOcean].forEach((streetX) => {
    ctx.beginPath();
    ctx.moveTo(mapX(streetX), 10);
    ctx.lineTo(mapX(streetX), height - 10);
    ctx.stroke();
  });

  CROSS_STREETS.forEach((street) => {
    const z = projectLat(street.lat);
    ctx.beginPath();
    ctx.moveTo(mapX(xWashington - 2), mapZ(z));
    ctx.lineTo(mapX(xPark + 3), mapZ(z));
    ctx.stroke();
  });

  businessEntries.forEach((entry) => {
    ctx.beginPath();
    ctx.arc(mapX(entry.worldPosition.x), mapZ(entry.worldPosition.z), 4, 0, Math.PI * 2);
    ctx.fillStyle = entry.id === state.selectedId ? "#ffffff" : entry.discovered ? "#89ffc9" : "#ff78da";
    ctx.fill();
  });

  ctx.beginPath();
  ctx.arc(mapX(player.position.x), mapZ(player.position.z), 5, 0, Math.PI * 2);
  ctx.fillStyle = "#7deeff";
  ctx.fill();
  ctx.strokeStyle = "#071321";
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.fillStyle = "rgba(245,248,252,0.8)";
  ctx.font = '700 11px "Space Grotesk"';
  ctx.fillText("BAY", 12, 20);
  ctx.fillText("OCEAN", width - 54, 20);
}

function handlePointerClick(event) {
  const rect = canvas.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObjects(pickables, false)[0];
  if (!hit) {
    return;
  }
  const id = hit.object.userData.businessId;
  if (id) {
    selectBusiness(id);
  }
}

function interactNearest() {
  if (state.activeId) {
    selectBusiness(state.activeId);
  }
}

function animate() {
  requestAnimationFrame(animate);
  const delta = Math.min(clock.getDelta(), 0.033);
  const elapsed = clock.elapsedTime;

  if (state.started) {
    applyMovement(delta);
    updateProximity();
    updateHud();
  }

  updateCamera(delta);
  updateWorldEffects(elapsed);
  drawMinimap();
  renderer.render(scene, camera);
}

function resize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

function clampPitch() {
  state.cameraPitch = THREE.MathUtils.clamp(state.cameraPitch, 0.28, 0.84);
}

window.addEventListener("resize", resize);

document.addEventListener("keydown", (event) => {
  if (event.code === "KeyW" || event.code === "ArrowUp") state.keys.forward = true;
  if (event.code === "KeyS" || event.code === "ArrowDown") state.keys.backward = true;
  if (event.code === "KeyA" || event.code === "ArrowLeft") state.keys.left = true;
  if (event.code === "KeyD" || event.code === "ArrowRight") state.keys.right = true;
  if (event.code === "ShiftLeft" || event.code === "ShiftRight") state.keys.fast = true;
  if (event.code === "KeyE") interactNearest();
});

document.addEventListener("keyup", (event) => {
  if (event.code === "KeyW" || event.code === "ArrowUp") state.keys.forward = false;
  if (event.code === "KeyS" || event.code === "ArrowDown") state.keys.backward = false;
  if (event.code === "KeyA" || event.code === "ArrowLeft") state.keys.left = false;
  if (event.code === "KeyD" || event.code === "ArrowRight") state.keys.right = false;
  if (event.code === "ShiftLeft" || event.code === "ShiftRight") state.keys.fast = false;
});

canvas.addEventListener("pointerdown", (event) => {
  state.mouseDrag = { x: event.clientX, y: event.clientY };
  canvas.setPointerCapture(event.pointerId);
});

canvas.addEventListener("pointermove", (event) => {
  if (!state.mouseDrag) {
    return;
  }
  const deltaX = event.clientX - state.mouseDrag.x;
  const deltaY = event.clientY - state.mouseDrag.y;
  state.mouseDrag.x = event.clientX;
  state.mouseDrag.y = event.clientY;
  state.cameraYaw -= deltaX * 0.008;
  state.cameraPitch -= deltaY * 0.006;
  clampPitch();
});

canvas.addEventListener("pointerup", (event) => {
  if (state.mouseDrag) {
    canvas.releasePointerCapture(event.pointerId);
  }
  state.mouseDrag = null;
});

canvas.addEventListener("click", handlePointerClick);
canvas.addEventListener("wheel", (event) => {
  state.cameraDistance = THREE.MathUtils.clamp(state.cameraDistance + event.deltaY * 0.012, 11, 24);
});

visitButton.addEventListener("click", interactNearest);
closePanel.addEventListener("click", () => {
  state.selectedId = null;
  businessPanel.classList.add("hidden");
  renderQueue();
});

startButton.addEventListener("click", () => {
  state.started = true;
  intro.classList.remove("open");
  intro.classList.add("hidden");
  showToast("South Beach voxel slice loaded.");
  updateStats();
});

resize();
updateHud();
updateProximity();
animate();
