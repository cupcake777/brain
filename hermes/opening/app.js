import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

const $ = (id) => document.getElementById(id);
const viewport = $("viewport");
const bootFill = $("bootFill");
const bootText = $("bootText");
const bootLoader = $("loader");
const intro = $("intro");
const helpEl = $("help");
const speedEl = $("speed");
const distEl = $("dist");
const etimeEl = $("etime");
const laneEl = $("lane");
const clockEl = $("clock");
const nitroFill = $("nitroFill");
const pauseOverlay = $("pauseOverlay");
const pauseBtn = $("pauseBtn");
const resumeBtn = $("resumeBtn");
const exitBtn = $("exitBtn");
const menuBtn = $("menuBtn");
const reselectBtn = $("reselectBtn");
const selectScreen = $("selectScreen");
const startBtn = $("startBtn");
const openingError = $("openingError");
const titleChip = $("titleChip");
const modeChip = $("modeChip");
const speedUnit = $("speedUnit");
const boostLabel = $("boostLabel");
const laneLabel = $("laneLabel");
const introEyebrow = $("introEyebrow");
const introWordA = $("introWordA");
const introWordB = $("introWordB");
const introTag = $("introTag");
const introHint = $("introHint");
const footerLeft = $("footerLeft");
const footerRight = $("footerRight");

const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const isMobile = matchMedia("(max-width: 820px), (pointer: coarse)").matches;
let motionEnabled = !reduced;
let pauseReturnFocus = null;

const keys = { left: false, right: false, up: false, down: false, nitro: false };
const carState = {
  x: 0, // lane -1..1
  z: 0, // world z forward negative
  speed: 28, // m/s ~100km/h
  nitro: 1,
  nitroOn: false,
  distance: 0,
  yaw: 0,
  crash: 0,
  hitCd: 0,
  stunned: 0, // hard collision lock
  carLen: 3.4,
  carWidth: 1.8,
  flightY: 7,
  pitch: 0,
  gateCount: 0,
};

let renderer, scene, camera, composer, bloomPass, clock;
let carRoot, carMesh;
let roadMesh, stripeMeshes = [];
let skyMesh, cityMesh, sunMesh;
let buildingPool = [], palmPool = [], lightPool = [], trafficPool = [];
let templates = { car: null, palm: null, buildings: [], streetLight: null, wheel: null };
let startedAt = 0;
let introGone = false;
let roadScroll = 0;
let paused = false;
let pauseStartedAt = 0;
let pauseAccum = 0; // total paused ms, keep TIME honest
let worldRoot = null;
let assetsCache = null;
let selectedScene = "blade"; // v22: catalog opens on corridor mission matching boot wallpaper
let selectedVehicle = "spinner";
let selecting = true;
let launched = false;
let bladeTowerPool = [], bladeGatePool = [], bladeTrafficPool = [];
let bladeDeckPool = [];
let bladeHolograms = [], bladeRain = null, bladeRainData = null;
let bladeSearchlights = [], bladeFogSheets = [], bladeLandmark = null;
let bladeFarSlabPool = [];
let bladeGlintPool = [];
let bladeMaterials = null;
let bladeFacadeCache = [];
let bladePulse = 0;
let bladeHardwareFallback = false;
let bootPreview = false;
let bootPreviewScene = null; // "blade" | "sunset" — living wallpaper matches catalog pick
let bootCamT = 0;
const BOOT_LOOP_SEC = 10.5;
// v23: curved corridor path (rocktree-style sweeping turns, not infinite straight)
let pathBend = 0;          // current lateral bend offset (world X of corridor center)
let pathHeading = 0;       // yaw of corridor tangent (radians)
let pathBendTarget = 0;
let pathBendPhase = 0;
let bladeBillboardPool = [];
let adTextureCache = {}; // v24 photo billboard maps
// v25: hard free-air half-width (craft envelope ~±7.2m + margin)
const BLADE_AIR_HALF = 11.5;

const ROAD_HALF = 5.2;
const LANE_W = 3.2;
const EXIT_URL = "/"; // back to Brain homepage / other pages

function setBoot(p, label) {
  const pct = Math.max(0, Math.min(100, Math.round(p * 100)));
  if (bootFill) bootFill.style.width = pct + "%";
  if (bootText) bootText.textContent = label ? `${pct}% · ${label}` : pct + "%";
}

function addWorld(...objects) {
  (worldRoot || scene).add(...objects);
}

function makeRenderer() {
  renderer = new THREE.WebGLRenderer({
    antialias: !isMobile,
    powerPreference: "high-performance",
    alpha: false,
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, isMobile ? 1.25 : 1.5));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  const glInfo = renderer.getContext().getExtension("WEBGL_debug_renderer_info");
  const gpuName = glInfo ? renderer.getContext().getParameter(glInfo.UNMASKED_RENDERER_WEBGL) : "";
  bladeHardwareFallback = /swiftshader|llvmpipe|software/i.test(gpuName);
  renderer.shadowMap.enabled = !isMobile && !bladeHardwareFallback;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  viewport.appendChild(renderer.domElement);
}

function makeScene() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x07040f);
  scene.fog = new THREE.FogExp2(0x0b0818, 0.018);

  camera = new THREE.PerspectiveCamera(58, window.innerWidth / window.innerHeight, 0.1, 400);
  camera.position.set(0, 3.2, 8.5);

  // lights
  const amb = new THREE.AmbientLight(0x6a5a90, 0.55);
  amb.name = "base-ambient";
  addWorld(amb);

  const hemi = new THREE.HemisphereLight(0x7cf7ff, 0x1a0a28, 0.65);
  hemi.name = "base-hemi";
  addWorld(hemi);

  const sun = new THREE.DirectionalLight(0xffb078, 1.35);
  sun.name = "base-sun";
  sun.position.set(8, 18, -10);
  if (!isMobile) {
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    sun.shadow.camera.near = 1;
    sun.shadow.camera.far = 80;
    sun.shadow.camera.left = -30;
    sun.shadow.camera.right = 30;
    sun.shadow.camera.top = 30;
    sun.shadow.camera.bottom = -30;
  }
  addWorld(sun);

  const cyan = new THREE.PointLight(0x2fd8fa, 18, 50, 2);
  cyan.name = "base-cyan";
  cyan.position.set(-8, 4, 2);
  addWorld(cyan);

  const magenta = new THREE.PointLight(0xe62ffa, 18, 50, 2);
  magenta.name = "base-magenta";
  magenta.position.set(8, 4, 2);
  addWorld(magenta);

  const head = new THREE.SpotLight(0xfff0c8, 22, 40, Math.PI / 8, 0.45, 1.3);
  // temporary scene placement; reparented onto carRoot after mesh bounds known
  head.position.set(0, 1.2, -1.5);
  head.target.position.set(0, 0.4, -18);
  carState._head = head;
}

function makeComposer() {
  composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  // lower strength/threshold so road dashes don't strobe the center of the screen
  bloomPass = new UnrealBloomPass(
    new THREE.Vector2(window.innerWidth, window.innerHeight),
    isMobile ? 0.28 : 0.42,
    0.4,
    0.88
  );
  composer.addPass(bloomPass);
  composer.addPass(new OutputPass());
}

const ASSET_LOAD_TIMEOUT_MS = 30000;

