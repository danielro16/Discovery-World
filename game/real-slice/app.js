import { realSliceBusinesses } from "./businesses.js";

const mapEl = document.getElementById("map");
const queueList = document.getElementById("queue-list");
const detailEmpty = document.getElementById("detail-empty");
const detailContent = document.getElementById("detail-content");
const businessNameEl = document.getElementById("business-name");
const businessCategoryEl = document.getElementById("business-category");
const businessCompletenessEl = document.getElementById("business-completeness");
const businessDistanceEl = document.getElementById("business-distance");
const businessAddressEl = document.getElementById("business-address");
const knownPhoneEl = document.getElementById("known-phone");
const knownWebsiteEl = document.getElementById("known-website");
const knownHoursEl = document.getElementById("known-hours");
const factsList = document.getElementById("facts-list");
const feedList = document.getElementById("feed-list");
const nearbyCountEl = document.getElementById("nearby-count");
const verifiedCountEl = document.getElementById("verified-count");
const actionsCountEl = document.getElementById("actions-count");
const visitPrompt = document.getElementById("visit-prompt");
const visitCopy = document.getElementById("visit-copy");
const visitButton = document.getElementById("visit-button");
const focusButton = document.getElementById("focus-button");
const businessSourceEl = document.getElementById("business-source");
const businessLicenseEl = document.getElementById("business-license");
const toast = document.getElementById("toast");

const CATEGORY_META = {
  restaurant: { label: "Restaurant", accent: "low" },
  cafe: { label: "Cafe", accent: "medium" },
  gym: { label: "Gym", accent: "high" },
};

const state = {
  selectedId: null,
  activeNearbyId: null,
  move: { forward: false, backward: false, left: false, right: false, fast: false },
  feed: [
    { text: "Jules confirmed outdoor seating at News Cafe.", time: "2m ago" },
    { text: "Mia flagged missing hours at Yoga Lab.", time: "5m ago" },
    { text: "Andre verified day pass info for Crunch Fitness.", time: "8m ago" },
  ],
  toastTimer: null,
};

const businesses = realSliceBusinesses.map((business) => ({
  ...business,
  baseCompleteness: business.completeness,
  marker: null,
  markerEl: null,
  distance: Infinity,
}));

const map = new maplibregl.Map({
  container: mapEl,
  style: "https://tiles.openfreemap.org/styles/liberty",
  center: [-80.1324, 25.7807],
  zoom: 16.55,
  pitch: 58,
  bearing: -18,
});

map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
map.dragRotate.disable();
map.touchZoomRotate.disableRotation();

map.on("load", () => {
  addSliceLayers();
  addBusinessMarkers();
  updateSpatialState();
  renderFeed();
});

map.on("move", updateSpatialState);
map.on("zoom", updateSpatialState);

function addSliceLayers() {
  const slicePolygon = {
    type: "Feature",
    properties: {},
    geometry: {
      type: "Polygon",
      coordinates: [[
        [-80.1428, 25.7760],
        [-80.1297, 25.7760],
        [-80.1297, 25.7866],
        [-80.1428, 25.7866],
        [-80.1428, 25.7760],
      ]],
    },
  };

  const routeLines = {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { color: "#7deeff", name: "Ocean Drive" },
        geometry: {
          type: "LineString",
          coordinates: [
            [-80.1305, 25.7772],
            [-80.1304, 25.7787],
            [-80.1303, 25.7802],
            [-80.1302, 25.7822],
            [-80.1300, 25.7856],
          ],
        },
      },
      {
        type: "Feature",
        properties: { color: "#ff78da", name: "Washington Ave" },
        geometry: {
          type: "LineString",
          coordinates: [
            [-80.1334, 25.7770],
            [-80.1330, 25.7794],
            [-80.1324, 25.7819],
            [-80.1320, 25.7842],
          ],
        },
      },
    ],
  };

  map.addSource("slice-area", { type: "geojson", data: slicePolygon });
  map.addLayer({
    id: "slice-fill",
    type: "fill",
    source: "slice-area",
    paint: {
      "fill-color": "#7deeff",
      "fill-opacity": 0.08,
    },
  });
  map.addLayer({
    id: "slice-outline",
    type: "line",
    source: "slice-area",
    paint: {
      "line-color": "#7deeff",
      "line-width": 2,
      "line-dasharray": [2, 2],
      "line-opacity": 0.55,
    },
  });

  map.addSource("slice-routes", { type: "geojson", data: routeLines });
  map.addLayer({
    id: "slice-routes-line",
    type: "line",
    source: "slice-routes",
    paint: {
      "line-color": ["get", "color"],
      "line-width": 4,
      "line-opacity": 0.7,
      "line-blur": 0.5,
    },
  });
}

