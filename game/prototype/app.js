import * as THREE from "https://unpkg.com/three@0.161.0/build/three.module.js";

const WORLD = {
  minX: -18,
  maxX: 46,
  minZ: -68,
  maxZ: 42,
};

const LANDMARKS = [
  {
    id: "south-pointe",
    name: "South Pointe Pier",
    district: "South Pointe",
    position: new THREE.Vector3(38, 1, -58),
    description: "The southern tip of Miami Beach, rebuilt here with its long pier, marina edge and open Atlantic horizon.",
  },
  {
    id: "casa-casuarina",
    name: "Casa Casuarina",
    district: "Ocean Drive",
    position: new THREE.Vector3(5.5, 1, -14),
    description: "A voxel tribute to the Versace mansion on Ocean Drive, with a courtyard, palms and a brighter facade than the hotels around it.",
  },
  {
    id: "ocean-drive",
    name: "Ocean Drive Strip",
    district: "Ocean Drive",
    position: new THREE.Vector3(11, 1, 2),
    description: "Pastel art deco frontage, neon marquees and the Lummus Park median define the postcard view most people associate with South Beach.",
  },
  {
    id: "lummus-park",
    name: "Lummus Park Tower",
    district: "Beachfront",
    position: new THREE.Vector3(28, 1, -6),
    description: "The beach zone keeps the broad sand, lifeguard tower and palm-lined park that sit between Ocean Drive and the Atlantic.",
  },
  {
    id: "espanola-way",
    name: "Española Way",
    district: "Española Way",
    position: new THREE.Vector3(-2, 1, 12),
    description: "A tighter pedestrian lane with string lights and lower buildings, meant to feel more intimate and Mediterranean than the beachfront strip.",
  },
  {
    id: "lincoln-road",
    name: "Lincoln Road",
    district: "Lincoln Road",
    position: new THREE.Vector3(5, 1, 32),
    description: "This cross-axis promenade swaps ocean-facing hotels for retail blocks, sculpture and a central walkable spine.",
  },
];

const canvas = document.getElementById("viewport");
const minimap = document.getElementById("minimap");
const districtLabel = document.getElementById("district-label");
const moodLabel = document.getElementById("mood-label");
const postcardCount = document.getElementById("postcard-count");
const zonePill = document.getElementById("zone-pill");
const prompt = document.getElementById("prompt");
const promptTitle = document.getElementById("prompt-title");
const visitButton = document.getElementById("visit-button");
const mobileVisit = document.getElementById("mobile-visit");
const tourList = document.getElementById("tour-list");
const toast = document.getElementById("toast");
const intro = document.getElementById("intro");
const startButton = document.getElementById("start-button");
const postcard = document.getElementById("postcard");
const postcardTitle = document.getElementById("postcard-title");
const postcardDescription = document.getElementById("postcard-description");
const postcardDistrict = document.getElementById("postcard-district");
const closePostcard = document.getElementById("close-postcard");
const movePad = document.getElementById("move-pad");
const moveStick = document.getElementById("move-stick");
const lookPad = document.getElementById("look-pad");

const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: true,
  alpha: false,
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
renderer.setSize(window.innerWidth, window.innerHeight);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf6a76f);
scene.fog = new THREE.Fog(0xf3a46f, 56, 170);

const camera = new THREE.PerspectiveCamera(52, window.innerWidth / window.innerHeight, 0.1, 280);

const ambientLight = new THREE.HemisphereLight(0xffd9b3, 0x1e425c, 1.45);
scene.add(ambientLight);

const sunLight = new THREE.DirectionalLight(0xffe2be, 1.8);
sunLight.position.set(42, 64, 18);
scene.add(sunLight);

const fillLight = new THREE.DirectionalLight(0x8ef9ff, 0.65);
fillLight.position.set(-28, 20, -32);
scene.add(fillLight);

const world = new THREE.Group();
scene.add(world);

const clouds = [];
const waveBands = [];
const neonMaterials = [];
const landmarks = [];
const markers = [];
const obstacleRects = [];
const clock = new THREE.Clock();
const tempVector = new THREE.Vector3();

const state = {
  started: false,
  cameraYaw: Math.PI * 0.83,
  cameraPitch: 0.52,
  cameraDistance: 18,
  sprint: false,
  keys: {
    forward: false,
    backward: false,
    left: false,
    right: false,
  },
  joystick: { x: 0, y: 0 },
  lookDrag: null,
  mouseDrag: null,
  activeLandmark: null,
  discovered: new Set(),
  toastTimer: null,
  moodIndex: 0,
};

const MATERIALS = createMaterials();
buildWorld();
const player = createPlayer();
scene.add(player);

LANDMARKS.forEach((data) => {
  const entry = {
    ...data,
    discovered: false,
    marker: createMarker(data),
  };
  entry.marker.position.copy(data.position);
  world.add(entry.marker);
  landmarks.push(entry);
  markers.push(entry.marker);
});

renderTourList();
updatePostcardCount();

const currentCameraPos = new THREE.Vector3();
const desiredCameraPos = new THREE.Vector3();
const cameraTarget = new THREE.Vector3();
const moveDirection = new THREE.Vector3();
const rightDirection = new THREE.Vector3();
const nextPosition = new THREE.Vector3();
const lookOffset = new THREE.Vector3();

