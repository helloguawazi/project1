from django.urls import path
from . import views

app_name = 'shop_ui'

urlpatterns = [
    path('categories/', views.category_list_view, name='category_list'),
    path('categories/create/', views.category_create_view, name='category_create'),
    path('categories/<slug:category_slug>/edit/', views.category_edit_view, name='category_edit'),
    
    path('products/', views.product_list_view, name='product_list'),
    path('products/create/', views.product_create_view, name='product_create'),
    path('products/<slug:product_slug>/edit/', views.product_edit_view, name='product_edit'),
    
    # TODO: Add URLs for managing product images and attributes if they get dedicated pages
    # e.g., path('products/<slug:product_slug>/images/', views.product_images_view, name='product_images'),
]
