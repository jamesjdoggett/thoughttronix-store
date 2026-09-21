# Codebase Map

1. **Apps and what they own:** Accounts handles users and login. Products handles the catalog, products, categories, and tags. Orders handles carts, checkout, and orders. Dashboard handles sales information for staff.

2. **Path of one request:** config/urls.py sends / to products/urls.py. That runs CatalogView from products/views.py, which gets the products and renders templates/products/catalog.html. That template uses templates/base.html.

3. **A model I read:** The Cart model represents one user’s shopping cart. Its add() method either adds a new product or increases its quantity if it is already in the cart.

4. **Deleting a category:** Django will not let you delete a category if products still belong to it. The on_delete=models.PROTECT line in products/models.py controls this.

5. **Where the tests live:** Tests are stored inside the app they test. The root conftest.py contains shared fixtures, which create reusable test users, products, carts, categories, and other test data.

6. **Something I’m still learning:** I would say orders/services.py was confusing at first. I asked why place_order() is separate from the view and learned that the view handles the webpage while the service handles the actual order process, making it easier to test and reuse.