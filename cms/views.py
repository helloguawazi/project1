from rest_framework import viewsets, generics, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import CmsCategory, Tag, Article, Page, Comment, MetaTag, SitemapEntry # Added MetaTag, SitemapEntry
from .serializers import (
    CmsCategorySerializer, TagSerializer, ArticleSerializer, 
    PageSerializer, CommentSerializer, MetaTagSerializer, SitemapEntrySerializer # Added MetaTagSerializer, SitemapEntrySerializer
)

class CmsCategoryViewSet(viewsets.ModelViewSet):
    queryset = CmsCategory.objects.all().prefetch_related('articles')
    serializer_class = CmsCategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name']

class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all().prefetch_related('articles')
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']

class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.filter(is_published=True).select_related('author').prefetch_related('categories', 'tags', 'comments')
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] # Allow read for anyone, write for authenticated authors/staff
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        'categories__slug': ['exact'],
        'tags__slug': ['exact'],
        'author__username': ['exact'],
        'is_featured': ['exact'],
        'is_published': ['exact'], # Allow filtering for published/unpublished by admins
    }
    search_fields = ['title', 'content', 'categories__name', 'tags__name', 'author__username']
    ordering_fields = ['published_at', 'created_at', 'updated_at', 'title']
    lookup_field = 'slug' # Use slug for retrieving articles

    def get_queryset(self):
        queryset = super().get_queryset()
        # For non-authenticated users or non-staff, only show published articles
        if not self.request.user.is_authenticated or not self.request.user.is_staff:
            queryset = queryset.filter(is_published=True, published_at__lte=timezone.now())
        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        # If is_published is being set to True and was False, set published_at
        instance = serializer.instance
        if serializer.validated_data.get('is_published') and not instance.is_published:
            serializer.save(author=self.request.user, published_at=timezone.now())
        else:
            serializer.save(author=self.request.user)


# SEO Related Views
from django.contrib.contenttypes.models import ContentType

class MetaTagViewSet(viewsets.ModelViewSet):
    queryset = MetaTag.objects.all().select_related('content_type')
    serializer_class = MetaTagSerializer
    permission_classes = [permissions.IsAdminUser] # Meta tags typically managed by admins/SEO specialists
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        'name': ['exact', 'icontains'],
        'content_type__app_label': ['exact'],
        'content_type__model': ['exact'],
        'object_id': ['exact'],
    }
    search_fields = ['name', 'content']
    ordering_fields = ['name', 'created_at', 'content_type']

    @action(detail=False, methods=['get'], url_path='get-for-object', permission_classes=[permissions.AllowAny]) # Allow reading meta tags for content
    def get_for_object(self, request):
        """
        Retrieves meta tags for a specific content object.
        Query params: content_type_model (e.g., 'cms.article'), object_id
        """
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

        # Optional: Check if the actual content object exists (can be slow if done for many requests)
        # related_model_class = content_type.model_class()
        # if not related_model_class.objects.filter(pk=object_id).exists():
        #    return Response({'detail': 'Content object not found.'}, status=status.HTTP_404_NOT_FOUND)

        tags = MetaTag.objects.filter(content_type=content_type, object_id=object_id)
        serializer = self.get_serializer(tags, many=True)
        return Response(serializer.data)


class SitemapEntryViewSet(viewsets.ModelViewSet): # Changed from ReadOnlyModelViewSet to ModelViewSet for CRUD
    queryset = SitemapEntry.objects.all()
    serializer_class = SitemapEntrySerializer
    permission_classes = [permissions.IsAdminUser] # Sitemap entries typically managed by admins or system
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['change_frequency', 'priority']
    search_fields = ['location_url']
    ordering_fields = ['priority', 'last_modified', 'location_url']

    # Public list view for generating sitemap.xml (could be a separate, non-DRF view too)
    @action(detail=False, methods=['get'], url_path='view-sitemap', permission_classes=[permissions.AllowAny])
    def view_sitemap(self, request):
        # This action provides the data. Rendering to XML would typically be done
        # by a Django view using a template, or a dedicated sitemap generation library.
        # For an API, just returning the list of entries is fine.
        queryset = self.filter_queryset(self.get_queryset().order_by('-priority', '-last_modified'))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


    @action(detail=False, methods=['get'], url_path='featured')
    def featured_articles(self, request):
        featured = self.get_queryset().filter(is_featured=True)
        page = self.paginate_queryset(featured)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(featured, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='recent')
    def recent_articles(self, request):
        # Order by published_at, limit to a certain number (e.g., 10)
        recent = self.get_queryset().order_by('-published_at')[:10]
        serializer = self.get_serializer(recent, many=True)
        return Response(serializer.data)

    # Comments related actions
    @action(detail=True, methods=['post'], url_path='add-comment', serializer_class=CommentSerializer)
    def add_comment(self, request, slug=None):
        article = self.get_object()
        serializer = CommentSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user if request.user.is_authenticated else None
            name = serializer.validated_data.get('name', '')
            if user: # If user is authenticated, override name with username
                name = user.username
            
            Comment.objects.create(
                article=article, 
                user=user,
                name=name, # Use username or provided name
                email=serializer.validated_data.get('email', ''),
                content=serializer.validated_data['content'],
                is_approved= not user # Auto-approve comments from authenticated users, others might need moderation
            )
            # Return the article with updated comments or just a success message
            return Response(self.get_serializer(article).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='comments')
    def list_comments(self, request, slug=None):
        article = self.get_object()
        comments = Comment.objects.filter(article=article, is_approved=True) # Only show approved comments
        # TODO: Add pagination for comments
        serializer = CommentSerializer(comments, many=True, context={'request': request})
        return Response(serializer.data)


class PageViewSet(viewsets.ModelViewSet):
    queryset = Page.objects.filter(is_published=True)
    serializer_class = PageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] # Similar to Articles
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['title', 'content']
    ordering_fields = ['title', 'published_at']
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_authenticated or not self.request.user.is_staff:
            queryset = queryset.filter(is_published=True, published_at__lte=timezone.now())
        return queryset
        
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.instance
        if serializer.validated_data.get('is_published') and not instance.is_published:
            serializer.save(author=self.request.user, published_at=timezone.now())
        else:
            serializer.save(author=self.request.user)


# View for creating comments (could also be an action in ArticleViewSet)
# This is somewhat redundant if using the action in ArticleViewSet but provides a separate endpoint if desired.
class CommentCreateView(generics.CreateAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] # Allow anonymous (with name/email) or authenticated

    def perform_create(self, serializer):
        article_id = self.request.data.get('article_id') # Expecting article_id in request body
        try:
            article = Article.objects.get(id=article_id, is_published=True)
        except Article.DoesNotExist:
            raise serializers.ValidationError({'article_id': 'Published article not found.'})
        
        user = self.request.user if self.request.user.is_authenticated else None
        name = serializer.validated_data.get('name', '')
        if user:
            name = user.username

        serializer.save(
            article=article, 
            user=user, 
            name=name,
            is_approved= not user # Auto-approve for logged-in users
        )
