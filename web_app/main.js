// ==========================================
// SCENE SETUP
// ==========================================
const container = document.getElementById('canvas-container');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x87CEEB); // Sky blue
scene.fog = new THREE.FogExp2(0x87CEEB, 0.002);

const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 100, 150);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
container.appendChild(renderer.domElement);

const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.05;
controls.maxPolarAngle = Math.PI / 2 - 0.05;

// Lighting
const ambientLight = new THREE.AmbientLight(0x404040, 1.5);
scene.add(ambientLight);

const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
dirLight.position.set(100, 200, 50);
dirLight.castShadow = true;
dirLight.shadow.mapSize.width = 2048;
dirLight.shadow.mapSize.height = 2048;
dirLight.shadow.camera.near = 0.5;
dirLight.shadow.camera.far = 500;
dirLight.shadow.camera.left = -200;
dirLight.shadow.camera.right = 200;
dirLight.shadow.camera.top = 200;
dirLight.shadow.camera.bottom = -200;
scene.add(dirLight);

// Globals
const simplex = new SimplexNoise();
let terrainMesh, environmentGroup, waterMesh;
let gltfLoader = null;
if (window.THREE && THREE.GLTFLoader) {
    gltfLoader = new THREE.GLTFLoader();
}
const size = 300; 

// Dynamic AI States
let currentHasWater = false;
let currentCustomModels = [];

// Materials (Now dynamic based on AI Biome)
const terrainMat = new THREE.MeshStandardMaterial({ color: 0x3d5e3a, roughness: 0.8, flatShading: true });
const rockMat = new THREE.MeshStandardMaterial({ color: 0x888888, roughness: 0.9, flatShading: true });
const trunkMat = new THREE.MeshStandardMaterial({ color: 0x4a3b22, roughness: 1.0 });
const leafMat = new THREE.MeshStandardMaterial({ color: 0x2d4c1e, roughness: 0.8, flatShading: true });
const waterMat = new THREE.MeshStandardMaterial({
    color: 0x0066ff,
    transparent: true,
    opacity: 0.6,
    roughness: 0.1,
    metalness: 0.8
});

function applyBiomeColors(colors) {
    if (colors.terrain) terrainMat.color.setHex(parseInt(colors.terrain, 16));
    if (colors.rock) rockMat.color.setHex(parseInt(colors.rock, 16));
    if (colors.trunk) trunkMat.color.setHex(parseInt(colors.trunk, 16));
    if (colors.leaf) leafMat.color.setHex(parseInt(colors.leaf, 16));
    if (colors.water) waterMat.color.setHex(parseInt(colors.water, 16));
    if (colors.sky) {
        scene.background.setHex(parseInt(colors.sky, 16));
        scene.fog.color.setHex(parseInt(colors.sky, 16));
    }
}

// UI Elements
const els = {
    res: document.getElementById('res-slider'),
    height: document.getElementById('height-slider'),
    scale: document.getElementById('scale-slider'),
    octaves: document.getElementById('octaves-slider'),
    path: document.getElementById('path-toggle'),
    trees: document.getElementById('trees-slider'),
    rocks: document.getElementById('rocks-slider'),
    resVal: document.getElementById('res-val'),
    heightVal: document.getElementById('height-val'),
    scaleVal: document.getElementById('scale-val'),
    octavesVal: document.getElementById('octaves-val'),
    treesVal: document.getElementById('trees-val'),
    rocksVal: document.getElementById('rocks-val'),
    loading: document.getElementById('loading-overlay'),
    apiKey: document.getElementById('api-key'),
    meshyKey: document.getElementById('meshy-key'),
    prompt: document.getElementById('ai-prompt'),
    aiBtn: document.getElementById('ai-generate-btn')
};

// Bind sliders
['res', 'height', 'scale', 'octaves', 'trees', 'rocks'].forEach(id => {
    els[id].addEventListener('input', (e) => { els[id+'Val'].innerText = e.target.value; });
    els[id].addEventListener('change', () => generateAll(false)); // False means manual slider adjust
});
els.path.addEventListener('change', () => generateAll(false));


// ==========================================
// PROCEDURAL GENERATION
// ==========================================

function fbm(x, y, octaves, scale) {
    let total = 0;
    let frequency = scale / 100;
    let amplitude = 1;
    let maxValue = 0;
    for(let i=0; i<octaves; i++) {
        total += simplex.noise2D(x * frequency, y * frequency) * amplitude;
        maxValue += amplitude;
        amplitude *= 0.5;
        frequency *= 2.0;
    }
    return total / maxValue;
}

function getPathDistance(x, y) {
    const curveX = Math.sin(y * 0.02) * 40 + Math.cos(y * 0.01) * 20;
    return Math.abs(x - curveX);
}

