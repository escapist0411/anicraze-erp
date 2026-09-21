# EVM wireless barcode scanner acceptance

The ANICRAZE scanner workspace treats the EVM EWLS/EVMS 126 family as a standard USB/Bluetooth HID keyboard scanner. It does not require a browser extension, proprietary SDK, or native driver integration.

## Manual hardware test

1. Open TextEdit or Notes and scan a barcode. The barcode characters should appear, followed by Enter.
2. Sign in as Owner or Manager and open **Barcode Scanner → Test Scanner**.
3. Click **Start Scanner** and scan a registered ANICRAZE barcode. The page should show the received code, product, and Scanner input: WORKING.
4. Scan an unknown barcode. The page should show Scanner: WORKING and Product: NOT FOUND.
5. Select a pending receipt in **Godown Intake** and scan an expected product. The count must increase exactly once.
6. Repeated scans of the same product are valid until its expected quantity is reached. An additional scan must be rejected.
7. Confirm stock entry only after every expected unit is scanned.

If scanning produces no text, verify that the scanner is configured in USB HID / keyboard mode. Hardware-specific configuration barcodes must only be used after consulting the scanner's verified manual.