function createMaterials() {
  const mat = (color, options = {}) =>
    new THREE.MeshStandardMaterial({
      color,
      flatShading: true,
      roughness: 0.9,
      metalness: 0.03,
      ...options,
    });

  const neon = (color, intensity = 0.9, options = {}) => {
    const material = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: intensity,
      flatShading: true,
      roughness: 0.35,
      metalness: 0.08,
      ...options,
    });
    neonMaterials.push(material);
    return material;
  };

  return {
    sand: mat(0xf1cd8b),
    wetSand: mat(0xe5c07d),
    grass: mat(0x71bd74),
    darkerGrass: mat(0x4c8d56),
    ocean: new THREE.MeshStandardMaterial({
      color: 0x31bbf9,
      emissive: 0x0f5982,
      emissiveIntensity: 0.45,
      transparent: true,
      opacity: 0.88,
      roughness: 0.22,
      metalness: 0.16,
      flatShading: true,
    }),
    bay: new THREE.MeshStandardMaterial({
      color: 0x2284b8,
      emissive: 0x0d3a53,
      emissiveIntensity: 0.3,
      transparent: true,
      opacity: 0.86,
      roughness: 0.28,
      metalness: 0.12,
      flatShading: true,
    }),
    foam: neon(0xb8feff, 0.9),
    road: mat(0x2f4156),
    lane: neon(0xfff7d6, 0.4),
    boardwalk: mat(0xb67f4b),
    sidewalk: mat(0xf0d3bb),
    baywalk: mat(0xd5cab8),
    hotelPink: mat(0xff99ad),
    hotelMint: mat(0x7fe7d7),
    hotelCream: mat(0xf8efd2),
    hotelLavender: mat(0xcfb0ff),
    hotelPeach: mat(0xffc497),
    hotelBlue: mat(0x95d7ff),
    towerBlue: mat(0xb7dff9),
    towerWhite: mat(0xf8fbff),
    glass: neon(0xc4f7ff, 0.25, { transparent: true, opacity: 0.92 }),
    neonCyan: neon(0x7ef7ff, 1.1),
    neonMagenta: neon(0xff71d8, 1.1),
    neonAmber: neon(0xffcc73, 0.95),
    roof: mat(0xfff3dd),
    darkRoof: mat(0x4c4054),
    palmTrunk: mat(0x8d5d35),
    palmLeaf: mat(0x2fa55f),
    white: mat(0xfefefe),
    dark: mat(0x25334a),
    marinaDeck: mat(0xc49365),
    sculpture: neon(0xb6ffdd, 0.6),
    skyline: mat(0x20314a),
    billboard: neon(0x94ffff, 0.6),
    avatarSkin: mat(0xf0b48a),
    avatarShirt: neon(0xff69d4, 0.8),
    avatarShorts: mat(0x38bdd8),
    avatarShoe: mat(0x222c3c),
    skateboard: neon(0x98f9ff, 0.55),
  };
}

function addBox(group, x, y, z, width, height, depth, material) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material);
  mesh.position.set(x, y + height / 2, z);
  group.add(mesh);
  return mesh;
}

function addObstacle(x, z, width, depth, padding = 0.7) {
  obstacleRects.push({
    minX: x - width / 2 - padding,
    maxX: x + width / 2 + padding,
    minZ: z - depth / 2 - padding,
    maxZ: z + depth / 2 + padding,
  });
}

