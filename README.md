# The ThoughtTronix Store

*Your Thoughts, Our Business.*

A server-rendered Django 6 storefront and back office for the world's most
beloved consumer neural technology: browse the catalog, fill a cart, check
out through a fully validated form, and — if you're staff — run the store
from the back office, analytics dashboard included.

## Getting started

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/). No Node.js —
Tailwind runs as a standalone binary.

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py seed
uv run python manage.py tailwind runserver
```

Then open <http://127.0.0.1:8000/>. From clone to browsing the store, this
takes about two minutes.

## Demo logins

The `seed` command creates a fixed demo world — the same one every run:

| Username   | Password      | Who they are                                                  |
| ---------- | ------------- | ------------------------------------------------------------- |
| `admin`    | `admin123`    | Superuser: everything below, plus the Django admin at `/admin/` |
| `employee` | `employee123` | Staff: the back office (products, orders, dashboard)           |
| `customer` | `customer123` | A customer with order history and a live cart                  |

## Commands

| Command                                     | What it does                             |
| ------------------------------------------- | ---------------------------------------- |
| `uv sync`                                    | Install dependencies                     |
| `uv run python manage.py migrate`            | Apply database migrations                |
| `uv run python manage.py seed`               | Reset the database to the demo world (destructive, idempotent) |
| `uv run python manage.py tailwind runserver` | Dev server + Tailwind watch              |
| `uv run python manage.py tailwind build`     | Compile production CSS                   |
| `uv run pytest`                              | Run the test suite                       |
| `uv run ruff check .`                        | Lint                                     |
| `uv run ruff format .`                       | Format                                   |

## Repo layout

`config/` is the project package (settings, root URLs); the four apps are
`accounts` (custom user model), `products` (the public catalog and its
back-office CRUD), `orders` (cart, checkout, orders — with the
`place_order` service in `orders/services.py`), and `dashboard` (staff
analytics, with the aggregations in `dashboard/queries.py`). Project-level
templates live in `templates/`, static sources in `assets/`. The product
requirements are in `prd/`, the phase-by-phase build plan in `plans/`, and
`PROMPTS.md` is where AI usage on this codebase gets logged.

## Discount coupons

Staff manage promotions under **Back office → Coupons**. Codes are fixed,
case-insensitive, and contain 3–30 letters, digits, or hyphens. Choose a
whole percentage from 1–100%, either the whole order or selected products,
and an end date. Coupons start inactive; enable **Is active** to launch or
disable it to retire. End dates include the entire day in America/Chicago.

Customers apply one code at checkout and see the savings before ordering.
The cart remembers the code until removal or successful checkout. There
are no usage limits or minimum spend. Discounts are rounded half up per
product line; ineligible lines receive no discount. Free orders require
contact and addresses but no card. Completed orders retain their purchase
amounts even after coupon or product edits. Dashboard revenue is after
discounts and still excludes cancelled orders.

### Browser verification

Apply migrations and start the development server using the commands above.
Use the existing database; do not reseed to test coupons. Use separate browser
profiles (or a private window) for staff and customer logins.

1. As staff, create `SERAPHINE50`: 50%, Selected products, select Seraphine,
   choose a future end date, and enable Is active. Create an order-wide
   `ORDER50` coupon as well. Try a duplicate code in lowercase and a
   product-specific coupon with no products; both should show form errors.
2. As a customer, put two $249 Seraphines and one $100 ineligible product
   in the cart. If needed, create a $100 test accessory through product
   management. Apply ` seraphine50 ` at checkout. Expect **$598.00 subtotal,
   $249.00 discount, $349.00 total**. Apply `ORDER50` instead: expect
   **$299.00 discount and $299.00 total**. Only one code is selected.
3. Return to the cart, change quantities, and reopen checkout. The selected
   code should persist and savings should update. Remove it to restore
   full pricing. Apply/Remove should preserve typed address details and
   work before the address form is complete.
4. Restore the example cart, apply `SERAPHINE50`, and place the order using
   a valid demo card such as `4242 4242 4242 4242`, a future expiry, and a
   three-digit CVV. Confirmation and customer/staff order details should
   retain the same subtotal, discount, and total. The cart/code should clear.
5. Retire `SERAPHINE50` as staff. Revisit the completed order: its amounts
   must not change. Applying that code to another cart should show an
   inactive message and block placement. Reactivate it to allow reuse.
6. Set the code's end date to yesterday. Apply it: expect a readable
   expiration message, an intact cart, and no order. Remove or replace it
   to continue. Also try an unknown code and a cart with no eligible products.
7. Preview a valid coupon, then change its percentage in the staff window.
   Submit the old customer preview: no order should be placed. Review the
   refreshed breakdown and submit again to accept the new terms.
8. Create an active 100% whole-order coupon. Applying it should show
   **No payment required**, omit card inputs, and allow checkout after
   contact and addresses are filled. Removing it should restore card inputs.
9. Check the dashboard: product revenue should reflect saved line discounts.
   Signed-in customers must receive 403 when visiting `/backoffice/coupons/`.

Run `uv run pytest`, `uv run ruff check .`, and
`uv run python manage.py tailwind build` for automated verification. Tests
create their own fixtures and never run the seed command. After browser
review, complete the assignment's feature commit/push, a separate meaningful
review change and commit/push, then the requested session log and your own
reflection with the final commit/push.


## Product images

Employees upload one optional product image on the back-office create/edit form;
superusers use the same image controls and current-image preview in Django admin.
Choose **Remove image** to restore the category placeholder. Unrelated edits keep
existing artwork. Still JPEG, PNG and WebP contents are accepted regardless of
filename or claimed MIME type. Files must be at most **10 MiB (10,485,760 bytes)**,
at most **20,000,000 decoded pixels**, and at least **400 pixels on both axes**.
Corrupt, truncated and animated files are rejected with inline errors.

Uploads are decoded before saving, oriented using EXIF, and converted to WebP at
quality 85. Only a catalog version (longest side at most 600 pixels) and a detail
version (at most 1,200 pixels) are retained. Aspect ratio and transparency are
preserved; small images are never enlarged. Square frames show complete artwork
without cropping. Catalog cards lazy-load the small version; detail images load
normally. Each missing version independently falls back to its category SVG.

`MEDIA_ROOT` defaults to repository-root `media/`; `MEDIA_URL` defaults to
`/media/`. Both can be configured in `.env`. Never set `MEDIA_ROOT` to
`product-images/`. This checkout excludes both directories through
`.git/info/exclude`; `.gitignore` is unchanged. Other checkouts should add local
excludes for `/media/` and `/product-images/`, or keep media outside the repository.
In production, use a persistent writable media volume, back it up with the
database, and configure the web server to serve `MEDIA_URL` from that volume.
Django's DEBUG media serving is for local development only.

Image pairs get unique filenames and are referenced only after both writes
succeed. Partial write failures are cleaned up; invalid forms write nothing.
Replaced/removed/deleted files are cleaned only after database commit. Database
rollback preserves the old image; because filesystem writes are not transactional,
a rollback or interrupted request can leave an unreferenced new pair. Periodically
run `uv run python manage.py prune_product_images` to review unreferenced WebPs
older than 24 hours, then use `--delete` to remove them. Run reconciliation during
a quiet maintenance window, with no long-running image imports or transactions.

### Marketing import

After applying migrations, run:

```bash
uv run python manage.py import_product_images
# Or use a separate source location:
uv run python manage.py import_product_images --source "path/to/artwork"
```

This command changes only images on existing products without any stored image
reference. It reports imports, existing-image skips, missing target products and
missing/invalid files, then totals; valid files continue importing after failures.
Reruns preserve employee uploads. It does not seed, create products, move sources
or keep original uploads in media. The twelve explicit assignments include
SoulSear **Mark I** only and **SyncRest GPT No Text.png**; the text-bearing SyncRest
and related variants are not imported. Source artwork remains untouched and can
be archived separately after verification; shoppers use only media files.

### Image browser verification

Use the existing database, without reseeding. Run `uv run python manage.py migrate`
and `uv run python manage.py tailwind runserver`. Use separate employee,
superuser and customer browser sessions.

1. As employee, create a disposable product with a valid JPEG/PNG/WebP, then edit
   it. Check the current preview, replace it, save an unrelated edit, and remove
   the image. Expect replacement to appear, unrelated edits to preserve it, and
   removal to restore the placeholder. Repeat in `/admin/` as superuser. A
   customer must get 403 at `/backoffice/products/` and its create/edit URLs.
2. With an existing image, try a renamed unsupported file, a corrupt/truncated
   image, an animated PNG/WebP, a file over 10 MiB, dimensions over 20 million
   pixels, and an image with either side below 400. Expect inline errors and the
   previous image unchanged. Also submit a valid image with an invalid price:
   nothing should save until the complete form is valid.
3. Review catalog, category and detail at mobile and desktop widths, using
   portrait art, landscape MindSync Duo, text-bearing art and placeholders.
   Confirm square aligned frames, complete uncropped images, visible text and
   transparency, and stable layout. In browser Network, cards request
   `-catalog.webp` with lazy loading; detail requests `-detail.webp` normally.
   Original marketing PNGs must not be requested.
4. On a disposable test product only, note its media paths, temporarily rename
   its `-catalog.webp` file and reload the catalog/category: expect a placeholder
   while detail still works. Restore it, then repeat with `-detail.webp`: only
   detail falls back. Restore both files afterward.
5. Run the marketing command when ready and review its report and assignments,
   including Mark I and text-free SyncRest. Rerun: existing images must be skipped.
   Use `--source` with a disposable copy containing a missing/corrupt file to
   exercise individual failures on products without images. Valid assignments
   should still import. Temporarily rename that disposable source directory and
   reload imported products: their images must still display from media.
   Keep the supplied originals intact until verification is complete.
