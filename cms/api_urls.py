from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CmsCategoryViewSet, TagViewSet, ArticleViewSet, PageViewSet,
    # CommentCreateView, # Commented out as add_comment action is preferred
    MetaTagViewSet, SitemapEntryViewSet
)

router = DefaultRouter()
router.register(r'categories', CmsCategoryViewSet, basename='cms-category')
router.register(r'tags', TagViewSet, basename='tag')
router.register(r'articles', ArticleViewSet, basename='article')
router.register(r'pages', PageViewSet, basename='page')
router.register(r'meta-tags', MetaTagViewSet, basename='meta-tag')
router.register(r'sitemap-entries', SitemapEntryViewSet, basename='sitemap-entry')

urlpatterns = [
    path('', include(router.urls)),
]