function createLabelSprite(text, borderColor) {
  const canvasTexture = document.createElement("canvas");
  canvasTexture.width = 512;
  canvasTexture.height = 128;
  const ctx = canvasTexture.getContext("2d");
  ctx.clearRect(0, 0, canvasTexture.width, canvasTexture.height);
  roundRect(ctx, 8, 12, 496, 104, 28);
  ctx.fillStyle = "rgba(8, 12, 24, 0.82)";
  ctx.fill();
  ctx.lineWidth = 6;
  ctx.strokeStyle = borderColor;
  ctx.stroke();
  ctx.font = '700 60px "Space Grotesk"';
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = "#f7fbff";
  ctx.fillText(text, 256, 66);
  const texture = new THREE.CanvasTexture(canvasTexture);
  texture.needsUpdate = true;
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(11, 2.75, 1);
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

function createPlayer() {
  const avatar = new THREE.Group();
  addBox(avatar, 0, 0, 0, 1.2, 0.35, 2.5, MATERIALS.skateboard);
  addBox(avatar, 0, 0.35, 0.4, 1.2, 0.6, 0.65, MATERIALS.avatarShorts);
  addBox(avatar, 0, 1, 0.5, 1.25, 1.35, 0.75, MATERIALS.avatarShirt);
  addBox(avatar, 0, 2.02, 0.5, 1.05, 1.05, 1.05, MATERIALS.avatarSkin);
  addBox(avatar, -0.34, 0.06, 0.95, 0.38, 0.3, 0.72, MATERIALS.avatarShoe);
  addBox(avatar, 0.34, 0.06, 0.95, 0.38, 0.3, 0.72, MATERIALS.avatarShoe);
  addBox(avatar, -0.18, 2.12, 1.02, 0.16, 0.16, 0.16, MATERIALS.dark);
  addBox(avatar, 0.18, 2.12, 1.02, 0.16, 0.16, 0.16, MATERIALS.dark);
  avatar.position.set(18, 0, -46);
  return avatar;
}

function createMarker(data) {
  const marker = new THREE.Group();
  addBox(marker, 0, 0, 0, 0.9, 1, 0.9, MATERIALS.neonCyan);
  addBox(marker, 0, 1.25, 0, 0.35, 1.6, 0.35, MATERIALS.neonMagenta);
  addBox(marker, 0, 3.2, 0, 1.1, 0.3, 1.1, MATERIALS.neonAmber);
  const label = createLabelSprite(data.name, "#7ef7ff");
  label.position.set(0, 6, 0);
  marker.add(label);
  return marker;
}

function addPalm(group, x, z, height = 5.5) {
  addBox(group, x, 0.7, z, 0.6, height, 0.6, MATERIALS.palmTrunk);
  const crownY = height + 1.2;
  addBox(group, x, crownY, z, 2.8, 0.35, 0.9, MATERIALS.palmLeaf);
  addBox(group, x, crownY, z, 0.9, 0.35, 2.8, MATERIALS.palmLeaf);
  addBox(group, x + 0.85, crownY - 0.25, z + 0.2, 1.9, 0.25, 0.55, MATERIALS.palmLeaf);
  addBox(group, x - 0.85, crownY - 0.25, z - 0.2, 1.9, 0.25, 0.55, MATERIALS.palmLeaf);
}

function addUmbrella(group, x, z, colorMaterial) {
  addBox(group, x, 0.35, z, 0.14, 1.2, 0.14, MATERIALS.dark);
  addBox(group, x, 1.55, z, 1.8, 0.2, 1.8, colorMaterial);
}

function addLifeguardTower(group, x, z) {
  addBox(group, x, 0.25, z, 2.8, 0.4, 2.8, MATERIALS.white);
  addBox(group, x, 0.65, z, 1.8, 0.8, 1.8, MATERIALS.hotelBlue);
  addBox(group, x, 1.5, z, 2.4, 0.3, 2.4, MATERIALS.neonAmber);
  addBox(group, x, 1.85, z, 2.6, 0.18, 2.6, MATERIALS.roof);
  addBox(group, x - 0.95, 0, z - 0.95, 0.22, 1, 0.22, MATERIALS.white);
  addBox(group, x + 0.95, 0, z - 0.95, 0.22, 1, 0.22, MATERIALS.white);
  addBox(group, x - 0.95, 0, z + 0.95, 0.22, 1, 0.22, MATERIALS.white);
  addBox(group, x + 0.95, 0, z + 0.95, 0.22, 1, 0.22, MATERIALS.white);
}

function addBoat(group, x, z, heading = 0) {
  const boat = new THREE.Group();
  addBox(boat, 0, 0.2, 0, 3.8, 0.45, 1.4, MATERIALS.white);
  addBox(boat, -0.4, 0.72, 0, 1.8, 0.6, 1, MATERIALS.hotelBlue);
  addBox(boat, 0.7, 0.5, 0, 1.1, 0.25, 0.9, MATERIALS.dark);
  boat.position.set(x, 0.15, z);
  boat.rotation.y = heading;
  group.add(boat);
}

function addRoadStripe(group, x, z, width, depth) {
  addBox(group, x, 0.66, z, width, 0.08, depth, MATERIALS.lane);
}

function addStringLights(group, startX, endX, z, height) {
  const bulbCount = 7;
  for (let index = 0; index < bulbCount; index += 1) {
    const t = index / (bulbCount - 1);
    const x = THREE.MathUtils.lerp(startX, endX, t);
    const y = height - Math.sin(t * Math.PI) * 0.8;
    const material = index % 2 === 0 ? MATERIALS.neonMagenta : MATERIALS.neonAmber;
    addBox(group, x, y, z, 0.22, 0.22, 0.22, material);
  }
}

function addCloud(x, y, z, scale = 1) {
  const cloud = new THREE.Group();
  addBox(cloud, 0, 0, 0, 7 * scale, 1.7 * scale, 3.2 * scale, MATERIALS.white);
  addBox(cloud, -2.2 * scale, 0.8 * scale, 0.4 * scale, 3.4 * scale, 1.8 * scale, 2.5 * scale, MATERIALS.white);
  addBox(cloud, 2.4 * scale, 0.6 * scale, 0.2 * scale, 4.1 * scale, 1.7 * scale, 2.8 * scale, MATERIALS.white);
  cloud.position.set(x, y, z);
  cloud.userData.originX = x;
  cloud.userData.speed = 1.8 + scale * 0.35;
  clouds.push(cloud);
  scene.add(cloud);
}

function buildWorld() {
  const ground = new THREE.Group();

  addBox(ground, -34, -0.35, -13, 32, 0.7, 140, MATERIALS.bay);
  addBox(ground, 53, -0.3, -12, 38, 0.6, 150, MATERIALS.ocean);
  addBox(ground, -9, -0.05, -13, 18, 0.5, 110, MATERIALS.baywalk);
  addBox(ground, 4, -0.05, -13, 8, 0.5, 110, MATERIALS.sidewalk);
  addBox(ground, 11, -0.06, -20, 6, 0.52, 96, MATERIALS.road);
  addBox(ground, 18, -0.05, -20, 8, 0.48, 96, MATERIALS.grass);
  addBox(ground, 23, -0.04, -20, 2, 0.5, 96, MATERIALS.boardwalk);
  addBox(ground, 29, -0.04, -20, 10, 0.52, 96, MATERIALS.sand);
  addBox(ground, 2, -0.02, 33, 40, 0.56, 10, MATERIALS.sidewalk);
  addBox(ground, 2, -0.03, 32, 32, 0.5, 5.8, MATERIALS.boardwalk);
  addBox(ground, -1, -0.02, 12, 16, 0.46, 7.5, MATERIALS.sidewalk);
  addBox(ground, 19, -0.05, -58, 10, 0.48, 10, MATERIALS.darkerGrass);
  addBox(ground, 35, -0.04, -58, 22, 0.45, 4.8, MATERIALS.boardwalk);
  addBox(ground, -13, -0.04, -58, 10, 0.48, 10, MATERIALS.marinaDeck);

  world.add(ground);

  for (let z = -60; z <= 18; z += 10) {
    addRoadStripe(world, 11, z, 0.5, 4);
  }
  for (let x = -10; x <= 12; x += 4) {
    addRoadStripe(world, x, 32, 0.45, 2.6);
  }

  buildHotels();
  buildCollinsRow();
  buildLincolnRoad();
  buildEspanolaWay();
  buildBeach();
  buildSouthPointe();
  buildBayline();
  buildSkyline();
  buildDistrictLabels();
  buildEnvironment();
}

function buildHotels() {
  const hotelRow = new THREE.Group();
  const hotelConfigs = [
    { x: 4, z: -34, width: 6.8, depth: 11, height: 6, body: MATERIALS.hotelMint, accent: MATERIALS.neonCyan },
    { x: 4, z: -14, width: 8.2, depth: 12, height: 7, body: MATERIALS.hotelCream, accent: MATERIALS.neonAmber, villa: true },
    { x: 4, z: 4, width: 6.8, depth: 13, height: 6.4, body: MATERIALS.hotelPink, accent: MATERIALS.neonMagenta },
    { x: 4, z: 22, width: 6.6, depth: 12, height: 8.3, body: MATERIALS.hotelLavender, accent: MATERIALS.neonCyan },
  ];

  hotelConfigs.forEach((config) => {
    const segment = new THREE.Group();
    addBox(segment, config.x, 0, config.z, config.width, config.height, config.depth, config.body);
    addBox(segment, config.x, config.height, config.z, config.width - 1.3, 1.1, config.depth - 2.2, config.body);
    addBox(segment, config.x, config.height + 1.05, config.z, config.width - 2.2, 0.5, config.depth - 3.6, MATERIALS.roof);
    addBox(segment, config.x + config.width / 2 - 0.32, 0.4, config.z, 0.24, config.height + 1.4, config.depth + 0.8, config.accent);
    addBox(segment, config.x + config.width / 2 - 0.95, 0.7, config.z, 0.18, config.height + 0.8, config.depth + 0.2, config.accent);

    for (let floor = 1; floor <= Math.floor(config.height); floor += 1) {
      for (let bay = -Math.floor(config.depth / 2) + 2; bay < config.depth / 2 - 1; bay += 2.2) {
        addBox(segment, config.x + config.width / 2 - 0.52, floor + 0.1, config.z + bay, 0.18, 0.9, 1, MATERIALS.glass);
      }
    }

    addBox(segment, config.x + config.width / 2 + 0.55, 0.28, config.z, 2.3, 0.58, config.depth - 1.5, config.accent);
    addBox(segment, config.x + config.width / 2 + 1.25, 0.8, config.z, 1.2, 1, config.depth * 0.42, MATERIALS.dark);

    if (config.villa) {
      addBox(segment, config.x - 1.8, 0.12, config.z, 2.2, 2.2, 4.4, MATERIALS.hotelPeach);
      addBox(segment, config.x - 2.1, 0.1, config.z - 3.2, 1.4, 1.8, 1.4, MATERIALS.neonAmber);
      addBox(segment, config.x - 2.1, 0.1, config.z + 3.2, 1.4, 1.8, 1.4, MATERIALS.neonAmber);
      addPalm(segment, config.x - 3.6, config.z - 2.8, 4.6);
      addPalm(segment, config.x - 3.5, config.z + 2.9, 4.6);
    }

    hotelRow.add(segment);
    addObstacle(config.x, config.z, config.width + 0.3, config.depth + 0.3);
  });

  addBox(hotelRow, 7.1, 0.18, 4, 1.1, 0.36, 73, MATERIALS.neonMagenta);
  addBox(hotelRow, 7.35, 0.2, -22, 0.35, 0.4, 20, MATERIALS.neonCyan);
  addBox(hotelRow, 7.35, 0.2, 18, 0.35, 0.4, 20, MATERIALS.neonCyan);

  world.add(hotelRow);
}

function buildCollinsRow() {
  const collins = new THREE.Group();
  const towers = [
    { x: -4.8, z: -30, height: 16, depth: 12, width: 8.2, body: MATERIALS.towerWhite },
    { x: -5.6, z: -4, height: 14, depth: 10, width: 7, body: MATERIALS.towerBlue },
    { x: -4.2, z: 22, height: 18, depth: 13, width: 8.8, body: MATERIALS.towerWhite },
  ];

  towers.forEach((tower) => {
    addBox(collins, tower.x, 0, tower.z, tower.width, tower.height, tower.depth, tower.body);
    addBox(collins, tower.x, tower.height, tower.z, tower.width - 1.4, 1, tower.depth - 1.6, MATERIALS.roof);
    addBox(collins, tower.x + tower.width / 2 - 0.32, 0.3, tower.z, 0.22, tower.height + 1.5, tower.depth + 0.5, MATERIALS.neonCyan);
    for (let floor = 1; floor <= tower.height - 1; floor += 2) {
      for (let bay = -tower.depth / 2 + 1.4; bay <= tower.depth / 2 - 1.4; bay += 2.4) {
        addBox(collins, tower.x + tower.width / 2 - 0.55, floor + 0.2, tower.z + bay, 0.18, 1.1, 1.2, MATERIALS.glass);
      }
    }
    addObstacle(tower.x, tower.z, tower.width + 0.5, tower.depth + 0.5);
  });

  addPalm(collins, -11.2, -42, 5.2);
  addPalm(collins, -11.2, -14, 5.4);
  addPalm(collins, -11.2, 12, 5.4);
  addPalm(collins, -11.2, 34, 5.4);

  world.add(collins);
}

function buildLincolnRoad() {
  const lincoln = new THREE.Group();
  const shopDepth = 4.2;
  const shopWidth = 5.4;
  for (let x = -8; x <= 14; x += 7) {
    addBox(lincoln, x, 0, 26.5, shopWidth, 4, shopDepth, MATERIALS.hotelPeach);
    addBox(lincoln, x, 0, 37.5, shopWidth, 4, shopDepth, MATERIALS.hotelBlue);
    addBox(lincoln, x, 1.2, 28.4, shopWidth - 0.8, 1.2, 0.3, MATERIALS.glass);
    addBox(lincoln, x, 1.2, 35.6, shopWidth - 0.8, 1.2, 0.3, MATERIALS.glass);
    addBox(lincoln, x, 3.8, 28.5, shopWidth + 0.2, 0.26, 0.45, MATERIALS.neonAmber);
    addBox(lincoln, x, 3.8, 35.5, shopWidth + 0.2, 0.26, 0.45, MATERIALS.neonCyan);
    addObstacle(x, 26.5, shopWidth + 0.2, shopDepth + 0.2);
    addObstacle(x, 37.5, shopWidth + 0.2, shopDepth + 0.2);
  }

  addPalm(lincoln, -4, 32, 4.8);
  addPalm(lincoln, 4, 32, 5);
  addPalm(lincoln, 12, 32, 4.9);
  addBox(lincoln, 5.4, 0.15, 32, 1.2, 3.1, 1.2, MATERIALS.sculpture);
  addBox(lincoln, 5.4, 3.2, 32, 2.8, 0.38, 0.8, MATERIALS.sculpture);

  world.add(lincoln);
}

function buildEspanolaWay() {
  const alley = new THREE.Group();
  const facades = [
    { x: -6, z: 9.3, color: MATERIALS.hotelCream },
    { x: -2, z: 14.8, color: MATERIALS.hotelPink },
    { x: 2.5, z: 10.8, color: MATERIALS.hotelMint },
  ];

  facades.forEach((item) => {
    addBox(alley, item.x, 0, item.z, 3.6, 4.2, 4.2, item.color);
    addBox(alley, item.x, 3.95, item.z, 3.2, 0.35, 4.2, MATERIALS.neonAmber);
    addBox(alley, item.x, 1.2, item.z + 2.05, 2.4, 1.25, 0.3, MATERIALS.glass);
    addObstacle(item.x, item.z, 3.7, 4.3);
  });

  addStringLights(alley, -8, 4, 8.2, 5.8);
  addStringLights(alley, -8, 4, 15.8, 5.6);
  addPalm(alley, -9.2, 12, 4.4);
  addPalm(alley, 5, 12, 4.4);

  world.add(alley);
}

function buildBeach() {
  const beach = new THREE.Group();
  for (let z = -54; z <= 20; z += 10) {
    addPalm(beach, 16, z, 5.6);
    addPalm(beach, 20.5, z + 3.2, 5.2);
  }

  addLifeguardTower(beach, 28, -30);
  addLifeguardTower(beach, 28, -6);
  addLifeguardTower(beach, 28, 18);

  const umbrellaMaterials = [MATERIALS.neonMagenta, MATERIALS.neonAmber, MATERIALS.neonCyan];
  let umbrellaIndex = 0;
  for (let z = -48; z <= 22; z += 8) {
    addUmbrella(beach, 31.5, z, umbrellaMaterials[umbrellaIndex % umbrellaMaterials.length]);
    addUmbrella(beach, 26.8, z + 2.5, umbrellaMaterials[(umbrellaIndex + 1) % umbrellaMaterials.length]);
    umbrellaIndex += 1;
  }

  for (let z = -68; z <= 42; z += 6) {
    const band = addBox(beach, 40.8, -0.15, z, 13.5, 0.18, 2.2, MATERIALS.foam);
    waveBands.push({ mesh: band, baseY: band.position.y, phase: z * 0.14 });
  }

  world.add(beach);
}

function buildSouthPointe() {
  const south = new THREE.Group();
  addPalm(south, 16.5, -61.8, 5.4);
  addPalm(south, 21.2, -54.8, 5.4);
  addPalm(south, 15.4, -53.8, 5.4);
  addBoat(south, -13.2, -56, Math.PI * 0.25);
  addBoat(south, -10.6, -61.5, Math.PI * 0.16);
  addBoat(south, -7.4, -55.5, Math.PI * 0.32);

  addBox(south, 35.2, 0.15, -58, 22, 0.38, 2.8, MATERIALS.marinaDeck);
  addBox(south, 46.2, 1.1, -58, 2.6, 2.2, 2.6, MATERIALS.white);
  addBox(south, 46.2, 3.15, -58, 1.1, 2, 1.1, MATERIALS.neonCyan);

  world.add(south);
}

function buildBayline() {
  const bayline = new THREE.Group();
  addBox(bayline, -16.4, 0.12, -13, 0.4, 1.2, 104, MATERIALS.neonCyan);
  addBox(bayline, -14.8, 0.15, -18, 2.5, 0.4, 60, MATERIALS.lane);
  addRoadStripe(bayline, -14.8, -40, 1.6, 3.5);
  addRoadStripe(bayline, -14.8, -8, 1.6, 3.5);
  addRoadStripe(bayline, -14.8, 24, 1.6, 3.5);
  world.add(bayline);
}

function buildSkyline() {
  const skyline = new THREE.Group();
  const blocks = [
    { x: -45, z: -18, w: 6, d: 10, h: 18 },
    { x: -40, z: 4, w: 8, d: 12, h: 24 },
    { x: -46, z: 18, w: 5, d: 9, h: 14 },
    { x: -38, z: 28, w: 7, d: 10, h: 20 },
    { x: -50, z: 30, w: 4, d: 7, h: 11 },
  ];

  blocks.forEach((block) => {
    addBox(skyline, block.x, 0, block.z, block.w, block.h, block.d, MATERIALS.skyline);
    for (let y = 2; y < block.h - 1; y += 3) {
      addBox(skyline, block.x + block.w / 2 - 0.18, y, block.z - 2, 0.08, 1.1, 0.8, MATERIALS.neonCyan);
      addBox(skyline, block.x + block.w / 2 - 0.18, y, block.z + 2, 0.08, 1.1, 0.8, MATERIALS.neonMagenta);
    }
  });

  addBox(skyline, -29, 0.1, 26, 22, 0.5, 1.8, MATERIALS.boardwalk);
  addBox(skyline, -32, 1.4, 26, 12, 2.8, 0.8, MATERIALS.dark);
  world.add(skyline);
}

function buildDistrictLabels() {
  const labels = new THREE.Group();
  const oceanDriveLabel = createLabelSprite("Ocean Drive", "#ff71d8");
  oceanDriveLabel.position.set(13, 7.4, 2);
  labels.add(oceanDriveLabel);

  const lincolnLabel = createLabelSprite("Lincoln Road", "#7ef7ff");
  lincolnLabel.position.set(5, 7, 32);
  labels.add(lincolnLabel);

  const southLabel = createLabelSprite("South Pointe", "#ffd28f");
  southLabel.position.set(34, 7.2, -58);
  labels.add(southLabel);

  world.add(labels);
}

function buildEnvironment() {
  addCloud(16, 30, -10, 1.5);
  addCloud(42, 34, -36, 1.15);
  addCloud(-6, 28, 18, 1.2);
  addCloud(28, 33, 34, 1.4);

  const sun = new THREE.Mesh(
    new THREE.SphereGeometry(6, 16, 16),
    new THREE.MeshBasicMaterial({ color: 0xffda86 })
  );
  sun.position.set(58, 44, -28);
  scene.add(sun);
}

function renderTourList() {
  tourList.innerHTML = "";
  landmarks.forEach((item) => {
    const li = document.createElement("li");
    const copy = document.createElement("div");
    copy.className = "tour-item-copy";
    const title = document.createElement("strong");
    title.textContent = item.name;
    const district = document.createElement("span");
    district.textContent = item.district;
    copy.appendChild(title);
    copy.appendChild(district);

    const stateTag = document.createElement("span");
    stateTag.className = `tour-state${item.discovered ? " done" : ""}`;
    stateTag.textContent = item.discovered ? "Visited" : "Pending";

    li.appendChild(copy);
    li.appendChild(stateTag);
    tourList.appendChild(li);
  });
}

function updatePostcardCount() {
  postcardCount.textContent = String(state.discovered.size);
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => {
    toast.classList.remove("visible");
  }, 2200);
}

