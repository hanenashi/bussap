import * as pdfjs from "/vendor/pdf.mjs";

pdfjs.GlobalWorkerOptions.workerSrc = "/vendor/pdf.worker.mjs";

document.getElementById("back").addEventListener("click", () => {
  window.close();
  setTimeout(() => { if (!window.closed) location.replace("/"); }, 150);
});

const viewport = document.getElementById("viewport");
const canvas = document.getElementById("page");
const pointers = new Map();
const state = { zoom: 2.3, x: 0, y: 0, width: 0, height: 0, ready: false };
let lastTap = null;
let multiTouch = false;

function dimensions() {
  const width = viewport.clientWidth * state.zoom;
  return { width, height: width * state.height / state.width };
}

function position() {
  const { width, height } = dimensions();
  state.x = width <= viewport.clientWidth ? (viewport.clientWidth - width) / 2 : Math.max(viewport.clientWidth - width, Math.min(0, state.x));
  state.y = height <= viewport.clientHeight ? (viewport.clientHeight - height) / 2 : Math.max(viewport.clientHeight - height, Math.min(0, state.y));
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  canvas.style.transform = `translate3d(${state.x}px, ${state.y}px, 0)`;
}

function zoomAt(next, oldX, oldY, newX = oldX, newY = oldY) {
  const oldZoom = state.zoom;
  state.zoom = Math.max(1, Math.min(8, next));
  const ratio = state.zoom / oldZoom;
  state.x = newX - (oldX - state.x) * ratio;
  state.y = newY - (oldY - state.y) * ratio;
  position();
}

function localPoint(event) {
  const rect = viewport.getBoundingClientRect();
  return { x: event.clientX - rect.left, y: event.clientY - rect.top };
}

viewport.addEventListener("pointerdown", event => {
  if (!state.ready) return;
  viewport.setPointerCapture(event.pointerId);
  const point = localPoint(event);
  pointers.set(event.pointerId, { ...point, startX: point.x, startY: point.y, moved: false });
  if (pointers.size > 1) { multiTouch = true; lastTap = null; }
});

viewport.addEventListener("pointermove", event => {
  const previous = pointers.get(event.pointerId);
  if (!previous || !state.ready) return;
  const point = localPoint(event);
  const before = [...pointers.values()];
  pointers.set(event.pointerId, { ...previous, x: point.x, y: point.y,
    moved: previous.moved || Math.hypot(point.x - previous.startX, point.y - previous.startY) > 10 });
  if (pointers.size === 1) {
    state.x += point.x - previous.x;
    state.y += point.y - previous.y;
    position();
  } else if (pointers.size === 2) {
    const after = [...pointers.values()];
    const distance = pair => Math.hypot(pair[0].x - pair[1].x, pair[0].y - pair[1].y);
    const oldDistance = distance(before);
    if (oldDistance > 0) {
      const oldMid = { x: (before[0].x + before[1].x) / 2, y: (before[0].y + before[1].y) / 2 };
      const newMid = { x: (after[0].x + after[1].x) / 2, y: (after[0].y + after[1].y) / 2 };
      zoomAt(state.zoom * distance(after) / oldDistance, oldMid.x, oldMid.y, newMid.x, newMid.y);
    }
  }
});

function endPointer(event) {
  const pointer = pointers.get(event.pointerId);
  if (!pointer) return;
  pointers.delete(event.pointerId);
  if (event.type === "pointerup" && !multiTouch && !pointer.moved) {
    const now = performance.now();
    if (lastTap && now - lastTap.time < 320 && Math.hypot(pointer.x - lastTap.x, pointer.y - lastTap.y) < 35) {
      zoomAt(state.zoom >= 7.5 ? 1 : state.zoom * 2, pointer.x, pointer.y);
      lastTap = null;
    } else lastTap = { time: now, x: pointer.x, y: pointer.y };
  }
  if (pointers.size === 0) multiTouch = false;
}
viewport.addEventListener("pointerup", endPointer);
viewport.addEventListener("pointercancel", endPointer);
viewport.addEventListener("contextmenu", event => event.preventDefault());

viewport.addEventListener("wheel", event => {
  if (!state.ready) return;
  event.preventDefault();
  if (event.ctrlKey || event.metaKey) {
    const point = localPoint(event);
    zoomAt(state.zoom * Math.exp(-event.deltaY * 0.01), point.x, point.y);
  } else {
    state.x -= event.deltaX;
    state.y -= event.deltaY;
    position();
  }
}, { passive: false });

viewport.addEventListener("keydown", event => {
  if (!state.ready) return;
  if (["+", "=", "-"].includes(event.key)) {
    event.preventDefault();
    zoomAt(state.zoom * (event.key === "-" ? 0.7 : 1.4), viewport.clientWidth / 2, viewport.clientHeight / 2);
  } else if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
    event.preventDefault();
    state.x += event.key === "ArrowLeft" ? 60 : event.key === "ArrowRight" ? -60 : 0;
    state.y += event.key === "ArrowUp" ? 60 : event.key === "ArrowDown" ? -60 : 0;
    position();
  }
});

try {
  const pdf = await pdfjs.getDocument("/network-map.pdf").promise;
  const page = await pdf.getPage(1);
  const original = page.getViewport({ scale: 1 });
  const renderViewport = page.getViewport({ scale: 1.5 });
  canvas.width = Math.ceil(renderViewport.width);
  canvas.height = Math.ceil(renderViewport.height);
  await page.render({ canvas, canvasContext: canvas.getContext("2d"), viewport: renderViewport }).promise;
  state.width = original.width;
  state.height = original.height;
  state.ready = true;
  const { width, height } = dimensions();
  state.x = (viewport.clientWidth - width) / 2;
  state.y = (viewport.clientHeight - height) / 2;
  position();
  let previousViewWidth = viewport.clientWidth;
  let previousViewHeight = viewport.clientHeight;
  new ResizeObserver(() => {
    const previousWidth = Number.parseFloat(canvas.style.width);
    const previousHeight = Number.parseFloat(canvas.style.height);
    const centerX = previousWidth ? (previousViewWidth / 2 - state.x) / previousWidth : 0.5;
    const centerY = previousHeight ? (previousViewHeight / 2 - state.y) / previousHeight : 0.5;
    const next = dimensions();
    state.x = viewport.clientWidth / 2 - centerX * next.width;
    state.y = viewport.clientHeight / 2 - centerY * next.height;
    previousViewWidth = viewport.clientWidth;
    previousViewHeight = viewport.clientHeight;
    position();
  }).observe(viewport);
  document.getElementById("message").hidden = true;
} catch (error) {
  document.getElementById("message").textContent = "PDFを表示できませんでした。";
  console.error("PDF reference could not be rendered", error);
}