function withAssetTimeout(promise, label) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label} timed out`)), ASSET_LOAD_TIMEOUT_MS);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

function loadTexture(url) {
  return withAssetTimeout(new Promise((resolve, reject) => {
    const loader = new THREE.TextureLoader();
    loader.load(
      url,
      (tex) => {
        tex.colorSpace = THREE.SRGBColorSpace;
        resolve(tex);
      },
      undefined,
      reject
    );
  }), url);
}

function loadGLB(loader, url) {
  return withAssetTimeout(new Promise((resolve, reject) => {
    loader.load(url, resolve, undefined, reject);
  }), url);
}

function prepModel(root, { cast = true, receive = true, neon = false } = {}) {
  root.traverse((o) => {
    if (!o.isMesh) return;
    o.castShadow = cast && !isMobile;
    o.receiveShadow = receive && !isMobile;
    if (o.material) {
      const mats = Array.isArray(o.material) ? o.material : [o.material];
      for (const m of mats) {
        if (!m) continue;
        // boost emissive for neon feel on dark materials
        if (neon && m.color) {
          const c = m.color;
          const lum = 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
          if (lum < 0.2) {
            m.emissive = m.emissive || new THREE.Color();
            m.emissive.setRGB(c.r * 0.3 + 0.05, c.g * 0.2 + 0.02, c.b * 0.45 + 0.12);
            m.emissiveIntensity = 0.8;
          }
        }
        if (m.map) m.map.colorSpace = THREE.SRGBColorSpace;
      }
    }
  });
  return root;
}

function fitToBox(object, targetSize = 1) {
  const box = new THREE.Box3().setFromObject(object);
  const size = new THREE.Vector3();
  box.getSize(size);
  const maxDim = Math.max(size.x, size.y, size.z) || 1;
  const s = targetSize / maxDim;
  object.scale.multiplyScalar(s);
  // recompute and ground
  box.setFromObject(object);
  const center = new THREE.Vector3();
  box.getCenter(center);
  object.position.x -= center.x;
  object.position.z -= center.z;
  object.position.y -= box.min.y;
  return object;
}

async function loadAssets() {
  const draco = new DRACOLoader();
  draco.setDecoderPath("./vendor/jsm/libs/draco/gltf/");
  draco.preload();
  const gltfLoader = new GLTFLoader();
  gltfLoader.setDRACOLoader(draco);

  const jobs = [
    ["sky", () => loadTexture("./assets/nightsky.jpg")],
    ["city", () => loadTexture("./assets/city.webp")],
    ["env", () => loadTexture("./assets/envmap.jpg")],
    ["street", () => loadTexture("./assets/city_street.jpg")],
    ["sun", () => loadTexture("./assets/sunset.png")],
    ["car", () => loadGLB(gltfLoader, "./assets/models/vehicle.dglb")],
    ["wheel", () => loadGLB(gltfLoader, "./assets/models/wheel.dglb")],
    ["palm", () => loadGLB(gltfLoader, "./assets/models/palm.dglb")],
    ["b1", () => loadGLB(gltfLoader, "./assets/models/building_01.dglb")],
    ["b2", () => loadGLB(gltfLoader, "./assets/models/building_02.dglb")],
    ["b3", () => loadGLB(gltfLoader, "./assets/models/building_03.dglb")],
    ["b4", () => loadGLB(gltfLoader, "./assets/models/building_04.dglb")],
    ["light", () => loadGLB(gltfLoader, "./assets/models/street_light.dglb")],
  ];

  const out = {};
  let done = 0;
  await Promise.all(jobs.map(async ([name, fn]) => {
    try {
      out[name] = await fn();
    } catch (err) {
      console.error("load fail", name, err);
      out[name] = null;
    } finally {
      done += 1;
      setBoot(done / jobs.length, name);
    }
  }));
  return out;
}

function buildEnvironment(assets) {
  // sky dome
  if (assets.sky) {
    const geo = new THREE.SphereGeometry(180, 48, 32);
    const mat = new THREE.MeshBasicMaterial({
      map: assets.sky,
      side: THREE.BackSide,
      fog: false,
    });
    skyMesh = new THREE.Mesh(geo, mat);
    skyMesh.rotation.y = Math.PI;
    addWorld(skyMesh);
  }

  // sunset disc + stripe (always visible; texture is bonus)
  {
    // large warm sun disc on horizon
    const disc = new THREE.Mesh(
      new THREE.CircleGeometry(18, 64),
      new THREE.MeshBasicMaterial({
        color: 0xff9a4a,
        transparent: true,
        opacity: 1.0,
        fog: false,
        depthWrite: false,
        toneMapped: false,
      })
    );
    disc.position.set(0, 16, -90);
    disc.renderOrder = 0;
    addWorld(disc);
    // magenta/cyan glow shell
    const glow = new THREE.Mesh(
      new THREE.CircleGeometry(28, 64),
      new THREE.MeshBasicMaterial({
        color: 0xff4fd8,
        transparent: true,
        opacity: 0.28,
        fog: false,
        depthWrite: false,
        toneMapped: false,
      })
    );
    glow.position.set(0, 14, -96);
    addWorld(glow);
    // lower half cut with dark plane? keep full disc + horizon haze
    const haze = new THREE.Mesh(
      new THREE.PlaneGeometry(180, 22),
      new THREE.MeshBasicMaterial({
        color: 0xff6a2a,
        transparent: true,
        opacity: 0.16,
        fog: false,
        depthWrite: false,
        toneMapped: false,
      })
    );
    haze.position.set(0, 7, -90);
    addWorld(haze);

    if (assets.sun) {
      const mat = new THREE.SpriteMaterial({
        map: assets.sun,
        transparent: true,
        depthWrite: false,
        fog: false,
        opacity: 0.95,
        blending: THREE.AdditiveBlending,
        toneMapped: false,
      });
      sunMesh = new THREE.Sprite(mat);
      sunMesh.scale.set(78, 24, 1);
      sunMesh.position.set(0, 18, -88);
      sunMesh.renderOrder = 3;
      addWorld(sunMesh);
    }

    // horizon neon band
    const band = new THREE.Mesh(
      new THREE.PlaneGeometry(170, 8),
      new THREE.MeshBasicMaterial({
        color: 0xe62ffa,
        transparent: true,
        opacity: 0.22,
        fog: false,
        depthWrite: false,
        toneMapped: false,
      })
    );
    band.position.set(0, 5.5, -86);
    addWorld(band);
  }

  // city skyline billboard strip
  if (assets.city) {
    assets.city.wrapS = THREE.RepeatWrapping;
    assets.city.repeat.set(2.2, 1);
    const geo = new THREE.PlaneGeometry(220, 42);
    const mat = new THREE.MeshBasicMaterial({
      map: assets.city,
      color: 0xffd0b0, // warm multiply — California dusk skyline
      transparent: true,
      opacity: 0.95,
      depthWrite: false,
      fog: false,
      toneMapped: false,
    });
    cityMesh = new THREE.Mesh(geo, mat);
    cityMesh.position.set(0, 12, -88);
    cityMesh.renderOrder = 1;
    addWorld(cityMesh);

    // second layer slight parallax
    const city2 = cityMesh.clone();
    city2.position.z = -86;
    city2.position.y = 9.5;
    city2.scale.set(1.05, 0.9, 1);
    city2.material = mat.clone();
    city2.material.opacity = 0.55;
    addWorld(city2);
  }

  // ground sides — warm dusk asphalt / dirt (California boulevard, not void)
  const sideMat = new THREE.MeshStandardMaterial({
    color: 0x1c1424,
    emissive: 0x2a1420,
    emissiveIntensity: 0.22,
    roughness: 0.92,
    metalness: 0.08,
  });
  for (const side of [-1, 1]) {
    const g = new THREE.Mesh(new THREE.PlaneGeometry(80, 260), sideMat);
    g.rotation.x = -Math.PI / 2;
    g.position.set(side * 28, -0.02, -40);
    g.receiveShadow = true;
    addWorld(g);
  }

  // road
  if (assets.street) {
    assets.street.wrapS = THREE.RepeatWrapping;
    assets.street.wrapT = THREE.RepeatWrapping;
    assets.street.repeat.set(1.5, 18);
    assets.street.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  }
  const roadMat = new THREE.MeshStandardMaterial({
    color: 0x2a2438,
    map: assets.street || null,
    emissive: 0x1a1020,
    emissiveIntensity: 0.25,
    roughness: 0.82,
    metalness: 0.12,
  });
  roadMesh = new THREE.Mesh(new THREE.PlaneGeometry(ROAD_HALF * 2.15, 240), roadMat);
  roadMesh.rotation.x = -Math.PI / 2;
  roadMesh.position.set(0, 0, -50);
  roadMesh.receiveShadow = true;
  addWorld(roadMesh);

  // neon curbs — soft edge glow only, avoid center-road strobe
  const makeCurb = (x, color) => {
    const mat = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.55,
      roughness: 0.45,
      metalness: 0.35,
    });
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.12, 240), mat);
    mesh.position.set(x, 0.05, -50);
    addWorld(mesh);
    return mesh;
  };
  makeCurb(-ROAD_HALF, 0x2fd8fa);
  makeCurb(ROAD_HALF, 0xe62ffa);

  // lane dashes — matte, no emissive (bloom was making center road flash)
  const dashMat = new THREE.MeshStandardMaterial({
    color: 0xc8d4e8,
    emissive: 0x000000,
    emissiveIntensity: 0,
    roughness: 0.85,
    metalness: 0.05,
  });
  for (let i = 0; i < 28; i++) {
    const dash = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.02, 1.6), dashMat);
    dash.position.set(0, 0.025, -i * 7.5);
    addWorld(dash);
    stripeMeshes.push(dash);
  }
  // lane separators — dim cyan, barely emissive
  for (const x of [-LANE_W * 0.55, LANE_W * 0.55]) {
    for (let i = 0; i < 22; i++) {
      const dash = new THREE.Mesh(
        new THREE.BoxGeometry(0.06, 0.015, 1.1),
        new THREE.MeshStandardMaterial({
          color: 0x3a6a80,
          emissive: 0x123040,
          emissiveIntensity: 0.08,
          roughness: 0.9,
        })
      );
      dash.position.set(x, 0.02, -i * 9 - 2);
      addWorld(dash);
      stripeMeshes.push(dash);
    }
  }

  // env map soft
  if (assets.env) {
    assets.env.mapping = THREE.EquirectangularReflectionMapping;
    scene.environment = assets.env;
  }
}

function cloneTemplate(src, size) {
  const o = src.clone(true);
  fitToBox(o, size);
  prepModel(o, { neon: true });
  return o;
}

function attachLightsToCar(root, mesh) {
  // measure actual car bounds so lights stick to body, not float away
  // force world matrices so bounds are correct after rotation.y = PI
  mesh.updateWorldMatrix(true, true);
  root.updateWorldMatrix(true, true);
  const box = new THREE.Box3().setFromObject(mesh);
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);

  // convert world-ish bounds into mesh-local via inverse matrix
  const inv = new THREE.Matrix4().copy(mesh.matrixWorld).invert();
  const localMin = box.min.clone().applyMatrix4(inv);
  const localMax = box.max.clone().applyMatrix4(inv);
  const localCenter = center.clone().applyMatrix4(inv);
  const localSize = new THREE.Vector3().subVectors(localMax, localMin);

  // use real mesh size — do NOT floor-inflate or hitboxes become "ghost walls"
  carState.carLen = Math.max(1.6, Math.min(3.2, size.z || 2.2));
  carState.carWidth = Math.max(1.0, Math.min(2.2, size.x || 1.6));

  const halfW = Math.max(0.25, localSize.x * 0.28);
  const y = localMin.y + localSize.y * 0.38;
  // after rotation.y=PI, model nose points to -Z in world; in local mesh space
  // the front is still whatever the asset defined. Place both ends, pick by world z.
  const zA = localMin.z + localSize.z * 0.04;
  const zB = localMax.z - localSize.z * 0.04;
  // sample which local z is more forward in world (-Z)
  const aWorld = new THREE.Vector3(localCenter.x, y, zA).applyMatrix4(mesh.matrixWorld);
  const bWorld = new THREE.Vector3(localCenter.x, y, zB).applyMatrix4(mesh.matrixWorld);
  const zFrontLocal = aWorld.z < bWorld.z ? zA : zB;
  const zBackLocal = aWorld.z < bWorld.z ? zB : zA;

  const hlMat = new THREE.MeshStandardMaterial({
    color: 0xfff2c0,
    emissive: 0xffe08a,
    emissiveIntensity: 1.6,
    toneMapped: true,
  });
  const tlMat = new THREE.MeshStandardMaterial({
    color: 0xff2d55,
    emissive: 0xff2d55,
    emissiveIntensity: 1.2,
    toneMapped: true,
  });

  // parent lights under the mesh itself so they never separate
  for (const x of [-halfW, halfW]) {
    const hl = new THREE.Mesh(
      new THREE.BoxGeometry(Math.max(0.12, localSize.x * 0.12), Math.max(0.06, localSize.y * 0.08), 0.1),
      hlMat
    );
    hl.position.set(localCenter.x + x, y, zFrontLocal);
    hl.name = "headlight";
    mesh.add(hl);

    // soft glow disc at headlight
    const glow = new THREE.Mesh(
      new THREE.CircleGeometry(0.14, 12),
      new THREE.MeshBasicMaterial({ color: 0xfff0b0, transparent: true, opacity: 0.35, toneMapped: true })
    );
    glow.position.set(localCenter.x + x, y, zFrontLocal - 0.02);
    glow.rotation.y = Math.PI; // face forward-ish
    mesh.add(glow);

    const tl = new THREE.Mesh(
      new THREE.BoxGeometry(Math.max(0.14, localSize.x * 0.14), Math.max(0.06, localSize.y * 0.08), 0.08),
      tlMat
    );
    tl.position.set(localCenter.x + x, y, zBackLocal);
    tl.name = "taillight";
    mesh.add(tl);
  }

  // spotlight parented to carRoot (same transform tree as body)
  if (carState._head) {
    const old = carState._head;
    if (old.parent) old.parent.remove(old);
    if (old.target?.parent) old.target.parent.remove(old.target);
  }
  const head = new THREE.SpotLight(0xfff0c8, 24, 42, Math.PI / 8, 0.4, 1.25);
  // place in root-local using mesh local front mapped roughly
  head.position.set(0, Math.max(0.6, y + 0.1), -Math.max(1.2, carState.carLen * 0.42));
  head.target.position.set(0, 0.15, -22);
  root.add(head);
  root.add(head.target);
  carState._head = head;
}

function buildWorld(assets) {
  // car
  if (assets.car) {
    templates.car = assets.car.scene;
    carMesh = cloneTemplate(templates.car, 2.35);
    // face down -Z (camera looks toward -Z)
    carMesh.rotation.y = Math.PI;
  } else {
    carMesh = new THREE.Group();
    const body = new THREE.Mesh(
      new THREE.BoxGeometry(1.8, 0.45, 3.4),
      new THREE.MeshStandardMaterial({ color: 0x2a1238, emissive: 0x4a1a70, emissiveIntensity: 0.5, metalness: 0.7, roughness: 0.35 })
    );
    body.position.y = 0.45;
    carMesh.add(body);
  }
  carRoot = new THREE.Group();
  carRoot.add(carMesh);
  // lights bound to measured mesh bounds (fixes floating detached lamps)
  attachLightsToCar(carRoot, carMesh);
  carRoot.position.set(0, 0, 0);
  addWorld(carRoot);

  // buildings pool
  const bScenes = [assets.b1, assets.b2, assets.b3, assets.b4].filter(Boolean).map((g) => g.scene);
  templates.buildings = bScenes;
  for (let i = 0; i < 24; i++) {
    let mesh;
    if (bScenes.length) {
      const src = bScenes[i % bScenes.length];
      mesh = cloneTemplate(src, 8 + (i % 5) * 2.5);
    } else {
      mesh = new THREE.Mesh(
        new THREE.BoxGeometry(4 + (i % 3), 8 + (i % 6) * 2, 4),
        new THREE.MeshStandardMaterial({
          color: 0x151028,
          emissive: i % 2 ? 0x2fd8fa : 0xe62ffa,
          emissiveIntensity: 0.25,
          metalness: 0.4,
          roughness: 0.6,
        })
      );
      mesh.position.y = 0;
    }
    const side = i % 2 === 0 ? -1 : 1;
    const group = new THREE.Group();
    group.add(mesh);
    group.userData = {
      side,
      z: -10 - i * 12 - Math.random() * 4,
      xBase: side * (10 + (i % 4) * 2.5),
    };
    group.position.set(group.userData.xBase, 0, group.userData.z);
    addWorld(group);
    buildingPool.push(group);
  }

  // v24: California photo billboards along the boulevard
  for (let i = 0; i < 10; i++) {
    const bb = makeStandaloneBillboard(i, SUNSET_AD_CATALOG, false);
    // NormalBlending ads — saturated dusk colors, not pure neon additive
    const side = i % 2 === 0 ? -1 : 1;
    bb.userData.side = side;
    bb.userData.baseX = side * (11 + (i % 4) * 1.5);
    bb.position.set(bb.userData.baseX, 3.2 + (i % 4) * 1.4, -18 - i * 22);
    // slight yaw toward road
    bb.rotation.y = side > 0 ? -0.35 : 0.35;
    addWorld(bb);
    // reuse building recycle path? store in buildingPool-like via palm? use lightPool no —
    // tag into buildingPool so they scroll with city sides
    bb.userData.side = side;
    buildingPool.push(bb);
  }

  // palms
  if (assets.palm) templates.palm = assets.palm.scene;
  for (let i = 0; i < 16; i++) {
    let mesh;
    if (templates.palm) {
      mesh = cloneTemplate(templates.palm, 4.5 + (i % 3) * 0.6);
    } else {
      mesh = new THREE.Mesh(
        new THREE.ConeGeometry(1.2, 4, 6),
        new THREE.MeshStandardMaterial({ color: 0x1a0d22, emissive: 0x3a1848, emissiveIntensity: 0.3 })
      );
    }
    const side = i % 2 === 0 ? -1 : 1;
    const group = new THREE.Group();
    group.add(mesh);
    group.userData = {
      side,
      z: -8 - i * 14,
      xBase: side * (7.2 + (i % 2) * 1.2),
    };
    group.position.set(group.userData.xBase, 0, group.userData.z);
    addWorld(group);
    palmPool.push(group);
  }

  // street lights
  if (assets.light) templates.streetLight = assets.light.scene;
  for (let i = 0; i < 14; i++) {
    let mesh;
    if (templates.streetLight) {
      mesh = cloneTemplate(templates.streetLight, 3.8);
    } else {
      mesh = new THREE.Mesh(
        new THREE.CylinderGeometry(0.08, 0.08, 4, 8),
        new THREE.MeshStandardMaterial({ color: 0x222, emissive: 0x2fd8fa, emissiveIntensity: 0.4 })
      );
    }
    const side = i % 2 === 0 ? -1 : 1;
    const group = new THREE.Group();
    group.add(mesh);
    // lamp glow
    const glow = new THREE.PointLight(side < 0 ? 0x2fd8fa : 0xe62ffa, 3.5, 12, 2);
    glow.position.set(0, 3.2, 0);
    group.add(glow);
    group.userData = {
      side,
      z: -6 - i * 16,
      xBase: side * (ROAD_HALF + 1.1),
    };
    group.position.set(group.userData.xBase, 0, group.userData.z);
    addWorld(group);
    lightPool.push(group);
  }

  // traffic cars (simple clones or boxes)
  for (let i = 0; i < 7; i++) {
    let mesh;
    if (templates.car) {
      mesh = cloneTemplate(templates.car, 2.1);
      mesh.rotation.y = Math.PI;
      // recolor body-ish
      mesh.traverse((o) => {
        if (o.isMesh && o.material && o.material.name === "body") {
          o.material = o.material.clone();
          o.material.color = new THREE.Color(i % 2 ? 0x1a2030 : 0x301020);
          o.material.emissive = new THREE.Color(i % 2 ? 0x2fd8fa : 0xff2d55);
          o.material.emissiveIntensity = 0.25;
        }
      });
    } else {
      mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1.6, 0.5, 3),
        new THREE.MeshStandardMaterial({ color: 0x1a1020, emissive: 0xff2d55, emissiveIntensity: 0.4 })
      );
      mesh.position.y = 0.4;
    }
    const group = new THREE.Group();
    group.add(mesh);
    group.userData = {
      lane: [-1, 0, 1, -1, 1, 0, -1][i],
      z: -25 - i * 18,
      speed: 12 + Math.random() * 8,
    };
    group.position.set(group.userData.lane * LANE_W * 0.75, 0, group.userData.z);
    addWorld(group);
    trafficPool.push(group);
  }
}

function resetWorldRefs() {
  carRoot = carMesh = null;
  roadMesh = skyMesh = cityMesh = sunMesh = null;
  stripeMeshes = [];
  buildingPool = [];
  palmPool = [];
  lightPool = [];
  trafficPool = [];
  bladeTowerPool = [];
  bladeGatePool = [];
  bladeTrafficPool = [];
  bladeDeckPool = [];
  bladeHolograms = [];
  bladeSearchlights = [];
  bladeFogSheets = [];
  bladeLandmark = null;
  bladeFarSlabPool = [];
  bladeGlintPool = [];
  bladeMaterials = null;
  bladeFacadeCache = [];
  bladeRain = bladeRainData = null;
  bladeBillboardPool = [];
  pathBend = 0;
  pathHeading = 0;
  pathBendTarget = 0;
  pathBendPhase = 0;
}

function removeWorld() {
  if (!worldRoot) return;
  scene.remove(worldRoot);
  worldRoot.clear();
  worldRoot = null;
  renderer?.renderLists?.dispose();
  resetWorldRefs();
}

function makeHologramTexture(script, title, detail, color, kicker, style = 0) {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 360;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Style variants: 0 neon panel, 1 bold poster, 2 strip ticker, 3 photo-ad with color blocks
  if (style === 1) {
    ctx.fillStyle = color;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "rgba(8,6,12,0.82)";
    ctx.fillRect(18, 18, canvas.width - 36, canvas.height - 36);
  } else if (style === 2) {
    const g = ctx.createLinearGradient(0, 0, canvas.width, 0);
    g.addColorStop(0, "rgba(4,8,16,0.95)");
    g.addColorStop(0.5, color);
    g.addColorStop(1, "rgba(4,8,16,0.95)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  } else if (style === 3) {
    // California sunset ad blocks
    const blocks = ["#ff6b3d", "#ffb347", "#ff4d8d", "#4ecdc4", "#ffe66d", "#a78bfa"];
    for (let i = 0; i < 6; i++) {
      ctx.fillStyle = blocks[(i + script.length) % blocks.length];
      ctx.globalAlpha = 0.85;
      ctx.fillRect((i % 3) * 170, Math.floor(i / 3) * 180, 170, 180);
    }
    ctx.globalAlpha = 1;
    ctx.fillStyle = "rgba(10,6,18,0.55)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  } else {
    const glow = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
    glow.addColorStop(0, "rgba(2,4,16,.18)");
    glow.addColorStop(0.16, color);
    glow.addColorStop(0.19, "rgba(5,8,24,.88)");
    glow.addColorStop(0.82, "rgba(9,4,20,.86)");
    glow.addColorStop(0.86, color);
    glow.addColorStop(1, "rgba(2,4,16,.18)");
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  ctx.strokeStyle = color;
  ctx.globalAlpha = 0.82;
  ctx.lineWidth = 7;
  ctx.shadowColor = color;
  ctx.shadowBlur = 24;
  ctx.strokeRect(14, 14, canvas.width - 28, canvas.height - 28);
  ctx.shadowBlur = 0;
  ctx.fillStyle = color;
  ctx.globalAlpha = 0.22;
  for (let y = 6; y < canvas.height; y += 8) {
    if ((y / 9) % 7 === 0) continue;
    ctx.fillRect(0, y, canvas.width, 2);
  }
  ctx.shadowColor = color;
  ctx.shadowBlur = 18;
  ctx.globalAlpha = 0.9;
  ctx.font = "600 22px monospace";
  ctx.fillText(script, 42, 67);
  ctx.globalAlpha = 1;
  ctx.fillStyle = style === 1 ? "#fff8e8" : color;
  ctx.font = "700 24px monospace";
  ctx.fillText(kicker, 43, 112);
  ctx.font = "900 72px Arial Narrow, sans-serif";
  ctx.fillText(title, 36, 200);
  ctx.shadowBlur = 9;
  ctx.globalAlpha = 0.9;
  ctx.font = "500 22px monospace";
  ctx.fillText(detail, 43, 258);
  ctx.shadowBlur = 0;
  ctx.globalAlpha = 0.66;
  ctx.fillStyle = "white";
  ctx.font = "500 16px monospace";
  ctx.fillText(style >= 2 ? "LIVE SIGNAL  ·  DISTRICT FEED" : "PUBLIC TRANSMISSION  ·  SIGNAL DEGRADED", 43, 320);
  ctx.globalCompositeOperation = "destination-out";
  ctx.globalAlpha = 0.35;
  for (let n = 0; n < 18; n++) {
    const x = (n * 173) % canvas.width;
    const y = (n * 71) % canvas.height;
    ctx.fillRect(x, y, 18 + (n % 5) * 14, 2 + (n % 3));
  }
  ctx.globalCompositeOperation = "source-over";
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearFilter;
  return texture;
}

// Diverse ad copy — neon brands + California sunset commerce language
const BLADE_AD_CATALOG = [
  ["NEXUS CITY", "DREAM", "MEMORIES MADE WHILE YOU WAIT", "#8fbdb4", "記憶設計 / SYNTHETIC SOUL"],
  ["KITE SYSTEMS", "ASCEND", "AIR LANE ACCESS · LEVEL 12", "#c9a27a", "空中都市 / VIDA ELEVADA"],
  ["TANHAUSER", "MIDNIGHT", "NOCTURNAL DISTRICT OPEN", "#b7c7b8", "夜市 / MARCHE DE NUIT"],
  ["OFF-WORLD", "BEGIN AGAIN", "A NEW LIFE AWAITS", "#6f8f88", "新天地 / VIDA NUEVA"],
  ["TYRELL", "MORE HUMAN", "GENETIC DESIGN BOUTIQUE", "#e8a0c8", "REPLICA SERIES / R"],
  ["PACIFIC GAS", "GOLDEN", "SUNSET BOULEVARD POWER", "#ffb347", "CALIFORNIA / GRID"],
  ["RODEO DRIVE", "LUXE", "NIGHT MARKET · OPEN LATE", "#ff6b9d", "BEVERLY / HILLS"],
  ["VENICE", "BOARDWALK", "NEON ROLLER · LIVE MUSIC", "#4ecdc4", "LA COAST / WAVE"],
  ["HOLLYWOOD", "SIGN", "OPEN CASTING · TONIGHT", "#ffe66d", "STUDIO CITY / CAST"],
  ["SAKURA", "RAMEN", "24H NOODLE · LEVEL B2", "#ff8c69", "下町 / LATE NIGHT"],
  ["ORBITAL", "BANK", "CRYPTO CLEARANCE OPEN", "#7dd3fc", "SECURE / LEDGER"],
  ["SPINNER", "RENTAL", "HOVER BY THE HOUR", "#a78bfa", "FLEET / READY"],
  ["MALIBU", "COAST", "PACIFIC GOLDEN HOUR", "#fb923c", "SURF / SUNSET"],
  ["NEON LOTUS", "CLUB", "BASS UNTIL DAWN", "#f472b6", "ECHO PARK / NIGHT"],
  ["CITY OF ANGELS", "FLY", "FREEWAY IN THE SKY", "#fbbf24", "LA / 2049"],
  ["ZODIAC", "MART", "GROCERY DRONES DELIVER", "#34d399", "KOREATOWN / 24H"],
];

const SUNSET_AD_CATALOG = [
  ["PACIFIC", "GOLD", "GOLDEN HOUR DRIVE", "#ffb347", "CALIFORNIA DREAMIN"],
  ["VENICE", "WAVE", "BOARDWALK · SUNSET", "#4ecdc4", "LA COAST"],
  ["HOLLYWOOD", "NITE", "NEON CASTING OPEN", "#ff6b9d", "STUDIO ROW"],
  ["MALIBU", "SURF", "PACIFIC PULL-OFF", "#fb923c", "PCH / 1"],
  ["RODEO", "LUXE", "AFTER DARK MARKET", "#fbbf24", "BEVERLY"],
  ["ECHO", "PARK", "LIVE JAZZ TERRACE", "#a78bfa", "SILVER LAKE"],
  ["TACO", "TRUCK", "AL PASTOR · OPEN", "#ff8c69", "STREET FOOD"],
  ["CITRUS", "GROVE", "ORANGE BLOSSOM LANE", "#ffe66d", "OC / GROVE"],
  ["FREEWAY", "EXIT", "NEXT STOP · HOME", "#7dd3fc", "405 / 10"],
  ["PALM", "COURT", "POOLSIDE TONIGHT", "#34d399", "WESTSIDE"],
];

function addBladeHologram(group, i, width, depth, y, compact = false) {
  // v24: prefer photo ads; NormalBlending; NO double halo clone (was the green/pink soup).
  const usePhoto = i % 3 !== 2; // 2/3 photo, 1/3 procedural neon for variety
  let texture;
  if (usePhoto) {
    texture = getAdTexture(BLADE_PHOTO_ADS[i % BLADE_PHOTO_ADS.length]);
  } else {
    const a = BLADE_AD_CATALOG[i % BLADE_AD_CATALOG.length];
    texture = makeHologramTexture(a[0], a[1], a[2], a[3], a[4], 0);
  }
  const material = new THREE.MeshBasicMaterial({
    map: texture,
    transparent: !usePhoto,
    opacity: usePhoto ? 1 : (compact ? 0.78 : 0.88),
    blending: usePhoto ? THREE.NormalBlending : THREE.AdditiveBlending,
    depthWrite: usePhoto,
    toneMapped: usePhoto,
    side: THREE.FrontSide,
  });
  const holo = new THREE.Mesh(
    new THREE.PlaneGeometry(compact ? 7.5 : Math.min(11, width * 0.95), compact ? 2.2 : 4.6),
    material
  );
  // Parked on facade, slightly inset so it does not stick into air lane
  holo.position.set(0, y, depth / 2 + 0.12);
  group.add(holo);
  holo.userData.phase = i * 0.77;
  holo.userData.baseOpacity = material.opacity;
  bladeHolograms.push(holo);
}

function getAdTexture(url) {
  if (adTextureCache[url]) return adTextureCache[url];
  const tex = new THREE.TextureLoader().load(url);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.magFilter = THREE.LinearFilter;
  tex.anisotropy = 4;
  adTextureCache[url] = tex;
  return tex;
}

// Photo billboard decks (real image assets under ./assets/ads/)
const SUNSET_PHOTO_ADS = [
  "./assets/ads/sunset_pacific.jpg",
  "./assets/ads/sunset_venice.jpg",
  "./assets/ads/sunset_hollywood.jpg",
  "./assets/ads/sunset_malibu.jpg",
  "./assets/ads/sunset_hollywood2.jpg",
  "./assets/ads/sunset_palm.jpg",
  "./assets/ads/sunset_citrus.jpg",
  "./assets/ads/sunset_echo.jpg",
];
const BLADE_PHOTO_ADS = [
  "./assets/ads/blade_nexus.jpg",
  "./assets/ads/blade_tyrell.jpg",
  "./assets/ads/blade_offworld.jpg",
  "./assets/ads/blade_orbital.jpg",
  "./assets/ads/blade_spinner.jpg",
  "./assets/ads/blade_tanhauser.jpg",
];

function makeStandaloneBillboard(i, catalog, corridor = true) {
  // v24: photo maps, NormalBlending, parked outside the air lane — no additive soup.
  const group = new THREE.Group();
  const urls = corridor ? BLADE_PHOTO_ADS : SUNSET_PHOTO_ADS;
  const url = urls[i % urls.length];
  const texture = getAdTexture(url);
  const w = corridor ? 7.2 + (i % 3) * 0.8 : 6.5 + (i % 3) * 1.0;
  const h = corridor ? 3.8 + (i % 2) * 0.5 : 3.6 + (i % 2) * 0.6;
  const mat = new THREE.MeshBasicMaterial({
    map: texture,
    transparent: false,
    toneMapped: true,
    side: THREE.FrontSide,
  });
  const board = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
  const frameMat = corridor
    ? (bladeMaterials ? bladeMaterials.darkMetal : new THREE.MeshStandardMaterial({ color: 0x141820 }))
    : new THREE.MeshStandardMaterial({
        color: 0x2a2430,
        metalness: 0.35,
        roughness: 0.65,
        emissive: 0x1a1018,
        emissiveIntensity: 0.25,
      });
  const frame = new THREE.Mesh(new THREE.BoxGeometry(w + 0.35, h + 0.35, 0.22), frameMat);
  frame.position.z = -0.12;
  group.add(frame);
  group.add(board);
  const poleH = corridor ? 5 + (i % 3) * 1.6 : 3.5 + (i % 3) * 1.2;
  const pole = new THREE.Mesh(new THREE.BoxGeometry(0.22, poleH, 0.22), frameMat);
  pole.position.set(0, -h / 2 - poleH / 2, -0.12);
  group.add(pole);
  // thin warm edge only — not a second glowing plane
  const edgeColor = corridor ? 0x6f9a96 : 0xffb347;
  const accent = new THREE.Mesh(
    new THREE.BoxGeometry(w + 0.4, 0.08, 0.08),
    new THREE.MeshBasicMaterial({ color: edgeColor, toneMapped: false })
  );
  accent.position.set(0, h / 2 + 0.1, 0.04);
  group.add(accent);

  const side = i % 2 === 0 ? -1 : 1;
  group.userData = {
    side,
    phase: i * 0.91,
    baseOpacity: 1,
    catalog: corridor ? "blade" : "sunset",
    board,
  };
  return group;
}


function makeSpinner({ traffic = false, accent = 0x59e8ff } = {}) {
  const root = new THREE.Group();
  const bodyMat = new THREE.MeshStandardMaterial({
    color: traffic ? 0x16191a : 0x202628,
    metalness: 0.8,
    roughness: 0.52,
    emissive: 0x020303,
    emissiveIntensity: 0.15,
  });
  const trimMat = new THREE.MeshStandardMaterial({
    color: accent,
    emissive: accent,
    emissiveIntensity: traffic ? 1.05 : 1.65,
    metalness: 0.4,
    roughness: 0.48,
  });
  const glassMat = new THREE.MeshPhysicalMaterial({
    color: 0x172126,
    emissive: 0x061014,
    emissiveIntensity: 0.34,
    transparent: true,
    opacity: 0.88,
    roughness: 0.32,
    metalness: 0.38,
  });

  const belly = new THREE.Mesh(new THREE.BoxGeometry(2.18, 0.52, 3.65), bodyMat);
  belly.position.y = 0.2;
  root.add(belly);
  const cabin = new THREE.Mesh(new THREE.BoxGeometry(1.62, 0.64, 1.84), glassMat);
  cabin.scale.set(0.96, 0.78, 1);
  cabin.rotation.x = -0.07;
  cabin.position.set(0, 0.65, -0.23);
  root.add(cabin);
  const nose = new THREE.Mesh(new THREE.BoxGeometry(1.75, 0.34, 1.25), bodyMat);
  nose.rotation.x = -0.11;
  nose.position.set(0, 0.08, -2.22);
  root.add(nose);

  if (traffic) {
    // Distant vehicles read by silhouette, not component count.
    for (const side of [-1, 1]) {
      const pod = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.42, 2.12), bodyMat);
      pod.position.set(side * 1.28, 0.05, 0.3);
      root.add(pod);
    }
    const tail = new THREE.Mesh(new THREE.BoxGeometry(1.28, 0.11, 0.08), trimMat);
    tail.position.set(0, 0.23, 1.87);
    root.add(tail);
    root.scale.setScalar(0.6);
    return root;
  }

  for (const side of [-1, 1]) {
    const nacelle = new THREE.Group();
    nacelle.position.set(side * 1.32, 0.06, 0.35);
    const housing = new THREE.Mesh(new THREE.BoxGeometry(0.68, 0.46, 2.26), bodyMat);
    nacelle.add(housing);
    const core = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.25, 0.18, 16), trimMat);
    core.rotation.z = Math.PI / 2;
    core.position.x = side * 0.34;
    nacelle.add(core);
    const jet = new THREE.Mesh(
      new THREE.ConeGeometry(0.14, 0.78, 12),
      new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.62, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false })
    );
    jet.rotation.x = -Math.PI / 2;
    jet.position.z = 1.38;
    jet.userData.thruster = true;
    nacelle.add(jet);
    root.add(nacelle);
  }

  for (const x of [-0.66, 0.66]) {
    const lamp = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.12, 0.08), trimMat);
    lamp.position.set(x, 0.31, 1.86);
    root.add(lamp);
  }
  const bumper = new THREE.Mesh(new THREE.BoxGeometry(1.65, 0.17, 0.16), bodyMat);
  bumper.position.set(0, -0.03, 1.94);
  root.add(bumper);
  const policeBar = new THREE.Mesh(new THREE.BoxGeometry(traffic ? 0.9 : 1.05, 0.07, 0.1), trimMat);
  policeBar.position.set(0, 1.05, 0.18);
  root.add(policeBar);
  root.scale.setScalar(1.08);
  return root;
}

function makeBladeTower(i) {
  // v26: skyline teeth — staggered heights, setbacks, L-blocks, needles, plazas
  // Free-air rule preserved: mass stays outside BLADE_AIR_HALF.
  const group = new THREE.Group();
  const side = i % 2 === 0 ? -1 : 1;
  const seed = (i * 1103515245 + 12345) >>> 0;
  const r1 = (seed & 255) / 255;
  const r2 = ((seed >>> 8) & 255) / 255;
  const r3 = ((seed >>> 16) & 255) / 255;
  const r4 = ((seed >>> 24) & 255) / 255;

  const bins = [0.12, 0.28, 0.48, 0.66, 0.78, 0.90, 1.01];
  let arch = 0;
  for (let b = 0; b < bins.length; b++) {
    if (r1 < bins[b]) { arch = b; break; }
  }

  const heightBoost = ((i * 3) % 5 === 0) ? 1.35 : ((i * 3) % 5 === 1) ? 0.72 : (0.9 + r4 * 0.35);

  const baseW = [
    11 + r2 * 7, 8 + r2 * 5, 9 + r2 * 5, 11 + r2 * 6,
    4.2 + r2 * 2.2, 10 + r2 * 6, 14 + r2 * 8,
  ][arch];
  const baseD = [
    12 + r3 * 6, 9 + r3 * 4, 10 + r3 * 5, 12 + r3 * 6,
    5 + r3 * 2.5, 11 + r3 * 5, 16 + r3 * 7,
  ][arch];
  const totalH = [
    14 + r4 * 12, 28 + r4 * 24, 48 + r4 * 36, 78 + r4 * 55,
    100 + r4 * 55, 36 + r4 * 40, 55 + r4 * 50,
  ][arch] * heightBoost;

  // v28: ~1/3 of non-needle towers get light-mega-ads baked into facade surface
  const wantMegaAd = arch !== 4 && totalH > 36 && (i % 3 === 0 || (arch >= 2 && i % 5 === 1));
  const facadeMat = getBladeFacadeMaterial(i * 3 + arch, baseW, totalH, wantMegaAd);
  const bodyMat = [
    bladeMaterials.concreteWarm, bladeMaterials.concrete, bladeMaterials.darkMetal,
    bladeMaterials.serviceMetal, bladeMaterials.rustMetal,
  ][i % 5];
  const accent = [
    bladeMaterials.neonCyan, bladeMaterials.neonMagenta, bladeMaterials.neonAmber,
    bladeMaterials.hazard, bladeMaterials.coldWindow, bladeMaterials.sodiumWindow,
  ][i % 6];

  let yCursor = -6;
  let w = baseW;
  let d = baseD;

  const addBox = (bw, bh, bd, mat, ox = 0, oy = 0, oz = 0) => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(bw, bh, bd), mat);
    mesh.position.set(ox, oy, oz);
    group.add(mesh);
    return mesh;
  };

  if (arch === 0) {
    addBox(w, totalH * 0.7, d, bodyMat, 0, yCursor + totalH * 0.35, 0);
    if (r2 > 0.4) {
      // second slab further OUT, not into air lane
      addBox(w * 0.7, totalH * 0.45, d * 0.65, facadeMat, side * w * 0.28, yCursor + totalH * 0.85, -d * 0.1);
    }
    yCursor += totalH;
  } else if (arch === 1) {
    addBox(w, totalH * 0.55, d, bodyMat, 0, yCursor + totalH * 0.275, 0);
    addBox(w * 0.82, totalH * 0.45, d * 0.82, facadeMat, 0, yCursor + totalH * 0.775, r3 > 0.5 ? 0.4 : -0.3);
    yCursor += totalH;
  } else if (arch === 2) {
    const fracs = r2 > 0.5 ? [0.38, 0.28, 0.22, 0.12] : [0.42, 0.32, 0.26];
    for (let s = 0; s < fracs.length; s++) {
      const h = totalH * fracs[s];
      addBox(w, h, d, s === 0 ? bodyMat : facadeMat, 0, yCursor + h / 2, (s % 2 ? 0.2 : -0.15) * s);
      if (s < fracs.length - 1) {
        addBox(w * 1.08, 0.45, d * 1.08, bladeMaterials.darkMetal, 0, yCursor + h + 0.1, 0);
      }
      yCursor += h;
      w *= 0.78 + r2 * 0.06;
      d *= 0.8 + r3 * 0.05;
    }
  } else if (arch === 3) {
    const fracs = [0.34, 0.26, 0.22, 0.18];
    for (let s = 0; s < fracs.length; s++) {
      const h = totalH * fracs[s];
      const ww = w * (s === 1 ? 1.12 : 1);
      addBox(ww, h, d, s === 0 ? bodyMat : facadeMat, s === 1 ? side * 0.4 : 0, yCursor + h / 2, 0);
      yCursor += h;
      w *= 0.8;
      d *= 0.82;
    }
  } else if (arch === 4) {
    w *= 0.5;
    d *= 0.5;
    addBox(w * 1.4, totalH * 0.18, d * 1.4, bodyMat, 0, yCursor + totalH * 0.09, 0);
    addBox(w, totalH * 0.62, d, facadeMat, 0, yCursor + totalH * 0.49, 0);
    addBox(w * 0.45, totalH * 0.28, d * 0.45, accent, 0, yCursor + totalH * 0.9, 0);
    yCursor += totalH;
  } else if (arch === 5) {
    // L / twin — BOTH shafts bias OUTWARD (side), never toward free-air
    const hMain = totalH * (0.7 + r2 * 0.2);
    const hWing = totalH * (0.35 + r3 * 0.25);
    addBox(w * 0.62, hMain, d, facadeMat, side * w * 0.12, yCursor + hMain / 2, 0);
    addBox(w * 0.55, hWing, d * 0.7, bodyMat, side * w * 0.48, yCursor + hWing / 2, -d * 0.15);
    if (r4 > 0.45) {
      addBox(w * 0.3, totalH * 0.2, d * 0.3, accent, side * w * 0.1, yCursor + hMain + totalH * 0.08, 0);
    }
    yCursor += Math.max(hMain, hWing);
  } else {
    addBox(w, totalH * 0.5, d, bodyMat, 0, yCursor + totalH * 0.25, 0);
    addBox(w * 0.75, totalH * 0.28, d * 0.7, facadeMat, side * w * 0.08, yCursor + totalH * 0.64, -0.4);
    addBox(w * 0.45, totalH * 0.22, d * 0.45, bladeMaterials.darkMetal, -side * w * 0.1, yCursor + totalH * 0.89, 0);
    yCursor += totalH;
  }

  if (arch === 4 || (arch >= 2 && r1 > 0.55)) {
    addBox(0.22, 6 + arch * 2.2, 0.22, accent, side * 0.12, yCursor + 3 + arch * 0.4, 0);
    addBox(0.65, 0.65, 0.65, bladeMaterials.neonAmber, side * 0.12, yCursor + 7 + arch * 0.8, 0);
  } else if (arch === 3 || arch === 6) {
    addBox(Math.max(2, w * 0.55), 2.2 + arch * 0.35, Math.max(2, d * 0.55), bladeMaterials.darkMetal, 0, yCursor + 1.2, 0);
  } else if (arch === 1 || arch === 5) {
    addBox(w * 0.5, 1.4, d * 0.5, bladeMaterials.serviceMetal, side * 0.2, yCursor + 0.8, 0);
  }

  if (arch >= 2 && arch !== 4 && i % 3 !== 0) {
    // accent on OUTER face only
    addBox(0.16, totalH * 0.5, 0.1, accent, side * baseW * 0.38, 2 + totalH * 0.15, baseD / 2 + 0.08);
  }
  if (arch >= 3 && i % 4 === 0) {
    addBox(baseW * 0.5, 0.14, 0.08, bladeMaterials.neonAmber, 0, 8 + totalH * 0.18, baseD / 2 + 0.08);
  }

  // v28: fewer plane holograms — mega light-ads live IN the facade now
  if (!wantMegaAd && i % 5 === 0) {
    const hy = arch === 0 ? 5 + (i % 2) * 2 : 7 + (i % 5) * 4 + r2 * 4;
    addBladeHologram(group, i, baseW, baseD, Math.min(hy, totalH * 0.55), arch === 0 || arch === 4);
  }
  if (!wantMegaAd && arch >= 3 && i % 7 === 0) {
    addBladeHologram(group, i + 11, baseW * 0.75, baseD, totalH * 0.7, true);
  }

  if (arch !== 4 && arch !== 0 && r3 > 0.25) {
    const annexH = 7 + r2 * 16;
    const annex = new THREE.Mesh(
      new THREE.BoxGeometry(baseW * (0.55 + r3 * 0.35), annexH, baseD * (0.45 + r2 * 0.25)),
      getBladeFacadeMaterial(i + 17, baseW * 0.6, annexH)
    );
    annex.position.set(side * baseW * 0.78, -6 + annexH / 2, -baseD * 0.4);
    group.add(annex);
  }

  if (arch >= 2 && i % 4 === 0) {
    addBox(baseW * 0.32, 1.0, baseD * 0.8, bladeMaterials.serviceMetal, side * baseW * 0.55, 8 + r2 * 14, -baseD * 0.2);
  }

  if (!bladeHardwareFallback && arch >= 2 && arch !== 4 && i % 2 === 0) {
    const outerX = side * (baseW / 2 + 0.25);
    for (let n = 0; n < 2; n++) {
      addBox(0.26, totalH * 0.32, 0.38, n ? bladeMaterials.rustMetal : bladeMaterials.serviceMetal, outerX, 2 + n * 11, (n - 0.5) * 1.3);
    }
  }

  const depthRow = (i + (seed % 3)) % 3;
  // v27: extra free-air pad (was 1.0 — still felt tight with wide annexes)
  const lateral =
    depthRow === 0
      ? BLADE_AIR_HALF + baseW / 2 + 2.4 + r2 * 2.0
      : depthRow === 1
        ? BLADE_AIR_HALF + baseW / 2 + 9 + r3 * 3.5
        : BLADE_AIR_HALF + baseW / 2 + 16 + r4 * 4.5;
  const zBase = -6 - i * (8.2 + r2 * 3.5) - depthRow * (1.5 + r3 * 2.5) - (i % 5) * 1.8;

  group.userData = {
    side, width: baseW, height: totalH, arch, depthRow,
    baseX: side * lateral, z: zBase,
  };
  group.position.set(group.userData.baseX, 0, group.userData.z);
  return group;
}

function makeBladeFarSlab(i) {
  // v26 deep megablocks — varied silhouette + scroll with world
  const group = new THREE.Group();
  const side = i % 2 === 0 ? -1 : 1;
  const seed = (i * 2654435761) >>> 0;
  const r = ((seed & 255) / 255);
  const r2 = (((seed >>> 8) & 255) / 255);
  const kind = i % 5;
  let w = 12 + (i % 6) * 3.5 + r * 4;
  let h = kind === 0 ? 22 + r * 18
        : kind === 1 ? 48 + r * 30
        : kind === 2 ? 95 + r * 40
        : kind === 3 ? 55 + r * 45
        : 70 + r * 50;
  const d = 10 + (i % 5) * 4 + r2 * 4;
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(w, h, d),
    getBladeFacadeMaterial(i + 30 + kind * 3, w, h)
  );
  body.position.y = -4 + h / 2;
  group.add(body);
  if (kind === 3) {
    const wing = new THREE.Mesh(
      new THREE.BoxGeometry(w * 0.45, h * (0.45 + r * 0.2), d * 0.6),
      getBladeFacadeMaterial(i + 77, w * 0.45, h * 0.5)
    );
    wing.position.set(side * w * 0.4, -4 + h * 0.28, -d * 0.15);
    group.add(wing);
  }
  if (kind === 4 || kind === 2) {
    const top = new THREE.Mesh(
      new THREE.BoxGeometry(w * (0.4 + r * 0.25), h * 0.2, d * 0.5),
      bladeMaterials.darkMetal
    );
    top.position.y = -4 + h * 0.95;
    group.add(top);
  } else {
    const top = new THREE.Mesh(
      new THREE.BoxGeometry(w * 0.62, h * 0.14, d * 0.62),
      i % 2 ? bladeMaterials.concreteWarm : bladeMaterials.serviceMetal
    );
    top.position.y = -4 + h * 0.92;
    group.add(top);
  }
  if (i % 3 === 0) {
    const rim = new THREE.Mesh(new THREE.BoxGeometry(0.28, h * 0.4, 0.1), bladeMaterials.neonAmber);
    rim.position.set(side * w * 0.32, 10, d / 2 + 0.08);
    group.add(rim);
  }
  // outer bank only — never free-air
  const baseX = side * (36 + (i % 4) * 6 + w * 0.2 + r * 4);
  const zBase = -55 - i * (20 + r * 8);
  group.userData = { side, baseX, width: w, z: zBase };
  group.position.set(baseX, 0, zBase);
  return group;
}

function makeBladeGate(i) {
  // v25: wide open arch — supports outside free-air envelope (rocktree: open vanishing center)
  const group = new THREE.Group();
  const bridgeY = [7.5, 10.0, 12.5, 15.0, 17.5][i % 5];
  const supportX = BLADE_AIR_HALF + 0.8; // ~12.3
  const span = supportX * 2 + 2.2;
  const beam = new THREE.Mesh(new THREE.BoxGeometry(span, 1.2, 2.2), bladeMaterials.concreteWarm);
  beam.position.y = 3.6;
  group.add(beam);
  const under = new THREE.Mesh(new THREE.BoxGeometry(span - 1.5, 0.24, 2.5), bladeMaterials.serviceMetal);
  under.position.y = 2.9;
  group.add(under);
  for (const x of [-supportX, supportX]) {
    const support = new THREE.Mesh(new THREE.BoxGeometry(1.0, 8.2, 1.8), bladeMaterials.darkMetal);
    support.position.set(x, -0.6, 0);
    group.add(support);
    const hazard = new THREE.Mesh(new THREE.BoxGeometry(0.14, 1.0, 0.1), bladeMaterials.hazard);
    hazard.position.set(x - Math.sign(x) * 0.55, 0.2, 1.0);
    group.add(hazard);
  }
  // nav lamps on supports only — center stays empty air
  for (const x of [-supportX * 0.55, supportX * 0.55]) {
    const beacon = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.12, 0.12), bladeMaterials.sodiumWindow);
    beacon.position.set(x, 2.75, 1.1);
    group.add(beacon);
  }
  if (i % 2 === 0) {
    const tex = getAdTexture(BLADE_PHOTO_ADS[i % BLADE_PHOTO_ADS.length]);
    const plate = new THREE.Mesh(
      new THREE.PlaneGeometry(2.8, 1.8),
      new THREE.MeshBasicMaterial({ map: tex, toneMapped: true, side: THREE.FrontSide })
    );
    plate.position.set(-supportX, 1.2, 1.05);
    group.add(plate);
  }
  group.userData = {
    x: 0,
    y: bridgeY,
    z: -60 - i * 58,
    checked: false,
  };
  group.position.set(group.userData.x, group.userData.y, group.userData.z);
  return group;
}

function makeBladeRain() {
  // v24.1: light rain suggestion — not a green additive curtain
  const count = isMobile ? 140 : 280;
  const positions = new Float32Array(count * 6);
  const drops = [];
  for (let i = 0; i < count; i++) {
    const x = (Math.random() - 0.5) * 40;
    const y = Math.random() * 32 - 5;
    const z = Math.random() * -100 + 14;
    const len = 0.6 + Math.random() * 1.4;
    const p = i * 6;
    positions[p] = x; positions[p + 1] = y; positions[p + 2] = z;
    positions[p + 3] = x - 0.05; positions[p + 4] = y - len; positions[p + 5] = z + 0.28;
    drops.push({ x, y, z, len, speed: 12 + Math.random() * 14 });
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const material = new THREE.LineBasicMaterial({
    color: 0x9aabae,
    transparent: true,
    opacity: 0.12,
    blending: THREE.NormalBlending,
    depthWrite: false,
  });
  bladeRainData = { drops, positions };
  bladeRain = new THREE.LineSegments(geometry, material);
  bladeRain.frustumCulled = false;
  addWorld(bladeRain);
}

function makeBladeMaterials() {
  // Phase 0: materials must survive ACES + fog + software GL.
  // Concrete is dark but not pure void; windows/neon carry the read.
  const standard = (color, metalness, roughness, emissive = 0x000000, emissiveIntensity = 0) =>
    new THREE.MeshStandardMaterial({ color, metalness, roughness, emissive, emissiveIntensity });
  return {
    concrete: standard(0x1a242a, 0.22, 0.86, 0x0a1418, 0.22),
    concreteWarm: standard(0x241e1a, 0.2, 0.88, 0x120e0a, 0.2),
    darkMetal: standard(0x10161a, 0.86, 0.38, 0x05080a, 0.16),
    serviceMetal: standard(0x1c2a30, 0.76, 0.46, 0x081218, 0.18),
    rustMetal: standard(0x322018, 0.66, 0.58, 0x180c08, 0.18),
    deck: standard(0x141c22, 0.72, 0.42, 0x081018, 0.35),
    deckEdge: standard(0x1a262c, 0.55, 0.48, 0x0c1820, 0.28),
    coldWindow: standard(0x8fc4be, 0.12, 0.28, 0x6fb0a8, 2.8),
    sodiumWindow: standard(0xd4a070, 0.1, 0.3, 0xc88848, 3.1),
    hazard: standard(0xc86a48, 0.18, 0.34, 0xb04a30, 2.4),
    neonCyan: standard(0xa8d8d0, 0.06, 0.24, 0x68b0a4, 3.2),
    neonMagenta: standard(0xd4a888, 0.06, 0.24, 0xa87850, 2.8),
    neonAmber: standard(0xe0c098, 0.06, 0.26, 0xc09050, 2.9),
    laneMark: standard(0xd8c8a0, 0.08, 0.4, 0xb8a070, 2.2),
    gutter: standard(0x1a3040, 0.4, 0.5, 0x4a8898, 1.8),
  };
}

function paintBladeMegaAd(ctx, seed, rand) {
  // v28: giant facade ads made of LIGHT (window LEDs / glow panels), not separate boards.
  // Draws into the facade canvas itself so the building surface IS the ad.
  const ads = BLADE_AD_CATALOG;
  const a = ads[Math.abs(seed | 0) % ads.length];
  const brand = String(a[0] || "NEXUS");
  const title = String(a[1] || "CITY");
  const tag = String(a[2] || "").slice(0, 22);
  const hex = String(a[3] || "#8fbdb4");
  const kicker = String(a[4] || "").slice(0, 18);

  // parse hex → rgb
  let r = 140, g = 200, b = 180;
  const m = /^#?([0-9a-f]{6})$/i.exec(hex);
  if (m) {
    r = parseInt(m[1].slice(0, 2), 16);
    g = parseInt(m[1].slice(2, 4), 16);
    b = parseInt(m[1].slice(4, 6), 16);
  }

  // LED wall panel region (mid facade) — dark glass with dense lit cells
  const px = 6, py = 48, pw = 116, ph = 120;
  ctx.fillStyle = "rgba(4,8,14,0.92)";
  ctx.fillRect(px, py, pw, ph);

  // grid of "pixels" forming the ad body
  const cell = 3;
  for (let y = py + 2; y < py + ph - 2; y += cell + 1) {
    for (let x = px + 2; x < px + pw - 2; x += cell + 1) {
      const edge = x < px + 8 || x > px + pw - 10 || y < py + 6 || y > py + ph - 8;
      const aLit = edge ? 0.15 + rand() * 0.15 : 0.25 + rand() * 0.55;
      if (!edge && rand() < 0.08) continue; // dead pixels
      ctx.fillStyle = `rgba(${r},${g},${b},${aLit})`;
      ctx.fillRect(x, y, cell, cell);
    }
  }

  // soft brand glow field (reads as big light logo block)
  const gx = px + 8, gy = py + 18, gw = pw - 16, gh = 38;
  const grad = ctx.createLinearGradient(gx, gy, gx + gw, gy + gh);
  grad.addColorStop(0, `rgba(${r},${g},${b},0.15)`);
  grad.addColorStop(0.45, `rgba(${r},${g},${b},0.85)`);
  grad.addColorStop(1, `rgba(${r},${g},${b},0.2)`);
  ctx.fillStyle = grad;
  ctx.fillRect(gx, gy, gw, gh);

  // text as emissive light (canvas text → part of facade map)
  ctx.save();
  ctx.shadowColor = `rgb(${r},${g},${b})`;
  ctx.shadowBlur = 10;
  ctx.fillStyle = `rgba(${Math.min(255, r + 40)},${Math.min(255, g + 40)},${Math.min(255, b + 40)},0.95)`;
  ctx.font = "bold 11px monospace";
  ctx.fillText(brand.slice(0, 14), px + 10, py + 16);
  ctx.font = "900 28px Arial Narrow, sans-serif";
  ctx.fillText(title.slice(0, 10), px + 10, py + 48);
  ctx.shadowBlur = 6;
  ctx.font = "600 9px monospace";
  ctx.fillStyle = `rgba(255,240,220,0.85)`;
  ctx.fillText(tag || kicker, px + 10, py + 68);
  ctx.font = "500 8px monospace";
  ctx.fillStyle = `rgba(${r},${g},${b},0.75)`;
  ctx.fillText(kicker || "PUBLIC SIGNAL", px + 10, py + 84);
  ctx.restore();

  // scanlines / horizontal LED strips (reads as media facade)
  ctx.fillStyle = `rgba(${r},${g},${b},0.18)`;
  for (let y = py + 92; y < py + ph - 6; y += 5) {
    ctx.fillRect(px + 6, y, pw - 12, 2);
  }
  // thin frame glow
  ctx.strokeStyle = `rgba(${r},${g},${b},0.55)`;
  ctx.lineWidth = 1;
  ctx.strokeRect(px + 0.5, py + 0.5, pw - 1, ph - 1);
}

function makeBladeFacadeTexture(seed, warmBias = 0.35, style = 0, megaAd = false) {
  // v26: multiple window languages; v28: optional mega light-ad baked into surface
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 256;
  const ctx = canvas.getContext("2d");
  let s = (seed * 1664525 + 1013904223) >>> 0;
  const rand = () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return (s >>> 0) / 4294967296;
  };
  const bases = ["#1a242c", "#2a221c", "#181e28", "#222018", "#1c2620", "#201c28"];
  ctx.fillStyle = bases[style % bases.length];
  ctx.fillRect(0, 0, 128, 256);

  const vStep = [10, 14, 16, 12, 8, 18][style % 6];
  const hStep = [10, 12, 14, 8, 16, 11][style % 6];
  ctx.fillStyle = "rgba(6,10,14,0.42)";
  for (let x = 0; x < 128; x += vStep) ctx.fillRect(x, 0, style % 3 === 0 ? 1 : 2, 256);
  ctx.fillStyle = "rgba(4,8,12,0.55)";
  for (let y = 0; y < 256; y += hStep) ctx.fillRect(0, y, 128, style % 2 ? 1 : 2);

  const cols = [5, 6, 7, 8, 4, 9][style % 6];
  const rows = [16, 18, 20, 22, 14, 24][style % 6];
  const cellW = 128 / cols;
  const cellH = 256 / rows;
  const litSkip = [0.22, 0.32, 0.40, 0.18, 0.50, 0.28][style % 6];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const roll = rand();
      if (roll < litSkip) continue;
      if (style % 6 === 2 && r % 3 === 0 && rand() > 0.35) {
        ctx.fillStyle = warmBias > 0.5
          ? `rgba(230,${160 + (rand() * 40) | 0},90,0.7)`
          : `rgba(100,${180 + (rand() * 40) | 0},190,0.65)`;
        ctx.fillRect(2, r * cellH + 1, 124, cellH - 2);
        break;
      }
      const warm = rand() < warmBias;
      const a = 0.55 + rand() * 0.4;
      if (style % 6 === 4) {
        if (rand() > 0.35) continue;
        ctx.fillStyle = `rgba(${200 + (rand() * 40) | 0},${120 + (rand() * 40) | 0},60,${a})`;
      } else if (warm) {
        ctx.fillStyle = `rgba(${210 + (rand() * 40) | 0},${140 + (rand() * 60) | 0},${70 + (rand() * 50) | 0},${a})`;
      } else {
        ctx.fillStyle = `rgba(${100 + (rand() * 60) | 0},${170 + (rand() * 50) | 0},${170 + (rand() * 50) | 0},${a})`;
      }
      const padX = 1.0 + rand() * 2.0;
      const padY = 1.0 + rand() * 1.4;
      if (style % 6 === 5 && c % 2 === 0) {
        ctx.fillRect(c * cellW + padX, r * cellH + 0.5, Math.max(2, cellW * 0.35), cellH - 1);
      } else {
        ctx.fillRect(c * cellW + padX, r * cellH + padY, cellW - padX * 2, cellH - padY * 2 - 1);
      }
    }
  }
  const bands = 1 + (style % 3);
  for (let b = 0; b < bands; b++) {
    const y = ((seed + b * 41 + style * 13) % 18) * 12 + 4;
    const cool = (style + b) % 2 === 0;
    ctx.fillStyle = cool ? "rgba(120,210,200,0.42)" : "rgba(230,170,100,0.48)";
    ctx.fillRect(2, y, 124, style % 6 === 2 ? 9 : 5);
  }

  // v28: bake giant light-ad into surface (not a billboard mesh)
  if (megaAd) {
    paintBladeMegaAd(ctx, seed, rand);
  }

  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  // mega-ad facades should NOT tile-repeat into gibberish — single face panel
  tex.wrapS = tex.wrapT = megaAd ? THREE.ClampToEdgeWrapping : THREE.RepeatWrapping;
  tex.magFilter = THREE.NearestFilter;
  tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.anisotropy = 4;
  return tex;
}

function getBladeFacadeMaterial(seed, width = 10, height = 40, megaAd = false) {
  // v26: 16 facade variants; v28: megaAd = light-composed facade ads (unique per seed)
  if (megaAd) {
    // unique cache key — ad content depends on seed
    const key = `mega:${Math.abs(seed | 0) % 64}`;
    if (!bladeFacadeCache[key]) {
      const warmBias = 0.45;
      const map = makeBladeFacadeTexture(2000 + (Math.abs(seed | 0) % 64) * 17, warmBias, (seed | 0) % 6, true);
      map.repeat.set(1, 1);
      const mat = new THREE.MeshStandardMaterial({
        map,
        color: 0xffffff,
        metalness: 0.28,
        roughness: 0.62,
        emissiveMap: map,
        emissive: 0xffffff,
        emissiveIntensity: bladeHardwareFallback ? 2.55 : 2.05,
      });
      bladeFacadeCache[key] = mat;
    }
    const shared = bladeFacadeCache[key];
    const mat = shared.clone();
    mat.map = shared.map.clone();
    mat.map.repeat.set(1, 1);
    mat.emissiveMap = mat.map;
    mat.emissiveIntensity = bladeHardwareFallback ? 2.55 : 2.05;
    return mat;
  }

  const idx = Math.abs(seed | 0) % 16;
  if (!bladeFacadeCache[idx]) {
    const warmBias = [0.22, 0.55, 0.35, 0.70, 0.18, 0.48, 0.62, 0.30,
                      0.40, 0.75, 0.25, 0.58, 0.15, 0.50, 0.68, 0.33][idx];
    const map = makeBladeFacadeTexture(1000 + idx * 97, warmBias, idx % 6, false);
    map.repeat.set(Math.max(1, Math.round(width / 8)), Math.max(2, Math.round(height / 18)));
    const mat = new THREE.MeshStandardMaterial({
      map,
      color: 0xffffff,
      metalness: 0.35,
      roughness: 0.72,
      emissiveMap: map,
      emissive: 0xffffff,
      emissiveIntensity: bladeHardwareFallback ? 2.15 : 1.65,
    });
    bladeFacadeCache[idx] = mat;
  }
  const shared = bladeFacadeCache[idx];
  const mat = shared.clone();
  mat.map = shared.map.clone();
  mat.map.repeat.set(
    Math.max(1, Math.round(width / 8)),
    Math.max(2, Math.round(height / 18))
  );
  mat.emissiveMap = mat.map;
  mat.emissiveIntensity = bladeHardwareFallback ? 2.15 : 1.65;
  return mat;
}

function makeBladeDeckSegment(i) {
  // Visible flight deck under the spinner: wet asphalt + lane marks + edge gutters.
  // Scrolls with the world so the corridor never feels like flying over pure void.
  const group = new THREE.Group();
  const deck = new THREE.Mesh(new THREE.BoxGeometry(18.5, 0.55, 22), bladeMaterials.deck);
  deck.position.y = 0;
  group.add(deck);

  // Shoulder plates — slightly raised curb so edge reads against fog.
  for (const x of [-8.2, 8.2]) {
    const curb = new THREE.Mesh(new THREE.BoxGeometry(2.2, 0.85, 22), bladeMaterials.deckEdge);
    curb.position.set(x, 0.2, 0);
    group.add(curb);
  }

  // Center lane dashes.
  for (let n = 0; n < 4; n++) {
    const dash = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.08, 2.4), bladeMaterials.laneMark);
    dash.position.set(0, 0.32, -8 + n * 5.2);
    group.add(dash);
  }
  // Side lane lines.
  for (const x of [-3.4, 3.4]) {
    const line = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.06, 20), bladeMaterials.laneMark);
    line.position.set(x, 0.3, 0);
    group.add(line);
  }

  // Sodium gutter lamps along both edges — the "street is lit" cue.
  for (const x of [-9.1, 9.1]) {
    for (let n = 0; n < 3; n++) {
      if ((n + i) % 4 === 0) continue;
      const post = new THREE.Mesh(new THREE.BoxGeometry(0.18, 1.6, 0.18), bladeMaterials.darkMetal);
      post.position.set(x, 1.0, -7 + n * 7);
      group.add(post);
      const lamp = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.16, 0.9), bladeMaterials.sodiumWindow);
      lamp.position.set(x - Math.sign(x) * 0.15, 1.85, -7 + n * 7);
      group.add(lamp);
      // Soft spill disc on deck.
      const spill = new THREE.Mesh(
        new THREE.CircleGeometry(1.2, 12),
        new THREE.MeshBasicMaterial({
          color: 0xa88868,
          transparent: true,
          opacity: 0.07,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
          toneMapped: false,
        })
      );
      spill.rotation.x = -Math.PI / 2;
      spill.position.set(x - Math.sign(x) * 1.2, 0.36, -7 + n * 7);
      group.add(spill);
    }
    // Cyan air-lane marker strip in gutter.
    const gutter = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.1, 20), bladeMaterials.gutter);
    gutter.position.set(x - Math.sign(x) * 0.9, 0.34, 0);
    group.add(gutter);
  }

  // Lower street suggestion under the deck — parallax depth, not playable.
  const under = new THREE.Mesh(new THREE.BoxGeometry(22, 0.35, 22), bladeMaterials.darkMetal);
  under.position.y = -4.2;
  group.add(under);
  for (let n = 0; n < 5; n++) {
    const streetLamp = new THREE.Mesh(
      new THREE.BoxGeometry(0.35, 0.12, 1.6),
      n % 2 ? bladeMaterials.sodiumWindow : bladeMaterials.coldWindow
    );
    streetLamp.position.set((n - 2) * 3.6, -3.9, (i % 2 ? 1 : -1) * 4);
    group.add(streetLamp);
  }

  group.userData = { z: -8 - i * 20 };
  group.position.set(0, 0.4, group.userData.z);
  return group;
}

function makeBladeLandmark() {
  // v27: vanishing-point skyline that NEVER enters free-air envelope.
  // rocktree: open canyon center + mass at horizon. Center cluster is deep/low/narrow.
  const root = new THREE.Group();
  const mk = (w, h, d, mat, x, y, z) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
    m.position.set(x, y, z);
    root.add(m);
    return m;
  };
  // LEFT/RIGHT banks — well outside air half (min |x| ~ 28)
  for (const side of [-1, 1]) {
    mk(16, 70 + side * 4, 14, bladeMaterials.concreteWarm, side * 48, 20, -side * 6);
    mk(12, 54, 11, bladeMaterials.darkMetal, side * 40, 34, 8);
    mk(9, 40, 9, bladeMaterials.serviceMetal, side * 34, 42, -10);
    mk(7, 88, 7, getBladeFacadeMaterial(310 + side * 3, 7, 88), side * 56, 36, -14);
    const spine = new THREE.Mesh(new THREE.BoxGeometry(0.28, 48, 0.1), bladeMaterials.neonAmber);
    spine.position.set(side * 44, 28, 10);
    root.add(spine);
  }
  // DEEP center vanishing silhouettes — narrow needles / low pods only
  // Keep |x| + halfW small in screen space via distance, not by filling the lane.
  const centerPlan = [
    // w,h,d, mat, x, yBase, zLocal (relative to landmark root)
    [10, 22, 10, "concrete", 0, -6, 8],
    [6, 38, 6, "concreteWarm", -5, -2, -8],
    [5, 48, 5, "darkMetal", 5, 0, -14],
    [4, 56, 4, "serviceMetal", -2, 2, -22],
    [3.5, 64, 3.5, "darkMetal", 3, 4, -28],
    [8, 18, 8, "concreteWarm", 0, -8, -4],
    [4, 32, 4, "serviceMetal", -8, -1, -18],
    [4, 36, 4, "darkMetal", 8, 0, -20],
  ];
  const matMap = {
    concrete: bladeMaterials.concrete,
    concreteWarm: bladeMaterials.concreteWarm,
    darkMetal: bladeMaterials.darkMetal,
    serviceMetal: bladeMaterials.serviceMetal,
  };
  for (let i = 0; i < centerPlan.length; i++) {
    const [w, h, d, mkName, x, yb, z] = centerPlan[i];
    const mat = h > 40
      ? getBladeFacadeMaterial(220 + i * 11, w, h)
      : matMap[mkName];
    mk(w, h, d, mat, x, yb + h / 2 - 8, z);
  }
  // sodium crown pips (depth cue)
  for (const [x, y, z] of [[-5, 30, -8], [5, 40, -14], [3, 52, -28], [0, 10, 6]]) {
    const lamp = new THREE.Mesh(
      new THREE.BoxGeometry(0.9, 0.6, 0.9),
      bladeMaterials.sodiumWindow
    );
    lamp.position.set(x, y - 6, z);
    root.add(lamp);
  }
  // soft horizon haze — decorative, not a solid wall
  const haze = new THREE.Mesh(
    new THREE.PlaneGeometry(70, 14),
    new THREE.MeshBasicMaterial({
      color: 0x1a2830,
      transparent: true,
      opacity: 0.28,
      depthWrite: false,
      fog: true,
    })
  );
  haze.position.set(0, 1, 16);
  root.add(haze);

  // deep + slow — recycle keeps it past z=-160 so it never becomes mid-FOV slab
  root.userData = { baseX: 0, baseZ: -240, parallax: 0.22, minZ: -160 };
  root.position.set(0, 0, -240);
  return root;
}

function makeFogSheet(i) {
  // v25: very soft side haze only — never a colored slab in FOV center
  const mat = new THREE.MeshBasicMaterial({
    color: 0x3a4a52,
    transparent: true,
    opacity: isMobile ? 0.012 : 0.018,
    blending: THREE.NormalBlending,
    depthWrite: false,
    side: THREE.DoubleSide,
    fog: false,
  });
  const sheet = new THREE.Mesh(new THREE.PlaneGeometry(28, 14), mat);
  const side = i % 2 ? -1 : 1;
  const baseX = side * (30 + i * 4);
  sheet.position.set(baseX, 8 + (i % 2) * 2, -60 - i * 45);
  sheet.rotation.y = side * -0.4;
  sheet.userData = { baseX, phase: i * 1.13, side };
  return sheet;
}

function makeSearchlight(i) {
  // v25: far side beams, low opacity — never cross spinner path
  const root = new THREE.Group();
  const material = new THREE.MeshBasicMaterial({
    color: 0xa89878,
    transparent: true,
    opacity: isMobile ? 0.012 : 0.018,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  const beam = new THREE.Mesh(new THREE.ConeGeometry(3.2, 42, 12, 1, true), material);
  beam.position.y = -22;
  root.add(beam);
  const baseX = i % 2 ? -40 : 40;
  root.position.set(baseX, 42 + i * 2, -80 - i * 70);
  root.userData = { phase: i * 1.9, baseZ: root.position.z, baseX };
  return root;
}

function buildBladeWorld() {
  if (bladeHardwareFallback) {
    renderer.setPixelRatio(isMobile ? 0.75 : 0.6);
    renderer.setSize(window.innerWidth, window.innerHeight);
  }
  // Phase 0 exposure: mid-ground must read before photographic restraint.
  // v25: lift mid-ground readability (rocktree dusk-grey, not crushed blacks)
  scene.background.set(0x0b1a22);
  // v26: farther fog end so vanishing skyline still reads
  scene.fog = new THREE.Fog(0x121f28, isMobile ? 40 : 55, isMobile ? 220 : 300);
  camera.fov = isMobile ? 52 : 48;
  camera.far = 380;
  camera.updateProjectionMatrix();
  renderer.toneMappingExposure = bladeHardwareFallback ? 1.48 : 1.38;
  if (bloomPass) {
    // restrained bloom — windows read, no neon soup
    bloomPass.strength = isMobile ? 0.26 : 0.34;
    bloomPass.radius = 0.38;
    bloomPass.threshold = 0.62;
  }
  scene.getObjectByName("base-ambient").intensity = 0.78;
  scene.getObjectByName("base-hemi").intensity = 0.62;
  scene.getObjectByName("base-sun").intensity = 0.42;
  // cool grey + sodium — no candy wash
  scene.getObjectByName("base-cyan").visible = true;
  scene.getObjectByName("base-magenta").visible = true;
  scene.getObjectByName("base-cyan").intensity = bladeHardwareFallback ? 1.4 : 1.8;
  scene.getObjectByName("base-magenta").intensity = bladeHardwareFallback ? 1.0 : 1.2;
  scene.getObjectByName("base-cyan").color.set(0x8aa0a8);
  scene.getObjectByName("base-magenta").color.set(0xa89888);
  bladeMaterials = makeBladeMaterials();

  const ambient = new THREE.AmbientLight(0x6a7a80, 1.15);
  const overcast = new THREE.HemisphereLight(0x8a9aa0, 0x181c20, 1.15);
  const sodium = new THREE.DirectionalLight(0xd0b090, 1.05);
  sodium.position.set(-10, 8, -18);
  const institutional = new THREE.DirectionalLight(0xa8bcc2, 0.95);
  institutional.position.set(-6, 22, 10);
  const deckFill = new THREE.DirectionalLight(0xb8a898, 0.7);
  deckFill.position.set(0, -6, 4);
  addWorld(ambient, overcast, sodium, institutional, deckFill);

  // Continuous flight deck under the corridor — THIS is the ground.
  const deckCount = bladeHardwareFallback ? 8 : 10;
  for (let i = 0; i < deckCount; i++) {
    const seg = makeBladeDeckSegment(i);
    addWorld(seg);
    bladeDeckPool.push(seg);
  }

  // Far wet void — scrolls slowly as deep floor (pooled as glint-like parallax)
  const voidFloor = new THREE.Mesh(
    new THREE.PlaneGeometry(80, 160),
    new THREE.MeshStandardMaterial({
      color: 0x0a141c,
      emissive: 0x081820,
      emissiveIntensity: 0.55,
      metalness: 0.85,
      roughness: 0.28,
    })
  );
  voidFloor.rotation.x = -Math.PI / 2;
  voidFloor.position.set(0, -4.6, -140);
  voidFloor.userData = { baseX: 0, parallax: 0.25, kind: "void" };
  addWorld(voidFloor);
  bladeGlintPool.push(voidFloor);

  // Quiet wet-street glints under deck — MUST scroll with world (was the "stuck color bars")
  const reflectionMats = [0x6a7a78, 0x8a7860].map((color) => new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: bladeHardwareFallback ? 0.05 : 0.07,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    toneMapped: false,
  }));
  for (let i = 0; i < 4; i++) {
    const streak = new THREE.Mesh(new THREE.PlaneGeometry(0.7 + (i % 2) * 0.3, 22 + (i % 3) * 4), reflectionMats[i % 2]);
    streak.rotation.x = -Math.PI / 2;
    // keep glints under shoulders, not center FOV paint
    const side = i % 2 ? -1 : 1;
    const baseX = side * (5.5 + (i % 2) * 1.2);
    streak.position.set(baseX, -4.45, -40 - i * 28);
    streak.userData = { baseX, parallax: 1.0, kind: "glint" };
    addWorld(streak);
    bladeGlintPool.push(streak);
  }

  // Far megablocks — pooled so they recycle/scroll like near towers
  const farCount = bladeHardwareFallback ? (isMobile ? 8 : 11) : (isMobile ? 10 : 14);
  for (let i = 0; i < farCount; i++) {
    const slab = makeBladeFarSlab(i);
    addWorld(slab);
    bladeFarSlabPool.push(slab);
  }

  // v27: NO mid-corridor axis slabs — those scrolled through free-air and clipped craft.
  // Vanishing mass lives only in makeBladeLandmark (deep z, never enters envelope).

  // Dense multi-row skyline with stronger packing variance
  const towerCount = bladeHardwareFallback ? (isMobile ? 18 : 24) : (isMobile ? 20 : 30);
  for (let i = 0; i < towerCount; i++) {
    const tower = makeBladeTower(i);
    addWorld(tower);
    bladeTowerPool.push(tower);
  }
  for (let i = 0; i < 5; i++) {
    const gate = makeBladeGate(i);
    addWorld(gate);
    bladeGatePool.push(gate);
  }

  // v25: sparse photo billboards well outside free-air envelope
  const bbCount = bladeHardwareFallback ? (isMobile ? 4 : 6) : (isMobile ? 5 : 8);
  for (let i = 0; i < bbCount; i++) {
    const bb = makeStandaloneBillboard(i, BLADE_AD_CATALOG, true);
    const side = bb.userData.side;
    const baseX = side * (BLADE_AIR_HALF + 4.5 + (i % 4) * 1.8);
    bb.userData.baseX = baseX;
    bb.position.set(baseX, 6 + (i % 4) * 2.2, -18 - i * 36);
    bb.rotation.y = side > 0 ? -0.18 : 0.18;
    addWorld(bb);
    bladeBillboardPool.push(bb);
  }

  bladeLandmark = makeBladeLandmark();
  addWorld(bladeLandmark);
  const fogCount = isMobile ? 1 : 2;
  for (let i = 0; i < fogCount; i++) {
    const sheet = makeFogSheet(i);
    addWorld(sheet);
    bladeFogSheets.push(sheet);
  }
  const beamCount = isMobile ? 1 : 2;
  for (let i = 0; i < beamCount; i++) {
    const beam = makeSearchlight(i);
    addWorld(beam);
    bladeSearchlights.push(beam);
  }

  // v25: sparse traffic on OUTER air lanes only — same world-scroll physics family
  const trafficCount = bladeHardwareFallback ? (isMobile ? 2 : 3) : (isMobile ? 3 : 4);
  for (let i = 0; i < trafficCount; i++) {
    const traffic = makeSpinner({ traffic: true, accent: [0x8a9a96, 0xa89078, 0x7a8f8a][i % 3] });
    const side = i % 2 === 0 ? -1 : 1;
    // outer shoulder: never share center FOV with player craft
    const laneX = side * (7.8 + (i % 2) * 1.2);
    const altitude = 4.5 + (i % 3) * 3.8;
    traffic.position.set(laneX, altitude, -40 - i * 36);
    // speed close to player → small relative motion (rocktree: traffic co-moves)
    traffic.userData = { laneX, altitude, speed: 48 + (i % 3) * 4, phase: i * 0.9 };
    addWorld(traffic);
    bladeTrafficPool.push(traffic);
  }

  carMesh = makeSpinner({ traffic: false, accent: 0x8fbdb4 });
  carRoot = new THREE.Group();
  carRoot.add(carMesh);
  carRoot.position.set(0, carState.flightY, 0);
  carState.carWidth = 2.8;
  carState.carLen = 4.1;
  // Always give the spinner a headlight — software GL needs local light most.
  const flightLight = new THREE.SpotLight(0xe8f0e8, bladeHardwareFallback ? 42 : 32, 70, Math.PI / 7, 0.55, 1.3);
  flightLight.position.set(0, 0.4, -1.4);
  flightLight.target.position.set(0, -1.2, -26);
  carRoot.add(flightLight, flightLight.target);
  carState._head = flightLight;
  // Secondary sodium fill under nose so deck stays lit near the car.
  const noseFill = new THREE.PointLight(0xd4a070, bladeHardwareFallback ? 6.5 : 4.2, 28, 1.4);
  noseFill.position.set(0, -0.6, -2.2);
  carRoot.add(noseFill);
  addWorld(carRoot);
  makeBladeRain();
}

function updateBladeRain(dt, move) {
  if (!bladeRainData || !bladeRain) return;
  const { drops, positions } = bladeRainData;
  for (let i = 0; i < drops.length; i++) {
    const d = drops[i];
    d.y -= d.speed * dt;
    d.z += move * 0.38;
    if (d.y < -5 || d.z > 14) {
      d.y = 24 + Math.random() * 8;
      d.x = carRoot.position.x + (Math.random() - 0.5) * 44;
      d.z = -78 - Math.random() * 18;
    }
    const p = i * 6;
    positions[p] = d.x; positions[p + 1] = d.y; positions[p + 2] = d.z;
    positions[p + 3] = d.x - 0.08; positions[p + 4] = d.y - d.len; positions[p + 5] = d.z + 0.34;
  }
  bladeRain.geometry.attributes.position.needsUpdate = true;
}

function advanceCorridorPath(dt, move) {
  // v25: slower boulevard arcs — rocktree long sweeps, not tilt-a-whirl
  pathBendPhase += dt * (0.08 + Math.min(0.05, carState.speed * 0.0006));
  const targetHeading =
    Math.sin(pathBendPhase) * 0.12 +
    Math.sin(pathBendPhase * 0.27 + 0.9) * 0.05;
  pathHeading += (targetHeading - pathHeading) * Math.min(1, dt * 0.7);
  pathBend += Math.sin(pathHeading) * move * 0.18;
  pathBend = THREE.MathUtils.clamp(pathBend, -8, 8);
  pathBendTarget = pathBend;
  return pathBend;
}

function corridorXAt(z) {
  // Minimal lookahead — large z*sin sheared mass into FOV (v23 bug)
  const ahead = THREE.MathUtils.clamp(z, -60, 20);
  return pathBend + Math.sin(pathHeading) * ahead * 0.012;
}

function updateBladeWorld(dt) {
  // v25 physics contract (rocktree-style):
  // 1) Everything that is "city mass" scrolls toward camera at the SAME rate.
  // 2) Only true parallax layers (deep skyline / void) use a fixed slower factor.
  // 3) Traffic shares the airspace but on OUTER lanes with small relative speed.
  // 4) No object yaws its mass into the free-air corridor.
  const move = carState.speed * dt;
  carState.distance += move;
  bladePulse += dt;
  advanceCorridorPath(dt, move);
  const bend = pathBend;
  const head = pathHeading;

  for (const tower of bladeTowerPool) {
    tower.position.z += move;
    if (tower.position.z > 28) {
      const row = tower.userData.depthRow ?? 0;
      const w = tower.userData.width || 10;
      // v27: keep side sticky, pad free-air, irregular spacing only
      const lateral =
        row === 0
          ? BLADE_AIR_HALF + w / 2 + 2.4 + Math.random() * 2.0
          : row === 1
            ? BLADE_AIR_HALF + w / 2 + 9 + Math.random() * 3.5
            : BLADE_AIR_HALF + w / 2 + 16 + Math.random() * 4.5;
      tower.position.z -= bladeTowerPool.length * (9.0 + Math.random() * 3.5);
      tower.userData.baseX = tower.userData.side * lateral;
    }
    tower.position.x = tower.userData.baseX + corridorXAt(tower.position.z);
    tower.rotation.y = 0;
  }

  for (const deck of bladeDeckPool) {
    deck.position.z += move;
    if (deck.position.z > 18) {
      deck.position.z -= bladeDeckPool.length * 20;
    }
    deck.position.x = corridorXAt(deck.position.z);
    deck.rotation.y = -head * 0.25;
  }

  // Far slabs scroll on OUTER banks only (v27: no center-axis free-air mass)
  for (const slab of bladeFarSlabPool) {
    slab.position.z += move * 0.92;
    if (slab.position.z > 40) {
      const w = slab.userData.width || 16;
      const side = slab.userData.side || 1;
      slab.position.z -= Math.max(24, bladeFarSlabPool.length * 18);
      // hard free-air: outer bank only, min |x| well past air half + half-width
      slab.userData.baseX = side * (36 + Math.random() * 12 + w * 0.15);
      slab.userData.side = side;
    }
    slab.position.x = (slab.userData.baseX || 0) + corridorXAt(slab.position.z) * 0.55;
    slab.rotation.y = 0;
  }

  for (const g of bladeGlintPool) {
    const para = g.userData.parallax ?? 1;
    g.position.z += move * para;
    if (g.userData.kind === "glint" && g.position.z > 16) {
      g.position.z -= 4 * 28;
    }
    if (g.userData.kind === "void" && g.position.z > -40) {
      g.position.z = -140;
    }
    if (g.userData.baseX != null) {
      g.position.x = g.userData.baseX + corridorXAt(g.position.z) * (para > 0.5 ? 1 : 0.3);
    }
  }

  for (const bb of bladeBillboardPool) {
    bb.position.z += move;
    if (bb.position.z > 22) {
      bb.position.z -= bladeBillboardPool.length * 36;
      const side = bb.userData.side;
      bb.userData.baseX = side * (BLADE_AIR_HALF + 4.5 + Math.random() * 5);
      bb.position.y = 5 + Math.random() * 10;
    }
    bb.position.x = (bb.userData.baseX || 0) + corridorXAt(bb.position.z);
    bb.rotation.y = bb.userData.side > 0 ? -0.18 : 0.18;
  }

  for (const holo of bladeHolograms) {
    if (holo.material && holo.material.blending === THREE.AdditiveBlending) {
      const base = holo.userData.baseOpacity ?? 0.82;
      holo.material.opacity = base + Math.sin(bladePulse * 1.6 + holo.userData.phase) * 0.02;
    }
  }

  for (const sheet of bladeFogSheets) {
    // same family as city — soft side haze scrolls, never drifts to center
    sheet.position.z += move * 0.55;
    sheet.position.x = sheet.userData.baseX + bend * 0.1;
    if (sheet.position.z > 20) sheet.position.z -= bladeFogSheets.length * 50;
  }

  for (const light of bladeSearchlights) {
    light.position.z += move * 0.4;
    light.position.x = (light.userData.baseX || 0) + bend * 0.12;
    // gentle sweep, keep beams on outer banks
    light.rotation.z = Math.sin(bladePulse * 0.12 + light.userData.phase) * 0.28;
    light.rotation.x = Math.sin(bladePulse * 0.09 + light.userData.phase) * 0.05;
    if (light.position.z > 24) light.position.z = (light.userData.baseZ || -80) - 160;
  }

  if (bladeLandmark) {
    const para = bladeLandmark.userData.parallax ?? 0.22;
    const minZ = bladeLandmark.userData.minZ ?? -160;
    bladeLandmark.position.z += move * para;
    // v27: never let horizon mass enter mid FOV / free-air
    if (bladeLandmark.position.z > minZ) {
      bladeLandmark.position.z = bladeLandmark.userData.baseZ || -240;
    }
    // keep twin towers on sides of vanishing point
    bladeLandmark.position.x = bend * 0.12 + carRoot.position.x * -0.015;
  }

  for (const gate of bladeGatePool) {
    const prevZ = gate.position.z;
    gate.position.z += move;
    gate.position.x = corridorXAt(gate.position.z);
    gate.rotation.y = -head * 0.18;
    if (!bootPreview && !gate.userData.checked && prevZ < -1.2 && gate.position.z >= -1.2) {
      const dx = Math.abs(carRoot.position.x - gate.position.x);
      const dy = Math.abs(carRoot.position.y - gate.position.y);
      // wide free air — only punish extreme misses
      if (dx < 9.0 && dy < 6.0) {
        carState.gateCount += 1;
        carState.nitro = Math.min(1, carState.nitro + 0.14);
      } else {
        carState.crash = 0.45;
        carState.speed *= 0.85;
      }
      gate.userData.checked = true;
    }
    if (gate.position.z > 18) {
      gate.position.z -= bladeGatePool.length * 52;
      gate.position.y = [5.5, 8.2, 11.5, 14.8, 17.5][Math.floor(Math.random() * 5)];
      gate.userData.y = gate.position.y;
      gate.userData.checked = false;
    }
  }

  for (const t of bladeTrafficPool) {
    const rel = carState.speed - t.userData.speed;
    t.position.z += rel * dt;
    const cx = corridorXAt(t.position.z);
    // hard outer lane — tiny sway only
    t.position.x = cx + t.userData.laneX + Math.sin(bladePulse * 0.4 + t.userData.phase) * 0.15;
    t.position.y = t.userData.altitude + Math.sin(bladePulse * 0.7 + t.userData.phase) * 0.15;
    t.rotation.y = -head * 0.18;
    t.rotation.z = -head * 0.05;
    if (t.position.z > 16 || t.position.z < -200) {
      t.position.z = -100 - Math.random() * 70;
      const side = Math.random() < 0.5 ? -1 : 1;
      t.userData.laneX = side * (7.8 + Math.random() * 1.4);
      t.userData.altitude = 4.2 + Math.random() * 8;
      t.userData.speed = 46 + Math.random() * 10;
    }
    const dx = Math.abs(t.position.x - carRoot.position.x);
    const dy = Math.abs(t.position.y - carRoot.position.y);
    const dz = Math.abs(t.position.z);
    if (!bootPreview && dx < 1.5 && dy < 1.0 && dz < 2.0 && carState.hitCd <= 0) {
      carState.speed *= 0.55;
      carState.hitCd = 0.8;
      carState.crash = 0.7;
      carState.nitro = Math.max(0.1, carState.nitro - 0.15);
      t.position.z = -90 - Math.random() * 40;
    }
  }
  updateBladeRain(dt, move);
}

function updateSpinner(dt) {
  const steer = (keys.left ? -1 : 0) + (keys.right ? 1 : 0);
  const lift = (keys.up ? 1 : 0) + (keys.down ? -1 : 0);
  if (carState.hitCd > 0) carState.hitCd -= dt;
  carState.nitroOn = keys.nitro && carState.nitro > 0.05;
  carState.crash = Math.max(0, carState.crash - dt * 1.8);

  const targetSpeed = carState.nitroOn ? 92 : 58;
  carState.speed += (targetSpeed - carState.speed) * Math.min(1, dt * 2.1);
  if (carState.nitroOn) carState.nitro = Math.max(0, carState.nitro - dt * 0.25);
  else carState.nitro = Math.min(1, carState.nitro + dt * 0.1);

  carState.x += steer * dt * (0.9 + carState.speed * 0.015);
  carState.x = THREE.MathUtils.clamp(carState.x, -0.96, 0.96);
  carState.flightY += lift * dt * (5.2 + carState.speed * 0.02);
  // v23: climb into super-tall band so height variety is playable
  carState.flightY = THREE.MathUtils.clamp(carState.flightY, 2.0, 28);
  // Light curve assist — player still owns the lane
  const curveAssist = pathHeading * 0.25;
  carState.yaw += ((steer + curveAssist) - carState.yaw) * Math.min(1, dt * 5.5);
  carState.pitch += (lift - carState.pitch) * Math.min(1, dt * 4.8);

  const x = pathBend + carState.x * 7.2;
  carRoot.position.set(x, carState.flightY, 0);
  carRoot.rotation.y = -pathHeading * 0.45 - carState.yaw * 0.16;
  carRoot.rotation.z = -carState.yaw * 0.28 - pathHeading * 0.18;
  carRoot.rotation.x = carState.pitch * 0.12;
  const hover = Math.sin(performance.now() * 0.004) * 0.05;
  carMesh.position.y = hover;
  carMesh.traverse((o) => {
    if (o.userData.thruster) {
      const boost = carState.nitroOn ? 1.65 : 1;
      o.scale.y = boost + Math.sin(bladePulse * 18) * 0.08;
      o.material.opacity = carState.nitroOn ? 0.98 : 0.7;
    }
  });
  if (carState._head) carState._head.intensity = carState.nitroOn
    ? (bladeHardwareFallback ? 55 : 42)
    : (bladeHardwareFallback ? 42 : 32);

  const lookX = pathBend + Math.sin(pathHeading) * 4 + carState.x * 5.5;
  const camPos = new THREE.Vector3(
    x * 0.7 + carState.yaw - Math.sin(pathHeading) * 1.0,
    carState.flightY + 2.55,
    11.2 + Math.min(1.6, carState.speed * 0.012)
  );
  camera.position.lerp(camPos, 1 - Math.pow(0.0015, dt));
  camera.lookAt(lookX, carState.flightY + carState.pitch * 0.8, -10.5);
}

function applySunsetLook() {
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, isMobile ? 1.25 : 1.5));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.shadowMap.enabled = !isMobile && !bladeHardwareFallback;
  scene.background.set(0x241428);
  scene.fog = new THREE.FogExp2(0x3a2048, 0.0085);
  camera.fov = 58;
  camera.far = 420;
  camera.updateProjectionMatrix();
  renderer.toneMappingExposure = 1.38;
  const amb = scene.getObjectByName("base-ambient");
  if (amb) { amb.intensity = 0.92; amb.color.set(0xffd2b0); }
  const hemi = scene.getObjectByName("base-hemi");
  if (hemi) {
    hemi.intensity = 1.15;
    hemi.color.set(0xffd8b8);
    hemi.groundColor.set(0x4a2040);
  }
  const sun = scene.getObjectByName("base-sun");
  if (sun) {
    sun.intensity = 2.55;
    sun.color.set(0xffa86a);
    sun.position.set(12, 16, -16);
  }
  const cyan = scene.getObjectByName("base-cyan");
  const mag = scene.getObjectByName("base-magenta");
  if (cyan) { cyan.visible = true; cyan.intensity = 12; cyan.color.set(0x5ad4ff); }
  if (mag) { mag.visible = true; mag.intensity = 14; mag.color.set(0xff5ab0); }
  if (bloomPass) {
    bloomPass.strength = isMobile ? 0.34 : 0.5;
    bloomPass.radius = 0.48;
    bloomPass.threshold = 0.78;
  }
}

function startBootPreview(forceScene = null) {
  if (!assetsCache) return;
  const want = forceScene || selectedScene || "blade";
  // already showing this scene as living wallpaper
  if (bootPreview && bootPreviewScene === want && worldRoot) return;

  removeWorld();
  worldRoot = new THREE.Group();
  worldRoot.name = want === "blade" ? "blade-boot-preview" : "sunset-boot-preview";
  scene.add(worldRoot);

  // Build with the preview scene active, then keep catalog selection as-is
  // (caller already set selectedScene; vehicle is paired in syncRunCards).
  const savedScene = selectedScene;
  const savedVehicle = selectedVehicle;
  selectedScene = want;
  selectedVehicle = want === "blade" ? "spinner" : "cruiser";
  resetRunState();

  if (want === "blade") {
    carState.speed = 46;
    carState.flightY = 8.5;
    buildBladeWorld();
    document.body.classList.add("is-blade");
  } else {
    carState.speed = 34;
    carState.flightY = 0;
    applySunsetLook();
    buildEnvironment(assetsCache);
    buildWorld(assetsCache);
    document.body.classList.remove("is-blade");
  }

  selectedScene = savedScene;
  selectedVehicle = savedVehicle;
  document.body.classList.add("is-selecting");
  document.body.classList.remove("is-paused");
  bootPreview = true;
  bootPreviewScene = want;
  bootCamT = 0;
  launched = false;
  selecting = true;
  introGone = true;
  intro?.classList.remove("ready");
  intro?.classList.add("gone");
  if (carRoot) {
    carRoot.position.set(0, want === "blade" ? carState.flightY : 0, 0);
    carRoot.visible = true;
  }
}

// back-compat alias
function startBladeBootPreview() {
  startBootPreview("blade");
}

function stopBladeBootPreview() {
  bootPreview = false;
  bootPreviewScene = null;
  bootCamT = 0;
}

function updateBladeBootLoop(dt) {
  if (!bootPreview || !carRoot) return;
  bootCamT += dt;
  const loop = BOOT_LOOP_SEC;
  const u = (bootCamT % loop) / loop; // 0..1
  // Autopilot cruise — world scrolls, craft weaves like a film establishing shot.
  carState.speed = 44 + Math.sin(bootCamT * 0.55) * 6;
  carState.nitroOn = (bootCamT % loop) > loop * 0.62 && (bootCamT % loop) < loop * 0.78;
  carState.nitro = carState.nitroOn ? 0.55 : 0.85;
  // Lane weave + follow corridor curve so boot is not a straight tunnel
  carState.x = Math.sin(bootCamT * 0.32) * 0.42 + Math.sin(bootCamT * 0.11) * 0.12;
  // Altitude sweeps low streets → upper spires
  carState.flightY = 5.5 + Math.sin(bootCamT * 0.28) * 4.2 + Math.sin(bootCamT * 0.09) * 1.8;
  carState.yaw += ((Math.sin(bootCamT * 0.32) * 0.4 + pathHeading * 0.3) - carState.yaw) * Math.min(1, dt * 3.2);
  carState.pitch += (Math.sin(bootCamT * 0.38) * 0.35 - carState.pitch) * Math.min(1, dt * 2.8);
  // distance/scroll is advanced inside updateBladeWorld

  updateBladeWorld(dt);

  const x = pathBend + carState.x * 8.2;
  carRoot.position.set(x, carState.flightY, 0);
  carRoot.rotation.y = -pathHeading * 0.4 - carState.yaw * 0.16;
  carRoot.rotation.z = -carState.yaw * 0.28 - pathHeading * 0.15;
  carRoot.rotation.x = carState.pitch * 0.14;
  const hover = Math.sin(performance.now() * 0.004) * 0.06;
  if (carMesh) carMesh.position.y = hover;
  carMesh?.traverse((o) => {
    if (o.userData.thruster) {
      const boost = carState.nitroOn ? 1.7 : 1.05;
      o.scale.y = boost + Math.sin(bladePulse * 18) * 0.08;
      o.material.opacity = carState.nitroOn ? 0.98 : 0.72;
    }
  });
  if (carState._head) {
    carState._head.intensity = carState.nitroOn
      ? (bladeHardwareFallback ? 58 : 48)
      : (bladeHardwareFallback ? 44 : 34);
  }

  // Three-beat camera: side glide → chase → low underpass push. Looks into curve.
  const beat = u < 0.34 ? 0 : u < 0.68 ? 1 : 2;
  const ahead = pathBend + Math.sin(pathHeading) * 10;
  let camPos, look;
  if (beat === 0) {
    // Side-rail establishing shot — feel the canyon width + bend
    const side = 5.8 + Math.sin(bootCamT * 0.2) * 0.8;
    camPos = new THREE.Vector3(x + side - Math.sin(pathHeading) * 1.5, carState.flightY + 2.1, 9.2);
    look = new THREE.Vector3(ahead * 0.55 + x * 0.25, carState.flightY + 0.4, -16);
  } else if (beat === 1) {
    // Classic chase over the deck, banked into turn
    camPos = new THREE.Vector3(
      x * 0.55 + carState.yaw * 1.4 - Math.sin(pathHeading) * 2.0,
      carState.flightY + 2.9 + Math.sin(bootCamT * 0.25) * 0.35,
      11.4 + Math.min(1.4, carState.speed * 0.012)
    );
    look = new THREE.Vector3(ahead * 0.45 + x * 0.4, carState.flightY + carState.pitch * 0.6, -14);
  } else {
    // Low push under a bridge / into neon — more dramatic
    camPos = new THREE.Vector3(
      x * 0.35 - 1.6 - Math.sin(pathHeading) * 1.2,
      carState.flightY + 1.15,
      8.6
    );
    look = new THREE.Vector3(ahead * 0.5 + x * 0.45, carState.flightY + 1.8, -20);
  }
  camera.position.lerp(camPos, 1 - Math.pow(0.0008, dt));
  camera.lookAt(look);
  // Soft exposure pulse on nitro beat for film energy
  renderer.toneMappingExposure = (bladeHardwareFallback ? 1.28 : 1.18) + (carState.nitroOn ? 0.08 : 0);
}

function updateSunsetBootLoop(dt) {
  if (!bootPreview || !carRoot) return;
  bootCamT += dt;
  const loop = BOOT_LOOP_SEC;
  const u = (bootCamT % loop) / loop;

  // Autopilot cruise on the highway — world scrolls, light weave
  carState.speed = 32 + Math.sin(bootCamT * 0.5) * 5;
  carState.nitroOn = (bootCamT % loop) > loop * 0.58 && (bootCamT % loop) < loop * 0.74;
  carState.nitro = carState.nitroOn ? 0.5 : 0.9;
  carState.x = Math.sin(bootCamT * 0.38) * 0.55 + Math.sin(bootCamT * 0.13) * 0.12;
  carState.yaw += ((Math.sin(bootCamT * 0.38) * 0.55) - carState.yaw) * Math.min(1, dt * 4);
  carState.flightY = 0;
  carState.pitch = 0;

  updateWorld(dt);

  const x = carState.x * (ROAD_HALF - 1.1);
  carRoot.position.set(x, 0, 0);
  carRoot.rotation.y = -carState.yaw * 0.18;
  carRoot.rotation.z = -carState.yaw * 0.08;
  carRoot.rotation.x = 0;
  if (carMesh) {
    carMesh.position.y = Math.sin(performance.now() * 0.01 + carState.speed) * 0.01;
  }
  if (carState._head) {
    carState._head.intensity = carState.nitroOn ? 52 : 36;
    carState._head.target.position.x = carState.yaw * 3;
    carState._head.target.position.z = -22;
    carState._head.target.updateMatrixWorld?.();
  }

  // camera: chase → side glide → low nose push
  const beat = u < 0.36 ? 0 : u < 0.7 ? 1 : 2;
  let camPos, lookY;
  if (beat === 0) {
    camPos = new THREE.Vector3(
      x * 0.55 + carState.yaw * 0.9,
      2.5 + Math.min(1.0, carState.speed * 0.012),
      7.0 + Math.min(2.0, carState.speed * 0.02)
    );
    lookY = 0.85;
  } else if (beat === 1) {
    camPos = new THREE.Vector3(x + 4.2, 1.9, 6.2);
    lookY = 0.7;
  } else {
    camPos = new THREE.Vector3(x * 0.4 - 0.8, 1.35, 5.6);
    lookY = 0.95;
  }
  camera.position.lerp(camPos, 1 - Math.pow(0.0012, dt));
  camera.lookAt(x * 0.7, lookY, -5);
  renderer.toneMappingExposure = 1.32 + (carState.nitroOn ? 0.1 : 0);
  if (skyMesh) skyMesh.rotation.y += dt * 0.01;
}

function updateBootLoop(dt) {
  if (!bootPreview) return;
  if (bootPreviewScene === "sunset") updateSunsetBootLoop(dt);
  else updateBladeBootLoop(dt);
}

function configureRunUi() {
  const blade = selectedScene === "blade";
  document.body.classList.toggle("is-blade", blade);
  titleChip.textContent = blade ? "SPINNER 44 · UNIT K" : "ORBIT RACE 3D";
  modeChip.textContent = blade ? "LOW CITY / CORRIDOR 09" : "FREE DRIVE";
  speedUnit.textContent = blade ? "KPH / AIR" : "KM/H";
  boostLabel.textContent = blade ? "LIFT RESERVE" : "NITRO";
  laneLabel.textContent = blade ? "ALT M" : "LANE";
  $("helpUp").textContent = blade ? "↑ ascend" : "↑ accel";
  $("helpDown").textContent = blade ? "↓ descend" : "↓ brake";
  introEyebrow.textContent = blade ? "LOS ANGELES · RESTRICTED AIR · 2049" : "SUNSET RACE INSPIRED · THREE.JS";
  introWordA.textContent = blade ? "LOW" : "ORBIT";
  introWordB.textContent = blade ? "CITY" : "RACE";
  introTag.textContent = blade ? "ACID RAIN · VIS 28M · CIVIL FLIGHT CLOSED" : "NEON CITY · TRUE 3D · FREE DRIVE";
  introHint.textContent = blade ? "WASD FLIGHT · SPACE THRUST · R RESET · ESC PAUSE" : "WASD / ARROWS · SPACE NITRO · R RESET · ESC PAUSE";
  footerLeft.textContent = blade ? "LIFT CELL 04 · DEGRADED" : "3D REMAKE · DRIVE FREELY";
  footerRight.textContent = blade ? "PUBLIC ACCESS / SECTOR CATALOG" : "REF: SUNSET RACE";
  const strip = $("instrumentStrip");
  if (strip) strip.setAttribute("aria-hidden", blade ? "false" : "true");
  if ($("instA")) $("instA").textContent = blade ? "CORR 09" : "ORBIT";
  if ($("instB")) $("instB").textContent = blade ? "VIS 28M" : "FREE DRIVE";
  if ($("instC")) $("instC").textContent = blade ? "LIFT CELL 04" : "NITRO READY";
  if ($("instD")) $("instD").textContent = blade ? "AUTH · K" : "CRUISER";
}

function resetRunState() {
  carState.x = 0;
  carState.speed = selectedScene === "blade" ? 58 : 28;
  carState.nitro = 1;
  carState.nitroOn = false;
  carState.distance = 0;
  carState.yaw = 0;
  carState.crash = 0;
  carState.hitCd = 0;
  carState.stunned = 0;
  carState.flightY = selectedScene === "blade" ? 9.5 : 0;
  carState.pitch = 0;
  carState.gateCount = 0;
  roadScroll = 0;
  pauseAccum = 0;
  pauseStartedAt = 0;
  clearKeys();
}

function launchSelectedRun() {
  if (!assetsCache) return;
  if (reduced && !motionEnabled) {
    motionEnabled = true;
  }
  const reuse =
    bootPreview &&
    worldRoot &&
    bootPreviewScene === selectedScene;
  if (!reuse) {
    stopBladeBootPreview();
    removeWorld();
    worldRoot = new THREE.Group();
    worldRoot.name = selectedScene === "blade" ? "blade-world" : "sunset-world";
    scene.add(worldRoot);
    resetRunState();
    configureRunUi();
    if (selectedScene === "blade") buildBladeWorld();
    else {
      applySunsetLook();
      buildEnvironment(assetsCache);
      buildWorld(assetsCache);
    }
  } else {
    // Seamless handoff from matching boot wallpaper into play
    stopBladeBootPreview();
    worldRoot.name = selectedScene === "blade" ? "blade-world" : "sunset-world";
    resetRunState();
    if (selectedScene === "blade") carState.speed = 58;
    else carState.speed = 28;
    configureRunUi();
  }
  selecting = false;
  launched = true;
  paused = false;
  document.body.classList.remove("is-selecting", "is-paused");
  selectScreen?.classList.add("gone");
  selectScreen?.setAttribute("aria-hidden", "true");
  pauseOverlay?.classList.remove("open");
  introGone = false;
  intro?.classList.remove("gone");
  intro?.classList.add("ready");
  helpEl?.classList.remove("dim");
  startedAt = performance.now();
  if (clock) clock.getDelta();
}

function openRunSelect() {
  selecting = true;
  launched = false;
  paused = false;
  clearKeys();
  document.body.classList.add("is-selecting");
  document.body.classList.remove("is-paused");
  selectScreen?.classList.remove("gone");
  selectScreen?.setAttribute("aria-hidden", "false");
  pauseOverlay?.classList.remove("open");
  intro?.classList.add("gone");
  intro?.classList.remove("ready");
  // Living wallpaper follows the currently selected run
  startBootPreview(selectedScene);
}

function syncRunCards() {
  // vehicle is always paired to scene (no separate UI)
  selectedVehicle = selectedScene === "blade" ? "spinner" : "cruiser";
  document.querySelectorAll("[data-scene]").forEach((card) => {
    const active = card.dataset.scene === selectedScene;
    card.classList.toggle("is-active", active);
    card.setAttribute("aria-checked", active ? "true" : "false");
  });
  if (startBtn) {
    startBtn.textContent = reduced && !motionEnabled
      ? "ENABLE MOTION & START"
      : selectedScene === "blade" ? "▶ FLY LOW CITY" : "▶ DRIVE SUNSET";
  }
  const sub = $("selectSub");
  const hint = $("selectHint");
  if (sub) {
    sub.textContent = selectedScene === "blade"
      ? "spinner · rain corridor · free flight"
      : "cruiser · neon highway · free drive";
  }
  if (hint) {
    hint.textContent = selectedScene === "blade"
      ? "WASD fly · SPACE thrust · ESC pause"
      : "WASD drive · SPACE boost · ESC pause";
  }
  // v30: living select wallpaper follows the chosen run
  if (selecting && assetsCache) {
    startBootPreview(selectedScene);
  }
}

function bindRunSelect() {
  document.querySelectorAll("[data-scene]").forEach((card) => {
    card.addEventListener("click", () => {
      selectedScene = card.dataset.scene;
      syncRunCards();
    });
  });
  startBtn?.addEventListener("click", launchSelectedRun);
  reselectBtn?.addEventListener("click", openRunSelect);
  syncRunCards();
}

function recycleZ(entity, minZ, resetTo) {
  if (entity.position.z > minZ) {
    entity.position.z = resetTo - Math.random() * 10;
  }
}

function updateWorld(dt) {
  const move = carState.speed * dt;
  carState.distance += move;
  roadScroll += move;

  // scroll road texture
  if (roadMesh && roadMesh.material && roadMesh.material.map) {
    roadMesh.material.map.offset.y = (roadScroll * 0.035) % 1;
  }

  // dashes
  for (const d of stripeMeshes) {
    d.position.z += move;
    if (d.position.z > 8) d.position.z -= 240;
  }

  // side props move toward camera (positive z)
  for (const b of buildingPool) {
    b.position.z += move;
    if (b.position.z > 20) {
      b.position.z -= 12 * buildingPool.length * 0.5 + Math.random() * 8;
      b.position.x = b.userData.side * (10 + Math.random() * 8);
      b.rotation.y = (Math.random() - 0.5) * 0.3;
    }
  }
  for (const p of palmPool) {
    p.position.z += move;
    if (p.position.z > 15) {
      p.position.z -= 14 * palmPool.length * 0.55;
      p.position.x = p.userData.side * (7 + Math.random() * 1.5);
    }
  }
  for (const l of lightPool) {
    l.position.z += move;
    if (l.position.z > 12) l.position.z -= 16 * lightPool.length * 0.55;
  }

  // traffic relative + solid collision (tight boxes — previous half-lengths were inflated)
  // World: player at z=0, forward = -Z. Lane spacing ≈ LANE_W*0.75 = 2.4
  const myX = carRoot.position.x;
  // visual car ~2.1–2.4 long / ~1.5–1.8 wide → slim box so near-miss is free
  const myHalfW = carState.carWidth * 0.34; // ~0.55–0.7
  const myHalfL = carState.carLen * 0.34;   // ~0.75–0.95
  const otherHalfW = 0.62;
  const otherHalfL = 0.9;
  const contactGap = 0.12;
  const minSep = myHalfL + otherHalfL - contactGap; // ~1.5–1.7 (was ~3.2!)
  for (const t of trafficPool) {
    const targetX = t.userData.lane * LANE_W * 0.75;
    t.position.x += (targetX - t.position.x) * Math.min(1, dt * 2);

    // relative motion: faster player makes traffic approach from front (z → 0 from negative)
    const relSpeed = carState.speed - t.userData.speed;
    const prevZ = t.position.z;
    t.position.z += relSpeed * dt;

    // recycle when past camera / far behind
    if (t.position.z > 12) {
      t.position.z = -70 - Math.random() * 50;
      t.userData.lane = [-1, 0, 1][Math.floor(Math.random() * 3)];
      t.userData.hitLock = 0;
      continue;
    }

    // only care about cars near the player longitudinally
    const tz = t.position.z;
    if (tz < -10 || tz > 5) continue;

    const dx = Math.abs(t.position.x - myX);
    // adjacent lane center is 2.4 away; keep halfW sum < ~1.5 so side-by-side is free
    const overlapX = dx < myHalfW + otherHalfW;
    if (!overlapX) continue;

    // swept front collision: if traffic was ahead and this step would cross our bumper, hard hit
    // (prevents high-speed tunneling through the thin contact zone)
    const bumperZ = -minSep;
    const crossedFront =
      prevZ < bumperZ && tz >= bumperZ - 0.05; // approached from front past bumper
    const overlapFront = tz <= 0.2 && tz >= -minSep;
    const overlapRear = tz > 0.2 && tz < myHalfL * 0.65;
    if (!(crossedFront || overlapFront || overlapRear)) continue;

    // solid resolve: pin traffic just outside our front bumper when hit from front
    if (crossedFront || (overlapFront && tz <= 0.05)) {
      t.position.z = bumperZ;
    } else if (overlapRear) {
      t.position.z = Math.max(t.position.z, minSep * 0.55);
    } else {
      t.position.z = bumperZ;
    }

    const hardFront = crossedFront || overlapFront;
    carState.speed = Math.min(carState.speed, hardFront ? 8 : 12);
    if (carState.hitCd <= 0 && hardFront) {
      carState.stunned = Math.max(carState.stunned, 0.55);
      carState.crash = 1;
      carState.nitro = Math.max(0.12, carState.nitro - 0.18);
      carState.hitCd = 0.65;
      if (dx > 0.18) {
        const push = Math.sign(myX - t.position.x);
        carState.x = THREE.MathUtils.clamp(carState.x + push * 0.08, -0.95, 0.95);
      }
    }
  }

  // city parallax
  if (cityMesh && cityMesh.material.map) {
    cityMesh.material.map.offset.x = (roadScroll * 0.0015) % 1;
  }
  if (sunMesh) {
    sunMesh.position.x = carRoot.position.x * 0.15;
  }
}

function updateCar(dt) {
  const steer = (keys.left ? -1 : 0) + (keys.right ? 1 : 0);
  let accel = keys.up ? 1 : 0;
  const brake = keys.down ? 1 : 0;
  if (carState.hitCd > 0) carState.hitCd -= dt;
  if (carState.stunned > 0) {
    carState.stunned -= dt;
    accel = 0; // cannot punch through after crash
  }
  carState.nitroOn = keys.nitro && carState.nitro > 0.05 && carState.stunned <= 0;
  carState.crash = Math.max(0, carState.crash - dt * 1.8);

  // speed in m/s (100 km/h ~= 28 m/s)
  let target = 28;
  if (accel) target = 52; // ~187 km/h
  if (brake || carState.stunned > 0) target = 5;
  if (carState.nitroOn) {
    target += 28;
    carState.nitro = Math.max(0, carState.nitro - dt * 0.28);
  } else if (carState.nitro < 1) {
    carState.nitro = Math.min(1, carState.nitro + dt * 0.12);
  }
  carState.speed += (target - carState.speed) * Math.min(1, dt * 2.2);
  carState.speed = Math.max(3, Math.min(85, carState.speed));

  // lateral
  const steerPower = 6.5 + carState.speed * 0.05;
  carState.x += steer * steerPower * dt * 0.22;
  carState.x = THREE.MathUtils.clamp(carState.x, -0.95, 0.95);
  carState.yaw += (steer - carState.yaw) * Math.min(1, dt * 7);

  // place car
  const x = carState.x * (ROAD_HALF - 1.1);
  carRoot.position.x = x;
  carRoot.position.y = 0;
  carRoot.position.z = 0;
  carRoot.rotation.y = -carState.yaw * 0.18;
  carRoot.rotation.z = -carState.yaw * 0.08;
  if (carMesh) {
    // keep body grounded; tiny bob only, no light separation
    const bob = Math.sin(performance.now() * 0.01 + carState.speed) * 0.01;
    carMesh.position.y = bob;
  }

  // headlight intensity only (position parented to car)
  if (carState._head) {
    carState._head.intensity = carState.nitroOn ? 55 : 38;
    // aim slightly with steering
    carState._head.target.position.x = carState.yaw * 3;
    carState._head.target.position.z = -22;
    carState._head.target.updateMatrixWorld();
  }

  // camera chase
  const camTarget = new THREE.Vector3(x * 0.75, 0.9, -4);
  const camPos = new THREE.Vector3(
    x * 0.55 + carState.yaw * 0.8,
    2.6 + Math.min(1.2, carState.speed * 0.01),
    7.2 + Math.min(2.5, carState.speed * 0.02)
  );
  camera.position.lerp(camPos, 1 - Math.pow(0.001, dt));
  camera.lookAt(camTarget.x, camTarget.y, camTarget.z);

  // sky slow rotate
  if (skyMesh) skyMesh.rotation.y += dt * 0.01;
}

function clearKeys() {
  keys.left = keys.right = keys.up = keys.down = keys.nitro = false;
}

function setPaused(next) {
  if (selecting || !launched) return;
  if (next === paused) return;
  paused = next;
  document.body.classList.toggle("is-paused", paused);
  pauseOverlay?.classList.toggle("open", paused);
  pauseOverlay?.setAttribute("aria-hidden", paused ? "false" : "true");
  pauseBtn?.setAttribute("aria-pressed", paused ? "true" : "false");
  pauseBtn && (pauseBtn.textContent = paused ? "▶ RESUME" : "❚❚ PAUSE");
  if (paused) {
    pauseReturnFocus = document.activeElement;
    pauseStartedAt = performance.now();
    clearKeys();
    if (clock) clock.getDelta(); // drop frame delta on unpause edge later
    resumeBtn?.focus();
  } else {
    if (pauseStartedAt) pauseAccum += performance.now() - pauseStartedAt;
    pauseStartedAt = 0;
    if (clock) clock.getDelta(); // discard stalled delta
    const target = pauseReturnFocus instanceof HTMLElement ? pauseReturnFocus : pauseBtn;
    target?.focus();
    pauseReturnFocus = null;
  }
}

function togglePause() {
  setPaused(!paused);
}

function trapPauseFocus(event) {
  if (!paused || event.key !== "Tab" || !pauseOverlay) return;
  const controls = [...pauseOverlay.querySelectorAll("button:not([disabled]), a[href]")];
  if (!controls.length) return;
  const first = controls[0];
  const last = controls[controls.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function exitGame() {
  // prefer parent/Brain home; fall back to history if embedded
  try {
    if (window.top && window.top !== window) {
      window.top.location.href = EXIT_URL;
      return;
    }
  } catch (_) { /* cross-origin frame */ }
  window.location.href = EXIT_URL;
}

function updateHud() {
  const kmh = Math.round(carState.speed * 3.6);
  speedEl.textContent = String(kmh).padStart(3, "0");
  distEl.textContent = (carState.distance / 1000).toFixed(2);
  const el = Math.max(0, (performance.now() - startedAt - pauseAccum - (paused && pauseStartedAt ? performance.now() - pauseStartedAt : 0)) / 1000);
  const mm = String(Math.floor(el / 60)).padStart(2, "0");
  const ss = String(Math.floor(el % 60)).padStart(2, "0");
  etimeEl.textContent = `${mm}:${ss}`;
  laneEl.textContent = selectedScene === "blade"
    ? `${carState.flightY.toFixed(1)}K`
    : carState.x < -0.35 ? "L" : carState.x > 0.35 ? "R" : "C";
  nitroFill.style.width = `${Math.round(carState.nitro * 100)}%`;
  clockEl.textContent = new Date().toTimeString().slice(0, 8);
  if (selectedScene === "blade") {
    if ($("instA")) $("instA").textContent = `CORR 09 · G${carState.gateCount}`;
    if ($("instB")) $("instB").textContent = carState.nitroOn ? "THRUST HOT" : "VIS 28M";
    if ($("instC")) $("instC").textContent = `ALT ${carState.flightY.toFixed(1)}`;
    if ($("instD")) $("instD").textContent = carState.crash > 0.05 ? "SIGNAL DEGRADED" : "AUTH · K";
  }
}

function onResize() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  const bladeScale = selectedScene === "blade" && bladeHardwareFallback ? (isMobile ? 0.75 : 0.6) : Math.min(window.devicePixelRatio || 1, isMobile ? 1.25 : 1.5);
  renderer.setPixelRatio(bladeScale);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
  composer.setSize(w, h);
}

function bindInput() {
  window.addEventListener("keydown", (e) => {
    // Esc / P always toggle pause (even while paused)
    if (e.code === "Escape" || e.code === "KeyP") {
      e.preventDefault();
      if (e.repeat) return;
      if (selecting) return;
      togglePause();
      return;
    }
    if (paused || selecting || !launched) return;
    if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].includes(e.code)) e.preventDefault();
    setKey(e.code, true);
  });
  window.addEventListener("keyup", (e) => {
    if (paused || selecting || !launched) return;
    setKey(e.code, false);
  });

  pauseBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    togglePause();
  });
  resumeBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    setPaused(false);
  });
  pauseOverlay?.addEventListener("keydown", trapPauseFocus);
  exitBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    exitGame();
  });
  menuBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    if (launched && !selecting) setPaused(true);
  });

  const touch = $("touch");
  if (touch) {
    touch.querySelectorAll("button").forEach((btn) => {
      const k = btn.dataset.k;
      const on = (v) => (e) => {
        e.preventDefault();
        if (paused) return;
        if (k in keys) keys[k] = v;
      };
      btn.addEventListener("pointerdown", on(true));
      btn.addEventListener("pointerup", on(false));
      btn.addEventListener("pointerleave", on(false));
      btn.addEventListener("pointercancel", on(false));
    });
  }
}

function setKey(code, down) {
  switch (code) {
    case "ArrowLeft":
    case "KeyA":
      keys.left = down;
      break;
    case "ArrowRight":
    case "KeyD":
      keys.right = down;
      break;
    case "ArrowUp":
    case "KeyW":
      keys.up = down;
      break;
    case "ArrowDown":
    case "KeyS":
      keys.down = down;
      break;
    case "Space":
      keys.nitro = down;
      break;
    case "KeyR":
      if (down && !paused) {
        resetRunState();
        startedAt = performance.now();
        if (selectedScene === "blade") {
          for (const [i, t] of bladeTrafficPool.entries()) t.position.z = -35 - i * 18 - Math.random() * 30;
          for (const [i, g] of bladeGatePool.entries()) {
            g.position.z = -62 - i * 64;
            g.userData.checked = false;
          }
        } else {
          for (const t of trafficPool) t.position.z = -30 - Math.random() * 60;
        }
      }
      break;
  }
}

function frame() {
  requestAnimationFrame(frame);
  const dt = Math.min(0.05, clock.getDelta());
  if (motionEnabled && selecting && bootPreview) {
    updateBootLoop(dt);
  } else if (motionEnabled && launched && !selecting && !paused) {
    if (selectedScene === "blade") {
      updateSpinner(dt);
      updateBladeWorld(dt);
    } else {
      updateCar(dt);
      updateWorld(dt);
    }

    if (!introGone && performance.now() - startedAt - pauseAccum > 2400) {
      introGone = true;
      intro?.classList.add("gone");
      setTimeout(() => helpEl?.classList.add("dim"), 2200);
    }

    // Blade grade — slightly higher so facades stay readable after ACES.
    const baseExposure = selectedScene === "blade" ? (bladeHardwareFallback ? 1.18 : 1.08) : 1.32;
    renderer.toneMappingExposure = baseExposure + carState.crash * 0.12;
    if (carState.nitroOn) renderer.toneMappingExposure = selectedScene === "blade" ? 1.16 : 1.42;
  } else if (launched && paused) {
    renderer.toneMappingExposure = 0.92;
  }
  updateHud();
  // Both modes use the composer. Blade's lower internal resolution on weak
  // GPUs keeps its stronger bloom affordable and preserves the intended glow.
  composer.render();
  if (selectedScene === "blade" || bootPreviewScene === "blade") {
    let objects = 0, meshes = 0, lights = 0;
    scene.traverse((o) => {
      objects++;
      if (o.isMesh) meshes++;
      if (o.isLight) lights++;
    });
    window.__bladeStats = {
      render: { ...renderer.info.render },
      memory: { ...renderer.info.memory },
      objects, meshes, lights,
      canvas: [renderer.domElement.width, renderer.domElement.height]
    };
  }
}

async function main() {
  makeRenderer();
  makeScene();
  makeComposer();
  bindInput();
  bindRunSelect();
  window.addEventListener("resize", onResize);

  setBoot(0.02, "init");
  assetsCache = await loadAssets();

  setBoot(1, "ready");
  bootLoader?.classList.add("done");
  document.body.classList.add("is-selecting");
  selectScreen?.setAttribute("aria-hidden", "false");
  clock = new THREE.Clock();
  // Living wallpaper matches default / last selected run
  if (!reduced) startBootPreview(selectedScene);
  requestAnimationFrame(frame);
}

main().catch((err) => {
  console.error(err);
  setBoot(1, "error");
  if (bootText) {
    bootText.setAttribute("role", "alert");
    bootText.textContent = "Opening unavailable. Continue to Brain Home.";
  }
  if (openingError) openingError.hidden = false;
});
