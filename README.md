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
