from django.urls import path

from . import review_views, views

app_name = "products"

urlpatterns = [
    path("", views.CatalogView.as_view(), name="catalog"),
    path("products/<slug:slug>/", views.ProductDetailView.as_view(), name="detail"),
    path(
        "products/<slug:slug>/reviews/",
        review_views.ReviewCreateView.as_view(),
        name="review_create",
    ),
    path(
        "products/<slug:slug>/reviews/<int:pk>/edit/",
        review_views.ReviewEditView.as_view(),
        name="review_edit",
    ),
    path(
        "products/<slug:slug>/reviews/<int:pk>/delete/",
        review_views.ReviewDeleteView.as_view(),
        name="review_delete",
    ),
    path("categories/<slug:slug>/", views.CategoryView.as_view(), name="category"),
    # Back office — staff-only, pk URLs per the URL conventions.
    path(
        "backoffice/products/",
        views.ManageProductListView.as_view(),
        name="manage_products",
    ),
    path(
        "backoffice/products/add/",
        views.ManageProductCreateView.as_view(),
        name="manage_product_create",
    ),
    path(
        "backoffice/products/<int:pk>/edit/",
        views.ManageProductUpdateView.as_view(),
        name="manage_product_update",
    ),
    path(
        "backoffice/products/<int:pk>/delete/",
        views.ManageProductDeleteView.as_view(),
        name="manage_product_delete",
    ),
    path(
        "backoffice/catalog/",
        views.ManageCatalogView.as_view(),
        name="manage_catalog",
    ),
    path(
        "backoffice/categories/add/",
        views.ManageCategoryCreateView.as_view(),
        name="manage_category_create",
    ),
    path(
        "backoffice/categories/<int:pk>/edit/",
        views.ManageCategoryUpdateView.as_view(),
        name="manage_category_update",
    ),
    path(
        "backoffice/tags/add/",
        views.ManageTagCreateView.as_view(),
        name="manage_tag_create",
    ),
    path(
        "backoffice/tags/<int:pk>/edit/",
        views.ManageTagUpdateView.as_view(),
        name="manage_tag_update",
    ),
]
