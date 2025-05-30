from django.shortcuts import render, get_object_or_404, redirect # For template views
from django.contrib.auth.decorators import login_required # For template views
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db import transaction as django_db_transaction # Not strictly needed here yet, but good for complex saves

from .forms import ArticleForm, PageForm, CmsCategoryForm, TagForm, CommentAdminForm

# Existing DRF API View imports
from rest_framework import viewsets, generics, permissions, status # Ensure status is imported
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.contrib.contenttypes.models import ContentType # For MetaTag view

from .models import CmsCategory, Tag, Article, Page, Comment, MetaTag, SitemapEntry # Added MetaTag, SitemapEntry
from .serializers import (
    CmsCategorySerializer, TagSerializer, ArticleSerializer, 
    PageSerializer, CommentSerializer, MetaTagSerializer, SitemapEntrySerializer # Added MetaTagSerializer, SitemapEntrySerializer
)

# API ViewSets (Keep all existing API Viewsets as they are)
# CmsCategoryViewSet, TagViewSet, ArticleViewSet, PageViewSet, MetaTagViewSet, SitemapEntryViewSet
# ... (all existing API view code remains here) ...
class CmsCategoryViewSet(viewsets.ModelViewSet):
    queryset = CmsCategory.objects.all().prefetch_related('articles')
    serializer_class = CmsCategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['slug']
    search_fields = ['name', 'description']
    ordering_fields = ['name']
    lookup_field = 'slug'

class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all().prefetch_related('articles')
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['slug']
    search_fields = ['name']
    ordering_fields = ['name']
    lookup_field = 'slug'

class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.filter(is_published=True).select_related('author').prefetch_related('categories', 'tags', 'comments')
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] 
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        'categories__slug': ['exact'],
        'tags__slug': ['exact'],
        'author__username': ['exact'],
        'is_featured': ['exact'],
        'is_published': ['exact'], 
    }
    search_fields = ['title', 'content', 'categories__name', 'tags__name', 'author__username']
    ordering_fields = ['published_at', 'created_at', 'updated_at', 'title']
    lookup_field = 'slug' 

    def get_queryset(self):
        queryset = Article.objects.all() # Start with all for staff/admin
        if not self.request.user.is_staff: # Filter for non-staff
            queryset = queryset.filter(is_published=True, published_at__lte=timezone.now())
        return queryset.select_related('author').prefetch_related('categories', 'tags', 'comments')


    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.instance
        if serializer.validated_data.get('is_published') and not instance.is_published:
            serializer.save(published_at=timezone.now()) # Author already set, or can be updated if needed
        else:
            serializer.save()


    @action(detail=False, methods=['get'], url_path='featured')
    def featured_articles(self, request):
        featured = self.get_queryset().filter(is_featured=True, is_published=True, published_at__lte=timezone.now())
        page = self.paginate_queryset(featured)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(featured, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='recent')
    def recent_articles(self, request):
        recent = self.get_queryset().filter(is_published=True, published_at__lte=timezone.now()).order_by('-published_at')[:10]
        serializer = self.get_serializer(recent, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='add-comment', serializer_class=CommentSerializer)
    def add_comment(self, request, slug=None):
        article = self.get_object()
        serializer = CommentSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user if request.user.is_authenticated else None
            name = serializer.validated_data.get('name', '')
            if user: 
                name = user.username
            
            Comment.objects.create(
                article=article, user=user, name=name,
                email=serializer.validated_data.get('email', ''),
                content=serializer.validated_data['content'],
                is_approved= not user 
            )
            return Response(self.get_serializer(article).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='comments')
    def list_comments(self, request, slug=None):
        article = self.get_object()
        # For API, maybe show unapproved to article author or admin
        # For now, only approved
        comments = Comment.objects.filter(article=article, is_approved=True) 
        serializer = CommentSerializer(comments, many=True, context={'request': request})
        return Response(serializer.data)


class PageViewSet(viewsets.ModelViewSet):
    queryset = Page.objects.all() # Show all for staff/admin
    serializer_class = PageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] 
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['is_published']
    search_fields = ['title', 'content']
    ordering_fields = ['title', 'published_at']
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff: # Filter for non-staff
            queryset = queryset.filter(is_published=True, published_at__lte=timezone.now())
        return queryset.select_related('author')
        
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.instance
        if serializer.validated_data.get('is_published') and not instance.is_published:
            serializer.save(published_at=timezone.now())
        else:
            serializer.save()