function generateTerrain() {
    if(terrainMesh) scene.remove(terrainMesh);
    if(waterMesh) scene.remove(waterMesh);

    const res = parseInt(els.res.value);
    const heightMult = parseFloat(els.height.value);
    const scale = parseFloat(els.scale.value);
    const octaves = parseInt(els.octaves.value);
    const hasPath = els.path.checked;

    const geo = new THREE.PlaneGeometry(size, size, res, res);
    geo.rotateX(-Math.PI / 2);

    const pos = geo.attributes.position;
    
    for(let i=0; i<pos.count; i++) {
        const x = pos.getX(i);
        const z = pos.getZ(i);
        
        let h = fbm(x, z, octaves, scale);
        
        if (hasPath) {
            const dist = getPathDistance(x, z);
            if (dist < 15) {
                const influence = 1 - (dist / 15);
                h = h * (1 - influence) - (influence * 0.1); 
            }
        }
        
        pos.setY(i, h * heightMult);
    }

    geo.computeVertexNormals();
    terrainMesh = new THREE.Mesh(geo, terrainMat);
    terrainMesh.receiveShadow = true;
    terrainMesh.castShadow = true;
    scene.add(terrainMesh);

    // Add Water Layer
    if (currentHasWater) {
        const wGeo = new THREE.PlaneGeometry(size, size);
        wGeo.rotateX(-Math.PI / 2);
        waterMesh = new THREE.Mesh(wGeo, waterMat);
        waterMesh.position.y = -2; // Water level
        scene.add(waterMesh);
    }

    return geo;
}

function createTree() {
    const group = new THREE.Group();
    const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.8, 3, 5), trunkMat);
    trunk.position.y = 1.5;
    trunk.castShadow = true;
    group.add(trunk);
    const leaves = new THREE.Mesh(new THREE.ConeGeometry(3, 7, 5), leafMat);
    leaves.position.y = 5.5;
    leaves.castShadow = true;
    group.add(leaves);
    return group;
}

function createRock() {
    const r = Math.random() * 2 + 0.5;
    const geo = new THREE.DodecahedronGeometry(r, 0);
    const pos = geo.attributes.position;
    for(let i=0; i<pos.count; i++) {
        pos.setXYZ(i, 
            pos.getX(i) + (Math.random()-0.5)*0.5,
            pos.getY(i) + (Math.random()-0.5)*0.5,
            pos.getZ(i) + (Math.random()-0.5)*0.5
        );
    }
    geo.computeVertexNormals();
    const rock = new THREE.Mesh(geo, rockMat);
    rock.castShadow = true;
    rock.receiveShadow = true;
    rock.position.y = r * 0.5;
    return rock;
}


// ==========================================
// 100% FREE AI PROCEDURAL MESH GENERATION (GEMINI CODE-GEN)
// ==========================================
async function generateEnvironment(terrainGeo, fetchCustomModels = false) {
    if(environmentGroup) scene.remove(environmentGroup);
    environmentGroup = new THREE.Group();

    const treeCount = parseInt(els.trees.value);
    const rockCount = parseInt(els.rocks.value);
    const hasPath = els.path.checked;

    const pos = terrainGeo.attributes.position;
    const vertexCount = pos.count;

    const placeObject = (createFunc, count) => {
        let placed = 0;
        let attempts = 0;
        while(placed < count && attempts < count * 3) {
            attempts++;
            const idx = Math.floor(Math.random() * vertexCount);
            const x = pos.getX(idx);
            const y = pos.getY(idx);
            const z = pos.getZ(idx);

            if(hasPath && getPathDistance(x, z) < 18) continue;
            if(y < (currentHasWater ? -1 : -10)) continue;
            
            const obj = createFunc();
            obj.position.set(x, y, z);
            obj.rotation.y = Math.random() * Math.PI * 2;
            const scale = Math.random() * 0.5 + 0.8;
            obj.scale.set(scale, scale, scale);
            
            environmentGroup.add(obj);
            placed++;
        }
    };

    placeObject(createTree, treeCount);
    placeObject(createRock, rockCount);

    // Build Custom Models programmed on-the-fly by Gemini
    if (fetchCustomModels && currentCustomModels.length > 0) {
        for (let modelData of currentCustomModels) {
            try {
                document.getElementById('loading-text').innerText = `Building AI Procedural Mesh: ${modelData.name}...`;
                
                // Gemini generated a JS function string. We convert it to a real function.
                const generateMeshFunc = new Function('THREE', 'return (' + modelData.code + ')(THREE);');
                const model = generateMeshFunc(THREE);
                
                if (model) {
                    // Place it somewhere visible
                    model.position.set(Math.random()*40 - 20, 10, Math.random()*40 - 20);
                    model.scale.set(3, 3, 3); // Scale up so it's visible
                    
                    // Add basic shadow casting to the generated primitives
                    model.traverse((child) => {
                        if (child.isMesh) {
                            child.castShadow = true;
                            child.receiveShadow = true;
                        }
                    });
                    
                    environmentGroup.add(model);
                }
            } catch (err) {
                console.warn("Could not compile/build custom AI model:", err);
            }
        }
    }

    scene.add(environmentGroup);
    els.loading.classList.add('hidden');
}

