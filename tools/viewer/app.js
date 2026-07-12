(function () {
  "use strict";
  var DATA = window.VIEWER_DATA;
  var STRUCTURE = 0x4fb2e8;
  var KINEMATIC = 0xf5a742;
  var SANDWICH = 0xa78bfa; // OUTER face-sheet shells — distinct from structure/kinematic (P6 WIP)
  var SANDWICH_CORE = 0xf472b6; // core shells — distinct from face sheets AND the status red
  var SANDWICH_INNER = 0x2dd4bf; // INNER face-sheet shells — third layer of the panel
  var FALSE_SPAR = 0xa3e635; // device-cut closing wall — distinct from KINEMATIC's amber
  var RIB_SOLID = 0xfb923c; // solid rib plates — distinct from every other P6 layer color

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

  function disposeGroup(group) {
    group.traverse(function (obj) {
      if (obj.geometry) obj.geometry.dispose();
      if (obj.material) {
        (Array.isArray(obj.material) ? obj.material : [obj.material]).forEach(function (m) { m.dispose(); });
      }
    });
  }

  // ---- camera: fit-to-model + hand-rolled orbit controls -------------------

  var theta = Math.PI * 0.32;
  var phi = Math.PI * 0.38;
  var camRadius = 1000, minRadius = 100, maxRadius = 8000, target = new THREE.Vector3();

  function updateCamera() {
    var x = target.x + camRadius * Math.sin(phi) * Math.sin(theta);
    var y = target.y + camRadius * Math.cos(phi);
    var z = target.z + camRadius * Math.sin(phi) * Math.cos(theta);
    camera.position.set(x, y, z);
    camera.up.set(0, 1, 0);
    camera.lookAt(target);
  }

  function fitCameraToRoot() {
    var box = new THREE.Box3().setFromObject(root);
    var sphere = box.getBoundingSphere(new THREE.Sphere());
    target = sphere.center.clone();
    var radius = Math.max(sphere.radius, 50);
    camRadius = radius * 2.4;
    minRadius = radius * 0.4;
    maxRadius = radius * 8;
    updateCamera();
  }

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

  // ---- live hinge deflection (rotates the CS about the REAL hinge axis,   --
  // ---- not a pre-baked snapshot — this is the same rigid rotation the P4  --
  // ---- gate applies to prove clearance holds at every angle) ---------------

  var deflectionPivot = null; // THREE.Group whose origin sits at the hinge point
  var currentHingeDir = null;

  function setDeflectionDeg(deg) {
    if (!deflectionPivot || !currentHingeDir) return;
    deflectionPivot.setRotationFromAxisAngle(currentHingeDir, (deg * Math.PI) / 180);
  }

  // ---- sidebar builders ------------------------------------------------

  var layerListEl = document.getElementById("layer-list");
  var capsEl = document.getElementById("capabilities");
  var statsEl = document.getElementById("stats");
  var gateEl = document.getElementById("gate-metrics");
  var deflectionRow = document.getElementById("deflection-row");
  var deflectionSlider = document.getElementById("deflection-slider");
  var deflectionLabel = document.getElementById("deflection-label");
  var curvaturePanel = document.getElementById("curvature-panel");
  var curvatureStationSelect = document.getElementById("curvature-station-select");
  var curvatureBadge = document.getElementById("curvature-badge");
  var curvatureCanvas = document.getElementById("curvature-canvas");
  var curvatureReadout = document.getElementById("curvature-readout");
  var rejectedPanel = document.getElementById("rejected-panel");
  var rejectedList = document.getElementById("rejected-list");
  var sandwichPanel = document.getElementById("sandwich-panel");
  var sandwichWarning = document.getElementById("sandwich-warning");

  function statRow(container, k, v) {
    var row = document.createElement("div");
    row.className = "stat-row";
    row.innerHTML = '<span class="stat-key">' + k + '</span><span class="stat-val">' + v + "</span>";
    container.appendChild(row);
  }

  // ---- nose curvature chart (canvas) — the exact diagnostic that caught  --
  // ---- and confirmed the fix for the lumpy-nose defect (ADR-003)         --

  var curvatureStations = []; // current config's te_cut.curvature_check.stations
  var curvatureHoverIdx = -1;

  function drawCurvatureChart(station) {
    var ctx = curvatureCanvas.getContext("2d");
    var w = curvatureCanvas.width, h = curvatureCanvas.height;
    var pad = { l: 34, r: 10, t: 10, b: 16 };
    var plotW = w - pad.l - pad.r, plotH = h - pad.t - pad.b;
    var kink = station.kink_deg;

    ctx.clearRect(0, 0, w, h);

    var maxVal = Math.max.apply(null, kink);
    var scaleMax = Math.max(maxVal * 1.2, station.mean_deg * 1.4, 0.02);

    function x(i) { return pad.l + (i / (kink.length - 1)) * plotW; }
    function y(v) { return pad.t + plotH - (v / scaleMax) * plotH; }

    // axes
    ctx.strokeStyle = "rgba(124, 134, 152, 0.35)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad.l, pad.t);
    ctx.lineTo(pad.l, pad.t + plotH);
    ctx.lineTo(pad.l + plotW, pad.t + plotH);
    ctx.stroke();

    // mean reference (dashed) — "flat at the mean" is the smooth signature
    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = "rgba(124, 134, 152, 0.55)";
    ctx.beginPath();
    ctx.moveTo(pad.l, y(station.mean_deg));
    ctx.lineTo(pad.l + plotW, y(station.mean_deg));
    ctx.stroke();
    ctx.setLineDash([]);

    // data line
    ctx.strokeStyle = "#f5a742";
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.beginPath();
    kink.forEach(function (v, i) {
      var px = x(i), py = y(v);
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    });
    ctx.stroke();

    // hover crosshair + point
    if (curvatureHoverIdx >= 0 && curvatureHoverIdx < kink.length) {
      var hx = x(curvatureHoverIdx), hy = y(kink[curvatureHoverIdx]);
      ctx.strokeStyle = "rgba(221, 227, 238, 0.3)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(hx, pad.t);
      ctx.lineTo(hx, pad.t + plotH);
      ctx.stroke();
      ctx.fillStyle = "#f5a742";
      ctx.beginPath();
      ctx.arc(hx, hy, 3, 0, Math.PI * 2);
      ctx.fill();
    }

    // axis labels
    ctx.fillStyle = "#7c8698";
    ctx.font = "9.5px ui-monospace, monospace";
    ctx.textAlign = "right";
    ctx.fillText(scaleMax.toFixed(2) + "°", pad.l - 5, pad.t + 8);
    ctx.fillText("0°", pad.l - 5, pad.t + plotH + 2);
    ctx.textAlign = "left";
    ctx.fillText("Pl-side", pad.l, h - 3);
    ctx.textAlign = "right";
    ctx.fillText("Pu-side", pad.l + plotW, h - 3);
  }

  function updateCurvatureReadout(station) {
    if (curvatureHoverIdx >= 0 && curvatureHoverIdx < station.kink_deg.length) {
      curvatureReadout.textContent =
        "point " + curvatureHoverIdx + "/" + station.kink_deg.length +
        ": " + station.kink_deg[curvatureHoverIdx].toFixed(3) + "° (mean " + station.mean_deg.toFixed(3) + "°)";
    } else {
      curvatureReadout.textContent = "mean " + station.mean_deg.toFixed(3) + "° across " + station.kink_deg.length + " points — hover the chart to inspect a point";
    }
  }

  curvatureCanvas.addEventListener("mousemove", function (e) {
    var station = curvatureStations[curvatureStationSelect.selectedIndex];
    if (!station) return;
    var rect = curvatureCanvas.getBoundingClientRect();
    var px = (e.clientX - rect.left) * (curvatureCanvas.width / rect.width);
    var pad = { l: 34, r: 10 };
    var plotW = curvatureCanvas.width - pad.l - pad.r;
    var frac = Math.min(Math.max((px - pad.l) / plotW, 0), 1);
    curvatureHoverIdx = Math.round(frac * (station.kink_deg.length - 1));
    drawCurvatureChart(station);
    updateCurvatureReadout(station);
  });
  curvatureCanvas.addEventListener("mouseleave", function () {
    curvatureHoverIdx = -1;
    var station = curvatureStations[curvatureStationSelect.selectedIndex];
    if (station) { drawCurvatureChart(station); updateCurvatureReadout(station); }
  });

  function renderCurvatureStation() {
    var station = curvatureStations[curvatureStationSelect.selectedIndex];
    if (!station) return;
    curvatureHoverIdx = -1;
    drawCurvatureChart(station);
    updateCurvatureReadout(station);
    var good = station.spike_ratio < 1.5; // matches the gate's own bound (test_nose_surface_smoothness)
    curvatureBadge.textContent = station.spike_ratio.toFixed(2) + "x spike";
    curvatureBadge.className = "spike-badge " + (good ? "good" : "attention");
  }

  function updateCurvaturePanel(data) {
    var check = data.te_cut && data.te_cut.curvature_check;
    if (!check) {
      curvaturePanel.style.display = "none";
      return;
    }
    curvaturePanel.style.display = "";
    curvatureStations = check.stations;
    curvatureStationSelect.innerHTML = "";
    check.stations.forEach(function (s) {
      var opt = document.createElement("option");
      opt.textContent = s.label + " (spanwise)";
      curvatureStationSelect.appendChild(opt);
    });
    curvatureStationSelect.selectedIndex = Math.floor(check.stations.length / 2); // default: mid-span
    renderCurvatureStation();
  }

  curvatureStationSelect.addEventListener("change", renderCurvatureStation);

  var layers = {};

  function rebuildSidebar(data) {
    capsEl.innerHTML = "";
    data.capabilities.forEach(function (line) {
      var div = document.createElement("div");
      var m = line.match(/^(P\d+):\s*(.*)$/);
      div.innerHTML = m ? "<b>" + m[1] + "</b> " + m[2] : line;
      capsEl.appendChild(div);
    });

    layerListEl.innerHTML = "";
    var layerRows = data.te_cut
      ? [["wing", "Wing (fixed)", STRUCTURE], ["cs", "Control Surface", KINEMATIC]]
      : [["oml", "Outer Mold Line", STRUCTURE]];
    Object.keys(data.spars).forEach(function (name) {
      layerRows.push(["spar_" + name, name.charAt(0).toUpperCase() + name.slice(1) + " Spar", STRUCTURE]);
    });
    layerRows.push(["ribs", "Rib Planes (" + data.rib_planes.length + ")", STRUCTURE]);
    if (Object.keys(data.hinge_axes).length) {
      layerRows.push(["hinge_axes_display", "Hinge Axes", KINEMATIC]);
    }
    if (data.hardpoints.length) {
      layerRows.push(["hardpoints", "Hardpoints (" + data.hardpoints.length + ")", KINEMATIC]);
    }
    if (data.sandwich) {
      layerRows.push(["sandwich_face_outer_upper", "Upper outer face (P6 WIP)", SANDWICH]);
      layerRows.push(["sandwich_face_outer_lower", "Lower outer face (P6 WIP)", SANDWICH]);
      layerRows.push(["sandwich_core_upper", "Upper core (P6 WIP)", SANDWICH_CORE]);
      layerRows.push(["sandwich_core_lower", "Lower core (P6 WIP)", SANDWICH_CORE]);
      layerRows.push(["sandwich_face_inner_upper", "Upper inner face (P6 WIP)", SANDWICH_INNER]);
      layerRows.push(["sandwich_face_inner_lower", "Lower inner face (P6 WIP)", SANDWICH_INNER]);
      layerRows.push(["sandwich_false_spar", "False spar (P6 WIP)", FALSE_SPAR]);
      var ribKeys = Object.keys(data.sandwich).filter(function (k) { return k.indexOf("wing_rib_") === 0; });
      if (ribKeys.length) {
        layerRows.push(["sandwich_ribs", "Ribs (" + ribKeys.length + ", P6 WIP)", RIB_SOLID]);
      }
    }
    layerRows.forEach(function (row) {
      var rowKey = row[0], label = row[1], color = row[2];
      var wrap = document.createElement("label");
      wrap.className = "layer-row";
      var hex = "#" + color.toString(16).padStart(6, "0");
      wrap.innerHTML =
        '<input type="checkbox" checked>' +
        '<span class="swatch" style="background:' + hex + '"></span>' +
        '<span class="layer-name">' + label + "</span>";
      wrap.querySelector("input").addEventListener("change", function (e) {
        if (layers[rowKey]) layers[rowKey].visible = e.target.checked;
      });
      layerListEl.appendChild(wrap);
    });

    var triCount = data.te_cut
      ? data.te_cut.wing.triangles.length + data.te_cut.control_surface.triangles.length
      : data.oml.triangles.length;
    Object.keys(data.spars).forEach(function (n) { triCount += data.spars[n].triangles.length; });

    statsEl.innerHTML = "";
    statRow(statsEl, "config", data.config_name);
    statRow(statsEl, "half-span", data.half_span_mm.toFixed(0) + " mm");
    statRow(statsEl, "triangles", triCount.toLocaleString());
    statRow(statsEl, "rib planes", String(data.rib_planes.length));
    statRow(statsEl, "hinge axes", String(Object.keys(data.hinge_axes).length));
    if (data.te_cut) {
      statRow(statsEl, "bodies", "2 (wing + control surf)");
      statRow(statsEl, "nose radius R range", data.te_cut.nose_radius_range_mm.join("–") + " mm");
      statRow(statsEl, "cove clearance target", data.te_cut.cove_clearance_target_mm + " mm");
      statRow(statsEl, "anti-unporting margin", data.te_cut.overlap_margin_deg + "°");
    } else {
      statRow(statsEl, "hardpoints", String(data.hardpoints.length));
    }

    gateEl.innerHTML = "";
    var gm = data.te_cut && data.te_cut.gate_metrics;
    if (gm) {
      gateEl.style.display = "";
      statRow(gateEl, "nose tangency (mean-R)", gm.nose_tangency.worst_mean_radius_err_deg + "° (< 2.0°)");
      statRow(gateEl, "nose single-arc dev", gm.nose_is_single_arc.worst_radius_dev_mm + " mm");
      statRow(gateEl, "cove clearance @ 0°", gm.cove_clearance_mm.rest + " mm");
      statRow(gateEl, "cove clearance @ +max", gm.cove_clearance_mm.deflected + " mm");
      statRow(gateEl, "no-unporting margin", gm.no_unporting_worst_margin_deg + "°");
      statRow(gateEl, "volume conservation", gm.conservation_pct + "%");
      statRow(gateEl, "shards (F3)", String(gm.shards));
    } else {
      gateEl.style.display = "none";
    }

    if (data.te_cut) {
      deflectionRow.style.display = "";
      var maxDefl = data.te_cut.max_deflection_deg;
      deflectionSlider.min = -maxDefl;
      deflectionSlider.max = maxDefl;
      deflectionSlider.step = Math.max(0.5, maxDefl / 100);
      deflectionSlider.value = 0;
      deflectionLabel.textContent = "0.0°";
    } else {
      deflectionRow.style.display = "none";
    }

    updateCurvaturePanel(data);

    if (data.sandwich) {
      sandwichPanel.style.display = "";
      var dw = data.sandwich.device_window_y_mm;
      sandwichWarning.textContent = data.sandwich.warning + " Device window: y ∈ [" +
        dw[0] + ", " + dw[1] + "] mm.";
    } else {
      sandwichPanel.style.display = "none";
    }
  }

  // ---- scene assembly (re-invokable so a config switch rebuilds in place) --

  function buildScene(data) {
    disposeGroup(root);
    root.clear();
    layers = {};
    deflectionPivot = null;
    currentHingeDir = null;

    if (data.te_cut) {
      layers.wing = indexedMesh(data.te_cut.wing, STRUCTURE, 0.28);
      root.add(layers.wing);

      var csMesh = indexedMesh(data.te_cut.control_surface, KINEMATIC, 0.9);
      var hp = data.te_cut.hinge_point, hd = data.te_cut.hinge_dir;
      deflectionPivot = new THREE.Group();
      deflectionPivot.position.set(hp[0], hp[1], hp[2]);
      csMesh.position.set(-hp[0], -hp[1], -hp[2]);
      deflectionPivot.add(csMesh);
      root.add(deflectionPivot);
      currentHingeDir = new THREE.Vector3(hd[0], hd[1], hd[2]).normalize();
      layers.cs = deflectionPivot; // toggling visibility hides the pivot + its CS child
    } else {
      layers.oml = indexedMesh(data.oml, STRUCTURE, 0.32);
      root.add(layers.oml);
    }

    Object.keys(data.spars).forEach(function (name) {
      var g = indexedMesh(data.spars[name], STRUCTURE, 0.85);
      root.add(g);
      layers["spar_" + name] = g;
    });

    var ribGroup = new THREE.Group();
    data.rib_planes.forEach(function (rib) { ribGroup.add(ribPlane(rib, STRUCTURE)); });
    root.add(ribGroup);
    layers.ribs = ribGroup;

    var hingeRadius = Math.max(2, data.half_span_mm * 0.0025);
    var hingeAxesGroup = new THREE.Group();
    Object.keys(data.hinge_axes).forEach(function (name) {
      var pts = data.hinge_axes[name];
      hingeAxesGroup.add(axisRod(pts[0], pts[1], KINEMATIC, hingeRadius));
    });
    root.add(hingeAxesGroup);
    layers.hinge_axes_display = hingeAxesGroup;

    var hpGroup = new THREE.Group();
    var hpRadius = Math.max(3, data.half_span_mm * 0.006);
    data.hardpoints.forEach(function (p) { hpGroup.add(hardpointMarker(p, KINEMATIC, hpRadius)); });
    root.add(hpGroup);
    layers.hardpoints = hpGroup;

    if (data.sandwich) {
      [["sandwich_face_outer_upper", "wing_face_outer_upper", SANDWICH, 0.5],
       ["sandwich_face_outer_lower", "wing_face_outer_lower", SANDWICH, 0.5],
       ["sandwich_core_upper", "wing_core_upper", SANDWICH_CORE, 0.75],
       ["sandwich_core_lower", "wing_core_lower", SANDWICH_CORE, 0.75],
       ["sandwich_face_inner_upper", "wing_face_inner_upper", SANDWICH_INNER, 0.85],
       ["sandwich_face_inner_lower", "wing_face_inner_lower", SANDWICH_INNER, 0.85],
       ["sandwich_false_spar", "wing_false_spar", FALSE_SPAR, 0.9]].forEach(function (row) {
        var mesh = indexedMesh(data.sandwich[row[1]], row[2], row[3]);
        root.add(mesh);
        layers[row[0]] = mesh;
      });

      var ribGroupSolid = new THREE.Group();
      Object.keys(data.sandwich).filter(function (k) { return k.indexOf("wing_rib_") === 0; })
        .forEach(function (key) { ribGroupSolid.add(indexedMesh(data.sandwich[key], RIB_SOLID, 0.8)); });
      if (ribGroupSolid.children.length) {
        root.add(ribGroupSolid);
        layers.sandwich_ribs = ribGroupSolid;
      }
    }

    fitCameraToRoot();
    rebuildSidebar(data);
    document.getElementById("config-name").textContent = data.config_name + ".yaml";
  }

  // ---- rejected configs (global, not per-config-switch — ADR-003's        --
  // ---- config-time validation firing correctly on a deliberately too-     --
  // ---- aggressive twist/hinge_xc combination) -------------------------------

  (function renderRejectedPanel() {
    var rejected = DATA.rejected || {};
    var stems = Object.keys(rejected);
    if (!stems.length) { rejectedPanel.style.display = "none"; return; }
    rejectedPanel.style.display = "";
    rejectedList.innerHTML = "";
    stems.forEach(function (stem) {
      var item = document.createElement("div");
      item.className = "rejected-item";
      item.innerHTML =
        '<div class="rejected-name">' + stem + ".yaml</div>" +
        '<div class="rejected-reason">' + rejected[stem].message + "</div>";
      rejectedList.appendChild(item);
    });
  })();

  // ---- config switcher -----------------------------------------------------

  var configSelect = document.getElementById("config-select");
  Object.keys(DATA.configs).forEach(function (stem) {
    var opt = document.createElement("option");
    opt.value = stem;
    opt.textContent = stem;
    configSelect.appendChild(opt);
  });
  configSelect.value = DATA.default_config;
  configSelect.addEventListener("change", function () {
    buildScene(DATA.configs[configSelect.value]);
  });

  deflectionSlider.addEventListener("input", function () {
    var deg = parseFloat(deflectionSlider.value);
    deflectionLabel.textContent = deg.toFixed(1) + "°";
    setDeflectionDeg(deg);
  });

  buildScene(DATA.configs[DATA.default_config]);
})();
