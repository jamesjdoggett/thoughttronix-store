## Featured Products

 Question 1 - Trace the feature: Checking Featured in admin saves is_featured=True on the Product model. catalog.html and detail.html check {% if product.is_featured %} and display the badge when true.

 Question 2 - How I verified it: I checked the main catalog and the detail pages for Seraphine. SoulSear Mark 1 and 2. The three that I selected showed the featured badge while the others didn't. Also all 176 tests ran successfully. 

 Question 3 - Judgement: My terminal was still showing the old django-test virtual environment, but uv explained that it ignored theat environment annd used Thoughttronix's .venv. The migration and tests still completed successfully. 