class MetaTagViewSet(viewsets.ModelViewSet):
    queryset = MetaTag.objects.all().select_related('content_type')
    serializer_class = MetaTagSerializer
    permission_classes = [permissions.IsAdminUser] 
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        'name': ['exact', 'icontains'],
        'content_type__app_label': ['exact'],
        'content_type__model': ['exact'],
        'object_id': ['exact'],
    }
    search_fields = ['name', 'content']
    ordering_fields = ['name', 'created_at', 'content_type']

    @action(detail=False, methods=['get'], url_path='get-for-object', permission_classes=[permissions.AllowAny]) 
    def get_for_object(self, request):
        content_type_model_str = request.query_params.get('content_type_model')
        object_id_str = request.query_params.get('object_id')
        if not content_type_model_str or not object_id_str:
            return Response({'detail': "Parameters 'content_type_model' (app_label.model) and 'object_id' are required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            app_label, model_name = content_type_model_str.split('.')
            content_type = ContentType.objects.get(app_label=app_label, model=model_name)
            object_id = int(object_id_str)
        except (ContentType.DoesNotExist, ValueError, TypeError):
            return Response({'detail': "Invalid 'content_type_model' or 'object_id'."}, status=status.HTTP_400_BAD_REQUEST)
        tags = MetaTag.objects.filter(content_type=content_type, object_id=object_id)
        serializer = self.get_serializer(tags, many=True)
        return Response(serializer.data)

class SitemapEntryViewSet(viewsets.ModelViewSet): 
    queryset = SitemapEntry.objects.all()
    serializer_class = SitemapEntrySerializer
    permission_classes = [permissions.IsAdminUser] 
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['change_frequency', 'priority']
    search_fields = ['location_url']
    ordering_fields = ['priority', 'last_modified', 'location_url']

    @action(detail=False, methods=['get'], url_path='view-sitemap', permission_classes=[permissions.AllowAny])
    def view_sitemap(self, request):
        queryset = self.filter_queryset(self.get_queryset().order_by('-priority', '-last_modified'))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

# Django Template Views for CMS Management (AdminLTE)
@staff_member_required
def article_list_view(request):
    articles = Article.objects.all().select_related('author').prefetch_related('categories', 'tags').order_by('-created_at')
    context = {
        'articles': articles,
        'page_title': 'Article List',
        'breadcrumb_active': 'Articles'
    }
    return render(request, 'cms/article_list.html', context)

@staff_member_required
def article_create_view(request):
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES or None)
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            # Handle published_at based on is_published
            if form.cleaned_data.get('is_published') and not form.cleaned_data.get('published_at'):
                article.published_at = timezone.now()
            elif not form.cleaned_data.get('is_published'): # Ensure published_at is cleared if not published
                article.published_at = None
            article.save()
            form.save_m2m() # Important for ManyToMany fields like categories and tags
            messages.success(request, f"Article '{article.title}' created successfully.")
            return redirect('cms_ui:article_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ArticleForm()
    
    context = {
        'form': form,
        'form_type': 'create',
        'page_title': 'Create Article',
        'breadcrumb_active': 'Create Article'
    }
    return render(request, 'cms/article_form.html', context)

@staff_member_required
def article_edit_view(request, article_slug):
    article = get_object_or_404(Article.objects.prefetch_related('categories', 'tags', 'comments'), slug=article_slug)
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES or None, instance=article)
        if form.is_valid():
            edited_article = form.save(commit=False)
            if form.cleaned_data.get('is_published') and not form.cleaned_data.get('published_at'):
                edited_article.published_at = timezone.now()
            elif not form.cleaned_data.get('is_published'):
                 edited_article.published_at = None
            edited_article.save()
            form.save_m2m()
            messages.success(request, f"Article '{article.title}' updated successfully.")
            return redirect('cms_ui:article_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ArticleForm(instance=article)
        
    context = {
        'form': form,
        'article_instance': article,
        'form_type': 'edit',
        'page_title': f'Edit Article: {article.title}',
        'breadcrumb_active': 'Edit Article'
    }
    return render(request, 'cms/article_form.html', context)

@staff_member_required
def cms_category_list_view(request):
    categories = CmsCategory.objects.all().order_by('name')
    context = {
        'cms_categories': categories, # Changed context key for clarity
        'page_title': 'CMS Categories',
        'breadcrumb_active': 'CMS Categories'
    }
    return render(request, 'cms/cms_category_list.html', context)

@staff_member_required
def cms_category_create_view(request):
    if request.method == 'POST':
        form = CmsCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"CMS Category '{form.cleaned_data['name']}' created successfully.")
            return redirect('cms_ui:cms_category_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CmsCategoryForm()
    context = {
        'form': form,
        'form_type': 'create',
        'page_title': 'Create CMS Category',
        'breadcrumb_active': 'Create CMS Category'
    }
    return render(request, 'cms/cms_category_form.html', context)

@staff_member_required
def cms_category_edit_view(request, category_slug):
    category = get_object_or_404(CmsCategory, slug=category_slug)
    if request.method == 'POST':
        form = CmsCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f"CMS Category '{category.name}' updated successfully.")
            return redirect('cms_ui:cms_category_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CmsCategoryForm(instance=category)
    context = {
        'form': form,
        'category_instance': category,
        'form_type': 'edit',
        'page_title': f'Edit CMS Category: {category.name}',
        'breadcrumb_active': 'Edit CMS Category'
    }
    return render(request, 'cms/cms_category_form.html', context)


@staff_member_required
def tag_list_view(request):
    tags = Tag.objects.all().order_by('name')
    context = {
        'tags': tags,
        'page_title': 'CMS Tags',
        'breadcrumb_active': 'Tags'
    }
    return render(request, 'cms/tag_list.html', context)

@staff_member_required
def tag_create_view(request):
    if request.method == 'POST':
        form = TagForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Tag '{form.cleaned_data['name']}' created successfully.")
            return redirect('cms_ui:tag_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = TagForm()
    context = {
        'form': form,
        'form_type': 'create',
        'page_title': 'Create Tag',
        'breadcrumb_active': 'Create Tag'
    }
    return render(request, 'cms/tag_form.html', context)

@staff_member_required
def tag_edit_view(request, tag_slug):
    tag = get_object_or_404(Tag, slug=tag_slug)
    if request.method == 'POST':
        form = TagForm(request.POST, instance=tag)
        if form.is_valid():
            form.save()
            messages.success(request, f"Tag '{tag.name}' updated successfully.")
            return redirect('cms_ui:tag_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = TagForm(instance=tag)
    context = {
        'form': form,
        'tag_instance': tag,
        'form_type': 'edit',
        'page_title': f'Edit Tag: {tag.name}',
        'breadcrumb_active': 'Edit Tag'
    }
    return render(request, 'cms/tag_form.html', context)

# Page Management (Simplified for now, similar to Articles)
@staff_member_required
def page_list_view(request):
    pages = Page.objects.all().select_related('author').order_by('-created_at')
    context = {
        'pages_list': pages, 
        'page_title': 'Page List',
        'breadcrumb_active': 'Pages'
    }
    return render(request, 'cms/page_list.html', context)

@staff_member_required
def page_create_view(request):
    if request.method == 'POST':
        form = PageForm(request.POST, request.FILES or None)
        if form.is_valid():
            page_obj = form.save(commit=False)
            page_obj.author = request.user
            if form.cleaned_data.get('is_published') and not form.cleaned_data.get('published_at'):
                page_obj.published_at = timezone.now()
            elif not form.cleaned_data.get('is_published'):
                 page_obj.published_at = None
            page_obj.save()
            messages.success(request, f"Page '{page_obj.title}' created successfully.")
            return redirect('cms_ui:page_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PageForm()
    context = {
        'form': form,
        'form_type': 'create',
        'page_title': 'Create Page',
        'breadcrumb_active': 'Create Page'
    }
    return render(request, 'cms/page_form.html', context)

@staff_member_required
def page_edit_view(request, page_slug):
    page_obj = get_object_or_404(Page, slug=page_slug)
    if request.method == 'POST':
        form = PageForm(request.POST, request.FILES or None, instance=page_obj)
        if form.is_valid():
            edited_page = form.save(commit=False)
            if form.cleaned_data.get('is_published') and not form.cleaned_data.get('published_at'):
                edited_page.published_at = timezone.now()
            elif not form.cleaned_data.get('is_published'):
                edited_page.published_at = None
            edited_page.save()
            messages.success(request, f"Page '{page_obj.title}' updated successfully.")
            return redirect('cms_ui:page_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PageForm(instance=page_obj)
    context = {
        'form': form,
        'page_instance': page_obj,
        'form_type': 'edit',
        'page_title': f'Edit Page: {page_obj.title}',
        'breadcrumb_active': 'Edit Page'
    }
    return render(request, 'cms/page_form.html', context)

# TODO: Comment management views (list all, approve, delete) could be added later if needed as separate UI.
# Currently, comments are listed on article API detail and can be added there.
# MetaTag and SitemapEntry views are API only for now as per previous subtasks.
# If UI is needed for MetaTag/SitemapEntry, similar form/view/template structure would apply.
