## Featured Products

 Question 1 - Trace the feature: Checking Featured in admin saves is_featured=True on the Product model. catalog.html and detail.html check {% if product.is_featured %} and display the badge when true.

 Question 2 - How I verified it: I checked the main catalog and the detail pages for Seraphine. SoulSear Mark 1 and 2. The three that I selected showed the featured badge while the others didn't. Also all 176 tests ran successfully. 

 Question 3 - Judgement: My terminal was still showing the old django-test virtual environment, but uv explained that it ignored theat environment annd used Thoughttronix's .venv. The migration and tests still completed successfully. 

 ## Discount Coupons

Question 1 — A decision from the interview: I was unsure what “product-specific discount” would mean when a customer had other products in the same cart, so I asked Codex for a mixed-cart example before approving the plan. It used two Seraphines at $249 each and an ineligible $100 accessory. The subtotal was $598. A 50% Seraphine coupon took $249 off the Seraphine line and nothing off the accessory, leaving a $349 total. That example made the rule clear to me, and proved that it seemed to work. At checkout, the quote calculates the discount on eligible cart lines, rounds each line to cents, and shows the subtotal, savings, and final total before the customer places the order. Order placement checks the coupon and pricing again, then saves the coupon code, percentage, totals, and line discounts on the order. That saved information is why retiring or editing a coupon later does not change an old order.

Question 2 — My change after review: The original product picker on the New coupon page was difficult to use. When I opened it in the browser, the product names looked jumbled, and I could not select Seraphine. I showed Codex a screenshot and asked it to fix the picker. It changed the form to a scrollable list of labeled checkboxes, which I refreshed and verified in the browser. I could then select Seraphine, and the problem was fixed. The full suite of 233 tests seemed to pass to my knowledge. 