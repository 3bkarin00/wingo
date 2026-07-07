(function () {
  "use strict";
  var DATA = window.VIEWER_DATA;
  var STRUCTURE = 0x4fb2e8;
  var KINEMATIC = 0xf5a742;

  var canvas = document.getElementById("gl");
  var renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  var scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0d12);
  scene.fog = new THREE.Fog(0x0a0d12, 4000, 12000);

  var camera = new THREE.PerspectiveCamera(38, 1, 1, 50000);

  scene.add(new THREE.HemisphereLight(0xaecbff, 0x0a0d12, 1.1));
  var key = new THREE.DirectionalLight(0xffffff, 1.0);
  key.position.set(1, 1.6, 1);
  scene.add(key);
  var fill = new THREE.DirectionalLight(0x4fb2e8, 0.35);
  fill.position.set(-1, -0.4, -0.6);
  scene.add(fill);

  var root = new THREE.Group();
  scene.add(root);

  // ---- geometry builders --------------------------------------------------

  function indexedMesh(tess, color, opacity) {
    var geom = new THREE.BufferGeometry();
    var verts = new Float32Array(tess.vertices.length * 3);
    for (var i = 0; i < tess.vertices.length; i++) {
      verts[i * 3] = tess.vertices[i][0];
      verts[i * 3 + 1] = tess.vertices[i][1];
      verts[i * 3 + 2] = tess.vertices[i][2];
    }
    geom.setAttribute("position", new THREE.BufferAttribute(verts, 3));
    var idx = new Uint32Array(tess.triangles.length * 3);
    for (var j = 0; j < tess.triangles.length; j++) {
      idx[j * 3] = tess.triangles[j][0];
      idx[j * 3 + 1] = tess.triangles[j][1];
      idx[j * 3 + 2] = tess.triangles[j][2];
    }
    geom.setIndex(new THREE.BufferAttribute(idx, 1));
    geom.computeVertexNormals();

    var group = new THREE.Group();
    var mat = new THREE.MeshStandardMaterial({
      color: color, transparent: true, opacity: opacity,
      side: THREE.DoubleSide, roughness: 0.55, metalness: 0.05,
      depthWrite: opacity > 0.6,
    });
    group.add(new THREE.Mesh(geom, mat));

    var edges = new THREE.EdgesGeometry(geom, 28);
    var lineMat = new THREE.LineBasicMaterial({ color: color, transparent: true, opacity: 0.55 });
    group.add(new THREE.LineSegments(edges, lineMat));
    return group;
  }

  function ribPlane(rib, color) {
    var c = rib.corners;
    var verts = new Float32Array([].concat(c[0], c[1], c[2], c[0], c[2], c[3]));
    var geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.BufferAttribute(verts, 3));
    geom.computeVertexNormals();
    var group = new THREE.Group();
    group.add(new THREE.Mesh(geom, new THREE.MeshBasicMaterial({
      color: color, transparent: true, opacity: 0.06, side: THREE.DoubleSide, depthWrite: false,
    })));
    var loopPts = [c[0], c[1], c[2], c[3], c[0]].map(function (p) { return new THREE.Vector3(p[0], p[1], p[2]); });
    var loopGeom = new THREE.BufferGeometry().setFromPoints(loopPts);
    group.add(new THREE.Line(loopGeom, new THREE.LineBasicMaterial({ color: color, transparent: true, opacity: 0.4 })));
    return group;
  }

  function axisRod(p1, p2, color, radius) {
    var a = new THREE.Vector3(p1[0], p1[1], p1[2]);
    var b = new THREE.Vector3(p2[0], p2[1], p2[2]);
    var dir = new THREE.Vector3().subVectors(b, a);
    var len = dir.length();
    var geom = new THREE.CylinderGeometry(radius, radius, len, 10);
    geom.translate(0, len / 2, 0);
    geom.rotateX(Math.PI / 2);
    var mesh = new THREE.Mesh(geom, new THREE.MeshStandardMaterial({ color: color, emissive: color, emissiveIntensity: 0.25 }));
    mesh.position.copy(a);
    mesh.lookAt(b);
    return mesh;
  }

  function hardpointMarker(p, color, radius) {
    var geom = new THREE.SphereGeometry(radius, 16, 12);
    var mesh = new THREE.Mesh(geom, new THREE.MeshStandardMaterial({ color: color, emissive: color, emissiveIntensity: 0.3 }));
    mesh.position.set(p[0], p[1], p[2]);
    return mesh;
  }

  // ---- assemble scene from VIEWER_DATA ------------------------------------

  var layers = {};

  if (DATA.te_cut) {
    // P4: show the two cut bodies. Fixed wing translucent so the cove/gap is
    // visible; control surface opaque amber as the highlighted moving part.
    layers.wing = indexedMesh(DATA.te_cut.wing, STRUCTURE, 0.28);
    root.add(layers.wing);
    layers.cs = indexedMesh(DATA.te_cut.control_surface, KINEMATIC, 0.9);
    root.add(layers.cs);
  } else {
    layers.oml = indexedMesh(DATA.oml, STRUCTURE, 0.32);
    root.add(layers.oml);
  }

  Object.keys(DATA.spars).forEach(function (name) {
    var g = indexedMesh(DATA.spars[name], STRUCTURE, 0.85);
    root.add(g);
    layers["spar_" + name] = g;
  });

  var ribGroup = new THREE.Group();
  DATA.rib_planes.forEach(function (rib) { ribGroup.add(ribPlane(rib, STRUCTURE)); });
  root.add(ribGroup);
  layers.ribs = ribGroup;

  var hingeRadius = Math.max(2, DATA.half_span_mm * 0.0025);
  var hingeGroup = new THREE.Group();
  Object.keys(DATA.hinge_axes).forEach(function (name) {
    var pts = DATA.hinge_axes[name];
    hingeGroup.add(axisRod(pts[0], pts[1], KINEMATIC, hingeRadius));
  });
  root.add(hingeGroup);
  layers.hinges = hingeGroup;

  var hpGroup = new THREE.Group();
  var hpRadius = Math.max(3, DATA.half_span_mm * 0.006);
  DATA.hardpoints.forEach(function (p) { hpGroup.add(hardpointMarker(p, KINEMATIC, hpRadius)); });
  root.add(hpGroup);
  layers.hardpoints = hpGroup;

  // ---- fit camera to model -------------------------------------------------

  var box = new THREE.Box3().setFromObject(root);
  var sphere = box.getBoundingSphere(new THREE.Sphere());
  var target = sphere.center.clone();
  var radius = Math.max(sphere.radius, 50);

  var theta = Math.PI * 0.32;
  var phi = Math.PI * 0.38;
  var camRadius = radius * 2.4;
  var minRadius = radius * 0.4;
  var maxRadius = radius * 8;

  function updateCamera() {
    var x = target.x + camRadius * Math.sin(phi) * Math.sin(theta);
    var y = target.y + camRadius * Math.cos(phi);
    var z = target.z + camRadius * Math.sin(phi) * Math.cos(theta);
    camera.position.set(x, y, z);
    camera.up.set(0, 1, 0);
    camera.lookAt(target);
  }
  updateCamera();

  // ---- hand-rolled orbit controls (drag to orbit, wheel to zoom) ---------

  var dragging = false, lastX = 0, lastY = 0;
  canvas.addEventListener("pointerdown", function (e) {
    dragging = true; lastX = e.clientX; lastY = e.clientY;
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener("pointerup", function (e) {
    dragging = false;
    canvas.releasePointerCapture(e.pointerId);
  });
  canvas.addEventListener("pointermove", function (e) {
    if (!dragging) return;
    var dx = e.clientX - lastX, dy = e.clientY - lastY;
    lastX = e.clientX; lastY = e.clientY;
    theta -= dx * 0.006;
    phi = Math.min(Math.max(phi - dy * 0.006, 0.05), Math.PI - 0.05);
    updateCamera();
  });
  canvas.addEventListener("wheel", function (e) {
    e.preventDefault();
    camRadius *= Math.pow(1.0012, e.deltaY);
    camRadius = Math.min(Math.max(camRadius, minRadius), maxRadius);
    updateCamera();
  }, { passive: false });

  // ---- resize --------------------------------------------------------------

  function resize() {
    var w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);
  resize();

  (function loop() {
    requestAnimationFrame(loop);
    renderer.render(scene, camera);
  })();

  // ---- sidebar: build layer rows from what was actually exported ----------

  var layerRows = DATA.te_cut
    ? [["wing", "Wing (fixed)", STRUCTURE], ["cs", "Control Surface", KINEMATIC]]
    : [["oml", "Outer Mold Line", STRUCTURE]];
  Object.keys(DATA.spars).forEach(function (name) {
    layerRows.push(["spar_" + name, name.charAt(0).toUpperCase() + name.slice(1) + " Spar", STRUCTURE]);
  });
  layerRows.push(["ribs", "Rib Planes (" + DATA.rib_planes.length + ")", STRUCTURE]);
  if (Object.keys(DATA.hinge_axes).length) {
    layerRows.push(["hinges", "Hinge Axes", KINEMATIC]);
  }
  if (DATA.hardpoints.length) {
    layerRows.push(["hardpoints", "Hardpoints (" + DATA.hardpoints.length + ")", KINEMATIC]);
  }

  var listEl = document.getElementById("layer-list");
  layerRows.forEach(function (row) {
    var key = row[0], label = row[1], color = row[2];
    var wrap = document.createElement("label");
    wrap.className = "layer-row";
    var hex = "#" + color.toString(16).padStart(6, "0");
    wrap.innerHTML =
      '<input type="checkbox" checked>' +
      '<span class="swatch" style="background:' + hex + '"></span>' +
      '<span class="layer-name">' + label + "</span>";
    wrap.querySelector("input").addEventListener("change", function (e) {
      if (layers[key]) layers[key].visible = e.target.checked;
    });
    listEl.appendChild(wrap);
  });

  // ---- header + capability list -----------------------------------------

  document.getElementById("config-name").textContent = DATA.config_name + ".yaml";
  var capsEl = document.getElementById("capabilities");
  DATA.capabilities.forEach(function (line) {
    var div = document.createElement("div");
    var m = line.match(/^(P\d+):\s*(.*)$/);
    div.innerHTML = m ? "<b>" + m[1] + "</b> " + m[2] : line;
    capsEl.appendChild(div);
  });

  // ---- stats readout ---------------------------------------------------------

  var triCount = DATA.te_cut
    ? DATA.te_cut.wing.triangles.length + DATA.te_cut.control_surface.triangles.length
    : DATA.oml.triangles.length;
  Object.keys(DATA.spars).forEach(function (n) { triCount += DATA.spars[n].triangles.length; });

  var statLines = [
    ["config", DATA.config_name],
    ["half-span", DATA.half_span_mm.toFixed(0) + " mm"],
    ["triangles", triCount.toLocaleString()],
    ["rib planes", String(DATA.rib_planes.length)],
    ["hinge axes", String(Object.keys(DATA.hinge_axes).length)],
  ];
  if (DATA.te_cut) {
    statLines.push(["bodies", "2 (wing + control surf)"]);
    statLines.push(["cove / nose", DATA.te_cut.cove_radius_mm + " / " + DATA.te_cut.nose_radius_mm + " mm"]);
  } else {
    statLines.push(["hardpoints", String(DATA.hardpoints.length)]);
  }
  var statsEl = document.getElementById("stats");
  statLines.forEach(function (pair) {
    var row = document.createElement("div");
    row.className = "stat-row";
    row.innerHTML = '<span class="stat-key">' + pair[0] + '</span><span class="stat-val">' + pair[1] + "</span>";
    statsEl.appendChild(row);
  });
})();
