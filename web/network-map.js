import * as pdfjs from "/vendor/pdf.mjs";

pdfjs.GlobalWorkerOptions.workerSrc = "/vendor/pdf.worker.mjs";

document.getElementById("back").addEventListener("click", () => {
  window.close();
  setTimeout(() => { if (!window.closed) location.replace("/"); }, 150);
});

try {
  const pdf = await pdfjs.getDocument("/network-map.pdf").promise;
  const page = await pdf.getPage(1);
  const viewport = page.getViewport({scale: 1});
  const canvas = document.getElementById("page");
  canvas.width = Math.ceil(viewport.width);
  canvas.height = Math.ceil(viewport.height);
  await page.render({canvas, canvasContext: canvas.getContext("2d"), viewport}).promise;
  document.getElementById("message").hidden = true;
} catch (error) {
  document.getElementById("message").textContent = "PDFを表示できませんでした。";
  console.error("PDF reference could not be rendered", error);
}
