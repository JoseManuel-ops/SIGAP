import { apiGet } from "./api.js";

// Pide el PDF de la factura al backend y lo descarga en el navegador.
export async function descargarPdfFactura(referencia) {
  const { nombre, pdf_base64: pdfBase64 } = await apiGet(`/api/despachos/${referencia}/factura/pdf`);
  const bytes = Uint8Array.from(atob(pdfBase64), (c) => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre.endsWith(".pdf") ? nombre : `${nombre}.pdf`;
  enlace.click();
  URL.revokeObjectURL(url);
}