function openPostcard(entry) {
  postcardTitle.textContent = entry.name;
  postcardDescription.textContent = entry.description;
  postcardDistrict.textContent = entry.district;
  postcard.classList.remove("hidden");
}

function closePostcardPanel() {
  postcard.classList.add("hidden");
}

function currentDistrict() {
  const { x, z } = player.position;
  if (z < -46) {
    return { label: "South Pointe", zone: "South Pointe pier" };
  }
  if (z > 26 && z < 38) {
    return { label: "Lincoln Road", zone: "Lincoln Road promenade" };
  }
  if (x < 0 && z > 7 && z < 18) {
    return { label: "Española Way", zone: "Española Way lane" };
  }
  if (x > 22) {
    return { label: "Beachfront", zone: "Atlantic beach" };
  }
  if (x > 8 && x < 16) {
    return { label: "Ocean Drive", zone: "Ocean Drive strip" };
  }
  if (x < 0) {
    return { label: "Collins Avenue", zone: "Collins skyline" };
  }
  return { label: "South Beach", zone: "Miami Beach core" };
}

function interactWithLandmark() {
  const entry = state.activeLandmark;
  if (!entry) {
    return;
  }
  if (!entry.discovered) {
    entry.discovered = true;
    state.discovered.add(entry.id);
    updatePostcardCount();
    renderTourList();
    showToast(`Postcard collected: ${entry.name}`);
  } else {
    showToast(`Back at ${entry.name}`);
  }
  openPostcard(entry);
}

