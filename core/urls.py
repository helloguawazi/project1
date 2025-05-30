"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import ( # Although not used by dashboard directly, keep for API
    TokenObtainPairView,
    TokenRefreshView,
)
from django.contrib.auth import views as auth_views # Django auth views
# Import dashboard views if you want to make it the root
from dashboard.views import dashboard_view

urlpatterns = [
    path('admin/', admin.site.urls), # Django admin
    
    # Auth views
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'), # Redirect to login after logout

    path('', dashboard_view, name='dashboard_root'), # Dashboard as root
    path('dashboard/', include('dashboard.urls', namespace='dashboard')), # Dashboard app
    
    # API tokens (if you keep both session auth for templates and JWT for API)
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/accounts/', include('accounts.api_urls')), 
    path('api/shop/', include('shop.api_urls')), 
    path('api/cms/', include('cms.api_urls')), 
    path('api/finance/', include('finance.urls')),
    path('api/site-settings/', include('site_settings.urls')),

    # Management UI paths
    path('manage/users/', include('accounts.urls', namespace='accounts_ui')),
    path('manage/shop/', include('shop.urls', namespace='shop_ui')),
    path('manage/cms/', include('cms.urls', namespace='cms_ui')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
