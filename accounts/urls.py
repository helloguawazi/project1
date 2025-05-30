from django.urls import path
from . import views

app_name = 'accounts_ui' # Different from 'accounts' if that was used for API, or ensure API uses a different one.

urlpatterns = [
    path('', views.user_list_view, name='user_list'),
    path('create/', views.user_create_view, name='user_create'),
    path('<int:user_id>/edit/', views.user_edit_view, name='user_edit'),
    # Add other user/profile related template view URLs here
    # e.g., path('<int:user_id>/profile/', views.profile_view, name='profile_view'),
]
