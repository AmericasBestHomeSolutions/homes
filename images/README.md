# Home photos go in this folder

The website shows a photo on a home **the moment you add it here** — you do NOT
edit `homes.js` or any code. It works by matching the file name to the home's ID.

## How to add a photo

1. Find the home's **ID** in `homes.js` (the `id:` line), or in the web address
   (`home.html?home=THIS-PART`). Example ID: `decatur-il-1830-lowber`.
2. Save the main photo as that ID + `.jpg` and drop it in this folder:
   `images/decatur-il-1830-lowber.jpg`
   → it now shows on that home's card AND at the top of its page.
3. (Optional) Extra photos for the photo gallery on the home's page — add up to four:
   `images/decatur-il-1830-lowber-1.jpg`
   `images/decatur-il-1830-lowber-2.jpg`
   `images/decatur-il-1830-lowber-3.jpg`
   `images/decatur-il-1830-lowber-4.jpg`

That's it. No photo yet = the home shows a clean navy card with its city — never a
broken image.

## Tips
- Use `.jpg` (lowercase). Keep files reasonably small (under ~500 KB each loads fast).
- The ID must match **exactly**, including the dashes.
- `_photo-filenames.txt` in this folder lists every current home and the exact main
  file name to use — handy when downloading a batch from OneDrive.