function addBusinessMarkers() {
  businesses.forEach((business) => {
    const markerEl = document.createElement("button");
    markerEl.className = `marker ${statusClassFor(business)}`;
    markerEl.innerHTML = `
      <span class="marker-label">${business.name}</span>
      <span class="marker-beam"></span>
      <span class="marker-core"></span>
    `;
    markerEl.addEventListener("click", () => selectBusiness(business.id, true));

    const marker = new maplibregl.Marker({ element: markerEl, anchor: "bottom" })
      .setLngLat(business.coords)
      .addTo(map);

    business.marker = marker;
    business.markerEl = markerEl;
  });
}

function statusClassFor(business) {
  if (business.completeness < 45) {
    return "low";
  }
  if (business.completeness < 65) {
    return "medium";
  }
  return "high";
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

function updateSpatialState() {
  const center = map.getCenter();
  const centerCoords = [center.lng, center.lat];

  businesses.forEach((business) => {
    business.distance = haversineMeters(centerCoords, business.coords);
  });

  businesses.sort((first, second) => first.distance - second.distance);

  const nearby = businesses.filter((business) => business.distance < 95);
  nearbyCountEl.textContent = String(nearby.length);
  verifiedCountEl.textContent = String(totalVerifiedFacts());
  actionsCountEl.textContent = String(totalActions());

  const nearest = businesses[0];
  state.activeNearbyId = nearest && nearest.distance < 60 ? nearest.id : null;

  businesses.forEach((business) => {
    if (!business.markerEl) {
      return;
    }
    business.markerEl.className = `marker ${statusClassFor(business)}`;
    if (business.id === state.selectedId) {
      business.markerEl.classList.add("selected");
    }
    if (business.distance < 95) {
      business.markerEl.classList.add("nearby");
    }
  });

  renderQueue();
  renderPrompt();

  if (state.selectedId) {
    renderBusinessDetails(getBusiness(state.selectedId));
  }
}

function totalVerifiedFacts() {
  return businesses.reduce(
    (count, business) => count + business.facts.filter((fact) => fact.confirmations >= fact.target).length,
    0
  );
}

function totalActions() {
  return businesses.reduce(
    (count, business) => count + business.facts.reduce((sum, fact) => sum + fact.confirmations, 0),
    0
  );
}

function missingFactCount(business) {
  return business.facts.filter((fact) => fact.confirmations < fact.target).length;
}

function renderQueue() {
  const queueItems = businesses.slice(0, 6);
  queueList.innerHTML = "";

  queueItems.forEach((business) => {
    const item = document.createElement("button");
    item.className = `queue-item${business.id === state.selectedId ? " active" : ""}`;
    item.innerHTML = `
      <div class="queue-top">
        <span class="queue-title">${business.name}</span>
        <span class="queue-distance">${Math.round(business.distance)}m</span>
      </div>
      <div class="queue-bottom">
        <span class="queue-pending">${missingFactCount(business)} open facts</span>
        <span class="queue-badges">
          <span class="pill ${statusClassFor(business)}">${business.completeness}%</span>
          <span class="pill">${CATEGORY_META[business.category].label}</span>
        </span>
      </div>
    `;
    item.addEventListener("click", () => selectBusiness(business.id, true));
    queueList.appendChild(item);
  });
}

function getBusiness(id) {
  return businesses.find((business) => business.id === id) ?? null;
}

function selectBusiness(id, flyTo = false) {
  state.selectedId = id;
  const business = getBusiness(id);
  if (!business) {
    return;
  }

  if (flyTo) {
    map.easeTo({
      center: business.coords,
      duration: 900,
      zoom: Math.max(map.getZoom(), 16.7),
      pitch: 58,
      bearing: -18,
    });
  }

  renderQueue();
  renderBusinessDetails(business);
  updateSpatialState();
}

function renderBusinessDetails(business) {
  if (!business) {
    detailEmpty.classList.remove("hidden");
    detailContent.classList.add("hidden");
    return;
  }

  detailEmpty.classList.add("hidden");
  detailContent.classList.remove("hidden");

  businessNameEl.textContent = business.name;
  businessCategoryEl.textContent = CATEGORY_META[business.category].label;
  businessCompletenessEl.textContent = `${business.completeness}% complete`;
  businessDistanceEl.textContent = `${Math.round(business.distance)}m away`;
  businessAddressEl.textContent = business.address || "Address still needs cleanup from source data.";
  knownPhoneEl.textContent = business.fields.phone ? "Known" : "Missing";
  knownWebsiteEl.textContent = business.fields.website ? "Known" : "Missing";
  knownHoursEl.textContent = business.fields.hours ? "Known" : "Missing";
  businessSourceEl.textContent = `Source: ${business.source.toUpperCase()}`;
  businessLicenseEl.textContent = `License: ${business.sourceLicense}`;

  factsList.innerHTML = "";
  business.facts.forEach((fact) => {
    const verified = fact.confirmations >= fact.target;
    const card = document.createElement("div");
    card.className = "fact-card";
    const progress = Math.min(100, (fact.confirmations / fact.target) * 100);

    const options = fact.options
      .map(
        (option) =>
          `<button class="fact-option" data-business="${business.id}" data-fact="${fact.key}" data-value="${option}" ${verified ? "disabled" : ""}>${option}</button>`
      )
      .join("");

    card.innerHTML = `
      <div class="fact-top">
        <div>
          <div class="fact-title">${fact.label}</div>
          <div class="fact-copy">${fact.prompt}</div>
        </div>
        <span class="pill ${verified ? "high" : "medium"}">${verified ? "verified" : "needs input"}</span>
      </div>
      <div class="fact-progress">
        <span>${fact.confirmations}/${fact.target} confirmations</span>
        <span>${verified ? "Consensus reached" : "Community still verifying"}</span>
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

function submitFact(businessId, factKey, value) {
  const business = getBusiness(businessId);
  if (!business) {
    return;
  }

  const fact = business.facts.find((item) => item.key === factKey);
  if (!fact || fact.confirmations >= fact.target) {
    return;
  }

  fact.confirmations += 1;
  const justVerified = fact.confirmations >= fact.target;
  business.completeness = Math.min(100, business.completeness + (justVerified ? 8 : 3));

  if (["phone", "website", "hours"].includes(fact.key)) {
    business.fields[fact.key] = value !== "Unavailable";
  }

  state.feed.unshift({
    text: `You answered "${value}" for ${fact.label} at ${business.name}.`,
    time: "now",
  });
  state.feed = state.feed.slice(0, 8);

  renderFeed();
  renderBusinessDetails(business);
  renderQueue();
  updateSpatialState();
  showToast(justVerified ? `${fact.label} verified for ${business.name}` : `Answer submitted for ${fact.label}`);
}

function renderFeed() {
  feedList.innerHTML = "";
  state.feed.forEach((entry) => {
    const item = document.createElement("div");
    item.className = "feed-item";
    item.innerHTML = `
      <div class="feed-top">
        <span class="feed-title">${entry.text}</span>
        <span class="feed-time">${entry.time}</span>
      </div>
    `;
    feedList.appendChild(item);
  });
}

function renderPrompt() {
  const business = state.activeNearbyId ? getBusiness(state.activeNearbyId) : null;
  if (!business) {
    visitPrompt.classList.add("hidden");
    return;
  }

  visitPrompt.classList.remove("hidden");
  visitCopy.textContent = `${business.name} is inside the scan ring`;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => {
    toast.classList.remove("visible");
  }, 2200);
}

visitButton.addEventListener("click", () => {
  if (state.activeNearbyId) {
    selectBusiness(state.activeNearbyId, true);
  }
});

focusButton.addEventListener("click", () => {
  if (state.selectedId) {
    selectBusiness(state.selectedId, true);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.code === "KeyW" || event.code === "ArrowUp") state.move.forward = true;
  if (event.code === "KeyS" || event.code === "ArrowDown") state.move.backward = true;
  if (event.code === "KeyA" || event.code === "ArrowLeft") state.move.left = true;
  if (event.code === "KeyD" || event.code === "ArrowRight") state.move.right = true;
  if (event.code === "ShiftLeft" || event.code === "ShiftRight") state.move.fast = true;
  if (event.code === "KeyE" && state.activeNearbyId) selectBusiness(state.activeNearbyId, true);
});

document.addEventListener("keyup", (event) => {
  if (event.code === "KeyW" || event.code === "ArrowUp") state.move.forward = false;
  if (event.code === "KeyS" || event.code === "ArrowDown") state.move.backward = false;
  if (event.code === "KeyA" || event.code === "ArrowLeft") state.move.left = false;
  if (event.code === "KeyD" || event.code === "ArrowRight") state.move.right = false;
  if (event.code === "ShiftLeft" || event.code === "ShiftRight") state.move.fast = false;
});

function tickMovement() {
  const x = (state.move.right ? 1 : 0) - (state.move.left ? 1 : 0);
  const y = (state.move.backward ? 1 : 0) - (state.move.forward ? 1 : 0);

  if (x !== 0 || y !== 0) {
    const speed = state.move.fast ? 14 : 8;
    map.panBy([x * speed, y * speed], { animate: false });
  }

  requestAnimationFrame(tickMovement);
}

tickMovement();