function updatePrompt() {
  let nearest = null;
  let nearestDistance = Infinity;
  landmarks.forEach((entry) => {
    const distance = player.position.distanceTo(entry.position);
    if (distance < 6.2 && distance < nearestDistance) {
      nearest = entry;
      nearestDistance = distance;
    }
  });

  state.activeLandmark = nearest;

  if (nearest) {
    prompt.hidden = false;
    promptTitle.textContent = nearest.discovered ? `Revisit ${nearest.name}` : `Visit ${nearest.name}`;
    visitButton.hidden = false;
    mobileVisit.hidden = false;
  } else {
    prompt.hidden = true;
    visitButton.hidden = true;
    mobileVisit.hidden = true;
  }
}

function isWalkable(x, z) {
  const onPier = x > 23 && x < 46 && z > -60.8 && z < -55.2;
  if (z < WORLD.minZ || z > WORLD.maxZ) {
    return false;
  }
  if (x < WORLD.minX || x > 34) {
    return onPier;
  }
  for (const rect of obstacleRects) {
    if (x > rect.minX && x < rect.maxX && z > rect.minZ && z < rect.maxZ) {
      return false;
    }
  }
  return true;
}

function applyMovement(delta) {
  let inputX = state.joystick.x;
  let inputZ = -state.joystick.y;
  if (state.keys.left) {
    inputX -= 1;
  }
  if (state.keys.right) {
    inputX += 1;
  }
  if (state.keys.forward) {
    inputZ += 1;
  }
  if (state.keys.backward) {
    inputZ -= 1;
  }

  moveDirection.set(0, 0, 0);
  rightDirection.set(0, 0, 0);

  if (inputX !== 0 || inputZ !== 0) {
    const inputVector = new THREE.Vector2(inputX, inputZ);
    if (inputVector.lengthSq() > 1) {
      inputVector.normalize();
    }

    const forwardYaw = state.cameraYaw + Math.PI;
    moveDirection.set(Math.sin(forwardYaw), 0, Math.cos(forwardYaw));
    rightDirection.set(Math.sin(forwardYaw - Math.PI / 2), 0, Math.cos(forwardYaw - Math.PI / 2));

    tempVector.copy(moveDirection).multiplyScalar(inputVector.y);
    tempVector.addScaledVector(rightDirection, inputVector.x);

    const speed = state.sprint ? 9.5 : 6.25;
    nextPosition.copy(player.position).addScaledVector(tempVector, speed * delta);

    if (isWalkable(nextPosition.x, player.position.z)) {
      player.position.x = nextPosition.x;
    }
    if (isWalkable(player.position.x, nextPosition.z)) {
      player.position.z = nextPosition.z;
    }

    player.rotation.y = Math.atan2(tempVector.x, tempVector.z);
    const sway = Math.sin(clock.elapsedTime * 10) * 0.07;
    player.position.y = Math.abs(sway) * 0.2;
  } else {
    player.position.y = THREE.MathUtils.lerp(player.position.y, 0, 0.12);
  }
}

