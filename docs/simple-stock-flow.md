# ANICRAZE simple stock flow

## 1. Product Master

Choose products that already exist in the approved Product Master. Selling prices stay controlled by the Product Master.

## 2. Receive Stock

Open **Receive Stock**, add every purchased product to one receipt, and enter its quantity and purchase cost per unit. Saving the receipt records pending pieces only; it does not increase warehouse stock.

## 3. Barcode Centre

Continue to **Barcode Centre**. Existing product barcodes are reused. Generate a Code 128 barcode only when a product has none, then print the required number of identical labels for each product.

## 4. Scan to Godown

Stick the labels on the physical products and open **Scan to Godown**. Select the receiving batch and scan with a USB scanner, phone camera, or manual entry. Every scan increments that product's verified count. The system prevents scanning more than the receipt expects.

## 5. Inventory

When every expected piece has been scanned, select **Confirm Stock Entry**. Only then does stock enter the Central Warehouse. The backend updates weighted-average cost and writes the existing immutable inventory movement and ledger records. Repeating confirmation cannot add stock twice.

## 6. Transfer

Open **Inventory**, select **Transfer to Shop**, add multiple products, and complete the existing approval, picking, packing, and dispatch steps.

## 7. Shop Receive

The shop manager checks the dispatched products and confirms the received quantities. Cost information remains restricted to authorized management.

## 8. Sell

The employee opens **Scan & Bill**, scans the product, and sells it at its Product Master selling price. The shop stock, invoice, payment, owner dashboard, inventory reports, finance, cost of goods, and gross profit update through the existing ERP services.

> Demo storage note: generated labels and documents use temporary hosting storage and are not permanent production document archives.
