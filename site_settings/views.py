from rest_framework import viewsets, permissions, status, serializers # Added serializers for ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.core.cache import cache # For cache clearing action, if needed beyond model signals

from .models import Setting
from .serializers import SettingSerializer

class SettingViewSet(viewsets.ModelViewSet):
    queryset = Setting.objects.all()
    serializer_class = SettingSerializer
    permission_classes = [permissions.IsAdminUser] # Only admins can manage settings
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['group', 'key', 'value_type', 'is_public', 'is_editable']
    search_fields = ['key', 'value', 'group', 'description']
    ordering_fields = ['group', 'key', 'updated_at']
    lookup_field = 'key' # Allow lookup by key instead of pk

    def perform_update(self, serializer):
        instance = self.get_object()
        # Check is_editable before saving if value or value_type is being changed by API user
        # The serializer already has a check, this is an additional view-level check if needed,
        # or if serializer's check needs instance context not easily available there.
        if not instance.is_editable:
            # Check if restricted fields are being changed
            restricted_changed = False
            if 'value' in serializer.validated_data and serializer.validated_data['value'] != instance.value:
                restricted_changed = True
            if 'value_type' in serializer.validated_data and serializer.validated_data['value_type'] != instance.value_type:
                 restricted_changed = True
            
            if restricted_changed:
                # Re-validate with the instance context if serializer didn't catch it
                # (though the current SettingSerializer.validate should handle this)
                raise serializers.ValidationError(f"Setting '{instance.key}' value or type is not editable via API.")
        serializer.save()

    @action(detail=False, methods=['get'], url_path='group/(?P<group_name>[^/.]+)', permission_classes=[permissions.IsAdminUser])
    def get_by_group(self, request, group_name=None):
        """Retrieves all settings belonging to a specific group."""
        if not group_name:
            return Response({'detail': 'Group name is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        settings_in_group = Setting.objects.filter(group__iexact=group_name)
        if not settings_in_group.exists():
            return Response({'detail': f"No settings found for group '{group_name}'."}, status=status.HTTP_404_NOT_FOUND)
            
        serializer = self.get_serializer(settings_in_group, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='public', permission_classes=[permissions.AllowAny]) # Publicly accessible
    def public_settings(self, request):
        """Retrieves all settings marked as public."""
        public_settings_dict = Setting.get_public_settings()
        return Response(public_settings_dict)

    @action(detail=False, methods=['post'], url_path='clear-cache', permission_classes=[permissions.IsAdminUser])
    def clear_cache_all(self, request):
        """Clears all cached settings from the Django cache."""
        cleared_count = Setting.clear_all_settings_cache()
        return Response({'detail': f'Successfully cleared cache for {cleared_count} settings.'})

    @action(detail=True, methods=['post'], url_path='clear-key-cache', permission_classes=[permissions.IsAdminUser])
    def clear_key_cache(self, request, key=None): # 'key' here is the lookup_field value
        """Clears cache for a specific setting key."""
        setting_instance = self.get_object() # Gets instance based on lookup_field 'key'
        Setting.clear_all_settings_cache(specific_keys=[setting_instance.key])
        return Response({'detail': f"Cache cleared for setting '{setting_instance.key}'."})

    # Configuration of common parameters like page titles and sidebar layout is achieved by
    # creating/updating 'Setting' instances with appropriate keys:
    # e.g., key='SITE_TITLE', value='My Awesome Project', value_type='string'
    # e.g., key='SIDEBAR_LAYOUT', value='{"theme": "dark", "default_state": "expanded"}', value_type='json'
    # These can be created via the standard POST endpoint of this ViewSet by an admin.
    # The application then uses `Setting.get_setting('KEY_NAME')` to retrieve these values.
    # For example, a base Django template could fetch 'SITE_TITLE':
    # {% load site_settings_tags %} <!-- Assuming a custom template tag -->
    # <title>{% get_site_setting 'SITE_TITLE' default='Default Title' %}</title>
    # Or in a view: site_title = Setting.get_setting('SITE_TITLE', 'Default Title')
    # This provides a flexible mechanism.
    # The `is_public=True` flag allows frontend applications to fetch these settings if needed.