function updateCamera(delta) {
  cameraTarget.set(player.position.x, 4.6, player.position.z);

  const pitchCos = Math.cos(state.cameraPitch);
  lookOffset.set(
    Math.sin(state.cameraYaw) * pitchCos * state.cameraDistance,
    Math.sin(state.cameraPitch) * state.cameraDistance + 3.2,
    Math.cos(state.cameraYaw) * pitchCos * state.cameraDistance
  );

  desiredCameraPos.copy(cameraTarget).add(lookOffset);
  currentCameraPos.lerp(desiredCameraPos, 1 - Math.exp(-delta * 7));
  camera.position.copy(currentCameraPos);
  camera.lookAt(cameraTarget);
}

function updateNeonAndSky(elapsed) {
  const pulse = (Math.sin(elapsed * 1.7) + 1) * 0.5;
  neonMaterials.forEach((material, index) => {
    material.emissiveIntensity = 0.45 + pulse * 0.7 + (index % 3) * 0.04;
  });

  waveBands.forEach((entry, index) => {
    entry.mesh.position.y = entry.baseY + Math.sin(elapsed * 1.8 + entry.phase + index * 0.3) * 0.08;
  });

  markers.forEach((marker, index) => {
    marker.position.y = LANDMARKS[index].position.y + Math.sin(elapsed * 2.2 + index) * 0.45;
    marker.rotation.y += 0.005;
  });

  clouds.forEach((cloud) => {
    cloud.position.x += cloud.userData.speed * 0.01;
    if (cloud.position.x > 82) {
      cloud.position.x = -60;
    }
  });

  const moodPhase = Math.floor((elapsed / 12) % 3);
  const moods = ["Golden hour", "Neon dusk", "Blue twilight"];
  if (state.moodIndex !== moodPhase) {
    state.moodIndex = moodPhase;
    moodLabel.textContent = moods[moodPhase];
  }
}

