## Product Images

Question 1 — One decision from grill me:

I accepted all the agent’s recommendations and did not ask any follow-up questions. One important decision was whether to import the supplied images with a command or upload each one manually through the back office. I chose the recommended import command because it avoided uploading every image individually. Employees can still use the back office for future uploads. The command also preserves existing images and reports imports, skips, and failures.

Question 2 — Find the upload code:

The image fields are in `products/models.py`, lines 67–68:

```python
image_catalog = models.ImageField(upload_to="products/", blank=True, editable=False)
image_detail = models.ImageField(upload_to="products/", blank=True, editable=False)
```

`upload_to="products/"` specifies a subfolder within the configured media storage. In this implementation, `prepare_image()` explicitly creates the filenames under `products/` and saves them through Django’s storage system. The database stores the relative filenames rather than the image contents.

The opening upload form tag is in `templates/products/manage_product_form.html`, line 16:

```html
<form method="post" enctype="multipart/form-data" class="mt-2 space-y-4">
```

The `enctype` allows the browser to send the image file along with the text fields. Django receives the uploaded file through `request.FILES`.

Question 3 — Follow the upload process:

My invented product is the FocusHalo. Its uploaded image was converted into two optimized WebP files.

The files are stored on disk at:

```text
C:\Users\james\cidm3312\thoughttronix-store\media\products\4b08f0a5af5b4dbcbe4b894a71ebd31d-catalog.webp
C:\Users\james\cidm3312\thoughttronix-store\media\products\4b08f0a5af5b4dbcbe4b894a71ebd31d-detail.webp
```

`MEDIA_ROOT` in `config/settings.py`, line 135, determines the media directory. `prepare_image()` in `products/models.py`, lines 121–137, creates the relative filenames and saves the files.

The database values are:

```text
image_catalog: products/4b08f0a5af5b4dbcbe4b894a71ebd31d-catalog.webp
image_detail: products/4b08f0a5af5b4dbcbe4b894a71ebd31d-detail.webp
```

These values are stored in the `image_catalog` and `image_detail` fields defined in `products/models.py`, lines 67–68.

The browser requests:

```text
http://127.0.0.1:8000/media/products/4b08f0a5af5b4dbcbe4b894a71ebd31d-catalog.webp
http://127.0.0.1:8000/media/products/4b08f0a5af5b4dbcbe4b894a71ebd31d-detail.webp
```

`MEDIA_URL` in `config/settings.py`, line 136, supplies the `/media/` prefix. The image fields’ storage generates their URLs, and the catalog and detail templates display the corresponding version.

In `config/urls.py`, line 19, this code makes the media URLs work during development:

```python
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

With `DEBUG=True`, it serves files from `MEDIA_ROOT` at the `MEDIA_URL` prefix.

## Discount Coupons

Question 1 — A decision from the interview: I was unsure what “product-specific discount” would mean when a customer had other products in the same cart, so I asked Codex for a mixed-cart example before approving the plan. It used two Seraphines at $249 each and an ineligible $100 accessory. The subtotal was $598. A 50% Seraphine coupon took $249 off the Seraphine line and nothing off the accessory, leaving a $349 total. That example made the rule clear to me, and proved that it seemed to work. At checkout, the quote calculates the discount on eligible cart lines, rounds each line to cents, and shows the subtotal, savings, and final total before the customer places the order. Order placement checks the coupon and pricing again, then saves the coupon code, percentage, totals, and line discounts on the order. That saved information is why retiring or editing a coupon later does not change an old order.

Question 2 — My change after review: The original product picker on the New coupon page was difficult to use. When I opened it in the browser, the product names looked jumbled, and I could not select Seraphine. I showed Codex a screenshot and asked it to fix the picker. It changed the form to a scrollable list of labeled checkboxes, which I refreshed and verified in the browser. I could then select Seraphine, and the problem was fixed. The full suite of 233 tests seemed to pass to my knowledge. 

## Featured Products

 Question 1 - Trace the feature: Checking Featured in admin saves is_featured=True on the Product model. catalog.html and detail.html check {% if product.is_featured %} and display the badge when true.

 Question 2 - How I verified it: I checked the main catalog and the detail pages for Seraphine. SoulSear Mark 1 and 2. The three that I selected showed the featured badge while the others didn't. Also all 176 tests ran successfully. 

 Question 3 - Judgement: My terminal was still showing the old django-test virtual environment, but uv explained that it ignored theat environment annd used Thoughttronix's .venv. The migration and tests still completed successfully. 