function generateAll(fetchCustomModels = false) {
    els.loading.classList.remove('hidden');
    setTimeout(() => {
        const geo = generateTerrain();
        generateEnvironment(geo, fetchCustomModels);
    }, 50);
}


// ==========================================
// GEMINI AI INTEGRATION
// ==========================================
els.aiBtn.addEventListener('click', async () => {
    const key = els.apiKey.value.trim();
    const prompt = els.prompt.value.trim();

    if(!key) { alert("Please enter your Gemini API Key."); return; }
    if(!prompt) { alert("Please enter a prompt."); return; }

    els.loading.classList.remove('hidden');
    document.getElementById('loading-text').innerText = "AI is designing environment...";

    const systemInstruction = `
    You are an expert technical artist and Three.js developer. Given a user's prompt, return ONLY RAW JSON matching this structure exactly (NO MARKDOWN, NO BACKTICKS):
    {
      "resolution": 150,
      "heightMultiplier": 40,
      "noiseScale": 3.0,
      "octaves": 5,
      "hasPath": false,
      "treeDensity": 100,
      "rockDensity": 80,
      "hasWater": true,
      "colors": {
        "terrain": "0xeab676",
        "rock": "0xaa8866",
        "trunk": "0x8b4513",
        "leaf": "0x6b8e23",
        "water": "0x00aaff",
        "sky": "0xffd700"
      },
      "customModels": [
        {
          "name": "brown bear",
          "code": "function(THREE) { const g = new THREE.Group(); const body = new THREE.Mesh(new THREE.BoxGeometry(2,1,1), new THREE.MeshStandardMaterial({color:0x8b4513})); g.add(body); return g; }"
        }
      ]
    }
    IMPORTANT: Adapt the "colors" object strictly to match the requested biome (e.g., desert = yellow sand 0xeab676, winter = white snow 0xffffff, grass = green 0x3d5e3a). Use hex strings like "0xffffff".
    For "customModels": If the user asks for specific distinct entities (animals, caves, waterfalls, etc), you MUST write a valid Javascript function string that takes THREE as a parameter and returns a THREE.Group or THREE.Mesh representing a Low-Poly version of that object using basic Three.js primitives (BoxGeometry, CylinderGeometry, etc.) and StandardMaterials. Limit to 3 items max.
    `;

    try {
        const modelsRes = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${key}`);
        const modelsData = await modelsRes.json();
        if(modelsData.error) throw new Error(modelsData.error.message);
        
        const validModel = modelsData.models.find(m => 
            m.name.includes("gemini") && 
            m.supportedGenerationMethods && m.supportedGenerationMethods.includes("generateContent")
        );
        if (!validModel) throw new Error("No compatible Gemini model found.");

        const combinedPrompt = systemInstruction + "\n\nUSER PROMPT: " + prompt;
        const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/${validModel.name}:generateContent?key=${key}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contents: [{ parts: [{ text: combinedPrompt }] }] })
        });

        const data = await res.json();
        if(data.error) throw new Error(data.error.message);

        let text = data.candidates[0].content.parts[0].text;
        text = text.replace(/```json/g, '').replace(/```/g, '').trim();
        const params = JSON.parse(text);

        // Update UI
        els.res.value = params.resolution;
        els.height.value = params.heightMultiplier;
        els.scale.value = params.noiseScale;
        els.octaves.value = params.octaves;
        els.path.checked = params.hasPath;
        els.trees.value = params.treeDensity;
        els.rocks.value = params.rockDensity;
        
        currentHasWater = params.hasWater === true;
        currentCustomModels = params.customModels || [];

        if (params.colors) {
            applyBiomeColors(params.colors);
        }

        ['res', 'height', 'scale', 'octaves', 'trees', 'rocks'].forEach(id => {
            els[id].dispatchEvent(new Event('input'));
        });

        generateAll(true); // Trigger generation including external API fetching
        
    } catch (e) {
        alert("AI Request Failed: " + e.message);
        els.loading.classList.add('hidden');
    }
});


// ==========================================
// RENDER LOOP & INIT
// ==========================================
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

// Water animation
function animate() {
    requestAnimationFrame(animate);
    controls.update();
    
    if (waterMesh) {
        // Simple tide animation
        waterMesh.position.y = -2 + Math.sin(Date.now() * 0.001) * 0.5;
    }
    
    renderer.render(scene, camera);
}

document.getElementById('loading-text').innerText = "Generating Terrain...";
generateAll(false);
animate();