function updateHud() {
  const location = currentDistrict();
  districtLabel.textContent = location.label;
  zonePill.textContent = location.zone;
}

function drawMinimap() {
  const ctx = minimap.getContext("2d");
  const width = minimap.width;
  const height = minimap.height;
  const mapX = (value) => ((value - WORLD.minX) / (WORLD.maxX - WORLD.minX)) * (width - 28) + 14;
  const mapZ = (value) => ((value - WORLD.minZ) / (WORLD.maxZ - WORLD.minZ)) * (height - 28) + 14;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#071422";
  ctx.fillRect(0, 0, width, height);

  ctx.fillStyle = "#15527f";
  ctx.fillRect(mapX(34), 8, width - mapX(34) - 8, height - 16);
  ctx.fillStyle = "#103f62";
  ctx.fillRect(8, 8, mapX(-18) - 8, height - 16);

  ctx.fillStyle = "#f2cf8f";
  ctx.fillRect(mapX(24), mapZ(-68), mapX(34) - mapX(24), mapZ(28) - mapZ(-68));

  ctx.fillStyle = "#73bf73";
  ctx.fillRect(mapX(14), mapZ(-68), mapX(22) - mapX(14), mapZ(28) - mapZ(-68));
  ctx.fillRect(mapX(14), mapZ(-68), mapX(24) - mapX(14), mapZ(-52) - mapZ(-68));

  ctx.fillStyle = "#37495e";
  ctx.fillRect(mapX(8), mapZ(-68), mapX(14) - mapX(8), mapZ(28) - mapZ(-68));

  ctx.fillStyle = "#be8754";
  ctx.fillRect(mapX(-14), mapZ(29), mapX(22) - mapX(-14), mapZ(35) - mapZ(29));
  ctx.fillRect(mapX(24), mapZ(-60), mapX(46) - mapX(24), mapZ(-56) - mapZ(-60));

  ctx.strokeStyle = "rgba(255,255,255,0.12)";
  ctx.lineWidth = 1;
  for (let x = WORLD.minX; x <= 34; x += 8) {
    ctx.beginPath();
    ctx.moveTo(mapX(x), 12);
    ctx.lineTo(mapX(x), height - 12);
    ctx.stroke();
  }

  ctx.fillStyle = "rgba(255,255,255,0.8)";
  ctx.font = '700 12px "Space Grotesk"';
  ctx.fillText("ATLANTIC", width - 64, 24);
  ctx.fillText("BAY", 18, 24);
  ctx.fillText("OCEAN DR", mapX(8), mapZ(-6));
  ctx.fillText("LINCOLN RD", mapX(-2), mapZ(32));

  landmarks.forEach((entry) => {
    ctx.beginPath();
    ctx.arc(mapX(entry.position.x), mapZ(entry.position.z), 4, 0, Math.PI * 2);
    ctx.fillStyle = entry.discovered ? "#88ffcf" : "#ff71d8";
    ctx.fill();
  });

  ctx.beginPath();
  ctx.arc(mapX(player.position.x), mapZ(player.position.z), 5, 0, Math.PI * 2);
  ctx.fillStyle = "#ffffff";
  ctx.fill();
  ctx.strokeStyle = "#071422";
  ctx.lineWidth = 2;
  ctx.stroke();
}

