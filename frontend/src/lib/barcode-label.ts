export interface ThermalBarcodeLabel {
  productName: string;
  barcode: string;
  barcodeImageUrl: string;
  sellingPrice: string | number;
}

const escapeHtml = (value: string) => String(value).replace(
  /[&<>'"]/g,
  (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]!,
);

export function formatThermalLabelPrice(value: string | number) {
  const numericValue = typeof value === 'number' ? value : Number(value);
  if (value === '' || !Number.isFinite(numericValue) || numericValue < 0) {
    throw new Error('Selling price is invalid. Correct the product before printing.');
  }
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(numericValue);
}

function productNameSizeClass(productName: string) {
  if (productName.length > 42) return ' product-name--very-long';
  if (productName.length > 28) return ' product-name--long';
  return '';
}

/** Build one 50 mm × 25 mm page per label for a direct thermal printer. */
export function buildThermalLabelDocument(labels: ThermalBarcodeLabel[], title = 'ANICRAZE barcode labels') {
  const pages = labels.map((label) => `
    <article class="barcode-label">
      <div class="product-name${productNameSizeClass(label.productName)}" title="${escapeHtml(label.productName)}">${escapeHtml(label.productName)}</div>
      <div class="barcode-graphic"><img class="barcode-image" src="${escapeHtml(label.barcodeImageUrl)}" alt="Barcode ${escapeHtml(label.barcode)}"></div>
      <div class="barcode-value">${escapeHtml(label.barcode)}</div>
      <div class="selling-price">${escapeHtml(formatThermalLabelPrice(label.sellingPrice))}</div>
    </article>`).join('');

  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>${escapeHtml(title)}</title>
    <style>
      @page { size: 50mm 25mm; margin: 0; }
      * { box-sizing: border-box; }
      html, body { width: 50mm; margin: 0; padding: 0; background: #fff; }
      body { color: #000; font-family: Arial, Helvetica, sans-serif; }
      .barcode-label {
        width: 50mm;
        height: 25mm;
        padding: 1.4mm 2mm .8mm;
        display: flex;
        flex-direction: column;
        align-items: center;
        overflow: hidden;
        break-after: page;
        page-break-after: always;
      }
      .barcode-label:last-child { break-after: auto; page-break-after: auto; }
      .product-name {
        width: 100%;
        height: 3.8mm;
        flex: 0 0 3.8mm;
        padding-top: .35mm;
        overflow: hidden;
        font-size: 8pt;
        font-weight: 700;
        line-height: 3.1mm;
        text-align: center;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .product-name--long { font-size: 7.25pt; }
      .product-name--very-long { font-size: 6.5pt; }
      .barcode-graphic {
        display: block;
        width: 46mm;
        height: 10mm;
        flex: 0 0 10mm;
        margin: .3mm 0 0;
        overflow: hidden;
      }
      .barcode-image {
        display: block;
        width: 46mm;
        height: 14.4mm;
        object-fit: fill;
      }
      .barcode-value {
        width: 100%;
        height: 2.8mm;
        flex: 0 0 2.8mm;
        overflow: hidden;
        font-family: "Courier New", monospace;
        font-size: 6.5pt;
        font-weight: 600;
        line-height: 2.8mm;
        text-align: center;
        white-space: nowrap;
      }
      .selling-price {
        width: 100%;
        height: 4.5mm;
        flex: 0 0 4.5mm;
        overflow: hidden;
        font-size: 11pt;
        font-weight: 800;
        line-height: 4.5mm;
        text-align: center;
        white-space: nowrap;
      }
      @media screen {
        body { width: auto; padding: 24px; background: #e5e7eb; }
        .barcode-label { margin: 0 auto 18px; background: #fff; box-shadow: 0 3px 14px rgba(0,0,0,.18); transform: scale(2); transform-origin: top center; }
        .barcode-label:not(:last-child) { margin-bottom: 48mm; }
      }
      @media print {
        html, body { width: 50mm; height: auto; background: #fff; }
      }
    </style>
  </head>
  <body>${pages}
    <script>
      (async () => {
        const images = Array.from(document.images);
        await Promise.all(images.map((image) => image.complete
          ? (image.decode ? image.decode().catch(() => undefined) : Promise.resolve())
          : new Promise((resolve) => { image.onload = image.onerror = resolve; })));
        window.setTimeout(() => window.print(), 100);
      })();
    <\/script>
  </body>
</html>`;
}

export function openThermalLabelPrintWindow(labels: ThermalBarcodeLabel[], title?: string) {
  const printWindow = window.open('', '_blank', 'width=900,height=700');
  if (!printWindow) throw new Error('Allow pop-ups to print barcode labels.');
  printWindow.document.write(buildThermalLabelDocument(labels, title));
  printWindow.document.close();
}
