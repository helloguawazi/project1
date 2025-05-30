from django.urls import path
from . import views

app_name = 'cms_ui'

urlpatterns = [
    path('articles/', views.article_list_view, name='article_list'),
    path('articles/create/', views.article_create_view, name='article_create'),
    path('articles/<slug:article_slug>/edit/', views.article_edit_view, name='article_edit'),

    path('pages/', views.page_list_view, name='page_list'),
    path('pages/create/', views.page_create_view, name='page_create'),
    path('pages/<slug:page_slug>/edit/', views.page_edit_view, name='page_edit'),

    path('categories/', views.cms_category_list_view, name='cms_category_list'),
    path('categories/create/', views.cms_category_create_view, name='cms_category_create'),
    path('categories/<slug:category_slug>/edit/', views.cms_category_edit_view, name='cms_category_edit'),

    path('tags/', views.tag_list_view, name='tag_list'),
    path('tags/create/', views.tag_create_view, name='tag_create'),
    path('tags/<slug:tag_slug>/edit/', views.tag_edit_view, name='tag_edit'),
]
