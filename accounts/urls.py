from django.urls import path
from .views import RegisterView, UserProfileView, ProfileDetailView, ChangePasswordView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    path('profile/details/', ProfileDetailView.as_view(), name='profile_details'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
]