function animate() {
  requestAnimationFrame(animate);
  const delta = Math.min(clock.getDelta(), 0.033);
  const elapsed = clock.elapsedTime;

  if (state.started) {
    applyMovement(delta);
    updatePrompt();
    updateHud();
  }

  updateCamera(delta);
  updateNeonAndSky(elapsed);
  drawMinimap();
  renderer.render(scene, camera);
}

function resize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

function clampPitch() {
  state.cameraPitch = THREE.MathUtils.clamp(state.cameraPitch, 0.26, 0.84);
}

function onKeyChange(event, pressed) {
  const { code } = event;
  if (code === "KeyW" || code === "ArrowUp") {
    state.keys.forward = pressed;
  }
  if (code === "KeyS" || code === "ArrowDown") {
    state.keys.backward = pressed;
  }
  if (code === "KeyA" || code === "ArrowLeft") {
    state.keys.left = pressed;
  }
  if (code === "KeyD" || code === "ArrowRight") {
    state.keys.right = pressed;
  }
  if (code === "ShiftLeft" || code === "ShiftRight") {
    state.sprint = pressed;
  }
  if (pressed && code === "KeyE") {
    interactWithLandmark();
  }
}

window.addEventListener("resize", resize);
window.addEventListener("keydown", (event) => onKeyChange(event, true));
window.addEventListener("keyup", (event) => onKeyChange(event, false));

canvas.addEventListener("pointerdown", (event) => {
  if (!state.started || event.pointerType === "touch") {
    return;
  }
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

canvas.addEventListener("wheel", (event) => {
  state.cameraDistance = THREE.MathUtils.clamp(state.cameraDistance + event.deltaY * 0.012, 10, 24);
});

visitButton.addEventListener("click", interactWithLandmark);
mobileVisit.addEventListener("click", interactWithLandmark);
closePostcard.addEventListener("click", closePostcardPanel);

startButton.addEventListener("click", () => {
  state.started = true;
  intro.classList.remove("open");
  showToast("Welcome to Miami Beach.");
});

function setupMovePad() {
  const radius = 42;
  const center = { x: 0, y: 0 };

  const updateStick = (clientX, clientY) => {
    const rect = movePad.getBoundingClientRect();
    center.x = rect.left + rect.width / 2;
    center.y = rect.top + rect.height / 2;
    let dx = clientX - center.x;
    let dy = clientY - center.y;
    const distance = Math.hypot(dx, dy);
    if (distance > radius) {
      const scale = radius / distance;
      dx *= scale;
      dy *= scale;
    }
    moveStick.style.transform = `translate(${dx}px, ${dy}px)`;
    state.joystick.x = dx / radius;
    state.joystick.y = dy / radius;
  };

  movePad.addEventListener("pointerdown", (event) => {
    movePad.setPointerCapture(event.pointerId);
    updateStick(event.clientX, event.clientY);
  });

  movePad.addEventListener("pointermove", (event) => {
    if (event.pressure === 0 && event.pointerType !== "touch") {
      return;
    }
    if (!movePad.hasPointerCapture(event.pointerId)) {
      return;
    }
    updateStick(event.clientX, event.clientY);
  });

  const reset = () => {
    moveStick.style.transform = "translate(0px, 0px)";
    state.joystick.x = 0;
    state.joystick.y = 0;
  };

  movePad.addEventListener("pointerup", (event) => {
    movePad.releasePointerCapture(event.pointerId);
    reset();
  });
  movePad.addEventListener("pointercancel", reset);
}

function setupLookPad() {
  lookPad.addEventListener("pointerdown", (event) => {
    lookPad.setPointerCapture(event.pointerId);
    state.lookDrag = { x: event.clientX, y: event.clientY };
  });

  lookPad.addEventListener("pointermove", (event) => {
    if (!state.lookDrag || !lookPad.hasPointerCapture(event.pointerId)) {
      return;
    }
    const deltaX = event.clientX - state.lookDrag.x;
    const deltaY = event.clientY - state.lookDrag.y;
    state.lookDrag.x = event.clientX;
    state.lookDrag.y = event.clientY;
    state.cameraYaw -= deltaX * 0.01;
    state.cameraPitch -= deltaY * 0.008;
    clampPitch();
  });

  const release = (event) => {
    if (lookPad.hasPointerCapture(event.pointerId)) {
      lookPad.releasePointerCapture(event.pointerId);
    }
    state.lookDrag = null;
  };

  lookPad.addEventListener("pointerup", release);
  lookPad.addEventListener("pointercancel", release);
}

setupMovePad();
setupLookPad();
resize();
updateHud();
updatePrompt();
drawMinimap();
animate();
